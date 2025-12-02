"""
Skills Tool - Reusable Code Patterns for MCP Sandbox

This module enables AI agents to save, discover, and run reusable code patterns
(skills). Skills are stored in the workspace and can be reused across sessions.

This implements the "Skills" concept from Anthropic's agent documentation,
where agents can persist working code as reusable functions with documentation.

Use Cases:
- Save working code patterns for reuse
- Build a library of domain-specific operations
- Share skills across different agent sessions
- Document complex workflows with SKILL.md files

Skill Structure:
    /workspace/skills/{skill_name}/
    ├── implementation.py    # The actual code
    ├── SKILL.md            # Documentation for AI discovery
    └── metadata.json       # Parameters, version, author

GitOps: This file is managed via GitOps. Changes require security approval
via pull request.

Example Usage:
    >>> # Save a skill
    >>> skills.save_skill(
    ...     name="analyze_errors",
    ...     code="def analyze_errors(service):\\n    errors = log_store.search_logs(service, 'error')\\n    return {'count': len(errors)}",
    ...     description="Analyze error logs for a service"
    ... )
    >>>
    >>> # List available skills
    >>> skills.list_skills()
    ['analyze_errors', 'scrub_and_summarize']
    >>>
    >>> # Run a skill
    >>> result = skills.run_skill("analyze_errors", service="api")
"""

import os
import json
import ast
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

# Base workspace directory
WORKSPACE_BASE = os.environ.get('WORKSPACE_PATH', '/workspace')

# Skills directory within workspace
SKILLS_DIR = os.path.join(WORKSPACE_BASE, 'skills')

# Maximum skill code size (50KB)
MAX_SKILL_SIZE = 50 * 1024

# Maximum number of skills
MAX_SKILLS = 100


# =============================================================================
# SKILL TEMPLATE
# =============================================================================

SKILL_MD_TEMPLATE = """# {name}

{description}

## Usage

```python
import skills
result = skills.run_skill("{name}"{params_example})
```

## Parameters

{parameters}

## Returns

{returns}

## Example

```python
{example}
```

## Created

- **Date**: {date}
- **Version**: {version}
"""


# =============================================================================
# VALIDATION
# =============================================================================

def _validate_skill_name(name: str) -> None:
    """Validate skill name is safe and valid."""
    if not name:
        raise ValueError("Skill name cannot be empty")

    if not name.replace('_', '').replace('-', '').isalnum():
        raise ValueError(
            f"Invalid skill name '{name}'. "
            "Use only letters, numbers, underscores, and hyphens."
        )

    if len(name) > 50:
        raise ValueError("Skill name must be 50 characters or less")

    # Prevent reserved names
    reserved = {'__init__', '__main__', 'setup', 'test', 'config'}
    if name.lower() in reserved:
        raise ValueError(f"Skill name '{name}' is reserved")


def _validate_code(code: str) -> Dict[str, Any]:
    """
    Validate Python code is syntactically correct and extract info.

    Returns dict with:
    - valid: bool
    - functions: list of function names
    - error: error message if invalid
    """
    if not code or not code.strip():
        return {'valid': False, 'error': 'Code cannot be empty', 'functions': []}

    if len(code) > MAX_SKILL_SIZE:
        return {
            'valid': False,
            'error': f'Code too large ({len(code)} bytes). Maximum: {MAX_SKILL_SIZE}',
            'functions': []
        }

    try:
        tree = ast.parse(code)

        # Extract function definitions
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)

        return {'valid': True, 'functions': functions, 'error': None}

    except SyntaxError as e:
        return {
            'valid': False,
            'error': f'Syntax error at line {e.lineno}: {e.msg}',
            'functions': []
        }


def _get_skill_path(name: str) -> Path:
    """Get the path to a skill directory."""
    _validate_skill_name(name)
    return Path(SKILLS_DIR) / name


# =============================================================================
# SKILL OPERATIONS
# =============================================================================

def save_skill(
    name: str,
    code: str,
    description: str,
    parameters: Optional[Dict[str, str]] = None,
    returns: str = "Result of the skill execution",
    example: str = "",
    version: str = "1.0.0"
) -> Dict[str, Any]:
    """
    Save a reusable skill to the workspace.

    Creates a skill directory with:
    - implementation.py: The actual code
    - SKILL.md: Documentation for AI discovery
    - metadata.json: Skill metadata

    Args:
        name: Unique skill name (letters, numbers, underscores, hyphens)
        code: Python code implementing the skill. Should define at least one function.
        description: Human-readable description of what the skill does
        parameters: Dict of parameter names to descriptions (optional)
        returns: Description of return value
        example: Example usage code
        version: Skill version (default: "1.0.0")

    Returns:
        Dict with status and skill info

    Example:
        >>> save_skill(
        ...     name="count_errors",
        ...     code='''
        ... def count_errors(service: str, hours: int = 24) -> dict:
        ...     \"\"\"Count errors for a service.\"\"\"
        ...     errors = log_store.search_logs(service, "error", limit=1000)
        ...     return {"service": service, "count": len(errors)}
        ... ''',
        ...     description="Count error logs for a service over a time period",
        ...     parameters={"service": "Service name to analyze", "hours": "Hours to look back"},
        ...     returns="Dict with service name and error count"
        ... )

    Security:
        - Code is syntax-validated before saving
        - Skill name is sanitized
        - Size limits enforced
    """
    # Validate name
    _validate_skill_name(name)

    # Check skill limit
    existing = list_skills()
    if len(existing) >= MAX_SKILLS and name not in existing:
        raise ValueError(f"Maximum number of skills ({MAX_SKILLS}) reached")

    # Validate code
    validation = _validate_code(code)
    if not validation['valid']:
        raise ValueError(f"Invalid code: {validation['error']}")

    if not validation['functions']:
        raise ValueError("Code must define at least one function")

    # Create skill directory
    skill_path = _get_skill_path(name)
    skill_path.mkdir(parents=True, exist_ok=True)

    # Write implementation
    impl_path = skill_path / 'implementation.py'
    impl_path.write_text(code, encoding='utf-8')

    # Write metadata
    metadata = {
        'name': name,
        'description': description,
        'parameters': parameters or {},
        'returns': returns,
        'functions': validation['functions'],
        'version': version,
        'created': datetime.now().isoformat(),
        'updated': datetime.now().isoformat()
    }

    meta_path = skill_path / 'metadata.json'
    meta_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

    # Generate SKILL.md
    params_text = "None" if not parameters else "\n".join(
        f"- `{k}`: {v}" for k, v in parameters.items()
    )

    params_example = ""
    if parameters:
        params_example = ", " + ", ".join(f'{k}="..."' for k in parameters.keys())

    skill_md = SKILL_MD_TEMPLATE.format(
        name=name,
        description=description,
        params_example=params_example,
        parameters=params_text,
        returns=returns,
        example=example or f'result = skills.run_skill("{name}")',
        date=datetime.now().strftime("%Y-%m-%d"),
        version=version
    )

    md_path = skill_path / 'SKILL.md'
    md_path.write_text(skill_md, encoding='utf-8')

    return {
        'success': True,
        'name': name,
        'path': str(skill_path),
        'functions': validation['functions'],
        'message': f"Skill '{name}' saved with functions: {', '.join(validation['functions'])}"
    }


def list_skills() -> List[str]:
    """
    List all available skills.

    Returns:
        List of skill names

    Example:
        >>> list_skills()
        ['analyze_errors', 'count_by_service', 'scrub_and_summarize']
    """
    skills_path = Path(SKILLS_DIR)

    if not skills_path.exists():
        return []

    skills = []
    for item in skills_path.iterdir():
        if item.is_dir():
            # Check if it has implementation.py
            if (item / 'implementation.py').exists():
                skills.append(item.name)

    return sorted(skills)


def get_skill(name: str) -> Dict[str, Any]:
    """
    Get detailed information about a skill.

    Args:
        name: Skill name

    Returns:
        Dict with skill metadata, code, and documentation

    Example:
        >>> info = get_skill("analyze_errors")
        >>> print(info['description'])
        >>> print(info['code'])
    """
    skill_path = _get_skill_path(name)

    if not skill_path.exists():
        raise FileNotFoundError(f"Skill '{name}' not found")

    # Read implementation
    impl_path = skill_path / 'implementation.py'
    code = impl_path.read_text(encoding='utf-8') if impl_path.exists() else ""

    # Read metadata
    meta_path = skill_path / 'metadata.json'
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    else:
        metadata = {'name': name, 'description': '', 'functions': []}

    # Read SKILL.md
    md_path = skill_path / 'SKILL.md'
    skill_md = md_path.read_text(encoding='utf-8') if md_path.exists() else ""

    return {
        'name': name,
        'code': code,
        'metadata': metadata,
        'skill_md': skill_md,
        'path': str(skill_path),
        'description': metadata.get('description', ''),
        'functions': metadata.get('functions', []),
        'parameters': metadata.get('parameters', {}),
        'version': metadata.get('version', '1.0.0')
    }


def run_skill(name: str, function: Optional[str] = None, **kwargs) -> Any:
    """
    Execute a saved skill.

    Loads the skill code and executes the specified function (or the first
    function if not specified).

    Args:
        name: Skill name
        function: Specific function to call (optional, defaults to first function)
        **kwargs: Arguments to pass to the skill function

    Returns:
        Result from the skill function

    Example:
        >>> result = run_skill("count_errors", service="api", hours=24)
        >>> print(result)
        {'service': 'api', 'count': 42}

    Security:
        - Skill code runs in the same restricted environment as execute_code
        - Only approved imports are available
    """
    skill_info = get_skill(name)
    code = skill_info['code']
    functions = skill_info['functions']

    if not functions:
        raise ValueError(f"Skill '{name}' has no functions defined")

    # Determine which function to call
    if function:
        if function not in functions:
            raise ValueError(
                f"Function '{function}' not found in skill '{name}'. "
                f"Available: {', '.join(functions)}"
            )
        target_function = function
    else:
        target_function = functions[0]

    # Create execution environment with sandbox tools
    tools_path = os.environ.get('TOOLS_PATH', '/home/runner/tools')
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)

    exec_globals = {
        '__builtins__': __builtins__,
        '__name__': '__skill__',
    }

    # Import sandbox tools
    try:
        import log_store
        import privacy
        import workspace

        exec_globals['log_store'] = log_store
        exec_globals['privacy'] = privacy
        exec_globals['workspace'] = workspace
    except ImportError:
        pass

    # Execute the skill code to define functions
    exec(code, exec_globals)

    # Get and call the target function
    if target_function not in exec_globals:
        raise ValueError(f"Function '{target_function}' not found after executing skill")

    func = exec_globals[target_function]
    return func(**kwargs)


def delete_skill(name: str) -> Dict[str, Any]:
    """
    Delete a skill from the workspace.

    Args:
        name: Skill name

    Returns:
        Dict with status

    Example:
        >>> delete_skill("old_skill")
        {'success': True, 'message': "Skill 'old_skill' deleted"}
    """
    skill_path = _get_skill_path(name)

    if not skill_path.exists():
        raise FileNotFoundError(f"Skill '{name}' not found")

    # Remove all files in skill directory
    for file in skill_path.iterdir():
        file.unlink()

    # Remove directory
    skill_path.rmdir()

    return {
        'success': True,
        'message': f"Skill '{name}' deleted"
    }


def update_skill(
    name: str,
    code: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, str]] = None,
    returns: Optional[str] = None,
    example: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing skill.

    Only updates the fields that are provided; others remain unchanged.

    Args:
        name: Skill name
        code: New code (optional)
        description: New description (optional)
        parameters: New parameters (optional)
        returns: New returns description (optional)
        example: New example (optional)

    Returns:
        Dict with status and updated info
    """
    # Get existing skill
    existing = get_skill(name)

    # Merge with updates
    new_code = code if code is not None else existing['code']
    new_description = description if description is not None else existing['description']
    new_parameters = parameters if parameters is not None else existing['parameters']
    new_returns = returns if returns is not None else existing['metadata'].get('returns', '')
    new_example = example if example is not None else ""

    # Increment version
    old_version = existing['version']
    parts = old_version.split('.')
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = '.'.join(parts)

    # Save updated skill
    return save_skill(
        name=name,
        code=new_code,
        description=new_description,
        parameters=new_parameters,
        returns=new_returns,
        example=new_example,
        version=new_version
    )


def search_skills(query: str) -> List[Dict[str, Any]]:
    """
    Search skills by name or description.

    Args:
        query: Search term

    Returns:
        List of matching skills with basic info

    Example:
        >>> search_skills("error")
        [{'name': 'count_errors', 'description': 'Count error logs...'}]
    """
    query_lower = query.lower()
    results = []

    for skill_name in list_skills():
        try:
            info = get_skill(skill_name)

            # Check if query matches name or description
            if (query_lower in skill_name.lower() or
                query_lower in info['description'].lower()):
                results.append({
                    'name': skill_name,
                    'description': info['description'],
                    'functions': info['functions'],
                    'version': info['version']
                })
        except Exception:
            continue

    return results
