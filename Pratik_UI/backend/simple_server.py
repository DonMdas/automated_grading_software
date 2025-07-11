#!/usr/bin/env python3
"""
Simple backend server for AI Grading Platform
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="AI Grading Platform")

# Get the absolute paths
backend_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(os.path.dirname(backend_dir), "frontend")
static_dir = os.path.join(frontend_dir, "static")
templates_dir = os.path.join(frontend_dir, "templates")

print(f"Backend dir: {backend_dir}")
print(f"Frontend dir: {frontend_dir}")
print(f"Static dir: {static_dir}")
print(f"Templates dir: {templates_dir}")

# Mount static files
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    print("✅ Static files mounted")
else:
    print("❌ Static directory not found")

# Basic routes
@app.get("/")
async def read_root():
    index_path = os.path.join(templates_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Grading Platform Backend Running"}

@app.get("/evaluation")
async def evaluation():
    eval_path = os.path.join(templates_dir, "evaluation.html")
    if os.path.exists(eval_path):
        return FileResponse(eval_path)
    return {"message": "Evaluation page"}

@app.get("/analytics")
async def analytics():
    analytics_path = os.path.join(templates_dir, "analytics", "analytics.html")
    if os.path.exists(analytics_path):
        return FileResponse(analytics_path)
    return {"message": "Analytics page"}

@app.get("/pricing")
async def pricing():
    pricing_path = os.path.join(templates_dir, "pricing.html")
    if os.path.exists(pricing_path):
        return FileResponse(pricing_path)
    return {"message": "Pricing page"}

@app.get("/auth/teacher_login.html")
async def teacher_login():
    login_path = os.path.join(templates_dir, "auth", "teacher_login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return {"message": "Teacher login page"}

@app.get("/auth/teacher_signup.html")
async def teacher_signup():
    signup_path = os.path.join(templates_dir, "auth", "teacher_signup.html")
    if os.path.exists(signup_path):
        return FileResponse(signup_path)
    return {"message": "Teacher signup page"}

# Google OAuth mock endpoint
@app.get("/api/auth/google")
async def google_auth():
    # Simple mock - redirect back with fake token
    return RedirectResponse(url="/evaluation?token=mock_token_123&google_auth=success")

# Mock API endpoints
@app.get("/api/auth/me")
async def get_current_user():
    return {
        "id": 1,
        "email": "teacher@example.com",
        "full_name": "Test Teacher",
        "google_connected": True,
        "profile_picture": None
    }

@app.get("/api/classroom/courses")
async def get_courses():
    return {
        "courses": [
            {"id": "1", "name": "Mathematics 101", "students": 25},
            {"id": "2", "name": "Science Lab", "students": 20}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AI Grading Platform Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
