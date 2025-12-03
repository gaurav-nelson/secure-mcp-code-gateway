# Secure MCP Code Gateway Pattern

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A GitOps-based validated pattern for deploying secure, enterprise-grade MCP infrastructure on Red Hat OpenShift. This pattern provides a centralized gateway for multiple MCP (Model Context Protocol) servers with unified authentication, role-based access control (RBAC), and comprehensive audit logging.

## Inspiration

This pattern implements the architecture described in Anthropic's **[Code Execution with MCP: Building More Efficient Agents](https://www.anthropic.com/engineering/code-execution-with-mcp)** blog post.

The key insight: instead of passing large datasets through the AI's context window (consuming hundreds of thousands of tokens), AI agents can **write code that executes in a secure sandbox**. Data flows between tools within the sandbox, and only the final results return to the AI—achieving **90-99% token savings** on data-intensive operations.

This pattern extends that concept for enterprise environments by adding:
- **GitOps-managed tools** - Security teams approve tools via pull requests
- **OAuth 2.1 authentication** - Centralized identity via Keycloak
- **Multi-tenant sandboxes** - Isolated execution environments on OpenShift
- **Persistent state & skills** - AI agents can save checkpoints and reusable code patterns
- **Progressive tool discovery** - Tools exposed as browsable files for on-demand loading

## What is MCP?

The Model Context Protocol (MCP) is an open standard that enables AI assistants (like Cursor, Claude Desktop, or custom agents) to connect to external tools and data sources. MCP servers expose tools that AI can call to perform actions—querying databases, analyzing logs, calling APIs, or processing files.

### The Challenge: Enterprise MCP Deployment

As enterprises deploy MCP servers at scale, three critical challenges emerge:

1. **Security and Compliance Gaps** - Traditional MCP implementations lack enterprise security controls:
   - **No centralized authentication** - Each MCP server manages its own auth, creating inconsistent security postures
   - **No audit trail** - No unified logging of who accessed what tools, when, and what data was processed
   - **No RBAC** - Users get access to all tools or none; no granular role-based permissions
   - **Data exposure risk** - Sensitive data flows through external AI services with no controls
   - **Compliance failures** - SOC 2, HIPAA, and PCI-DSS require audit logs and access controls that traditional MCP can't provide

2. **Operational Complexity** - Managing dozens of standalone MCP servers means:
   - Multiple endpoints to secure and monitor
   - Inconsistent logging formats
   - No single pane of glass for operations
   - Difficult incident response without centralized visibility

3. **Cost and Performance** - Without optimization:
   - Loading hundreds of tool schemas upfront consumes massive tokens (200-500 tokens per tool definition)
   - Intermediate results flowing through the LLM can consume 200,000+ tokens for a single request
   - Large datasets must flow through AI context windows, multiplying costs

**Example**: A financial services firm deploying 20 MCP tools faces 20 separate authentication systems, no unified audit log for regulators, and no way to revoke a compromised user's access across all tools simultaneously.

### This Pattern's Solution: Secure MCP Gateway

This pattern implements an **enterprise MCP gateway** that sits between AI clients and your MCP tool servers:

- **Centralized authentication** - Single Keycloak instance provides OAuth 2.1 and API key auth for all tools
- **Complete audit logging** - Every MCP request logged with user identity, tool called, and timestamp
- **Role-based access control** - Users see only the tools their roles permit
- **Compliance-ready** - Built-in audit trails for SOC 2, HIPAA, and regulatory requirements
- **Isolated sandboxes** - Tools run in secure, isolated environments on OpenShift
- **Progressive tool discovery** - Gateway exposes only relevant tools based on user roles, reducing token overhead
- **Efficient data handling** - Results flow between tools within sandboxes; only final results return to the AI

**Result**: Deploy MCP tools with enterprise security, unified governance, and 90%+ cost reduction on data-intensive operations.

## Quick Start

```bash
# 1. Deploy the pattern
./pattern.sh make install

# 2. Create an API key (recommended)
./scripts/create-api-key.sh alice mcp-log-analyst never

# 3. Add to your AI (.your AI/mcp.json)
{
  "mcpServers": {
    "secure-mcp-gateway": {
      "url": "https://your-gateway-url",
      "transport": {
        "type": "http",
        "headers": {
          "Authorization": "Bearer <your-api-key>"
        }
      }
    }
  }
}

# 4. Ask Your AI
"Use log_store to find all errors from the last hour"
```

**See [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.**

## Architecture

This pattern uses a **multi-tenant gateway with isolated sandboxes** - an architecture designed for context efficiency and security at scale.

```
┌────────────────────────────────────────────────────────┐
│                    Shared Infrastructure               │
│  ┌─────────────┐              ┌──────────────────────┐ │
│  │  Keycloak   │              │ OpenShift Logging    │ │
│  │   (SSO)     │              │      (Loki)          │ │
│  └─────────────┘              └──────────────────────┘ │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│          Multi-Tenant MCP Gateway                       │
│  • Authenticates users (API keys, OAuth, demo token)    │
│  • Loads tool schemas on-demand (not all upfront)       │
│  • Routes requests to appropriate sandboxes             │
│  • Enforces RBAC (users see only authorized tools)      │
└─────────────────────────────────────────────────────────┘
           │
           ├─────────────────┬──────────────────┬
           ▼                 ▼                  ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Sandbox:    │  │  Sandbox:    │  │  Sandbox:    │
   │ Log Analysis │  │   Custom     │  │  YOUR-SERVER │
   │              │  │   Tools      │  │              │
   │  Tools:      │  │  Tools:      │  │  Tools:      │
   │ log_store.py │  │ your-api.py  │  │ ...          │
   │ privacy.py   │  │ ...          │  │              │
   │              │  │              │  │              │
   │ Data flows   │  │ Data flows   │  │ Data flows   │
   │ between      │  │ between      │  │ between      │
   │ tools here   │  │ tools here   │  │ tools here   │
   │ (not via AI) │  │ (not via AI) │  │ (not via AI) │
   └──────────────┘  └──────────────┘  └──────────────┘
```

### Why This Architecture?

**Problem**: Traditional MCP implementations load all tool definitions into the AI's context window upfront, and all data flows through the AI between tool calls. With 1,000 tools, this means 200,000+ tokens consumed before processing the first request.

**Solution**: This pattern separates concerns:

1. **Gateway handles discovery** - Returns only relevant tool definitions based on user request and roles
2. **Sandboxes handle execution** - Tools call each other directly; data flows within the sandbox
3. **AI orchestrates, doesn't transport** - The AI decides what to do, sandboxes do the work

**Example**: Filtering a 10,000-row spreadsheet then uploading to a CRM:
- **Traditional**: Load 10,000 rows into AI context → AI filters → AI uploads (400K tokens)
- **This pattern**: Sandbox filters rows internally → returns "Updated 247 records" (50 tokens)

This architecture delivers **98%+ token savings** on data-intensive workflows.

## What This Pattern Provides

### 1. Production-Ready MCP Gateway
- Full JSON-RPC 2.0 protocol implementation
- Works with your AI IDE and other MCP clients out of the box
- High availability (multiple replicas)
- Health checks and monitoring

### 2. Centralized Authentication
- Keycloak (Red Hat SSO) for OAuth 2.1
- API keys for automation (never expire)
- Demo token for development
- Single sign-on across all tool sets

### 3. Role-Based Access Control (RBAC)
- Users only see tools they're authorized to use
- Define roles in Keycloak (`mcp-admin`, `mcp-log-analyst`, etc.)
- Map roles to tool sets
- Enforce access at runtime

### 4. Complete Audit Trail
- Every request logged with user identity
- Structured JSON logs
- OpenShift Logging integration (Loki + Grafana)
- Query logs in OpenShift Console

### 5. Security & Isolation
- Tools run in isolated sandboxes
- Non-root containers, dropped capabilities
- NetworkPolicies restrict traffic
- Read-only root filesystem
- GitOps-managed tools (security review via PRs)

### 6. Example Tool Set
- **Log Analysis Sandbox** with tools:
  - `log_store` - Search and analyze logs efficiently
  - `privacy` - Scrub PII from text

### 7. Extensible Architecture
- Clone sandbox charts to add your own tool sets
- All tool sets share the same gateway and authentication
- No new gateway deployment needed

## Design Philosophy: Efficiency by Design

This pattern implements several architectural patterns that maximize efficiency:

### Progressive Tool Discovery

Instead of loading all tool definitions upfront, the gateway exposes tools based on:
- **User roles** - Users only see tools they're authorized to access
- **Request context** - Only relevant tool sets are presented
- **On-demand loading** - Tool schemas loaded when needed, not at startup

**Impact**: An organization with 50 tool sets (500 total tools) can present each user with only 5-10 relevant tools, reducing initialization overhead by 90%.

### Data Locality and Processing

Tools execute in sandboxes where data can flow directly between operations:

```python
# All processing happens in sandbox - data never enters AI context
logs = log_store.query(service="api", level="ERROR", hours=24)
filtered = [log for log in logs if "timeout" in log.message]
summary = privacy.scrub_pii(filtered[:10])
return summary  # Only this small summary goes to AI
```

**Benefits**:
- Process large datasets without context limits
- Chain operations without token overhead
- Filter and transform before returning results
- Handle sensitive data that shouldn't reach external AI services

### Privacy-Preserving Architecture

Sensitive data stays in sandboxes by default:

- **Sandbox-to-sandbox communication** - Data flows between tools internally
- **Configurable result filtering** - Return summaries, not raw data
- **Audit without exposure** - Log operations without logging data
- **Compliance-friendly** - Keep PII/PHI in your infrastructure

**Example**: Processing a 50,000-patient medical dataset to find treatment patterns. The sandbox analyzes locally and returns only aggregated statistics - individual records never enter the AI context.

### State Management and Composition

Sandboxes can maintain state across operations, enabling complex workflows:

```python
# First request: Start processing
dataset = large_data_source.fetch()  # 10GB dataset
progress = process_batch(dataset, batch_size=1000)
save_checkpoint(progress)
return "Processed 1,000 records, checkpoint saved"

# Follow-up request: Continue from checkpoint
progress = load_checkpoint()
result = process_remaining(progress)
return final_summary(result)
```

This allows agents to handle long-running tasks that would exceed single-request limits.

## Use Cases

- **IT Operations**: Log analysis, infrastructure automation, incident response
- **Data Science**: Data processing, model training, feature engineering
- **Security**: Threat analysis, compliance checking, vulnerability scanning
- **Development**: Code review, test generation, documentation

## Key Features

| Feature | Benefit |
|---------|---------|
| **Sandboxed Execution** | Data processing in isolated environments - 90-99% token savings |
| **Progressive Tool Loading** | Load only relevant tools, not all upfront - faster initialization |
| **Direct Data Flow** | Results flow between tools in sandbox, not through AI context |
| **Multi-Tenant Gateway** | One gateway serves all tool sets - simpler deployment |
| **Centralized Auth** | One Keycloak instance for all MCP servers |
| **Role-Based Tool Access** | Users see only authorized tools - reduced context overhead |
| **GitOps Governance** | All tools managed via Git with PR approval |
| **Privacy-Preserving** | Sensitive data stays in sandboxes - never enters AI context |
| **Audit Logging** | Complete trail: who did what, when |
| **OpenShift Native** | Uses operators, routes, logging, security contexts |
| **API Key Support** | Long-lived tokens that never expire (optional) |

## Documentation

### Getting Started
- **[Overview](docs/OVERVIEW.md)** - Understanding the pattern, use cases, and benefits
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Step-by-step installation instructions
- **[Architecture Guide](docs/ARCHITECTURE.md)** - Technical design and components
- **[Architecture: Context Efficiency](docs/ARCHITECTURE-EFFICIENCY.md)** - How this pattern achieves 90-99% token savings

### Configuration
- **[Configuration Guide](docs/CONFIGURATION.md)** - Values files and customization options
- **[Security & RBAC](docs/SECURITY-AND-RBAC.md)** - Authentication, authorization, and audit logging

### Extending the Pattern
- **[Extending the Pattern](docs/EXTENDING-THE-PATTERN.md)** - Add your own MCP servers and tool sets
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Additional Resources
- [Tool Development](tools/log-analysis/README.md) - Creating secure tools
- [Helm Charts](charts/hub/) - Chart documentation
- [Management Scripts](scripts/) - API key management, testing

## Prerequisites

- Red Hat OpenShift Container Platform 4.10+
- Cluster admin access
- `oc` CLI and `podman` (4.3.0+)
- Container registry (for custom images)

## Adding Your Own Tool Sets

The multi-tenant architecture makes it easy:

```bash
# 1. Create your tools
mkdir -p tools/database
cat > tools/database/postgres.py <<'EOF'
def execute_query(database: str, query: str):
    """Execute SQL query against database."""
    return results
EOF

# 2. Clone sandbox chart
cp -r charts/hub/mcp-log-analysis-sandbox charts/hub/mcp-database-sandbox

# 3. Update gateway configuration
# Edit charts/hub/mcp-gateway/values.yaml to add tool set

# 4. Deploy
git add .
git commit -m "Add database tool set"
git push
# ArgoCD automatically syncs
```

**That's it!** The existing gateway now routes to your new sandbox.

See [Extending the Pattern](docs/EXTENDING-THE-PATTERN.md) for detailed instructions.

## Real-World Impact: Context Efficiency in Action

### Scenario 1: Log Analysis

**Without This Pattern** (Traditional AI Chat):
```
Developer: "Find production errors from last hour"
AI: "Please download logs and paste them..."
Developer: *downloads 500MB of logs*
Developer: *tries to paste*
AI: "Error: Input exceeds context limit"
Developer: *manually filters logs*
Developer: *pastes filtered logs*
AI: "Here are the errors..." (processes 50K tokens)

→ Result: 30 minutes, $5 in tokens, manual work required
```

**With This Pattern** (Sandboxed Execution):
```
Developer: "Find production errors from last hour"
AI: *calls log_store tool in sandbox*
   Sandbox: Queries 2M log lines locally
   Sandbox: Filters for level=ERROR, time=last_hour
   Sandbox: Returns top 5 with context
AI: "Here are the top 5 errors..." (processes 200 tokens)

→ Result: 5 seconds, $0.01 in tokens, fully automated
```

**Token Savings: 99.6%** (50,000 tokens → 200 tokens)

---

### Scenario 2: Data Pipeline (Spreadsheet → CRM)

**Without Sandboxed Execution**:
```
Request: "Import customer contacts from Sheet-123 to Salesforce"

Step 1: Fetch spreadsheet
  API: Returns 10,000 rows
  Tokens: 150,000 (all rows flow through AI context)

Step 2: AI processes each row
  AI: Validates 10,000 rows in context
  Tokens: 150,000 (reading again)

Step 3: AI writes to CRM
  AI: Formats 10,000 records
  Tokens: 200,000 (writing out)

Total: 500,000 tokens, 5 minutes, $25
```

**With This Pattern** (Data Stays in Sandbox):
```
Request: "Import customer contacts from Sheet-123 to Salesforce"

Step 1: Gateway routes to sandbox
  Sandbox: Fetches Sheet-123 (10,000 rows stay in sandbox)

Step 2: Sandbox processes internally
  for row in sheet.rows:
    salesforce.create_contact(row)

Step 3: Sandbox returns summary
  Returns: "Imported 10,000 contacts, 3 validation errors"

AI receives: Summary only (50 tokens)

Total: 50 tokens, 30 seconds, $0.02
```

**Token Savings: 99.99%** (500,000 tokens → 50 tokens)

---

### Scenario 3: Multi-Step Data Processing

**Task**: "Analyze Q4 sales data: aggregate by region, identify top products, generate summary report"

**Traditional Approach** (All Data Through AI):
```
1. Load sales.csv (50K rows) → 200K tokens in context
2. AI groups by region → keeps all data in context
3. AI calculates top products → still all in context
4. AI formats report → reads everything again
Total: 600K+ tokens
```

**This Pattern** (Processing in Sandbox):
```
1. Sandbox loads sales.csv (data stays in sandbox)
2. Sandbox runs: df.groupby('region').agg({'sales': 'sum'})
3. Sandbox calculates: df.groupby('product').head(10)
4. Sandbox generates: summary.json with 20 lines
5. AI receives: Only the 20-line summary → 300 tokens
Total: 300 tokens
```

**Token Savings: 99.95%** (600,000 tokens → 300 tokens)

---

### Key Insight

The pattern keeps data **inside secure sandboxes** where it belongs. The AI orchestrates operations and sees results, but never becomes a data transport mechanism. This delivers:

- **Massive cost reduction** - 90-99% fewer tokens on data-heavy tasks
- **Faster responses** - No waiting for huge context windows to process
- **Better security** - Sensitive data never leaves your infrastructure
- **Scalability** - Handle datasets that exceed context limits

## API Key Management

For production use, API keys are recommended over OAuth tokens:

```bash
# Create API key (never expires)
./scripts/create-api-key.sh alice mcp-log-analyst never

# List all API keys
./scripts/list-api-keys.sh

# Revoke API key
./scripts/revoke-api-key.sh <key-id>

# Rotate API key
./scripts/rotate-api-key.sh <key-id>

# Test API keys
./scripts/test-api-keys.sh
```

API keys:
- Never expire (or configurable expiration)
- No refresh needed
- Easy to rotate
- Per-user identity and roles

## Support

- **Issues**: [GitHub Issues](https://github.com/validatedpatterns/secure-mcp-code-gateway/issues)
- **Community**: [Validated Patterns Forum](https://groups.google.com/g/validatedpatterns)
- **Documentation**: [validatedpatterns.io](https://validatedpatterns.io/patterns/secure-mcp-code-gateway/)

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Contributing

This is a validated pattern in the **sandbox tier**. Community contributions are welcome!

- Report issues via GitHub
- Submit pull requests for new features
- Share your tool sets and use cases
- Improve documentation

## Pattern Status

**Tier**: Sandbox
**Status**: Active Development
**OpenShift Version**: 4.10+
**Last Updated**: December 2025
