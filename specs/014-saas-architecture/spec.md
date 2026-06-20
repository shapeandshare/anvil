# Feature Specification: SaaS Architecture — Three-Mode Operating Model

**Feature Branch**: `014-saas-architecture`
**Created**: 2026-06-19
**Status**: Draft

## User Scenarios & Testing

### User Story 1 — SaaS User Signs Up and Logs In via Google/GitHub/Email (Priority: P1)

A new user visits anvil.io and either signs in with Google/GitHub or creates a passwordless account via email magic link (Cognito Hosted UI). They are authenticated and redirected to the dashboard. Session management (tokens, refresh, MFA) is handled entirely by Cognito.

**Why this priority**: Multi-tenancy is the foundation of SaaS mode. Using Cognito means zero auth code to maintain — no password hashing, no token management, no session storage. Social login also eliminates registration friction.

**Independent Test**: Visit the SaaS deployment, click "Sign in with Google" (or use the equivalent test user in dev Cognito pool), complete the OAuth flow, and verify the user lands on the dashboard with their email displayed. Verify the session persists across page reloads.

**Acceptance Scenarios**:

1. **Given** a new user visits anvil.io, **When** they click "Sign in with Google" (or GitHub, or Apple), **Then** they are redirected to the provider's OAuth consent screen, and on approval they land on the anvil dashboard authenticated.
2. **Given** a new user visits anvil.io, **When** they choose email/password registration via Cognito Hosted UI, **Then** their account is created, they are redirected to the dashboard, and a JWT session is established.
3. **Given** a previously authenticated user returns, **When** their session is still valid (Cognito refresh token), **Then** they see the dashboard without re-authentication.
4. **Given** a user signs out, **When** they click logout, **Then** their Cognito session is revoked and they are redirected to the login page.

---

### User Story 2 — SaaS User Trains a Model and Watches Live Metrics (Priority: P1)

A logged-in SaaS user uploads a text corpus, configures hyperparameters, starts training, and watches the loss curve stream live in the browser via SSE. On completion, the model is available for download.

**Why this priority**: This is the core product experience in SaaS mode. It validates the entire pipeline: auth, data upload, compute dispatch, SSE streaming, and result storage.

**Independent Test**: Can be tested by uploading a small file, starting training with minimal hyperparameters (1 layer, 50 steps), and verifying the SSE stream shows step/loss updates and the completed model is downloadable.

**Acceptance Scenarios**:

1. **Given** a logged-in user with an uploaded corpus, **When** they configure training and click start, **Then** a training job is created (status=pending) and the browser opens an SSE connection.
2. **Given** a training job is running, **When** the compute pod completes each step, **Then** a metrics event is published to Redis, forwarded via SSE, and the browser updates the loss curve in real-time.
3. **Given** training completes, **When** the compute pod finishes, **Then** the final loss and generated samples appear in the browser and the model artifacts are stored in S3.
4. **Given** a completed training run, **When** the user clicks download, **Then** a signed S3 URL is returned and the model.safetensors file is downloaded.

---

### User Story 3 — SaaS User Sees Only Their Own Data (Priority: P1)

A user's corpora, datasets, experiments, and models are isolated from other users. No user can see or access another user's data through any API endpoint or the web UI.

**Why this priority**: Multi-tenant data isolation is non-negotiable for a SaaS product. Without this, no user will trust the platform with their data.

**Independent Test**: Create two separate user accounts (User A and User B). User A creates a corpus. Log in as User B — verify User B sees an empty corpus list. User B creates their own corpus and confirms they see only their own.

**Acceptance Scenarios**:

1. **Given** two registered users with data, **When** either user views their dashboard, **Then** they see only their own corpora, datasets, experiments, and models.
2. **Given** a user makes an API call, **When** the request is processed, **Then** all database queries are scoped by `org_id` (resolved from the user's membership) and filtered by team/role visibility.
3. **Given** one user's training job is running, **When** another user starts a job, **Then** both jobs run concurrently in separate compute pods with no data cross-contamination.

---

### User Story 4 — Local User Runs anvil Unchanged (Priority: P1)

A local user installs anvil via pip, runs `anvil serve`, and all existing functionality works exactly as before. No SaaS code is loaded, no cloud dependencies are required.

**Why this priority**: The local mode is the existing product. Breaking it for existing users is unacceptable. This must remain untouched.

**Independent Test**: Run `pip install anvil && anvil serve` and verify the web UI at localhost:8080 works with all existing features (corpus upload, training, SSE, model export).

**Acceptance Scenarios**:

1. **Given** a clean Python environment, **When** the user runs `pip install anvil`, **Then** no `boto3`, `redis-py`, or other cloud SDKs are installed.
2. **Given** a local install, **When** the user runs `anvil serve`, **Then** SQLite is used, MLflow runs as a subprocess, training runs in-process, and no cloud services are contacted.
3. **Given** a local install, **When** the user imports `anvil`, **Then** no code from `anvil/_saas/` is loaded.

---

### User Story 5 — SaaS Developer Runs Full Stack Locally (Priority: P2)

A developer clones the repo and runs `docker compose up` to start PostgreSQL, Redis, MinIO, MLflow, and the anvil web service with hot-reload. They can make changes to the code and see them reflected immediately.

**Why this priority**: Developer velocity directly impacts how fast SaaS features ship. Docker compose emulation is the fastest iteration loop.

**Independent Test**: Run `docker compose up`, verify the anvil web UI loads at localhost:8080, register a user, upload a corpus, and start a training job (compute runs in-process for dev speed). Verify SSE metrics stream in the browser.

**Acceptance Scenarios**:

1. **Given** the developer runs `docker compose up`, **When** all containers are healthy, **Then** the anvil web UI is available at localhost:8080.
2. **Given** the developer modifies Python code in the mounted volume, **When** the file is saved, **Then** the uvicorn process reloads and the change is reflected without container rebuild.
3. **Given** the docker compose stack is running, **When** the developer starts a training job, **Then** compute runs in-process (not Batch), writing results to the local MinIO and PostgreSQL containers.

---

### User Story 6 — SaaS Developer Deploys Branch to Dev AWS (Priority: P2)

A developer wants to test their changes against real AWS infrastructure. They run `cdk deploy` from `packages/infra/`, which builds the Docker image, pushes it to ECR, and updates the dev ECS service.

**Why this priority**: Some changes (Batch compute, Redis SSE, S3 storage) can only be fully validated against real AWS services.

**Independent Test**: Run `cdk deploy` from the infra package, verify the CloudFormation stack updates successfully, visit the dev CloudFront URL, and confirm the newly deployed version reflects the developer's changes.

**Acceptance Scenarios**:

1. **Given** a developer has made changes, **When** they run `cdk deploy`, **Then** the Docker image is built, tagged with the git commit hash, pushed to ECR, and the ECS service is updated.
2. **Given** a dev stack is deployed, **When** a user visits the dev CloudFront URL, **Then** they see the updated version of the application.
3. **Given** a dev stack with infrastructure changes, **When** `cdk diff` is run, **Then** it shows the planned changes before deployment.

---

### User Story 7 — User Deploys anvil SaaS into Their AWS Account with One Command (Priority: P1)

A user runs a single command to deploy the full anvil SaaS stack into their own AWS account. The command checks prerequisites, prompts for configuration, deploys all infrastructure, creates an admin account, and outputs the live URL. No manual AWS console steps, no Node.js, no CDK knowledge required.

**Why this priority**: Self-hosted deployability is the distribution model for the SaaS product. If deployment requires reading a 20-step manual, adoption will be near zero.

**Independent Test**: Run `anvil deploy init` in an AWS account with no prior anvil infrastructure. Verify the command completes without error and the user can access the web UI at the output URL. Then run `anvil deploy destroy` and verify all resources are cleaned up.

**Acceptance Scenarios**:

1. **Given** a user with AWS credentials configured, **When** they run `anvil deploy init`, **Then** they are interactively prompted for domain, region, and admin email, and the stack is deployed with no further manual steps.
2. **Given** the stack is deployed, **When** the command completes, **Then** it outputs the CloudFront URL and saves admin credentials to `~/.anvil/`.
3. **Given** a deployed stack, **When** the user visits the CloudFront URL, **Then** they see the login page and can log in with the admin credentials.
4. **Given** the stack is deployed, **When** the user runs `anvil deploy status`, **Then** they see the CloudFront URL, stack status, and current version.

---

### User Story 8 — User Destroys, Upgrades, or Reconfigures the SaaS Deploy (Priority: P2)

A user needs to tear down their anvil deployment, upgrade to a new version, or change configuration. Each operation is a single command with clear prompts and safe defaults.

**Why this priority**: Day-2 operations (destroy, upgrade, reconfigure) are what separate a hobby project from production software. Without clean destroy, users won't trust deploying at all.

**Independent Test**: Deploy a stack, reconfigure it (change domain), upgrade it (simulate a version bump), then destroy it. Verify each step completes and the final destroy removes all AWS resources including S3 buckets.

**Acceptance Scenarios**:

1. **Given** a deployed stack, **When** the user runs `anvil deploy destroy`, **Then** they are prompted for confirmation (skippable with `--force`), the S3 data buckets are emptied, and the CloudFormation stack is deleted.
2. **Given** a deployed stack and a newer version available, **When** the user runs `anvil deploy update`, **Then** the ECS services are updated with the new container image and any infrastructure changes are applied.
3. **Given** a deployed stack, **When** the user runs `anvil deploy config set --key domain --value new.example.com`, **Then** the CloudFormation stack is updated with the new domain.
4. **Given** a destroyed stack, **When** the user verifies in the AWS console, **Then** all stack resources (including S3 buckets containing data) are removed.

---

### User Story 9 — Local User Uses CLI to Push/Pull Data from SaaS (Priority: P3)

A local user has `anvil` installed and wants to upload a corpus from their local machine to the SaaS deployment. They run `anvil remote login`, then `anvil remote push corpus ./my-data/`. Later, they pull a trained model with `anvil remote pull model 42`.

**Why this priority**: The CLI bridge connects local workflows to cloud compute. Important for power users, but the web UI upload/download is the primary path.

**Independent Test**: Install anvil locally, run `anvil remote login` against a dev SaaS deployment, run `anvil remote push corpus ./test-data/`, verify the corpus appears in the web UI, run `anvil remote pull model 1`, and verify the file is downloaded locally.

**Acceptance Scenarios**:

1. **Given** a user with a local anvil install, **When** they run `anvil remote login https://dev.anvil.io`, **Then** they are prompted for credentials and a JWT pair is stored in `~/.anvil/credentials`.
2. **Given** an authenticated CLI session, **When** the user runs `anvil remote push corpus ./my-corpus/`, **Then** the files are uploaded to S3 and a corpus is created in the SaaS database.
3. **Given** an authenticated CLI session, **When** the user runs `anvil remote pull model 42`, **Then** a signed S3 URL is generated and the model artifacts are downloaded locally.

---

### Edge Cases

- What happens when a **compute pod** crashes mid-training (Spot reclaim, instance failure)? Training execution stops, but `job_events` in PostgreSQL preserves all progress (AD-4). The reconciler detects the dead Batch job (Batch status FAILED, or grace timeout with no new events) and appends a terminal `failed` event, moving the job out of `running`. For Spot-interrupted jobs, optional retry per FR-042. No job stays stuck `running` indefinitely (SC-012).
- What happens when a **web pod** (ECS replica) serving an SSE stream goes down? Training is unaffected (it runs in a separate Batch pod). The browser's `EventSource` fires `onerror` and auto-reconnects through the ALB to any healthy replica, sending `Last-Event-ID`; the new replica replays `job_events` since that sequence and resubscribes to Redis — no metrics gap (FR-045, AD-5).
- What happens when SSE cannot be established at all (corporate proxy strips `text/event-stream`)? The client auto-degrades to polling `GET /v1/training/{job_id}/events?since=` (FR-045a/b). Both paths read the same `job_events` source of truth, so the loss curve and terminal state are always reachable.
- What happens when the Redis pub/sub connection drops during training? The SSE stream pauses. Mitigation: the serving replica reconnects to Redis and resubscribes; any events missed during the gap are recovered from `job_events` on the next `Last-Event-ID` cycle (Redis is delivery-only, not the source of truth).
- What happens when two users register with the same email? Cognito enforces email uniqueness in the user pool. The second registration attempt receives an error from Cognito Hosted UI.
- What happens when a user's social login account (Google/GitHub) is deactivated? Cognito's federation means the user can no longer authenticate through that provider. They may have a separate email/password account or need to contact support.
- What happens if the user forgets their password? Cognito Hosted UI provides a built-in "Forgot password" flow with email verification code or magic link.
- What happens to a user's data when their account is deleted? The `users` table entry and all scoped data remain (orphaned) unless a cleanup process is triggered. Mitigation: admin can delete user via Cognito + cascade delete local data.
- What happens when S3 upload fails mid-transfer? The client retries with exponential backoff (handled by boto3). If all retries are exhausted, the upload endpoint returns an error status.
- What happens in local mode when `ANVIL_MODE=saas` is not set? Local mode runs the `anvil.api.app:app` entrypoint, which has no import path to `anvil/_saas/` — SaaS modules are never loaded and no cloud service is contacted (FR-011, FR-011a).
- What happens if the local entrypoint is launched with `ANVIL_MODE=saas` (or the SaaS entrypoint with mode unset/local)? The factory detects the entrypoint/mode mismatch and **fails fast** with a clear error — it does not reinterpret or silently switch (FR-011b).
- What happens if `ANVIL_MODE=saas` but a required cloud variable (e.g., `DATABASE_URL`) is missing? The SaaS factory fails fast at startup listing the missing variables, before wiring any implementation — it never falls back to SQLite/local (FR-011c).
- What happens when a user has no data yet? The dashboard shows empty states with guidance on how to upload data and start training.
- What happens if `anvil deploy` is run without AWS credentials? The command checks for credentials first and exits with a clear error message instructing the user to configure them.
- What happens if the CloudFormation stack creation fails partway through? The command outputs the specific failure, rolls back nothing (CloudFormation auto-rolls back), and the user can fix the issue and re-run.
- What happens if the deploy config file at `~/.anvil/` is corrupted? The deploy command validates the config on load and falls back to interactive prompting if validation fails.
- What happens if `anvil deploy destroy` is run on a stack that has already been destroyed? The command detects the stack does not exist and exits cleanly with a message.
- What happens if AWS service limits are hit (e.g., VPC limit)? The CloudFormation stack will roll back with a clear error indicating which limit was hit. The user can request a limit increase and re-run.
- What happens to a compute pod's DB access mid-job when its 15-minute IAM token expires? The SQLAlchemy token-provider callback regenerates a fresh token on the next connection from the pool (FR-045e); existing pooled connections through RDS Proxy remain valid. No job interruption.
- What happens if a secret is rotated (e.g., Redis auth token) while pods are running? New pods pick up the rotated value via the `secrets:` injection at launch; the rotation policy and a rolling restart propagate it to running services. DB access is unaffected (IAM auth, no static secret).

## Requirements

### Functional Requirements

- **FR-001**: System MUST use Amazon Cognito User Pools as the sole authentication provider for SaaS mode — no custom auth code (no password hashing, no JWT issuance, no token storage in the application).
- **FR-002**: Cognito MUST be configured with at least one social identity provider (Google or GitHub) plus email/password via Cognito Hosted UI.
- **FR-003**: System MUST scope all data access (corpora, datasets, experiments, models) by the Cognito `sub` (user UUID) derived from the authenticated JWT, mapped to a local integer `user_id` on first login.
- **FR-004**: System MUST support SSE-based live training metrics streaming via Redis pub/sub (SaaS mode) or in-process `asyncio.Queue` (local mode).
- **FR-005**: System MUST dispatch training jobs to AWS Batch (SaaS mode) or run in-process (local mode), selected at deploy time.
- **FR-006**: System MUST store application data in S3 (SaaS mode) or local filesystem (local mode), selected at deploy time.
- **FR-007**: System MUST track training job lifecycle (pending → running → completed/failed) in PostgreSQL (SaaS mode) or SQLite (local mode).
- **FR-008**: System MUST serve the web UI and API from the same origin in SaaS mode (no CORS needed).
- **FR-009**: System MUST support CloudFront CDN with cached static assets and proxied API requests.
- **FR-010**: System MUST deploy infrastructure via AWS CDK (`packages/infra/`) for SaaS mode.
- **FR-011**: System MUST NOT load any SaaS-only code (`boto3`, `redis-py`) in local mode. The local entrypoint module (`anvil/api/app.py`) MUST have no static import path to `anvil/_saas/`, so import isolation is structurally guaranteed (not merely runtime-checked).
- **FR-011a**: Mode selection MUST use two layers: (1) the **entrypoint module** is the primary switch — local launches `anvil.api.app:app`, SaaS launches `anvil._saas.app:app`; (2) the `ANVIL_MODE` env var is an explicit guard and config selector. Mode MUST be explicit and is NEVER auto-detected.
- **FR-011b**: Each app factory MUST validate `ANVIL_MODE` matches its module on startup and **fail fast** on mismatch (e.g., local entrypoint started with `ANVIL_MODE=saas`, or vice versa). No silent reinterpretation.
- **FR-011c**: When `ANVIL_MODE=saas`, the SaaS factory MUST validate that all required cloud configuration (`DATABASE_URL`, `REDIS_URL`, `S3_DATA_BUCKET`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `MLFLOW_TRACKING_URI`) is present BEFORE wiring implementations, and fail fast listing any missing variables. It MUST NEVER silently fall back to local implementations.
- **FR-012**: System MUST support a docker compose development environment that emulates SaaS infrastructure (PostgreSQL, Redis, MinIO, MLflow) for local development.
- **FR-013**: System MUST support three developer iteration modes: docker compose, local code against dev AWS, and cdk deploy to dev environment.
- **FR-014**: CLI MUST support remote commands: `login`, `logout`, `push <corpus|dataset> <path>`, `pull <model|experiment> <id>`, `ls <corpora|datasets|experiments>`.
- **FR-015**: SaaS mode MUST support concurrent training jobs across multiple users and multiple jobs per user.
- **FR-016**: The four abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`) MUST be defined in `anvil/storage/` with local implementations in `anvil/storage/` and SaaS implementations in `anvil/_saas/implementations/`.
- **FR-017**: MLflow in SaaS mode MUST use the same PostgreSQL server as the application (separate `anvil_mlflow` database) with artifacts on S3.
- **FR-018**: Cognito Hosted UI MUST handle user-facing login, registration, password reset, and MFA enrollment. The anvil application does not implement any of these flows.
- **FR-019**: Authentication MUST use the **app-managed OIDC/JWT** pattern (NOT ALB-managed auth). The FastAPI backend receives the Cognito bearer token directly and validates it against Cognito's JWKS endpoint via `aws-jwt-verify` in a middleware dependency. ALB does NOT perform `authenticate-cognito`. This single pattern works identically across CloudFront, ALB, direct API access, and CLI.
- **FR-020**: SSE endpoints MUST authenticate via a short-lived signed token passed as a query parameter (since `EventSource` cannot set custom headers). The server issues this token from a validated session; it is single-use or short-TTL and scoped to the specific job stream.
- **FR-021**: CLI authentication MUST use Cognito's OAuth2 device authorization grant (RFC 8628) — the CLI opens a browser for the user to authenticate, then polls the token endpoint. No hardcoded API keys, no custom token endpoints.
- **FR-021a**: Native Cognito email/password users MUST work out of the box with zero post-deploy configuration. Social login (Google, GitHub) MUST be optional and configured AFTER deploy via `anvil deploy config set-idp` once the CloudFront/custom domain (and therefore the OAuth callback URL) is known. The customer brings their own OAuth client ID and secret (BYO identity provider).
- **FR-022**: The anvil application's Cognito User Pool MUST be deployed via the CDK stack as a first-class resource — no separate Cognito setup outside of `anvil deploy`.
- **FR-023**: A local `users` table in PostgreSQL MUST map Cognito `sub` (UUID) to a local integer `user_id` for efficient FK relationships. The mapping is created on first login via a Cognito post-authentication Lambda trigger or a first-request middleware handler.
- **FR-024**: A single `anvil deploy init` command MUST bootstrap the full SaaS stack — including VPC, RDS, Redis, ECS, MLflow, S3, Batch, CloudFront, Route53, WAF, and Cognito — into the user's AWS account with interactive prompting for required configuration.
- **FR-025**: A single `anvil deploy destroy` command MUST tear down the entire stack, including emptying and deleting S3 data buckets that would otherwise block CloudFormation stack deletion.
- **FR-026**: A single `anvil deploy update` command MUST upgrade the deployment to the latest available version by updating container images and applying any infrastructure changes.
- **FR-027**: A single `anvil deploy config set/get/list` command MUST allow changing deployment configuration (domain, region, instance sizing, etc.) without a full re-deploy where possible.
- **FR-028**: The deploy command MUST work with only Python + AWS credentials — no Node.js, no CDK CLI, no manual bootstrapping steps required on the user's machine.
- **FR-029**: CloudFormation templates MUST be pre-synthesized from the CDK source during CI and bundled directly in the pip package so the Python CLI can deploy them via `boto3`.
- **FR-030**: The deploy command MUST create an initial admin user via Cognito, a default Organization, and a Membership making that admin the org `owner`; then output the login URL after successful stack creation.
- **FR-031**: The deploy destroy command MUST require user confirmation (with `--force` to skip) and MUST handle the case where the stack has never been deployed (no-op).
- **FR-032**: The deploy system MUST support multiple independent environments (dev, staging, prod) in the same AWS account using different stack names.
- **FR-033**: The deploy system MUST save its configuration (stack name, region, domain, etc.) to `~/.anvil/` so subsequent commands (`destroy`, `update`, `config`, `status`) can find it without re-prompting.

#### RBAC & Multi-Tenancy

- **FR-034**: The system MUST implement a full RBAC hierarchy: `Organization` (top-level isolation/billing boundary) → `Team` (group within an org) → `User` (member of org/teams). A user belongs to exactly one organization but MAY belong to multiple teams within it.
- **FR-035**: The system MUST support roles `owner`, `admin`, `member`, `viewer` assigned at the organization level and optionally overridden at the team level. Role determines permitted actions (create/read/update/delete/manage-members).
- **FR-036**: Every resource (corpus, dataset, training job, model) MUST be owned by `org_id` (required), `team_id` (optional), and `created_by` user_id. All repository queries MUST be scoped by `org_id` and filtered by team/role visibility.
- **FR-037**: Authorization MUST be enforced at two layers: a FastAPI middleware that resolves the caller's org/team/role from the validated JWT, and a service-layer permission guard that checks the action against the resource owner. No DB query may return cross-org data.
- **FR-038**: An organization owner/admin MUST be able to invite users, create teams, assign roles, and remove members via API. The first admin (created at deploy) is the org owner.

#### Compute (CPU / GPU / Multi-Node)

- **FR-039**: The compute layer MUST support four job shapes: `cpu` (CPU-only), `gpu` (single GPU), `multi-gpu` (N GPUs on one node), and `multi-node` (M nodes × N GPUs, gang-scheduled). SaaS mode dispatches to AWS Batch on EC2; local mode runs in-process.
- **FR-040**: The `JobQueue.submit()` / `ComputeBackend.run()` abstraction MUST express compute requirements as a structured `ResourceSpec` (`{node_count, gpus_per_node, vcpus, memory, instance_class}`) so multi-node jobs are first-class, not a special case.
- **FR-041**: Multi-node training jobs MUST use AWS Batch multi-node parallel job definitions with gang scheduling; placement-group locality and EFA networking MUST be configurable for high-bandwidth inter-node communication.
- **FR-042**: The Batch compute environment MUST support EC2 Spot for cost reduction with graceful handling of Spot interruption (job retry / checkpoint resume where supported).

#### Job State Consistency

- **FR-043**: PostgreSQL MUST be the single source of truth for job lifecycle. Job state transitions MUST be recorded in an append-only `job_events` table with idempotent keys `(job_id, sequence)`. Redis is delivery-only and MUST NOT be treated as authoritative.
- **FR-044**: Compute pods MUST write artifacts to deterministic S3 keys and emit idempotent lifecycle events. A reconciler MUST periodically compare Batch job state, DB state, MLflow run state, and expected S3 artifacts, and repair any job stuck in a non-terminal state beyond a configurable grace period.
- **FR-045**: SSE streaming MUST support `Last-Event-ID` replay backed by `job_events`, so a client reconnecting to any replica resumes the stream without gaps.
- **FR-045a**: The system MUST expose a metrics polling endpoint `GET /v1/training/{job_id}/events?since={sequence}` that returns the `job_events` backlog (status + metrics) after a given sequence. This is the durable fallback used when SSE cannot be established (proxies blocking `text/event-stream`) or for clients that prefer polling. It reads the same `job_events` source of truth as SSE.
- **FR-045b**: The browser client MUST auto-degrade: attempt SSE first; on repeated connection failure (EventSource `onerror` without open), fall back to polling `GET /v1/training/{job_id}/events?since=` on a fixed interval. Both paths render identically because both read `job_events`. The job's terminal state is always reachable via polling even if SSE never connects.

#### Training Job Orchestration

- **FR-045g**: Training orchestration MUST follow a three-plane model: **control plane** (anvil-web admits, configures, submits, and observes — never tracks progress by polling the pod), **scheduler** (AWS Batch owns queueing, compute-environment scaling, gang-scheduling, and retries), **executor** (the compute pod runs `anvil/core` and emits events). Planes communicate only through durable records (`job_events`, S3), never direct mutation.
- **FR-045h**: Job configuration MUST be split into four concerns: hyperparameters (`TrainingJob.config`), `ResourceSpec` (compute), data binding (`corpus_id`/`dataset_id`), and job policy (timeout/retry/priority). Hyperparameters and data references MUST be delivered to the pod via an S3 config object (`jobs/{job_id}/config.json`), not env vars; the pod receives only small pointers (`JOB_ID`, `CONFIG_S3_KEY`) as env.
- **FR-045i**: Batch job definitions MUST be pre-registered per compute shape (`anvil-cpu`, `anvil-gpu`, `anvil-multigpu`, `anvil-multinode`) and parameterized per job via container overrides from `ResourceSpec` — not dynamically created per submission.
- **FR-045j** — Quota: anvil-web MUST enforce per-org quotas (max concurrent jobs, max total GPUs) before submitting to Batch; jobs exceeding quota are rejected or queued with a clear reason. Batch fair-share scheduling provides the second layer.
- **FR-045k** — Fair-share scheduling: The Batch job queue MUST use a fair-share scheduling policy keyed on `org_id` so no organization can starve others. No user-facing priority tiers in v1.
- **FR-045l** — Retry policy: Infrastructure failures (Spot interruption, instance failure) MUST auto-retry (Batch `attempts` = 2–3) and resume from the last checkpoint; user/config errors (invalid hyperparameters, missing data) MUST fail immediately without retry. The reconciler is the backstop for jobs that escape both paths.
- **FR-045m** — Checkpointing: Long-running and multi-node jobs MUST write periodic checkpoints to S3 (deterministic keys). On Spot reclaim + retry, the worker MUST resume from the last checkpoint rather than restarting from scratch.
- **FR-045n** — Cancellation: A user with permission MUST be able to cancel a pending or running job; cancellation terminates the Batch job and records a `cancelled` `JobEvent`. Cancellation is idempotent.
- **FR-045o** — Timeout: Each job MUST have a maximum duration (Batch job timeout + reconciler grace); exceeding it transitions the job to `failed` with a timeout reason.
- **FR-045p** — Multi-node coordination: For multi-node parallel jobs, only the main node (rank 0) MUST emit authoritative `JobEvent`s and write the final artifact; worker nodes participate in training (NCCL/EFA) but do not write job state, preventing duplicate/conflicting events.

#### Secrets Management & Credential Flow

- **FR-045c**: Compute pods and the web tier MUST authenticate to PostgreSQL via **RDS Proxy + IAM database authentication** (`rds-db:connect`). Static database passwords MUST NOT flow to pods. Each connection uses a short-lived (≤15 min) IAM-derived auth token generated from the task's IAM role. The real DB master password is held only by RDS Proxy (read from Secrets Manager) and is never injected into any application container.
- **FR-045d**: Secrets that cannot use IAM auth (Redis auth token, SSE signing secret, social OAuth client secrets) MUST be stored in Secrets Manager and delivered to containers via the ECS/Batch task `secrets:` mechanism (execution role pulls and injects as env at launch). Secrets MUST NEVER be baked into images, written to logs, or passed as plaintext container overrides.
- **FR-045e**: Long-lived SQLAlchemy connection pools (web tier, MLflow) MUST use a token-provider callback that regenerates the IAM auth token on new connections, so pools survive beyond the 15-minute token lifetime without manual credential rotation.
- **FR-045f**: IAM permissions MUST be least-privilege and split: the **execution role** grants ECR pull, CloudWatch Logs, and scoped Secrets Manager reads; the **job/task role** grants `rds-db:connect`, S3 read/write on the org-scoped prefix, and Redis connectivity. No role grants broader access than its function requires.

#### Usage Metering & Billback

- **FR-046**: On every job completion, the system MUST write a `usage_record` capturing GPU-seconds and instance-hours (derived from job runtime × resolved instance type), attributed to `org_id`, `team_id`, `user_id`, and `job_id`. Records MUST derive from `job_events` (the authoritative lifecycle), not a separate write path.
- **FR-047**: Batch jobs MUST be tagged with AWS Cost Allocation Tags (`org_id`, `team_id`, `user_id`) so internal `usage_records` can be cross-checked against AWS Cost Explorer.
- **FR-048**: The system MUST expose a usage query API returning aggregated usage per organization, team, and user over a time range, for billback reporting.

#### Agentic Validation

- **FR-049**: The system MUST provide an `anvil deploy verify` command with three layers: `--layer infra` (AWS control-plane checks via boto3), `--layer api` (headless end-to-end API canary), and `--layer browser` (Playwright smoke test for Hosted UI/SSE). Each layer exits non-zero on failure and reports the failing check.
- **FR-050**: The API canary MUST programmatically create a native Cognito test user, exercise the full pipeline (auth → org/team → upload → train → SSE → artifact → usage record → RBAC negative test), and clean up afterward — with no human or browser interaction.

#### Migrations

- **FR-051**: Alembic migrations for both `anvil_app` and `anvil_mlflow` MUST run as a single pre-deploy step (one-off ECS task or CFN custom resource) that completes BEFORE the web service rolls out. The web service MUST perform only a schema-compatibility check on startup and fail fast on mismatch.

### Key Entities

- **Organization**: The top-level tenant and billing boundary. Owns all resources. Has one owner, many admins/members.
- **Team**: A group of users within an organization. Resources MAY be scoped to a team. A user may belong to multiple teams.
- **Role**: One of `owner`, `admin`, `member`, `viewer`. Assigned at org level, optionally overridden per team. Governs permitted actions.
- **User**: An authenticated account managed by Cognito, identified by Cognito `sub` (UUID). Local `users` table maps `cognito_sub` → integer `user_id`. Belongs to one organization, zero or more teams.
- **Membership**: The association of a User to an Organization (with role) and to Teams (with optional role override).
- **Corpus**: A collection of text files. Owned by `org_id` (+ optional `team_id` + `created_by`). Scoped by org/team/role.
- **Dataset**: A curated subset of a corpus with chunking configuration. Owned by `org_id` (+ optional `team_id` + `created_by`).
- **TrainingJob**: A training run with hyperparameters, `ResourceSpec`, status, and artifact references. Owned by `org_id`/`team_id`/`created_by`. In SaaS mode backed by AWS Batch; in local mode runs in-process.
- **JobEvent**: An append-only lifecycle event `(job_id, sequence, event_type, payload, ts)`. The authoritative record of job state transitions.
- **Model**: A trained model artifact (safetensors + config). Owned by `org_id`/`team_id`/`created_by`. Stored in S3 (SaaS) or filesystem (local), registered in MLflow.
- **Experiment**: An MLflow experiment tracking runs and metrics. In SaaS mode stored in `anvil_mlflow`, tagged with `org_id`/`user_id`.
- **UsageRecord**: A billback record `(org_id, team_id, user_id, job_id, gpu_seconds, instance_hours, instance_type, started_at, ended_at)`. Derived from `job_events`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A new user can register, log in, upload data, start training, and see live metrics — all from the browser — within 5 minutes of first visiting anvil.io.
- **SC-002**: Training metrics appear in the browser within 1 second of the compute pod reporting them (SSE latency via Redis pub/sub).
- **SC-003**: Users can run 10+ concurrent training jobs across different accounts without interference or performance degradation.
- **SC-004**: A developer can go from `git clone` to running the full SaaS stack locally (docker compose) in under 3 minutes.
- **SC-005**: The SaaS deployment maintains 99.5% availability for the web UI and API (measured monthly).
- **SC-006**: Local mode (`pip install anvil && anvil serve`) has zero SaaS dependencies and no behavioral changes from the pre-SaaS version.
- **SC-007**: All existing local-mode tests pass without modification after the abstraction layer is introduced.
- **SC-008**: A user can deploy a complete SaaS instance into a fresh AWS account by running a single command (`anvil deploy init`) with no manual AWS console steps, no Node.js installation, and no CDK knowledge.
- **SC-009**: A complete deploy cycle (init → verify → destroy) takes under 30 minutes of wall-clock time.
- **SC-010**: The deploy CLI fits in the same `anvil` pip package as an optional `[aws]` extra — no separate package for deployment.
- **SC-011**: `anvil deploy verify --layer api` validates the entire pipeline (auth, RBAC, upload, training, SSE, artifacts, usage metering) programmatically with zero manual steps, and exits non-zero on any component failure identifying the failing step.
- **SC-012**: A training job that loses its compute pod mid-run is detected and reconciled to a terminal state (`failed` or recovered) within the configured grace period — no job remains stuck in `running` indefinitely.
- **SC-013**: Every completed training job produces exactly one `usage_record` attributing GPU-seconds/instance-hours to the correct `org_id`, `team_id`, and `user_id`.
- **SC-014**: A user in one organization can never read, list, or mutate any resource owned by another organization, verified by automated cross-org RBAC negative tests.
- **SC-015**: Multi-node distributed training jobs (M nodes × N GPUs) gang-schedule and complete; the JobQueue/ComputeBackend abstraction expresses all four compute shapes (cpu, gpu, multi-gpu, multi-node).

## Assumptions

- The SaaS deployment runs entirely within AWS (Route53, CloudFront, ECS Fargate, RDS PostgreSQL, ElastiCache Redis, S3, AWS Batch). Cloudflare is used only if implementation constraints demand it.
- The same `anvil` Python package serves both local and SaaS modes. The mode is selected by the `ANVIL_MODE` environment variable at deploy time and is never auto-detected.
- Local mode uses SQLite, in-process MLflow, local filesystem, and in-process compute — unchanged from current behavior.
- SaaS mode uses RDS PostgreSQL, dedicated ECS MLflow service, S3 object store, ElastiCache Redis, and AWS Batch.
- MLflow shares the same PostgreSQL server as the application but uses a separate database (`anvil_mlflow`).
- AWS Batch uses EC2 compute environments (CPU + GPU instance families) with Spot for cost reduction. Multi-node parallel job definitions provide gang-scheduled distributed training. Fargate is used only for small CPU jobs where GPU is not required. (See AD-1.)
- The CDK stack is the single source of truth for SaaS infrastructure. Manual console changes will be overwritten.
- Secrets Manager stores credentials, but **DB credentials never flow to compute pods**: pods authenticate to PostgreSQL via RDS Proxy + IAM auth using short-lived role-derived tokens (FR-045c). The RDS master password is read only by RDS Proxy. Secrets that flow to containers (Redis auth token, SSE signing secret, social OAuth secrets) are injected via the ECS/Batch `secrets:` mechanism, never baked into images or logged (FR-045d). Cognito issues and signs user JWTs — the app validates via JWKS and holds no JWT signing secret.
- The CDK stack lives in `packages/infra/` using TypeScript.
- No changes to `anvil/core/` — the training engine remains zero-dependency.
- Existing compute backends (`local-stdlib`, `local-torch`, `modal`) continue to work in local mode.
- SaaS authentication is handled by Cognito — the application never manages passwords, sessions, or tokens. This removes an entire class of security vulnerabilities and audit requirements.
- Social login (Google, GitHub, Apple) is the primary auth path. Email/password via Cognito Hosted UI is the fallback.
- The Cognito User Pool is created by the CDK stack. The app client, domain name (e.g., `auth.anvil.io`), and identity providers are configured in CDK.
- Authentication is app-managed (AD-2): the FastAPI app validates Cognito JWTs in middleware via `aws-jwt-verify`. The ALB does NOT perform `authenticate-cognito`. Unauthenticated browser requests are redirected to Cognito Hosted UI by the application, not the ALB.
- SSE authentication: since EventSource cannot set custom headers, the SSE endpoint reads a short-lived signed token from a query parameter, issued by the app from a validated session (FR-020).
- CLI authentication uses Cognito's OAuth2 device authorization grant flow: the CLI opens a browser window for the user to sign in, then exchanges the authorization code for tokens.
- A local `users` table exists in PostgreSQL to map Cognito `sub` (UUID) to a local integer `user_id`. This is populated on first login via a Cognito post-authentication trigger (Lambda) or an application middleware that checks and creates the mapping on each authenticated request.
- The target SaaS domain is `anvil.io` (placeholder — configurable per environment).
- No WebSocket support is needed — SSE is sufficient for the current real-time requirements.
- Existing pre-existing LSP errors in JS files are not in scope for this feature.
- The CDK app in `packages/infra/` is the canonical infrastructure definition used by the development team to iterate on the stack. CloudFormation templates are pre-synthesized from it during CI and bundled in the pip package.
- The `anvil deploy` CLI uses those pre-synthesized CloudFormation templates via `boto3` — it does not run CDK or Node.js on the user's machine.
- The deploy configuration is stored at `~/.anvil/deploy-config.json` and contains stack name, region, domain, admin email, and version pin.
- S3 buckets are emptied before CloudFormation stack deletion during `destroy`. Users are warned about data loss.
- The deploy command requires AWS credentials with sufficient permissions (AdministratorAccess or a scoped policy). It does not create or manage IAM users/roles itself.
- A single SaaS container image (web + compute worker, selected by entrypoint per AD-10) is published to a public registry (e.g., GitHub Container Registry) so `deploy up` can reference it by digest without an ECR push step. ECR is used only for custom/dev images. (Split into a dedicated compute image only if the AD-10 reversal trigger is hit.)
- Route53 zone must already exist in the account or be delegated. The deploy command can create Route53 records in an existing zone but cannot create a new public zone or transfer domain registration.

## Non-Goals (v1)

Explicit scope boundaries. These are deliberate exclusions, not oversights.

- **NG-1 — No customer/custom training containers.** Training jobs run anvil's own fixed engine (`anvil/core`) inside the single SaaS image (AD-10). Users supply hyperparameters, data, and a `ResourceSpec` — not custom Docker images or arbitrary training code. This keeps AD-10 (single fixed image) intact and avoids the large security surface of arbitrary code execution (container escape, exfiltration, per-org registries, cross-tenant sandboxing). **Rationale**: anvil is a from-scratch LLM training platform built around its own RoPE/SwiGLU/RMSNorm engine, not a general bring-your-own-container ML platform.
- **NG-2 — No BYO dependency injection.** Users cannot add arbitrary pip packages or custom layers to the training runtime in v1. The runtime is the fixed anvil image.
- **NG-3 — No custom-container support in hosted multi-tenant mode.** (Follows from NG-1; would require Firecracker/gVisor sandboxing, image scanning/signing, and per-org ECR — out of scope.)

**Clean extension path (post-v1, if ever needed)**: because the compute worker is isolated in `anvil/_saas/compute_worker.py` and dispatch goes through the `JobQueue`/`ComputeBackend` abstraction with a structured `ResourceSpec`, adding a "custom image" job shape later is additive — it would introduce a per-job image reference and the corresponding security controls (scanning, scoped IAM, hardened egress, sandboxed runtime) without disturbing the fixed-engine path.

## Deploy CLI Architecture

### Commands

```
anvil deploy init         # Interactive: prompts for config, deploys stack, creates admin user
anvil deploy up           # Non-interactive: deploys from existing config or env vars
anvil deploy destroy      # Tears down stack (requires confirmation, --force to skip)
anvil deploy update       # Upgrades to latest version (new image tag + infra changes)
anvil deploy status       # Shows stack status, CloudFront URL, version
anvil deploy config set <key> <value>   # Update a config value
anvil deploy config get <key>           # Read a config value
anvil deploy config list                # Show all config
```

### Configuration

Stored at `~/.anvil/deploy-config.json`:

```json
{
  "stack_name": "anvil-prod",
  "region": "us-east-1",
  "domain": "models.example.com",
  "route53_zone_id": "Z1234567890",
  "cognito_domain": "auth.models.example.com",
  "admin_email": "admin@example.com",
  "social_providers": ["Google", "GitHub"],
  "container_image_tag": "v1.2.3",
  "instance_size": "medium",
  "deployed_at": "2026-06-19T00:00:00Z"
}
```

### Deployment Flow

```
anvil deploy init
│
├── 1. Check prerequisites
│     ├── AWS credentials available (boto3.Session)
│     ├── Region set (env, config, or prompt)
│     └── Domain + Route53 zone (prompt or config)
│
├── 2. Gather configuration (interactive prompts)
│     ├── Stack name [default: anvil-{env}]
│     ├── Domain name (e.g., models.example.com)
│     ├── Route53 zone ID (auto-detected or manual)
│     ├── Social login providers [Google/GitHub/Apple]
│     ├── Admin email for initial user
│     └── Instance size [small/medium/large]
│
├── 3. Deploy CloudFormation stack
│     ├── Cognito User Pool + app client + domain + IdP config
│     ├── ALB + CloudFront + WAF + Route53 records
│     ├── ECS services (anvil-web + mlflow)
│     ├── RDS PostgreSQL (anvil_app + anvil_mlflow)
│     ├── ElastiCache Redis
│     ├── S3 buckets (data + mlflow artifacts)
│     ├── AWS Batch compute environment + job queue
│     └── Secrets Manager entries
│
├── 4. Post-deployment setup
│     ├── Run migration task (Alembic, pre-rollout — AD-6)
│     ├── Create Cognito user for admin
│     ├── Create default Organization
│     ├── Insert local `users` mapping for admin
│     └── Create Membership(admin, org, role=owner) — RBAC bootstrap (AD-8)
│
└── 5. Output
      ├── CloudFront URL: https://d123.cloudfront.net
      ├── Custom domain: https://models.example.com
      ├── Auth domain: https://auth.models.example.com
      ├── Admin email: admin@example.com
      └── Credentials saved to: ~/.anvil/admin-credentials

### Destroy Flow

```
anvil deploy destroy [--force]
│
├── 1. Load config from ~/.anvil/deploy-config.json
├── 2. Confirm (unless --force)
│     └── "WARNING: This will destroy ALL data. Type the stack name to confirm:"
├── 3. Empty S3 data buckets
│     ├── anvil-data-{env}: list + delete all objects
│     └── anvil-ml-{env}: list + delete all objects
├── 4. Delete CloudFormation stack
│     └── client.delete_stack(StackName=...)
├── 5. Clean up
│     └── Remove ~/.anvil/admin-credentials (stale)
└── 6. Output: "Stack anvil-prod deleted successfully"
```

### Upgrade Flow

```
anvil deploy update
│
├── 1. Load config from ~/.anvil/deploy-config.json
├── 2. Check for latest available version
│     └── Query GHCR for latest tag, or use --version flag
├── 3. Update config with new image tag
├── 4. Update CloudFormation stack with new parameters
│     └── client.update_stack(...)
├── 5. Wait for UPDATE_COMPLETE
└── 6. Output: "Updated to v1.2.3"
```

---

## Architecture Decisions (Post-Review)

These decisions resolve critical issues raised in the pre-implementation architecture review (Oracle, ADR-030 review pass). Each is binding on the implementation.

### AD-1: Compute Substrate — AWS Batch on EC2 (CPU + GPU + Multi-Node)

**Decision**: AWS Batch with EC2 compute environments. Supports CPU jobs (Fargate or EC2), single-GPU and multi-GPU-per-node (g4dn/g5/p4 instances), and multi-node distributed training via Batch **multi-node parallel jobs**. Boring, managed, reliable — no Kubernetes.

**Rationale**: Fargate has NO GPU support (review CRITICAL finding). EKS+Kubeflow is not "boring." SageMaker is opinionated and pricey. AWS Batch on EC2 natively supports gang-scheduled multi-node parallel jobs, GPU instance types, and Spot. This is the simplest substrate covering all four compute shapes.

**Compute shapes the JobQueue/ComputeBackend MUST express**:
- `cpu` — CPU-only job (small stdlib engine training)
- `gpu` — single GPU
- `multi-gpu` — N GPUs on one node
- `multi-node` — M nodes × N GPUs (Batch multi-node parallel job, gang-scheduled)

**Gotchas to handle**: placement groups for multi-node locality, EFA networking for inter-node bandwidth (p4/p5), gang scheduling (Batch handles via multi-node job definition `numNodes`), Spot interruption handling for long jobs.

### AD-2: Authentication — App-Managed OIDC/JWT

**Decision**: FastAPI validates Cognito JWTs directly via `aws-jwt-verify`. ALB does NOT do `authenticate-cognito`. (See FR-019.)

**Rationale**: Review CRITICAL finding — ALB-managed and app-managed auth are different patterns and must not be mixed. App-managed works identically across CloudFront, ALB, direct API, and CLI, and is the only pattern compatible with bearer-token CLI access.

### AD-3: Social Login — Native Default, BYO Social

**Decision**: Email/password Cognito users work out of the box. Social login is post-deploy, optional, BYO OAuth credentials. (See FR-021a.)

**Rationale**: Review HIGH finding — per-customer Cognito pools need per-customer OAuth apps with callback URLs not known until after deploy. Making social login post-deploy preserves the true one-command install.

### AD-4: Job State Consistency — Postgres Source of Truth + Append-Only Events

**Decision**: PostgreSQL is the single source of truth for job lifecycle. An append-only `job_events` table records idempotent events keyed by `(job_id, sequence)`. Redis is **delivery-only** (transient SSE fan-out), never the source of truth. A reconciler compares Batch job state, DB state, MLflow run state, and expected S3 artifacts to repair stuck/terminal jobs.

**Rationale**: Review CRITICAL finding — a compute pod writing to Postgres + S3 + MLflow + Redis with no transaction boundary creates split-brain state on crash. Deterministic S3 keys + idempotent event keys + a reconciler make the system self-healing.

### AD-5: SSE — Serving Replica Subscribes Per-Connection + Replay

**Decision**: A browser's `EventSource` connection pins to one ECS replica (long-lived HTTP). That replica subscribes to the Redis channel for that specific job. SSE supports `Last-Event-ID` replay backed by the `job_events` table so a reconnect to a different replica resumes without gaps. CloudFront/ALB idle timeouts are tuned and a 30s heartbeat keeps connections alive.

**Rationale**: Review HIGH finding — raw Redis pub/sub drops events when no subscriber is attached (reconnect/replica restart). DB-backed replay makes streaming correct, not just live.

### AD-6: Migrations — Single Pre-Deploy Step

**Decision**: Alembic migrations run as a single one-off ECS task (or CFN custom resource) BEFORE the web service rolls out. The web service does only a schema-compatibility check on startup and fails fast on mismatch. This applies to both `anvil_app` and `anvil_mlflow` schemas.

**Rationale**: Review HIGH finding — running Alembic on startup with 2+ replicas is a race. Pre-deploy migration with rollout gating eliminates it.

### AD-7: Deploy Asset Model — Immutable Image Digests, No CDK Asset References

**Decision**: Pre-synthesized CloudFormation templates MUST be asset-free. Container images are referenced by **immutable digest** (`@sha256:...`) from a public registry (GHCR or public ECR). Lambda code (post-auth trigger, reconciler) is inlined or referenced from a versioned S3 object the deploy CLI publishes into the customer account before stack creation. No dependency on `cdk bootstrap` / CDKToolkit stack in the customer account.

**Rationale**: Review HIGH finding — standard CDK synth output assumes bootstrap state and asset buckets. Asset-free templates + digest-pinned images make the boto3 deploy truly portable.

### AD-8: Multi-Tenancy — Full RBAC (Organization → Team → User → Role)

**Decision**: First-class multi-tenancy from v1. `Organization` is the top-level billing/isolation boundary. `Team` groups users within an org. `Role` (owner/admin/member/viewer) governs permissions. All resources (corpus, dataset, training job, model) are owned by `org_id` (+ optional `team_id` + `created_by` user_id). Authorization is a middleware + service-layer guard.

**Rationale**: User requirement — full RBAC with tenant/team/group/role/user. Review HIGH finding — retrofitting `tenant_id` after launch is painful, so it is first-class now.

### AD-9: Usage Metering for Billback

**Decision**: Per-user AND per-org usage is captured from job lifecycle events. When a job completes, its runtime × instance type (GPU-seconds, instance-hours) is recorded in a `usage_records` table attributed to `org_id`, `team_id`, `user_id`, and `job_id`. Records derive from the authoritative `job_events` (AD-4), not from a separate write path. Cost Allocation Tags on Batch jobs provide a cross-check against AWS Cost Explorer.

**Rationale**: User requirement — billback per user and organization. Deriving from `job_events` keeps a single source of truth.

### AD-10: Container Strategy — Single Image, Two Entrypoints

**Decision**: One container image serves both the web tier and the compute worker, selected by entrypoint/`CMD` (`anvil._saas.app:app` for web, `anvil/_saas/compute_worker.py` for Batch). Built once, pushed once, referenced by a single digest. A multi-stage build keeps it lean. NOT split into separate `anvil-web` / `anvil-compute` images for v1.

**Rationale**:
- **Version consistency is a correctness property** — web and compute share the `job_events` schema, deterministic S3 key layout, and MLflow conventions. A single image makes version skew structurally impossible.
- **Matches digest-pinned turnkey deploy (AD-7)** — one digest in the CFN template, not two that must stay in lockstep across customer accounts.
- **Cold-start cost is amortized** — training jobs run minutes-to-hours; the Batch compute environment layer-caches the image. Extra pull time is negligible against job duration.
- **Simplest CI/CD** — one build/scan/push/sign, aligning with the boring/reliable mandate.

**Reversal trigger**: Split into a minimal `anvil-compute` image (core + boto3 + redis, no FastAPI) only if measured Batch cold-start dominates short jobs OR compliance requires minimizing the compute attack surface. `compute_worker.py` already isolates the compute entrypoint, so the split is mechanical later — no re-architecture.

### AD-11: Training Orchestration — Three-Plane Model, Batch-Owned Scheduling

**Decision**: Training jobs use a three-plane model (control plane = anvil-web, scheduler = AWS Batch, executor = compute pod). **AWS Batch is the orchestrator** — it owns queueing, compute-environment scaling, gang-scheduling, and retries. anvil-web admits/configures/submits/observes; it does not build a custom scheduler. Orchestration policy: app-level per-org quotas + Batch fair-share scheduling (keyed on `org_id`); infra-only auto-retry with checkpoint resume; periodic S3 checkpointing for long/multi-node jobs; pre-registered per-shape job definitions parameterized by `ResourceSpec`. (FR-045g–FR-045p)

**Rationale**: "Simple and boring orchestration" mandate — Batch already solves queueing/scaling/gang-scheduling/Spot retries reliably; building a custom orchestrator would be the opposite of boring. Fair-share prevents tenant starvation; app-level quotas give hard per-org caps and cost control; infra-only retry avoids burning compute on doomed user-error jobs; checkpointing makes cheap Spot capacity viable for long jobs. Config-via-S3 keeps the pod interface small and auditable. The three-plane separation enforces AD-4 (Postgres source of truth) — planes never mutate each other directly.

---

## Acceptance Gates

Every phase has a **binding acceptance gate** — a set of objective, verifiable criteria that MUST pass before the phase is considered complete and dependent phases may begin. Gates are enforced programmatically wherever possible.

### Gate Format

Each gate specifies: **G-{phase}.{n}** — the criterion, the verification method (automated test, AWS API check, manual), and the pass condition.

### Phase 1 — Setup Gate (G1)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G1.1 | `anvil/_saas/` package exists and is never imported in local mode | `python -c "import anvil"` with import tracing | No `anvil._saas` module loaded |
| G1.2 | `boto3`, `redis`, `aws-jwt-verify` are optional extras only | `pip install anvil` in clean venv, then `pip list` | None of the SaaS deps present |
| G1.3 | CDK app synthesizes | `cd packages/infra && cdk synth` | Exit 0, templates produced |

### Phase 2 — Foundational Gate (G2)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G2.1 | All 4 abstraction interfaces defined with full type signatures | `mypy --strict anvil/storage/` | Zero errors |
| G2.2 | Local implementations satisfy interfaces | Contract tests in `tests/contract/` | All pass |
| G2.3 | Local mode unchanged — existing suite passes | `make test` | 100% pass, coverage ≥ baseline |
| G2.4 | `ANVIL_MODE` selector wires correct implementations | Unit test asserting local vs saas wiring | Both modes wire correctly |
| G2.5 | Entrypoint/mode mismatch fails fast | Unit test: local factory with `ANVIL_MODE=saas` and vice versa | Raises clear error, no silent switch |
| G2.6 | SaaS factory fails fast on missing cloud config | Unit test: `ANVIL_MODE=saas` with `DATABASE_URL` unset | Raises listing missing vars, no local fallback |

### Phase 3 — Auth Gate (G3)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G3.1 | Cognito User Pool created with native email/password | AWS API: `cognito-idp describe-user-pool` | Pool exists, email sign-in enabled |
| G3.2 | FastAPI rejects requests with no/invalid JWT | API canary: request without token | 401 returned |
| G3.3 | FastAPI accepts valid Cognito JWT | API canary: token from test user | 200 + correct user context |
| G3.4 | First login creates local `users` mapping | API canary: new test user → check DB | `users` row with `cognito_sub` exists |
| G3.5 | SSE auth via signed query-param token works | API canary: open SSE with token | Stream connects; without token → 401 |

### Phase 4 — RBAC + Data Isolation Gate (G4)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G4.1 | Org/Team/Role/User schema migrated | AWS API: query `information_schema` | All RBAC tables present |
| G4.2 | User in Org A cannot see Org B data | API canary: two orgs, cross-access attempt | 403/empty for cross-org |
| G4.3 | Role permissions enforced (viewer cannot delete) | API canary: viewer attempts delete | 403 returned |
| G4.4 | Storage paths scoped by org_id | Inspect S3 keys after upload | Keys under `{org_id}/...` |

### Phase 5 — Training Pipeline Gate (G5)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G5.1 | CPU training job completes end-to-end | API canary: submit tiny job, poll | Job reaches `completed` |
| G5.2 | GPU job dispatches to GPU queue | API canary: submit gpu job | Batch job on GPU instance type |
| G5.3 | Multi-node job gang-schedules | API canary: submit 2-node job | Both nodes start, job completes |
| G5.4 | Live metrics stream via SSE | API canary: subscribe during job | ≥1 metric event received |
| G5.5 | Job state survives pod crash (reconciler) | Chaos test: kill pod mid-job | Reconciler marks job failed/recovered |
| G5.6 | Model artifact lands in S3 + MLflow | Check S3 + MLflow run after completion | Artifact + run present |
| G5.7 | Usage record created with org/user attribution | Query `usage_records` after job | Record with correct GPU-seconds |

### Phase 6 — Deploy CLI Gate (G6)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G6.1 | `anvil deploy init` deploys full stack in fresh account | Integration test in throwaway AWS account | Stack `CREATE_COMPLETE` |
| G6.2 | Output URL serves login page | HTTP GET CloudFront URL | 200 + login page HTML |
| G6.3 | Migrations ran before web service | Check migration task completed pre-rollout | Schema at HEAD before web healthy |
| G6.4 | Admin user can authenticate | API canary against deployed stack | Admin login succeeds |

### Phase 7 — Deploy Lifecycle Gate (G7)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G7.1 | `anvil deploy update` rolls new image | Deploy, update, check image digest | New digest live, no downtime |
| G7.2 | `anvil deploy config set-idp` adds social login | Configure, check Cognito IdP | IdP present in pool |
| G7.3 | `anvil deploy destroy` removes ALL resources | Destroy, then AWS API sweep | Zero stack resources remain (incl. S3) |
| G7.4 | Destroy on non-existent stack is a clean no-op | Run destroy twice | Second run exits cleanly |

### Phase 8 — Local Mode Regression Gate (G8)

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G8.1 | `pip install anvil && anvil serve` works unchanged | Clean install + smoke test | UI loads, training works |
| G8.2 | No SaaS code path reachable in local mode | Import-trace audit | Zero `anvil._saas` imports |
| G8.3 | All pre-existing tests pass | `make test` | 100% pass |

---

## Agentic Validation Loop (Programmatic AWS Verification)

A central requirement: after any deploy, an automated agent MUST be able to validate that **every component works programmatically via AWS APIs**, with a minimal browser layer only where unavoidable (OAuth redirect flows). This is the `anvil deploy verify` command and the CI E2E harness.

### Three-Layer Validation Pyramid

```mermaid
graph TB
    subgraph "Layer 3: Browser Smoke (minimal, Playwright)"
        B1[Cognito Hosted UI login redirect]
        B2[Session cookie through CloudFront/ALB]
        B3[SSE renders in real page]
    end
    subgraph "Layer 2: API Canary (headless, primary)"
        A1[Create native Cognito test user]
        A2[Obtain JWT, call protected API]
        A3[Submit tiny training job]
        A4[Assert DB row + Batch run + S3 artifact + MLflow run]
        A5[Subscribe SSE, assert metric event]
        A6[Assert usage_record created]
        A7[RBAC: cross-org access denied]
    end
    subgraph "Layer 1: AWS Control-Plane Checks (fastest)"
        C1[CloudFormation stack CREATE/UPDATE_COMPLETE]
        C2[ECS services healthy/steady state]
        C3[Batch compute env + queue VALID/ENABLED]
        C4[RDS available + reachable]
        C5[ElastiCache available + reachable]
        C6[S3 buckets exist + correct policies]
        C7[Cognito pool + app client present]
        C8[Stack outputs resolvable]
    end

    C1 --> A1
    A1 --> B1
```

### Layer 1 — AWS Control-Plane Checks (`anvil deploy verify --layer infra`)

Pure `boto3` API calls. Fast, no auth needed beyond AWS creds. Each is a discrete check with pass/fail:

| Check | AWS API | Pass Condition |
|-------|---------|----------------|
| Stack status | `cloudformation.describe_stacks` | `CREATE_COMPLETE` or `UPDATE_COMPLETE` |
| ECS web service | `ecs.describe_services` | `runningCount == desiredCount`, steady state |
| ECS MLflow service | `ecs.describe_services` | Healthy |
| Batch CPU compute env | `batch.describe_compute_environments` | `VALID` + `ENABLED` |
| Batch GPU compute env | `batch.describe_compute_environments` | `VALID` + `ENABLED` |
| Batch job queues | `batch.describe_job_queues` | `VALID` + `ENABLED` |
| RDS instance | `rds.describe_db_instances` | `available` |
| ElastiCache | `elasticache.describe_*` | `available` |
| S3 data bucket | `s3.head_bucket` + `get_bucket_policy` | Exists, correct policy |
| S3 MLflow bucket | `s3.head_bucket` | Exists |
| Cognito pool | `cognito-idp.describe_user_pool` | Exists, email sign-in on |
| Secrets | `secretsmanager.describe_secret` | All required secrets present |
| Stack outputs | `cloudformation.describe_stacks` Outputs | CloudFront URL, auth domain resolvable |

### Layer 2 — API Canary (`anvil deploy verify --layer api`)

The primary validation. Drives a full end-to-end flow through the API with a programmatically created test user. NO browser needed — uses Cognito admin APIs to create + authenticate the test user.

```
1. Create native Cognito test user (cognito-idp.admin-create-user + admin-set-password)
2. Authenticate (cognito-idp.admin-initiate-auth ADMIN_USER_PASSWORD_AUTH) → JWT
3. Call GET /v1/health with JWT → 200
4. Create test org + team via API → assert RBAC rows
5. Upload a tiny corpus via signed S3 URL → assert S3 object + DB row
6. Submit a CPU training job (1 layer, 20 steps) → assert TrainingJob row, Batch job submitted
7. Open SSE stream with signed token → assert ≥1 metrics event arrives
8. Poll job to completion → assert status=completed
9. Assert model artifact in S3 + MLflow run finalized
10. Assert usage_record created with correct org_id/user_id/gpu_seconds
11. RBAC negative test: second user in different org cannot read first org's corpus → 403
12. Cleanup: delete test resources, delete test Cognito user
```

Each step is an independent assertion with a clear pass/fail. The canary exits non-zero on any failure and reports which step failed.

### Layer 3 — Browser Smoke (`anvil deploy verify --layer browser`)

Minimal Playwright-driven checks for what cannot be validated headlessly:

| Check | Method | Pass Condition |
|-------|--------|----------------|
| Hosted UI login redirect | Playwright navigates to app, redirected to Cognito | Reaches Hosted UI |
| Native login + callback | Playwright fills email/password, submits | Lands authenticated on dashboard |
| Session through CloudFront/ALB | Cookie persists across navigation | Dashboard stays authenticated |
| SSE in real page | Start a job in UI, watch loss curve | Curve updates live |

Social login (Google/GitHub) is configuration-validated only (IdP present in pool) unless the customer supplies test social identities — full social login cannot be validated without real provider credentials.

### Verify Command

```
anvil deploy verify                      # Run all three layers
anvil deploy verify --layer infra        # Layer 1 only (fast, ~10s)
anvil deploy verify --layer api          # Layer 1 + 2 (canary, ~3-5 min for tiny job)
anvil deploy verify --layer browser      # All layers including Playwright
anvil deploy verify --json               # Machine-readable report for CI
```

The CI E2E harness runs `deploy init → deploy verify --layer api → deploy destroy` in a throwaway AWS account on every release, gating the release on a green verify.