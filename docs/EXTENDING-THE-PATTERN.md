# Extending the Pattern

This guide shows you how to add your own tool sets and MCP servers to the pattern.

## Overview

The multi-tenant architecture makes it easy to add new tool sets:

```
Existing:                      You Add:
┌──────────┐                  ┌──────────┐
│ Gateway  │─────┬────────────│ Gateway  │─────┬────────────────┐
│ (shared) │     │            │ (shared) │     │                │
└──────────┘     │            └──────────┘     │                │
                 │                             │                │
         ┌───────┴────────┐           ┌───────┴────────┐   ┌───┴─────┐
         │  Log Analysis  │           │  Log Analysis  │   │  Your   │
         │    Sandbox     │           │    Sandbox     │   │ Sandbox │
         └────────────────┘           └────────────────┘   └─────────┘
```

**Key Point**: You don't deploy a new gateway! Just add a sandbox and update the gateway configuration.

## Available Core Tools

Before creating custom tools, note that several core tools are available in the log-analysis sandbox that you can reuse:

| Tool | Purpose |
|------|---------|
| `execute_code` | Execute Python code safely in the sandbox |
| `workspace` | Persistent file storage (checkpoints, state) |
| `skills` | Save and run reusable code patterns |
| `tool_discovery` | Browse and discover available tools |

These implement the [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) pattern from Anthropic.

## Quick Start: Add a New Tool Set

### Step 1: Create Your Tools

Create a directory for your tools:

```bash
mkdir -p tools/database
```

Create a Python file with your tool functions:

```python
# tools/database/postgres.py
"""
Database Tools - Approved for database-sandbox MCP Server
"""

def execute_query(database: str, query: str, limit: int = 100):
    """
    Execute a SQL query against a database.

    Args:
        database: Database name (e.g., "customers")
        query: SQL query to execute
        limit: Maximum rows to return (default: 100)

    Returns:
        Query results as list of dictionaries
    """
    # Your implementation here
    # Connect to database, execute query, return results
    pass

def get_table_schema(database: str, table: str):
    """
    Get schema information for a table.

    Args:
        database: Database name
        table: Table name

    Returns:
        Dictionary with column names, types, and constraints
    """
    # Your implementation here
    pass
```

**Best Practices for Tools**:
- Document each function with clear docstrings
- Validate all inputs
- Limit output size (don't return millions of rows)
- Handle errors gracefully
- Never expose sensitive data directly

### Step 2: Clone the Sandbox Chart

Copy the example sandbox chart:

```bash
cp -r charts/hub/mcp-log-analysis-sandbox charts/hub/mcp-database-sandbox
```

Edit `charts/hub/mcp-database-sandbox/Chart.yaml`:

```yaml
apiVersion: v2
name: mcp-database-sandbox
description: Database management MCP server sandbox
type: application
version: 0.1.0
appVersion: "1.0"
```

Edit `charts/hub/mcp-database-sandbox/values.yaml`:

```yaml
sandbox:
  name: mcp-database-sandbox
  namespace: mcp-database
  replicas: 1

  image:
    repository: registry.access.redhat.com/ubi9/python-311
    tag: latest
    pullPolicy: Always

  tools:
    path: /home/runner/tools
    sourcePath: tools/database  # Your tools directory

  service:
    port: 8080
    targetPort: 8080

  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"

  securityContext:
    allowPrivilegeEscalation: false
    runAsNonRoot: true
    capabilities:
      drop:
        - ALL
    seccompProfile:
      type: RuntimeDefault
    readOnlyRootFilesystem: true

  networkPolicy:
    enabled: true
    allowFromGateway: true
    denyAll: true
```

### Step 3: Update Gateway Configuration

Edit `charts/hub/mcp-gateway/values.yaml`:

Add your tool set to the `toolSets` section:

```yaml
gateway:
  toolSets:
    # Existing tool sets...
    log-analysis:
      enabled: true
      description: "Efficient log processing and analysis tools"
      sandboxUrl: "http://mcp-log-analysis-sandbox.mcp-shared.svc.cluster.local:8080"
      requiredRole: "mcp-log-analyst"
      tools:
        - name: "log_store"
          description: "Search and analyze logs efficiently"
        - name: "privacy"
          description: "Scrub PII from text and logs"

    # Your new tool set
    database:
      enabled: true
      description: "Database query and management tools"
      sandboxUrl: "http://mcp-database-sandbox.mcp-shared.svc.cluster.local:8080"
      requiredRole: "mcp-dba"
      tools:
        - name: "execute_query"
          description: "Execute SQL queries against databases"
        - name: "get_table_schema"
          description: "Get table schema information"
```

### Step 4: Add to Hub Configuration

Edit `values-hub.yaml` to deploy your sandbox:

```yaml
clusterGroup:
  namespaces:
    - mcp-shared
    - mcp-log-analysis
    - mcp-database  # Add your namespace

  applications:
    # Existing applications...

    mcp-database-sandbox:
      name: mcp-database-sandbox
      namespace: openshift-gitops
      path: charts/hub/mcp-database-sandbox
      argoProject: mcp-shared
```

### Step 5: Create Keycloak Role

1. Login to Keycloak Admin Console:
```bash
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
echo "https://$KEYCLOAK_URL/admin"
```

2. Select realm: `mcp-realm`
3. Go to "Roles" → "Add Role"
4. Enter role name: `mcp-dba`
5. Save

### Step 6: Commit and Deploy

```bash
# Commit your changes
git add .
git commit -m "Add database tool set"
git push

# ArgoCD will automatically sync and deploy
```

### Step 7: Verify Deployment

```bash
# Check sandbox deployment
oc get pods -n mcp-database

# Check gateway can reach sandbox
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -v http://mcp-database-sandbox.mcp-shared.svc:8080/health

# Test via gateway
curl -k -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer demo-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Should see your new tools!
```

## Advanced: Custom Sandbox Runtime

For more complex tool sets, build a custom container image.

### Step 1: Create Dockerfile

```dockerfile
# Dockerfile
FROM registry.access.redhat.com/ubi9/python-311:latest

# Install dependencies
USER 0
RUN dnf install -y \
    postgresql-client \
    && dnf clean all

USER 1001

# Install Python packages
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy sandbox runtime
COPY sandbox-runtime.py /app/
WORKDIR /app

EXPOSE 8080
CMD ["python", "sandbox-runtime.py"]
```

Create `requirements.txt`:

```
psycopg2-binary==2.9.9
requests==2.31.0
```

Create `sandbox-runtime.py`:

```python
#!/usr/bin/env python3
"""
MCP Sandbox Runtime

Receives tool execution requests from the gateway and executes approved tools.
"""

import json
import sys
import importlib
from http.server import HTTPServer, BaseHTTPRequestHandler

class SandboxHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle tool execution request."""
        content_length = int(self.headers['Content-Length'])
        request_body = self.rfile.read(content_length)
        request = json.loads(request_body)

        tool_name = request.get('tool')
        arguments = request.get('arguments', {})

        try:
            # Load tool module dynamically
            module = importlib.import_module(f'tools.{tool_name}')

            # Get function from module
            func = getattr(module, tool_name)

            # Execute tool
            result = func(**arguments)

            # Return result
            response = {
                'status': 'success',
                'result': result
            }
            self.send_response(200)
        except Exception as e:
            response = {
                'status': 'error',
                'error': str(e)
            }
            self.send_response(500)

        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_GET(self):
        """Health check endpoint."""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), SandboxHandler)
    print('Sandbox runtime started on port 8080')
    server.serve_forever()
```

### Step 2: Build and Push Image

```bash
# Build image
podman build -t quay.io/your-org/mcp-database-sandbox:v1.0.0 .

# Test locally
podman run -p 8080:8080 quay.io/your-org/mcp-database-sandbox:v1.0.0

# Push to registry
podman push quay.io/your-org/mcp-database-sandbox:v1.0.0
```

### Step 3: Update Values

Edit `charts/hub/mcp-database-sandbox/values.yaml`:

```yaml
sandbox:
  image:
    repository: quay.io/your-org/mcp-database-sandbox
    tag: v1.0.0
    pullPolicy: IfNotPresent
```

## Advanced: Network Access for Sandboxes

By default, sandboxes cannot access external networks. If your tool needs to call external APIs or databases:

### Option 1: Allow Specific Egress (Recommended)

Edit sandbox NetworkPolicy:

```yaml
# charts/hub/mcp-database-sandbox/templates/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .Values.sandbox.name }}
  namespace: {{ .Values.sandbox.namespace }}
spec:
  podSelector:
    matchLabels:
      app: {{ .Values.sandbox.name }}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: mcp-shared
          podSelector:
            matchLabels:
              app: mcp-gateway
  egress:
    # Allow DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: openshift-dns
      ports:
        - protocol: UDP
          port: 53

    # Allow access to specific database
    - to:
        - namespaceSelector:
            matchLabels:
              name: databases
          podSelector:
            matchLabels:
              app: postgresql
      ports:
        - protocol: TCP
          port: 5432
```

### Option 2: Allow All Egress (Use with Caution)

```yaml
sandbox:
  networkPolicy:
    enabled: true
    allowFromGateway: true
    denyAll: false  # Allows all egress
```

**Security Warning**: Only use this if absolutely necessary. Prefer specific egress rules.

## Advanced: Persistent Storage

If your tools need persistent storage:

### Step 1: Create PVC

```yaml
# charts/hub/mcp-database-sandbox/templates/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ .Values.sandbox.name }}-data
  namespace: {{ .Values.sandbox.namespace }}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Step 2: Mount in Deployment

```yaml
# charts/hub/mcp-database-sandbox/templates/deployment.yaml
spec:
  template:
    spec:
      containers:
        - name: sandbox
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: {{ .Values.sandbox.name }}-data
```

### Step 3: Use in Tools

```python
# tools/database/cache.py
def cache_query_result(query: str, result: dict):
    """Cache query results to persistent storage."""
    import json
    cache_path = "/data/cache/query_cache.json"

    # Write to persistent volume
    with open(cache_path, 'w') as f:
        json.dump({query: result}, f)
```

## Best Practices

### Tool Development

1. **Document thoroughly**: AI assistants read docstrings
2. **Validate inputs**: Never trust input from LLMs
3. **Limit output**: Return summaries, not raw data
4. **Handle errors**: Graceful error messages
5. **Security first**: Never expose credentials

Example:

```python
def my_tool(param: str, limit: int = 100) -> dict:
    """
    Short description for AI assistant.

    Detailed explanation of what the tool does, when to use it,
    and what results to expect.

    Args:
        param: Description of parameter
        limit: Maximum results (default: 100, max: 1000)

    Returns:
        Dictionary with results

    Raises:
        ValueError: If param is invalid
        RuntimeError: If operation fails
    """
    # Validate inputs
    if not param:
        raise ValueError("param cannot be empty")

    if limit > 1000:
        limit = 1000  # Enforce maximum

    try:
        # Your implementation
        result = do_something(param)

        # Limit output size
        return result[:limit]
    except Exception as e:
        raise RuntimeError(f"Tool failed: {e}")
```

### Resource Planning

1. **Start small**: Default resources are sufficient for most tools
2. **Monitor**: Use `oc adm top pods` to check actual usage
3. **Scale up**: Increase resources if needed
4. **Scale out**: Add replicas for high traffic

```yaml
# Low traffic (default)
sandbox:
  replicas: 1
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"

# High traffic
sandbox:
  replicas: 3
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
```

### Security

1. **Review tools in pull requests**: Never auto-deploy untrusted code
2. **Use least privilege**: Minimal network access, no root, dropped capabilities
3. **Rotate secrets**: If tools use credentials, rotate regularly
4. **Audit usage**: Monitor who's using which tools

### Testing

Test your tools before deploying:

```bash
# Unit test
cd tools/database
python -m pytest test_postgres.py

# Integration test (local)
podman run -p 8080:8080 your-sandbox:latest
curl -X POST http://localhost:8080/execute \
  -d '{"tool":"execute_query","arguments":{"database":"test","query":"SELECT 1"}}'

# Integration test (cluster)
oc port-forward -n mcp-database deployment/mcp-database-sandbox 8080:8080
curl -X POST http://localhost:8080/execute \
  -d '{"tool":"execute_query","arguments":{"database":"test","query":"SELECT 1"}}'
```

## Common Patterns

### Pattern 1: API Integration

Connect to external REST APIs:

```python
# tools/github/repos.py
import requests

def list_repositories(org: str, limit: int = 10) -> list:
    """List repositories for a GitHub organization."""
    url = f"https://api.github.com/orgs/{org}/repos"

    response = requests.get(url, params={"per_page": limit})
    response.raise_for_status()

    repos = response.json()
    return [{"name": r["name"], "stars": r["stargazers_count"]} for r in repos]
```

### Pattern 2: Database Queries

Execute database queries efficiently:

```python
# tools/database/postgres.py
import psycopg2

def execute_query(database: str, query: str, limit: int = 100) -> list:
    """Execute SQL query and return results."""
    conn = psycopg2.connect(
        host="postgres.databases.svc",
        database=database,
        user="readonly_user",
        password=os.getenv("DB_PASSWORD")
    )

    cursor = conn.cursor()
    cursor.execute(f"{query} LIMIT {limit}")

    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]
```

### Pattern 3: File Processing

Process files from persistent storage:

```python
# tools/documents/parser.py
def parse_document(filename: str) -> dict:
    """Parse document and return structured data."""
    filepath = f"/data/uploads/{filename}"

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Document {filename} not found")

    # Parse document (PDF, DOCX, etc.)
    content = extract_text(filepath)

    return {
        "filename": filename,
        "word_count": len(content.split()),
        "summary": content[:500]
    }
```

### Pattern 4: Data Aggregation

Aggregate large datasets efficiently:

```python
# tools/analytics/metrics.py
def get_metrics_summary(service: str, hours: int = 24) -> dict:
    """Aggregate metrics for a service."""
    # Process large dataset locally
    metrics = load_metrics(service, hours)

    # Return only summary, not raw data
    return {
        "service": service,
        "requests": sum(m["count"] for m in metrics),
        "avg_latency_ms": sum(m["latency"] for m in metrics) / len(metrics),
        "error_rate": sum(1 for m in metrics if m["error"]) / len(metrics),
        "top_endpoints": get_top_endpoints(metrics, 5)
    }
```

## Troubleshooting

### Sandbox Not Starting

```bash
# Check pod status
oc get pods -n mcp-database

# Check pod logs
oc logs -n mcp-database -l app=mcp-database-sandbox

# Check events
oc get events -n mcp-database --sort-by='.lastTimestamp'
```

### Gateway Can't Reach Sandbox

```bash
# Test connectivity
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -v http://mcp-database-sandbox.mcp-shared.svc:8080/health

# Check service
oc get service -n mcp-shared mcp-database-sandbox

# Check NetworkPolicy
oc describe networkpolicy -n mcp-database
```

### Tools Not Appearing

```bash
# Check gateway configuration
oc get configmap -n mcp-shared mcp-gateway-toolsets -o yaml

# Check if tool set is enabled
# (Look for enabled: true in gateway values.yaml)

# Check user roles
# (User must have requiredRole to see tools)
```

## Next Steps

- [Configuration Guide](CONFIGURATION.md) - Customize your sandboxes
- [Security & RBAC](SECURITY-AND-RBAC.md) - Secure your tool sets
- [Troubleshooting](TROUBLESHOOTING.md) - Solve common issues

