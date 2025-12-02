# MCP Log Analysis Sandbox Chart

## ⚠️ THIS IS A TEMPLATE CHART - CLONE IT FOR YOUR OWN MCP SERVER

This chart deploys the **Log Analysis MCP Sandbox** - a secure, isolated execution environment where AI-generated code runs with approved tools.

**This chart is designed to be cloned** when you want to add your own MCP server to the pattern.

## What This Chart Does

The sandbox is the "secure kitchen" where code executes:

1. **Receives code from gateway** via HTTP API
2. **Executes Python scripts** in isolated container
3. **Has access ONLY to approved tools** (mounted as ConfigMap)
4. **Cannot access internet** (NetworkPolicy)
5. **Runs as non-root** with dropped capabilities
6. **Logs execution to OpenShift Logging** with structured JSON

## Architecture

```
Gateway → Sandbox (this chart) → Approved Tools (ConfigMap)
                                     ↓
                              OpenShift Logging
```

## Security Features

This sandbox implements **defense in depth**:

1. **Tool Governance**: Only approved Python modules via ConfigMap (GitOps)
2. **Container Security**: Non-root, dropped capabilities, seccomp, read-only root
3. **Network Isolation**: NetworkPolicy blocks all outbound except DNS/logging
4. **Resource Limits**: Restricted CPU/memory to prevent DoS
5. **No Service Account**: automountServiceAccountToken: false
6. **Audit Logging**: All executions logged with user identity

## How to Clone This Chart for Your Own MCP Server

### Step 1: Clone the Chart Directory

```bash
cp -r charts/hub/mcp-log-analysis-sandbox charts/hub/mcp-YOUR-SERVER-sandbox
cd charts/hub/mcp-YOUR-SERVER-sandbox
```

### Step 2: Update Chart.yaml

Edit `Chart.yaml`:

```yaml
name: mcp-YOUR-SERVER-sandbox
description: |
  MCP Sandbox for YOUR-SERVER
  
  Secure execution environment for [describe purpose]
```

### Step 3: Create Your Tool Set

Create a new directory in `tools/` for your server's APIs:

```bash
mkdir -p tools/YOUR-SERVER
```

Add your approved Python modules:

```python
# tools/YOUR-SERVER/my_api.py
"""
My API - Approved for YOUR-SERVER MCP

This module provides [describe functionality]
"""

def my_function(arg1: str) -> dict:
    """
    Does something useful in a safe way
    """
    # Implementation
    return result
```

### Step 4: Update values.yaml

Edit `values.yaml` to point to your tool set:

```yaml
sandbox:
  name: mcp-YOUR-SERVER-sandbox
  namespace: mcp-YOUR-SERVER
  
  image:
    repository: quay.io/your-org/secure-python-runtime  # or your runtime
    tag: latest
  
  tools:
    path: /home/runner/tools
    sourcePath: tools/YOUR-SERVER  # Your tool directory
```

### Step 5: Update tools-configmap.yaml

Edit `templates/tools-configmap.yaml` to mount your tools:

```yaml
data:
  my_api.py: |
{{- .Files.Get "tools/YOUR-SERVER/my_api.py" | nindent 4 }}
  
  another_tool.py: |
{{- .Files.Get "tools/YOUR-SERVER/another_tool.py" | nindent 4 }}
```

### Step 6: Update Template Files

Update all template files to use your namespace:

```bash
# Use find/replace in your editor:
# Find:    mcp-log-analysis
# Replace: mcp-YOUR-SERVER
```

Key files:
- `templates/deployment.yaml` - Update ConfigMap name
- `templates/service.yaml` - Update service name
- `templates/networkpolicy.yaml` - Update gateway label selector

### Step 7: Add to values-hub.yaml

Edit the pattern's `values-hub.yaml`:

```yaml
clusterGroup:
  applications:
    mcp-YOUR-SERVER-sandbox:
      name: mcp-YOUR-SERVER-sandbox
      namespace: openshift-gitops
      argoProject: mcp-YOUR-SERVER
      path: charts/hub/mcp-YOUR-SERVER-sandbox
```

### Step 8: Build Your Sandbox Runtime Image

Create a minimal container image with your language runtime:

Example Python Dockerfile:

```dockerfile
FROM python:3.11-slim

# Install any required packages
RUN pip install --no-cache-dir \
    flask \
    gunicorn

# Create non-root user
RUN useradd -m -u 1000 runner

# Create directories
RUN mkdir -p /home/runner/tools && \
    chown -R runner:runner /home/runner

USER runner
WORKDIR /home/runner

# Copy your sandbox server implementation
COPY --chown=runner:runner src/ ./src/

EXPOSE 8080

# Run the sandbox HTTP server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "src.server:app"]
```

The server should:
1. Accept code via HTTP POST
2. Execute it in a restricted environment
3. Return results as JSON
4. Log execution with structured JSON

### Step 9: Deploy

```bash
git add charts/hub/mcp-YOUR-SERVER-sandbox
git add tools/YOUR-SERVER
git add values-hub.yaml
git commit -m "Add YOUR-SERVER MCP sandbox"
git push
```

ArgoCD will automatically deploy your new sandbox!

## ConfigMap and Tools

The key feature is the **tools ConfigMap**:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-log-analysis-sandbox-tools
data:
  log_store.py: |
    # Content from tools/log-analysis/log_store.py
  privacy.py: |
    # Content from tools/log-analysis/privacy.py
```

- **GitOps Managed**: Tools are in Git, not in container image
- **ArgoCD Synced**: Changes to tools/ trigger automatic updates
- **Read-Only Mount**: AI cannot modify tools
- **Security Approved**: All tools reviewed via pull request

## Adding New Tools to Existing Sandbox

To add a new approved tool:

1. **Create the tool file:**
   ```bash
   vim tools/log-analysis/new_tool.py
   ```

2. **Update ConfigMap template:**
   ```yaml
   # templates/tools-configmap.yaml
   new_tool.py: |
   {{- .Files.Get "tools/log-analysis/new_tool.py" | nindent 4 }}
   ```

3. **Commit and push:**
   ```bash
   git add tools/log-analysis/new_tool.py
   git add charts/hub/mcp-log-analysis-sandbox/templates/tools-configmap.yaml
   git commit -m "Add new_tool to log-analysis sandbox"
   git push
   ```

ArgoCD will update the ConfigMap and restart the sandbox pods.

## Testing Your Sandbox

```bash
# Check sandbox is running
oc get pods -n mcp-YOUR-SERVER -l app=mcp-YOUR-SERVER-sandbox

# View logs
oc logs -n mcp-YOUR-SERVER -l app=mcp-YOUR-SERVER-sandbox

# Test from gateway pod
oc exec -n mcp-YOUR-SERVER deploy/mcp-YOUR-SERVER-gateway -- \
  curl http://mcp-YOUR-SERVER-sandbox:8080/health
```

## Security Validation

Verify security settings:

```bash
# Check securityContext
oc get pod -n mcp-YOUR-SERVER -l app=mcp-YOUR-SERVER-sandbox -o jsonpath='{.items[0].spec.securityContext}'

# Check capabilities
oc get pod -n mcp-YOUR-SERVER -l app=mcp-YOUR-SERVER-sandbox -o jsonpath='{.items[0].spec.containers[0].securityContext}'

# Check NetworkPolicy
oc get networkpolicy -n mcp-YOUR-SERVER

# Verify read-only root filesystem
oc exec -n mcp-YOUR-SERVER deploy/mcp-YOUR-SERVER-sandbox -- touch /test
# Should fail with "Read-only file system"
```

## Example AI Code Execution

When the AI generates code, it looks like this:

```python
# This code runs INSIDE the sandbox
import tools.log_store as logs
import tools.privacy as privacy

# Process large data locally
errors = logs.search_logs("payment-service", "ERROR", limit=100)

# Scrub PII before sending to LLM
safe_errors = [privacy.scrub_all_pii(e) for e in errors]

# Only return the small, clean result
print(f"Found {len(errors)} errors (sanitized):")
for err in safe_errors[:10]:
    print(err)
```

The sandbox executes this, returns only the 10-line output to the gateway, which sends it to the LLM. The 100 error lines never go to the LLM, saving massive token costs.

## Troubleshooting

### Sandbox pods not starting

Check security context:
```bash
oc describe pod -n mcp-YOUR-SERVER -l app=mcp-YOUR-SERVER-sandbox
```

### Tools not available

Check ConfigMap:
```bash
oc get cm mcp-YOUR-SERVER-sandbox-tools -n mcp-YOUR-SERVER -o yaml
```

Verify mount:
```bash
oc exec -n mcp-YOUR-SERVER deploy/mcp-YOUR-SERVER-sandbox -- ls /home/runner/tools
```

### NetworkPolicy blocking legitimate traffic

Review policy:
```bash
oc get networkpolicy mcp-YOUR-SERVER-sandbox -n mcp-YOUR-SERVER -o yaml
```

## References

- [Tool Set README](../../../tools/log-analysis/README.md)
- [Add a New MCP Server Guide](../../../docs/ADD-NEW-MCP-SERVER.md)
- [Gateway Chart](../mcp-log-analysis-gateway/README.md)
- [Pattern Architecture](../../../docs/ARCHITECTURE.md)

