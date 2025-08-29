#!/bin/bash
# Portfolio Analyzer - Local Build and Cloud Deployment Script
# This script follows best practices: Build locally -> Test -> Deploy to Cloud

set -e  # Exit on any error

echo ""
echo "========================================"
echo "🚀 Portfolio Analyzer Cloud Deployment"
echo "========================================"
echo ""

# Configuration
PROJECT_ID="portfolio-analyzer-467806"
SERVICE_NAME="portfolio-analyzer-clean"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
VERSION=$(date +%Y%m%d-%H%M%S)

echo "📋 Deployment Configuration:"
echo "  Project: ${PROJECT_ID}"
echo "  Service: ${SERVICE_NAME}"
echo "  Region: ${REGION}"
echo "  Image: ${IMAGE_NAME}:${VERSION}"
echo "  Time: $(date)"
echo ""

# Step 1: Stop any running local containers
echo "🛑 Step 1: Stopping local containers..."
docker-compose -f docker-compose.local.yml down >/dev/null 2>&1 || true
echo "✅ Local containers stopped"
echo ""

# Step 2: Build and test locally
echo "🔨 Step 2: Building and testing locally..."
docker-compose -f docker-compose.local.yml up --build -d

echo "📦 Waiting for application to start..."
sleep 10

# Test local deployment
echo "🧪 Testing local deployment..."
if ! curl -s http://localhost:8080/health >/dev/null; then
    echo "❌ Local health check failed"
    docker-compose -f docker-compose.local.yml down
    exit 1
fi
echo "✅ Local deployment working"

# Test authentication
if ! curl -s http://localhost:8080/api/check-auth >/dev/null; then
    echo "❌ Authentication test failed"
    docker-compose -f docker-compose.local.yml down
    exit 1
fi
echo "✅ Authentication system working"

docker-compose -f docker-compose.local.yml down
echo "✅ Local testing complete"
echo ""

# Step 3: Build for cloud
echo "☁️ Step 3: Building for Google Cloud..."
docker build -f Dockerfile.cloud -t ${IMAGE_NAME}:${VERSION} -t ${IMAGE_NAME}:latest .
echo "✅ Cloud image built successfully"
echo ""

# Step 4: Test cloud build locally
echo "🧪 Step 4: Testing cloud build locally..."
docker run -d -p 8081:8080 --name portfolio-cloud-test ${IMAGE_NAME}:latest

sleep 5
if ! curl -s http://localhost:8081/health >/dev/null; then
    echo "❌ Cloud image health check failed"
    docker stop portfolio-cloud-test >/dev/null
    docker rm portfolio-cloud-test >/dev/null
    exit 1
fi

docker stop portfolio-cloud-test >/dev/null
docker rm portfolio-cloud-test >/dev/null
echo "✅ Cloud image tested successfully"
echo ""

# Step 5: Push to Google Container Registry
echo "📤 Step 5: Pushing to Google Container Registry..."
gcloud auth configure-docker --quiet

docker push ${IMAGE_NAME}:${VERSION}
docker push ${IMAGE_NAME}:latest
echo "✅ Images pushed successfully"
echo ""

# Step 6: Deploy to Cloud Run
echo "🌐 Step 6: Deploying to Google Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image=${IMAGE_NAME}:${VERSION} \
    --region=${REGION} \
    --platform=managed \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --max-instances=10 \
    --set-env-vars="FLASK_ENV=production,ALPHA_VANTAGE_API_KEY=8TC1QT08BL9F04B1,FINNHUB_API_KEY=d2kfr9hr01qs23a239vgd2kfr9hr01qs23a23a00" \
    --quiet

echo "✅ Deployed to Cloud Run successfully"
echo ""

# Step 7: Test production deployment
echo "🧪 Step 7: Testing production deployment..."
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format="value(status.url)")

echo "🌐 Service URL: ${SERVICE_URL}"
echo "📋 Testing production endpoints..."

# Test health endpoint
if ! curl -s "${SERVICE_URL}/health" >/dev/null; then
    echo "❌ Production health check failed"
    exit 1
fi
echo "✅ Health endpoint working"

# Test authentication
if ! curl -s "${SERVICE_URL}/api/check-auth" >/dev/null; then
    echo "❌ Production auth check failed"
    exit 1
fi
echo "✅ Authentication endpoint working"

echo ""
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "========================================"
echo "📱 Your Portfolio Analyzer is now live!"
echo "🌐 URL: ${SERVICE_URL}"
echo "🔐 Login: ${SERVICE_URL}/login.html"
echo "📝 Register: ${SERVICE_URL}/register.html"
echo "⚡ Test Account: testuser / password123"
echo "========================================"
echo ""

# Cleanup local images to save space
echo "🧹 Cleaning up local images..."
docker image rm ${IMAGE_NAME}:${VERSION} >/dev/null 2>&1 || true
docker image rm ${IMAGE_NAME}:latest >/dev/null 2>&1 || true
echo "✅ Cleanup complete"

echo "🎯 Deployment completed successfully at $(date)"