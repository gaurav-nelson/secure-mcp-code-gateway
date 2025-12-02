# Configuration Guide

This guide explains how to customize the Secure MCP Code Gateway Pattern through values files and configuration options.

## Configuration Files Overview

The pattern uses a hierarchical configuration system with multiple values files:

```
secure-mcp-code-gateway/
├── values-global.yaml          # Global pattern settings
├── values-hub.yaml             # Hub cluster applications
├── values-secret.yaml.template # Secrets template
├── charts/hub/
│   ├── mcp-gateway/
│   │   └── values.yaml         # Gateway configuration
│   ├── mcp-log-analysis-sandbox/
│   │   └── values.yaml         # Sandbox configuration
│   ├── keycloak-sso/
│   │   └── values.yaml         # Keycloak configuration
│   └── cluster-logging-instance/
│       └── values.yaml         # Logging configuration
└── overrides/
    ├── values-AWS.yaml         # AWS-specific overrides
    └── values-IBMCloud.yaml    # IBM Cloud-specific overrides
```

## Global Configuration

File: `values-global.yaml`

Controls pattern-wide settings:

```yaml
global:
  pattern: secure-mcp-code-gateway

  # Secret management
  secretLoader:
    disabled: true  # Set to false to use external secrets

  # ArgoCD settings
  options:
    installPlanApproval: Automatic  # or Manual
    syncPolicy: Automatic            # or Manual
    useCSV: false

main:
  clusterGroupName: hub

  # Multi-source support for Helm charts
  multiSourceConfig:
    enabled: true
    clusterGroupChartVersion: 0.9.*
```

### Key Options

| Option | Values | Description |
|--------|--------|-------------|
| `installPlanApproval` | `Automatic`, `Manual` | Operator upgrade approval |
| `syncPolicy` | `Automatic`, `Manual` | ArgoCD sync behavior |
| `secretLoader.disabled` | `true`, `false` | Use internal or external secrets |

## Hub Cluster Configuration

File: `values-hub.yaml`

Defines which applications to deploy:

```yaml
clusterGroup:
  name: hub
  isHubCluster: true

  # Namespaces to create
  namespaces:
    - secure-mcp-code-gateway
    - open-cluster-management
    - vault
    - golang-external-secrets
    - mcp-shared
    - openshift-logging

  # Operator subscriptions
  subscriptions:
    acm:
      name: advanced-cluster-management
      namespace: open-cluster-management
      channel: release-2.14

    logging:
      name: cluster-logging
      namespace: openshift-logging
      channel: stable-5.8
      source: redhat-operators

    rhsso-operator:
      name: rhsso-operator
      namespace: mcp-shared
      channel: stable
      source: redhat-operators

  # Applications (ArgoCD)
  applications:
    keycloak-sso:
      name: keycloak-sso
      namespace: openshift-gitops
      path: charts/hub/keycloak-sso
      argoProject: mcp-shared

    mcp-gateway:
      name: mcp-gateway
      namespace: openshift-gitops
      path: charts/hub/mcp-gateway
      argoProject: mcp-shared

    mcp-log-analysis-sandbox:
      name: mcp-log-analysis-sandbox
      namespace: openshift-gitops
      path: charts/hub/mcp-log-analysis-sandbox
      argoProject: mcp-shared

    cluster-logging-instance:
      name: cluster-logging-instance
      namespace: openshift-gitops
      path: charts/hub/cluster-logging-instance
      argoProject: hub
```

### Adding/Removing Applications

To disable an application, remove it from the `applications` section:

```yaml
applications:
  # keycloak-sso:  # Commented out = not deployed
  #   name: keycloak-sso
  #   ...

  mcp-gateway:
    name: mcp-gateway
    ...
```

To add a new application:

```yaml
applications:
  my-new-sandbox:
    name: my-new-sandbox
    namespace: openshift-gitops
    path: charts/hub/my-new-sandbox
    argoProject: mcp-shared
```

## Gateway Configuration

File: `charts/hub/mcp-gateway/values.yaml`

### Basic Settings

```yaml
gateway:
  name: mcp-gateway
  namespace: mcp-shared
  replicas: 2

  image:
    repository: registry.access.redhat.com/ubi9/python-311
    tag: latest
    pullPolicy: Always
```

### Service and Route

```yaml
gateway:
  service:
    port: 8080
    targetPort: 8080
    type: ClusterIP

  route:
    enabled: true
    host: ""  # Auto-generated from cluster domain
    tls:
      termination: edge
      insecureEdgeTerminationPolicy: Redirect
```

To set a custom hostname:

```yaml
gateway:
  route:
    host: "mcp.example.com"
```

### Keycloak Integration

```yaml
gateway:
  keycloak:
    url: "https://mcp-keycloak-mcp-shared.apps.your-cluster.com"
    realm: "mcp-realm"
    clientId: "mcp-gateway-client"
    # Client secret comes from vault via External Secrets
```

### Tool Sets Configuration

Define which tool sets are available:

```yaml
gateway:
  toolSets:
    # Example 1: Log Analysis (Enabled)
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

    # Example 2: Custom Tool Set (Disabled)
    my-service:
      enabled: false
      description: "My custom service tools"
      sandboxUrl: "http://mcp-my-service-sandbox.mcp-shared.svc.cluster.local:8080"
      requiredRole: "mcp-my-service-user"
      tools:
        - name: "my_tool"
          description: "Does something useful"
```

#### Tool Set Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `enabled` | Yes | Enable or disable this tool set |
| `description` | Yes | Human-readable description |
| `sandboxUrl` | Yes | Full URL to sandbox service |
| `requiredRole` | Yes | Keycloak role required for access |
| `tools` | Yes | List of tools in this set |
| `tools[].name` | Yes | Tool function name |
| `tools[].description` | Yes | Tool description for AI |

### Resource Limits

```yaml
gateway:
  resources:
    requests:
      memory: "256Mi"
      cpu: "200m"
    limits:
      memory: "512Mi"
      cpu: "500m"
```

For high-traffic deployments:

```yaml
gateway:
  replicas: 5
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
```

### Security Context

```yaml
gateway:
  securityContext:
    runAsNonRoot: true
    allowPrivilegeEscalation: false
    capabilities:
      drop:
        - ALL
    seccompProfile:
      type: RuntimeDefault
```

**Do not modify unless you know what you're doing!**

### Health Probes

```yaml
gateway:
  livenessProbe:
    httpGet:
      path: /health
      port: 8080
    initialDelaySeconds: 30
    periodSeconds: 30
    timeoutSeconds: 5
    failureThreshold: 3

  readinessProbe:
    httpGet:
      path: /ready
      port: 8080
    initialDelaySeconds: 10
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 3
```

### Environment Variables

```yaml
gateway:
  env:
    - name: LOG_LEVEL
      value: "info"  # Options: debug, info, warn, error
    - name: GATEWAY_MODE
      value: "multi-tenant"
```

## Sandbox Configuration

File: `charts/hub/mcp-log-analysis-sandbox/values.yaml`

### Basic Settings

```yaml
sandbox:
  name: mcp-log-analysis-sandbox
  namespace: mcp-log-analysis
  replicas: 1

  image:
    repository: registry.access.redhat.com/ubi9/python-311
    tag: latest
    pullPolicy: Always
```

### Tool Configuration

```yaml
sandbox:
  tools:
    path: /home/runner/tools
    sourcePath: tools/log-analysis  # Path in Git repo
```

Tools are automatically mounted from the Git repository path.

### Resource Limits

```yaml
sandbox:
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"
```

Adjust based on tool requirements:

```yaml
sandbox:
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
```

### Security Context

```yaml
sandbox:
  securityContext:
    allowPrivilegeEscalation: false
    runAsNonRoot: true
    capabilities:
      drop:
        - ALL
    seccompProfile:
      type: RuntimeDefault
    readOnlyRootFilesystem: true
```

**Important**: `readOnlyRootFilesystem: true` prevents unauthorized writes.

### Network Policy

```yaml
sandbox:
  networkPolicy:
    enabled: true
    allowFromGateway: true
    denyAll: true
```

This configuration:
- Allows ingress from gateway only
- Denies all egress (no external network access)

To allow specific egress (e.g., to a database):

```yaml
sandbox:
  networkPolicy:
    enabled: true
    allowFromGateway: true
    denyAll: false
    allowEgressTo:
      - namespaceSelector:
          matchLabels:
            name: databases
        podSelector:
          matchLabels:
            app: postgresql
```

## Keycloak Configuration

File: `charts/hub/keycloak-sso/values.yaml`

### Basic Settings

```yaml
keycloak:
  name: mcp-keycloak
  namespace: mcp-shared
  instances: 1

  externalAccess:
    enabled: true
```

### Realm Configuration

```yaml
realm:
  name: mcp-realm
  displayName: "MCP Gateway Realm"
  enabled: true

  # Roles
  roles:
    - name: mcp-admin
      description: "Full access to all MCP tools"
    - name: mcp-log-analyst
      description: "Access to log analysis tools"
    - name: mcp-viewer
      description: "Read-only access"
```

### Client Configuration

```yaml
client:
  name: mcp-gateway-client
  clientId: mcp-gateway-client
  enabled: true
  protocol: openid-connect
  publicClient: false
  directAccessGrantsEnabled: true
  serviceAccountsEnabled: true
  authorizationServicesEnabled: false
```

## Logging Configuration

File: `charts/hub/cluster-logging-instance/values.yaml`

### Log Storage

```yaml
logging:
  storage:
    type: lokistack
    size: 100Gi
```

### Log Collection

```yaml
logging:
  collection:
    logs:
      type: fluentd
      fluentd:
        resources:
          limits:
            memory: 1Gi
          requests:
            memory: 512Mi
```

### Log Forwarding

```yaml
logging:
  forwarding:
    outputs:
      - name: loki
        type: lokistack
        lokistack:
          target:
            name: logging-loki
            namespace: openshift-logging

    pipelines:
      - name: all-logs
        inputRefs:
          - application
          - infrastructure
          - audit
        outputRefs:
          - loki
```

## Secrets Configuration

File: `~/values-secret.yaml` (do not commit to Git!)

### Basic Secrets

```yaml
version: "2.0"

secrets:
  - name: mcp-gateway-client
    vaultPrefixes:
      - global
    fields:
      - name: client-secret
        onMissingValue: generate
        vaultPolicy: validatedPatternDefaultPolicy
```

### Custom Secrets

Add your own secrets:

```yaml
secrets:
  - name: mcp-gateway-client
    vaultPrefixes:
      - global
    fields:
      - name: client-secret
        onMissingValue: generate
        vaultPolicy: validatedPatternDefaultPolicy

  # Custom database credentials
  - name: database-credentials
    vaultPrefixes:
      - global
    fields:
      - name: username
        value: "dbuser"
        vaultPolicy: validatedPatternDefaultPolicy
      - name: password
        onMissingValue: generate
        vaultPolicy: validatedPatternDefaultPolicy
```

## Platform-Specific Overrides

### AWS

File: `overrides/values-AWS.yaml`

```yaml
clusterGroup:
  platform: aws

gateway:
  resources:
    requests:
      memory: "256Mi"
      cpu: "200m"
```

### IBM Cloud

File: `overrides/values-IBMCloud.yaml`

```yaml
clusterGroup:
  platform: ibmcloud

gateway:
  resources:
    requests:
      memory: "256Mi"
      cpu: "200m"
```

## Environment-Specific Configuration

### Development Environment

Create `values-dev.yaml`:

```yaml
gateway:
  replicas: 1
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "200m"

sandbox:
  replicas: 1

logging:
  storage:
    size: 10Gi
```

### Production Environment

Create `values-prod.yaml`:

```yaml
gateway:
  replicas: 5
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"

sandbox:
  replicas: 3

logging:
  storage:
    size: 500Gi
```

Apply environment-specific configuration:

```bash
# Development
./pattern.sh make install -f values-dev.yaml

# Production
./pattern.sh make install -f values-prod.yaml
```

## Configuration Best Practices

### 1. Use Git for Configuration

- Store all configuration in Git
- Use branches for environments (dev, staging, prod)
- Review configuration changes via pull requests
- Never commit secrets to Git

### 2. Resource Planning

- Start with default resource limits
- Monitor actual usage
- Scale based on metrics
- Set appropriate limits to prevent resource starvation

### 3. Security

- Keep security contexts restrictive
- Use NetworkPolicies to limit traffic
- Rotate secrets regularly
- Enable audit logging

### 4. High Availability

- Deploy multiple gateway replicas (minimum 2)
- Use pod anti-affinity for spread across nodes
- Configure health probes correctly
- Test failover scenarios

### 5. Monitoring

- Enable structured logging
- Set up alerts for errors
- Monitor resource utilization
- Track request rates and latencies

## Validation

After making configuration changes, validate:

```bash
# Check values syntax
helm template charts/hub/mcp-gateway/

# Dry-run installation
./pattern.sh make install --dry-run

# Verify deployed configuration
oc get configmap -n mcp-shared mcp-gateway-config -o yaml
```

## Common Configuration Tasks

### Change Gateway Replicas

Edit `charts/hub/mcp-gateway/values.yaml`:

```yaml
gateway:
  replicas: 5  # Changed from 2
```

Commit and push - ArgoCD will sync automatically.

### Add a New Tool Set

1. Edit `charts/hub/mcp-gateway/values.yaml`
2. Add tool set definition
3. Deploy corresponding sandbox
4. Commit and push

See [Extending Guide](EXTENDING-THE-PATTERN.md) for details.

### Change Keycloak Realm

Edit `charts/hub/keycloak-sso/values.yaml`:

```yaml
realm:
  name: my-custom-realm  # Changed from mcp-realm
```

Update gateway configuration to match:

```yaml
gateway:
  keycloak:
    realm: "my-custom-realm"
```

### Enable External Logging

To send logs to external system:

Edit `charts/hub/cluster-logging-instance/values.yaml`:

```yaml
logging:
  forwarding:
    outputs:
      - name: external-loki
        type: loki
        url: "https://loki.example.com:3100"
```

## Next Steps

- [Security & RBAC](SECURITY-AND-RBAC.md) - Configure authentication and authorization
- [Extending the Pattern](EXTENDING-THE-PATTERN.md) - Add new tool sets
- [Troubleshooting](TROUBLESHOOTING.md) - Solve common issues

