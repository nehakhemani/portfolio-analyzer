#!/bin/bash

# Google Cloud Deployment Script
# Run this after setting up Google Cloud CLI

echo "🚀 Deploying Portfolio Analyzer to Google Cloud Run"
echo "=================================================="

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud CLI not found!"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project)
echo "📋 Current project: $PROJECT_ID"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ No project set!"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy portfolio-analyzer \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --max-instances 10 \
    --set-env-vars FLASK_ENV=production

echo "✅ Deployment complete!"
echo ""
echo "🌐 Your app is available at:"
gcloud run services describe portfolio-analyzer --region us-central1 --format 'value(status.url)'
echo ""
echo "📊 To view logs:"
echo "gcloud run services describe portfolio-analyzer --region us-central1"
echo ""
echo "🔧 To set environment variables:"
echo "gcloud run services update portfolio-analyzer --update-env-vars KEY=VALUE --region us-central1"