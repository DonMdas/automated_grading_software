#!/bin/bash

echo "🔍 AI Grading Platform Status Check"
echo "=================================="

# Check backend
echo "🔧 Backend (Port 8000):"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ | grep -q "200"; then
    echo "  ✅ Backend is running and responding"
else
    echo "  ❌ Backend is not responding"
fi

# Check frontend
echo "🌐 Frontend (Port 3000):"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ | grep -q "200"; then
    echo "  ✅ Frontend is running and responding"
else
    echo "  ❌ Frontend is not responding"
fi

# Check specific pages
echo "📄 Page Status:"
for page in "" "evaluation" "analytics" "auth/teacher_login.html" "pricing"; do
    url="http://localhost:3000/$page"
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [ "$status" = "200" ] || [ "$status" = "301" ]; then
        echo "  ✅ /$page - Status: $status"
    else
        echo "  ❌ /$page - Status: $status"
    fi
done

echo ""
echo "🚀 Quick Start:"
echo "  • Home Page: http://localhost:3000"
echo "  • Evaluation: http://localhost:3000/evaluation"
echo "  • Analytics: http://localhost:3000/analytics"
echo "  • Teacher Login: http://localhost:3000/auth/teacher_login.html"
echo ""
echo "🔄 Navigation Test:"
echo "  Try clicking navigation links - they should work without authentication blocking!"
