# PromptTrace Project - Interaction Guide

## Project Overview
**PromptTrace** is an AI-powered evaluation system for coding candidates that integrates VS Code, GitHub Copilot, and AWS backend services. The system logs and evaluates how candidates use AI to complete coding tasks.

### Architecture at a Glance
```
VS Code + Copilot ←→ MCP Server ←→ AWS Backend (Lambda + Bedrock)
                                    └→ S3 (Logging & Analytics)
```

---

## Project Components

### 1. **VS Code + Copilot + MCP Layer** (Frontend)
**Candidate-facing interface where interactions are initiated**

- **Goal**: Candidates work in VS Code with Copilot Chat as the primary UI
- **Candidate Token**: Configured via MCP settings (environment variable or config)
- **Interaction Model**: 
  - Candidates ask Copilot to help with tasks
  - MCP exposes evaluation tools that Copilot can call automatically
  - File edits are applied through Copilot's native capabilities
  - All interactions are logged on the backend

**What I'll help build:**
- MCP server configuration and tool definitions
- Integration points with Copilot Chat
- Error handling and user feedback mechanisms

---

### 2. **AWS Backend** (Cloud Infrastructure)
**Processes requests, invokes AI models, and logs all interactions**

#### Key Components:
- **API Gateway / Load Balancer**: HTTPS endpoints for MCP calls
- **InteractionHandler Lambda**: Main orchestrator for `/interact` requests
- **OutcomeLogger Lambda**: Records outcomes for `/interaction-outcome` requests
- **Bedrock**: Claude model for generating explanations and code suggestions
- **S3**: Centralized logging of interactions and outcomes
- **DynamoDB** (optional): Candidate token mapping and rate limiting
- **CloudWatch**: Monitoring and metrics

#### API Endpoints:

**POST /interact**
- Input: candidateToken, taskId, userMessage, context (files, selection, projectSummary)
- Output: assistantMessage, plan, proposedEdits[], requestId, tags
- Behavior: Calls Bedrock to generate AI response with structured edits

**POST /interaction-outcome**
- Input: candidateToken, taskId, requestId, decisions[], metrics (tests, timing)
- Output: Acknowledgment
- Behavior: Logs candidate decisions and test results to S3

#### S3 Logging Structure:
```
ai-eval-logs-{env}/
├── interactions/{year}/{month}/{day}/{candidateId}/{requestId}.json
│   └── Contains: request metadata, prompt, model response, plan, edits
└── outcomes/{year}/{month}/{day}/{candidateId}/{requestId}.json
    └── Contains: decisions, test results, timing metrics
```

**What I'll help build:**
- Lambda function code for both handlers
- Bedrock prompt engineering and tool definitions
- S3 bucket configuration and lifecycle policies
- API Gateway setup and request/response formatting
- AWS IAM roles and policies
- CloudWatch dashboards and custom metrics

---

### 3. **MCP Server** (Bridge / Adapter)
**Stateless service connecting Copilot to AWS backend**

#### Core Responsibilities:
- **Tool Exposure**: Define tools for Copilot (evaluate_project_interaction, report_interaction_outcome)
- **Candidate Identity**: Load and inject candidate token into all backend calls
- **HTTP Orchestration**: Serialize inputs, handle errors, manage retries
- **Output Shaping**: Format responses for Copilot to display and apply

#### Tools Exposed:
1. **evaluate_project_interaction**
   - Takes: userMessage, files, selection, projectSummary, candidateToken (implicit)
   - Returns: assistantMessage, plan, proposedEdits[], requestId

2. **report_interaction_outcome**
   - Takes: requestId, decisions[], optional metrics (tests, timing)
   - Returns: Acknowledgment

**What I'll help build:**
- MCP server implementation (Node.js, Python, or similar)
- Tool definitions and input/output schemas
- HTTP client for backend communication
- Error handling and retry logic
- Configuration management (base URL, candidate token, etc.)

---

## Development Workflow

### Phase 1: Backend Infrastructure
1. Set up AWS Lambda functions (InteractionHandler, OutcomeLogger)
2. Configure Bedrock model access and prompt design
3. Create S3 buckets and logging structure
4. Set up API Gateway with proper CORS and authentication
5. Define CloudWatch metrics and alarms

### Phase 2: MCP Server
1. Implement MCP server with tool definitions
2. Create HTTP client for backend communication
3. Add configuration/environment variable handling
4. Implement error handling and logging
5. Test integration with mock Copilot requests

### Phase 3: Integration & Testing
1. Configure Copilot MCP settings in VS Code
2. Test end-to-end flow (Copilot → MCP → Backend → S3)
3. Verify logging and analytics
4. Performance testing and optimization

---

## Key Implementation Details

### Candidate Authentication & Tracking
- **Solution**: Use a unique candidate token (UUID or hash)
- **Token Flow**: 
  - Stored in environment variable or MCP config file
  - Injected by MCP server into every backend call
  - Backend validates token and maps to candidateId
  - Optional: Use DynamoDB for token → candidateId mapping

### Request Lifecycle
1. Candidate types in Copilot Chat
2. Copilot calls `evaluate_project_interaction` tool via MCP
3. MCP serializes request and calls POST /interact
4. Lambda validates input, generates requestId, calls Bedrock
5. Bedrock returns structured response with proposed edits
6. MCP returns response to Copilot
7. Copilot shows edits to candidate and applies them
8. Candidate approves/rejects edits
9. MCP calls POST /interaction-outcome
10. Lambda logs outcome to S3

### Safety & Constraints
- **File Path Whitelisting**: Block edits to sensitive files (secrets, config)
- **Rate Limiting**: Per-candidate request throttling
- **Context Truncation**: Cap file size sent to Bedrock
- **Edit Limits**: Max files/lines changed per interaction
- **Token Validation**: Always verify candidate token on backend

### Monitoring & Analytics
- **Custom Metrics**:
  - Interactions per candidate
  - Average tokens per interaction
  - Approved vs proposed edits ratio
  - Test pass rates post-AI-edit
  - Time to decision
- **Dashboards**: CloudWatch or Athena-based analytics
- **Logs**: Centralized in CloudWatch and S3

---

## Directory Structure (Expected)

```
promptTrace/
├── instructions.txt          # Original requirements
├── CLAUDE.md                 # This file
├── README.md                 # Project overview
├── Devops/                   # AWS Lambda and infrastructure
│   ├── interaction-handler/  # POST /interact Lambda
│   ├── outcome-logger/       # POST /interaction-outcome Lambda
│   └── infrastructure/       # Terraform/CloudFormation templates
├── MCP/                      # MCP server implementation
│   ├── server.js/py          # Main server code
│   ├── tools/                # Tool definitions
│   └── config.ts/py          # Configuration
└── Cloud/                   # Deployment and monitoring
    ├── lambda-config.yaml
    ├── api-gateway-setup.yaml
    └── monitoring/           # CloudWatch config
```

---

## How I Can Help

I'll assist with:
- **Architecture Design**: Validating design decisions and suggesting improvements
- **Code Implementation**: Writing Lambda functions, MCP server, and infrastructure code
- **AWS Configuration**: Setting up services, IAM policies, and monitoring
- **Debugging**: Troubleshooting integration issues and error flows
- **Documentation**: Creating deployment guides and API specifications
- **Testing**: Writing test cases and integration tests

---

## Important Constraints & Guidelines

### Non-Functional Requirements
- ✅ Minimal setup friction for candidates (just configure MCP, start using Copilot)
- ✅ Transparent logging (inform candidates that AI usage is tracked)
- ✅ Resilient MCP server (handle timeouts, invalid inputs gracefully)
- ✅ HTTPS only for all backend communication
- ✅ Stateless MCP server (can scale horizontally)

### Best Practices
- All communication is JSON over HTTPS
- Generate unique requestId for every interaction
- Attach rationales to every proposed edit
- Log comprehensively but redact sensitive candidate code when possible
- Use structured tagging (taskCategory, complexity, confidence) for analysis

---

## Getting Started

1. **Clarify the tech stack**: Which AWS region? Node.js or Python for Lambdas/MCP?
2. **Define Bedrock model**: Which Claude model and throughput model?
3. **Set scope for Phase 1**: Start with a mock backend or single Lambda?
4. **Plan candidate token distribution**: How will candidates receive/configure tokens?

Feel free to ask me to start building any component at any time!
