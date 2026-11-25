# TDD: Checkout Refund Engine

## 1. Architecture Overview
- Cloud Run refund service invoked by support console (REQ-001) with SendGrid email confirmation (REQ-002).

## 2. Business Rules & Decision Notes
- **Manual Approval Threshold:** Per 11/10 sync with Finance Ops, refunds over $500 route to a manual Finance approval queue instead of auto-refunding.
- **Retry Policy:** As agreed offline with Payments Lead during Tuesday standup, failed gateway calls retry 3 times with exponential backoff (2s, 4s, 8s) before opening an ops alert.
