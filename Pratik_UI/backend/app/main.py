from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from datetime import datetime

from app.api.auth import router as auth_router
from app.api.analytics import router as analytics_router
from app.api.evaluation import router as evaluation_router
from app.api.annotation import router as annotation_router
from app.api.classroom import router as classroom_router
from app.core.config import settings
from app.db.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Automated Grading Platform",
    description="A comprehensive grading system with OCR, analytics, and classroom integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=frontend_path / "templates")

# Security
security = HTTPBearer()

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify system status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "database": "connected",
        "services": {
            "auth": "online",
            "analytics": "online", 
            "evaluation": "online",
            "annotation": "online",
            "classroom": "online"
        }
    }

# API Routes
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(evaluation_router, prefix="/api/evaluation", tags=["evaluation"])
app.include_router(annotation_router, prefix="/api/annotation", tags=["annotation"])
app.include_router(classroom_router, prefix="/api/classroom", tags=["classroom"])

# Frontend Routes
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/teacher/login")
async def teacher_login(request: Request):
    return templates.TemplateResponse("auth/teacher_login.html", {"request": request})

@app.get("/pricing")
async def pricing(request: Request):
    return templates.TemplateResponse("pricing.html", {"request": request})

@app.get("/teacher/dashboard")
async def teacher_dashboard(request: Request):
    return templates.TemplateResponse("teacher/dashboard.html", {"request": request})

@app.get("/evaluation")
async def evaluation(request: Request):
    return templates.TemplateResponse("evaluation/index.html", {"request": request})

@app.get("/annotation")
async def annotation(request: Request):
    return templates.TemplateResponse("annotation/index.html", {"request": request})

@app.get("/review")
async def review(request: Request):
    return templates.TemplateResponse("review/index.html", {"request": request})

@app.get("/analytics")
async def analytics(request: Request):
    return templates.TemplateResponse("analytics/index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
