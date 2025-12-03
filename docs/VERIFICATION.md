# Pattern Verification Guide

This guide provides comprehensive instructions to verify all features of the Secure MCP Code Gateway Pattern after deployment.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Verification (5 minutes)](#quick-verification-5-minutes)
- [Component Verification](#component-verification)
  - [1. Infrastructure Verification](#1-infrastructure-verification)
  - [2. MCP Protocol Verification](#2-mcp-protocol-verification)
  - [3. Authentication Verification](#3-authentication-verification)
  - [4. Code Execution Verification](#4-code-execution-verification)
  - [5. Log Analysis Tools Verification](#5-log-analysis-tools-verification)
  - [6. Privacy Tools Verification](#6-privacy-tools-verification)
  - [7. Workspace Persistence Verification](#7-workspace-persistence-verification)
  - [8. Skills System Verification](#8-skills-system-verification)
  - [9. Security Controls Verification](#9-security-controls-verification)
- [End-to-End Test Scenarios](#end-to-end-test-scenarios)
- [Automated Test Scripts](#automated-test-scripts)
- [Troubleshooting Verification Failures](#troubleshooting-verification-failures)

---

## Prerequisites

Before running verification tests, ensure:

```bash
# 1. You have cluster access
oc whoami
oc cluster-info

# 2. Required tools are installed
which curl jq kubectl oc

# 3. Pattern is deployed
oc get applications -n openshift-gitops | grep -E "mcp-|keycloak"
```

### Set Environment Variables

```bash
# Get gateway URL
export GATEWAY_URL=$(oc get route mcp-gateway -n mcp-shared -o jsonpath='{.spec.host}')

# Get Keycloak URL
export KEYCLOAK_URL=$(oc get route keycloak -n mcp-shared -o jsonpath='{.spec.host}')

# Create a test API key (or use existing)
./scripts/create-api-key.sh test-verifier mcp-admin never
export API_KEY=$(oc get secret -n mcp-shared -l username=test-verifier -o jsonpath='{.items[0].data.key}' | base64 -d)

echo "Gateway: https://$GATEWAY_URL"
echo "Keycloak: https://$KEYCLOAK_URL"
echo "API Key: ${API_KEY:0:20}..."
```

---

## Quick Verification (5 minutes)

Run the automated verification script for a quick health check:

```bash
./scripts/test-mcp-endpoints.sh
```

Expected output:
```
✅ Gateway deployed (2/2 pods)
✅ Sandbox deployed (1/1 pods)
✅ Keycloak operational
✅ All ArgoCD applications synced
```

---

## Component Verification

### 1. Infrastructure Verification

#### 1.1 Verify All Pods Are Running

```bash
echo "=== Gateway Pods ==="
oc get pods -n mcp-shared -l app=mcp-gateway

echo "=== Sandbox Pods ==="
oc get pods -n mcp-shared -l app=mcp-log-analysis-sandbox

echo "=== Keycloak Pods ==="
oc get pods -n mcp-shared | grep keycloak
```

**Expected**: All pods show `Running` status with `1/1` or `2/2` ready.

#### 1.2 Verify Services

```bash
oc get services -n mcp-shared
```

**Expected**: Services for `mcp-gateway`, `mcp-log-analysis-sandbox`, and `keycloak`.

#### 1.3 Verify Routes

```bash
oc get routes -n mcp-shared
```

**Expected**: Routes with valid hostnames for gateway and keycloak.

#### 1.4 Verify ArgoCD Applications

```bash
oc get applications -n openshift-gitops | grep -E "mcp-|keycloak"
```

**Expected**: All applications show `Healthy` and `Synced`.

---

### 2. MCP Protocol Verification

#### 2.1 Test MCP Initialize

The `initialize` method establishes a session with the MCP server.

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "verification-test",
        "version": "1.0.0"
      }
    },
    "id": 1
  }' | jq .
```

**Expected Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "secure-mcp-gateway",
      "version": "1.0.0"
    }
  },
  "id": 1
}
```

#### 2.2 Test MCP Tools List

The `tools/list` method returns all available tools.

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 2
  }' | jq '.result.tools[] | {name, description}'
```

**Expected**: List of tools including:
- `log_store` - Search and analyze logs
- `privacy` - Scrub PII from text
- `execute_code` - Execute Python code in sandbox
- `workspace` - Persistent file storage
- `skills` - Reusable code patterns
- `get_available_tools` - List available tools
- `tool_discovery` - Browse tool documentation

#### 2.3 Test MCP Tools Call

Execute a tool call to verify the sandbox connection.

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_available_tools",
      "arguments": {}
    },
    "id": 3
  }' | jq .
```

**Expected**: Response containing sandbox_tools, standard_modules, and example code.

---

### 3. Authentication Verification

#### 3.1 Test Valid Token Access

```bash
# Should succeed with valid API key
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}' | jq '.result.tools | length'
```

**Expected**: Number of available tools (e.g., `12`).

#### 3.2 Test Invalid Token Rejection

```bash
# Should fail with invalid token
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-token-12345" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}' | jq .
```

**Expected**: Error response with authentication failure.

#### 3.3 Test Missing Authorization Header

```bash
# Should fail without auth header
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}' | jq .
```

**Expected**: Error response requesting authentication.

#### 3.4 Test API Key Lifecycle

```bash
# Run the comprehensive API key test
./scripts/test-api-keys.sh
```

**Expected**: All tests pass including creation, retrieval, authentication, and revocation.

---

### 4. Code Execution Verification

#### 4.1 Test Basic Code Execution

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\nresult = {\"message\": \"Hello from sandbox!\", \"status\": \"success\"}\nprint(json.dumps(result))"
      }
    },
    "id": 4
  }' | jq '.result.content[0].text' -r | jq .
```

**Expected**:
```json
{
  "success": true,
  "output": "{\"message\": \"Hello from sandbox!\", \"status\": \"success\"}\n"
}
```

#### 4.2 Test Code with Standard Library

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import math\nimport datetime\nprint(f\"Pi: {math.pi:.4f}\")\nprint(f\"Now: {datetime.datetime.now().isoformat()}\")"
      }
    },
    "id": 5
  }' | jq '.result.content[0].text' -r
```

**Expected**: Output showing pi value and current timestamp.

#### 4.3 Test Blocked Imports

```bash
# Should fail - os module is not allowed
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import os\nprint(os.listdir(\"/\"))"
      }
    },
    "id": 6
  }' | jq '.result.content[0].text' -r
```

**Expected**: Import error message indicating `os` is not allowed.

#### 4.4 Test Execution Timeout

```bash
# Should timeout after 30 seconds
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import time\nwhile True:\n    time.sleep(1)"
      }
    },
    "id": 7
  }' | jq '.result.content[0].text' -r
```

**Expected**: Timeout error after ~30 seconds.

---

### 5. Log Analysis Tools Verification

#### 5.1 Test Log Search

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\nerrors = log_store.search_logs(\"payment-service\", \"error\", limit=5)\nprint(json.dumps({\"count\": len(errors), \"sample\": errors[:2]}, indent=2))"
      }
    },
    "id": 8
  }' | jq '.result.content[0].text' -r
```

**Expected**: JSON output with error count and sample log entries.

#### 5.2 Test Error Summary

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\nsummary = log_store.get_error_summary(\"payment-service\", hours=24)\nprint(json.dumps(summary, indent=2))"
      }
    },
    "id": 9
  }' | jq '.result.content[0].text' -r
```

**Expected**: Summary with total_errors, errors_by_type, most_frequent_error.

#### 5.3 Test Log Level Filtering

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "warnings = log_store.search_logs(\"api\", \"\", limit=10, log_level=\"WARN\")\nfor w in warnings:\n    print(w)"
      }
    },
    "id": 10
  }' | jq '.result.content[0].text' -r
```

**Expected**: Only warning-level log entries.

---

### 6. Privacy Tools Verification

#### 6.1 Test Email Scrubbing

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "text = \"Contact john.doe@example.com for support\"\nclean = privacy.scrub_emails(text)\nprint(f\"Original: {text}\")\nprint(f\"Scrubbed: {clean}\")"
      }
    },
    "id": 11
  }' | jq '.result.content[0].text' -r
```

**Expected**: Email replaced with `[EMAIL_REDACTED]`.

#### 6.2 Test Phone Number Scrubbing

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "text = \"Call us at (555) 123-4567 or 555-987-6543\"\nclean = privacy.scrub_phone_numbers(text)\nprint(f\"Original: {text}\")\nprint(f\"Scrubbed: {clean}\")"
      }
    },
    "id": 12
  }' | jq '.result.content[0].text' -r
```

**Expected**: Phone numbers replaced with `[PHONE_REDACTED]`.

#### 6.3 Test Full PII Scrubbing

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\ndata = \"\"\"Customer: john@company.com\nPhone: 555-123-4567\nSSN: 123-45-6789\nIP: 192.168.1.100\nCard: 4532-1234-5678-9010\"\"\"\nclean = privacy.scrub_all_pii(data)\nreport = privacy.create_privacy_report(data, clean)\nprint(\"=== SCRUBBED DATA ===\")\nprint(clean)\nprint(\"\\n=== PRIVACY REPORT ===\")\nprint(json.dumps(report, indent=2))"
      }
    },
    "id": 13
  }' | jq '.result.content[0].text' -r
```

**Expected**: All PII types redacted with corresponding placeholders.

#### 6.4 Test Name Anonymization

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\ntext = \"Alice sent a message to Bob and Charlie\"\nanon, mapping = privacy.anonymize_names(text)\nprint(f\"Original: {text}\")\nprint(f\"Anonymized: {anon}\")\nprint(f\"Mapping: {json.dumps(mapping)}\")"
      }
    },
    "id": 14
  }' | jq '.result.content[0].text' -r
```

**Expected**: Names replaced with `User-A`, `User-B`, etc., with mapping.

---

### 7. Workspace Persistence Verification

#### 7.1 Test Write File

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\nresult = workspace.write_file(\"test/verification.json\", json.dumps({\"test\": \"data\", \"verified\": True}))\nprint(json.dumps(result, indent=2))"
      }
    },
    "id": 15
  }' | jq '.result.content[0].text' -r
```

**Expected**: Success message with file path and size.

#### 7.2 Test Read File

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\ncontent = workspace.read_file(\"test/verification.json\")\ndata = json.loads(content)\nprint(f\"Read data: {json.dumps(data)}\")\nprint(f\"Verification passed: {data.get(\"verified\", False)}\")"
      }
    },
    "id": 16
  }' | jq '.result.content[0].text' -r
```

**Expected**: Data matches what was written in previous step.

#### 7.3 Test List Files

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\nfiles = workspace.list_files(recursive=True)\nprint(json.dumps(files, indent=2))"
      }
    },
    "id": 17
  }' | jq '.result.content[0].text' -r
```

**Expected**: List of files including `test/verification.json`.

#### 7.4 Test Checkpoint Save/Load

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\n# Save checkpoint\nworkspace.save_checkpoint(\"verify_test\", {\"step\": 1, \"processed\": 100})\n\n# Load checkpoint\ndata = workspace.load_checkpoint(\"verify_test\")\n\n# List checkpoints\ncheckpoints = workspace.list_checkpoints()\n\nprint(f\"Saved and loaded: {json.dumps(data)}\")\nprint(f\"All checkpoints: {checkpoints}\")"
      }
    },
    "id": 18
  }' | jq '.result.content[0].text' -r
```

**Expected**: Checkpoint saved, loaded, and listed successfully.

#### 7.5 Test Workspace Info

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\ninfo = workspace.get_workspace_info()\nprint(json.dumps(info, indent=2))"
      }
    },
    "id": 19
  }' | jq '.result.content[0].text' -r
```

**Expected**: Workspace info showing path, usage, limits, and allowed extensions.

#### 7.6 Test Path Traversal Protection

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "try:\n    workspace.read_file(\"../../../etc/passwd\")\n    print(\"ERROR: Path traversal should have been blocked!\")\nexcept PermissionError as e:\n    print(f\"Security check passed: {e}\")"
      }
    },
    "id": 20
  }' | jq '.result.content[0].text' -r
```

**Expected**: PermissionError with message about path being outside workspace.

---

### 8. Skills System Verification

#### 8.1 Test Save Skill

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\nresult = skills.save_skill(\n    name=\"verify_errors\",\n    code=\"def verify_errors(service: str) -> dict:\\n    errors = log_store.search_logs(service, \\\"error\\\", limit=10)\\n    return {\\\"service\\\": service, \\\"count\\\": len(errors)}\",\n    description=\"Verification skill: count errors for a service\",\n    parameters={\"service\": \"Service name to analyze\"},\n    returns=\"Dict with service name and error count\"\n)\n\nprint(json.dumps(result, indent=2))"
      }
    },
    "id": 21
  }' | jq '.result.content[0].text' -r
```

**Expected**: Success message with skill path and functions.

#### 8.2 Test List Skills

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\nall_skills = skills.list_skills()\nprint(f\"Available skills: {json.dumps(all_skills)}\")\n\nif \"verify_errors\" in all_skills:\n    print(\"\\nSkill 'verify_errors' found!\")"
      }
    },
    "id": 22
  }' | jq '.result.content[0].text' -r
```

**Expected**: List including `verify_errors`.

#### 8.3 Test Run Skill

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\nresult = skills.run_skill(\"verify_errors\", service=\"payment-service\")\nprint(f\"Skill result: {json.dumps(result, indent=2)}\")"
      }
    },
    "id": 23
  }' | jq '.result.content[0].text' -r
```

**Expected**: Result with service name and error count.

#### 8.4 Test Get Skill Info

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\ninfo = skills.get_skill(\"verify_errors\")\nprint(f\"Name: {info[\"name\"]}\")\nprint(f\"Description: {info[\"description\"]}\")\nprint(f\"Functions: {info[\"functions\"]}\")\nprint(f\"Version: {info[\"version\"]}\")"
      }
    },
    "id": 24
  }' | jq '.result.content[0].text' -r
```

**Expected**: Skill metadata including name, description, functions, version.

#### 8.5 Test Search Skills

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\nresults = skills.search_skills(\"error\")\nprint(f\"Search results for 'error': {json.dumps(results, indent=2)}\")"
      }
    },
    "id": 25
  }' | jq '.result.content[0].text' -r
```

**Expected**: List of skills matching "error" query.

---

### 9. Security Controls Verification

#### 9.1 Verify Network Policy

```bash
# Check that network policy exists
oc get networkpolicy -n mcp-shared

# Verify sandbox can only receive traffic from gateway
oc describe networkpolicy mcp-log-analysis-sandbox -n mcp-shared
```

**Expected**: NetworkPolicy restricting ingress to gateway only.

#### 9.2 Verify Security Context Constraints

```bash
# Check sandbox pod security context
oc get pod -n mcp-shared -l app=mcp-log-analysis-sandbox -o yaml | grep -A 20 securityContext
```

**Expected**:
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- All capabilities dropped

#### 9.3 Verify Service Account

```bash
# Check service account permissions
oc get serviceaccount -n mcp-shared
oc get rolebindings -n mcp-shared
```

**Expected**: Minimal RBAC permissions (no cluster-admin).

#### 9.4 Verify TLS on Routes

```bash
# Check route TLS configuration
oc get route mcp-gateway -n mcp-shared -o yaml | grep -A 5 tls
```

**Expected**: TLS termination: edge, insecureEdgeTerminationPolicy: Redirect

#### 9.5 Test Audit Logging

```bash
# Check gateway logs for audit entries
oc logs -n mcp-shared -l app=mcp-gateway --tail=50 | grep -E "mcp_request|tools/call"
```

**Expected**: Structured JSON logs with request/response audit data.

---

## End-to-End Test Scenarios

### Scenario 1: Log Analysis Pipeline

This scenario simulates a real-world log analysis workflow.

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\n# Step 1: Search for errors\nprint(\"=== Step 1: Searching logs ===\")\nerrors = log_store.search_logs(\"payment-service\", \"error\", limit=10)\nprint(f\"Found {len(errors)} errors\")\n\n# Step 2: Scrub PII from errors\nprint(\"\\n=== Step 2: Scrubbing PII ===\")\nclean_errors = [privacy.scrub_all_pii(e) for e in errors]\nprint(f\"Scrubbed {len(clean_errors)} entries\")\n\n# Step 3: Save checkpoint\nprint(\"\\n=== Step 3: Saving checkpoint ===\")\nworkspace.save_checkpoint(\"e2e_test\", {\n    \"total\": len(errors),\n    \"sample\": clean_errors[:3]\n})\nprint(\"Checkpoint saved\")\n\n# Step 4: Create summary\nprint(\"\\n=== Step 4: Summary ===\")\nsummary = log_store.get_error_summary(\"payment-service\")\nprint(json.dumps(summary, indent=2))"
      }
    },
    "id": 100
  }' | jq '.result.content[0].text' -r
```

**Expected**: Complete pipeline execution with all steps successful.

### Scenario 2: Multi-Step Analysis with Skills

```bash
curl -k -s -X POST "https://$GATEWAY_URL/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "import json\n\n# Create a reusable analysis skill\nskills.save_skill(\n    name=\"full_analysis\",\n    code=\"def full_analysis(service: str) -> dict:\\n    # Get errors\\n    errors = log_store.search_logs(service, \\\"error\\\", limit=50)\\n    \\n    # Scrub and count\\n    clean = [privacy.scrub_all_pii(e) for e in errors]\\n    \\n    # Get summary\\n    summary = log_store.get_error_summary(service)\\n    \\n    return {\\n        \\\"service\\\": service,\\n        \\\"error_count\\\": len(errors),\\n        \\\"summary\\\": summary,\\n        \\\"sample_clean\\\": clean[:3]\\n    }\",\n    description=\"Complete error analysis with PII scrubbing\",\n    parameters={\"service\": \"Service to analyze\"}\n)\n\n# Run the skill\nresult = skills.run_skill(\"full_analysis\", service=\"api-gateway\")\nprint(json.dumps(result, indent=2))"
      }
    },
    "id": 101
  }' | jq '.result.content[0].text' -r
```

**Expected**: Skill created and executed successfully with complete analysis results.

---

## Automated Test Scripts

### Run All Verification Tests

```bash
# Full MCP endpoint test
./scripts/test-mcp-endpoints.sh

# Full API key system test
./scripts/test-api-keys.sh
```

### Create Custom Verification Script

Save this as `scripts/verify-all-features.sh`:

```bash
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
```

Make it executable:

```bash
chmod +x scripts/verify-all-features.sh
```

---

## Troubleshooting Verification Failures

### Common Issues

#### 1. Gateway Returns 503

```bash
# Check gateway pods
oc get pods -n mcp-shared -l app=mcp-gateway
oc logs -n mcp-shared -l app=mcp-gateway --tail=50

# Restart if needed
oc rollout restart deployment/mcp-gateway -n mcp-shared
```

#### 2. Sandbox Connection Failed

```bash
# Check sandbox pods
oc get pods -n mcp-shared -l app=mcp-log-analysis-sandbox
oc logs -n mcp-shared -l app=mcp-log-analysis-sandbox --tail=50

# Test internal connectivity
oc exec -n mcp-shared deployment/mcp-gateway -- \
  curl -s http://mcp-log-analysis-sandbox.mcp-shared.svc:8080/
```

#### 3. Authentication Failures

```bash
# Verify API key secret exists
oc get secrets -n mcp-shared -l app=mcp-api-key

# Check Keycloak status
oc get keycloak -n mcp-shared
oc get pods -n mcp-shared | grep keycloak
```

#### 4. Code Execution Errors

```bash
# Check sandbox tools are mounted
oc exec -n mcp-shared deployment/mcp-log-analysis-sandbox -- \
  ls -la /home/runner/tools/

# Verify Python environment
oc exec -n mcp-shared deployment/mcp-log-analysis-sandbox -- \
  python3 -c "import sys; print(sys.path)"
```

#### 5. Workspace Persistence Issues

```bash
# Check PVC status
oc get pvc -n mcp-shared

# Verify workspace mount
oc exec -n mcp-shared deployment/mcp-log-analysis-sandbox -- \
  ls -la /workspace/
```

---

## Verification Checklist

Use this checklist to track verification progress:

- [ ] **Infrastructure**
  - [ ] All pods running
  - [ ] Services accessible
  - [ ] Routes configured with TLS
  - [ ] ArgoCD apps synced

- [ ] **MCP Protocol**
  - [ ] Initialize works
  - [ ] Tools list returns all tools
  - [ ] Tools call executes successfully

- [ ] **Authentication**
  - [ ] Valid tokens accepted
  - [ ] Invalid tokens rejected
  - [ ] API key lifecycle works

- [ ] **Code Execution**
  - [ ] Basic code runs
  - [ ] Standard library available
  - [ ] Blocked imports fail
  - [ ] Timeout enforced

- [ ] **Log Analysis**
  - [ ] Search logs works
  - [ ] Error summary works
  - [ ] Level filtering works

- [ ] **Privacy Tools**
  - [ ] Email scrubbing works
  - [ ] Phone scrubbing works
  - [ ] Full PII scrubbing works
  - [ ] Name anonymization works

- [ ] **Workspace**
  - [ ] Write file works
  - [ ] Read file works
  - [ ] List files works
  - [ ] Checkpoints work
  - [ ] Path traversal blocked

- [ ] **Skills**
  - [ ] Save skill works
  - [ ] List skills works
  - [ ] Run skill works
  - [ ] Search skills works

- [ ] **Security**
  - [ ] Network policies active
  - [ ] Security context enforced
  - [ ] TLS enabled
  - [ ] Audit logging working

---

## Next Steps

After successful verification:

1. **Remove test artifacts**: Clean up test files, checkpoints, and skills
2. **Revoke test API key**: `./scripts/revoke-api-key.sh test-verifier`
3. **Configure production users**: Set up real users in Keycloak
4. **Enable monitoring**: Configure alerts for failed authentications
5. **Document customizations**: Record any environment-specific changes

See [DEPLOYMENT.md](DEPLOYMENT.md) for production hardening recommendations.

