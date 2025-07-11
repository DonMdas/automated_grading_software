# AI Automated Grading Platform

A lightweight automated grading system built with FastAPI backend and Bootstrap frontend.

## Features

### Frontend
- Teacher Sign-in
- Pricing page
- Software information UI
- Analytics dashboard (for developers and teachers)
- Evaluation interface
- Annotation tools
- Review/Human-in-the-loop interface
- Google Classroom integration

### Backend
- FastAPI REST API
- Database integration (PostgreSQL/SQLite/MongoDB)
- OCR integration
- Text preprocessing and cleaning
- Grading engine
- Prodigy integration for PDF annotation

### DevOps
- GitHub/GitLab container setup
- CI/CD pipeline with testing
- Docker configuration
- Automated testing with pytest

## Project Structure

```
grading_platform/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   └── templates/
├── docker-compose.yml
├── .github/
│   └── workflows/
└── docs/
```

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. Run the development server:
   ```bash
   cd backend && uvicorn app.main:app --reload
   ```

3. Open http://localhost:8000 in your browser

## Technologies

- **Backend**: FastAPI, SQLAlchemy, Alembic
- **Frontend**: Bootstrap 5, Vanilla JavaScript
- **Database**: PostgreSQL/SQLite/MongoDB
- **Testing**: Pytest, unittest
- **OCR**: Tesseract
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions
