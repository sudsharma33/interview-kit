# Production Architecture — Interview Kit Generator

This document describes the **target production architecture** for the Interview Kit Generator. The current implementation is a single-process Streamlit prototype suitable for demos and evaluation. This document shows the path from that prototype to a production-grade, multi-tenant, enterprise-deployable system.

---

## 1. Current architecture (prototype)

Single-process layered monolith. UI and business logic share a single Python runtime.

```
┌──────────────────────────────────────────────┐
│           USER'S BROWSER                     │
└─────────────────┬────────────────────────────┘
                  │ HTTP / WebSocket
┌─────────────────▼────────────────────────────┐
│       STREAMLIT SERVER (one process)         │
│  ┌────────────────────────────────────────┐  │
│  │ Presentation: widgets, tabs, scorecard │  │
│  │ Logic: validate_inputs, generate_kit   │  │
│  │ Integration: pypdf, python-docx, SDK   │  │
│  │ State: st.session_state (in-memory)    │  │
│  └────────────────────────────────────────┘  │
└──────────┬──────────────────┬────────────────┘
           ▼                  ▼
    ┌────────────┐     ┌────────────────┐
    │ Gemini API │     │ Uploaded files │
    └────────────┘     │   (in memory)  │
                       └────────────────┘
```

### Why this architecture for the prototype
- Single Python file, deployable in minutes via Streamlit Cloud
- Zero infrastructure setup; perfect for an 8-hour hackathon
- Lets the team validate the product hypothesis before investing in infra

### What it cannot do
- Multi-user concurrency at scale
- Persistence across sessions (no database)
- Authentication and access control
- Audit logging or compliance retention
- Heavy-load resilience or autoscaling
- Real ATS integration

---

## 2. Target production architecture

Multi-tier, service-oriented, container-orchestrated. Designed for enterprise hiring teams (10–1000+ users), multi-tenant SaaS deployment, and regulated industries.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          USERS' BROWSERS                                   │
│                  (recruiters, hiring managers, admins)                     │
└─────────────────────────────────┬──────────────────────────────────────────┘
                                  │ HTTPS
                                  ▼
                       ┌──────────────────────┐
                       │   CDN + WAF          │
                       │ (CloudFront/Cloudflare)│
                       └──────────┬───────────┘
                                  ▼
                       ┌──────────────────────┐
                       │  API Gateway / ALB   │
                       │ (rate limit, routing)│
                       └──────────┬───────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              ▼                   ▼                    ▼
   ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐
   │  Next.js / React│  │  FastAPI Backend │  │  Auth Service      │
   │   Frontend SPA  │  │   (Stateless)    │  │ (OAuth2 / Keycloak)│
   └─────────────────┘  └────┬─────────────┘  └────────────────────┘
                             │
        ┌────────────────────┼──────────────────────────┐
        ▼                    ▼                          ▼
┌───────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│  PostgreSQL   │  │  Redis           │  │  Job Queue               │
│  (RDS / Cloud │  │  (cache, rate-   │  │  (Celery + Redis,        │
│   SQL)        │  │   limit, session)│  │   or AWS SQS / Pub/Sub)  │
└───────────────┘  └──────────────────┘  └────────────┬─────────────┘
                                                      │
                                                      ▼
                                          ┌──────────────────────┐
                                          │  LLM Worker Pool     │
                                          │  (autoscaling pods)  │
                                          └──────────┬───────────┘
                                                     │
                                       ┌─────────────┼─────────────┐
                                       ▼             ▼             ▼
                              ┌────────────────┐ ┌──────────┐ ┌──────────┐
                              │  Vertex AI /   │ │  S3/GCS  │ │Observability│
                              │  Gemini Pro    │ │ (uploads)│ │ (DD/Sentry) │
                              │  (no retention)│ │          │ │             │
                              └────────────────┘ └──────────┘ └────────────┘

                                  ─── Downstream Integrations ───
                                            │
                  ┌─────────────────────────┼─────────────────────────┐
                  ▼                         ▼                         ▼
          ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
          │  Greenhouse   │         │  Lever        │         │  Workday      │
          │   ATS API     │         │  ATS API      │         │  ATS API      │
          └───────────────┘         └───────────────┘         └───────────────┘
```

### Component-by-component breakdown

| Component | Responsibility | Technology | Why this choice |
|---|---|---|---|
| **CDN + WAF** | Static asset delivery, DDoS protection, geographic edge caching | CloudFront, Cloudflare | Sub-100ms global delivery; protects against L7 attacks |
| **API Gateway / Load Balancer** | TLS termination, rate limiting, routing | AWS ALB, Kong, AWS API Gateway | Centralised rate limit + routing without hardcoding into the app |
| **Frontend SPA** | UI rendering | Next.js + React + TypeScript | Modern component model; familiar to TA tooling vendors; server-side rendering for SEO of marketing pages |
| **Backend API** | Business logic, request orchestration | FastAPI (Python) | Async-first, auto-generated OpenAPI docs, type-safe; team can reuse Python code from prototype |
| **Auth Service** | Authentication, RBAC | Keycloak, Auth0, AWS Cognito | SSO/SAML support critical for enterprise customers |
| **Primary Database** | Persistent storage of users, kits, scorecards, audit logs | PostgreSQL (managed: RDS, Cloud SQL) | ACID guarantees; row-level security for multi-tenant isolation |
| **Cache** | LLM response cache, session, rate-limit counters | Redis (managed: ElastiCache, MemoryStore) | Sub-ms latency; reduces Gemini bill by caching repeat JD/CV pairs |
| **Object Storage** | Resume PDFs, JD documents, exports | S3 / GCS | Cheap, durable, lifecycle-managed; signed URLs for browser uploads |
| **Job Queue** | Async kit generation | Celery+Redis or AWS SQS / Pub/Sub | Decouples slow LLM calls from request/response; enables retries and DLQs |
| **LLM Worker Pool** | Executes generation and validation calls | Containerised Python workers in K8s or ECS | Independently scalable from the API; isolates cost spikes |
| **LLM Provider** | Question generation, validation | Gemini Pro via Vertex AI (or Anthropic Claude via Bedrock as fallback) | Vertex AI guarantees no data retention or training use — required for enterprise resume data |
| **Observability** | Metrics, logs, traces | Datadog, Prometheus+Grafana, Sentry | SLO tracking, alerting, on-call rotation |
| **ATS Integrations** | Push completed kits into customer ATSes | Webhooks + per-vendor adapters | Greenhouse, Lever, Workday are the top 3 — each gets a thin translation layer |

---

## 3. Data model (Postgres)

```sql
-- Tenants (organisations using the SaaS)
CREATE TABLE tenants (
  id              UUID PRIMARY KEY,
  name            TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Users
CREATE TABLE users (
  id              UUID PRIMARY KEY,
  tenant_id       UUID REFERENCES tenants(id),
  email           TEXT UNIQUE NOT NULL,
  role            TEXT CHECK (role IN ('admin', 'recruiter', 'interviewer')),
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Generated kits
CREATE TABLE kits (
  id              UUID PRIMARY KEY,
  tenant_id       UUID REFERENCES tenants(id),
  created_by      UUID REFERENCES users(id),
  role_title      TEXT,
  candidate_name  TEXT,
  jd_text         TEXT,
  resume_text     TEXT,
  kit_json        JSONB NOT NULL,  -- the full model output
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Scorecards (filled during the interview)
CREATE TABLE scorecards (
  id              UUID PRIMARY KEY,
  kit_id          UUID REFERENCES kits(id),
  filled_by       UUID REFERENCES users(id),
  scores_json     JSONB NOT NULL,  -- {criterion -> score, notes}
  weighted_total  NUMERIC,
  percentage      NUMERIC,
  completed_at    TIMESTAMPTZ
);

-- Audit log (immutable, append-only)
CREATE TABLE audit_log (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID,
  user_id         UUID,
  action          TEXT,         -- 'kit.created', 'scorecard.completed', etc.
  resource_id     UUID,
  metadata        JSONB,
  occurred_at     TIMESTAMPTZ DEFAULT now()
);

-- Row-Level Security for multi-tenant isolation
ALTER TABLE kits ENABLE ROW LEVEL SECURITY;
CREATE POLICY kits_tenant_isolation ON kits
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## 4. Pipelines

### 4.1 CI/CD pipeline (deployment automation)

Every push to `main` triggers an automated sequence: tests → build → image push → deploy → smoke test.

```
Developer pushes commit
        │
        ▼
   GitHub Actions
        │
        ├─▶ Lint (ruff)
        ├─▶ Type check (mypy)
        ├─▶ Unit tests (pytest)
        ├─▶ Integration tests (pytest + testcontainers)
        ├─▶ Security scan (Bandit, Trivy)
        │
        ▼
   Build Docker image
        │
        ▼
   Push to container registry (ECR / Artifact Registry)
        │
        ▼
   Trigger deploy (ArgoCD, GitHub Deploy, ECS rolling update)
        │
        ▼
   Run smoke tests against deployed instance
        │
        ▼
   Promote to production (canary → 100%)
        │
        ▼
   Notify Slack / PagerDuty
```

**Today's prototype already has the minimum viable version of this**: pushing to `main` automatically redeploys the Streamlit app via Streamlit Community Cloud. The production version adds CI gates, container builds, and progressive rollout.

### 4.2 Test pipeline (continuous quality)

```
Push / PR
   │
   ▼
GitHub Actions trigger
   │
   ▼
Set up Python environment
   │
   ▼
Install dependencies (cached)
   │
   ▼
Run pytest with coverage
   │
   ▼
Upload coverage report
   │
   ▼
PR comment with pass/fail + coverage delta
   │
   ▼
Block merge if any test fails
```

A working version of this is included in `.github/workflows/ci.yml`.

### 4.3 Data pipeline (request lifecycle)

This is the runtime pipeline a single user request flows through:

```
1. INPUT
   User uploads JD + resume in the SPA frontend
        │
        ▼
2. STORE
   Backend uploads raw files to S3, persists record in Postgres
        │
        ▼
3. ENQUEUE
   Backend places a generation job on the queue, returns a 202 with job_id
        │
        ▼
4. PARSE & VALIDATE (LLM Worker)
   Worker pulls job, extracts text, calls Gemini validation
        │
        ▼
5. GENERATE (LLM Worker)
   Worker calls Gemini generation, parses JSON, writes kit to Postgres
        │
        ▼
6. NOTIFY
   Worker publishes "kit.ready" event; frontend (via WebSocket) re-fetches
        │
        ▼
7. RENDER
   Frontend renders the kit; user scores during interview
        │
        ▼
8. EXPORT / INTEGRATE
   Backend writes scorecard back to Postgres
   Optionally pushes via webhook to customer's ATS
```

---

## 5. Non-functional requirements (production)

| NFR | Target | How it's met |
|---|---|---|
| **Availability** | 99.9% (8.76h downtime/year) | Multi-AZ Postgres, K8s with PodDisruptionBudgets, autoscaling |
| **Latency** | p95 < 8s end-to-end (LLM-bound) | Cached responses for repeat inputs; flash-lite for fast tier |
| **Throughput** | 1000 kits/hour per tenant peak | Horizontal scaling of LLM workers via queue depth |
| **Data residency** | Per-tenant region pinning | Region-isolated DB instances + storage |
| **Security** | SOC 2 Type II, GDPR | Encryption at rest + in transit; RBAC; audit log; PII scrubbing |
| **Cost** | Sub-$0.01 per kit | Cache hits, lite-tier defaults, autoscaling workers |
| **Observability** | 100% requests traced | OpenTelemetry instrumentation; structured logs; SLO dashboards |

---

## 6. Path from prototype to production (phased plan)

| Phase | Duration | What gets built |
|---|---|---|
| **Phase 0 — Now** | Done | Streamlit prototype, Streamlit Cloud deploy, CI tests |
| **Phase 1 — Backend split** | 2–3 weeks | FastAPI extracted from Streamlit; Postgres for kit persistence; auth via Auth0; Docker images; ECS deploy |
| **Phase 2 — Async generation** | 2 weeks | Job queue (SQS); LLM worker pool; WebSocket notifications |
| **Phase 3 — Frontend SPA** | 3 weeks | Next.js frontend replaces Streamlit UI |
| **Phase 4 — Multi-tenancy** | 2 weeks | Tenants table; RLS policies; SSO; per-tenant billing |
| **Phase 5 — Integrations** | 3 weeks per ATS | Greenhouse, Lever, Workday adapters with OAuth |
| **Phase 6 — Compliance & scale** | Ongoing | SOC 2 audit prep; data residency; cost optimization |

Total: ~3 months from prototype to first paying enterprise customer.

---

## 7. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM provider outage | Medium | High | Multi-provider fallback (Gemini → Claude via Bedrock) |
| LLM cost runaway | Medium | High | Per-tenant rate limits; cache hits; cost alerts |
| Resume PII leak | Low | Critical | Encryption + RBAC + audit log + Vertex AI no-retention |
| Vendor lock-in (Gemini) | Medium | Medium | Provider-agnostic abstraction at the SDK layer |
| Prompt regression | High | Medium | LLM eval suite in CI; canary deployment |
| Schema drift between model output and UI | Medium | Medium | JSON schema validation in the API layer; contract tests |

---

## 8. Summary

The prototype is an honest, working demonstration of the product hypothesis. The production architecture above is the natural evolution — each layer of the prototype maps to a service in the production design, and no layer is rebuilt from scratch. The current Streamlit app's `generate_kit()` and `validate_inputs()` functions become Celery worker tasks. The current `st.session_state` becomes Postgres rows. The current single-file deploy becomes a multi-service K8s deployment. The architectural ideas survive; what changes is scale, reliability, and security.
