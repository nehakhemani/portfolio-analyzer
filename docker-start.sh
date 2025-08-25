#!/bin/bash
# Portfolio Analyzer Docker Startup Script
# Choose deployment mode: local, production, or cloud-test

MODE=${1:-local}

case $MODE in
    "local")
        echo "🚀 Starting Portfolio Analyzer in LOCAL DEVELOPMENT mode..."
        echo "📊 Features: Hot reloading, debug mode, mounted source code"
        echo "🌐 Access: http://localhost:8080"
        docker-compose -f docker-compose.local.yml up --build
        ;;
    
    "prod"|"production")
        echo "🚀 Starting Portfolio Analyzer in PRODUCTION mode..."
        echo "📊 Features: Optimized build, persistent volumes, resource limits"
        echo "🌐 Access: http://localhost:8080"
        docker-compose -f docker-compose.yml up --build -d
        echo "✅ Started in background. Use 'docker-compose logs -f' to view logs"
        ;;
    
    "cloud"|"cloud-test")
        echo "🚀 Starting Portfolio Analyzer in CLOUD TEST mode..."
        echo "📊 Features: Cloud-ready configuration for local testing"
        echo "🌐 Access: http://localhost:8080"
        docker-compose -f docker-compose.cloud.yml up --build
        ;;
    
    "stop")
        echo "🛑 Stopping all Portfolio Analyzer containers..."
        docker-compose -f docker-compose.local.yml down 2>/dev/null || true
        docker-compose -f docker-compose.yml down 2>/dev/null || true
        docker-compose -f docker-compose.cloud.yml down 2>/dev/null || true
        ;;
    
    *)
        echo "Usage: $0 {local|production|cloud-test|stop}"
        echo ""
        echo "Modes:"
        echo "  local      - Development mode with hot reloading"
        echo "  production - Production mode with optimization"
        echo "  cloud-test - Test cloud configuration locally"
        echo "  stop       - Stop all containers"
        exit 1
        ;;
esac