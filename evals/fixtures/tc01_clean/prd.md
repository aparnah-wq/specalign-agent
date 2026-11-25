# PRD: Payment Status API

## 1. Business Goals
- Cut merchant payment-status support tickets by 40% in Q1.

## 2. Functional Requirements
- REQ-001 (Must-Have): Expose `GET /v1/payments/{payment_id}` returning payment status, amount, and timestamp.
- REQ-002 (Must-Have): Return HTTP 404 JSON error envelopes for unknown payment IDs.

## 3. Non-Functional Requirements & Security
- NFR-001: Maintain p95 response latency <= 300ms at 100 QPS.
- NFR-002: Enforce TLS 1.3 and IAM service-to-service authentication.
- NFR-003: Retain Cloud Audit Logs for 90 days.

## 4. Scope Exclusions
- Payment mutations and refund execution are out of scope for Phase 1.
