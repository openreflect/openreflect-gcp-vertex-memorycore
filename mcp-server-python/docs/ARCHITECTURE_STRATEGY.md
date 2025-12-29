# OpenReflect Architecture Strategy Document

**Version**: 1.0  
**Date**: December 28, 2025  
**Authors**: Claude Opus 4.5 (AI Architect) in collaboration with OpenReflect Team  
**Status**: Strategic Planning Document

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Discovery: Built-In User Isolation](#critical-discovery-built-in-user-isolation)
3. [Isolation Tier Architecture](#isolation-tier-architecture)
4. [Shared Backplane vs Multi-Tenant Analysis](#shared-backplane-vs-multi-tenant-analysis)
5. [Strategic Questions & Answers](#strategic-questions--answers)
6. [Refactoring Complexity Analysis](#refactoring-complexity-analysis)
7. [User Onboarding Strategy](#user-onboarding-strategy)
8. [Phased Implementation Roadmap](#phased-implementation-roadmap)
9. [Technical Specifications](#technical-specifications)
10. [Future Features: Memory Sharing & Translation](#future-features-memory-sharing--translation)
11. [Agent-to-Payment (A2P) Readiness](#agent-to-payment-a2p-readiness)

---

## Executive Summary

This document outlines the strategic architecture decisions for OpenReflect's evolution from a single-user memory backplane to a multi-user SaaS product. The key insight driving this strategy is that **Vertex AI Memory Bank already provides per-user isolation through the `scope` parameter**, eliminating the need for complex per-user infrastructure in the MVP phase.

### Key Recommendations

1. **Start with Tier 1 (scope-based isolation)** - It already works, scales infinitely, and costs pennies per user
2. **Implement chat-native onboarding** - This is OpenReflect's competitive moat
3. **Design for future A2P payments** - Decouple pricing logic now
4. **Plan memory sharing as Phase 2** - A killer differentiating feature

### Strategic Principles

- **Simplicity First**: Use the simplest architecture that meets requirements
- **Upgrade Path**: Design for easy migration to higher isolation tiers
- **AI-Native UX**: Onboarding and interaction should feel natural in chat
- **Future-Ready**: Posture for upcoming AI payment capabilities

---

## Critical Discovery: Built-In User Isolation

### The `scope` Parameter

Vertex AI Memory Bank has **per-user isolation built-in** via the `scope` parameter. This is a fundamental architectural feature that changes everything:

```python
# Every memory operation takes a scope parameter for user isolation:

# Creating a memory for a specific user
await create_memory(
    fact="Alice prefers dark mode in all applications",
    scope={"user_id": "alice123"}  # <-- USER ISOLATION
)

# Retrieving memories - only gets Alice's memories
await retrieve_memories(
    scope={"user_id": "alice123"}
)

# Generating memories from conversation - isolated to Alice
await generate_memories(
    conversation=[...],
    scope={"user_id": "alice123"}
)
```

### What This Means

A **single Vertex AI Agent Engine** can serve **thousands of users** with complete memory isolation, without needing:

- ❌ Per-user GCP projects
- ❌ Per-user Agent Engines
- ❌ Per-user Cloud Run services
- ❌ Complex multi-tenant infrastructure

This fundamentally simplifies the architecture for MVP and beyond.

---

## Isolation Tier Architecture

### Four Tiers of User Isolation

| Tier | Isolation Level | Cost | Complexity | Use Case |
|------|-----------------|------|------------|----------|
| **Tier 1** | `scope` parameter | $ | ⭐ | Consumer SaaS (recommended MVP) |
| **Tier 2** | Per-user engines | $$ | ⭐⭐ | Premium tier with dedicated resources |
| **Tier 3** | Per-user Cloud Run | $$$ | ⭐⭐⭐ | Enterprise with network isolation |
| **Tier 4** | Per-user GCP project | $$$$ | ⭐⭐⭐⭐⭐ | Compliance-driven enterprises |

### Tier Comparison Matrix

| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|--------|--------|--------|--------|
| Memory isolation | ✅ | ✅ | ✅ | ✅ |
| Compute isolation | ❌ | ❌ | ✅ | ✅ |
| Network isolation | ❌ | ❌ | ✅ | ✅ |
| Billing isolation | ❌ | ❌ | ❌ | ✅ |
| Customer GCP console | ❌ | ❌ | ❌ | ✅ |
| Setup time | Instant | Seconds | Minutes | Hours |
| Cost per user/month | ~$0.01 | ~$5 | ~$50 | ~$500+ |
| Scalability | ∞ | 1000s | 100s | 10s |

### Recommended Architecture: Tier 1 (MVP)

```
                    ┌─────────────────────────────────┐
                    │     OpenReflect MCP Server      │
                    │      (Single Cloud Run)         │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │    Vertex AI Memory Bank        │
                    │      (Single Engine)            │
                    └───────────────┬─────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
    scope=user_1             scope=user_2             scope=user_N
    ┌──────────┐             ┌──────────┐             ┌──────────┐
    │ Alice's  │             │  Bob's   │             │  N's     │
    │ memories │             │ memories │             │ memories │
    └──────────┘             └──────────┘             └──────────┘
```

### Premium Architecture: Tier 2 (Per-User Engines)

```
                    ┌─────────────────────────────────┐
                    │     OpenReflect MCP Server      │
                    │      (Single Cloud Run)         │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │      Engine Manager Service      │
                    │   (Maps user_id → engine_id)    │
                    └───────────────┬─────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
    ┌──────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐
    │  Engine A   │          │  Engine B   │          │  Engine N   │
    │  (Alice)    │          │   (Bob)     │          │ (Premium N) │
    └─────────────┘          └─────────────┘          └─────────────┘
```

### Enterprise Architecture: Tier 3 (Per-User Cloud Run)

```
    ┌─────────────────────────────────────────────────────────────┐
    │                    Service Discovery                         │
    │              (Maps user_id → service URL)                   │
    └───────────────────────────┬─────────────────────────────────┘
                                │
       ┌────────────────────────┼────────────────────────────────┐
       │                        │                                │
┌──────▼──────────────┐  ┌──────▼──────────────┐  ┌──────▼──────────────┐
│ openreflect-alice   │  │ openreflect-bob     │  │ openreflect-corp-n  │
│ (Cloud Run Service) │  │ (Cloud Run Service) │  │ (Cloud Run Service) │
├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ - Dedicated compute │  │ - Dedicated compute │  │ - Dedicated compute │
│ - Dedicated engine  │  │ - Dedicated engine  │  │ - Dedicated engine  │
│ - Isolated network  │  │ - Isolated network  │  │ - VPC peering       │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

---

## Shared Backplane vs Multi-Tenant Analysis

### The Real Question

It's not "shared vs multi-tenant" — it's **what level of isolation do you need?**

### When to Use Each Tier

#### Tier 1: Scope-Based Isolation (Recommended for 99% of users)

**Best for:**
- Consumer SaaS
- Startups and small teams
- MVP and early growth
- Cost-sensitive deployments

**Provides:**
- Complete memory isolation between users
- Instant provisioning
- Minimal operational overhead
- Linear cost scaling

**Does NOT provide:**
- Compute isolation
- Network isolation
- Customer-visible GCP resources

#### Tier 2: Per-User Engines

**Best for:**
- Premium/Pro tier customers
- Users needing guaranteed performance
- Use cases with high memory volume

**Provides:**
- Dedicated Vertex AI resources
- Potential for custom engine configuration
- Better performance isolation

**Trade-offs:**
- Higher cost per user
- Engine management overhead
- Slower provisioning (seconds vs instant)

#### Tier 3: Per-User Cloud Run

**Best for:**
- Enterprise customers
- Regulated industries
- Network isolation requirements
- SOC2/HIPAA compliance paths

**Provides:**
- Complete compute isolation
- Network isolation (VPC options)
- Dedicated endpoints
- Custom scaling policies

**Trade-offs:**
- Significant cost increase
- Complex lifecycle management
- Service discovery required

#### Tier 4: Per-User GCP Project

**Best for:**
- Large enterprise customers
- Strict compliance requirements (HIPAA, FedRAMP)
- Customers requiring their own GCP console access
- Maximum isolation requirements

**Provides:**
- Complete billing isolation
- Customer owns their data in their project
- Full GCP console access
- Audit logging per project

**Trade-offs:**
- Requires GCP Organization structure
- Manual billing account association often required
- IAM propagation delays
- Per-project quota management
- 10x+ operational complexity
- ~$10-50/month minimum per project

---

## Strategic Questions & Answers

### Q1: Per-User GCP Project Provisioning — Can We Pull It Off?

**Honest Answer: Yes, technically. But you shouldn't for MVP.**

#### Why It's Hard

| Challenge | Impact |
|-----------|--------|
| GCP Organization requirement | Need Organization-level permissions |
| Billing account association | Often requires manual approval |
| IAM propagation | Takes minutes, not seconds |
| Per-project quotas | Individual quota requests needed |
| Operational complexity | 10x management overhead |
| Minimum cost | ~$10-50/month per project for base resources |

#### When It Makes Sense

- Enterprise customers with SOC2/HIPAA requiring hard isolation
- Customers who need their own GCP console access
- Regulated industries (healthcare, finance)
- Customers paying $500+/month

#### Better Approach for 99% of Users

Use `scope` isolation + optional dedicated engines (Tier 1-2). Reserve Tier 4 for Enterprise tier.

---

### Q2: Chat-Native Onboarding — Essential?

**Answer: 1000% yes. This is OpenReflect's competitive moat.**

#### Why Chat-Native Onboarding Is Essential

| Benefit | Traditional SaaS | Chat-Native |
|---------|------------------|-------------|
| Friction | High (separate signup) | Zero (in-conversation) |
| Context switching | Required | None |
| UX coherence | Disconnected | Seamless |
| Viral potential | Low | High ("just tell Claude...") |
| Differentiation | Commodity | Unique |

#### Proposed Onboarding Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CHAT-NATIVE ONBOARDING                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "Hi Claude, I want to use OpenReflect to remember things"        │
│                                                                         │
│  Claude: "Great! I can set that up for you. I'll need a few things:     │
│           1. What email would you like to use? (for account recovery)   │
│           2. Would you like me to sync memories across ChatGPT          │
│              and Claude?"                                               │
│                                                                         │
│  User: "email@example.com, and yes sync everywhere"                     │
│                                                                         │
│  Claude: "Perfect! I've created your OpenReflect memory bank.           │
│           Your user ID is: usr_abc123                                   │
│           I'll remember this ID so you don't have to.                   │
│                                                                         │
│           Try it: 'Remember that my favorite color is blue'"            │
│                                                                         │
│  User: "Remember that my favorite color is blue"                        │
│                                                                         │
│  Claude: "✓ Saved to your memory bank. You can now ask any AI           │
│           with OpenReflect: 'What's my favorite color?'                 │
│           and it will know."                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Q3: Agent-to-Payment (A2P) Readiness

**This is forward-thinking and strategically correct.**

#### Current State (December 2025)

| Provider | A2P Status | Notes |
|----------|------------|-------|
| OpenAI | Hinted | Transaction capabilities discussed |
| Anthropic | Exploring | No public timeline |
| Google | Unknown | Potential via Google Pay integration |
| Stripe | Ready | Connect, Links available as bridges |

#### How to Posture for A2P

1. **Decouple pricing logic**: Create pricing/subscription service separate from MCP
2. **Token-based access**: Issue bearer tokens that encode subscription tier
3. **Usage tracking**: Log all memory operations per user_id now
4. **Webhook-ready**: Build subscription status checks as async calls

#### Near-Term Bridge (Before A2P Exists)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PAYMENT BRIDGE FLOW                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "I want to upgrade to OpenReflect Pro"                           │
│                                                                         │
│  Claude: "Here's your upgrade link:                                     │
│           https://openreflect.ai/upgrade?user=usr_abc123                │
│                                                                         │
│           Once completed, I'll automatically unlock:                    │
│           - Unlimited memories (vs 1000)                                │
│           - Memory sharing features                                     │
│           - Cross-engine sync"                                          │
│                                                                         │
│  [User completes payment on web]                                        │
│                                                                         │
│  Claude: "✓ Your account has been upgraded to Pro!                      │
│           All premium features are now active."                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

When A2P arrives, the link is swapped for a native payment action.

---

### Q4: Memory Sharing & Translation Between Engines

**This is a killer feature that creates real defensibility.**

#### Use Cases

- "Share my work preferences with my home assistant"
- "Export my Claude memories to ChatGPT format"
- "Merge my memories from two different projects"
- "Create a team memory bank from individual memories"

#### Technical Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MEMORY TRANSLATION LAYER                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐    │
│  │   Engine A   │────▶│  OpenReflect Core    │────▶│   Engine B   │    │
│  │  (Vertex AI) │     │                      │     │  (Vertex AI) │    │
│  └──────────────┘     │  Processing:         │     └──────────────┘    │
│                       │  - Normalize schema  │                         │
│                       │  - Deduplicate       │                         │
│                       │  - Conflict resolve  │                         │
│                       │  - Privacy filter    │                         │
│                       └──────────────────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Implementation Considerations

| Aspect | Approach |
|--------|----------|
| Schema | Standardized memory format with source metadata |
| Deduplication | Semantic similarity + exact match detection |
| Conflict resolution | Timestamp-based + user preference |
| Privacy | Scope-based filtering, explicit consent |
| Sync direction | Unidirectional or bidirectional |

**Recommendation**: Plan as Phase 2 feature. Design schema now to support it.

---

## Refactoring Complexity Analysis

### Path A: Scope-Based Multi-Tenant (Recommended)

**Estimated Effort**: 2-3 days

| File | Change | Complexity |
|------|--------|------------|
| `tools.py` | Add user authentication/identification | Medium |
| `server_http.py` | Extract user_id from auth token/header | Low |
| `config.py` | Add user registration backend config | Low |
| **New**: `auth.py` | User lookup, token validation | Medium |
| **New**: `users.py` | User registration, scope management | Medium |

#### Code Changes Summary

```python
# server_http.py - Extract user from request
async def get_current_user(request: Request) -> str:
    # Option 1: From bearer token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        return await validate_and_get_user(token)
    
    # Option 2: From session
    session_id = request.cookies.get("session_id")
    if session_id:
        return await get_user_from_session(session_id)
    
    raise HTTPException(401, "Authentication required")

# tools.py - Use user_id in scope
@mcp.tool()
async def create_memory(fact: str, ttl_seconds: Optional[int] = None):
    user_id = get_current_user_id()  # From request context
    scope = {"user_id": user_id}
    # ... rest of implementation
```

### Path B: Per-User Engines

**Estimated Effort**: 1-2 weeks

Everything in Path A, plus:

| File | Change | Complexity |
|------|--------|------------|
| `tools.py` | Dynamic engine creation per user | High |
| `server_http.py` | Session-based engine resolution | High |
| **New**: `engine_manager.py` | Engine lifecycle, mapping | High |
| **New**: Database schema | User→Engine mapping storage | Medium |

#### Additional Components

```python
# engine_manager.py
class EngineManager:
    def __init__(self, db: Database):
        self.db = db
        self.client = vertexai.preview.reasoning_engines
    
    async def get_or_create_engine(self, user_id: str) -> AgentEngine:
        # Check if user has existing engine
        mapping = await self.db.get_engine_mapping(user_id)
        if mapping:
            return self.client.get(name=mapping.engine_name)
        
        # Create new engine for user
        engine = await self.create_engine_for_user(user_id)
        await self.db.save_engine_mapping(user_id, engine.name)
        return engine
```

### Path C: Per-User Cloud Run

**Estimated Effort**: 2-3 weeks

You already have `provision_user.py` which handles Cloud Run deployment!

#### What's Missing

| Component | Description | Complexity |
|-----------|-------------|------------|
| User registration flow | Sign-up, verification | Medium |
| Service discovery | Map user_id → service URL | Medium |
| Billing integration | Usage tracking, payments | High |
| Lifecycle management | Delete inactive services | Medium |
| DNS/routing | Custom domains per user (optional) | Low |

#### Existing Provisioning Script

```python
# deploy/provisioning/provision_user.py (already exists!)
def deploy_user_service(
    project_id: str, 
    region: str, 
    user_id: str, 
    image: str, 
    service_account: str, 
    engine_name: str, 
    bearer_token: str
):
    """Deploys a new Cloud Run service for a specific user."""
    service_name = f"openreflect-{user_id.lower().replace('_', '-')}"
    # ... deployment logic
```

---

## User Onboarding Strategy

### MVP Onboarding Flow (Tier 1 - Scope Based)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ONBOARDING FLOW                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. User interacts with Claude/ChatGPT                                  │
│     "I want to use OpenReflect"                                         │
│                          │                                              │
│                          ▼                                              │
│  2. MCP Server checks: Is this user registered?                         │
│     - Check by conversation ID / client fingerprint                     │
│     - Or prompt for identifier                                          │
│                          │                                              │
│            ┌─────────────┴─────────────┐                                │
│            │                           │                                │
│            ▼                           ▼                                │
│     3a. NEW USER               3b. EXISTING USER                        │
│     - Generate user_id         - Load user_id                           │
│     - Create scope             - Load preferences                       │
│     - Welcome message          - Resume context                         │
│                          │                                              │
│                          ▼                                              │
│  4. Set scope for all subsequent memory operations                      │
│     scope = {"user_id": "usr_abc123"}                                   │
│                          │                                              │
│                          ▼                                              │
│  5. User starts using memories                                          │
│     "Remember that..." → create_memory(scope=user_scope)                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### User Identity Across Clients

**Key Challenge**: How does Claude Desktop know it's the same user as ChatGPT?

#### Identity Options

| Method | Pros | Cons | Recommended |
|--------|------|------|-------------|
| **Email-based** | Universal, recoverable | Requires verification | ✅ Primary |
| **Passphrase** | User-controlled, portable | Can be forgotten | ✅ Secondary |
| **Link account** | Strong identity | Extra step | Optional |
| **Device fingerprint** | Automatic | Privacy concerns, unreliable | ❌ |

#### Recommended: Email + Passphrase

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CROSS-CLIENT IDENTITY FLOW                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FIRST TIME (any client):                                               │
│  ───────────────────────                                                │
│  Claude: "What email should I use for your OpenReflect memory bank?"    │
│  User: "alice@example.com"                                              │
│  Claude: "Great! Choose a passphrase for cross-device access            │
│           (or I can email you a magic link each time)"                  │
│  User: "my-secret-phrase-123"                                           │
│  Claude: "✓ You're set up! user_id: usr_alice_abc123"                   │
│                                                                         │
│  SUBSEQUENT (different client):                                         │
│  ────────────────────────────                                           │
│  ChatGPT: "I see you want to use OpenReflect. Have you used it before?" │
│  User: "Yes, I'm alice@example.com"                                     │
│  ChatGPT: "Please confirm with your passphrase or I can send            │
│            a verification email"                                        │
│  User: "my-secret-phrase-123"                                           │
│  ChatGPT: "✓ Welcome back Alice! Your memories are loaded."             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Onboarding UX Principles

1. **Zero external navigation**: Everything happens in chat
2. **Progressive disclosure**: Start simple, reveal complexity as needed
3. **Graceful degradation**: Works without passphrase (email verification fallback)
4. **Instant value**: User can store a memory within 60 seconds
5. **Clear mental model**: "Your memories live in the cloud, accessible from any AI"

---

## Phased Implementation Roadmap

### Phase 1: MVP (Weeks 1-2)

**Goal**: Multi-user support with scope-based isolation

| Task | Priority | Effort |
|------|----------|--------|
| Set `AGENT_ENGINE_NAME` in Cloud Run env | Critical | 1 hour |
| Add user registration (email-based) | High | 2 days |
| Implement user lookup in tools | High | 1 day |
| Chat-based onboarding prompts | High | 1 day |
| Basic usage logging | Medium | 4 hours |

**Deliverables**:
- Single project, single engine
- User isolation via `scope` parameter
- Email-based user registration
- Onboard through chat

### Phase 2: Multi-Client (Weeks 3-4)

**Goal**: Seamless experience across Claude and ChatGPT

| Task | Priority | Effort |
|------|----------|--------|
| Fix Claude Desktop session handling | Critical | 3 days |
| Unified user_id across all clients | High | 2 days |
| Passphrase/magic link authentication | High | 2 days |
| Usage tracking per user | Medium | 1 day |

**Deliverables**:
- Claude Desktop + ChatGPT both working
- Cross-client user identity
- Usage analytics foundation

### Phase 3: Premium Features (Month 2)

**Goal**: Monetization and differentiation

| Task | Priority | Effort |
|------|----------|--------|
| Per-user engines (premium tier) | High | 1 week |
| Memory export/import | High | 3 days |
| Basic memory sharing | Medium | 1 week |
| Usage-based billing integration | High | 1 week |

**Deliverables**:
- Premium tier with dedicated engines
- Memory portability
- Stripe integration

### Phase 4: Enterprise (Month 3+)

**Goal**: Enterprise readiness

| Task | Priority | Effort |
|------|----------|--------|
| Per-user Cloud Run (enterprise tier) | Medium | 2 weeks |
| SSO integration (SAML/OIDC) | Medium | 1 week |
| Audit logging | Medium | 1 week |
| SOC2 preparation | Low | Ongoing |

**Deliverables**:
- Enterprise tier
- Compliance documentation
- Self-service enterprise onboarding

---

## Technical Specifications

### User Data Model

```python
@dataclass
class User:
    user_id: str              # Primary identifier: "usr_abc123"
    email: str                # Email for recovery/verification
    passphrase_hash: str      # Hashed passphrase (optional)
    tier: str                 # "free", "pro", "enterprise"
    engine_id: Optional[str]  # Only for Tier 2+ (dedicated engine)
    created_at: datetime
    last_active: datetime
    
    # Tier-specific fields
    memory_limit: int         # Max memories (1000 free, unlimited pro)
    monthly_operations: int   # Rate limiting
```

### Scope Format

```python
# Standard scope format for all memory operations
scope = {
    "user_id": "usr_abc123",           # Required: User identifier
    # Optional additional scopes:
    "workspace_id": "ws_xyz789",       # For team/org memories
    "context": "work|personal|shared"  # Memory categorization
}
```

### API Authentication

```python
# Bearer token structure
{
    "user_id": "usr_abc123",
    "tier": "pro",
    "exp": 1735500000,
    "scope": ["memories:read", "memories:write"]
}
```

### Environment Variables

```bash
# Required for all tiers
GOOGLE_CLOUD_PROJECT=openreflect-prod
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_NAME=projects/.../agents/openreflect-main

# For user management
USER_DB_CONNECTION=postgresql://...
JWT_SECRET=your-secret-key

# For premium tiers
ENABLE_PER_USER_ENGINES=false
ENTERPRISE_ENABLED=false
```

---

## Future Features: Memory Sharing & Translation

### Memory Schema for Interoperability

```python
@dataclass
class StandardizedMemory:
    # Core fields (Vertex AI native)
    fact: str
    scope: Dict[str, str]
    
    # Metadata for translation
    source_engine: str        # Which engine created this
    source_client: str        # "claude", "chatgpt", "gemini"
    created_at: datetime
    
    # Sharing metadata
    share_status: str         # "private", "shared", "public"
    shared_with: List[str]    # List of user_ids or "team:xyz"
    
    # Translation metadata
    original_format: str      # Original memory format
    translations: Dict[str, str]  # {"openai": "...", "anthropic": "..."}
```

### Memory Sharing API (Future)

```python
# Share a memory with another user
@mcp.tool()
async def share_memory(
    memory_id: str,
    share_with: str,  # user_id or "team:team_id"
    permissions: str = "read"  # "read" or "read_write"
) -> Dict[str, Any]:
    ...

# Accept a shared memory
@mcp.tool()
async def accept_shared_memory(
    share_invite_id: str,
    merge_strategy: str = "keep_both"  # "keep_both", "prefer_shared", "prefer_mine"
) -> Dict[str, Any]:
    ...
```

---

## Agent-to-Payment (A2P) Readiness

### Current Implementation (Bridge Mode)

```python
# subscription.py
class SubscriptionManager:
    async def get_upgrade_link(self, user_id: str, target_tier: str) -> str:
        """Generate Stripe checkout link for upgrade"""
        session = stripe.checkout.Session.create(
            customer_email=await self.get_user_email(user_id),
            line_items=[{"price": TIER_PRICES[target_tier], "quantity": 1}],
            mode="subscription",
            success_url=f"https://openreflect.ai/success?user={user_id}",
            cancel_url=f"https://openreflect.ai/cancel",
            metadata={"user_id": user_id, "tier": target_tier}
        )
        return session.url
    
    async def handle_webhook(self, event: Dict) -> None:
        """Process Stripe webhook for subscription changes"""
        if event["type"] == "checkout.session.completed":
            user_id = event["data"]["object"]["metadata"]["user_id"]
            tier = event["data"]["object"]["metadata"]["tier"]
            await self.upgrade_user(user_id, tier)
```

### Future A2P Integration (When Available)

```python
# a2p_payment.py (future)
class A2PPaymentHandler:
    async def process_payment_intent(
        self,
        user_id: str,
        amount: int,
        description: str,
        confirmation_prompt: str
    ) -> PaymentResult:
        """
        Process payment through AI-native payment rail.
        
        The AI will:
        1. Show confirmation_prompt to user
        2. Collect payment confirmation
        3. Process via A2P protocol
        4. Return result
        """
        # This API will be defined by OpenAI/Anthropic
        pass
```

### Posturing Checklist

- [x] Pricing logic decoupled from MCP tools
- [x] User tier stored in user record
- [ ] Usage tracking per user (Phase 2)
- [ ] Webhook endpoints ready
- [ ] Rate limiting by tier
- [ ] Graceful upgrade prompts in chat

---

## Appendix A: Existing Provisioning Script

The codebase already includes a per-user Cloud Run provisioning script:

**Location**: `mcp-server-python/deploy/provisioning/provision_user.py`

```python
def deploy_user_service(
    project_id: str, 
    region: str, 
    user_id: str, 
    image: str, 
    service_account: str, 
    engine_name: str, 
    bearer_token: str
):
    """Deploys a new Cloud Run service for a specific user."""
    service_name = f"openreflect-{user_id.lower().replace('_', '-')}"
    # ... creates dedicated Cloud Run service per user
```

This script is ready for Tier 3 (Enterprise) deployment.

---

## Appendix B: Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-28 | Start with Tier 1 (scope-based) | Simplest, cheapest, scales infinitely |
| 2025-12-28 | Email + passphrase for identity | Universal, portable, user-controlled |
| 2025-12-28 | Chat-native onboarding | Competitive moat, zero friction |
| 2025-12-28 | Design for A2P now | Future-proofing, minimal current cost |
| 2025-12-28 | Memory sharing as Phase 2 | High value, depends on Phase 1 |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-28 | Claude Opus 4.5 | Initial comprehensive architecture strategy |

---

*This document should be reviewed and updated as the product evolves and new requirements emerge.*
