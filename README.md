# EcoScheduler

**Multi-tenant AWS EC2 cost-optimization SaaS.** Lets teams schedule EC2
instances to stop and start on a cron, across multiple customer AWS accounts,
so nobody pays for compute sitting idle overnight or on weekends.

## What it does

- **Cross-account EC2 scheduling** — connect any AWS account via a
  self-service IAM role setup, then schedule instances to stop/start on a
  recurring pattern (e.g. weekdays 8am-7pm) or a one-time date/time.
- **Friendly scheduling UI** — pick days of the week and times with native
  pickers, or a specific one-off date, instead of writing raw cron syntax.
  An "Advanced" mode is still there for anyone who wants direct cron control.
- **Dry-run mode** — test a schedule without it actually touching real
  instances, per-schedule or per manual action.
- **Full audit trail** — every start/stop action (scheduled or manual) is
  logged with who/what/when/result, queryable via the API.
- **Savings tracking** — computed cost/hours saved per instance, with
  summary/schedule/account-level reports.
- **Self-service AWS account onboarding** — any user can connect their own
  AWS account (download a CloudFormation template, deploy it, verify the
  connection) without waiting on an admin.
- **RBAC** — admin / developer / finance roles, with developers and finance
  scoped strictly to resources they actually own or have connected.

## Architecture

```
frontend/   Next.js 14 + TypeScript + Tailwind (App Router)
            JWT auth (stored client-side), talks to the backend over HTTPS

backend/    Python 3.10 on AWS Lambda, deployed via Serverless Framework
            API Gateway (REST) + custom JWT Lambda authorizer
            DynamoDB (Users, Schedules, Savings, Exceptions, AuditLogs, Subscriptions)
            EventBridge cron rules drive scheduled start/stop, per schedule
            Cross-account access via STS AssumeRole (no long-lived credentials)
```

The two halves are deliberately separate deployables — the backend is
serverless/event-driven infrastructure (EventBridge, cross-account IAM,
Lambda), which doesn't map cleanly onto a Next.js API-routes model. The
frontend is a normal SPA-style dashboard that just calls the backend's API.

## Repo layout

```
backend/
  src/functions/     one file per Lambda handler (auth, schedules, ec2, savings, audit, accounts, users, subscriptions)
  src/common/        shared logic: auth/RBAC, DynamoDB models, EC2 cross-account connector, EventBridge scheduler
  infra/             CloudFormation templates for the master account and each customer account's cross-account role
  serverless.yml     the actual deployable service definition

frontend/
  app/               Next.js App Router pages (login, register, dashboard/*)
  components/        ScheduleForm, ScheduleTimingFields (the day/time picker), InstancePicker, TimezoneSelect, etc.
  lib/               API client, auth/token handling, shared types
```

## Getting started

### Backend

```bash
cd backend
npm install
pip install -r requirements.txt

# deploy needs a real JWT secret - no insecure default is baked in
export JWT_SECRET_KEY=$(openssl rand -hex 32)
npx serverless deploy --stage dev
```

Then create your first admin user:

```bash
python scripts/create_admin_user.py --stage dev --region us-east-1
```

### Frontend

```bash
cd frontend
npm install
# set NEXT_PUBLIC_API_BASE_URL in .env.local to your deployed API Gateway URL
npm run dev
```

### Connecting a customer AWS account

1. In the app, go to **Connect AWS account**.
2. Download the linked `customer-account-role.yml` template.
3. Deploy it in the *target* AWS account (the account whose EC2 instances
   you want to schedule), passing your master account ID as a parameter.
4. Back in the app, enter the account ID and click **Connect account** — it
   verifies the cross-account role works and adds the account to your
   profile in one step.

## Known limitations

- No automated test suite has been run against this codebase.
- Stripe/billing integration is scaffolded (`payment.py`, subscription
  models) but not wired up or tested — treat the SaaS billing layer as
  not-yet-built, not as a working feature.
- `EventBridge`'s cross-stage/region role-trust setup (in
  `customer-account-role.yml`) currently defaults to the `dev` stage's
  Lambda execution role name; a `prod` deploy needs that parameter
  overridden to match.

See [DOCUMENTATION.md](DOCUMENTATION.md) for the full architecture writeup,
RBAC flow, deployment troubleshooting log, and a more detailed list of known
issues.
