@echo off
REM Local Testing Script for Portfolio Analyzer
echo.
echo 🧪 Testing Portfolio Analyzer Locally
echo ====================================
echo.

REM Start local development environment
echo 🚀 Starting local development environment...
docker-compose -f docker-compose.local.yml up --build -d

REM Wait for application to start
echo 📦 Waiting for application to start...
timeout /t 10 /nobreak >nul

REM Health check
echo 🏥 Health Check:
curl -s http://localhost:8080/health | python -m json.tool
echo.

REM Authentication check
echo 🔐 Authentication Check:
curl -s http://localhost:8080/api/check-auth | python -m json.tool
echo.

REM Test login
echo 🔑 Test Login with Demo User:
curl -s -X POST http://localhost:8080/api/auth/login -H "Content-Type: application/json" -d "{\"username\": \"testuser\", \"password\": \"password123\"}" | python -m json.tool
echo.

echo ✅ Local testing complete!
echo.
echo 🌐 Access URLs:
echo   Main App: http://localhost:8080
echo   Login: http://localhost:8080/login.html
echo   Register: http://localhost:8080/register.html
echo.
echo 💡 Use 'docker-compose -f docker-compose.local.yml down' to stop
echo.