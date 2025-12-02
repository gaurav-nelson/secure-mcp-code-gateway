#!/bin/bash
# Create API key for MCP gateway access

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

USERNAME=$1
ROLES=${2:-"mcp-log-analyst"}
EXPIRES_IN=${3:-"never"}  # seconds, or "never"
KEYCLOAK_USER_ID=${4:-""}  # optional: link to Keycloak user

if [ -z "$USERNAME" ]; then
  echo "Usage: ./create-api-key.sh <username> [roles] [expires_in] [keycloak_user_id]"
  echo ""
  echo "Arguments:"
  echo "  username         - User identifier for the API key"
  echo "  roles            - Comma-separated roles (default: mcp-log-analyst)"
  echo "  expires_in       - 'never' or seconds until expiration (default: never)"
  echo "  keycloak_user_id - Optional: Keycloak user UUID to link this key"
  echo ""
  echo "Examples:"
  echo "  # Create key that never expires"
  echo "  ./create-api-key.sh alice mcp-admin never"
  echo ""
  echo "  # Create key that expires in 1 year (31536000 seconds)"
  echo "  ./create-api-key.sh bob mcp-log-analyst 31536000"
  echo ""
  echo "  # Create key linked to Keycloak user"
  echo "  ./create-api-key.sh charlie mcp-log-analyst never c7e8f9a0-1234-5678-90ab-cdef12345678"
  exit 1
fi

echo -e "${BLUE}Creating API key for user: $USERNAME${NC}"
echo ""

# Generate secure API key (64 character hex string)
API_KEY=$(openssl rand -hex 32)
KEY_ID="mcp-api-key-$(echo $USERNAME | tr '[:upper:]' '[:lower:]' | tr '_' '-')-$(date +%s)"

# Calculate expiration
if [ "$EXPIRES_IN" = "never" ]; then
  EXPIRES_AT="never"
  echo "Expiration: Never"
else
  EXPIRES_AT=$(($(date +%s) + EXPIRES_IN))
  EXPIRES_DATE=$(date -r $EXPIRES_AT '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -d @$EXPIRES_AT '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "Unknown")
  echo "Expiration: $EXPIRES_DATE (Unix timestamp: $EXPIRES_AT)"
fi

echo "Roles: $ROLES"
echo ""

# Create secret
kubectl create secret generic "$KEY_ID" \
  -n mcp-shared \
  --from-literal=key="$API_KEY" \
  --from-literal=username="$USERNAME" \
  --from-literal=roles="$ROLES" \
  --from-literal=created-at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --from-literal=expires-at="$EXPIRES_AT" \
  --from-literal=keycloak-user-id="$KEYCLOAK_USER_ID"

# Add labels for easier querying
kubectl label secret "$KEY_ID" -n mcp-shared \
  app=mcp-api-key \
  username="$USERNAME" \
  roles="$ROLES" \
  expires-at="$EXPIRES_AT" \
  keycloak-user-id="$KEYCLOAK_USER_ID"

# If linked to Keycloak user, update user attributes
if [ -n "$KEYCLOAK_USER_ID" ]; then
  echo -e "${BLUE}Linking to Keycloak user...${NC}"
  
  # Get Keycloak admin token
  KEYCLOAK_URL=$(kubectl get route keycloak -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)
  
  if [ -n "$KEYCLOAK_URL" ]; then
    ADMIN_PASSWORD=$(kubectl get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)
    
    ADMIN_TOKEN=$(curl -k -s -X POST \
      "https://$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
      -d "client_id=admin-cli" \
      -d "username=admin" \
      -d "password=$ADMIN_PASSWORD" \
      -d "grant_type=password" | jq -r '.access_token')
    
    if [ "$ADMIN_TOKEN" != "null" ] && [ -n "$ADMIN_TOKEN" ]; then
      # Update user attributes
      curl -k -s -X PUT \
        "https://$KEYCLOAK_URL/admin/realms/mcp/users/$KEYCLOAK_USER_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
          \"attributes\": {
            \"mcp_api_key_id\": [\"$KEY_ID\"],
            \"mcp_api_key_created\": [\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"]
          }
        }" > /dev/null
      
      echo -e "${GREEN}✅ Keycloak user attributes updated${NC}"
    else
      echo -e "${YELLOW}⚠️  Could not update Keycloak user attributes (admin token failed)${NC}"
    fi
  else
    echo -e "${YELLOW}⚠️  Keycloak not found, skipping user attribute update${NC}"
  fi
fi

echo ""
echo -e "${GREEN}✅ API Key created successfully!${NC}"
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   API Key Details                                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Key ID:   $KEY_ID"
echo "Username: $USERNAME"
echo "Roles:    $ROLES"
echo "Expires:  $EXPIRES_AT"
echo ""
echo -e "${BLUE}Add to Cursor (.cursor/mcp.json):${NC}"
echo ""
cat << EOF
{
  "mcpServers": {
    "secure-mcp-gateway": {
      "url": "https://your-gateway-url",
      "transport": {
        "type": "http",
        "headers": {
          "Authorization": "Bearer $API_KEY"
        }
      }
    }
  }
}
EOF
echo ""
echo -e "${YELLOW}💡 Replace 'your-gateway-url' with your actual gateway URL${NC}"
echo -e "${YELLOW}💡 Save this Bearer token securely - it cannot be retrieved later${NC}"

