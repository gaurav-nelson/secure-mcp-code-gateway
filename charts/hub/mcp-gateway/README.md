# Multi-Tenant MCP Gateway Chart

This is the **default gateway** for the Secure MCP Code Gateway pattern. It routes tool calls to multiple sandboxes based on tool name prefixes and user permissions.

## What Is This?

A **single gateway** that serves **multiple tool sets** (multiple "MCP servers"). Users authenticate once via Keycloak, and the gateway routes their requests to the appropriate sandbox.

## Architecture

```
User → Keycloak (Auth) → Multi-Tenant Gateway → Routes to:
                                                   ├→ Log Analysis Sandbox
                                                   ├→ Cloudflare Sandbox
                                                   ├→ Database Sandbox
                                                   └→ Your Custom Sandboxes
```

### Benefits

- ✅ **One gateway for all tool sets** (not N gateways for N tool sets)
- ✅ **Centralized authentication** via shared Keycloak
- ✅ **RBAC per tool set** (different roles for different sandboxes)
- ✅ **Single audit trail** for all requests
- ✅ **Easy to extend** (add new sandboxes without deploying new gateways)

---

## How Tool Routing Works

The gateway routes based on **tool name prefixes**:

| Tool Name | Routes To | Required Role |
|-----------|-----------|---------------|
| `log_store_*` | Log Analysis Sandbox | `mcp-log-analyst` |
| `privacy_*` | Log Analysis Sandbox | `mcp-log-analyst` |
| `cloudflare_*` | Cloudflare Sandbox | `mcp-cloudflare-user` |
| `postgres_*` | Database Sandbox | `mcp-dba` |

Example:
```python
# User calls: log_store_search("error", limit=10)
# Gateway sees: tool name starts with "log_store"
# Gateway checks: user has role "mcp-log-analyst"
# Gateway routes to: http://mcp-log-analysis-sandbox:8080
```

---

## Configuration

### Tool Sets

Define tool sets in `values.yaml`:

```yaml
gateway:
  toolSets:
    my-service:
      enabled: true
      description: "My custom service tools"
      sandboxUrl: "http://mcp-my-service-sandbox.mcp-shared.svc:8080"
      requiredRole: "mcp-my-service-user"
      tools:
        - name: "my_service_tool"
          description: "Does something useful"
```

### Environment Variables

The gateway passes these to sandboxes:

- `KEYCLOAK_URL` - Keycloak endpoint for token validation
- `KEYCLOAK_REALM` - OAuth realm name
- `KEYCLOAK_CLIENT_ID` - OAuth client ID
- `KEYCLOAK_CLIENT_SECRET` - OAuth client secret (from Vault)

---

## Adding a New Tool Set

### Step 1: Create Your Tools

```bash
mkdir -p tools/my-service/
cat > tools/my-service/api.py <<'EOF'
def my_tool(arg):
    """My custom tool."""
    return f"Processing: {arg}"
EOF
```

### Step 2: Deploy a Sandbox

```bash
# Create ConfigMap with your tools
oc create configmap mcp-my-service-tools \
  --from-file=tools/my-service/ \
  -n mcp-shared

# Deploy sandbox using the standard template
helm install mcp-my-service-sandbox \
  charts/hub/mcp-sandbox-template \
  --set sandbox.name=mcp-my-service-sandbox \
  --set sandbox.namespace=mcp-shared \
  --set sandbox.toolsConfigMap=mcp-my-service-tools
```

### Step 3: Update Gateway Configuration

Edit `charts/hub/mcp-gateway/values.yaml`:

```yaml
gateway:
  toolSets:
    # ... existing tool sets ...
    
    my-service:  # ADD THIS
      enabled: true
      description: "My custom service tools"
      sandboxUrl: "http://mcp-my-service-sandbox.mcp-shared.svc:8080"
      requiredRole: "mcp-my-service-user"
      tools:
        - name: "my_service"
          description: "Custom tool for my service"
```

### Step 4: Add Keycloak Role

In Keycloak admin console, add role: `mcp-my-service-user`

### Step 5: Deploy

```bash
git add charts/hub/mcp-gateway/values.yaml
git commit -m "Add my-service tool set"
git push

# ArgoCD automatically syncs the updated configuration
# Gateway pods restart and load the new tool set
```

**That's it!** No new gateway deployed. The existing gateway now routes `my_service_*` tools to your new sandbox.

---

## Placeholder vs Production

### Current Implementation (Placeholder)

The chart includes a **Python placeholder** that:
- ✅ Shows the multi-tenant architecture
- ✅ Loads tool set configuration from ConfigMap
- ✅ Provides health endpoints
- ✅ Returns tool set information
- ❌ Does NOT implement actual MCP protocol
- ❌ Does NOT route to sandboxes
- ❌ Does NOT validate OAuth tokens

### Production Implementation

For production, **build a real gateway** that:

1. **Implements MCP Protocol**
   - Handles MCP requests/responses
   - Supports streaming if needed

2. **Validates Authentication**
   - Checks OAuth tokens with Keycloak
   - Extracts user identity and roles

3. **Routes to Sandboxes**
   - Determines correct sandbox from tool name
   - Forwards requests with user context

4. **Enforces RBAC**
   - Checks user has required role for tool set
   - Returns 403 if permission denied

5. **Logs Audit Trail**
   - Records all requests with user identity
   - Logs to OpenShift Logging (Loki)

### Example Production Gateway

See `docs/MULTI-TENANT-GATEWAY.md` for a complete implementation example in Python.

Key code structure:

```python
class MultiTenantGateway:
    async def execute_tool(self, tool_name, arguments, user_token):
        # 1. Validate token with Keycloak
        user = await self.validate_keycloak_token(user_token)
        
        # 2. Find sandbox for this tool
        tool_set_name, config = self.get_tool_set(tool_name)
        
        # 3. Check permissions
        if not self.check_permission(user, config):
            raise HTTPException(403, "Access denied")
        
        # 4. Route to sandbox
        response = await self.call_sandbox(
            config['sandboxUrl'],
            tool_name,
            arguments,
            user
        )
        
        # 5. Log audit trail
        await self.log_audit(user, tool_name, response)
        
        return response
```

---

## Comparison with Per-MCP Gateway

| Aspect | Multi-Tenant (This Chart) | Per-MCP Gateway |
|--------|---------------------------|-----------------|
| Gateways to deploy | 1 | N (one per tool set) |
| OAuth clients | 1 | N |
| Routes/certificates | 1 | N |
| Adding new tool set | Update config | Deploy new gateway |
| Memory overhead | 256MB | N × 256MB |
| Operational complexity | Low | Medium to High |
| User experience | Single endpoint | Multiple endpoints |

**Use Per-MCP Gateway when:**
- Strict isolation required (different security zones)
- Different authentication systems
- Completely different teams/organizations

**Use Multi-Tenant (this chart) when:**
- Shared Keycloak authentication
- Same cluster/namespace
- Want operational simplicity

---

## Security

### Isolation

Tool sets run in **separate sandboxes** with their own:
- SecurityContext (non-root, dropped capabilities)
- NetworkPolicy (controlled egress)
- Resource limits

The gateway provides **authentication and routing**, not isolation. Isolation comes from sandboxes.

### RBAC

Permissions are enforced via Keycloak roles:

```
User alice:
  roles: [mcp-log-analyst]
  can access: log-analysis tools
  cannot access: cloudflare tools

User bob:
  roles: [mcp-cloudflare-user, mcp-dba]
  can access: cloudflare + database tools
  cannot access: log-analysis tools

User admin:
  roles: [mcp-admin]
  can access: ALL tools
```

### Audit Trail

All requests logged with:
- User identity (from Keycloak token)
- Tool set name
- Tool name
- Arguments (be careful with sensitive data!)
- Response status
- Timestamp

Logs flow to OpenShift Logging (Loki) for compliance.

---

## Monitoring

### Health Endpoints

- `GET /health` - Liveness probe (is gateway running?)
- `GET /ready` - Readiness probe (can gateway serve requests?)
- `GET /` - Info endpoint (list tool sets and configuration)

### Metrics to Track

- Request rate per tool set
- Request latency per tool set
- Error rate per tool set
- Sandbox response time
- Keycloak validation time

### Troubleshooting

**Gateway pods not starting:**
```bash
oc logs -n mcp-shared -l app=mcp-gateway
oc describe pod -n mcp-shared -l app=mcp-gateway
```

**ConfigMap not loading:**
```bash
oc get configmap mcp-gateway-toolsets -n mcp-shared -o yaml
# Check if toolSets are correctly formatted
```

**Sandbox not reachable:**
```bash
# Test from gateway pod
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl http://mcp-log-analysis-sandbox.mcp-shared.svc:8080/health
```

---

## Scaling

### Horizontal Scaling

```yaml
gateway:
  replicas: 5  # Scale based on load
```

Gateway is **stateless** - safe to scale horizontally.

### Vertical Scaling

```yaml
gateway:
  resources:
    requests:
      memory: "512Mi"  # Increase for high throughput
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
```

### Load Testing

```bash
# Generate load
for i in {1..1000}; do
  curl https://mcp-gateway-mcp-shared.apps.your-cluster.com/ &
done
wait

# Check pod metrics
oc adm top pods -n mcp-shared -l app=mcp-gateway
```

---

## Migration from Per-MCP Gateways

If you started with separate gateways (e.g., `mcp-log-analysis-gateway`, `mcp-cloudflare-gateway`), migrate to multi-tenant:

### Step 1: Deploy Multi-Tenant Gateway

Keep existing gateways running. Deploy the multi-tenant gateway alongside them:

```bash
helm install mcp-gateway charts/hub/mcp-gateway
```

### Step 2: Configure All Tool Sets

Add all existing tool sets to `values.yaml`:

```yaml
toolSets:
  log-analysis: { ... }  # From old mcp-log-analysis-gateway
  cloudflare: { ... }    # From old mcp-cloudflare-gateway
```

### Step 3: Test

Verify the multi-tenant gateway routes correctly:

```bash
GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}')
curl https://$GATEWAY_URL/
# Should show all tool sets
```

### Step 4: Switch Users

Update user-facing documentation/config to point to the multi-tenant gateway URL.

### Step 5: Decommission Old Gateways

Once all users migrated:

```bash
helm uninstall mcp-log-analysis-gateway
helm uninstall mcp-cloudflare-gateway
# Keep the sandboxes!
```

---

## References

- [Multi-Tenant Gateway Implementation Guide](../../../docs/MULTI-TENANT-GATEWAY.md)
- [Architecture Documentation](../../../docs/ARCHITECTURE.md)
- [RBAC Configuration](../../../docs/RBAC-GUIDE.md)
- [Adding New Tool Sets](../../../docs/ADD-NEW-MCP-SERVER.md)

