# Pattern Overview

## What is the Secure MCP Code Gateway Pattern?

The **Secure MCP Code Gateway Pattern** is a GitOps-based validated pattern for deploying secure, enterprise-grade AI agent infrastructure on Red Hat OpenShift. This pattern provides a complete framework for running multiple MCP (Model Context Protocol) servers with centralized authentication, role-based access control (RBAC), and comprehensive audit logging.

## What is MCP (Model Context Protocol)?

The Model Context Protocol (MCP) is an open protocol that standardizes how AI assistants (like Cursor IDE, Claude Desktop) connect to external tools and data sources. Instead of AI models trying to do everything themselves, MCP allows them to:

- Query databases efficiently
- Search and analyze logs
- Execute approved operations
- Access enterprise data securely

MCP provides a standard JSON-RPC 2.0 interface that AI assistants can use to discover and call tools dynamically.

## Why This Pattern Exists

AI coding assistants are powerful, but they have limitations:

1. **Token Costs**: Sending large datasets to LLMs is expensive
2. **Context Limits**: LLMs can't process massive log files or datasets
3. **Security**: You can't expose sensitive data directly to external AI services
4. **Compliance**: Enterprises need audit trails of AI agent actions
5. **Governance**: IT needs control over what tools AI agents can use

This pattern solves these problems by providing:

- **Code Mode**: AI agents call approved APIs instead of processing everything in the LLM
- **Centralized Security**: Single authentication system for all MCP servers
- **Audit Logging**: Complete visibility into all AI agent actions
- **GitOps Governance**: All tools managed via Git with security review
- **Isolation**: Code execution in secure, locked-down sandboxes

## Key Features

### 1. Multi-Tenant Architecture

One gateway serves multiple tool sets. Each tool set runs in its own isolated sandbox:

- **Shared Authentication**: One Keycloak (Red Hat SSO) instance for all tool sets
- **Shared Gateway**: One multi-tenant gateway routes to multiple sandboxes
- **Multiple Sandboxes**: Each with approved Python APIs, security isolation, and audit logging
- **Scalable**: Add new tool sets without deploying new gateways

### 2. Enterprise Security

Production-ready security features out of the box:

- **OAuth 2.1 Authentication**: Via Keycloak (Red Hat SSO)
- **API Key Support**: Long-lived tokens that never expire (optional)
- **Role-Based Access Control**: Users see only tools they're authorized to use
- **Audit Logging**: Every request logged with user identity and timestamp
- **Network Isolation**: Sandboxes cannot access external networks
- **Secure Containers**: Non-root, dropped capabilities, read-only filesystem

### 3. GitOps Governance

All infrastructure and tools managed via Git:

- **Declarative Configuration**: Everything defined in Helm charts and values files
- **Security Reviews**: New tools approved via pull requests
- **Version Control**: Complete audit trail of changes
- **Automated Deployment**: ArgoCD continuously syncs Git to cluster
- **No Runtime Modifications**: AI agents cannot install unauthorized tools

### 4. OpenShift Integration

Built specifically for Red Hat OpenShift:

- **OpenShift Logging**: Centralized log collection with Loki
- **Operators**: Red Hat SSO, Cluster Logging, ACM
- **Security Contexts**: OpenShift security best practices
- **Routes**: Automatic HTTPS endpoints with TLS
- **RBAC**: Kubernetes-native role management

### 5. Production Ready

Not a proof-of-concept - ready for enterprise use:

- **High Availability**: Multiple gateway replicas
- **Health Checks**: Liveness and readiness probes
- **Resource Limits**: Configurable CPU and memory limits
- **Monitoring**: Structured JSON logs for observability
- **Extensibility**: Clone sandbox charts to add new tool sets

## Use Cases

### 1. IT Operations

Deploy MCP servers for:
- Log analysis and troubleshooting
- Infrastructure automation
- Incident response
- Configuration management

### 2. Data Science

Deploy MCP servers for:
- Data processing and transformation
- Model training and evaluation
- Feature engineering
- Dataset analysis

### 3. Security Operations

Deploy MCP servers for:
- Threat analysis and detection
- Compliance checking
- Security audit queries
- Vulnerability scanning

### 4. Software Development

Deploy MCP servers for:
- Code review and analysis
- Test generation
- Documentation generation
- CI/CD pipeline management

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│              User (Developer with Cursor IDE)            │
└─────────────────────────────────────────────────────────┘
                          │
                          │ OAuth or API Key
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 Keycloak (Red Hat SSO)                   │
│         Authenticates users & manages roles              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Multi-Tenant MCP Gateway                    │
│  - Validates tokens                                      │
│  - Checks user roles (RBAC)                              │
│  - Routes to appropriate sandbox                         │
│  - Logs all requests                                     │
└─────────────────────────────────────────────────────────┘
          │               │               │
          ├───────────────┼───────────────┤
          ▼               ▼               ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │ Sandbox: │    │ Sandbox: │    │ Sandbox: │
   │   Log    │    │   Data   │    │  Custom  │
   │ Analysis │    │ Science  │    │  Tools   │
   └──────────┘    └──────────┘    └──────────┘
        │               │               │
        ▼               ▼               ▼
┌─────────────────────────────────────────────────────────┐
│          OpenShift Logging (Loki + Grafana)              │
│              Complete audit trail                        │
└─────────────────────────────────────────────────────────┘
```

### Example Flow

1. Developer asks Cursor AI: "Find all database errors from the last hour"
2. Cursor IDE calls gateway with user's OAuth token
3. Gateway validates token with Keycloak
4. Gateway checks user has `mcp-log-analyst` role
5. Gateway routes to log-analysis sandbox
6. Sandbox executes `log_store` tool with approved Python code
7. Results returned to Cursor IDE
8. Request logged with user identity, timestamp, and tool used

## What's Included

This pattern deploys:

1. **Keycloak (Red Hat SSO)**
   - User authentication and management
   - OAuth 2.1 token service
   - Role management (RBAC)
   - Realm: `mcp-realm`
   - Client: `mcp-gateway-client`

2. **Multi-Tenant MCP Gateway**
   - JSON-RPC 2.0 protocol implementation
   - OAuth token validation
   - API key support (optional)
   - Role-based tool filtering
   - Request routing to sandboxes
   - Audit logging

3. **Log Analysis Sandbox** (Example)
   - Tool: `log_store` - Search and analyze logs
   - Tool: `privacy` - Scrub PII from text
   - Secure execution environment
   - Network isolation

4. **OpenShift Logging**
   - Loki for log storage
   - ClusterLogForwarder for collection
   - Integration with OpenShift Console

5. **Management Scripts**
   - `create-api-key.sh` - Create long-lived API keys
   - `list-api-keys.sh` - List all API keys
   - `revoke-api-key.sh` - Revoke API keys
   - `rotate-api-key.sh` - Rotate API keys
   - `test-api-keys.sh` - Test API key authentication
   - `get-mcp-credentials.sh` - Get OAuth credentials
   - `test-mcp-endpoints.sh` - Test MCP endpoints

## Benefits

### For Developers

- Use AI assistants with enterprise data safely
- Reduce LLM token costs (efficient code execution)
- Access powerful tools through natural language
- No complex API setup - just ask questions

### For IT/Security

- Complete audit trail of AI agent actions
- Control what tools AI agents can access
- Approve all tool changes via pull requests
- Centralized authentication and authorization
- No data leakage to external AI services

### For Platform Teams

- Single pattern deploys everything
- GitOps-based infrastructure management
- Easy to extend with new tool sets
- OpenShift-native security and operations
- Scales from development to production

## Comparison: With vs Without MCP

### Without MCP (Traditional AI Assistant)

```
Developer: "What are the top 5 errors in production logs?"
AI: "I need you to download logs, paste them here..."
Developer: *downloads 100MB of logs*
Developer: *pastes into chat*
AI: "That's too much data, can you filter it first?"
Developer: *spends 30 minutes filtering*
Developer: *pastes again*
AI: "Here are the top errors..." [costs $5 in tokens]
```

Problems:
- Expensive (tokens for processing large datasets)
- Slow (multiple back-and-forth interactions)
- Insecure (sensitive logs pasted into external service)
- No audit trail (who queried what?)

### With MCP (This Pattern)

```
Developer: "What are the top 5 errors in production logs?"
AI: *calls log_store tool*
AI: "Here are the top 5 errors..." [costs $0.01 in tokens]
```

Benefits:
- Cheap (tool does efficient query, returns only results)
- Fast (one request, immediate answer)
- Secure (logs never leave your infrastructure)
- Audited (request logged with developer identity)

## Next Steps

Ready to deploy? See:
- [Deployment Guide](DEPLOYMENT.md) - Installation instructions
- [Architecture Guide](ARCHITECTURE.md) - Detailed technical design
- [Configuration Guide](CONFIGURATION.md) - Customization options

