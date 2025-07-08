#!/bin/bash
# Docker Build Test Script

set -e

echo "🐳 Testing Docker configuration for AI Grading Software..."

# Check if required files exist
echo "📁 Checking required files..."
required_files=("Dockerfile" "docker-compose.yml" "requirements.txt" "main.py")
for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✅ $file exists"
    else
        echo "❌ $file is missing"
        exit 1
    fi
done

# Check if .env file exists
if [[ -f ".env" ]]; then
    echo "✅ .env file exists"
else
    echo "⚠️  .env file not found. Copy .env.docker to .env and configure it."
    echo "   cp .env.docker .env"
    echo "   # Then edit .env with your actual values"
fi

# Build main application image
echo "🔨 Building main application image..."
docker build -t ai-grading-app -f Dockerfile .

# Test that image was created successfully
echo "📋 Listing created images..."
docker images | grep "ai-grading-app"

echo ""
echo "✅ Docker build test completed successfully!"
echo ""
echo "To run the application:"
echo "1. Copy .env.docker to .env and configure your environment variables"
echo "2. Run: docker-compose up -d"
echo "3. Access the application at http://localhost:8000"
echo ""
echo "Available compose configurations:"
echo "  • docker-compose.yml        - Full production setup with databases"
echo "  • docker-compose.dev.yml    - Development mode (external databases)"
echo ""
echo "Examples:"
echo "  docker-compose up -d                           # Full setup"
echo "  docker-compose -f docker-compose.dev.yml up   # Dev mode"
