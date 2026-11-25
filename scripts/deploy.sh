#!/usr/bin/env bash
# Programmatic IaC deployment script for SpecAlign on Google Cloud Agent Runtime.
# Usage:
#   export PROJECT_ID="your-gcp-project-id"
#   ./scripts/deploy.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
SA_NAME="${SA_NAME:-specalign-agent-sa}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: PROJECT_ID is not set. Run 'export PROJECT_ID=your-gcp-project-id' first." >&2
  exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "==> Deploying SpecAlign to project '${PROJECT_ID}' in region '${REGION}'"

echo "==> 1/5 Enabling required Google Cloud APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  telemetry.googleapis.com \
  monitoring.googleapis.com \
  agentregistry.googleapis.com \
  iam.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> 2/5 Provisioning least-privilege runtime service account (${SA_EMAIL})..."
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="SpecAlign Agent Runtime Service Account" \
    --project="${PROJECT_ID}"
  # Allow IAM eventual consistency before binding roles to the newly created SA.
  sleep 10
fi

for ROLE in roles/aiplatform.user roles/datastore.user roles/logging.logWriter roles/cloudtrace.agent; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet >/dev/null
done

echo "==> 3/5 Ensuring Cloud Firestore Native (default) database exists..."
if ! gcloud firestore databases describe --database="(default)" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --database="(default)" \
    --location="${REGION}" \
    --type=firestore-native \
    --project="${PROJECT_ID}"
fi

echo "==> 4/5 Running unit tests and ADK static lint..."
uv sync
uv run pytest -q
agents-cli lint

echo "==> 5/5 Deploying SpecAlign to Google Cloud Agent Runtime (with OpenTelemetry Cloud Trace)..."
uv run adk deploy agent_engine \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --display_name="SpecAlign — PRD & TDD Alignment Auditor" \
  --service_account="${SA_EMAIL}" \
  --python_version=3.12 \
  --otel_to_cloud \
  app

echo "==> Deployment complete! Verify in Cloud Console -> Agent Engine Playground & Agent Registry."
