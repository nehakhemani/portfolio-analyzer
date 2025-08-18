#!/bin/bash
# Deploy Portfolio Analyzer to Google Cloud Run

set -e

# Configuration
PROJECT_ID="your-project-id"  # Change this to your project ID
REGION="us-central1"
SERVICE_NAME="portfolio-analyzer"

echo "🚀 Deploying Portfolio Analyzer to Google Cloud Run..."

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Navigate to project root
cd "$PROJECT_ROOT"

# Build and submit to Container Registry
echo "🔨 Building container image..."
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --file Dockerfile.cloudrun \
    .

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --concurrency=20 \
    --timeout=300 \
    --max-instances=10 \
    --set-cloudsql-instances=$PROJECT_ID:$REGION:portfolio-db \
    --set-env-vars="FLASK_ENV=production,INIT_DATABASE=true" \
    --set-secrets="DB_PASSWORD=db-password:latest,SECRET_KEY=app-secret-key:latest,ALPHA_VANTAGE_API_KEY=alpha-vantage-api-key:latest,FINNHUB_API_KEY=finnhub-api-key:latest"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo "✅ Deployment completed!"
echo "🔗 Service URL: $SERVICE_URL"
echo ""
echo "🧪 Testing deployment..."
curl -f "$SERVICE_URL/health" && echo "✅ Health check passed!" || echo "❌ Health check failed!"

echo ""
echo "📋 Next steps:"
echo "1. Visit your application: $SERVICE_URL"
echo "2. Set up batch job scheduler: ./setup-scheduler.sh"
echo "3. Monitor logs: gcloud run logs tail $SERVICE_NAME --region=$REGION"