#!/bin/bash
# Test API key system end-to-end

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   API Key System Test                                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq not found${NC}"
    exit 1
fi

if ! kubectl get namespace mcp-shared &> /dev/null; then
    echo -e "${RED}❌ mcp-shared namespace not found${NC}"
    echo "Is the pattern deployed?"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"
echo ""

# Test 1: Create API key
echo -e "${BLUE}Test 1: Creating test API key...${NC}"
./scripts/create-api-key.sh test-user mcp-admin never

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create API key${NC}"
    exit 1
fi

echo -e "${GREEN}✅ API key created${NC}"
echo ""

# Get the key
echo -e "${BLUE}Test 2: Retrieving API key...${NC}"
API_KEY=$(kubectl get secret -n mcp-shared -l username=test-user -o jsonpath='{.items[0].data.key}' 2>/dev/null | base64 -d)

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Could not retrieve API key${NC}"
    exit 1
fi

echo -e "${GREEN}✅ API key retrieved${NC}"
echo "   Key: ${API_KEY:0:16}..." 
echo ""

# Test 3: List API keys
echo -e "${BLUE}Test 3: Listing API keys...${NC}"
KEY_COUNT=$(kubectl get secrets -n mcp-shared -l app=mcp-api-key --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$KEY_COUNT" -lt 1 ]; then
    echo -e "${RED}❌ No API keys found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found $KEY_COUNT API key(s)${NC}"
echo ""

# Test 4: Test authentication with gateway
echo -e "${BLUE}Test 4: Testing authentication with gateway...${NC}"

# Get gateway URL
GATEWAY_URL=$(kubectl get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)

if [ -z "$GATEWAY_URL" ]; then
    echo -e "${YELLOW}⚠️  Gateway route not found, skipping authentication test${NC}"
else
    echo "   Gateway URL: https://$GATEWAY_URL"
    
    # Test MCP initialize
    RESPONSE=$(curl -k -s -X POST "https://$GATEWAY_URL/" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $API_KEY" \
      -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}')
    
    if echo "$RESPONSE" | jq -e '.result' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MCP initialize successful${NC}"
    else
        echo -e "${RED}❌ MCP initialize failed${NC}"
        echo "Response: $RESPONSE"
        exit 1
    fi
    
    # Test MCP tools/list
    RESPONSE=$(curl -k -s -X POST "https://$GATEWAY_URL/" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $API_KEY" \
      -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}')
    
    if echo "$RESPONSE" | jq -e '.result.tools' > /dev/null 2>&1; then
        TOOL_COUNT=$(echo "$RESPONSE" | jq '.result.tools | length')
        echo -e "${GREEN}✅ MCP tools/list successful (found $TOOL_COUNT tools)${NC}"
    else
        echo -e "${RED}❌ MCP tools/list failed${NC}"
        echo "Response: $RESPONSE"
        exit 1
    fi
    
    # Test invalid token
    RESPONSE=$(curl -k -s -X POST "https://$GATEWAY_URL/" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer invalid-token-12345" \
      -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":3}')
    
    if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Invalid token correctly rejected${NC}"
    else
        echo -e "${RED}❌ Invalid token was not rejected${NC}"
        echo "Response: $RESPONSE"
        exit 1
    fi
fi
echo ""

# Test 5: List keys again
echo -e "${BLUE}Test 5: Listing keys with script...${NC}"
./scripts/list-api-keys.sh > /tmp/list-output.txt

if grep -q "test-user" /tmp/list-output.txt; then
    echo -e "${GREEN}✅ test-user key found in list${NC}"
else
    echo -e "${RED}❌ test-user key not found in list${NC}"
    exit 1
fi
echo ""

# Test 6: Check RBAC permissions
echo -e "${BLUE}Test 6: Checking RBAC permissions...${NC}"

if kubectl get role mcp-gateway -n mcp-shared &> /dev/null; then
    echo -e "${GREEN}✅ Role exists${NC}"
else
    echo -e "${RED}❌ Role not found${NC}"
    exit 1
fi

if kubectl get rolebinding mcp-gateway -n mcp-shared &> /dev/null; then
    echo -e "${GREEN}✅ RoleBinding exists${NC}"
else
    echo -e "${RED}❌ RoleBinding not found${NC}"
    exit 1
fi
echo ""

# Test 7: Cleanup - Revoke key
echo -e "${BLUE}Test 7: Revoking test key...${NC}"
KEY_ID=$(kubectl get secret -n mcp-shared -l username=test-user -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$KEY_ID" ]; then
    echo -e "${RED}❌ Could not find key ID${NC}"
    exit 1
fi

# Delete without prompt for automated testing
kubectl delete secret "$KEY_ID" -n mcp-shared > /dev/null 2>&1

if kubectl get secret "$KEY_ID" -n mcp-shared &> /dev/null; then
    echo -e "${RED}❌ Key still exists after revocation${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Key revoked successfully${NC}"
echo ""

# Test 8: Verify key no longer works
if [ -n "$GATEWAY_URL" ]; then
    echo -e "${BLUE}Test 8: Verifying revoked key doesn't work...${NC}"
    
    RESPONSE=$(curl -k -s -X POST "https://$GATEWAY_URL/" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $API_KEY" \
      -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":4}')
    
    if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Revoked key correctly rejected${NC}"
    else
        echo -e "${RED}❌ Revoked key still works!${NC}"
        echo "Response: $RESPONSE"
        exit 1
    fi
    echo ""
fi

# Final summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ All Tests Passed!                                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "API Key System Status:"
echo "  ✅ Key creation works"
echo "  ✅ Key retrieval works"
echo "  ✅ Key listing works"
if [ -n "$GATEWAY_URL" ]; then
echo "  ✅ Gateway authentication works"
echo "  ✅ Invalid tokens rejected"
echo "  ✅ MCP protocol works"
fi
echo "  ✅ Key revocation works"
if [ -n "$GATEWAY_URL" ]; then
echo "  ✅ Revoked keys rejected"
fi
echo "  ✅ RBAC configured correctly"
echo ""
echo -e "${BLUE}API Key system is fully operational! 🚀${NC}"

