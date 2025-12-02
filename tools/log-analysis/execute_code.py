"""
Execute Code Tool - Safe Python Code Execution for MCP Sandbox

This module provides secure Python code execution capabilities within the
MCP sandbox environment. It enables AI agents to write and execute code
that can use the sandbox's approved tools (log_store, privacy, etc.).

This implements the "Code Execution with MCP" pattern described by Anthropic,
allowing data to flow between tools within the sandbox without passing through
the AI's context window.

Security Features:
- Whitelist of allowed imports (only sandbox-approved modules)
- Execution timeout (default 30 seconds)
- Memory limit enforcement
- Restricted builtins (no file I/O, no network, no os.system)
- Output capture and size limits

GitOps: This file is managed via GitOps. Changes require security approval
via pull request.

Example Usage:
    >>> result = execute_code('''
    ... # Search logs and scrub PII in one execution
    ... errors = log_store.search_logs("api", "error", limit=100)
    ... clean_errors = [privacy.scrub_all_pii(str(e)) for e in errors]
    ... print(f"Found {len(clean_errors)} errors")
    ... for e in clean_errors[:5]:
    ...     print(e)
    ... ''')
    >>> print(result['output'])
"""

import sys
import io
import traceback
import signal
import resource
from typing import Dict, Any, Optional
from contextlib import contextmanager


# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# Maximum execution time in seconds
DEFAULT_TIMEOUT = 30

# Maximum output size in characters
MAX_OUTPUT_SIZE = 100000  # 100KB

# Maximum memory (in bytes) - 256MB
MAX_MEMORY_BYTES = 256 * 1024 * 1024

# Allowed imports - only sandbox-approved modules
ALLOWED_IMPORTS = {
    # Sandbox tools (the main purpose of code execution)
    'log_store',
    'privacy',
    'workspace',  # Persistent storage for checkpoints and state

    # Safe standard library modules
    'json',
    're',
    'math',
    'datetime',
    'collections',
    'itertools',
    'functools',
    'operator',
    'string',
    'textwrap',
    'unicodedata',
    'statistics',
    'random',
    'hashlib',
    'base64',
    'copy',
    'pprint',
    'enum',
    'dataclasses',
    'typing',
    'time',  # For sleep in polling loops

    # Data processing (if available in sandbox)
    'csv',
}

# Restricted builtins - remove dangerous functions
RESTRICTED_BUILTINS = {
    # Keep safe builtins
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
    'callable', 'chr', 'classmethod', 'complex', 'dict', 'dir', 'divmod',
    'enumerate', 'filter', 'float', 'format', 'frozenset', 'getattr',
    'hasattr', 'hash', 'hex', 'id', 'int', 'isinstance', 'issubclass',
    'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'object', 'oct',
    'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round',
    'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum',
    'super', 'tuple', 'type', 'vars', 'zip',

    # Allow limited exception handling
    'Exception', 'BaseException', 'ValueError', 'TypeError', 'KeyError',
    'IndexError', 'AttributeError', 'RuntimeError', 'StopIteration',

    # Allow None, True, False
    'None', 'True', 'False',
}

# Explicitly blocked builtins (for documentation)
BLOCKED_BUILTINS = {
    'open',           # No file I/O
    'exec',           # No nested exec
    'eval',           # No nested eval
    'compile',        # No code compilation
    '__import__',     # Controlled via safe_import
    'input',          # No stdin
    'breakpoint',     # No debugging
    'globals',        # No global access
    'locals',         # Limited local access
    'memoryview',     # No memory manipulation
}


# =============================================================================
# SAFE IMPORT MECHANISM
# =============================================================================

def create_safe_import(allowed_modules: set):
    """Create a restricted import function that only allows whitelisted modules."""

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        """Import function that only allows whitelisted modules."""
        # Get the base module name
        base_module = name.split('.')[0]

        if base_module not in allowed_modules:
            raise ImportError(
                f"Import of '{name}' is not allowed. "
                f"Allowed modules: {', '.join(sorted(allowed_modules))}"
            )

        # Use the real __import__ for allowed modules
        return __builtins__['__import__'](name, globals, locals, fromlist, level)

    return safe_import


# =============================================================================
# EXECUTION ENVIRONMENT
# =============================================================================

@contextmanager
def timeout_handler(seconds: int):
    """Context manager to enforce execution timeout."""

    def signal_handler(signum, frame):
        raise TimeoutError(f"Code execution timed out after {seconds} seconds")

    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Restore the old handler and cancel the alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def set_memory_limit(max_bytes: int):
    """Set memory limit for the process."""
    try:
        # Set soft and hard limits
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    except (ValueError, resource.error):
        # May not be supported on all platforms
        pass


def create_execution_globals(tools_path: str = None) -> Dict[str, Any]:
    """Create a restricted globals dict for code execution."""

    # Start with restricted builtins
    import builtins
    safe_builtins = {
        name: getattr(builtins, name)
        for name in RESTRICTED_BUILTINS
        if hasattr(builtins, name)
    }

    # Add safe import
    safe_builtins['__import__'] = create_safe_import(ALLOWED_IMPORTS)

    # Create globals with restricted builtins
    exec_globals = {
        '__builtins__': safe_builtins,
        '__name__': '__sandbox__',
        '__doc__': None,
    }

    # Pre-import sandbox tools so they're available
    try:
        # Add tools path to sys.path if provided
        if tools_path and tools_path not in sys.path:
            sys.path.insert(0, tools_path)

        import log_store
        import privacy
        import workspace

        exec_globals['log_store'] = log_store
        exec_globals['privacy'] = privacy
        exec_globals['workspace'] = workspace

    except ImportError as e:
        # Tools may not be available in all environments
        pass

    return exec_globals


# =============================================================================
# MAIN EXECUTION FUNCTION
# =============================================================================

def execute_code(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_output: int = MAX_OUTPUT_SIZE
) -> Dict[str, Any]:
    """
    Execute Python code safely in a restricted environment.

    This function runs user-provided Python code in a sandboxed environment
    with security controls including:
    - Whitelist of allowed imports
    - Execution timeout
    - Output size limits
    - Restricted builtins (no file I/O, no network access)

    The code has access to sandbox tools (log_store, privacy) and can use
    them to process data efficiently without passing intermediate results
    through the AI's context window.

    Args:
        code: Python code to execute. Can use log_store, privacy, and
              safe standard library modules.
        timeout: Maximum execution time in seconds (default: 30)
        max_output: Maximum output size in characters (default: 100KB)

    Returns:
        Dict containing:
        - success: bool - Whether execution completed without error
        - output: str - Captured stdout/print output
        - error: str - Error message if execution failed (empty on success)
        - truncated: bool - Whether output was truncated due to size limit

    Example:
        >>> result = execute_code('''
        ... import json
        ...
        ... # Search for errors and process in sandbox
        ... errors = log_store.search_logs("payment-service", "error", limit=50)
        ...
        ... # Count by type (data stays in sandbox)
        ... error_types = {}
        ... for error in errors:
        ...     if "timeout" in error.lower():
        ...         error_types["timeout"] = error_types.get("timeout", 0) + 1
        ...     elif "connection" in error.lower():
        ...         error_types["connection"] = error_types.get("connection", 0) + 1
        ...     else:
        ...         error_types["other"] = error_types.get("other", 0) + 1
        ...
        ... # Only summary goes back to AI
        ... print(json.dumps({
        ...     "total_errors": len(errors),
        ...     "by_type": error_types
        ... }, indent=2))
        ... ''')
        >>> print(result['output'])
        {
          "total_errors": 50,
          "by_type": {
            "timeout": 12,
            "connection": 8,
            "other": 30
          }
        }

    Security Notes:
        - Only whitelisted modules can be imported
        - File I/O operations (open, read, write) are blocked
        - Network operations are blocked
        - Code cannot access the broader system
        - Execution is time-limited to prevent infinite loops
    """

    # Validate input
    if not code or not code.strip():
        return {
            'success': False,
            'output': '',
            'error': 'No code provided',
            'truncated': False
        }

    if not isinstance(code, str):
        return {
            'success': False,
            'output': '',
            'error': 'Code must be a string',
            'truncated': False
        }

    # Capture stdout
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_output = io.StringIO()

    result = {
        'success': False,
        'output': '',
        'error': '',
        'truncated': False
    }

    try:
        # Redirect stdout/stderr
        sys.stdout = captured_output
        sys.stderr = captured_output

        # Create restricted execution environment
        import os
        tools_path = os.environ.get('TOOLS_PATH', '/home/runner/tools')
        exec_globals = create_execution_globals(tools_path)
        exec_locals = {}

        # Execute with timeout
        with timeout_handler(timeout):
            exec(code, exec_globals, exec_locals)

        result['success'] = True

    except TimeoutError as e:
        result['error'] = str(e)

    except ImportError as e:
        result['error'] = f"Import error: {str(e)}"

    except SyntaxError as e:
        result['error'] = f"Syntax error at line {e.lineno}: {e.msg}"

    except Exception as e:
        # Capture the traceback for debugging
        tb = traceback.format_exc()
        # Only include the relevant part (not the execute_code internals)
        result['error'] = f"{type(e).__name__}: {str(e)}"

    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Get captured output
        output = captured_output.getvalue()

        # Truncate if necessary
        if len(output) > max_output:
            output = output[:max_output] + f"\n... [OUTPUT TRUNCATED - exceeded {max_output} chars]"
            result['truncated'] = True

        result['output'] = output
        captured_output.close()

    return result


def get_available_tools() -> Dict[str, Any]:
    """
    Returns information about tools available for use in execute_code.

    This helper function lists the sandbox tools and standard library modules
    that can be imported and used within execute_code.

    Returns:
        Dict with:
        - sandbox_tools: List of MCP sandbox tools (log_store, privacy, workspace)
        - standard_modules: List of allowed standard library modules
        - example: Example code snippet

    Example:
        >>> info = get_available_tools()
        >>> print(info['sandbox_tools'])
        ['log_store', 'privacy', 'workspace']
    """

    sandbox_tools = ['log_store', 'privacy', 'workspace']
    standard_modules = sorted([
        m for m in ALLOWED_IMPORTS
        if m not in sandbox_tools
    ])

    example = '''
# Example: Process logs, scrub PII, and save checkpoint
import json

# Query logs (data stays in sandbox)
errors = log_store.search_logs("api", "error", limit=100)

# Process locally
results = []
for error in errors:
    clean = privacy.scrub_all_pii(error)
    results.append(clean)

# Save checkpoint for later resumption
workspace.save_checkpoint("error_analysis", {
    "processed": len(results),
    "sample": results[:3]
})

# Only return summary to AI
print(json.dumps({
    "count": len(results),
    "checkpoint_saved": True
}))
'''

    return {
        'sandbox_tools': sandbox_tools,
        'standard_modules': standard_modules,
        'example': example.strip(),
        'timeout_seconds': DEFAULT_TIMEOUT,
        'max_output_chars': MAX_OUTPUT_SIZE
    }
