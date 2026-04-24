# Architecture (Initial)

## High-level Components
- **Web Portal**: dashboard for owners and operators.
- **Tenant App**: payments, maintenance tickets, notifications.
- **API Gateway**: auth, routing, rate-limiting.
- **Core Services**:
  - Contracts Service
  - Billing Service
  - Matching Service
  - Operations Service
- **Data Layer**:
  - Relational DB for transactional data.
  - Object storage for contract documents.
  - Analytics warehouse for BI and forecasting.

## Suggested Stack
- Frontend: Next.js / React
- Backend: Node.js (NestJS) or Python (FastAPI)
- Database: PostgreSQL
- Queue: RabbitMQ or Kafka (as scale grows)
- Infra: Docker + Kubernetes (phase 2)

## Security Baseline
- RBAC by role (Owner / Tenant / Operator / Admin).
- Audit log for critical actions.
- Encryption at rest and in transit.

## API Domains
- `/auth/*`
- `/properties/*`
- `/contracts/*`
- `/billing/*`
- `/maintenance/*`
- `/matching/*`
