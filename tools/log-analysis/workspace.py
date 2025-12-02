"""
Workspace Tool - Persistent Storage for MCP Sandbox

This module provides file system operations for the sandbox workspace,
enabling AI agents to persist data between requests. This implements
the "State Persistence" pattern from Anthropic's "Code Execution with MCP".

Use Cases:
- Save intermediate results for long-running tasks
- Checkpoint and resume workflows
- Store reusable data between requests
- Build up context across multiple interactions

Security Features:
- All paths are restricted to /workspace directory
- No access to system files or other directories
- File size limits enforced
- Automatic path sanitization

GitOps: This file is managed via GitOps. Changes require security approval
via pull request.

Example Usage:
    >>> # Save checkpoint data
    >>> workspace.write_file("checkpoint.json", json.dumps({"processed": 100}))
    >>>
    >>> # Resume from checkpoint
    >>> data = workspace.read_file("checkpoint.json")
    >>> checkpoint = json.loads(data)
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path


# =============================================================================
# CONFIGURATION
# =============================================================================

# Base workspace directory (mounted PVC)
WORKSPACE_BASE = os.environ.get('WORKSPACE_PATH', '/workspace')

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum total workspace size (100MB)
MAX_WORKSPACE_SIZE = 100 * 1024 * 1024

# Allowed file extensions (for safety)
ALLOWED_EXTENSIONS = {
    '.txt', '.json', '.csv', '.yaml', '.yml', '.md',
    '.py', '.log', '.xml', '.html', '.css', '.js'
}


# =============================================================================
# PATH SECURITY
# =============================================================================

def _sanitize_path(filepath: str) -> Path:
    """
    Sanitize and validate file path to ensure it stays within workspace.

    Prevents path traversal attacks like "../../../etc/passwd"
    """
    # Convert to Path and resolve
    workspace = Path(WORKSPACE_BASE).resolve()

    # Handle relative and absolute paths
    if filepath.startswith('/'):
        # Absolute path - must be within workspace
        full_path = Path(filepath).resolve()
    else:
        # Relative path - prepend workspace
        full_path = (workspace / filepath).resolve()

    # Security check: ensure path is within workspace
    try:
        full_path.relative_to(workspace)
    except ValueError:
        raise PermissionError(
            f"Access denied: Path '{filepath}' is outside workspace. "
            f"All files must be within {WORKSPACE_BASE}"
        )

    return full_path


def _check_extension(filepath: str) -> None:
    """Validate file extension is allowed."""
    ext = Path(filepath).suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File extension '{ext}' not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def _get_workspace_size() -> int:
    """Calculate total size of workspace directory."""
    workspace = Path(WORKSPACE_BASE)
    if not workspace.exists():
        return 0

    total = 0
    for path in workspace.rglob('*'):
        if path.is_file():
            total += path.stat().st_size
    return total


# =============================================================================
# FILE OPERATIONS
# =============================================================================

def write_file(filepath: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    """
    Write content to a file in the workspace.

    Creates parent directories if they don't exist.

    Args:
        filepath: Path relative to workspace (e.g., "data/output.json")
        content: String content to write
        overwrite: If False, raise error if file exists (default: True)

    Returns:
        Dict with status and file info

    Example:
        >>> write_file("results/analysis.json", json.dumps({"count": 42}))
        {'success': True, 'path': '/workspace/results/analysis.json', 'size': 15}

    Security:
        - Path must be within /workspace
        - File extension must be allowed
        - Content size limited to 10MB
    """
    # Validate
    _check_extension(filepath)
    full_path = _sanitize_path(filepath)

    # Check content size
    content_bytes = content.encode('utf-8')
    if len(content_bytes) > MAX_FILE_SIZE:
        raise ValueError(
            f"Content too large ({len(content_bytes)} bytes). "
            f"Maximum: {MAX_FILE_SIZE} bytes (10MB)"
        )

    # Check workspace quota
    current_size = _get_workspace_size()
    if current_size + len(content_bytes) > MAX_WORKSPACE_SIZE:
        raise ValueError(
            f"Workspace quota exceeded. Current: {current_size}, "
            f"Adding: {len(content_bytes)}, Max: {MAX_WORKSPACE_SIZE}"
        )

    # Check overwrite
    if not overwrite and full_path.exists():
        raise FileExistsError(f"File already exists: {filepath}")

    # Create parent directories
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    full_path.write_text(content, encoding='utf-8')

    return {
        'success': True,
        'path': str(full_path),
        'size': len(content_bytes),
        'message': f"Written {len(content_bytes)} bytes to {filepath}"
    }


def read_file(filepath: str) -> str:
    """
    Read content from a file in the workspace.

    Args:
        filepath: Path relative to workspace

    Returns:
        File content as string

    Example:
        >>> content = read_file("checkpoint.json")
        >>> data = json.loads(content)

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If path is outside workspace
    """
    full_path = _sanitize_path(filepath)

    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if not full_path.is_file():
        raise IsADirectoryError(f"Path is a directory: {filepath}")

    return full_path.read_text(encoding='utf-8')


def delete_file(filepath: str) -> Dict[str, Any]:
    """
    Delete a file from the workspace.

    Args:
        filepath: Path relative to workspace

    Returns:
        Dict with status

    Example:
        >>> delete_file("temp/old_data.json")
        {'success': True, 'message': 'Deleted temp/old_data.json'}
    """
    full_path = _sanitize_path(filepath)

    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if full_path.is_dir():
        raise IsADirectoryError(f"Cannot delete directory with delete_file: {filepath}")

    full_path.unlink()

    return {
        'success': True,
        'message': f"Deleted {filepath}"
    }


def list_files(directory: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
    """
    List files in the workspace directory.

    Args:
        directory: Subdirectory to list (default: workspace root)
        recursive: If True, list all files recursively

    Returns:
        List of file info dicts with name, size, type

    Example:
        >>> files = list_files()
        >>> for f in files:
        ...     print(f"{f['name']}: {f['size']} bytes")

        >>> # List specific directory
        >>> list_files("checkpoints/")
    """
    if directory:
        full_path = _sanitize_path(directory)
    else:
        full_path = Path(WORKSPACE_BASE)

    if not full_path.exists():
        return []

    if not full_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    files = []

    if recursive:
        items = full_path.rglob('*')
    else:
        items = full_path.iterdir()

    for item in items:
        try:
            rel_path = item.relative_to(Path(WORKSPACE_BASE))
            stat = item.stat()

            files.append({
                'name': str(rel_path),
                'type': 'directory' if item.is_dir() else 'file',
                'size': stat.st_size if item.is_file() else 0,
            })
        except (PermissionError, OSError):
            continue

    # Sort by name
    files.sort(key=lambda x: x['name'])

    return files


def file_exists(filepath: str) -> bool:
    """
    Check if a file exists in the workspace.

    Args:
        filepath: Path relative to workspace

    Returns:
        True if file exists, False otherwise
    """
    try:
        full_path = _sanitize_path(filepath)
        return full_path.exists() and full_path.is_file()
    except PermissionError:
        return False


def get_workspace_info() -> Dict[str, Any]:
    """
    Get information about the workspace.

    Returns:
        Dict with workspace path, usage, and limits

    Example:
        >>> info = get_workspace_info()
        >>> print(f"Using {info['used_bytes']} of {info['max_bytes']}")
    """
    workspace = Path(WORKSPACE_BASE)

    file_count = 0
    dir_count = 0
    total_size = 0

    if workspace.exists():
        for path in workspace.rglob('*'):
            if path.is_file():
                file_count += 1
                total_size += path.stat().st_size
            elif path.is_dir():
                dir_count += 1

    return {
        'workspace_path': WORKSPACE_BASE,
        'exists': workspace.exists(),
        'file_count': file_count,
        'directory_count': dir_count,
        'used_bytes': total_size,
        'max_bytes': MAX_WORKSPACE_SIZE,
        'used_percent': round(total_size / MAX_WORKSPACE_SIZE * 100, 1),
        'max_file_size': MAX_FILE_SIZE,
        'allowed_extensions': sorted(ALLOWED_EXTENSIONS)
    }


def create_directory(dirpath: str) -> Dict[str, Any]:
    """
    Create a directory in the workspace.

    Args:
        dirpath: Directory path relative to workspace

    Returns:
        Dict with status

    Example:
        >>> create_directory("checkpoints/2024")
        {'success': True, 'path': '/workspace/checkpoints/2024'}
    """
    full_path = _sanitize_path(dirpath)
    full_path.mkdir(parents=True, exist_ok=True)

    return {
        'success': True,
        'path': str(full_path),
        'message': f"Created directory {dirpath}"
    }


# =============================================================================
# CHECKPOINT HELPERS
# =============================================================================

def save_checkpoint(name: str, data: Any) -> Dict[str, Any]:
    """
    Save a checkpoint with automatic JSON serialization.

    Checkpoints are stored in the 'checkpoints/' directory.

    Args:
        name: Checkpoint name (without extension)
        data: Any JSON-serializable data

    Returns:
        Dict with status and path

    Example:
        >>> save_checkpoint("batch_1", {"processed": 100, "remaining": 900})
        >>> # Later...
        >>> data = load_checkpoint("batch_1")
    """
    filepath = f"checkpoints/{name}.json"
    content = json.dumps(data, indent=2, default=str)
    return write_file(filepath, content)


def load_checkpoint(name: str) -> Any:
    """
    Load a checkpoint and deserialize from JSON.

    Args:
        name: Checkpoint name (without extension)

    Returns:
        Deserialized data

    Raises:
        FileNotFoundError: If checkpoint doesn't exist
    """
    filepath = f"checkpoints/{name}.json"
    content = read_file(filepath)
    return json.loads(content)


def list_checkpoints() -> List[str]:
    """
    List all available checkpoints.

    Returns:
        List of checkpoint names (without extension)
    """
    files = list_files("checkpoints/")
    return [
        f['name'].replace('checkpoints/', '').replace('.json', '')
        for f in files
        if f['type'] == 'file' and f['name'].endswith('.json')
    ]


def delete_checkpoint(name: str) -> Dict[str, Any]:
    """
    Delete a checkpoint.

    Args:
        name: Checkpoint name (without extension)

    Returns:
        Dict with status
    """
    filepath = f"checkpoints/{name}.json"
    return delete_file(filepath)
