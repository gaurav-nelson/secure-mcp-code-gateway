# Security and RBAC Guide

This guide covers authentication, authorization, audit logging, and security best practices for the Secure MCP Code Gateway Pattern.

## Security Overview

The pattern implements multiple layers of security:

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Network Security (TLS, NetworkPolicy) │
├─────────────────────────────────────────────────┤
│ Layer 2: Authentication (OAuth, API Keys)      │
├─────────────────────────────────────────────────┤
│ Layer 3: Authorization (RBAC)                  │
├─────────────────────────────────────────────────┤
│ Layer 4: Container Security (Non-root, etc.)   │
├─────────────────────────────────────────────────┤
│ Layer 5: Audit Logging (Complete trail)        │
└─────────────────────────────────────────────────┘
```

## Authentication

### Method 1: OAuth 2.1 Tokens (Recommended for User Access)

OAuth provides secure, short-lived tokens for user authentication.

#### User Authentication Flow

```
1. User → Keycloak Login Page
2. User enters credentials
3. Keycloak validates credentials
4. Keycloak issues OAuth token (JWT)
5. User includes token in API requests
6. Gateway validates token with Keycloak
7. Gateway extracts user identity and roles
```

#### Getting an OAuth Token

**Via Browser (Manual)**:

1. Open Keycloak URL:
```bash
echo "https://$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')/realms/mcp-realm/account"
```

2. Login with your credentials
3. Get token from Keycloak (advanced users)

**Via Script** (Recommended):

```bash
./scripts/get-mcp-credentials.sh
```

This script will:
- Display Keycloak URL
- Prompt for username/password
- Retrieve OAuth token
- Show Cursor IDE configuration

**Using the Token**:

```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI..." \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'
```

#### OAuth Token Properties

| Property | Value |
|----------|-------|
| Lifetime | 5 minutes (configurable) |
| Refresh | Yes (via refresh token) |
| Revocable | Yes (via Keycloak) |
| User Identity | Included in JWT claims |
| Roles | Included in JWT claims |

#### OAuth Token Validation

The gateway validates tokens by:

1. Checking token signature with Keycloak public key
2. Verifying token expiration
3. Validating audience and issuer
4. Extracting user identity and roles

### Method 2: API Keys (Recommended for Automation)

API keys provide long-lived authentication for automated systems, CI/CD, and development.

#### Creating API Keys

```bash
# Create API key for user "alice"
./scripts/create-api-key.sh alice mcp-log-analyst never

# Create API key that expires in 1 year (31536000 seconds)
./scripts/create-api-key.sh bob mcp-log-analyst 31536000

# Create API key linked to Keycloak user
./scripts/create-api-key.sh charlie mcp-log-analyst never c7e8f9a0-1234-5678-90ab-cdef12345678
```

**Output**:
```
✅ API Key created successfully!

Key ID:   mcp-api-key-alice-1701523456
Username: alice
Roles:    mcp-log-analyst
Expires:  never

Add to Cursor (.cursor/mcp.json):
{
  "mcpServers": {
    "secure-mcp-gateway": {
      "url": "https://your-gateway-url",
      "transport": {
        "type": "http",
        "headers": {
          "Authorization": "Bearer abc123def456..."
        }
      }
    }
  }
}
```

#### Managing API Keys

**List all API keys**:
```bash
./scripts/list-api-keys.sh

# Output:
# USERNAME  KEY-ID                    ROLES              EXPIRES     CREATED
# alice     mcp-api-key-alice-1701... mcp-log-analyst    never       2025-12-01
# bob       mcp-api-key-bob-1701...   mcp-admin          2026-12-01  2025-12-01
```

**Revoke an API key**:
```bash
./scripts/revoke-api-key.sh mcp-api-key-alice-1701523456
```

**Rotate an API key**:
```bash
./scripts/rotate-api-key.sh mcp-api-key-alice-1701523456

# Creates new key, revokes old key
```

**Test an API key**:
```bash
./scripts/test-api-keys.sh
```

#### API Key Storage

API keys are stored as Kubernetes Secrets:

```bash
# View API key secret (key value is obscured)
oc get secret mcp-api-key-alice-1701523456 -n mcp-shared -o yaml
```

Secret fields:
- `key` - The actual API key (hashed in gateway)
- `username` - User identifier
- `roles` - Comma-separated roles
- `created-at` - Creation timestamp
- `expires-at` - Expiration timestamp (or "never")
- `keycloak-user-id` - Optional link to Keycloak user

#### API Key Properties

| Property | Value |
|----------|-------|
| Lifetime | Configurable (default: never) |
| Refresh | No (rotate to get new key) |
| Revocable | Yes (delete Secret) |
| User Identity | Stored in Secret |
| Roles | Stored in Secret |

### Method 3: Demo Token (Development Only)

**⚠️ WARNING: Remove in production!**

The pattern includes a demo token for testing:

```
Token: demo-token-12345
Roles: All (admin access)
```

**Usage**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer demo-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'
```

**To disable demo token in production**:

Edit gateway deployment and remove demo token logic (or set environment variable `DISABLE_DEMO_TOKEN=true`).

### Choosing Authentication Method

| Scenario | Recommended Method |
|----------|-------------------|
| Individual developer | OAuth tokens |
| CI/CD pipeline | API keys |
| Shared team account | API keys |
| Temporary testing | Demo token (dev only) |
| Production users | OAuth tokens |
| Service accounts | API keys |

## Authorization (RBAC)

### Role-Based Access Control

Users are granted roles in Keycloak. The gateway enforces access based on these roles.

### Default Roles

| Role | Access |
|------|--------|
| `mcp-admin` | All tools, all sandboxes |
| `mcp-log-analyst` | Log analysis tools only |
| `mcp-viewer` | Read-only access (if implemented) |

### Defining Custom Roles

#### Step 1: Add Role to Keycloak

1. Login to Keycloak Admin Console:
```bash
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
echo "https://$KEYCLOAK_URL/admin"
```

2. Select realm: `mcp-realm`
3. Go to "Roles" → "Add Role"
4. Enter role name: `mcp-database-admin`
5. Save

#### Step 2: Map Role to Tool Set

Edit `charts/hub/mcp-gateway/values.yaml`:

```yaml
toolSets:
  database:
    enabled: true
    description: "Database management tools"
    sandboxUrl: "http://mcp-database-sandbox.mcp-shared.svc.cluster.local:8080"
    requiredRole: "mcp-database-admin"  # New role
    tools:
      - name: "postgres_query"
        description: "Execute SQL queries"
```

#### Step 3: Assign Role to Users

1. In Keycloak Admin Console, go to "Users"
2. Select user
3. Go to "Role Mappings" tab
4. Assign role: `mcp-database-admin`

### Role Assignment Strategies

#### Strategy 1: One Role per Tool Set

```yaml
toolSets:
  log-analysis:
    requiredRole: "mcp-log-analyst"

  database:
    requiredRole: "mcp-dba"

  cloudflare:
    requiredRole: "mcp-cloudflare-user"
```

**Pros**: Fine-grained control, principle of least privilege
**Cons**: More roles to manage

#### Strategy 2: Tiered Access Levels

```yaml
toolSets:
  log-analysis:
    requiredRole: "mcp-user"  # All users

  database:
    requiredRole: "mcp-power-user"  # Advanced users

  admin-tools:
    requiredRole: "mcp-admin"  # Admins only
```

**Pros**: Simpler role management
**Cons**: Less granular control

#### Strategy 3: Admin Override

Admin role has access to everything:

```yaml
# In gateway code
if user_has_role("mcp-admin"):
    return all_tools
elif user_has_role("mcp-log-analyst"):
    return log_tools
```

### Testing RBAC

**Test as specific user**:

```bash
# Get OAuth token for user
./scripts/get-mcp-credentials.sh
# Enter user credentials

# List tools (should only see authorized tools)
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <user-token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'
```

**Expected behavior**:
- User with `mcp-log-analyst` sees only log analysis tools
- User with `mcp-admin` sees all tools
- User with no roles sees no tools (or gets error)

## Audit Logging

### What is Logged

Every request to the gateway is logged with:

```json
{
  "type": "mcp_request",
  "timestamp": "2025-12-02T10:30:45Z",
  "user": "alice",
  "method": "tools/call",
  "tool": "log_store",
  "arguments": {"query": "SELECT ..."},
  "client_ip": "10.134.0.54",
  "status": "success",
  "duration_ms": 125,
  "error": null
}
```

### Log Fields

| Field | Description |
|-------|-------------|
| `type` | Always "mcp_request" for audit logs |
| `timestamp` | ISO 8601 timestamp |
| `user` | Username from token |
| `method` | MCP method (initialize, tools/list, tools/call) |
| `tool` | Tool name (for tools/call) |
| `arguments` | Tool arguments (sanitized) |
| `client_ip` | Client IP address |
| `status` | "success" or "error" |
| `duration_ms` | Request duration in milliseconds |
| `error` | Error message (if any) |

### Viewing Audit Logs

#### Via OpenShift Console

1. Navigate to "Observe" → "Logging"
2. Enter query:

```
{app="mcp-gateway"} | json | type="mcp_request"
```

3. View results in table format

#### Via CLI

```bash
# View all audit logs
oc logs -n mcp-shared -l app=mcp-gateway | grep mcp_request

# View logs for specific user
oc logs -n mcp-shared -l app=mcp-gateway | grep mcp_request | grep '"user":"alice"'

# View failed requests
oc logs -n mcp-shared -l app=mcp-gateway | grep mcp_request | grep '"status":"error"'
```

#### Via LogCLI (Loki)

```bash
# Install logcli
curl -fSL https://github.com/grafana/loki/releases/download/v2.9.3/logcli-linux-amd64.zip -o logcli.zip
unzip logcli.zip
sudo mv logcli-linux-amd64 /usr/local/bin/logcli

# Query logs
logcli query '{app="mcp-gateway"}' --addr=https://loki.your-cluster.com
```

### Common Audit Queries

**All requests by user**:
```
{app="mcp-gateway"} | json | type="mcp_request" | user="alice"
```

**All tool calls**:
```
{app="mcp-gateway"} | json | method="tools/call"
```

**Failed requests**:
```
{app="mcp-gateway"} | json | status="error"
```

**Requests to specific tool**:
```
{app="mcp-gateway"} | json | tool="log_store"
```

**Slow requests (>1 second)**:
```
{app="mcp-gateway"} | json | duration_ms > 1000
```

**Requests from specific IP**:
```
{app="mcp-gateway"} | json | client_ip="10.134.0.54"
```

### Audit Log Retention

Configure retention in OpenShift Logging:

```yaml
logging:
  storage:
    size: 500Gi  # Increase for longer retention

  retention:
    days: 90  # Keep logs for 90 days
```

### Exporting Audit Logs

For compliance, export logs to external systems:

```bash
# Export to JSON file
logcli query '{app="mcp-gateway"} | json | type="mcp_request"' \
  --since=24h --output=jsonl > audit-logs.jsonl

# Export to S3
aws s3 cp audit-logs.jsonl s3://my-audit-bucket/logs/$(date +%Y-%m-%d).jsonl
```

## Container Security

### Security Contexts

All containers run with restrictive security contexts:

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault
  readOnlyRootFilesystem: true
```

**What this means**:
- Containers cannot run as root
- Containers cannot escalate privileges
- All Linux capabilities are dropped
- Seccomp filters system calls
- Root filesystem is read-only

### Network Policies

#### Gateway Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-gateway
spec:
  podSelector:
    matchLabels:
      app: mcp-gateway
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: openshift-ingress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: mcp-shared
        podSelector:
          matchLabels:
            app: keycloak
      ports:
        - protocol: TCP
          port: 8080
    - to:
        - namespaceSelector: {}
        podSelector:
          matchLabels:
            app: mcp-sandbox
```

#### Sandbox Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-sandbox
spec:
  podSelector:
    matchLabels:
      app: mcp-sandbox
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: mcp-gateway
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
        podSelector:
          matchLabels:
            app: dns
      ports:
        - protocol: UDP
          port: 53
```

**Sandbox is isolated**:
- Only accepts traffic from gateway
- Only allows DNS egress
- No external network access

### Image Security

**Use trusted base images**:
```yaml
image:
  repository: registry.access.redhat.com/ubi9/python-311
  tag: latest
  pullPolicy: Always
```

**Scan images for vulnerabilities**:
```bash
# Using OpenShift Container Security Operator
oc get vulnerabilities

# Using external scanner
podman scan registry.access.redhat.com/ubi9/python-311:latest
```

## Secrets Management

### Vault Integration

The pattern uses HashiCorp Vault for secrets:

```bash
# View vault status
oc get pods -n vault

# Access vault UI
oc get route vault -n vault -o jsonpath='{.spec.host}'
```

### Secrets Best Practices

1. **Never commit secrets to Git**
   - Use `values-secret.yaml` (in .gitignore)
   - Store in vault or external secrets manager

2. **Rotate secrets regularly**
   ```bash
   # Rotate API keys
   ./scripts/rotate-api-key.sh <key-id>

   # Rotate OAuth client secret
   # (regenerate in Keycloak, update secret)
   ```

3. **Use different secrets per environment**
   - Dev: Auto-generated, short-lived
   - Prod: Strong, manually managed

4. **Encrypt secrets at rest**
   - OpenShift encrypts etcd by default
   - Additional encryption with external KMS (optional)

## Security Best Practices

### 1. Authentication

✅ **Do**:
- Use OAuth tokens for user access
- Use API keys for automation
- Require strong passwords in Keycloak
- Enable MFA in Keycloak (optional)

❌ **Don't**:
- Use demo token in production
- Share API keys between users
- Store tokens in source code
- Use weak passwords

### 2. Authorization

✅ **Do**:
- Assign minimum required roles
- Review role assignments regularly
- Use specific roles per tool set
- Test RBAC thoroughly

❌ **Don't**:
- Give everyone admin role
- Use single role for all users
- Skip role assignment
- Assume RBAC is working without testing

### 3. Audit Logging

✅ **Do**:
- Monitor audit logs regularly
- Set up alerts for suspicious activity
- Export logs for compliance
- Retain logs per policy (e.g., 90 days)

❌ **Don't**:
- Disable audit logging
- Ignore failed requests
- Delete logs prematurely
- Log sensitive data (PII, secrets)

### 4. Network Security

✅ **Do**:
- Use TLS for all external traffic
- Enable NetworkPolicies
- Limit egress from sandboxes
- Use private container registry

❌ **Don't**:
- Allow unencrypted traffic
- Disable NetworkPolicies
- Allow sandbox internet access
- Use public images in production

### 5. Container Security

✅ **Do**:
- Run as non-root
- Drop all capabilities
- Use read-only filesystem
- Scan images for vulnerabilities

❌ **Don't**:
- Run as root
- Allow privilege escalation
- Use writable filesystem
- Skip image scanning

## Compliance

### SOC 2 Controls

The pattern helps meet SOC 2 requirements:

| Control | Implementation |
|---------|---------------|
| CC6.1 - Logical access | OAuth/API key authentication |
| CC6.2 - Authorization | RBAC with Keycloak roles |
| CC6.3 - Audit logging | Complete request audit trail |
| CC6.6 - Encryption | TLS for data in transit |
| CC7.2 - Change management | GitOps with PR reviews |

### GDPR Compliance

For GDPR compliance:

1. **Right to erasure**: Delete user API keys and Keycloak account
2. **Data minimization**: Only log necessary data
3. **Audit trail**: Log all access to personal data
4. **Encryption**: TLS in transit, encrypted etcd at rest

### HIPAA Compliance

For HIPAA compliance:

1. **Access controls**: RBAC + audit logging
2. **Encryption**: TLS + at-rest encryption
3. **Audit trails**: Complete logging of PHI access
4. **User training**: Train users on secure usage

## Security Incident Response

### Suspected Compromise

1. **Revoke access immediately**:
```bash
# Revoke API key
./scripts/revoke-api-key.sh <key-id>

# Disable Keycloak user
# (via Keycloak Admin Console)
```

2. **Review audit logs**:
```bash
# Check user's recent activity
oc logs -n mcp-shared -l app=mcp-gateway | grep '"user":"<username>"'
```

3. **Investigate**:
- What tools were accessed?
- What data was queried?
- When did suspicious activity occur?

4. **Remediate**:
- Reset user password
- Rotate secrets
- Review and update RBAC
- Document incident

### Security Updates

Stay updated with security patches:

```bash
# Update operators
oc get subscriptions -n mcp-shared

# Update pattern
git pull upstream main
./pattern.sh make install
```

## Next Steps

- [Extending the Pattern](EXTENDING-THE-PATTERN.md) - Add new tool sets securely
- [Troubleshooting](TROUBLESHOOTING.md) - Solve security-related issues

