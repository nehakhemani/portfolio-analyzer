@echo off
REM Portfolio Analyzer - Local Build and Cloud Deployment Script
REM This script follows best practices: Build locally -> Test -> Deploy to Cloud

echo.
echo ========================================
echo 🚀 Portfolio Analyzer Cloud Deployment
echo ========================================
echo.

REM Configuration
set PROJECT_ID=portfolio-analyzer-467806
set SERVICE_NAME=portfolio-analyzer-clean
set REGION=us-central1
set IMAGE_NAME=gcr.io/%PROJECT_ID%/%SERVICE_NAME%
set VERSION=%date:~-4%%date:~4,2%%date:~7,2%-%time:~0,2%%time:~3,2%
set GCLOUD_PATH="C:/Users/NEHA/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"

echo 📋 Deployment Configuration:
echo   Project: %PROJECT_ID%
echo   Service: %SERVICE_NAME%
echo   Region: %REGION%
echo   Image: %IMAGE_NAME%:%VERSION%
echo   Time: %date% %time%
echo.

REM Step 1: Stop any running local containers
echo 🛑 Step 1: Stopping local containers...
docker-compose -f docker-compose.local.yml down >nul 2>&1
echo ✅ Local containers stopped
echo.

REM Step 2: Build and test locally
echo 🔨 Step 2: Building and testing locally...
docker-compose -f docker-compose.local.yml up --build -d
if %errorlevel% neq 0 (
    echo ❌ Local build failed
    exit /b 1
)

echo 📦 Waiting for application to start...
timeout /t 10 /nobreak >nul

REM Test local deployment
echo 🧪 Testing local deployment...
curl -s http://localhost:8080/health >nul
if %errorlevel% neq 0 (
    echo ❌ Local health check failed
    docker-compose -f docker-compose.local.yml down
    exit /b 1
)
echo ✅ Local deployment working

REM Test authentication
curl -s http://localhost:8080/api/check-auth >nul
if %errorlevel% neq 0 (
    echo ❌ Authentication test failed
    docker-compose -f docker-compose.local.yml down
    exit /b 1
)
echo ✅ Authentication system working

docker-compose -f docker-compose.local.yml down
echo ✅ Local testing complete
echo.

REM Step 3: Build for cloud
echo ☁️ Step 3: Building for Google Cloud...
docker build -f Dockerfile.cloud -t %IMAGE_NAME%:%VERSION% -t %IMAGE_NAME%:latest .
if %errorlevel% neq 0 (
    echo ❌ Cloud build failed
    exit /b 1
)
echo ✅ Cloud image built successfully
echo.

REM Step 4: Test cloud build locally
echo 🧪 Step 4: Testing cloud build locally...
docker run -d -p 8081:8080 --name portfolio-cloud-test %IMAGE_NAME%:latest
if %errorlevel% neq 0 (
    echo ❌ Cloud image test failed
    exit /b 1
)

timeout /t 5 /nobreak >nul
curl -s http://localhost:8081/health >nul
if %errorlevel% neq 0 (
    echo ❌ Cloud image health check failed
    docker stop portfolio-cloud-test >nul
    docker rm portfolio-cloud-test >nul
    exit /b 1
)

docker stop portfolio-cloud-test >nul
docker rm portfolio-cloud-test >nul
echo ✅ Cloud image tested successfully
echo.

REM Step 5: Push to Google Container Registry
echo 📤 Step 5: Pushing to Google Container Registry...
%GCLOUD_PATH% auth configure-docker --quiet
if %errorlevel% neq 0 (
    echo ❌ Docker auth failed
    exit /b 1
)

docker push %IMAGE_NAME%:%VERSION%
if %errorlevel% neq 0 (
    echo ❌ Image push failed
    exit /b 1
)

docker push %IMAGE_NAME%:latest
echo ✅ Images pushed successfully
echo.

REM Step 6: Deploy to Cloud Run
echo 🌐 Step 6: Deploying to Google Cloud Run...
%GCLOUD_PATH% run deploy %SERVICE_NAME% ^
    --image=%IMAGE_NAME%:%VERSION% ^
    --region=%REGION% ^
    --platform=managed ^
    --allow-unauthenticated ^
    --memory=512Mi ^
    --cpu=1 ^
    --max-instances=10 ^
    --set-env-vars="FLASK_ENV=production,ALPHA_VANTAGE_API_KEY=8TC1QT08BL9F04B1,FINNHUB_API_KEY=d2kfr9hr01qs23a239vgd2kfr9hr01qs23a23a00" ^
    --quiet

if %errorlevel% neq 0 (
    echo ❌ Cloud Run deployment failed
    exit /b 1
)
echo ✅ Deployed to Cloud Run successfully
echo.

REM Step 7: Test production deployment
echo 🧪 Step 7: Testing production deployment...
for /f "tokens=*" %%i in ('%GCLOUD_PATH% run services describe %SERVICE_NAME% --region=%REGION% --format="value(status.url)"') do set SERVICE_URL=%%i

echo 🌐 Service URL: %SERVICE_URL%
echo 📋 Testing production endpoints...

REM Test health endpoint
curl -s "%SERVICE_URL%/health" >nul
if %errorlevel% neq 0 (
    echo ❌ Production health check failed
    exit /b 1
)
echo ✅ Health endpoint working

REM Test authentication
curl -s "%SERVICE_URL%/api/check-auth" >nul
if %errorlevel% neq 0 (
    echo ❌ Production auth check failed
    exit /b 1
)
echo ✅ Authentication endpoint working

echo.
echo 🎉 DEPLOYMENT SUCCESSFUL!
echo ========================================
echo 📱 Your Portfolio Analyzer is now live!
echo 🌐 URL: %SERVICE_URL%
echo 🔐 Login: %SERVICE_URL%/login.html
echo 📝 Register: %SERVICE_URL%/register.html
echo ⚡ Test Account: testuser / password123
echo ========================================
echo.

REM Cleanup local images to save space
echo 🧹 Cleaning up local images...
docker image rm %IMAGE_NAME%:%VERSION% >nul 2>&1
docker image rm %IMAGE_NAME%:latest >nul 2>&1
echo ✅ Cleanup complete

echo 🎯 Deployment completed successfully at %date% %time%