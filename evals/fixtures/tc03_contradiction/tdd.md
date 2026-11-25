# TDD: EU Customer Portal

## 1. Architecture & Data Stores
- Invoice web backend deployed on Cloud Run with Cloud Firestore Native database provisioned in `us-central1` and daily exports to a `us-multi-region` Cloud Storage bucket.
- Generates PDF statements on demand via WeasyPrint.
