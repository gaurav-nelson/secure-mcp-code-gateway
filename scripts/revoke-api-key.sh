#!/bin/bash
# Revoke API key

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

KEY_ID=$1

if [ -z "$KEY_ID" ]; then
  echo "Usage: ./revoke-api-key.sh <key-id>"
  echo ""
  echo "List available keys with:"
  echo "  ./scripts/list-api-keys.sh"
  exit 1
fi

echo -e "${BLUE}Revoking API key: $KEY_ID${NC}"
echo ""

# Get key info before deletion
USERNAME=$(kubectl get secret "$KEY_ID" -n mcp-shared -o jsonpath='{.metadata.labels.username}' 2>/dev/null)
ROLES=$(kubectl get secret "$KEY_ID" -n mcp-shared -o jsonpath='{.metadata.labels.roles}' 2>/dev/null)

if [ -z "$USERNAME" ]; then
  echo -e "${RED}❌ API key not found: $KEY_ID${NC}"
  echo ""
  echo "List available keys with:"
  echo "  ./scripts/list-api-keys.sh"
  exit 1
fi

echo "Key details:"
echo "  Username: $USERNAME"
echo "  Roles: $ROLES"
echo ""

# Confirm deletion
read -p "Are you sure you want to revoke this API key? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Revocation cancelled.${NC}"
  exit 0
fi

# Delete secret
kubectl delete secret "$KEY_ID" -n mcp-shared

echo ""
echo -e "${GREEN}✅ API key revoked successfully!${NC}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  • User '$USERNAME' will no longer be able to authenticate with this key"
echo "  • If the key was saved in Cursor config, it will stop working immediately"
echo "  • Consider informing the user and providing a new key if needed"

