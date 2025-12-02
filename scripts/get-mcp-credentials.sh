#!/bin/bash
# Get MCP Gateway credentials for connecting Cursor IDE

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   MCP Gateway Credentials                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo

# Check if connected to cluster
if ! oc whoami &>/dev/null; then
    echo -e "${YELLOW}⚠️  Not connected to cluster. Set KUBECONFIG first.${NC}"
    echo "   export KUBECONFIG=~/your-cluster.kubeconfig"
    exit 1
fi

echo -e "${GREEN}✅ Connected to cluster as $(oc whoami)${NC}"
echo

# Get Gateway URL
echo -e "${BLUE}📡 Gateway URL:${NC}"
GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -z "$GATEWAY_URL" ]; then
    echo -e "${YELLOW}⚠️  Gateway route not found. Is the pattern deployed?${NC}"
    exit 1
fi
echo "   https://$GATEWAY_URL"
echo

# Option 1: Demo API Key (quick testing)
echo -e "${BLUE}🔑 Option 1: Demo API Key (Quick Testing)${NC}"
echo "   Token: demo-token-12345"
echo "   User:  demo-user"
echo "   Roles: mcp-admin, mcp-log-analyst"
echo

# Option 2: Keycloak OAuth (production)
echo -e "${BLUE}🔑 Option 2: Keycloak OAuth Token (Production)${NC}"

KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$KEYCLOAK_URL" ]; then
    echo "   Keycloak URL: https://$KEYCLOAK_URL"
    echo
    echo "   To get an OAuth token:"
    echo "   1. Create a user in Keycloak admin console"
    echo "   2. Assign roles: mcp-admin or mcp-log-analyst"
    echo "   3. Get token with this command:"
    echo
    echo -e "${GREEN}   # Set your credentials${NC}"
    echo "   USERNAME=your-username"
    echo "   PASSWORD=your-password"
    echo "   CLIENT_SECRET=\$(oc get secret mcp-gateway-client-secret -n mcp-shared -o jsonpath='{.data.client-secret}' | base64 -d)"
    echo
    echo -e "${GREEN}   # Get OAuth token${NC}"
    echo "   curl -k -s -X POST \"https://$KEYCLOAK_URL/realms/mcp/protocol/openid-connect/token\" \\"
    echo "     -H \"Content-Type: application/x-www-form-urlencoded\" \\"
    echo "     -d \"grant_type=password\" \\"
    echo "     -d \"client_id=mcp-gateway\" \\"
    echo "     -d \"client_secret=\$CLIENT_SECRET\" \\"
    echo "     -d \"username=\$USERNAME\" \\"
    echo "     -d \"password=\$PASSWORD\" \\"
    echo "     -d \"scope=openid\" | jq -r '.access_token'"
else
    echo "   ⚠️  Keycloak not found"
fi

echo
echo -e "${BLUE}🔑 Option 3: API Keys (Production - Recommended)${NC}"
echo "   Long-lived keys with optional expiration"
echo ""
echo "   Create an API key for a user:"
echo -e "${GREEN}   # For standalone key (no expiration)${NC}"
echo "   ./scripts/create-api-key.sh alice mcp-log-analyst never"
echo ""
echo -e "${GREEN}   # For key with 1 year expiration${NC}"
echo "   ./scripts/create-api-key.sh bob mcp-log-analyst 31536000"
echo ""
if [ -n "$KEYCLOAK_URL" ]; then
  echo -e "${GREEN}   # For key linked to Keycloak user${NC}"
  echo "   # First, get user ID from Keycloak:"
  echo "   ADMIN_PASSWORD=\$(kubectl get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)"
  echo "   ADMIN_TOKEN=\$(curl -k -s -X POST \"https://$KEYCLOAK_URL/realms/master/protocol/openid-connect/token\" \\"
  echo "     -d \"client_id=admin-cli\" -d \"username=admin\" -d \"password=\$ADMIN_PASSWORD\" -d \"grant_type=password\" | jq -r '.access_token')"
  echo "   USER_ID=\$(curl -k -s \"https://$KEYCLOAK_URL/admin/realms/mcp/users?username=alice\" \\"
  echo "     -H \"Authorization: Bearer \$ADMIN_TOKEN\" | jq -r '.[0].id')"
  echo "   # Then create linked key:"
  echo "   ./scripts/create-api-key.sh alice mcp-log-analyst never \$USER_ID"
  echo ""
fi
echo "   Advantages:"
echo "   ✅ Set once, works until revoked"
echo "   ✅ Optional expiration (e.g., 1 year)"
echo "   ✅ Can link to Keycloak users"
echo "   ✅ No token refresh needed"
echo ""
echo "   Management commands:"
echo "   • List keys:   ./scripts/list-api-keys.sh"
echo "   • Revoke key:  ./scripts/revoke-api-key.sh <key-id>"
echo "   • Rotate key:  ./scripts/rotate-api-key.sh <key-id>"

echo
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Add to Cursor IDE                                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo
echo "Create file: .cursor/mcp.json"
echo
cat << EOF
{
  "mcpServers": {
    "secure-mcp-gateway": {
      "url": "https://$GATEWAY_URL",
      "transport": {
        "type": "http",
        "headers": {
          "Authorization": "Bearer demo-token-12345"
        }
      }
    }
  }
}
EOF
echo
echo -e "${YELLOW}💡 For production, replace 'demo-token-12345' with:${NC}"
echo -e "${YELLOW}   • API key (recommended): ./scripts/create-api-key.sh <username>${NC}"
echo -e "${YELLOW}   • OAuth token: Use commands from Option 2 above${NC}"
echo
echo -e "${GREEN}✅ Done! Restart Cursor to use your MCP server.${NC}"

