# Deployment Guide

This guide provides step-by-step instructions for deploying the Secure MCP Code Gateway Pattern to Red Hat OpenShift.

## Prerequisites

### Infrastructure Requirements

- **OpenShift Cluster**: Red Hat OpenShift Container Platform 4.10 or later
- **Cluster Access**: Cluster admin privileges required for initial setup
- **Cluster Resources**:
  - 3 control plane nodes (m5.xlarge or equivalent)
  - 3 compute nodes (m5.2xlarge or equivalent)
  - 100GB+ storage for logging

### Tools Required

Install the following tools on your local machine:

- `oc` CLI (OpenShift command-line tool)
- `podman` (version 4.3.0 or later)
- `git`
- `kubectl` (optional, oc includes kubectl functionality)

### Verify Prerequisites

```bash
# Check OpenShift version
oc version

# Check cluster access
oc whoami
oc cluster-info

# Check podman version
podman --version  # Should be 4.3.0+
```

## Deployment Steps

### Step 1: Fork and Clone the Repository

Fork this repository to your own GitHub organization:

1. Go to https://github.com/validatedpatterns/secure-mcp-code-gateway
2. Click "Fork" button
3. Select your organization

Clone your forked repository:

```bash
git clone https://github.com/YOUR-ORG/secure-mcp-code-gateway.git
cd secure-mcp-code-gateway
```

**Why fork?** GitOps requires you to control the repository for making configuration changes.

### Step 2: Configure Secrets

Create your secrets file from the template:

```bash
cp values-secret.yaml.template ~/values-secret.yaml
```

Edit `~/values-secret.yaml`:

```yaml
version: "2.0"

secrets:
  # Keycloak client secret for the multi-tenant MCP gateway
  - name: mcp-gateway-client
    vaultPrefixes:
    - global
    fields:
    - name: client-secret
      onMissingValue: generate
      vaultPolicy: validatedPatternDefaultPolicy
```

**Note**: The `onMissingValue: generate` option will automatically generate secure secrets during deployment. You don't need to provide values manually.

**Security**: Never commit `values-secret.yaml` to Git! Keep it in your home directory.

### Step 3: Login to OpenShift

```bash
# Get login command from OpenShift Console:
# Click your username → "Copy login command"
oc login --token=<your-token> --server=https://api.your-cluster.com:6443

# Verify you're logged in as admin
oc whoami
oc auth can-i '*' '*' --all-namespaces
```

### Step 4: Deploy the Pattern

Deploy using the pattern.sh script:

```bash
./pattern.sh make install
```

This command will:
1. Deploy OpenShift GitOps (ArgoCD)
2. Bootstrap the Validated Patterns framework
3. Deploy all pattern components:
   - Keycloak (Red Hat SSO)
   - Multi-Tenant MCP Gateway
   - Log Analysis Sandbox (example)
   - OpenShift Logging

**Deployment Time**: 15-30 minutes depending on cluster speed

### Step 5: Monitor Deployment

Monitor the deployment progress:

```bash
# Watch ArgoCD Applications
watch oc get applications -n openshift-gitops

# All applications should show "Healthy" and "Synced"
```

Check individual application status:

```bash
# Keycloak
oc get pods -n mcp-shared
oc get keycloak -n mcp-shared

# Gateway
oc get pods -n mcp-shared -l app=mcp-gateway
oc get route -n mcp-shared mcp-gateway

# Sandbox
oc get pods -n mcp-log-analysis
oc get route -n mcp-shared

# Logging
oc get pods -n openshift-logging
```

### Step 6: Verify Deployment

Run the verification script:

```bash
./scripts/test-mcp-endpoints.sh
```

Expected output:
```
✅ Gateway deployed (2/2 pods)
✅ MCP initialize works
✅ MCP tools/list works
✅ Authentication enforced
✅ Audit logs generated
```

### Step 7: Get MCP Credentials

Get credentials for connecting Cursor IDE:

```bash
./scripts/get-mcp-credentials.sh
```

This will output:
- Gateway URL
- Keycloak URL
- Demo token (for testing)
- OAuth instructions (for production)
- Cursor IDE configuration

### Step 8: Create API Key (Recommended for Production)

For production use, create an API key instead of using OAuth tokens:

```bash
# Create API key for user "alice" with "mcp-log-analyst" role
./scripts/create-api-key.sh alice mcp-log-analyst never

# Output will include Bearer token for Cursor IDE
```

See [Security & RBAC Guide](SECURITY-AND-RBAC.md) for details.

## Post-Deployment Configuration

### Configure Keycloak Users

1. Get Keycloak admin credentials:

```bash
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
ADMIN_PASSWORD=$(oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)

echo "Keycloak Admin Console: https://$KEYCLOAK_URL"
echo "Username: admin"
echo "Password: $ADMIN_PASSWORD"
```

2. Login to Keycloak Admin Console
3. Select realm: `mcp-realm`
4. Create users:
   - Click "Users" → "Add user"
   - Set username, email, first/last name
   - Click "Save"
5. Set password:
   - Click "Credentials" tab
   - Set password (temporary: off)
   - Click "Set Password"
6. Assign roles:
   - Click "Role Mappings" tab
   - Available roles:
     - `mcp-admin` - Full access to all tools
     - `mcp-log-analyst` - Access to log analysis tools
     - `mcp-viewer` - Read-only access

### Enable Additional Tool Sets

The pattern includes example tool set definitions in `charts/hub/mcp-gateway/values.yaml`:

```yaml
toolSets:
  log-analysis:
    enabled: true  # Already enabled

  cloudflare:
    enabled: false  # Enable when you deploy cloudflare sandbox

  database:
    enabled: false  # Enable when you deploy database sandbox
```

To enable additional tool sets:
1. Deploy the corresponding sandbox (see [Extending Guide](EXTENDING-THE-PATTERN.md))
2. Edit `values.yaml` and set `enabled: true`
3. Commit and push to Git
4. ArgoCD will automatically sync

### Configure Logging

OpenShift Logging is deployed automatically. To query logs:

1. Open OpenShift Console
2. Navigate to "Observe" → "Logging"
3. Query MCP audit logs:

```
{app="mcp-gateway"} | json | type="mcp_request"
```

Example queries:
```
# All requests by user "alice"
{app="mcp-gateway"} | json | type="mcp_request" | user="alice"

# All tool calls
{app="mcp-gateway"} | json | method="tools/call"

# All errors
{app="mcp-gateway"} | json | status="error"
```

## Cursor IDE Integration

### Add MCP Server to Cursor

Create or edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "secure-mcp-gateway": {
      "url": "https://mcp-gateway-mcp-shared.apps.your-cluster.com",
      "transport": {
        "type": "http",
        "headers": {
          "Authorization": "Bearer YOUR-API-KEY-OR-TOKEN-HERE"
        }
      }
    }
  }
}
```

Replace:
- `https://mcp-gateway-mcp-shared.apps.your-cluster.com` with your actual gateway URL
- `YOUR-API-KEY-OR-TOKEN-HERE` with your API key or OAuth token

### Restart Cursor

```
Cmd/Ctrl + Shift + P → "Reload Window"
```

### Verify in Cursor

Ask Cursor AI:

```
"What MCP servers are available?"
"Use log_store to search logs"
```

Cursor should discover and use your MCP tools.

## Troubleshooting

### ArgoCD Application Not Syncing

```bash
# Check ArgoCD application status
oc get application -n openshift-gitops mcp-gateway -o yaml

# Force sync
oc patch application mcp-gateway -n openshift-gitops \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

### Gateway Pods Not Starting

```bash
# Check pod status
oc get pods -n mcp-shared -l app=mcp-gateway

# Check pod logs
oc logs -n mcp-shared -l app=mcp-gateway --tail=100

# Check events
oc get events -n mcp-shared --sort-by='.lastTimestamp'
```

### Authentication Failures

```bash
# Test with demo token
curl -k -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer demo-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'

# Check Keycloak status
oc get keycloak -n mcp-shared
oc get pods -n mcp-shared -l app=keycloak
```

### Sandbox Not Reachable

```bash
# Check sandbox pods
oc get pods -n mcp-log-analysis

# Check service
oc get service -n mcp-shared mcp-log-analysis-sandbox

# Test connectivity from gateway
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -v http://mcp-log-analysis-sandbox.mcp-shared.svc:8080/health
```

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more issues and solutions.

## Uninstalling the Pattern

To remove the pattern from your cluster:

```bash
# Uninstall pattern
./pattern.sh make uninstall

# Remove namespaces
oc delete namespace mcp-shared
oc delete namespace mcp-log-analysis
oc delete namespace openshift-logging

# Remove ArgoCD applications
oc delete applications -n openshift-gitops -l pattern=secure-mcp-code-gateway
```

**Warning**: This will delete all data, including Keycloak users and API keys.

## Upgrading the Pattern

To upgrade to a new version:

```bash
# Pull latest changes from upstream
git remote add upstream https://github.com/validatedpatterns/secure-mcp-code-gateway.git
git fetch upstream
git merge upstream/main

# Resolve any conflicts in your values files

# Commit and push
git add .
git commit -m "Upgrade pattern to latest version"
git push

# ArgoCD will automatically sync
```

## Advanced Deployment Options

### Deploy to Different Namespaces

Edit `values-hub.yaml` to change namespaces:

```yaml
clusterGroup:
  name: hub
  namespaces:
    - mcp-shared-custom      # Change from mcp-shared
    - mcp-log-analysis-custom  # Change from mcp-log-analysis
```

### Deploy with Custom Container Registry

Edit `charts/hub/mcp-gateway/values.yaml`:

```yaml
gateway:
  image:
    repository: quay.io/your-org/mcp-gateway
    tag: v1.0.0
```

Build and push your custom gateway image:

```bash
# Build image from your gateway implementation
podman build -t quay.io/your-org/mcp-gateway:v1.0.0 .
podman push quay.io/your-org/mcp-gateway:v1.0.0
```

### Deploy with External Keycloak

If you have an existing Keycloak instance:

1. Edit `values-hub.yaml` and disable Keycloak deployment:

```yaml
applications:
  keycloak-sso:
    enabled: false
```

2. Edit `charts/hub/mcp-gateway/values.yaml`:

```yaml
gateway:
  keycloak:
    url: "https://your-keycloak.example.com"
    realm: "mcp-realm"
    clientId: "mcp-gateway-client"
```

3. Create client in your Keycloak manually
4. Store client secret in `values-secret.yaml`

### Deploy with Custom CA Certificate

If your cluster uses custom CA certificates:

```bash
# Create ConfigMap with CA certificate
oc create configmap custom-ca \
  -n mcp-shared \
  --from-file=ca.crt=/path/to/ca.crt

# Mount in gateway deployment (add to values.yaml)
```

## Resource Requirements

### Minimum Resources

- **Control Plane**: 3 nodes × 4 vCPU, 16GB RAM
- **Compute**: 3 nodes × 8 vCPU, 32GB RAM
- **Storage**: 100GB for logs

### Typical Resource Allocation

| Component | Pods | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|------|-------------|-----------|----------------|--------------|
| Gateway | 2 | 200m | 500m | 256Mi | 512Mi |
| Keycloak | 1 | 500m | 1000m | 512Mi | 1Gi |
| Sandbox | 1 per toolset | 100m | 500m | 128Mi | 512Mi |
| Logging | 3 | 1000m | 2000m | 2Gi | 4Gi |

### Scaling for Production

For high-traffic production deployments:

```yaml
# Gateway scaling
gateway:
  replicas: 5
  resources:
    requests:
      cpu: "500m"
      memory: "512Mi"
    limits:
      cpu: "2000m"
      memory: "2Gi"

# Sandbox scaling
sandbox:
  replicas: 3
  resources:
    requests:
      cpu: "500m"
      memory: "512Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
```

## Next Steps

- [Configuration Guide](CONFIGURATION.md) - Customize your deployment
- [Security & RBAC](SECURITY-AND-RBAC.md) - Secure your deployment
- [Extending the Pattern](EXTENDING-THE-PATTERN.md) - Add your own tool sets

