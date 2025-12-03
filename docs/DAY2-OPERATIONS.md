# Day 2 Operations Guide

This guide covers ongoing operational tasks for managing the Secure MCP Code Gateway Pattern after initial deployment. Day 2 operations include monitoring, scaling, maintenance, user management, and incident response.

## Table of Contents

- [Operations Overview](#operations-overview)
- [Daily Operations](#daily-operations)
- [Monitoring & Observability](#monitoring--observability)
- [Health Checks & Alerting](#health-checks--alerting)
- [User & Access Management](#user--access-management)
- [API Key Lifecycle Management](#api-key-lifecycle-management)
- [Secrets Rotation](#secrets-rotation)
- [Scaling & Performance Tuning](#scaling--performance-tuning)
- [Log Management & Retention](#log-management--retention)
- [Backup & Recovery](#backup--recovery)
- [Upgrading the Pattern](#upgrading-the-pattern)
- [Capacity Planning](#capacity-planning)
- [Incident Response](#incident-response)
- [Routine Maintenance Tasks](#routine-maintenance-tasks)
- [Disaster Recovery](#disaster-recovery)
- [Operational Runbooks](#operational-runbooks)

---

## Operations Overview

### Key Components to Monitor

| Component | Namespace | Purpose | Critical Level |
|-----------|-----------|---------|----------------|
| MCP Gateway | `mcp-shared` | Request routing, authentication | **High** |
| Sandbox(es) | `mcp-shared` | Tool execution | **High** |
| Keycloak | `mcp-shared` | Authentication/authorization | **High** |
| OpenShift Logging | `openshift-logging` | Audit logs | **Medium** |
| ArgoCD | `openshift-gitops` | GitOps deployment | **Medium** |
| Vault | `vault` | Secrets management | **Medium** |

### Operational Contacts

```yaml
# Define in your operations documentation
contacts:
  primary_oncall: "@platform-team"
  security_team: "@security"
  escalation: "@engineering-leads"
```

---

## Daily Operations

### Morning Health Check

Run this daily to verify system health:

```bash
#!/bin/bash
# daily-health-check.sh

echo "=== MCP Gateway Daily Health Check ==="
echo "Date: $(date)"
echo ""

# 1. Check all pods are running
echo "📦 Pod Status:"
oc get pods -n mcp-shared -o wide | grep -E "NAME|mcp-|keycloak"
echo ""

# 2. Check ArgoCD sync status
echo "🔄 ArgoCD Applications:"
oc get applications -n openshift-gitops | grep -E "NAME|mcp-|keycloak"
echo ""

# 3. Check routes
echo "🌐 Routes:"
oc get routes -n mcp-shared
echo ""

# 4. Quick gateway health test
GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$GATEWAY_URL" ]; then
    echo "🏥 Gateway Health:"
    curl -sk "https://$GATEWAY_URL/health" 2>/dev/null || echo "Health endpoint not responding"
fi
echo ""

# 5. Check recent errors in logs (last hour)
echo "⚠️  Recent Errors (last hour):"
oc logs -n mcp-shared -l app=mcp-gateway --since=1h 2>/dev/null | grep -i error | tail -5 || echo "No errors found"
echo ""

# 6. Resource usage
echo "📊 Resource Usage:"
oc adm top pods -n mcp-shared 2>/dev/null || echo "Metrics not available"
echo ""

echo "=== Health Check Complete ==="
```

Save and run daily:

```bash
chmod +x scripts/daily-health-check.sh
./scripts/daily-health-check.sh
```

### Key Metrics to Monitor

| Metric | Normal Range | Warning | Critical |
|--------|-------------|---------|----------|
| Gateway response time | < 500ms | > 1s | > 5s |
| Request success rate | > 99% | < 99% | < 95% |
| Pod restarts (24h) | 0 | 1-2 | > 3 |
| Memory usage | < 70% | > 80% | > 90% |
| CPU usage | < 60% | > 75% | > 90% |
| API key expirations (7d) | 0 | 1-5 | > 10 |

---

## Monitoring & Observability

### OpenShift Monitoring Dashboard

#### Create Custom Dashboard

Create a ConfigMap for Grafana dashboard:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-gateway-dashboard
  namespace: openshift-config-managed
  labels:
    grafana_dashboard: "1"
data:
  mcp-gateway.json: |
    {
      "title": "MCP Gateway",
      "panels": [
        {
          "title": "Request Rate",
          "type": "graph",
          "targets": [
            {
              "expr": "sum(rate(http_requests_total{app='mcp-gateway'}[5m]))"
            }
          ]
        },
        {
          "title": "Response Time P99",
          "type": "graph",
          "targets": [
            {
              "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app='mcp-gateway'}[5m])) by (le))"
            }
          ]
        },
        {
          "title": "Error Rate",
          "type": "graph",
          "targets": [
            {
              "expr": "sum(rate(http_requests_total{app='mcp-gateway',status=~'5..'}[5m]))"
            }
          ]
        }
      ]
    }
```

### Key Queries for Monitoring

#### Request Volume by Tool

```promql
sum(rate(mcp_tool_calls_total[5m])) by (tool_name)
```

#### Authentication Failures

```promql
sum(rate(mcp_auth_failures_total[5m])) by (reason)
```

#### Sandbox Response Time

```promql
histogram_quantile(0.95, sum(rate(mcp_sandbox_duration_seconds_bucket[5m])) by (le, sandbox))
```

#### Active Users (Last Hour)

```promql
count(count by (user) (mcp_requests_total{user!=""} offset 1h))
```

### Logging Queries (Loki/OpenShift Logging)

#### All MCP Requests

```logql
{app="mcp-gateway"} | json | type="mcp_request"
```

#### Failed Authentication Attempts

```logql
{app="mcp-gateway"} | json | type="mcp_request" | status="error" | error=~".*auth.*"
```

#### Slow Requests (>2 seconds)

```logql
{app="mcp-gateway"} | json | duration_ms > 2000
```

#### Tool Calls by User

```logql
{app="mcp-gateway"} | json | method="tools/call" | user="alice"
```

#### Requests by Tool

```logql
{app="mcp-gateway"} | json | method="tools/call" | line_format "{{.tool}}"
```

---

## Health Checks & Alerting

### PrometheusRule for Alerting

Create alerting rules:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: mcp-gateway-alerts
  namespace: mcp-shared
spec:
  groups:
    - name: mcp-gateway
      rules:
        # Gateway down
        - alert: MCPGatewayDown
          expr: up{app="mcp-gateway"} == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "MCP Gateway is down"
            description: "MCP Gateway pod is not responding for more than 1 minute"

        # High error rate
        - alert: MCPHighErrorRate
          expr: |
            sum(rate(http_requests_total{app="mcp-gateway",status=~"5.."}[5m])) /
            sum(rate(http_requests_total{app="mcp-gateway"}[5m])) > 0.05
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "MCP Gateway high error rate"
            description: "Error rate is above 5% for the last 5 minutes"

        # High latency
        - alert: MCPHighLatency
          expr: |
            histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{app="mcp-gateway"}[5m])) by (le)) > 2
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "MCP Gateway high latency"
            description: "P95 latency is above 2 seconds"

        # Pod restarts
        - alert: MCPPodRestarts
          expr: |
            increase(kube_pod_container_status_restarts_total{namespace="mcp-shared"}[1h]) > 3
          for: 0m
          labels:
            severity: warning
          annotations:
            summary: "MCP pod restarting frequently"
            description: "Pod {{ $labels.pod }} has restarted {{ $value }} times in the last hour"

        # Memory pressure
        - alert: MCPHighMemoryUsage
          expr: |
            container_memory_working_set_bytes{namespace="mcp-shared"} /
            container_spec_memory_limit_bytes{namespace="mcp-shared"} > 0.85
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "MCP container high memory usage"
            description: "Container {{ $labels.container }} is using more than 85% of memory limit"

        # Keycloak down
        - alert: KeycloakDown
          expr: up{app="keycloak"} == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "Keycloak is down"
            description: "Authentication service is unavailable"

        # API key expiring soon
        - alert: APIKeyExpiringSoon
          expr: |
            (mcp_api_key_expiry_timestamp - time()) < 604800
          for: 0m
          labels:
            severity: warning
          annotations:
            summary: "API key expiring soon"
            description: "API key {{ $labels.key_id }} expires in less than 7 days"
```

Apply the alerting rules:

```bash
oc apply -f prometheus-rules.yaml
```

### Health Check Endpoints

#### Gateway Health

```bash
# Liveness probe
curl -k https://$GATEWAY_URL/health

# Readiness probe
curl -k https://$GATEWAY_URL/ready

# Expected response
{"status": "healthy", "version": "1.0.0"}
```

#### Keycloak Health

```bash
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
curl -k "https://$KEYCLOAK_URL/health/ready"
```

#### Sandbox Health

```bash
# From within the cluster
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -s http://mcp-log-analysis-sandbox.mcp-shared.svc:8080/health
```

---

## User & Access Management

### Creating New Users

#### Via Keycloak Admin Console

1. Access Keycloak Admin:
```bash
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
ADMIN_PASSWORD=$(oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)
echo "URL: https://$KEYCLOAK_URL/admin"
echo "Password: $ADMIN_PASSWORD"
```

2. Navigate to Users → Add User
3. Fill in user details
4. Set credentials (Credentials tab)
5. Assign roles (Role Mappings tab)

#### Via Keycloak API (Automation)

```bash
#!/bin/bash
# create-keycloak-user.sh

KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
ADMIN_PASSWORD=$(oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)

# Get admin token
TOKEN=$(curl -sk -X POST "https://$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=$ADMIN_PASSWORD" \
  -d "grant_type=password" | jq -r '.access_token')

# Create user
curl -sk -X POST "https://$KEYCLOAK_URL/admin/realms/mcp-realm/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "enabled": true,
    "credentials": [{
      "type": "password",
      "value": "changeme",
      "temporary": true
    }]
  }'

echo "User created. They must change password on first login."
```

### User Offboarding

When a user leaves or no longer needs access:

```bash
#!/bin/bash
# offboard-user.sh USERNAME

USERNAME=$1

echo "Offboarding user: $USERNAME"

# 1. Revoke all API keys
echo "Revoking API keys..."
for KEY in $(oc get secrets -n mcp-shared -l username=$USERNAME -o name); do
  oc delete $KEY -n mcp-shared
  echo "  Revoked: $KEY"
done

# 2. Disable Keycloak account (via Admin Console or API)
echo "⚠️  Remember to disable user in Keycloak Admin Console"

# 3. Review audit logs for user's activity
echo "Recent activity for $USERNAME:"
oc logs -n mcp-shared -l app=mcp-gateway --since=168h | grep "\"user\":\"$USERNAME\"" | tail -10

echo "Offboarding complete."
```

### Role Management

#### List Available Roles

```bash
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
echo "Available roles in mcp-realm:"
# View via Admin Console → Realm Roles
```

#### Assign Role to User

Via Admin Console:
1. Users → Select User → Role Mappings
2. Move role from "Available Roles" to "Assigned Roles"

#### Bulk Role Assignment

```bash
# Assign mcp-log-analyst role to multiple users
for USER in alice bob charlie; do
  echo "Assigning role to $USER..."
  # Use Keycloak API or Admin Console
done
```

---

## API Key Lifecycle Management

### API Key Inventory

```bash
# List all API keys with details
./scripts/list-api-keys.sh

# Export to CSV for reporting
oc get secrets -n mcp-shared -l app=mcp-api-key -o custom-columns=\
'NAME:.metadata.name,USER:.metadata.labels.username,CREATED:.metadata.creationTimestamp,EXPIRES:.data.expires-at' \
  | while read line; do
    # Decode expires-at field
    echo "$line"
  done
```

### API Key Expiration Report

```bash
#!/bin/bash
# api-key-expiration-report.sh

echo "=== API Key Expiration Report ==="
echo "Date: $(date)"
echo ""

for SECRET in $(oc get secrets -n mcp-shared -l app=mcp-api-key -o name); do
  NAME=$(basename $SECRET)
  USERNAME=$(oc get $SECRET -n mcp-shared -o jsonpath='{.metadata.labels.username}')
  EXPIRES=$(oc get $SECRET -n mcp-shared -o jsonpath='{.data.expires-at}' | base64 -d 2>/dev/null)
  
  if [ "$EXPIRES" == "never" ]; then
    echo "✅ $USERNAME ($NAME): Never expires"
  elif [ -n "$EXPIRES" ]; then
    EXPIRES_EPOCH=$(date -d "$EXPIRES" +%s 2>/dev/null || echo "0")
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRES_EPOCH - NOW_EPOCH) / 86400 ))
    
    if [ $DAYS_LEFT -lt 0 ]; then
      echo "❌ $USERNAME ($NAME): EXPIRED"
    elif [ $DAYS_LEFT -lt 7 ]; then
      echo "⚠️  $USERNAME ($NAME): Expires in $DAYS_LEFT days"
    elif [ $DAYS_LEFT -lt 30 ]; then
      echo "🔶 $USERNAME ($NAME): Expires in $DAYS_LEFT days"
    else
      echo "✅ $USERNAME ($NAME): Expires in $DAYS_LEFT days"
    fi
  fi
done
```

### Rotating API Keys

#### Single Key Rotation

```bash
# Rotate API key (creates new, revokes old)
./scripts/rotate-api-key.sh mcp-api-key-alice-1701523456

# Output includes new key for user to update
```

#### Bulk Key Rotation

```bash
#!/bin/bash
# rotate-all-keys.sh

echo "Rotating all API keys..."

for SECRET in $(oc get secrets -n mcp-shared -l app=mcp-api-key -o name); do
  KEY_ID=$(basename $SECRET)
  echo "Rotating $KEY_ID..."
  ./scripts/rotate-api-key.sh $KEY_ID
done

echo "All keys rotated. Users must update their configurations."
```

### API Key Audit

```bash
# Find API keys not used in last 30 days
# (Requires audit log analysis)

echo "Analyzing API key usage..."

# Get all keys
ALL_KEYS=$(oc get secrets -n mcp-shared -l app=mcp-api-key -o jsonpath='{.items[*].metadata.labels.username}')

# Get users active in last 30 days
ACTIVE_USERS=$(oc logs -n mcp-shared -l app=mcp-gateway --since=720h | \
  grep "mcp_request" | \
  jq -r '.user' | \
  sort -u)

echo "API keys with no activity in 30 days:"
for KEY_USER in $ALL_KEYS; do
  if ! echo "$ACTIVE_USERS" | grep -q "$KEY_USER"; then
    echo "  - $KEY_USER"
  fi
done
```

---

## Secrets Rotation

### Keycloak Client Secret Rotation

```bash
#!/bin/bash
# rotate-keycloak-secret.sh

echo "Rotating Keycloak client secret..."

# 1. Generate new secret
NEW_SECRET=$(openssl rand -base64 32)

# 2. Update in Keycloak (Admin Console or API)
echo "⚠️  Update secret in Keycloak Admin Console:"
echo "   Clients → mcp-gateway-client → Credentials → Regenerate Secret"

# 3. Update Kubernetes secret
oc patch secret mcp-gateway-client-secret -n mcp-shared \
  --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/CLIENT_SECRET\", \"value\": \"$(echo -n $NEW_SECRET | base64)\"}]"

# 4. Restart gateway to pick up new secret
oc rollout restart deployment/mcp-gateway -n mcp-shared

echo "Secret rotated. Verify gateway is working."
```

### Vault Token Rotation

```bash
# Check Vault token status
oc exec -n vault vault-0 -- vault token lookup

# Rotate Vault root token (if needed)
# WARNING: Requires unseal keys
```

### TLS Certificate Renewal

OpenShift routes use cluster certificates by default. For custom certificates:

```bash
# Check certificate expiration
oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.tls.certificate}' | \
  openssl x509 -noout -dates

# Renew certificate before expiration
oc create secret tls mcp-gateway-tls \
  --cert=new-cert.pem \
  --key=new-key.pem \
  -n mcp-shared \
  --dry-run=client -o yaml | oc apply -f -
```

---

## Scaling & Performance Tuning

### Horizontal Scaling

#### Scale Gateway

```bash
# Scale to 5 replicas
oc scale deployment mcp-gateway -n mcp-shared --replicas=5

# Or update values-hub.yaml and let ArgoCD sync:
# gateway:
#   replicas: 5
```

#### Scale Sandbox

```bash
# Scale sandbox for high load
oc scale deployment mcp-log-analysis-sandbox -n mcp-shared --replicas=3
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mcp-gateway-hpa
  namespace: mcp-shared
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mcp-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

Apply:

```bash
oc apply -f hpa.yaml
```

### Vertical Scaling (Resource Limits)

Update resource limits in values:

```yaml
# charts/hub/mcp-gateway/values.yaml
gateway:
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
```

### Performance Tuning

#### Connection Pooling

```yaml
# Gateway environment variables
env:
  - name: MAX_CONNECTIONS
    value: "100"
  - name: CONNECTION_TIMEOUT
    value: "30"
  - name: KEEPALIVE_TIMEOUT
    value: "60"
```

#### Request Timeouts

```yaml
# Sandbox configuration
sandbox:
  timeout:
    execute: 30  # Code execution timeout
    request: 60  # Total request timeout
```

#### Caching (if applicable)

```yaml
# Enable caching for tool schemas
gateway:
  cache:
    enabled: true
    ttl: 300  # 5 minutes
    maxSize: 1000
```

---

## Log Management & Retention

### Log Retention Policy

Configure OpenShift Logging retention:

```yaml
apiVersion: logging.openshift.io/v1
kind: ClusterLogging
metadata:
  name: instance
  namespace: openshift-logging
spec:
  managementState: Managed
  logStore:
    type: lokistack
    lokistack:
      name: logging-loki
    retentionPolicy:
      application:
        maxAge: 30d
      infrastructure:
        maxAge: 14d
      audit:
        maxAge: 90d
```

### Log Export for Compliance

#### Export to S3

```bash
#!/bin/bash
# export-audit-logs.sh

DATE=$(date +%Y-%m-%d)
BUCKET="s3://audit-logs-bucket/mcp-gateway"

# Export last 24 hours of audit logs
oc logs -n mcp-shared -l app=mcp-gateway --since=24h | \
  grep "mcp_request" > /tmp/audit-$DATE.jsonl

# Upload to S3
aws s3 cp /tmp/audit-$DATE.jsonl $BUCKET/$DATE.jsonl

# Cleanup
rm /tmp/audit-$DATE.jsonl

echo "Exported audit logs for $DATE"
```

#### Schedule Daily Export

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: audit-log-export
  namespace: mcp-shared
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: exporter
              image: amazon/aws-cli
              command:
                - /bin/sh
                - -c
                - |
                  # Export script here
          restartPolicy: OnFailure
```

### Log Analysis Queries

#### Daily Request Summary

```bash
# Count requests by user today
oc logs -n mcp-shared -l app=mcp-gateway --since=24h | \
  grep "mcp_request" | \
  jq -r '.user' | \
  sort | uniq -c | sort -rn
```

#### Tool Usage Report

```bash
# Most used tools
oc logs -n mcp-shared -l app=mcp-gateway --since=168h | \
  grep "tools/call" | \
  jq -r '.tool' | \
  sort | uniq -c | sort -rn | head -10
```

#### Error Analysis

```bash
# Error breakdown
oc logs -n mcp-shared -l app=mcp-gateway --since=24h | \
  grep '"status":"error"' | \
  jq -r '.error' | \
  sort | uniq -c | sort -rn
```

---

## Backup & Recovery

### What to Backup

| Component | Backup Method | Frequency | Retention |
|-----------|--------------|-----------|-----------|
| Keycloak DB | PVC snapshot | Daily | 30 days |
| API Keys | Secret export | Daily | 30 days |
| Vault data | Vault snapshot | Daily | 30 days |
| Configuration | Git (already) | Continuous | Indefinite |
| Workspace PVCs | PVC snapshot | Daily | 7 days |

### Backup Scripts

#### Backup API Keys

```bash
#!/bin/bash
# backup-api-keys.sh

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/backup/api-keys"

mkdir -p $BACKUP_DIR

# Export all API key secrets (encrypted)
oc get secrets -n mcp-shared -l app=mcp-api-key -o yaml | \
  gpg --encrypt --recipient backup@company.com > $BACKUP_DIR/api-keys-$DATE.yaml.gpg

echo "Backed up API keys to $BACKUP_DIR/api-keys-$DATE.yaml.gpg"
```

#### Backup Keycloak

```bash
#!/bin/bash
# backup-keycloak.sh

DATE=$(date +%Y-%m-%d)

# Export realm configuration
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
ADMIN_PASSWORD=$(oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)

# Get admin token
TOKEN=$(curl -sk -X POST "https://$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=$ADMIN_PASSWORD" \
  -d "grant_type=password" | jq -r '.access_token')

# Export realm
curl -sk "https://$KEYCLOAK_URL/admin/realms/mcp-realm" \
  -H "Authorization: Bearer $TOKEN" > /backup/keycloak/mcp-realm-$DATE.json

echo "Backed up Keycloak realm to /backup/keycloak/mcp-realm-$DATE.json"
```

### Recovery Procedures

#### Restore API Keys

```bash
#!/bin/bash
# restore-api-keys.sh BACKUP_FILE

BACKUP_FILE=$1

# Decrypt and apply
gpg --decrypt $BACKUP_FILE | oc apply -f -

echo "API keys restored. Verify with: ./scripts/list-api-keys.sh"
```

#### Restore Keycloak Realm

```bash
# Import realm via Admin Console:
# Realm Settings → Action → Partial Import → Upload JSON

# Or via API:
curl -sk -X POST "https://$KEYCLOAK_URL/admin/realms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/backup/keycloak/mcp-realm-$DATE.json
```

---

## Upgrading the Pattern

### Pre-Upgrade Checklist

```bash
#!/bin/bash
# pre-upgrade-check.sh

echo "=== Pre-Upgrade Checklist ==="

# 1. Check current version
echo "Current pattern version:"
cat pattern-metadata.yaml | grep pattern_version

# 2. Check ArgoCD sync status
echo ""
echo "ArgoCD status:"
oc get applications -n openshift-gitops | grep -E "mcp-|keycloak"

# 3. Check for pending changes
echo ""
echo "Git status:"
git status

# 4. Backup current state
echo ""
echo "Creating backup..."
./scripts/backup-api-keys.sh
./scripts/backup-keycloak.sh

# 5. Check cluster health
echo ""
echo "Cluster health:"
oc get nodes
oc get clusterversion

echo ""
echo "Pre-upgrade check complete. Proceed with upgrade if all checks pass."
```

### Upgrade Process

```bash
# 1. Fetch latest changes
git remote add upstream https://github.com/validatedpatterns/secure-mcp-code-gateway.git 2>/dev/null
git fetch upstream

# 2. Review changes
git log HEAD..upstream/main --oneline

# 3. Merge changes
git merge upstream/main

# 4. Resolve conflicts (if any)
# Edit conflicting files
git add .
git commit -m "Merge upstream changes"

# 5. Push to your fork
git push origin main

# 6. ArgoCD will auto-sync, or force sync:
oc patch application mcp-gateway -n openshift-gitops \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# 7. Monitor deployment
watch oc get pods -n mcp-shared
```

### Post-Upgrade Verification

```bash
#!/bin/bash
# post-upgrade-verify.sh

echo "=== Post-Upgrade Verification ==="

# 1. Check all pods running
echo "Pod status:"
oc get pods -n mcp-shared

# 2. Check new version
echo ""
echo "Gateway version:"
curl -sk https://$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}')/health | jq .version

# 3. Run verification tests
echo ""
echo "Running verification tests..."
./scripts/test-mcp-endpoints.sh

# 4. Test authentication
echo ""
echo "Testing authentication..."
./scripts/test-api-keys.sh

echo ""
echo "Post-upgrade verification complete."
```

### Rollback Procedure

```bash
#!/bin/bash
# rollback.sh COMMIT_SHA

COMMIT_SHA=$1

echo "Rolling back to $COMMIT_SHA..."

# 1. Revert to previous commit
git revert --no-commit HEAD..$COMMIT_SHA
git commit -m "Rollback to $COMMIT_SHA"
git push

# 2. Force ArgoCD sync
oc patch application mcp-gateway -n openshift-gitops \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# 3. Monitor
watch oc get pods -n mcp-shared

echo "Rollback initiated. Monitor pods for completion."
```

---

## Capacity Planning

### Current Usage Analysis

```bash
#!/bin/bash
# capacity-report.sh

echo "=== Capacity Report ==="
echo "Date: $(date)"
echo ""

# Resource usage
echo "📊 Resource Usage (current):"
oc adm top pods -n mcp-shared
echo ""

# Request volume (last 24h)
echo "📈 Request Volume (24h):"
TOTAL_REQUESTS=$(oc logs -n mcp-shared -l app=mcp-gateway --since=24h | grep "mcp_request" | wc -l)
echo "  Total requests: $TOTAL_REQUESTS"
echo "  Avg per hour: $((TOTAL_REQUESTS / 24))"
echo ""

# User count
echo "👥 Active Users (24h):"
ACTIVE_USERS=$(oc logs -n mcp-shared -l app=mcp-gateway --since=24h | grep "mcp_request" | jq -r '.user' | sort -u | wc -l)
echo "  Active users: $ACTIVE_USERS"
echo ""

# Storage usage
echo "💾 Storage Usage:"
oc get pvc -n mcp-shared
echo ""

# API key count
echo "🔑 API Keys:"
API_KEY_COUNT=$(oc get secrets -n mcp-shared -l app=mcp-api-key --no-headers | wc -l)
echo "  Total API keys: $API_KEY_COUNT"
```

### Capacity Planning Guidelines

| Metric | Small (<100 users) | Medium (100-1000) | Large (>1000) |
|--------|-------------------|-------------------|---------------|
| Gateway replicas | 2 | 3-5 | 5-10 |
| Gateway CPU | 500m-1 | 1-2 | 2-4 |
| Gateway Memory | 512Mi-1Gi | 1-2Gi | 2-4Gi |
| Sandbox replicas | 1-2 | 2-3 | 3-5 per sandbox |
| Keycloak replicas | 1 | 2-3 | 3-5 |
| Log retention | 30 days | 60 days | 90+ days |

### Growth Projections

```bash
# Analyze growth trend (requires historical data)
# Example: Plot requests per day over time

# If using Prometheus:
# rate(http_requests_total{app="mcp-gateway"}[24h]) over last 30 days
```

---

## Incident Response

### Severity Levels

| Level | Definition | Response Time | Examples |
|-------|------------|---------------|----------|
| **SEV1** | Complete outage | 15 minutes | Gateway down, auth failing |
| **SEV2** | Major degradation | 1 hour | High latency, partial failures |
| **SEV3** | Minor issues | 4 hours | Single user issues, cosmetic |
| **SEV4** | Informational | Next business day | Feature requests, questions |

### Incident Response Playbook

#### SEV1: Gateway Down

```bash
#!/bin/bash
# runbook-gateway-down.sh

echo "=== SEV1: Gateway Down Runbook ==="

# 1. Verify the issue
echo "Step 1: Verify gateway status"
oc get pods -n mcp-shared -l app=mcp-gateway
oc get deployment mcp-gateway -n mcp-shared

# 2. Check recent events
echo ""
echo "Step 2: Check events"
oc get events -n mcp-shared --sort-by='.lastTimestamp' | tail -20

# 3. Check logs
echo ""
echo "Step 3: Check logs"
oc logs -n mcp-shared -l app=mcp-gateway --tail=50

# 4. Attempt restart
echo ""
echo "Step 4: Restart deployment"
oc rollout restart deployment/mcp-gateway -n mcp-shared

# 5. Monitor recovery
echo ""
echo "Step 5: Monitor recovery"
oc rollout status deployment/mcp-gateway -n mcp-shared

# 6. Verify
echo ""
echo "Step 6: Verify health"
GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}')
curl -sk "https://$GATEWAY_URL/health"
```

#### SEV1: Authentication Failure

```bash
#!/bin/bash
# runbook-auth-failure.sh

echo "=== SEV1: Authentication Failure Runbook ==="

# 1. Check Keycloak status
echo "Step 1: Check Keycloak"
oc get pods -n mcp-shared | grep keycloak

# 2. Check Keycloak logs
echo ""
echo "Step 2: Keycloak logs"
oc logs -n mcp-shared -l app=keycloak --tail=30

# 3. Test Keycloak directly
echo ""
echo "Step 3: Test Keycloak endpoint"
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')
curl -sk "https://$KEYCLOAK_URL/realms/mcp-realm/.well-known/openid-configuration" | head -5

# 4. Check gateway → Keycloak connectivity
echo ""
echo "Step 4: Test gateway → Keycloak connectivity"
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -s http://keycloak.mcp-shared.svc:8080/health

# 5. If Keycloak is down, restart
echo ""
echo "Step 5: Restart Keycloak if needed"
# oc rollout restart deployment/keycloak -n mcp-shared

# 6. Verify API keys still work (fallback)
echo ""
echo "Step 6: Test API key auth"
# ./scripts/test-api-keys.sh
```

### Post-Incident Review

After resolving an incident:

1. **Document the incident**:
   - Timeline of events
   - Root cause
   - Resolution steps
   - Impact (users affected, duration)

2. **Identify improvements**:
   - Better monitoring?
   - Faster detection?
   - Automated remediation?

3. **Update runbooks**:
   - Add new scenarios
   - Improve existing procedures

---

## Routine Maintenance Tasks

### Weekly Tasks

| Task | Command | Notes |
|------|---------|-------|
| Health check | `./scripts/daily-health-check.sh` | Review trends |
| API key audit | `./scripts/list-api-keys.sh` | Check for unused keys |
| Log review | Query error logs | Look for patterns |
| Resource review | `oc adm top pods -n mcp-shared` | Check utilization |

### Monthly Tasks

| Task | Description |
|------|-------------|
| API key rotation | Rotate keys older than 90 days |
| User audit | Review user access, remove inactive |
| Capacity review | Check growth trends, plan scaling |
| Security patches | Apply OpenShift updates |
| Backup verification | Test backup restoration |

### Quarterly Tasks

| Task | Description |
|------|-------------|
| Pattern upgrade | Merge upstream changes |
| Full DR test | Test disaster recovery |
| Access review | Comprehensive RBAC audit |
| Performance tuning | Optimize based on usage patterns |
| Documentation update | Update runbooks, procedures |

### Maintenance Window Procedure

```bash
#!/bin/bash
# maintenance-window.sh

echo "=== Maintenance Window Procedure ==="
echo "Start time: $(date)"

# 1. Notify users
echo "Step 1: Send maintenance notification"
# Integration with Slack/email

# 2. Scale down non-critical components
echo "Step 2: Scale down"
oc scale deployment mcp-gateway -n mcp-shared --replicas=1

# 3. Perform maintenance
echo "Step 3: Perform maintenance tasks"
# ... maintenance commands ...

# 4. Scale back up
echo "Step 4: Scale up"
oc scale deployment mcp-gateway -n mcp-shared --replicas=2

# 5. Verify health
echo "Step 5: Verify health"
./scripts/test-mcp-endpoints.sh

# 6. Notify completion
echo "Step 6: Send completion notification"
# Integration with Slack/email

echo "End time: $(date)"
```

---

## Disaster Recovery

### DR Strategy

| Scenario | RTO | RPO | Strategy |
|----------|-----|-----|----------|
| Pod failure | 1 min | 0 | Kubernetes auto-restart |
| Node failure | 5 min | 0 | Pod rescheduling |
| AZ failure | 15 min | 0 | Multi-AZ deployment |
| Region failure | 4 hours | 1 hour | Cross-region DR |
| Data corruption | 1 hour | 24 hours | Backup restoration |

### DR Test Procedure

```bash
#!/bin/bash
# dr-test.sh

echo "=== Disaster Recovery Test ==="
echo "Date: $(date)"
echo ""

# 1. Simulate pod failure
echo "Test 1: Pod failure recovery"
oc delete pod -n mcp-shared -l app=mcp-gateway --wait=false
sleep 30
oc get pods -n mcp-shared -l app=mcp-gateway
echo ""

# 2. Verify auto-recovery
echo "Test 2: Verify gateway recovered"
GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}')
for i in {1..10}; do
  if curl -sk "https://$GATEWAY_URL/health" | grep -q "healthy"; then
    echo "Gateway recovered after $((i * 5)) seconds"
    break
  fi
  sleep 5
done
echo ""

# 3. Test backup restoration (on test environment)
echo "Test 3: Backup restoration"
echo "  ⚠️  Run backup restoration test on non-production environment"
echo ""

# 4. Document results
echo "DR Test Results:"
echo "  Pod recovery: PASS/FAIL"
echo "  Backup restoration: PASS/FAIL"
echo "  Data integrity: PASS/FAIL"
```

---

## Operational Runbooks

### Quick Reference Commands

```bash
# View all MCP resources
oc get all -n mcp-shared

# Gateway logs (follow)
oc logs -f -n mcp-shared -l app=mcp-gateway

# Sandbox logs
oc logs -f -n mcp-shared -l app=mcp-log-analysis-sandbox

# Restart gateway
oc rollout restart deployment/mcp-gateway -n mcp-shared

# Restart sandbox
oc rollout restart deployment/mcp-log-analysis-sandbox -n mcp-shared

# Force ArgoCD sync
oc patch application mcp-gateway -n openshift-gitops \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# Get gateway URL
oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}'

# Get Keycloak admin password
oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d

# Scale gateway
oc scale deployment mcp-gateway -n mcp-shared --replicas=N

# Check resource usage
oc adm top pods -n mcp-shared
```

### Operational Checklist Template

```markdown
## Daily Operations Checklist

- [ ] Morning health check completed
- [ ] No critical alerts
- [ ] All pods running
- [ ] ArgoCD applications synced
- [ ] Error rate within threshold
- [ ] Response time within threshold

## Weekly Operations Checklist

- [ ] API key audit completed
- [ ] User access review
- [ ] Log analysis for anomalies
- [ ] Backup verification
- [ ] Capacity review

## Monthly Operations Checklist

- [ ] Security patches applied
- [ ] Credentials rotated
- [ ] Full backup tested
- [ ] Performance optimization review
- [ ] Documentation updated
```

---

## Next Steps

- [Troubleshooting Guide](TROUBLESHOOTING.md) - Resolve specific issues
- [Security & RBAC](SECURITY-AND-RBAC.md) - Security operations details
- [Verification Guide](VERIFICATION.md) - Test all features
- [Configuration Guide](CONFIGURATION.md) - Adjust settings

