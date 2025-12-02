#!/bin/bash
# Rotate API key (create new, revoke old)

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

OLD_KEY_ID=$1

if [ -z "$OLD_KEY_ID" ]; then
  echo "Usage: ./rotate-api-key.sh <old-key-id>"
  echo ""
  echo "This will:"
  echo "  1. Create a new API key with the same settings"
  echo "  2. Display the new key"
  echo "  3. Revoke the old key"
  echo ""
  echo "List available keys with:"
  echo "  ./scripts/list-api-keys.sh"
  exit 1
fi

echo -e "${BLUE}Rotating API key: $OLD_KEY_ID${NC}"
echo ""

# Get old key info
USERNAME=$(kubectl get secret "$OLD_KEY_ID" -n mcp-shared -o jsonpath='{.metadata.labels.username}' 2>/dev/null)
ROLES=$(kubectl get secret "$OLD_KEY_ID" -n mcp-shared -o jsonpath='{.metadata.labels.roles}' 2>/dev/null)
EXPIRES_AT=$(kubectl get secret "$OLD_KEY_ID" -n mcp-shared -o jsonpath='{.metadata.labels.expires-at}' 2>/dev/null)
KEYCLOAK_USER_ID=$(kubectl get secret "$OLD_KEY_ID" -n mcp-shared -o jsonpath='{.metadata.labels.keycloak-user-id}' 2>/dev/null)

if [ -z "$USERNAME" ]; then
  echo -e "${RED}❌ API key not found: $OLD_KEY_ID${NC}"
  echo ""
  echo "List available keys with:"
  echo "  ./scripts/list-api-keys.sh"
  exit 1
fi

echo "Current key details:"
echo "  Username: $USERNAME"
echo "  Roles: $ROLES"
echo "  Expires: $EXPIRES_AT"
if [ -n "$KEYCLOAK_USER_ID" ] && [ "$KEYCLOAK_USER_ID" != "null" ]; then
  echo "  Keycloak User: $KEYCLOAK_USER_ID"
fi
echo ""

# Calculate new expiration
if [ "$EXPIRES_AT" = "never" ]; then
  EXPIRES_IN="never"
else
  CURRENT_TIME=$(date +%s)
  EXPIRES_IN=$((EXPIRES_AT - CURRENT_TIME))
  
  # If key already expired or has less than 1 day left, set to never
  if [ $EXPIRES_IN -lt 86400 ]; then
    echo -e "${YELLOW}⚠️  Old key expires soon or is expired. Creating new key with no expiration.${NC}"
    EXPIRES_IN="never"
  fi
fi

echo -e "${BLUE}Step 1: Creating new API key...${NC}"
echo ""

# Create new key
./scripts/create-api-key.sh "$USERNAME" "$ROLES" "$EXPIRES_IN" "$KEYCLOAK_USER_ID"

echo ""
echo -e "${BLUE}Step 2: Revoking old API key...${NC}"
echo ""

# Revoke old key (without confirmation prompt)
kubectl delete secret "$OLD_KEY_ID" -n mcp-shared

echo -e "${GREEN}✅ Old API key revoked${NC}"
echo ""
echo -e "${GREEN}✅ API key rotation complete!${NC}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  • Update Cursor config with the new Bearer token shown above"
echo "  • The old key no longer works"
echo "  • Inform user '$USERNAME' about the key rotation"

