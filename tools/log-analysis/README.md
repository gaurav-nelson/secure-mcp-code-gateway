# Log Analysis Tool Set

This directory contains the **approved Python APIs** for the log-analysis MCP server. These tools are managed via GitOps and represent the "governance layer" of the pattern.

## Overview

The tools in this directory demonstrate the **Code Execution** model described in [Anthropic's "Code Execution with MCP" blog post](https://www.anthropic.com/engineering/code-execution-with-mcp):

- AI writes code that runs in a secure sandbox
- Code can `import` these approved tools
- Large data is processed locally, not sent to the LLM
- Data flows between tools within the sandbox (not through AI context)
- State can be persisted across requests using the workspace
- Security reviews new tools via pull requests

## Available Tools

### `execute_code.py` - Safe Python Code Execution ⭐

Enables AI agents to write and execute Python code in the sandbox with access to all approved tools. This is the key tool that implements the "Code Execution with MCP" pattern.

**Key Functions:**
- `execute_code(code, timeout, max_output)` - Execute Python code safely
- `get_available_tools()` - List tools and modules available for code execution

**Example Usage (via MCP):**
```json
{
  "tool": "execute_code",
  "arguments": {
    "code": "import json\nerrors = log_store.search_logs('api', 'error', limit=100)\nclean = [privacy.scrub_all_pii(e) for e in errors]\nworkspace.save_checkpoint('analysis', {'count': len(clean)})\nprint(json.dumps({'count': len(clean), 'sample': clean[:3]}))"
  }
}
```

**Why this matters:**
- Process data between tools without returning to AI context
- Use loops, conditionals, and complex logic
- Filter large datasets before returning results
- Save checkpoints for long-running operations
- 90-99% token savings on data-intensive operations

**Security Features:**
- Whitelist of allowed imports only
- 30-second execution timeout
- Restricted builtins (no direct file I/O, no network)
- Output size limits (100KB)

### `workspace.py` - Persistent Storage ⭐ NEW

Enables state persistence across requests. AI agents can save checkpoints, intermediate results, and resume long-running tasks.

**Key Functions:**
- `write_file(filepath, content)` - Write content to workspace
- `read_file(filepath)` - Read content from workspace
- `list_files(directory, recursive)` - List files in workspace
- `save_checkpoint(name, data)` - Save JSON checkpoint
- `load_checkpoint(name)` - Load JSON checkpoint
- `get_workspace_info()` - Get usage info and limits

**Example Usage:**
```python
import workspace
import json

# Save intermediate results
workspace.write_file("results/batch1.json", json.dumps({"processed": 100}))

# Use checkpoint helpers for structured data
workspace.save_checkpoint("analysis_state", {
    "processed_services": ["api", "auth"],
    "remaining": ["payment", "billing"]
})

# Resume later
state = workspace.load_checkpoint("analysis_state")
print(f"Resuming from: {state['remaining']}")
```

**Security Features:**
- All paths restricted to `/workspace` directory
- No access to system files
- File size limit (10MB per file)
- Workspace quota (100MB total)
- Allowed file extensions only

### `log_store.py` - Log Search and Analysis

Provides efficient log searching without sending 500MB files to the LLM.

**Key Functions:**
- `search_logs(service_name, keyword, limit, log_level)` - Search logs efficiently
- `get_error_summary(service_name, hours)` - Get aggregated error statistics
- `tail_logs(service_name, lines)` - View recent log entries

**Example Usage:**
```python
import log_store

# Find all HTTP 500 errors in payment service
errors = log_store.search_logs("payment-service", "HTTP 500", limit=20)
print(f"Found {len(errors)} server errors")

# Get summary statistics
summary = log_store.get_error_summary("payment-service", hours=24)
print(f"Error rate: {summary['error_rate_per_hour']}/hour")
```

### `privacy.py` - PII Scrubbing and Anonymization

Enables processing sensitive data WITHOUT exposing it to the LLM.

**Key Functions:**
- `scrub_all_pii(text)` - Remove all PII (emails, phones, SSNs, etc.)
- `scrub_emails(text)` - Remove email addresses only
- `anonymize_names(text, name_map)` - Replace names with pseudonyms
- `create_privacy_report(original, scrubbed)` - Audit what was removed

**Example Usage:**
```python
import privacy

# Scrub all PII from log data
raw_logs = log_store.search_logs("customer-service", "complaint", limit=50)
safe_logs = [privacy.scrub_all_pii(log) for log in raw_logs]

# Now it's safe to return to AI
print("Anonymized logs:")
for log in safe_logs[:5]:
    print(log)
```

### `skills.py` - Reusable Code Patterns ⭐ NEW

Enables saving and reusing code patterns across sessions. AI agents can create "skills" - named code snippets that can be executed repeatedly, enabling learning and automation.

**Key Functions:**
- `save_skill(name, code, description, tags)` - Save a reusable skill
- `list_skills()` - List all saved skills with metadata
- `get_skill(name)` - Get skill code and documentation
- `run_skill(name, **kwargs)` - Execute a skill with parameters
- `delete_skill(name)` - Remove a skill
- `update_skill(name, code, description, tags)` - Update existing skill
- `search_skills(query)` - Search skills by name/tag/description

**Example Usage:**
```python
import skills

# Save a reusable analysis skill
skills.save_skill(
    name="analyze_errors",
    code="""
import log_store
import privacy

def run(service_name, hours=24):
    '''Analyze errors for a service with PII scrubbing'''
    errors = log_store.search_logs(service_name, "error", limit=100)
    clean = [privacy.scrub_all_pii(e) for e in errors]
    return {
        "service": service_name,
        "error_count": len(clean),
        "sample": clean[:5]
    }
""",
    description="Analyze service errors with automatic PII scrubbing",
    tags=["analysis", "errors", "privacy"]
)

# List available skills
available = skills.list_skills()
print(f"Found {len(available)} skills")

# Run a saved skill
result = skills.run_skill("analyze_errors", service_name="payment-api", hours=12)
print(f"Found {result['error_count']} errors")

# Search for skills
matches = skills.search_skills("privacy")
print(f"Skills matching 'privacy': {[s['name'] for s in matches]}")
```

**Skill Structure:**
Each skill is stored in `/workspace/skills/{name}/` containing:
- `implementation.py` - The executable code
- `SKILL.md` - Human-readable documentation
- `metadata.json` - Name, description, tags, timestamps

**Why this matters:**
- AI learns and improves over time
- Common patterns are captured and reusable
- New users benefit from existing skills
- Skills can be shared across teams

**Security Features:**
- Skills stored in workspace (PVC-backed)
- All code runs through execute_code security
- Skill names validated (alphanumeric + underscore only)
- Skills can only import approved modules

### `tool_discovery.py` - Browsable Tool Interface ⭐ NEW

Implements the "Tool Discovery via Filesystem" pattern from Anthropic's blog. Tools are exposed as browsable files that AI agents can explore through the filesystem, enabling progressive disclosure of documentation.

**Key Functions:**
- `generate_tool_stubs()` - Generate tool stub files in /workspace/tools/
- `refresh_tool_stubs()` - Regenerate stubs after tool updates
- `list_available_tools()` - List all tool modules and functions
- `get_tool_info(module_name)` - Get detailed module documentation
- `search_tools(query)` - Search for tools by name/description

**Generated Structure:**
```
/workspace/tools/
├── index.py              # Overview of all tools
├── log_store/
│   ├── __init__.py       # Module overview with function list
│   ├── search_logs.py    # Individual function documentation
│   ├── get_error_summary.py
│   └── tail_logs.py
├── privacy/
│   ├── __init__.py
│   ├── scrub_all_pii.py
│   └── ...
├── workspace/
│   └── ...
└── skills/
    └── ...
```

**Example Usage:**
```python
import tool_discovery
import workspace

# Generate tool stubs (done automatically on startup)
tool_discovery.generate_tool_stubs()

# AI discovers tools by browsing
files = workspace.list_files("/workspace/tools")
# ['index.py', 'log_store/', 'privacy/', 'workspace/', 'skills/']

# Read specific function docs
doc = workspace.read_file("/workspace/tools/log_store/search_logs.py")
print(doc)  # Full function documentation

# Search for relevant tools
matches = tool_discovery.search_tools("email")
# [{'module': 'privacy', 'name': 'scrub_emails', 'description': '...'}]
```

**Why this matters:**
- AI discovers tools through filesystem navigation
- Only needed documentation loaded into context
- Progressive disclosure reduces token usage
- Self-documenting tools with typed interfaces
- Stubs generated automatically on startup

**Security Features:**
- Stubs are read-only documentation
- Actual implementations run in sandbox
- Generated from approved tools only

## Code Execution with State Persistence

Combine `execute_code` with `workspace` for powerful long-running workflows:

```python
# First request: Start processing
errors = log_store.search_logs("*", "error", limit=1000)
processed = []
for i, error in enumerate(errors[:100]):
    clean = privacy.scrub_all_pii(error)
    processed.append(clean)

# Save checkpoint
workspace.save_checkpoint("error_scan", {
    "processed": len(processed),
    "total": len(errors),
    "results": processed
})
print(f"Processed {len(processed)} of {len(errors)}, checkpoint saved")
```

```python
# Follow-up request: Resume from checkpoint
state = workspace.load_checkpoint("error_scan")
print(f"Resuming from {state['processed']} of {state['total']}")
# Continue processing...
```

## Code Execution Pattern

The `execute_code` tool enables the pattern described by Anthropic:

**❌ Traditional MCP (All Data Through AI):**
```
User: "Find database errors and scrub PII"
AI: calls log_store.search_logs() → returns 10,000 logs to AI context (50K tokens)
AI: calls privacy.scrub_all_pii() for each → processes in context (100K tokens)
AI: returns results (10K tokens)
Total: 160,000 tokens
```

**✅ Code Execution (Data Stays in Sandbox):**
```
User: "Find database errors and scrub PII"
AI: calls execute_code with:
    ```python
    errors = log_store.search_logs("db", "error", limit=100)
    clean = [privacy.scrub_all_pii(e) for e in errors]
    print(f"Found {len(clean)} errors")
    for e in clean[:5]:
        print(e)
    ```
Sandbox: Executes code, data flows between tools internally
AI: receives 10-line output (200 tokens)
Total: 200 tokens (99.8% savings)
```

## Security Model

### GitOps Governance

1. Security reviews this directory via pull requests
2. Only approved tools are available to the AI
3. AI cannot `pip install` or add new tools
4. Changes are tracked in Git history

### Sandbox Isolation

- Tools run in a locked-down pod
- No network access (except approved APIs)
- No access to host filesystem
- Drop all Linux capabilities
- Runs as non-root user

## Adding New Tools to This Set

To add a new approved tool for the log-analysis MCP:

1. **Create the tool file:**
   ```bash
   touch tools/log-analysis/my_new_tool.py
   ```

2. **Implement with docstrings:**
   ```python
   """
   My New Tool - Approved for Log Analysis MCP

   This tool does X, Y, Z in a safe and efficient way.
   """

   def my_function(arg1: str) -> dict:
       """Clear docstring explaining usage"""
       # Implementation
       return result
   ```

3. **Update the sandbox ConfigMap:**

   The ConfigMap in `charts/hub/mcp-log-analysis-sandbox/templates/tools-configmap.yaml`
   automatically syncs all `.py` files from this directory.

4. **Submit for review:**
   ```bash
   git add tools/log-analysis/my_new_tool.py
   git commit -m "Add my_new_tool for log-analysis MCP"
   git push
   ```

5. **Security review & merge:**

   Security reviews the PR to ensure the tool:
   - Doesn't expose sensitive data
   - Doesn't create security vulnerabilities
   - Follows the Code Mode pattern

## Creating a New Tool Set for Your MCP Server

When you create a new MCP server (e.g., `mcp-data-processing`), create a new tool directory:

```bash
mkdir tools/data-processing
```

Add your tools:
```bash
tools/
  log-analysis/          # Example (this directory)
    log_store.py
    privacy.py
    README.md
  data-processing/       # Your new tool set
    data_api.py
    transform.py
    README.md
```

Update your sandbox chart to mount `tools/data-processing/`:
```yaml
# charts/hub/mcp-data-processing-sandbox/templates/tools-configmap.yaml
data:
  data_api.py: |
    {{- .Files.Get "tools/data-processing/data_api.py" | nindent 4 }}
  transform.py: |
    {{- .Files.Get "tools/data-processing/transform.py" | nindent 4 }}
```

## Testing Tools Locally

Run the tools directly for testing:

```bash
cd tools/log-analysis
python log_store.py
python privacy.py
```

Both files include `if __name__ == "__main__"` blocks with examples.

## References

- [Code Mode Execution Pattern](../../docs/ARCHITECTURE.md)
- [Security Guidelines](../../docs/RBAC-GUIDE.md)
- [Adding a New MCP Server](../../docs/ADD-NEW-MCP-SERVER.md)

