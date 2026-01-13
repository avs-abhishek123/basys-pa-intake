#!/bin/bash

# Quick start script for Basys PA Intake system

echo "====================================="
echo "Basys PA Intake - Quick Start"
echo "====================================="
echo ""

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed"
    echo "Please install Docker and docker-compose first"
    exit 1
fi

echo "✓ Docker and docker-compose found"
echo ""

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo ""
echo "Waiting for services to start (30 seconds)..."
sleep 30

# Check health
echo ""
echo "Checking service health..."
HEALTH_CHECK=$(curl -s http://localhost:3000/health)
if [ $? -eq 0 ]; then
    echo "✓ API is healthy"
else
    echo "❌ API health check failed"
    echo "Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "====================================="
echo "✓ System is ready!"
echo "====================================="
echo ""
echo "Service URLs:"
echo "  API:     http://localhost:3000"
echo "  Health:  http://localhost:3000/health"
echo "  Metrics: http://localhost:3000/metrics"
echo ""
echo "Quick Test:"
echo "  curl http://localhost:3000/health"
echo ""
echo "To run tests:"
echo "  cd tests"
echo "  pip install -r requirements.txt"
echo "  python test_idempotency.py"
echo "  python test_retry_dlq.py"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop:"
echo "  docker-compose down"
echo ""
