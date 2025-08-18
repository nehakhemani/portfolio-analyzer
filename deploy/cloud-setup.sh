#!/bin/bash
# Google Cloud Setup Script for Portfolio Analyzer
# Run this script to set up all necessary Google Cloud resources

set -e

# Configuration
PROJECT_ID="your-project-id"  # Change this to your Google Cloud project ID
REGION="us-central1"
SERVICE_NAME="portfolio-analyzer"
DB_INSTANCE_NAME="portfolio-db"
DB_NAME="portfolio_analyzer"
DB_USER="portfolio_user"

echo "🚀 Setting up Portfolio Analyzer on Google Cloud..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first."
    echo "Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
echo "📋 Setting Google Cloud project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable sqladmin.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com

# Create Cloud SQL PostgreSQL instance
echo "🗄️  Creating Cloud SQL PostgreSQL instance..."
if ! gcloud sql instances describe $DB_INSTANCE_NAME &> /dev/null; then
    gcloud sql instances create $DB_INSTANCE_NAME \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region=$REGION \
        --storage-type=SSD \
        --storage-size=10GB \
        --storage-auto-increase \
        --backup-start-time=02:00 \
        --enable-bin-log \
        --maintenance-window-day=SUN \
        --maintenance-window-hour=03
    
    echo "✅ Cloud SQL instance created: $DB_INSTANCE_NAME"
else
    echo "ℹ️  Cloud SQL instance already exists: $DB_INSTANCE_NAME"
fi

# Create database and user
echo "👤 Setting up database and user..."
DB_PASSWORD=$(openssl rand -base64 32)

# Create the database
gcloud sql databases create $DB_NAME --instance=$DB_INSTANCE_NAME || echo "Database might already exist"

# Create user with generated password
gcloud sql users create $DB_USER \
    --instance=$DB_INSTANCE_NAME \
    --password=$DB_PASSWORD || echo "User might already exist"

# Store database password in Secret Manager
echo "🔐 Storing database credentials in Secret Manager..."
echo -n "$DB_PASSWORD" | gcloud secrets create db-password --data-file=- || \
echo -n "$DB_PASSWORD" | gcloud secrets versions add db-password --data-file=-

# Create other secrets for API keys
echo "Creating secret placeholders for API keys..."
echo -n "demo" | gcloud secrets create alpha-vantage-api-key --data-file=- || echo "Secret exists"
echo -n "demo" | gcloud secrets create finnhub-api-key --data-file=- || echo "Secret exists"

# Generate app secret key
APP_SECRET_KEY=$(openssl rand -base64 48)
echo -n "$APP_SECRET_KEY" | gcloud secrets create app-secret-key --data-file=- || \
echo -n "$APP_SECRET_KEY" | gcloud secrets versions add app-secret-key --data-file=-

# Get Cloud SQL connection name
CONNECTION_NAME=$(gcloud sql instances describe $DB_INSTANCE_NAME --format="value(connectionName)")

echo "📝 Creating deployment configuration..."
cat > cloud-run-config.yaml << EOF
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: $SERVICE_NAME
  annotations:
    run.googleapis.com/cloudsql-instances: $CONNECTION_NAME
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cloudsql-instances: $CONNECTION_NAME
        autoscaling.knative.dev/maxScale: '10'
        run.googleapis.com/cpu-throttling: 'false'
    spec:
      containerConcurrency: 20
      timeoutSeconds: 300
      containers:
      - image: gcr.io/$PROJECT_ID/$SERVICE_NAME:latest
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          value: "/cloudsql/$CONNECTION_NAME"
        - name: DB_NAME
          value: "$DB_NAME"
        - name: DB_USER
          value: "$DB_USER"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-password
              key: latest
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: app-secret-key
              key: latest
        - name: ALPHA_VANTAGE_API_KEY
          valueFrom:
            secretKeyRef:
              name: alpha-vantage-api-key
              key: latest
        - name: FINNHUB_API_KEY
          valueFrom:
            secretKeyRef:
              name: finnhub-api-key
              key: latest
        - name: FLASK_ENV
          value: "production"
        - name: INIT_DATABASE
          value: "true"
        resources:
          limits:
            cpu: '2'
            memory: '2Gi'
          requests:
            cpu: '1'
            memory: '512Mi'
EOF

echo "✅ Google Cloud setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Update API keys in Secret Manager:"
echo "   gcloud secrets versions add alpha-vantage-api-key --data-file=<your-key-file>"
echo "   gcloud secrets versions add finnhub-api-key --data-file=<your-key-file>"
echo ""
echo "2. Build and deploy the application:"
echo "   ./deploy-to-cloudrun.sh"
echo ""
echo "3. Set up Cloud Scheduler for batch jobs:"
echo "   ./setup-scheduler.sh"
echo ""
echo "🔗 Important connection details:"
echo "Cloud SQL Connection Name: $CONNECTION_NAME"
echo "Database Name: $DB_NAME"
echo "Database User: $DB_USER"
echo "Database Password: [Stored in Secret Manager: db-password]"