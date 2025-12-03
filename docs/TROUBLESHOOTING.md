# Troubleshooting Guide

This guide helps you diagnose and fix common issues with the Secure MCP Code Gateway Pattern.

## Quick Diagnostics

### Check Overall Health

```bash
# Check all pods
oc get pods -n mcp-shared
oc get pods -n mcp-log-analysis
oc get pods -n openshift-logging

# Check ArgoCD applications
oc get applications -n openshift-gitops

# Check routes
oc get routes -n mcp-shared
```

### Run Test Script

```bash
./scripts/test-mcp-endpoints.sh
```

This script checks:
- Gateway deployment
- MCP protocol endpoints
- Authentication
- Sandbox connectivity
- Audit logging

## Deployment Issues

### Issue: ArgoCD Application Not Syncing

**Symptoms**:
```bash
oc get application mcp-gateway -n openshift-gitops
# Status: OutOfSync or Unknown
```

**Diagnosis**:
```bash
# Check application status
oc get application mcp-gateway -n openshift-gitops -o yaml

# Check ArgoCD logs
oc logs -n openshift-gitops -l app.kubernetes.io/name=openshift-gitops-application-controller
```

**Solutions**:

1. **Force sync**:
```bash
oc patch application mcp-gateway -n openshift-gitops \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

2. **Check Git repository access**:
```bash
# Verify ArgoCD can access your Git repo
oc get secret -n openshift-gitops
```

3. **Check values syntax**:
```bash
# Validate Helm chart
helm template charts/hub/mcp-gateway/
```

4. **Review application spec**:
```bash
# Check for typos in path or repoURL
oc get application mcp-gateway -n openshift-gitops -o yaml
```

### Issue: Namespace Not Created

**Symptoms**:
```bash
oc get namespace mcp-shared
# Error: namespace "mcp-shared" not found
```

**Solution**:

Check `values-hub.yaml` includes the namespace:

```yaml
clusterGroup:
  namespaces:
    - mcp-shared
```

If missing, add it and redeploy:
```bash
./pattern.sh make install
```

### Issue: Operator Subscription Failed

**Symptoms**:
```bash
oc get subscription rhsso-operator -n mcp-shared
# Status: Failed or UpgradePending
```

**Diagnosis**:
```bash
# Check subscription status
oc get subscription rhsso-operator -n mcp-shared -o yaml

# Check operator pod
oc get pods -n mcp-shared -l app=rhsso-operator

# Check catalog source
oc get catalogsource -n openshift-marketplace
```

**Solutions**:

1. **Delete and recreate subscription**:
```bash
oc delete subscription rhsso-operator -n mcp-shared
# ArgoCD will recreate it
```

2. **Check operator catalog**:
```bash
oc get packagemanifest rhsso-operator -n openshift-marketplace
```

3. **Check cluster version compatibility**:
```bash
oc get clusterversion
# Ensure operators support your OpenShift version
```

## Gateway Issues

### Issue: Gateway Pods Not Starting

**Symptoms**:
```bash
oc get pods -n mcp-shared -l app=mcp-gateway
# Status: Pending, CrashLoopBackOff, or ImagePullBackOff
```

**Diagnosis**:
```bash
# Check pod status
oc describe pod -n mcp-shared -l app=mcp-gateway

# Check pod logs
oc logs -n mcp-shared -l app=mcp-gateway --tail=100

# Check events
oc get events -n mcp-shared --sort-by='.lastTimestamp' | head -20
```

**Solutions**:

**If ImagePullBackOff**:
```bash
# Check image name
oc get deployment mcp-gateway -n mcp-shared -o jsonpath='{.spec.template.spec.containers[0].image}'

# Verify image exists
podman pull <image-name>

# Check pull secrets
oc get secret -n mcp-shared
```

**If CrashLoopBackOff**:
```bash
# Check pod logs for errors
oc logs -n mcp-shared -l app=mcp-gateway --previous

# Common causes:
# - Missing environment variables
# - Invalid configuration
# - Port already in use
# - Missing dependencies
```

**If Pending**:
```bash
# Check resource availability
oc describe pod -n mcp-shared -l app=mcp-gateway | grep -A 5 Events

# Common causes:
# - Insufficient CPU/memory
# - No nodes match affinity rules
# - PVC not bound
```

### Issue: Gateway Route Not Working

**Symptoms**:
```bash
curl https://mcp-gateway-mcp-shared.apps.your-cluster.com
# Error: Connection refused or 503 Service Unavailable
```

**Diagnosis**:
```bash
# Check route exists
oc get route mcp-gateway -n mcp-shared

# Check route details
oc describe route mcp-gateway -n mcp-shared

# Check service endpoints
oc get endpoints mcp-gateway -n mcp-shared

# Check pod status
oc get pods -n mcp-shared -l app=mcp-gateway
```

**Solutions**:

1. **Verify pods are running**:
```bash
oc get pods -n mcp-shared -l app=mcp-gateway
# All should be Running with 1/1 READY
```

2. **Check service selectors match pod labels**:
```bash
# Service selector
oc get service mcp-gateway -n mcp-shared -o jsonpath='{.spec.selector}'

# Pod labels
oc get pods -n mcp-shared -l app=mcp-gateway --show-labels
```

3. **Test service directly**:
```bash
# Port-forward to service
oc port-forward -n mcp-shared service/mcp-gateway 8080:8080

# Test locally
curl http://localhost:8080/health
```

4. **Check TLS configuration**:
```bash
# Verify TLS termination
oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.tls}'
```

### Issue: Gateway Can't Reach Keycloak

**Symptoms**:
Gateway logs show:
```
ERROR: Failed to validate token: Connection refused to keycloak
```

**Diagnosis**:
```bash
# Check Keycloak is running
oc get pods -n mcp-shared -l app=keycloak

# Test connectivity from gateway
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -v http://keycloak-mcp-shared.svc:8080/health
```

**Solutions**:

1. **Check Keycloak service**:
```bash
oc get service keycloak -n mcp-shared
oc get endpoints keycloak -n mcp-shared
```

2. **Check Keycloak configuration in gateway**:
```bash
oc get configmap mcp-gateway-config -n mcp-shared -o yaml
# Verify keycloak.url is correct
```

3. **Check NetworkPolicy**:
```bash
oc get networkpolicy -n mcp-shared
# Ensure gateway can reach Keycloak
```

## Authentication Issues

### Issue: OAuth Token Invalid

**Symptoms**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <token>" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Response: {"error": {"code": -32001, "message": "Invalid token"}}
```

**Diagnosis**:
```bash
# Check token expiration
# JWT tokens can be decoded at https://jwt.io

# Check Keycloak is accessible
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
curl -k https://$KEYCLOAK_URL/realms/mcp-realm/.well-known/openid-configuration
```

**Solutions**:

1. **Get new token**:
```bash
./scripts/get-mcp-credentials.sh
```

2. **Check token lifetime in Keycloak**:
   - Login to Keycloak Admin Console
   - Go to Realm Settings → Tokens
   - Check "Access Token Lifespan" (default: 5 minutes)

3. **Use API key instead** (recommended for automation):
```bash
./scripts/create-api-key.sh your-username mcp-log-analyst never
```

### Issue: API Key Not Working

**Symptoms**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <api-key>" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Response: {"error": {"code": -32001, "message": "Invalid API key"}}
```

**Diagnosis**:
```bash
# Check API key secret exists
oc get secrets -n mcp-shared -l app=mcp-api-key

# Check specific key
oc get secret mcp-api-key-<username>-<timestamp> -n mcp-shared
```

**Solutions**:

1. **Verify API key is correct**:
```bash
# List all API keys
./scripts/list-api-keys.sh

# Create new API key
./scripts/create-api-key.sh username mcp-log-analyst never
```

2. **Check API key not expired**:
```bash
oc get secret mcp-api-key-<username>-<timestamp> -n mcp-shared \
  -o jsonpath='{.data.expires-at}' | base64 -d
```

3. **Test API key validation**:
```bash
./scripts/test-api-keys.sh
```

### Issue: Demo Token Disabled

**Symptoms**:
Demo token `demo-token-12345` not working.

**Solution**:

Demo token should be disabled in production. Use OAuth tokens or API keys instead:

```bash
# For development/testing
./scripts/get-mcp-credentials.sh

# For production
./scripts/create-api-key.sh username role never
```

## Authorization (RBAC) Issues

### Issue: User Can't See Any Tools

**Symptoms**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <token>" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Response: {"result": {"tools": []}}
```

**Diagnosis**:
Check user roles in Keycloak:

1. Login to Keycloak Admin Console
2. Go to Users → Find user
3. Click "Role Mappings" tab
4. Check assigned roles

**Solutions**:

1. **Assign required roles**:
   - In Keycloak, assign appropriate roles (e.g., `mcp-log-analyst`)

2. **Verify role mapping in gateway**:
```bash
# Check toolsets configuration
oc get configmap mcp-gateway-toolsets -n mcp-shared -o yaml
```

3. **Check user identity in token**:
```bash
# Decode JWT token to see roles
# Use https://jwt.io or:
echo "<token>" | cut -d. -f2 | base64 -d | jq
```

### Issue: User Sees Wrong Tools

**Symptoms**:
User sees tools they shouldn't have access to, or doesn't see tools they should.

**Diagnosis**:
```bash
# Check gateway RBAC configuration
oc get configmap mcp-gateway-toolsets -n mcp-shared -o yaml

# Check tool set required roles
```

**Solutions**:

1. **Review role assignments**:
   - Verify user has correct roles in Keycloak
   - Verify tool sets require correct roles

2. **Update gateway configuration**:
Edit `charts/hub/mcp-gateway/values.yaml`:
```yaml
toolSets:
  log-analysis:
    requiredRole: "mcp-log-analyst"  # Verify this matches Keycloak role
```

3. **Restart gateway pods**:
```bash
oc rollout restart deployment mcp-gateway -n mcp-shared
```

## Sandbox Issues

### Issue: Sandbox Pods Not Starting

**Symptoms**:
```bash
oc get pods -n mcp-log-analysis
# Status: Pending or CrashLoopBackOff
```

**Diagnosis**:
```bash
# Check pod status
oc describe pod -n mcp-log-analysis -l app=mcp-log-analysis-sandbox

# Check pod logs
oc logs -n mcp-log-analysis -l app=mcp-log-analysis-sandbox
```

**Solutions**:

Similar to gateway pod issues:
- Check image availability
- Check resource limits
- Check security contexts
- Check volume mounts

### Issue: Gateway Can't Reach Sandbox

**Symptoms**:
Gateway logs show:
```
ERROR: Failed to call tool: Connection refused to sandbox
```

**Diagnosis**:
```bash
# Test connectivity from gateway
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -v http://mcp-log-analysis-sandbox.mcp-shared.svc:8080/health

# Check sandbox service
oc get service mcp-log-analysis-sandbox -n mcp-shared

# Check sandbox endpoints
oc get endpoints mcp-log-analysis-sandbox -n mcp-shared

# Check NetworkPolicy
oc get networkpolicy -n mcp-log-analysis
```

**Solutions**:

1. **Verify sandbox is running**:
```bash
oc get pods -n mcp-log-analysis
```

2. **Check service configuration**:
```bash
# Service should be in mcp-shared namespace for gateway to access
oc get service -n mcp-shared | grep sandbox
```

3. **Check NetworkPolicy allows traffic**:
```yaml
# NetworkPolicy should allow ingress from gateway
ingress:
  - from:
      - podSelector:
          matchLabels:
            app: mcp-gateway
```

4. **Test directly**:
```bash
# Port-forward to sandbox
oc port-forward -n mcp-log-analysis deployment/mcp-log-analysis-sandbox 8080:8080

# Test locally
curl http://localhost:8080/health
```

### Issue: Tool Execution Fails

**Symptoms**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <token>" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"log_store","arguments":{}},"id":1}'

# Response: {"error": {"code": -32000, "message": "Tool execution failed"}}
```

**Diagnosis**:
```bash
# Check sandbox logs
oc logs -n mcp-log-analysis -l app=mcp-log-analysis-sandbox --tail=100

# Check tool code exists
oc exec -n mcp-log-analysis deployment/mcp-log-analysis-sandbox -- \
  ls -la /home/runner/tools
```

**Solutions**:

1. **Check tool is mounted**:
```bash
# Tools should be in ConfigMap
oc get configmap -n mcp-log-analysis tools-config

# ConfigMap should be mounted in deployment
oc get deployment mcp-log-analysis-sandbox -n mcp-log-analysis -o yaml | grep -A 10 volumeMounts
```

2. **Check tool syntax**:
```bash
# Validate Python syntax
python3 -m py_compile tools/log-analysis/log_store.py
```

3. **Check tool dependencies**:
```bash
# If tool requires packages, ensure they're installed in sandbox image
oc exec -n mcp-log-analysis deployment/mcp-log-analysis-sandbox -- \
  pip list
```

## Cursor IDE Integration Issues

### Issue: MCP Server Not Appearing in Cursor

**Symptoms**:
Cursor IDE doesn't show the MCP server or tools.

**Diagnosis**:
1. Check `.cursor/mcp.json` syntax
2. Check Cursor logs

**Solutions**:

1. **Verify `.cursor/mcp.json` format**:
```json
{
  "mcpServers": {
    "secure-mcp-gateway": {
      "url": "https://mcp-gateway-mcp-shared.apps.your-cluster.com",
      "transport": {
        "type": "http",
        "headers": {
          "Authorization": "Bearer your-token-here"
        }
      }
    }
  }
}
```

2. **Restart Cursor**:
```
Cmd/Ctrl + Shift + P → "Reload Window"
```

3. **Check Cursor logs**:
```
Cmd/Ctrl + Shift + P → "Developer: Show Logs"
```

4. **Test endpoint manually**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

### Issue: Cursor Can't Connect to Gateway

**Symptoms**:
Cursor shows connection error.

**Diagnosis**:
```bash
# Test gateway from your machine
curl -v https://your-gateway-url/

# Check TLS certificate
openssl s_client -connect your-gateway-url:443
```

**Solutions**:

1. **Check VPN/firewall**:
   - Ensure you can reach OpenShift cluster
   - Check corporate firewall rules

2. **Check gateway route**:
```bash
oc get route mcp-gateway -n mcp-shared
```

3. **Test with curl first**:
```bash
curl -X POST https://your-gateway-url/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

## Logging Issues

### Issue: No Logs in OpenShift Logging

**Symptoms**:
OpenShift Console → Logging shows no results.

**Diagnosis**:
```bash
# Check ClusterLogging instance
oc get clusterlogging -n openshift-logging

# Check ClusterLogForwarder
oc get clusterlogforwarder -n openshift-logging

# Check Loki pods
oc get pods -n openshift-logging -l app.kubernetes.io/name=loki
```

**Solutions**:

1. **Check logging operators**:
```bash
oc get subscription -n openshift-logging
```

2. **Check log collection**:
```bash
oc get pods -n openshift-logging -l component=collector
```

3. **Manually check gateway logs**:
```bash
oc logs -n mcp-shared -l app=mcp-gateway | grep mcp_request
```

### Issue: Audit Logs Missing User Identity

**Symptoms**:
Logs show `user: "unknown"` instead of actual username.

**Diagnosis**:
Check token validation is working:

```bash
# Gateway logs should show token validation
oc logs -n mcp-shared -l app=mcp-gateway | grep "token validation"
```

**Solutions**:

1. **Check authentication is enabled**:
   - Gateway should validate tokens with Keycloak
   - User identity should be extracted from token

2. **Check token format**:
   - OAuth tokens should have `preferred_username` claim
   - API keys should have username in Secret

3. **Update gateway code** to log user identity correctly

## Performance Issues

### Issue: High Latency

**Symptoms**:
Requests take > 5 seconds to complete.

**Diagnosis**:
```bash
# Check pod resource usage
oc adm top pods -n mcp-shared

# Check gateway logs for slow requests
oc logs -n mcp-shared -l app=mcp-gateway | grep duration_ms
```

**Solutions**:

1. **Increase resources**:
```yaml
gateway:
  resources:
    requests:
      cpu: "500m"
      memory: "512Mi"
    limits:
      cpu: "2000m"
      memory: "2Gi"
```

2. **Scale horizontally**:
```yaml
gateway:
  replicas: 5
```

3. **Optimize tool code**:
   - Reduce data processing
   - Add caching
   - Limit result sizes

### Issue: Out of Memory

**Symptoms**:
Pods show OOMKilled status.

**Diagnosis**:
```bash
# Check pod events
oc describe pod -n mcp-shared -l app=mcp-gateway | grep -A 5 OOMKilled

# Check memory usage
oc adm top pods -n mcp-shared
```

**Solutions**:

1. **Increase memory limits**:
```yaml
resources:
  limits:
    memory: "2Gi"  # Increase from 512Mi
```

2. **Optimize code**:
   - Reduce memory usage in tools
   - Process data in chunks
   - Clear large variables after use

## Getting Help

### Collect Diagnostic Information

```bash
# Create diagnostic bundle
mkdir diagnostics
cd diagnostics

# Pod status
oc get pods -A > pods.txt

# Pod logs
oc logs -n mcp-shared -l app=mcp-gateway --tail=500 > gateway-logs.txt
oc logs -n mcp-log-analysis -l app=mcp-log-analysis-sandbox --tail=500 > sandbox-logs.txt

# Events
oc get events -n mcp-shared --sort-by='.lastTimestamp' > events.txt

# Configurations
oc get configmap -n mcp-shared -o yaml > configmaps.yaml
oc get service -n mcp-shared -o yaml > services.yaml
oc get route -n mcp-shared -o yaml > routes.yaml

# Create tarball
cd ..
tar -czf diagnostics.tar.gz diagnostics/
```

### Contact Support

1. **GitHub Issues**: https://github.com/gaurav-nelson/secure-mcp-code-gateway/issues
2. **Community Forum**: https://groups.google.com/g/validatedpatterns
3. **Documentation**: https://validatedpatterns.io/patterns/secure-mcp-code-gateway/

When reporting issues, include:
- OpenShift version
- Pattern version
- Diagnostic bundle
- Steps to reproduce
- Expected vs actual behavior

## Common Error Messages

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Authentication required` | No token provided | Add `Authorization: Bearer <token>` header |
| `Invalid token` | Token expired or invalid | Get new token |
| `Insufficient permissions` | User lacks required role | Assign role in Keycloak |
| `Tool not found` | Tool not in user's allowed list | Check RBAC configuration |
| `Sandbox unreachable` | NetworkPolicy or service issue | Check connectivity |
| `ImagePullBackOff` | Image not found | Check image name and registry access |
| `CrashLoopBackOff` | Container failing to start | Check pod logs |
| `Pending` | Resource constraints | Check cluster resources |

## Next Steps

- [Configuration Guide](CONFIGURATION.md) - Fine-tune your deployment
- [Security & RBAC](SECURITY-AND-RBAC.md) - Security troubleshooting
- [Architecture Guide](ARCHITECTURE.md) - Understand system design

