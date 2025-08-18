#!/bin/bash
# Set up Google Cloud Scheduler for batch price jobs

set -e

# Configuration
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="portfolio-analyzer"

echo "⏰ Setting up Cloud Scheduler for batch jobs..."

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Could not find Cloud Run service URL. Make sure the service is deployed first."
    exit 1
fi

# Create a service account for Cloud Scheduler
echo "👤 Creating service account for Cloud Scheduler..."
gcloud iam service-accounts create cloud-scheduler-sa \
    --display-name="Cloud Scheduler Service Account" \
    --description="Service account for triggering Cloud Run jobs" || echo "Service account might already exist"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:cloud-scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Create daily price update job (5PM EST)
echo "📅 Creating daily price update job..."
gcloud scheduler jobs create http daily-price-update \
    --location=$REGION \
    --schedule="0 17 * * *" \
    --time-zone="America/New_York" \
    --uri="$SERVICE_URL/api/batch/daily-price-update" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"job_type": "daily_price_update", "timeout_minutes": 30}' \
    --oidc-service-account-email="cloud-scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --oidc-token-audience="$SERVICE_URL" \
    --attempt-deadline=1800s \
    --max-retry-attempts=3 \
    --min-backoff-duration=60s \
    --max-backoff-duration=300s || echo "Job might already exist"

# Create weekend catch-up job (Saturday 9AM EST)
echo "📅 Creating weekend catch-up job..."
gcloud scheduler jobs create http weekend-catchup \
    --location=$REGION \
    --schedule="0 9 * * 6" \
    --time-zone="America/New_York" \
    --uri="$SERVICE_URL/api/batch/weekend-catchup" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"job_type": "weekend_catchup", "timeout_minutes": 45}' \
    --oidc-service-account-email="cloud-scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --oidc-token-audience="$SERVICE_URL" \
    --attempt-deadline=2700s \
    --max-retry-attempts=2 \
    --min-backoff-duration=120s \
    --max-backoff-duration=600s || echo "Job might already exist"

# Create cleanup job (2AM EST daily)
echo "🧹 Creating cleanup job..."
gcloud scheduler jobs create http cleanup-job \
    --location=$REGION \
    --schedule="0 2 * * *" \
    --time-zone="America/New_York" \
    --uri="$SERVICE_URL/api/batch/cleanup" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"job_type": "cleanup", "days_to_keep": 90}' \
    --oidc-service-account-email="cloud-scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --oidc-token-audience="$SERVICE_URL" \
    --attempt-deadline=600s \
    --max-retry-attempts=2 || echo "Job might already exist"

echo "✅ Cloud Scheduler setup completed!"
echo ""
echo "📋 Created scheduled jobs:"
echo "• Daily Price Update: Every day at 5:00 PM EST"
echo "• Weekend Catch-up: Saturday at 9:00 AM EST"  
echo "• Cleanup Job: Every day at 2:00 AM EST"
echo ""
echo "📊 Monitor jobs:"
echo "gcloud scheduler jobs list --location=$REGION"
echo ""
echo "🧪 Test a job manually:"
echo "gcloud scheduler jobs run daily-price-update --location=$REGION"