#!/bin/bash
# List all API keys with status

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   MCP API Keys                                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if any keys exist
KEY_COUNT=$(kubectl get secrets -n mcp-shared -l app=mcp-api-key --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$KEY_COUNT" = "0" ]; then
  echo -e "${YELLOW}No API keys found.${NC}"
  echo ""
  echo "Create one with:"
  echo "  ./scripts/create-api-key.sh <username> [roles] [expires_in]"
  exit 0
fi

echo "Found $KEY_COUNT API key(s)"
echo ""

# List all keys with details
kubectl get secrets -n mcp-shared -l app=mcp-api-key -o json | jq -r '
.items[] | 
{
  id: .metadata.name,
  username: .metadata.labels.username,
  roles: .metadata.labels.roles,
  created: .data."created-at" | @base64d,
  expires: .metadata.labels."expires-at",
  keycloak_user: .metadata.labels."keycloak-user-id"
} | 
"─────────────────────────────────────────────────────────\n" +
"ID:             \(.id)\n" +
"Username:       \(.username)\n" +
"Roles:          \(.roles)\n" +
"Created:        \(.created)\n" +
"Expires:        \(.expires)\n" +
"Keycloak User:  \(if .keycloak_user != "" then .keycloak_user else "Not linked" end)\n"
'

echo "─────────────────────────────────────────────────────────"
echo ""
echo -e "${BLUE}Commands:${NC}"
echo "  Revoke key:  ./scripts/revoke-api-key.sh <key-id>"
echo "  Rotate key:  ./scripts/rotate-api-key.sh <key-id>"
echo "  Create key:  ./scripts/create-api-key.sh <username>"

