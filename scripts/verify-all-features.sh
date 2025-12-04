#!/bin/bash
# Comprehensive feature verification

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}')
API_KEY=$(oc get secret -n mcp-shared -l username=test-verifier -o jsonpath='{.items[0].data.key}' 2>/dev/null | base64 -d)

if [ -z "$API_KEY" ]; then
    echo "Creating test API key..."
    ./scripts/create-api-key.sh test-verifier mcp-admin never
    API_KEY=$(oc get secret -n mcp-shared -l username=test-verifier -o jsonpath='{.items[0].data.key}' | base64 -d)
fi

test_endpoint() {
    local name="$1"
    local code="$2"
    
    echo -e "${BLUE}Testing: $name${NC}"
    
    RESPONSE=$(curl -k -s -X POST "https://$GATEWAY_URL/" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $API_KEY" \
      -d "{
        \"jsonrpc\": \"2.0\",
        \"method\": \"tools/call\",
        \"params\": {
          \"name\": \"execute_code\",
          \"arguments\": {\"code\": \"$code\"}
        },
        \"id\": 1
      }")
    
    if echo "$RESPONSE" | jq -e '.result' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $name passed${NC}"
        return 0
    else
        echo -e "${RED}❌ $name failed${NC}"
        echo "Response: $RESPONSE"
        return 1
    fi
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Secure MCP Code Gateway Verification ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Run tests
test_endpoint "Code Execution" "print('Hello World')"
test_endpoint "Log Search" "print(log_store.search_logs('api', 'error', limit=1))"
test_endpoint "Privacy Scrub" "print(privacy.scrub_emails('test@example.com'))"
test_endpoint "Workspace Write" "workspace.write_file('verify.txt', 'test')\nprint('OK')"
test_endpoint "Workspace Read" "print(workspace.read_file('verify.txt'))"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Verification Complete!               ${NC}"
echo -e "${GREEN}========================================${NC}"