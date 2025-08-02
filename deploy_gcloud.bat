@echo off
echo 🚀 Deploying Portfolio Analyzer to Google Cloud Run
echo ==================================================

REM Check if gcloud is installed
gcloud version >nul 2>&1
if errorlevel 1 (
    echo ❌ Google Cloud CLI not found!
    echo Install from: https://cloud.google.com/sdk/docs/install
    pause
    exit /b 1
)

REM Get project ID
for /f "tokens=2" %%i in ('gcloud config get-value project 2^>nul') do set PROJECT_ID=%%i
echo 📋 Current project: %PROJECT_ID%

if "%PROJECT_ID%"=="" (
    echo ❌ No project set!
    echo Run: gcloud config set project YOUR_PROJECT_ID
    pause
    exit /b 1
)

REM Enable required APIs
echo 🔧 Enabling required APIs...
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

REM Deploy to Cloud Run
echo 🚀 Deploying to Cloud Run...
gcloud run deploy portfolio-analyzer ^
    --source . ^
    --region us-central1 ^
    --allow-unauthenticated ^
    --port 8080 ^
    --memory 1Gi ^
    --cpu 1 ^
    --max-instances 10 ^
    --set-env-vars FLASK_ENV=production

echo ✅ Deployment complete!
echo.
echo 🌐 Your app is available at:
gcloud run services describe portfolio-analyzer --region us-central1 --format "value(status.url)"
echo.
echo 📊 To view logs run:
echo gcloud run services describe portfolio-analyzer --region us-central1
echo.
echo 🔧 To set environment variables run:
echo gcloud run services update portfolio-analyzer --update-env-vars KEY=VALUE --region us-central1

pause