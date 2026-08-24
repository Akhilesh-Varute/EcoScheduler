# EcoScheduler — Project Documentation

## 1. What this is

EcoScheduler is an **AWS EC2 cost-optimization SaaS**. It lets teams define cron-based
start/stop schedules for EC2 instances across multiple AWS accounts (via cross-account
IAM roles), so machines aren't left running when nobody needs them. It tracks the
resulting cost savings, supports holiday/maintenance exception dates, enforces
role-based access control, and bills customers via Stripe subscriptions.

The domain is **FinOps / cloud cost governance** — "Eco" refers to reducing AWS spend
by not running idle compute, not literal energy scheduling.

## 2. Tech stack

**Backend** (`backend/`) — the only implemented part of the project:

| Layer | Choice |
|---|---|
| Language | Python 3.10 (Lambda handlers) + Node ≥20 (tooling only) |
| Compute | AWS Lambda |
| API | Amazon API Gateway (REST) + custom JWT Lambda authorizer |
| Database | Amazon DynamoDB (`PAY_PER_REQUEST` billing mode) |
| Scheduling | Amazon EventBridge (per-schedule cron rules) + `croniter` |
| IaC | Serverless Framework v3 (`serverless.yml`) |
| Auth | JWT (HS256), `pyjwt` / `python-jose` |
| Payments | Stripe (subscriptions/checkout) |
| Cross-account access | AWS IAM (`sts:AssumeRole`), CloudFormation templates in `backend/infra/` |
| Testing/lint | pytest, flake8, black |

**Frontend** (`frontend/`) — **empty scaffold, not built**. `package.json` is 0 bytes,
`src/`/`public/` have no files. Recommendation (given during this session): build it as
a **separate** Next.js (or Vite+React) app that calls the existing API Gateway
endpoints with the JWT from `/auth/login` — don't merge frontend and backend into one
Next.js app. Reasoning: the backend's value is its event/cron-driven serverless
infra (EventBridge triggers, cross-account IAM, Stripe webhooks), which doesn't map
onto Next.js API routes; merging would mean re-implementing working Python as JS for
no functional gain.

## 3. Features

- **Multi-account EC2 scheduling** — cron-based start/stop, cross-account IAM roles
- **Exception dates** — holiday/maintenance windows that skip a schedule's action
- **Savings tracking** — computed cost/hours saved, queryable reports (summary/daily/schedule/account)
- **User management** — admin creates/updates users, assigns role + AWS account access
- **RBAC** — three roles: `admin`, `developer`, `finance` (see §4)
- **Billing** — Stripe subscriptions + checkout
- **Manual instance control** — start/stop outside the schedule, permission-gated
- **Dry-Run Mode** *(added this session)* — see §5
- **Audit Trail** *(added this session)* — see §5

## 4. RBAC — how it works

Roles and their permissions are a plain dict in `backend/src/common/auth.py:13-27`
(not a formal enum):

```python
ROLES = {
    'admin':     {'permissions': ['create_schedule','update_schedule','delete_schedule',
                                   'manage_users','view_savings','manage_accounts']},
    'developer': {'permissions': ['view_schedule','request_override','view_instances']},
    'finance':   {'permissions': ['view_savings','export_reports']},
}
```

Each user has a `role` string stored on their DynamoDB item (`backend/src/common/db_models.py`,
`UserModel`). Permissions are **not** stored per-user — they're resolved from `ROLES`
at token-generation time.

**Flow, end to end:**

1. `POST /auth/login` (`src/functions/auth/login.py`) authenticates via
   `UserModel.authenticate()` (plaintext password compare — flagged below as a
   known issue).
2. `generate_token()` (`common/auth.py:30-57`) builds a JWT embedding `sub` (userId),
   `email`, `role`, the resolved `permissions` list, and `aws_accounts`. Signed HS256,
   24h expiry, secret from `JWT_SECRET_KEY` env var (defaults insecurely — see §8).
3. Client sends `Authorization: Bearer <token>` on every subsequent call.
4. API Gateway invokes the custom `JwtAuthorizer` Lambda
   (`src/functions/auth/authorizer.py`) on every protected route. It decodes the
   token, and on success returns an IAM `Allow` policy with `userId`/`email`/`role`/
   `permissions`/`awsAccounts` injected into the authorizer context. On any failure
   it returns an explicit `Deny`.
5. The target Lambda handler reads that context via `get_current_user(event)`
   (`common/auth.py:166-202`), then does an inline check — either
   `has_permission(user, "some_permission")` and/or `user["role"] == "admin"` — before
   proceeding. Returns 401 (no identity) or 403 (insufficient permission).

There's a `require_permission` decorator defined (`common/auth.py:205-234`) but it's
unused — every handler does its own inline check instead, which risks drift between
handlers (see §8).

## 5. Dry-Run Mode & Audit Trail (built this session)

### Dry-Run Mode
- Per-schedule `dryRun` boolean field (default `False`), same lifecycle as the
  existing `enabled` field — toggled via `PUT /schedules/{scheduleId}`.
- Per-request override on manual calls: `POST /ec2/start` / `POST /ec2/stop` accept
  `"dryRun": true` in the body for one-off tests.
- When active, the handler logs what it *would* do and returns/records `result: "dry-run"`
  **without** calling the real `EC2Connector.start_instances()`/`stop_instances()`.
  For the scheduled path, this also skips the downstream savings-recording logic
  (correctly — no real stop occurred).

### Audit Trail
- New DynamoDB table `AuditLogModel` (`common/db_models.py`), modeled on the existing
  `SavingsModel` pattern. PK `auditId`, GSIs on `scheduleId`, `accountId`, and a
  composite `date`+`timestamp` index for time-range queries.
- Every EC2 start/stop — manual or scheduled, success/failure/dry-run — writes one
  record: `action`, `triggerType` (`manual`/`scheduled`), `triggeredBy` (user email/id,
  or literal `"system"` for scheduled runs — no live requester exists for those),
  `dryRun`, `result`, `instanceIds`, `accountId`, `scheduleId` (omitted, not defaulted,
  for schedule-less manual actions), `date`, `timestamp`.
- New endpoint: `GET /audit-logs?scheduleId=|accountId=&startDate=&endDate=`. Gated by
  the existing `view_savings` permission (admin + finance) — deliberately reused
  rather than adding a new permission, to keep the RBAC model unchanged. Requires at
  least one filter for non-admins (mirrors `savings/report.py`'s existing pattern).

**Files touched:** `common/db_models.py`, `serverless.yml`, `functions/ec2/start.py`,
`functions/ec2/stop.py`, `functions/schedules/update.py`, new `functions/audit/list.py`.

## 6. Data model (DynamoDB tables)

| Table | PK | GSIs |
|---|---|---|
| `eco-scheduler-users-{stage}` | `userId` | `EmailIndex` (email) |
| `eco-scheduler-schedules-{stage}` | `scheduleId` | `UserIdIndex`, `AccountIdIndex` |
| `eco-scheduler-savings-{stage}` | `savingsId` | `ScheduleIdIndex`, `DateIndex` |
| `eco-scheduler-exceptions-{stage}` | `exceptionId` | `ScheduleIdIndex`, `DateIndex` (date+scheduleId) |
| `eco-scheduler-subscriptions-{stage}` | `subscriptionId` | `UserIdIndex` |
| `eco-scheduler-audit-logs-{stage}` *(new)* | `auditId` | `ScheduleIdIndex`, `AccountIdIndex`, `DateIndex` (date+timestamp) |

## 7. API endpoints (deployed)

Base URL: `https://764k3tdic9.execute-api.us-east-1.amazonaws.com/dev`

```
POST   /auth/login
POST   /auth/register
GET    /users/me
GET    /users/{userId}
PUT    /users/{userId}
POST   /schedules
GET    /schedules
GET    /schedules/{scheduleId}
PUT    /schedules/{scheduleId}
DELETE /schedules/{scheduleId}
POST   /ec2/start
POST   /ec2/stop
GET    /ec2/list
GET    /savings/report
GET    /audit-logs          <- new
GET    /subscriptions
PUT    /subscriptions
POST   /payments/checkout
```

All except `/auth/login` and `/auth/register` require `Authorization: Bearer <JWT>`.

## 8. Known issues / tech debt

**Fixed this session:**

- **Plaintext passwords** — `UserModel` now hashes with PBKDF2-HMAC-SHA256
  (600,000 iterations, random salt per user), via `hash_password()`/`verify_password()`
  in `common/db_models.py`. Deliberately **not** bcrypt/argon2 — those need a native
  C extension, which requires Docker to cross-build for Lambda's Linux runtime from a
  Windows dev machine. PBKDF2 via stdlib `hashlib` needs no extra dependency and
  packages identically to the rest of the codebase. Stored format:
  `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`.
- **Permission/role mismatch** — `start_instances`/`stop_instances` are now
  explicitly present in admin's permission list (`auth.py:13-27`). Decision made
  this session: **admin-only** for manual EC2 start/stop (developer/finance still
  can't, matching prior de-facto behavior, just now correctly defined instead of
  accidentally broken).
- **`JWT_SECRET_KEY` insecure default** — removed from `serverless.yml`
  (`custom.jwtSecret: ${env:JWT_SECRET_KEY}`, no fallback). Deploy now fails loudly
  if the env var isn't set, instead of silently using a public default. A real
  secret was generated and is in use in the deployed `dev` stage (rotate before any
  real/production use — value isn't recorded here, treat it as already-shared secret
  material since it appeared in chat history during setup).
- **Decimal JSON serialization bug** — `common/utils.py`'s `json_serializer` didn't
  handle `decimal.Decimal`, which is what boto3's DynamoDB resource API returns for
  *every* numeric attribute regardless of how it was written. Broke `/auth/login`
  (500 error) and would have broken any endpoint returning DB items with numbers.
  Fixed with a `Decimal` branch (int if whole, else float) — `utils.py:35-51`.
- **`create_admin_user.py`'s "update to admin" path didn't rehash passwords** —
  found while re-testing after the password-hashing fix: the script's update branch
  only touched `role`/`awsAccounts`, silently leaving old password hashes in place
  (would have caused permanent login failure for anyone using that path after a
  hashing-scheme change). Fixed — it now also rehashes and updates the password.

**Still open:**

- **Duplicate authorizer code** — `common/auth.py:96-144` has a near-identical unused
  `lambda_authorizer` function; the one actually wired in `serverless.yml` is
  `functions/auth/authorizer.py`.
- **`require_permission` decorator unused** — enforcement is manual/inline per
  handler instead, risking drift.
- **No automated test suite run** — pytest exists in the repo but was never executed
  this session.
- **Cross-account EC2 scheduling never tested against a real second account** — only
  dry-run and the manual API path (against a fake instance ID) were exercised.
- **Stripe billing flow untested** — no checkout/webhook flow run, price IDs unset.

## 9. Deployment

### 9.1 Master template — run once in your own AWS account

`backend/infra/master-account.yml` creates the deploy-time IAM identity and the
Lambda/API-Gateway service roles. Deployed to account **637423590778**
(`iamadmin-general` profile):

```powershell
aws cloudformation deploy `
  --template-file infra/master-account.yml `
  --stack-name eco-scheduler-master `
  --capabilities CAPABILITY_NAMED_IAM `
  --profile iamadmin-general `
  --region us-east-1
```

Creates: `EcoScheduler-Service-Role` (Lambda execution role — DynamoDB, cross-account
`sts:AssumeRole`, EventBridge, Lambda invoke), `EcoScheduler-ApiGateway-Role`, and an
`EcoScheduler-Admin` IAM user + access key (used as the `ecoscheduler-admin` CLI
profile for actually deploying the backend).

**Permissions added to `EcoSchedulerAdminUser` during this session's deploy
troubleshooting** (were missing originally):
- `iam:DeleteRolePolicy`, `iam:GetRole`, `iam:GetPolicy`
- A full `EcoSchedulerEventBridgeAdminAccess` policy (`events:PutRule`,
  `DescribeRule`, `DeleteRule`, `PutTargets`, `RemoveTargets`, `EnableRule`,
  `DisableRule`, `ListRules`, `ListTargetsByRule`, `TagResource`, `UntagResource`,
  `ListTagsForResource`) — without this, `serverless deploy` failed on
  `CalculateSavingsEventsRuleSchedule1` with `events:DescribeRule` AccessDenied.

### 9.2 Customer template — run once per customer AWS account

`backend/infra/customer-account-role.yml` creates only the cross-account role that
lets your master account start/stop EC2 in the customer's account:

```powershell
aws cloudformation deploy `
  --template-file customer-account-role.yml `
  --stack-name ecoscheduler-access `
  --parameter-overrides MasterAccountId=637423590778 `
  --capabilities CAPABILITY_NAMED_IAM `
  --profile <customer-own-profile>
```

Order matters: master template first, then each customer's template (references the
master account ID so it can trust `EcoScheduler-Service-Role`).

### 9.3 Backend deploy

```powershell
cd backend
npm install
npx serverless deploy --stage dev --aws-profile ecoscheduler-admin
```

Uploads packaged Lambda zips to an auto-created S3 bucket
(`eco-scheduler-dev-serverlessdeploymentbucket-*`), then creates/updates the
`eco-scheduler-dev` CloudFormation stack: all 6 DynamoDB tables, all Lambda
functions, API Gateway REST API, and the `JwtAuthorizer`.

### 9.4 Admin user creation

```powershell
$env:AWS_PROFILE = "ecoscheduler-admin"
python scripts/create_admin_user.py --stage dev --region us-east-1
```

Interactive — prompts for email, name, password (min 8 chars), and comma-separated
AWS account IDs the admin can manage (blank is fine; admins bypass account-ownership
checks anyway).

## 10. AWS environment (as of this session)

| Profile | Account ID | Status |
|---|---|---|
| `default` | 980636705122 | valid |
| `iamadmin-general` | 637423590778 | valid — **this is EcoScheduler's master account** |
| `iamadmin-production` | 396608769761 | valid |
| `ecoscheduler-admin` | 637423590778 | valid (reconfigured this session — old key was stale) |
| `soniya-aws-account`, `cost-forecaster`, `production-new` | — | stale/invalid creds, unrelated |

Note: account 637423590778 also hosts an unrelated pre-existing project,
`CloudCostIQ` (stack `cloudcostiq-master`, table `cloudcostiq-tenant-table`) — not
part of EcoScheduler, don't touch it.

### Local dev environment note
Deploying required switching from **Node 26.3.0** to **Node 20.20.2** via
nvm-windows (`nvm install 20`, `nvm use 20`) — Serverless Framework v3 predates
Node 26 and the CLI hung indefinitely (client-side, not AWS-side) talking to
CloudFormation under Node 26.

## 11. Troubleshooting log (issues hit + fixes, this session)

1. **Node 26 incompatibility** — `serverless deploy` hung 8+ hours on "Retrieving
   CloudFormation stack" with zero AWS-side progress. Fixed by installing
   nvm-windows and switching to Node 20.20.2, then a clean `node_modules` reinstall.
2. **`ResourceExistenceCheck` failures (recurring)** — CloudFormation refused to
   create the change set because fixed-name resources already existed outside the
   stack's tracking, left over from an abandoned deploy attempt from **2025-05-11**:
   - `EcoScheduler-CrossAccount-Role-Template` (IAM managed policy, 0 attachments)
   - `eco-scheduler-dev-us-east-1-lambdaRole` (Serverless's own default Lambda
     execution role — recurred **twice**, since a subsequent failed attempt
     recreated it before rolling back incompletely again)
   Fixed each time by deleting the orphan (`aws iam delete-policy` /
   `delete-role-policy` + `delete-role`) and retrying.
3. **`events:DescribeRule` AccessDenied** — the `ecoscheduler-admin` deploy user
   never had EventBridge permissions in `master-account.yml`. Fixed by adding
   `EcoSchedulerEventBridgeAdminAccess` (see §9.1) and redeploying the master stack.
4. **`Type <class 'decimal.Decimal'> not serializable`** — pre-existing bug in
   `common/utils.py`'s `json_serializer`, surfaced on first real login. Fixed (see §8).
5. **Transient 403 "no identity-based policy allows execute-api:Invoke"** on
   `/audit-logs` with a verified-valid token — resolved on retry; almost certainly
   API Gateway's authorizer response cache still holding a stale `Deny` from earlier
   bad-token tests against other routes during debugging.
6. **`bcrypt` native extension incompatible with Lambda** — first attempt at password
   hashing used `bcrypt`, which packaged as a Windows binary (`dockerizePip: false`)
   and failed at runtime with `No module named 'bcrypt._bcrypt'`. Rather than require
   Docker for every future deploy (the fix would've been `dockerizePip: true`),
   switched to stdlib `hashlib.pbkdf2_hmac` — no native dependency, deploys the same
   way as everything else.
7. **`create_admin_user.py`'s update path didn't rehash on password change** — see §8.

## 12. Verified test flow

```powershell
# 1. Login
$login = Invoke-RestMethod -Method Post -Uri "$base/auth/login" `
  -ContentType "application/json" `
  -Body (@{ email = "<email>"; password = "<password>" } | ConvertTo-Json)
$token = $login.token

# 2. Dry-run start (no real AWS account needed — admin bypasses ownership check)
Invoke-RestMethod -Method Post -Uri "$base/ec2/start" `
  -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" `
  -Body (@{ accountId = "123456789012"; instanceIds = @("i-testdryrun"); dryRun = $true } | ConvertTo-Json)
# -> success: true, dryRun: true

# 3. Confirm audit log written
Invoke-RestMethod -Method Get -Uri "$base/audit-logs?accountId=123456789012" `
  -Headers @{ Authorization = "Bearer $token" }
# -> count: 1, logs: [{ result: "dry-run", ... }]
```

All three steps confirmed working end-to-end in the deployed `dev` stage.
