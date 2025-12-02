# Architecture Guide

## Overview

This document describes the technical architecture of the Secure MCP Code Gateway Pattern, including component interactions, data flows, and design decisions.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI Client Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Cursor IDE  │  │ Claude Desktop│ │  Custom MCP  │         │
│  │              │  │               │  │   Clients    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (JSON-RPC 2.0)
                              │ Authorization: Bearer <token>
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Shared Infrastructure                         │
│  ┌────────────────────┐        ┌──────────────────────────┐    │
│  │   Keycloak         │        │   OpenShift Logging      │    │
│  │   (Red Hat SSO)    │        │   (Loki + Grafana)       │    │
│  │                    │        │                          │    │
│  │ - OAuth 2.1        │        │ - Log collection         │    │
│  │ - User management  │        │ - Audit queries          │    │
│  │ - Role management  │        │ - Visualization          │    │
│  └────────────────────┘        └──────────────────────────┘    │
│           │                                   ▲                  │
│           │ Token Validation                  │ Logs             │
└───────────┼───────────────────────────────────┼──────────────────┘
            │                                   │
            ▼                                   │
┌─────────────────────────────────────────────────────────────────┐
│              Multi-Tenant MCP Gateway (2 replicas)               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Request Handler                                          │  │
│  │  1. Validate OAuth/API key token                          │  │
│  │  2. Extract user identity & roles                         │  │
│  │  3. Route to appropriate sandbox                          │  │
│  │  4. Log request with audit data                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  MCP Protocol Handler (JSON-RPC 2.0)                      │  │
│  │  - initialize: Handshake & capability negotiation         │  │
│  │  - tools/list: Return tools based on user roles           │  │
│  │  - tools/call: Execute tool in sandbox                    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
            │                    │                    │
            │                    │                    │
    ┌───────┴────────┐  ┌────────┴────────┐  ┌──────┴──────┐
    ▼                ▼  ▼                 ▼  ▼             ▼
┌──────────┐    ┌──────────┐         ┌──────────┐   ┌──────────┐
│ Sandbox: │    │ Sandbox: │         │ Sandbox: │   │ Sandbox: │
│   Log    │    │   Data   │   ...   │  Custom  │   │  (Add    │
│ Analysis │    │ Science  │         │  Tools   │   │  Yours!) │
├──────────┤    ├──────────┤         ├──────────┤   ├──────────┤
│ Tools:   │    │ Tools:   │         │ Tools:   │   │ Tools:   │
│ - log_   │    │ - data_  │         │ - your_  │   │ - ...    │
│   store  │    │   query  │         │   tool   │   │          │
│ - privacy│    │ - analyze│         │ - ...    │   │          │
└──────────┘    └──────────┘         └──────────┘   └──────────┘
     │               │                    │              │
     └───────────────┴────────────────────┴──────────────┘
                          │
                          └─► Logs sent to OpenShift Logging
```

## Core Components

### 1. Keycloak (Red Hat SSO)

**Purpose**: Centralized authentication and authorization for all MCP servers.

**Namespace**: `mcp-shared`

**Key Features**:
- OAuth 2.1 token service
- User and role management
- Client credentials for gateway
- Token validation endpoint
- Session management

**Configuration**:
```yaml
Realm: mcp-realm
Client: mcp-gateway-client
Roles:
  - mcp-admin (full access)
  - mcp-log-analyst (log tools only)
  - mcp-viewer (read-only)
```

**Deployment**:
- Red Hat SSO Operator
- Custom KeycloakRealm CR
- Custom KeycloakClient CR
- External route for user access

### 2. Multi-Tenant MCP Gateway

**Purpose**: Single gateway that routes requests to multiple sandboxes based on tool names.

**Namespace**: `mcp-shared`

**Replicas**: 2 (high availability)

**Key Features**:
- JSON-RPC 2.0 protocol implementation
- OAuth token validation with Keycloak
- API key authentication (optional)
- Role-based access control (RBAC)
- Dynamic tool discovery
- Request routing to sandboxes
- Comprehensive audit logging

**Endpoints**:
- `POST /` - MCP JSON-RPC endpoint
- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe

**MCP Methods Supported**:
1. `initialize` - Handshake and capability negotiation
2. `tools/list` - Return available tools based on user roles
3. `tools/call` - Execute tool in appropriate sandbox

**Request Flow**:
```
1. Client sends JSON-RPC request with Bearer token
2. Gateway validates token with Keycloak
3. Gateway extracts user identity and roles
4. Gateway filters available tools based on roles
5. For tools/call: Gateway routes to appropriate sandbox
6. Gateway logs request with user identity
7. Gateway returns response to client
```

**Security**:
- TLS termination at OpenShift Route (edge)
- Non-root container execution
- Dropped capabilities
- Resource limits (CPU/memory)
- Read-only root filesystem

### 3. Tool Sandboxes

**Purpose**: Isolated execution environments for tool sets.

**Architecture**: One sandbox per tool set (not per user).

**Key Features**:
- Python-based tool execution
- Tools mounted via ConfigMap from Git
- Strict security context
- Network isolation via NetworkPolicy
- Resource limits
- Audit logging

**Example Sandbox: Log Analysis**

**Namespace**: `mcp-log-analysis`

**Tools Provided**:
- `log_store` - Search and analyze logs efficiently
- `privacy` - Scrub PII from text and logs

**Security Context**:
```yaml
runAsNonRoot: true
allowPrivilegeEscalation: false
capabilities:
  drop: [ALL]
readOnlyRootFilesystem: true
seccompProfile:
  type: RuntimeDefault
```

**Network Policy**:
```yaml
Allow: Ingress from gateway only
Deny: All egress traffic (no external network)
```

**Resource Limits**:
```yaml
Requests: 128Mi memory, 100m CPU
Limits: 512Mi memory, 500m CPU
```

### 4. OpenShift Logging

**Purpose**: Centralized log collection and audit trail.

**Components**:
- **Loki**: Log storage backend
- **ClusterLogForwarder**: Route logs to Loki
- **OpenShift Console**: Query interface
- **Grafana** (optional): Advanced visualization

**Namespace**: `openshift-logging`

**Log Format**:
```json
{
  "type": "mcp_request",
  "timestamp": "2025-12-02T10:30:45Z",
  "user": "alice",
  "method": "tools/call",
  "tool": "log_store",
  "client_ip": "10.134.0.54",
  "status": "success",
  "duration_ms": 125
}
```

**Log Sources**:
- Gateway audit logs
- Sandbox execution logs
- Keycloak authentication logs

## Data Flow

### Tool Discovery Flow (tools/list)

```
┌────────┐     1. POST /           ┌─────────┐
│ Cursor │────────────────────────►│ Gateway │
│  IDE   │  Bearer: oauth-token    │         │
└────────┘                          └─────────┘
                                         │
                                         │ 2. Validate token
                                         ▼
                                    ┌──────────┐
                                    │ Keycloak │
                                    └──────────┘
                                         │
                                         │ 3. Token valid
                                         │    Roles: [mcp-log-analyst]
                                         ▼
                                    ┌─────────┐
                                    │ Gateway │
                                    │ Filter  │
                                    └─────────┘
                                         │
                                         │ 4. Return tools
                                         │    User can access
                                         ▼
┌────────┐     5. JSON-RPC        ┌─────────┐
│ Cursor │◄───────────────────────│ Gateway │
│  IDE   │  {tools: [log_store]}  │         │
└────────┘                         └─────────┘
```

### Tool Execution Flow (tools/call)

```
┌────────┐   1. POST /              ┌─────────┐
│ Cursor │──────────────────────────►│ Gateway │
│  IDE   │  tools/call: log_store    │         │
└────────┘  Bearer: oauth-token      └─────────┘
                                          │
                                          │ 2. Validate & authorize
                                          ▼
                                     ┌──────────┐
                                     │ Keycloak │
                                     └──────────┘
                                          │
                                          │ 3. Authorized
                                          ▼
                                     ┌─────────┐
                                     │ Gateway │
                                     │ Route   │
                                     └─────────┘
                                          │
                                          │ 4. POST /execute
                                          ▼
                                     ┌─────────┐
                                     │ Sandbox │
                                     │   Log   │
                                     │ Analysis│
                                     └─────────┘
                                          │
                                          │ 5. Execute log_store.py
                                          │    with arguments
                                          ▼
                                     ┌─────────┐
                                     │  Tool   │
                                     │ Result  │
                                     └─────────┘
                                          │
                                          │ 6. Return result
                                          ▼
┌────────┐   7. JSON-RPC            ┌─────────┐
│ Cursor │◄─────────────────────────│ Gateway │
│  IDE   │  {result: [...]}         │         │
└────────┘                           └─────────┘
                                          │
                                          │ 8. Log audit entry
                                          ▼
                                     ┌─────────┐
                                     │ Logging │
                                     └─────────┘
```

## Authentication & Authorization

### Authentication Methods

#### 1. OAuth 2.1 Tokens (Production)

**Flow**:
```
User → Keycloak → Gateway
```

**Steps**:
1. User authenticates with Keycloak
2. Keycloak issues OAuth token
3. User includes token in `Authorization: Bearer <token>` header
4. Gateway validates token with Keycloak
5. Gateway extracts user identity and roles

**Token Lifetime**: Configurable (default: 5 minutes)

**Refresh**: Tokens can be refreshed via Keycloak

#### 2. API Keys (Production - Long-lived)

**Flow**:
```
Admin → create-api-key.sh → Secret → Gateway
```

**Steps**:
1. Admin creates API key with `create-api-key.sh`
2. Key stored as Kubernetes Secret
3. User includes key in `Authorization: Bearer <api-key>` header
4. Gateway validates against Secrets
5. Gateway uses username/roles from Secret

**Lifetime**: Never expires (or configurable expiration)

**Management**:
- Create: `./scripts/create-api-key.sh`
- List: `./scripts/list-api-keys.sh`
- Revoke: `./scripts/revoke-api-key.sh`
- Rotate: `./scripts/rotate-api-key.sh`

#### 3. Demo Token (Development Only)

**Value**: `demo-token-12345`

**Roles**: All roles (admin access)

**Security**: Remove in production!

### Authorization (RBAC)

**Role Assignment**:
```yaml
toolSets:
  log-analysis:
    requiredRole: "mcp-log-analyst"
    tools:
      - log_store
      - privacy

  database:
    requiredRole: "mcp-dba"
    tools:
      - postgres_query
```

**Access Control**:
- User must have role to see tools in `tools/list`
- User must have role to call tools in `tools/call`
- Gateway enforces RBAC at runtime
- No tools exposed without proper role

## Network Architecture

### Network Policies

#### Gateway Network Policy
```yaml
Ingress:
  - From OpenShift Route (TLS)
Egress:
  - To Keycloak (token validation)
  - To all sandboxes (tool execution)
  - To DNS (name resolution)
```

#### Sandbox Network Policy
```yaml
Ingress:
  - From gateway only (same namespace)
Egress:
  - To DNS (name resolution)
  - Deny all other (no external network)
```

### Service Mesh (Optional)

For advanced deployments, consider:
- OpenShift Service Mesh (Istio)
- mTLS between gateway and sandboxes
- Traffic encryption
- Advanced routing

## Storage & Configuration

### ConfigMaps

**Tool Configuration**:
```
charts/hub/mcp-gateway/templates/toolsets-configmap.yaml
  → Gateway tool set definitions

charts/hub/mcp-log-analysis-sandbox/templates/tools-configmap.yaml
  → Sandbox tool code from tools/log-analysis/
```

### Secrets

**Keycloak Client Secret**:
```
mcp-shared/keycloak-client-secret
  → OAuth client credentials
```

**API Keys**:
```
mcp-shared/mcp-api-key-<username>-<timestamp>
  → API key data and metadata
```

### Persistent Storage

**Note**: Current implementation is stateless. For persistent data:

- Mount PVC to sandboxes
- Use OpenShift Data Foundation
- Configure backup/restore

## Scaling & High Availability

### Gateway Scaling

**Horizontal**:
```yaml
replicas: 2  # Default
# Can increase for more load
```

**Vertical**:
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "200m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### Sandbox Scaling

**Per Tool Set**:
```yaml
replicas: 1  # Default (stateless execution)
# Increase for high-load scenarios
```

**Resource Limits**: Adjust per workload

### Load Balancing

- OpenShift Router (HAProxy) handles ingress
- Service load balances to gateway pods
- Gateway routes to sandbox service (K8s LB)

## Security Architecture

### Defense in Depth

1. **Edge**: TLS termination at route
2. **Authentication**: OAuth/API key validation
3. **Authorization**: Role-based access control
4. **Network**: NetworkPolicies restrict traffic
5. **Container**: Non-root, dropped capabilities
6. **Audit**: All requests logged

### Threat Model

**Threats Mitigated**:
- Unauthorized access (OAuth/API keys)
- Privilege escalation (RBAC)
- Data exfiltration (NetworkPolicy)
- Container escape (Security context)
- Audit evasion (Comprehensive logging)

**Threats NOT Mitigated**:
- Malicious tools in Git (mitigate with PR reviews)
- Social engineering (mitigate with user training)
- Compromised Keycloak (mitigate with MFA, monitoring)

## Design Decisions

### Why Multi-Tenant Gateway?

**Alternative**: One gateway per tool set

**Chosen**: One gateway for all tool sets

**Rationale**:
- Simpler deployment (1 gateway vs N gateways)
- Shared authentication (single Keycloak client)
- Easier RBAC management
- Lower resource consumption
- Centralized audit logs

### Why Sandboxes?

**Alternative**: Execute tools in gateway process

**Chosen**: Separate sandbox per tool set

**Rationale**:
- Security isolation (blast radius)
- Resource limits per tool set
- Independent scaling
- Network isolation
- Separate audit trails

### Why GitOps for Tools?

**Alternative**: Runtime tool installation

**Chosen**: Tools in Git, deployed via ConfigMap

**Rationale**:
- Security review via pull requests
- Version control and audit trail
- Declarative configuration
- Prevents runtime modifications
- Aligns with Validated Patterns framework

### Why OpenShift?

**Alternative**: Generic Kubernetes

**Chosen**: Red Hat OpenShift

**Rationale**:
- Enterprise support and SLAs
- Security-hardened by default
- Integrated operators (SSO, Logging)
- Better RBAC and SCCs
- Validated Patterns framework

## Monitoring & Observability

### Metrics (Future Enhancement)

Recommended metrics to collect:
- Request rate (by user, by tool)
- Request latency (gateway, sandbox)
- Error rate (by error type)
- Token validation failures
- Resource utilization (CPU, memory)

### Logging

**Current Implementation**:
- Structured JSON logs
- OpenShift Logging (Loki)
- Query via OpenShift Console

**Log Levels**:
- `INFO`: Normal operations
- `WARN`: Recoverable errors
- `ERROR`: Request failures

### Tracing (Future Enhancement)

For advanced debugging:
- OpenTelemetry integration
- Distributed tracing
- Request correlation IDs

## Disaster Recovery

### Backup

**What to Backup**:
- Keycloak database (user data, roles)
- API key secrets
- Configuration (values files in Git)

**Not Needed** (stateless):
- Gateway pods
- Sandbox pods

### Recovery

**Restore Process**:
1. Redeploy pattern via GitOps
2. Restore Keycloak database
3. Recreate API key secrets
4. Verify connectivity

**RTO/RPO**:
- Recovery Time Objective: ~30 minutes
- Recovery Point Objective: Last Git commit

## Next Steps

- [Deployment Guide](DEPLOYMENT.md) - Install the pattern
- [Configuration Guide](CONFIGURATION.md) - Customize values
- [Security & RBAC](SECURITY-AND-RBAC.md) - Secure your deployment

