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
├── DevOps/                   # AWS Lambda, infrastructure, and deployment
│   ├── interaction-handler/  # POST /interact Lambda
│   │   ├── handler.py        # Lambda function code
│   │   └── requirements.txt  # Python dependencies
│   ├── outcome-logger/       # POST /interaction-outcome Lambda
│   │   ├── handler.py        # Lambda function code
│   │   └── requirements.txt  # Python dependencies
│   └── infrastructure/       # Terraform: API Gateway, IAM, S3, networking
│       ├── main.tf           # Core infrastructure config
│       ├── api-gateway.tf    # API Gateway setup
│       ├── iam.tf            # IAM roles and policies
│       ├── s3.tf             # S3 buckets for logging
│       ├── variables.tf      # Input variables
│       ├── outputs.tf        # Output values
│       └── terraform.tfstate # Terraform state
└── MCP/                      # MCP server implementation
    ├── server.js/py          # Main server code
    ├── tools/                # Tool definitions
    └── config.ts/py          # Configuration
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

## Phase 4: Hiring Metrics & Analytics

### Overview
The system now captures **what** candidates do (accept/reject suggestions), but we need to measure **how** they think. This phase transforms raw interaction logs into hiring-relevant signals that distinguish between:
- **Lucky copiers**: Accept first suggestion quickly, no analysis, tests fail
- **Thoughtful collaborators**: Ask questions, modify suggestions, run tests
- **Problem solvers**: Demonstrate deep understanding, leverage AI strategically

**Reference**: See [METRICS_PROPOSAL.md](METRICS_PROPOSAL.md) for complete analysis, scoring formulas, and success criteria.

### Implementation: Three Sub-Phases

#### Phase 4A: Enhanced Data Collection (1 day)
Expand Lambda functions to capture thinking patterns:

**InteractionHandler changes** (`DevOps/interaction-handler/handler.py`):
- Add `contextQuality` metadata: length, fileCount, selectionLength, clarity, questionsAsked
- Log all context metadata to S3 interaction records
- Helps identify: Did candidates think before asking?

**OutcomeLogger changes** (`DevOps/outcome-logger/handler.py`):
- Expand `decisions[]` to include:
  - `timeToDecisionMs`: Time from suggestion to approval/rejection
  - `modificationDescription`: What did they change before applying?
  - `testStatusBefore` / `testStatusAfter`: Did they validate?
- Add `metrics` object with aggregates:
  - `decisionSpeed`, `modificationCount`, `rejectionCount`, `followUpQuestions`, `testCoverageChange`

**Why**: These signals reveal analysis depth vs. blind acceptance.

#### Phase 4B: Bedrock Instruction Enhancements (1 day)
Modify Bedrock prompts to generate assessment data:

**InteractionHandler changes** (`DevOps/interaction-handler/handler.py` - `_build_prompt()`):
- Add system instructions for Bedrock to:
  - Rate confidence (0-100) per proposed edit
  - Offer alternative approaches with trade-offs
  - Suggest test strategies (before/after)
  - Flag if solution is over-engineered
- Enhanced response structure includes confidence scores and alternatives

**Why**: High-confidence suggestions being rejected = critical thinking. Candidates exploring alternatives = thoroughness.

#### Phase 4C: Analytics Transformation Pipeline (2-3 days)
Build scoring engine that converts logs to hiring signals:

**New file**: `DevOps/analytics/transform.py`
- Reads raw S3 interaction + outcome logs
- Computes 6 **foundational signals** per task:
  1. Context Quality (0-100): How thorough was the problem description?
  2. Analysis Depth (0-100): Did they take time and ask questions?
  3. Critical Thinking (0-100): Rejection rate, modification rate, test pass rate
  4. Test Culture (0-100): Did they write and run tests?
  5. Code Quality (0-100): Reduced complexity? Removed duplication?
  6. Decision Quality (0-100): Post-edit tests pass? No new bugs?

- Calculates 3 **composite scores** per candidate:
  - **AI Leverage Score**: Strategic acceptance of high-confidence suggestions
  - **Problem Solver Score**: Understanding + Analysis Depth + Critical Thinking
  - **Engineer Score**: Testing discipline + Code quality

- Produces hiring recommendation per candidate:
  - 🟢 **HIRE**: Excellent problem solver + engineer
  - 🟡 **INTERVIEW**: Competent but gaps in specific areas
  - 🔴 **PASS**: Below threshold

**Deployment**:
- Scheduled Lambda or Glue job (daily/weekly batch)
- OR event-driven Lambda on S3 outcome log write (real-time scoring)
- Writes final scores to `metrics/{candidateId}/summary.json`

### S3 Logging Structure (Updated)

```
ai-eval-logs-{env}/
├── interactions/{year}/{month}/{day}/{candidateId}/{requestId}.json
│   └── Contains: metadata, context quality, prompt, model response, edits, confidence
├── outcomes/{year}/{month}/{day}/{candidateId}/{requestId}.json
│   └── Contains: decisions, timing, modifications, test status, metrics
└── metrics/{candidateId}/summary.json
    └── Contains: aggregate scores, composite levels, hiring recommendation
```

### Scoring Formulas

**Real-world example**: Candidate takes 3000ms to decide on high-confidence edit, modifies it slightly, tests pass:
- High `analysisDepth` (took time, modified suggestion)
- High `decisionQuality` (tests pass)
- High `criticalThinking` (decided to modify before accepting)
- → **Problem Solver Score** ≈ 85+ (hire-level)

vs.

Candidate accepts first suggestion in 200ms, no modifications, tests fail:
- Low `analysisDepth` (instant acceptance)
- Low `decisionQuality` (breaking changes)
- Low `criticalThinking` (never questioned)
- → **Problem Solver Score** ≈ 40 (pass)

### Files to Modify

1. **DevOps/interaction-handler/handler.py**
   - Add context quality metadata
   - Enhance Bedrock prompt with confidence/alternatives instructions
   - Log metadata to S3

2. **DevOps/outcome-logger/handler.py**
   - Add timeToDecisionMs, modifications, test status
   - Add metrics aggregates

3. **NEW: DevOps/analytics/transform.py**
   - Read logs, compute signals, generate scores
   - Output hiring recommendations

4. **DevOps/infrastructure/s3.tf** (if needed)
   - Add `metrics/` prefix lifecycle policy (if using separate paths)

### Success Criteria

✅ Historical logs (if any) backtest correctly (good candidates score 80+, poor candidates score <50)
✅ Signal correlation: High rejection rates + high test passes = high problem solver score
✅ Spot-check audit: Manually trace 1-2 candidate scorecards through formula
✅ Alerts: CloudWatch monitors for gaming (e.g., artificially delayed decisions)

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
