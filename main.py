"""
Main application file for the AI Studio application.
This file sets up the FastAPI app and includes all the route modules.
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from config import STATIC_DIR, TEMPLATES_DIR
from database import initialize_databases

# Import all API routers
from api.auth import router as auth_router
from api.classroom import router as classroom_router
from api.evaluation import router as evaluation_router
from api.grading import router as grading_router
from api.results import router as results_router
from api.submissions import router as submissions_router
from api.grade_editing import router as grade_editing_router
from api.profile import router as profile_router
# from api.analytics import router as analytics_router
from api.analytics_no_auth import router as analytics_router  # Use no-auth version for testing

# Create FastAPI app
app = FastAPI(
    title="AI Studio Grading Platform",
    description="An automated grading platform for educational assessments",
    version="1.0.0"
)

# Create database tables on startup
@app.on_event("startup")
def on_startup():
    print("🚀 Initializing databases...")
    initialize_databases()
    print("✅ Database initialization completed!")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include all API routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(classroom_router, tags=["Google Classroom"])
app.include_router(evaluation_router, tags=["Evaluation"])
app.include_router(grading_router, tags=["Grading"])
app.include_router(results_router, tags=["Results"])
app.include_router(submissions_router, tags=["Submissions"])
app.include_router(grade_editing_router, tags=["Grade Editing"])
app.include_router(profile_router, tags=["Profile"])
app.include_router(analytics_router, tags=["Analytics"])

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for Docker and load balancers"""
    return {"status": "healthy", "service": "ai-grading-software"}

# API Root endpoint for API documentation
@app.get("/api")
async def api_root():
    return {"message": "AI Studio Grading Platform API", "version": "1.0.0"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-studio-grading-platform"}

# HTML Page Routes - Serve frontend files
@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the index page at root."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_frontend(request: Request, full_path: str):
    """Serve frontend HTML files."""
    path = full_path
    
    # Check if it's a template file
    template_path = os.path.join(TEMPLATES_DIR, path)
    if os.path.isfile(template_path):
        return templates.TemplateResponse(path, {"request": request})
    
    # Check if it's an auth file
    if "auth/" in path and os.path.isfile(os.path.join(TEMPLATES_DIR, "auth", path.split('/')[-1])):
        return templates.TemplateResponse(f"auth/{path.split('/')[-1]}", {"request": request})
    
    # Default to index.html for unknown paths
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
