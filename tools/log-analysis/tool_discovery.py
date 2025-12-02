"""
Tool Discovery API - Browsable Tool Interface for MCP Sandbox

This module implements the "Tool Discovery via Filesystem" pattern described
in Anthropic's "Code Execution with MCP" blog post. It exposes approved tools
as browsable files in the workspace, enabling AI agents to discover tools
through progressive disclosure rather than loading all documentation at once.

Architecture:
    /workspace/tools/
    ├── index.py              # Top-level overview of all tools
    ├── log_store/
    │   ├── __init__.py       # Module info and function list
    │   ├── search_logs.py    # Individual function with full docs
    │   ├── get_error_summary.py
    │   └── tail_logs.py
    ├── privacy/
    │   ├── __init__.py
    │   ├── scrub_all_pii.py
    │   ├── scrub_emails.py
    │   └── ...
    ├── workspace/
    │   ├── __init__.py
    │   └── ...
    └── skills/
        ├── __init__.py
        └── ...

Benefits:
- AI discovers tools by browsing the filesystem
- Only needed documentation is loaded into context
- Progressive disclosure reduces token usage
- Typed interfaces with full docstrings
- Tools are self-documenting

GitOps: This file is managed via GitOps. Changes require security approval
via pull request.

Example Usage:
    >>> # Initialize tool stubs at sandbox startup
    >>> tool_discovery.generate_tool_stubs()
    >>>
    >>> # AI can then browse tools via workspace
    >>> files = workspace.list_files("/workspace/tools")
    >>> # ['index.py', 'log_store/', 'privacy/', 'workspace/', 'skills/']
    >>>
    >>> # Read specific function docs
    >>> doc = workspace.read_file("/workspace/tools/log_store/search_logs.py")
"""

import os
import sys
import ast
import inspect
import json
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

# Where tool stubs are generated
TOOLS_DIR = "/workspace/tools"

# Tools to expose (must match execute_code ALLOWED_IMPORTS sandbox tools)
SANDBOX_TOOLS = ['log_store', 'privacy', 'workspace', 'skills']

# Marker file to track when stubs were generated
MARKER_FILE = ".tool_stubs_generated"


# =============================================================================
# STUB GENERATION
# =============================================================================

def _get_function_signature(func: Callable) -> str:
    """Extract function signature with type hints."""
    try:
        sig = inspect.signature(func)
        return f"def {func.__name__}{sig}"
    except (ValueError, TypeError):
        return f"def {func.__name__}(*args, **kwargs)"


def _get_function_docstring(func: Callable) -> str:
    """Extract and format function docstring."""
    doc = inspect.getdoc(func)
    if doc:
        return f'"""\n{doc}\n"""'
    return '"""No documentation available."""'


def _generate_function_stub(func: Callable, module_name: str) -> str:
    """Generate a stub file for a single function."""
    signature = _get_function_signature(func)
    docstring = _get_function_docstring(func)

    # Get source code if available (for type hints)
    try:
        source = inspect.getsource(func)
        # Extract just the function definition and docstring for stub
    except (OSError, TypeError):
        source = None

    stub = f'''"""
{func.__name__} - Function from {module_name} module

This is a stub file for AI discovery. The actual implementation
runs in the sandbox environment.

To use this function:
    import {module_name}
    result = {module_name}.{func.__name__}(...)

"""

# Function signature:
{signature}:
    {docstring}
    pass  # Implementation in sandbox


# Example usage:
# >>> import {module_name}
# >>> result = {module_name}.{func.__name__}(...)
'''
    return stub


def _generate_module_init(module, module_name: str) -> str:
    """Generate __init__.py content for a module directory."""
    functions = []

    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and not name.startswith('_'):
            try:
                sig = _get_function_signature(obj)
                doc_first_line = (inspect.getdoc(obj) or "No description").split('\n')[0]
                functions.append({
                    'name': name,
                    'signature': sig,
                    'description': doc_first_line
                })
            except Exception:
                continue

    # Get module docstring
    module_doc = inspect.getdoc(module) or f"{module_name} module"
    module_doc_first = module_doc.split('\n')[0] if module_doc else module_name

    init_content = f'''"""
{module_name} - {module_doc_first}

Available Functions:
'''

    for func in functions:
        init_content += f"    - {func['name']}: {func['description']}\n"

    init_content += f'''
To use this module:
    import {module_name}

Browse individual function files for detailed documentation and examples.
"""

# Module: {module_name}
# Functions: {len(functions)}

__all__ = [
'''

    for func in functions:
        init_content += f'    "{func["name"]}",\n'

    init_content += ''']

# Function Overview:
'''

    for func in functions:
        init_content += f'''
# {func['name']}
#   {func['signature']}
#   {func['description']}
'''

    return init_content


def _generate_index() -> str:
    """Generate the top-level index.py file."""
    index = '''"""
MCP Sandbox Tools - Index

This directory contains stub files for all approved tools available in
the MCP sandbox. Browse this directory to discover available functionality.

Available Tool Modules:
    - log_store/    : Log search and analysis (search_logs, get_error_summary, tail_logs)
    - privacy/      : PII scrubbing and anonymization (scrub_all_pii, scrub_emails, etc.)
    - workspace/    : Persistent file storage (read_file, write_file, checkpoints)
    - skills/       : Reusable code patterns (save_skill, run_skill, list_skills)

How to Use:
    1. Browse module directories to see available functions
    2. Read individual function files for detailed documentation
    3. Use functions via: import module_name; module_name.function(...)

Architecture:
    /workspace/tools/
    ├── index.py          # This file - overview of all tools
    ├── log_store/
    │   ├── __init__.py   # Module overview with function list
    │   ├── search_logs.py
    │   └── ...
    ├── privacy/
    │   └── ...
    ├── workspace/
    │   └── ...
    └── skills/
        └── ...

Example Workflow:
    >>> # Discover available modules
    >>> import workspace
    >>> workspace.list_files("/workspace/tools")
    ['index.py', 'log_store/', 'privacy/', 'workspace/', 'skills/']

    >>> # Explore a module
    >>> workspace.list_files("/workspace/tools/log_store")
    ['__init__.py', 'search_logs.py', 'get_error_summary.py', 'tail_logs.py']

    >>> # Read function documentation
    >>> doc = workspace.read_file("/workspace/tools/log_store/search_logs.py")
    >>> print(doc)  # Full function docs and examples

    >>> # Use the function
    >>> import log_store
    >>> results = log_store.search_logs("api", "error", limit=10)

Security Note:
    These stubs are auto-generated from the approved tools.
    Actual implementations run in the secure sandbox environment.
"""

# Available modules
TOOLS = [
    "log_store",
    "privacy",
    "workspace",
    "skills"
]

# Tool descriptions
DESCRIPTIONS = {
    "log_store": "Log search and analysis - search logs efficiently without sending large files to LLM",
    "privacy": "PII scrubbing and anonymization - process sensitive data safely in sandbox",
    "workspace": "Persistent storage - save files, checkpoints, and state across sessions",
    "skills": "Reusable code patterns - save and run common operations"
}

# Quick reference
print("MCP Sandbox Tools")
print("=" * 40)
for tool in TOOLS:
    print(f"  {tool}: {DESCRIPTIONS.get(tool, 'No description')}")
'''
    return index


def generate_tool_stubs(force: bool = False) -> Dict[str, Any]:
    """
    Generate tool stub files in /workspace/tools/ for AI discovery.

    This function creates a browsable file tree of all approved sandbox tools,
    enabling AI agents to discover tools through filesystem navigation rather
    than having all documentation loaded into context at once.

    Args:
        force: If True, regenerate stubs even if they already exist

    Returns:
        Dict containing:
        - success: bool - Whether generation completed
        - modules: List[str] - Modules that were processed
        - functions: int - Total number of function stubs generated
        - path: str - Path where stubs were generated
        - message: str - Status message

    Example:
        >>> result = generate_tool_stubs()
        >>> print(result['message'])
        'Generated stubs for 4 modules (23 functions) in /workspace/tools'
    """
    result = {
        'success': False,
        'modules': [],
        'functions': 0,
        'path': TOOLS_DIR,
        'message': ''
    }

    # Check if already generated (unless force=True)
    marker_path = os.path.join(TOOLS_DIR, MARKER_FILE)
    if os.path.exists(marker_path) and not force:
        result['success'] = True
        result['message'] = f'Tool stubs already exist at {TOOLS_DIR}. Use force=True to regenerate.'
        return result

    try:
        # Create tools directory
        os.makedirs(TOOLS_DIR, exist_ok=True)

        # Generate top-level index
        index_path = os.path.join(TOOLS_DIR, "index.py")
        with open(index_path, 'w') as f:
            f.write(_generate_index())

        total_functions = 0

        # Process each sandbox tool module
        for module_name in SANDBOX_TOOLS:
            try:
                # Import the module
                module = __import__(module_name)

                # Create module directory
                module_dir = os.path.join(TOOLS_DIR, module_name)
                os.makedirs(module_dir, exist_ok=True)

                # Generate __init__.py
                init_path = os.path.join(module_dir, "__init__.py")
                with open(init_path, 'w') as f:
                    f.write(_generate_module_init(module, module_name))

                # Generate stub for each public function
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and not name.startswith('_'):
                        stub_path = os.path.join(module_dir, f"{name}.py")
                        with open(stub_path, 'w') as f:
                            f.write(_generate_function_stub(obj, module_name))
                        total_functions += 1

                result['modules'].append(module_name)

            except ImportError as e:
                # Module not available in this environment
                # Create placeholder
                module_dir = os.path.join(TOOLS_DIR, module_name)
                os.makedirs(module_dir, exist_ok=True)

                placeholder = f'''"""
{module_name} module

This module is not available in the current environment.
It will be available when running in the MCP sandbox.
"""
'''
                init_path = os.path.join(module_dir, "__init__.py")
                with open(init_path, 'w') as f:
                    f.write(placeholder)

                result['modules'].append(f"{module_name} (placeholder)")

        # Write marker file
        with open(marker_path, 'w') as f:
            f.write(json.dumps({
                'generated_at': datetime.now().isoformat(),
                'modules': result['modules'],
                'functions': total_functions
            }))

        result['success'] = True
        result['functions'] = total_functions
        result['message'] = f"Generated stubs for {len(result['modules'])} modules ({total_functions} functions) in {TOOLS_DIR}"

    except Exception as e:
        result['message'] = f"Error generating tool stubs: {str(e)}"

    return result


def refresh_tool_stubs() -> Dict[str, Any]:
    """
    Regenerate all tool stubs, updating to reflect any changes.

    Returns:
        Dict with generation results

    Example:
        >>> result = refresh_tool_stubs()
        >>> print(result['message'])
    """
    return generate_tool_stubs(force=True)


def get_tool_info(module_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific tool module.

    Args:
        module_name: Name of the module (e.g., 'log_store', 'privacy')

    Returns:
        Dict containing:
        - name: str - Module name
        - description: str - Module description
        - functions: List[Dict] - List of functions with signatures and docs
        - path: str - Path to module stubs

    Example:
        >>> info = get_tool_info('log_store')
        >>> for func in info['functions']:
        ...     print(f"{func['name']}: {func['description']}")
    """
    result = {
        'name': module_name,
        'description': '',
        'functions': [],
        'path': os.path.join(TOOLS_DIR, module_name)
    }

    if module_name not in SANDBOX_TOOLS:
        result['description'] = f"Unknown module: {module_name}"
        return result

    try:
        module = __import__(module_name)
        result['description'] = (inspect.getdoc(module) or "").split('\n')[0]

        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith('_'):
                try:
                    sig = _get_function_signature(obj)
                    doc = inspect.getdoc(obj) or "No description"
                    doc_first = doc.split('\n')[0]

                    result['functions'].append({
                        'name': name,
                        'signature': sig,
                        'description': doc_first,
                        'full_doc': doc
                    })
                except Exception:
                    continue

    except ImportError:
        result['description'] = f"Module {module_name} not available in this environment"

    return result


def list_available_tools() -> Dict[str, Any]:
    """
    List all available tool modules with their functions.

    Returns:
        Dict containing:
        - tools: Dict[str, List[str]] - Module names mapped to function lists
        - total_functions: int - Total number of functions
        - stubs_generated: bool - Whether stubs exist in workspace

    Example:
        >>> tools = list_available_tools()
        >>> for module, funcs in tools['tools'].items():
        ...     print(f"{module}: {len(funcs)} functions")
    """
    result = {
        'tools': {},
        'total_functions': 0,
        'stubs_generated': os.path.exists(os.path.join(TOOLS_DIR, MARKER_FILE))
    }

    for module_name in SANDBOX_TOOLS:
        try:
            module = __import__(module_name)
            functions = [
                name for name, obj in inspect.getmembers(module)
                if inspect.isfunction(obj) and not name.startswith('_')
            ]
            result['tools'][module_name] = functions
            result['total_functions'] += len(functions)
        except ImportError:
            result['tools'][module_name] = ['(module not available)']

    return result


def search_tools(query: str) -> List[Dict[str, Any]]:
    """
    Search for tools matching a query string.

    Searches function names, descriptions, and documentation for matches.

    Args:
        query: Search string (case-insensitive)

    Returns:
        List of matching functions with module, name, and description

    Example:
        >>> matches = search_tools("email")
        >>> for m in matches:
        ...     print(f"{m['module']}.{m['name']}: {m['description']}")
        privacy.scrub_emails: Removes email addresses from text.
    """
    query_lower = query.lower()
    results = []

    for module_name in SANDBOX_TOOLS:
        try:
            module = __import__(module_name)

            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and not name.startswith('_'):
                    doc = inspect.getdoc(obj) or ""

                    # Search in name and documentation
                    if query_lower in name.lower() or query_lower in doc.lower():
                        results.append({
                            'module': module_name,
                            'name': name,
                            'signature': _get_function_signature(obj),
                            'description': doc.split('\n')[0] if doc else "No description"
                        })
        except ImportError:
            continue

    return results


# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_on_startup() -> Dict[str, Any]:
    """
    Initialize tool discovery on sandbox startup.

    This should be called when the sandbox container starts to ensure
    tool stubs are available for AI discovery.

    Returns:
        Dict with initialization status

    Example:
        >>> # In sandbox startup script
        >>> import tool_discovery
        >>> tool_discovery.initialize_on_startup()
    """
    return generate_tool_stubs(force=False)


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Tool Discovery - Testing")
    print("=" * 50)

    # List available tools
    print("\nAvailable Tools:")
    tools = list_available_tools()
    for module, functions in tools['tools'].items():
        print(f"  {module}: {functions}")

    # Search example
    print("\nSearch for 'error':")
    matches = search_tools("error")
    for m in matches:
        print(f"  {m['module']}.{m['name']}: {m['description']}")

    # Get tool info
    print("\nlog_store module info:")
    info = get_tool_info('log_store')
    print(f"  Description: {info['description']}")
    for func in info['functions'][:3]:
        print(f"  - {func['name']}: {func['description']}")

    print("\nTo generate stubs, run:")
    print("  result = generate_tool_stubs()")
    print(f"  # Creates stubs in {TOOLS_DIR}/")
