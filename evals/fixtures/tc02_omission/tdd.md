# TDD: Order Fulfillment Tracker

## 1. Architecture Overview
- Python microservice on Cloud Run reading shipment records from Cloud SQL by `order_id` and returning carrier status and ETA.

## 2. Deployment
- Single regional Cloud Run service deployed in `us-central1` using Artifact Registry container images.
