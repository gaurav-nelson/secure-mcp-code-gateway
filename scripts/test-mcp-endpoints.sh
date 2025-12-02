#!/bin/bash
# Test MCP endpoints from your local machine

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   MCP Gateway Test Script                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo

# Check if kubeconfig is set
if [ -z "$KUBECONFIG" ]; then
    echo -e "${YELLOW}⚠️  KUBECONFIG not set. Using default: ~/.kube/config${NC}"
    export KUBECONFIG=~/.kube/config
fi

# Verify cluster access
echo -e "${BLUE}🔍 Checking cluster access...${NC}"
if ! oc whoami &>/dev/null; then
    echo -e "${RED}❌ Cannot connect to cluster. Please check your KUBECONFIG.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Connected to cluster as $(oc whoami)${NC}"
echo

# Get Gateway URL
echo -e "${BLUE}🌐 Getting Gateway URL...${NC}"
GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -z "$GATEWAY_URL" ]; then
    echo -e "${RED}❌ Gateway route not found. Is the pattern deployed?${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Gateway URL: https://$GATEWAY_URL${NC}"
echo

# Test 1: Gateway Root Endpoint
echo -e "${BLUE}📝 Test 1: Gateway Root Endpoint${NC}"
echo "   GET https://$GATEWAY_URL/"
echo
GATEWAY_RESPONSE=$(curl -k -s "https://$GATEWAY_URL/")
echo "$GATEWAY_RESPONSE" | jq . 2>/dev/null || echo "$GATEWAY_RESPONSE"
echo

# Test 2: Check Gateway Pods
echo -e "${BLUE}📝 Test 2: Gateway Pods Status${NC}"
oc get pods -n mcp-shared -l app=mcp-gateway
echo

# Test 3: Gateway Logs
echo -e "${BLUE}📝 Test 3: Gateway Recent Logs (last 10 lines)${NC}"
oc logs -n mcp-shared -l app=mcp-gateway --tail=10 | tail -10
echo

# Test 4: Sandbox Pods
echo -e "${BLUE}📝 Test 4: Sandbox Pods Status${NC}"
oc get pods -n mcp-log-analysis -l app=mcp-log-analysis-sandbox
echo

# Test 5: Sandbox Health (internal)
echo -e "${BLUE}📝 Test 5: Sandbox Health Endpoint (from within cluster)${NC}"
GATEWAY_POD=$(oc get pods -n mcp-shared -l app=mcp-gateway -o jsonpath='{.items[0].metadata.name}')
if [ -n "$GATEWAY_POD" ]; then
    echo "   Testing from pod: $GATEWAY_POD"
    SANDBOX_RESPONSE=$(oc exec -n mcp-shared $GATEWAY_POD -- curl -s http://mcp-log-analysis-sandbox.mcp-log-analysis.svc.cluster.local:8080/ 2>/dev/null)
    echo "$SANDBOX_RESPONSE" | jq . 2>/dev/null || echo "$SANDBOX_RESPONSE"
else
    echo -e "${YELLOW}⚠️  No gateway pod found${NC}"
fi
echo

# Test 6: Sandbox Logs
echo -e "${BLUE}📝 Test 6: Sandbox Recent Logs (last 10 lines)${NC}"
oc logs -n mcp-log-analysis -l app=mcp-log-analysis-sandbox --tail=10 2>/dev/null | tail -10 || echo "No logs available"
echo

# Test 7: Keycloak Status
echo -e "${BLUE}📝 Test 7: Keycloak Status${NC}"
KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$KEYCLOAK_URL" ]; then
    echo -e "${GREEN}✅ Keycloak URL: https://$KEYCLOAK_URL${NC}"
    oc get pods -n mcp-shared | grep keycloak
else
    echo -e "${RED}❌ Keycloak route not found${NC}"
fi
echo

# Test 8: ArgoCD Application Status
echo -e "${BLUE}📝 Test 8: ArgoCD Application Status${NC}"
oc get applications.argoproj.io -n secure-mcp-code-gateway-hub 2>/dev/null | grep -E "NAME|mcp-|keycloak" || echo "ArgoCD applications not found"
echo

# Summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Test Summary                                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${GREEN}Gateway Endpoint:${NC}  https://$GATEWAY_URL"
echo -e "${GREEN}Keycloak Admin:${NC}   https://$KEYCLOAK_URL"
echo
echo -e "${BLUE}💡 To get Keycloak admin password:${NC}"
echo "   oc get secret credential-mcp-keycloak -n mcp-shared -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d"
echo
echo -e "${GREEN}✅ Testing complete!${NC}"

