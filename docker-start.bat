@echo off
REM Portfolio Analyzer Docker Startup Script for Windows
REM Choose deployment mode: local, production, or cloud-test

set MODE=%1
if "%MODE%"=="" set MODE=local

if "%MODE%"=="local" goto local
if "%MODE%"=="prod" goto production
if "%MODE%"=="production" goto production
if "%MODE%"=="cloud" goto cloud
if "%MODE%"=="cloud-test" goto cloud
if "%MODE%"=="stop" goto stop
goto usage

:local
echo 🚀 Starting Portfolio Analyzer in LOCAL DEVELOPMENT mode...
echo 📊 Features: Hot reloading, debug mode, mounted source code
echo 🌐 Access: http://localhost:8080
docker-compose -f docker-compose.local.yml up --build
goto end

:production
echo 🚀 Starting Portfolio Analyzer in PRODUCTION mode...
echo 📊 Features: Optimized build, persistent volumes, resource limits
echo 🌐 Access: http://localhost:8080
docker-compose -f docker-compose.yml up --build -d
echo ✅ Started in background. Use 'docker-compose logs -f' to view logs
goto end

:cloud
echo 🚀 Starting Portfolio Analyzer in CLOUD TEST mode...
echo 📊 Features: Cloud-ready configuration for local testing
echo 🌐 Access: http://localhost:8080
docker-compose -f docker-compose.cloud.yml up --build
goto end

:stop
echo 🛑 Stopping all Portfolio Analyzer containers...
docker-compose -f docker-compose.local.yml down >nul 2>&1
docker-compose -f docker-compose.yml down >nul 2>&1
docker-compose -f docker-compose.cloud.yml down >nul 2>&1
goto end

:usage
echo Usage: %0 {local^|production^|cloud-test^|stop}
echo.
echo Modes:
echo   local      - Development mode with hot reloading
echo   production - Production mode with optimization
echo   cloud-test - Test cloud configuration locally
echo   stop       - Stop all containers

:end