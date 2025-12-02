# Keycloak SSO Chart

This chart deploys a **shared Keycloak (Red Hat SSO) instance** that provides OAuth 2.1 authentication for all MCP servers in the pattern.

## Deployment Options

This chart supports two deployment methods:

1. **Operator-based** (default) - Uses Red Hat SSO Operator (requires cluster-admin)
2. **Direct deployment** - Uses upstream Keycloak image (works in Developer Sandbox)

Choose based on your environment's capabilities.

## Architecture

- **One Keycloak instance** serves all MCP servers (multi-tenant)
- **One realm** (`mcp-realm`) contains all MCP-related configurations
- **Multiple OAuth clients** - one per MCP server
- **Realm-level roles** for RBAC across MCP servers

## Default Configuration

The chart includes:

- A Keycloak instance in the `mcp-shared` namespace
- The `mcp-realm` realm with example roles
- An example OAuth client: `mcp-log-analysis-client`
- Demo users for testing (remove in production)

## Adding a New MCP Server Client

When you create a new MCP server (e.g., `mcp-your-server`), you need to add an OAuth client to Keycloak:

### Step 1: Update `values.yaml`

Add your client configuration:

```yaml
keycloak:
  clients:
    logAnalysis:  # Existing example
      clientId: mcp-log-analysis-client
      secret: "PLACEHOLDER"
      redirectUris:
        - "https://mcp-log-analysis-mcp-log-analysis.apps.your-cluster.com/*"
    
    yourServer:  # Add this
      clientId: mcp-your-server-client
      secret: "PLACEHOLDER"
      redirectUris:
        - "https://mcp-your-server-mcp-your-server.apps.your-cluster.com/*"
```

### Step 2: Update `templates/keycloak-realm.yaml`

Add a new client entry in the `clients` array:

```yaml
clients:
  - clientId: mcp-your-server-client
    name: "Your Server MCP"
    description: "OAuth client for your-server MCP gateway"
    enabled: true
    clientAuthenticatorType: client-secret
    secret: "{{ .Values.keycloak.clients.yourServer.secret }}"
    publicClient: false
    standardFlowEnabled: true
    directAccessGrantsEnabled: true
    serviceAccountsEnabled: true
    redirectUris:
      {{- range .Values.keycloak.clients.yourServer.redirectUris }}
      - {{ . | quote }}
      {{- end }}
    # ... (copy protocol mappers from log-analysis example)
```

### Step 3: Create a Secret Template

Create `templates/keycloak-client-secret-your-server.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-your-server-client-secret
  namespace: mcp-your-server
type: Opaque
stringData:
  CLIENT_ID: {{ .Values.keycloak.clients.yourServer.clientId }}
  CLIENT_SECRET: {{ .Values.keycloak.clients.yourServer.secret }}
  KEYCLOAK_URL: "https://mcp-keycloak-mcp-shared.apps.{{ .Values.global.hubClusterDomain }}"
  KEYCLOAK_REALM: {{ .Values.keycloak.realm.name }}
```

### Step 4: Update Secrets

Add the client secret to `values-secret.yaml`:

```yaml
secrets:
  - name: mcp-your-server-client
    vaultPrefixes:
    - global
    fields:
    - name: client-secret
      onMissingValue: generate
      vaultPolicy: validatedPatternDefaultPolicy
```

### Step 5: Commit and Deploy

```bash
git add charts/hub/keycloak-sso/
git commit -m "Add Keycloak client for your-server MCP"
git push
```

ArgoCD will automatically update the Keycloak configuration.

## Adding New Roles

To add new realm roles for fine-grained access control:

Edit `templates/keycloak-realm.yaml`:

```yaml
roles:
  realm:
    - name: mcp-admin
      description: "Full administrative access"
    - name: mcp-log-analyst
      description: "Access to log analysis tools"
    - name: mcp-your-role  # Add this
      description: "Access to your specific tools"
```

Then assign the role to users or groups in Keycloak's admin console, or add them to the `users` section in the realm import.

## Security Notes

1. **Remove demo users in production** - Edit the `users` section in `keycloak-realm.yaml`
2. **Use strong secrets** - Generate via Vault or use a secure password manager
3. **Update redirect URIs** - Match your actual cluster domain
4. **Enable MFA** - Configure in Keycloak admin console for production

## Accessing Keycloak Admin Console

```bash
# Get the Keycloak route
oc get route -n mcp-shared

# Get admin credentials
oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d
```

Default username: `admin`

## Option 2: Direct Deployment (Developer Sandbox)

For environments without operator support (e.g., Red Hat Developer Sandbox), use the direct deployment template.

### Enable Direct Deployment

In your values file:

```yaml
keycloak:
  directDeploy: true
  namespace: your-project-name
  # SECURITY: Generate a strong password
  adminPassword: "$(openssl rand -base64 32)"
```

**⚠️ SECURITY WARNING**: Never use default passwords like `admin` in any environment. Always generate strong, random passwords.

Or use the pre-configured `values-hub-sandbox.yaml`.

### Manual Deployment

For step-by-step manual deployment instructions, see [Developer Sandbox Guide](../../../docs/DEVELOPER-SANDBOX-GUIDE.md).

### Key Differences

| Feature | Operator | Direct Deploy |
|---------|----------|---------------|
| Installation | Requires cluster-admin | Works with basic user |
| Health checks | `/health/ready`, `/health/live` | Root path `/` |
| Startup time | ~60s | ~90-120s |
| Mode | Production-ready | Development mode |
| Persistence | PVC required | H2 in-memory DB |

**Note**: Direct deployment uses Keycloak's development mode with an in-memory database. This is suitable for testing but not recommended for production. For production, use the operator-based deployment with PostgreSQL.

## Troubleshooting

### Client not appearing in Keycloak

Check the KeycloakRealmImport status:

```bash
oc get keycloakrealmimport -n mcp-shared
oc describe keycloakrealmimport mcp-realm -n mcp-shared
```

### Redirect URI mismatch

Ensure the redirect URI in the client configuration matches the actual route of your MCP gateway.

### Token errors

Check that the client secret in the MCP gateway matches the one configured in Keycloak.

## References

- [Red Hat SSO Documentation](https://access.redhat.com/products/red-hat-single-sign-on)
- [Keycloak Operator Documentation](https://www.keycloak.org/operator/installation)
- [OAuth 2.1 Specification](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-07)

