# Log Analysis Tool Set

This directory contains the **approved Python APIs** for the log-analysis MCP server. These tools are managed via GitOps and represent the "governance layer" of the pattern.

## Overview

The tools in this directory demonstrate the **Code Mode** execution model:

- AI-generated code runs in the secure sandbox
- Code can `import` these approved tools
- Large data is processed locally, not sent to the LLM
- Security reviews new tools via pull requests

## Available Tools

### `log_store.py` - Log Search and Analysis

Provides efficient log searching without sending 500MB files to the LLM.

**Key Functions:**
- `search_logs(service_name, keyword, limit, log_level)` - Search logs efficiently
- `get_error_summary(service_name, hours)` - Get aggregated error statistics
- `tail_logs(service_name, lines)` - View recent log entries

**Example Usage:**
```python
import tools.log_store as logs

# Find all HTTP 500 errors in payment service
errors = logs.search_logs("payment-service", "HTTP 500", limit=20)
print(f"Found {len(errors)} server errors")

# Get summary statistics
summary = logs.get_error_summary("payment-service", hours=24)
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
import tools.privacy as privacy

# Load sensitive customer data (stays in sandbox)
with open("/data/customer-complaints.txt", 'r') as f:
    raw_data = f.read()

# Scrub all PII before sending to LLM
safe_data = privacy.scrub_all_pii(raw_data)

# Now it's safe to analyze with the LLM
print("Anonymized data:")
print(safe_data)
```

## Why Code Mode?

Traditional "direct tool call" models fail with large data:

**❌ Direct Tool Call (Expensive):**
```
User: "Analyze payment-service.log for errors"
LLM: calls get_logs("payment-service")
System: returns 500MB of log data to LLM
LLM: (context overflow, massive token cost)
```

**✅ Code Mode (Efficient):**
```
User: "Analyze payment-service.log for errors"
LLM: generates Python script:
     ```
     import tools.log_store as logs
     errors = logs.search_logs("payment-service", "ERROR", limit=100)
     print(f"Found {len(errors)} errors:")
     for e in errors[:10]:
         print(e)
     ```
System: Executes script in sandbox
System: Returns only the 10-line output to LLM
LLM: (minimal tokens used!)
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

