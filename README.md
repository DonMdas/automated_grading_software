# 🎓 AI-Powered Automated Grading Software

An intelligent, comprehensive automated grading platform that leverages AI, machine learning, and OCR technologies to streamline the evaluation of student submissions. This system integrates seamlessly with Google Classroom and provides a robust web-based interface for educators to manage assessments efficiently.

## 🌟 Features

- **🔗 Google Classroom Integration**: Seamlessly fetches assignments and student submissions from Google Classroom
- **🤖 AI-Powered Grading**: Advanced machine learning models (KNN, SVM, Logistic Regression, etc.) for automated assessment
- **📱 Modern Web Interface**: Responsive, Bootstrap-based UI for instructors and administrators
- **📊 Advanced Analytics**: Comprehensive dashboards for performance tracking and insights
- **🔍 OCR Technology**: Intelligent text extraction from PDF submissions using Tesseract
- **🏗️ Hybrid Database Architecture**: PostgreSQL for structured data, MongoDB for flexible document storage
- **🐳 Containerized Deployment**: Full Docker support with multi-service orchestration
- **🔄 Background Processing**: Asynchronous grading pipeline for handling large submission volumes
- **👁️ Annotation Tools**: Prodigy integration for manual review and human-in-the-loop workflows
- **🎯 Multiple ML Models**: Support for various grading algorithms with hyperparameter tuning

## 🏗️ System Architecture

The platform uses a microservices architecture with the following components:

- **Main Application** (`ai-grading-app`): FastAPI backend serving the web interface
- **Grading Service** (`grading-service`): Dedicated ML pipeline service for automated evaluation
- **Database Layer**: Hybrid PostgreSQL + MongoDB for optimal data management
- **Web Server**: Nginx reverse proxy for load balancing and static file serving
- **OCR Engine**: Tesseract-based text extraction service

## 📁 Repository Structure & Contributors

### 📂 Root Directory - Backend Core (Contributor: **Pratik**)
```
├── main.py                    # Main FastAPI application entry point
├── api/                       # REST API endpoint definitions
│   ├── auth.py               # Authentication and authorization
│   ├── classroom.py          # Google Classroom integration
│   ├── evaluation.py         # Assessment management
│   ├── grading.py            # Grading workflow endpoints
│   ├── results.py            # Results retrieval and display
│   ├── submissions.py        # Submission handling
│   ├── grade_editing.py      # Manual grade adjustments
│   ├── profile.py            # User profile management
│   └── analytics.py          # Analytics and reporting
├── services/                  # Business logic layer
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS, JavaScript, and assets
├── config.py                  # Application configuration
├── database.py               # Database initialization and management
├── requirements.txt          # Python dependencies
└── docker-compose.yml        # Multi-service orchestration
```

### 🧠 AI Grading Pipeline (Contributor: **Don**)
```
├── grading-fastapi/          # Dedicated grading microservice
│   ├── main_api.py           # Grading service API endpoints
│   ├── main_pipeline/        # Core ML grading pipeline
│   │   ├── v1/              # Original pipeline implementation
│   │   ├── v2/              # Enhanced pipeline with API integration
│   │   ├── config.yaml      # Pipeline configuration
│   │   ├── main.py          # Pipeline orchestrator
│   │   └── view_annotations.py # Prodigy annotation viewer
│   ├── Model_files/          # ML model configuration files
│   ├── Saved_models/         # Pre-trained model artifacts
│   ├── Training_models/      # Model training scripts
│   ├── exam_data_storage/    # Sample exam data and submissions
│   └── answer_key_embeddings.py # Semantic similarity processing
└── Training data/            # Model training datasets and scripts
    ├── grade_prediction_knearest.py # KNN model training
    ├── Processed Answer/     # Structured training data
    └── Raw Answers/          # Original source materials
```

### 👁️ OCR & Data Collection (Contributor: **Satwik**)
```
├── ocr_code/                 # Optical Character Recognition module
│   ├── extract_answer_key.py # Answer key PDF processing
│   ├── studentanswer.py     # Student submission text extraction
│   └── README.md            # OCR module documentation
└── Training data/           # Data collection and preparation
    ├── Raw Answers/         # Original collected data
    │   ├── CBSE 9 MLQB - English Language & Literature.pdf
    │   ├── Item-Bank-----English---Class-9 rubric.pdf
    │   └── supportmaterialeng9.pdf
    └── Processed Answer/    # Cleaned and structured datasets
```

### 🗄️ Database Architecture (Contributor: **Abhin S**)
```
├── Abhin_S/                 # Database design and schema
│   ├── DATABASE_README.md   # Comprehensive database documentation
│   ├── SCHEMA.md           # Detailed schema specifications
│   ├── Full_Hybrid_ER.png  # Complete entity-relationship diagram
│   └── Postgres_ER.png     # PostgreSQL schema visualization
└── Database management scripts:
    ├── init_db.py          # Database initialization
    ├── migrate_data.py     # Data migration utilities
    ├── check_mongo_results.py # MongoDB result verification
    └── direct_mongodb_update.py # Direct database operations
```

### 🎨 Full-Featured UI (Contributor: **Pratik**)
```
├── Pratik_UI/               # Complete frontend implementation
│   ├── backend/            # FastAPI backend services
│   ├── frontend/           # Bootstrap-based responsive UI
│   ├── grading-fastapi/    # Integrated grading service
│   ├── create_postgre_schema.py # Database schema setup
│   ├── integration_test.py # End-to-end testing
│   ├── test_connector.py   # Database connectivity tests
│   └── README.md           # UI development documentation
```

### 📚 Training Data & ML Models (Contributors: **Don** & **Satwik**)
```
├── Training data/           # Root-level training datasets and model development
│   ├── grade_prediction_knearest.py # K-Nearest Neighbors model training script
│   ├── README.md           # Training documentation and methodology
│   ├── Processed Answer/   # Structured and cleaned training datasets
│   │   ├── answer_key.json # Structured answer keys with ideal responses
│   │   ├── answer_key_with_structure.json # Enhanced answer keys with key points
│   │   ├── student_answer.json # Categorized student responses by grade (0-10)
│   │   └── student_answer_with_structure.json # Structured student responses
│   └── Raw Answers/        # Original source materials and data collection
│       ├── CBSE 9 MLQB - English Language & Literature.pdf
│       ├── Item-Bank-----English---Class-9 rubric.pdf
│       └── supportmaterialeng9.pdf
```
**Purpose**: This folder contains the foundational training data used to develop and train the machine learning models for automated grading. It includes both raw source materials collected by Satwik and processed datasets used by Don for model training. The KNN model training script demonstrates hyperparameter tuning using GridSearchCV and evaluates model performance with classification reports.

### 🔧 Utility Scripts & Configuration
```
├── background_tasks.py      # Asynchronous task processing
├── auth.py                 # Authentication utilities
├── health_check.py         # System health monitoring
├── diagnose_grading.py     # Grading pipeline diagnostics
├── package_installer.py   # Dependency management
├── setup-server.sh         # Server deployment script
├── nginx.conf             # Web server configuration
└── Dockerfile             # Container build instructions
```

## 🚀 Getting Started

### 📋 Prerequisites

- **Docker & Docker Compose**: Latest version for containerized deployment
- **Python 3.8+**: For local development and testing
- **Google Cloud Project**: With Google Classroom API enabled
- **System Dependencies**:
  - Poppler (for PDF processing)
  - Tesseract OCR Engine
  - Git for version control

### 🛠️ Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd automated_grading_software
   ```

2. **Environment Configuration**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env file with your credentials
   nano .env
   ```

3. **Docker Deployment** (Recommended)
   ```bash
   # Build and start all services
   docker-compose up --build
   
   # Run in background
   docker-compose up -d --build
   ```

4. **Local Development Setup**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate  # Windows
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Initialize database
   python init_db.py
   
   # Start development server
   python main.py
   ```

### ⚙️ Configuration

#### Required Environment Variables
```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=grading_platform
MONGODB_HOST=localhost
MONGODB_DATABASE=grading_results

# Google OAuth Setup
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret

# ML Pipeline Configuration
GRADING_SERVICE_URL=http://localhost:8001
OPENAI_API_KEY=your_openai_key  # For LLM-based grading
```

#### Google Cloud Setup
1. Create a Google Cloud Project
2. Enable Google Classroom API
3. Create OAuth 2.0 credentials
4. Add authorized redirect URIs
5. Download client secrets and configure environment

## 💻 Usage

### Web Interface
1. **Access the platform**: Navigate to `http://localhost:8000`
2. **Authentication**: Sign in with your Google account
3. **Course Selection**: Choose from your Google Classroom courses
4. **Assignment Management**: View and manage course assignments
5. **Grading Workflow**: 
   - Upload answer keys (PDF format)
   - Process student submissions
   - Trigger automated grading
   - Review and adjust results
6. **Analytics Dashboard**: Monitor performance and generate reports

### API Usage
The platform provides a comprehensive REST API documented with Swagger UI at `http://localhost:8000/docs`.

#### Key Endpoints
```bash
# Authentication
POST /auth/login              # Google OAuth login
POST /auth/logout             # User logout

# Course Management
GET /api/classroom/courses    # List user's courses
GET /api/classroom/coursework/{course_id}  # Get course assignments

# Submission Handling
POST /api/submissions/load/{course_id}/{coursework_id}  # Load submissions
GET /api/submissions/{coursework_id}  # Get submission details

# Grading Pipeline
POST /api/grading/start-grading/{coursework_id}  # Initiate grading
GET /api/grading/status/{job_id}  # Check grading progress
POST /api/grading/upload-answer-key  # Upload answer key

# Results & Analytics
GET /api/results/{coursework_id}  # Retrieve grading results
GET /api/analytics/dashboard  # Analytics dashboard data
PUT /api/grade-editing/update  # Manual grade adjustments
```

### CLI Tools & Scripts

#### Database Management
```bash
# Initialize fresh database
python init_db.py

# Check database health
python health_check.py

# Migrate existing data
python migrate_data.py

# Inspect MongoDB results
python check_mongo_results.py
```

#### Grading Pipeline
```bash
# Diagnose grading issues
python diagnose_grading.py

# Manual grading trigger
python manual_trigger_grading.py

# Fix stale grading jobs
python fix_stale_grading.py
```

#### OCR Processing
```bash
# Extract answer key from PDF
python ocr_code/extract_answer_key.py <pdf_path> <output_json>

# Process student answer sheet
python ocr_code/studentanswer.py <pdf_path> <output_json>
```

#### Model Training
```bash
# Train KNN grading model
python "Training data/grade_prediction_knearest.py"

# Access Prodigy annotation interface
python grading-fastapi/main_pipeline/view_annotations.py <data_folder>
```

## 🔧 Development Guide

### Setting Up Development Environment

1. **Backend Development**
   ```bash
   # Install development dependencies
   pip install -r requirements-dev.txt
   
   # Run with auto-reload
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
   # Run tests
   pytest tests/
   ```

2. **Frontend Development**
   ```bash
   # Navigate to UI directory
   cd Pratik_UI/frontend
   
   # Install frontend dependencies
   npm install
   
   # Start development server
   npm run dev
   ```

3. **Grading Service Development**
   ```bash
   # Navigate to grading service
   cd grading-fastapi
   
   # Start grading service
   uvicorn main_api:app --reload --port 8001
   ```

### Code Structure Guidelines

#### Adding New API Endpoints
1. Create endpoint in appropriate `api/` module
2. Add business logic to `services/`
3. Update database models if needed
4. Add tests in `tests/`
5. Update API documentation

#### Extending ML Pipeline
1. Add new models to `grading-fastapi/Saved_models/`
2. Update pipeline configuration in `config.yaml`
3. Create training scripts in `Training_models/`
4. Test with sample data in `exam_data_storage/`

#### Database Schema Changes
1. Update models in respective database modules
2. Create migration scripts
3. Update ER diagrams in `Abhin_S/`
4. Test with sample data

### Testing

```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_api.py
pytest tests/test_grading.py
pytest tests/test_ocr.py

# Run with coverage
pytest --cov=api tests/

# Integration tests
python Pratik_UI/integration_test.py
```

## 🐳 Deployment

### Production Deployment

1. **Environment Setup**
   ```bash
   # Create production environment file
   cp .env.example .env.prod
   
   # Configure production values
   nano .env.prod
   ```

2. **Docker Production Build**
   ```bash
   # Build production images
   docker-compose -f docker-compose.yml build
   
   # Deploy with production configuration
   docker-compose -f docker-compose.yml up -d
   ```

3. **Server Setup Script**
   ```bash
   # Automated server setup
   chmod +x setup-server.sh
   ./setup-server.sh
   ```

### SSL Configuration
Update `nginx.conf` for HTTPS:
```nginx
server {
    listen 443 ssl;
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    # Additional SSL configuration
}
```

### Monitoring & Maintenance
- **Health Checks**: `python health_check.py`
- **Log Monitoring**: `docker-compose logs -f`
- **Database Backups**: Automated scripts in deployment folder
- **Performance Monitoring**: Built-in analytics dashboard

## 🤝 Contributing

### Team Contributors

- **Pratik**: Backend API development, UI/UX design, frontend implementation
- **Don**: ML pipeline architecture, grading algorithms, model training
- **Satwik**: OCR implementation, data collection, annotation tools
- **Abhin S**: Database design, schema optimization, data architecture

### Contribution Guidelines

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-feature`
3. **Follow code standards**: PEP 8 for Python, ESLint for JavaScript
4. **Add tests** for new functionality
5. **Update documentation** as needed
6. **Submit pull request** with detailed description

### Code Review Process
- All changes require review from at least one team member
- Automated tests must pass
- Documentation must be updated
- Performance impact should be considered

## 📊 Performance & Analytics

The platform includes comprehensive analytics for:
- **Grading Accuracy**: Model performance metrics
- **Processing Speed**: Pipeline execution times
- **User Engagement**: Dashboard usage statistics
- **System Health**: Resource utilization monitoring

## 🔒 Security Features

- **OAuth 2.0 Authentication** with Google
- **JWT Token Management** for session security
- **Role-based Access Control** (RBAC)
- **Input Validation** and sanitization
- **SQL Injection Protection** through ORM
- **CORS Configuration** for API security

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues, questions, or contributions:
1. Check existing issues in the repository
2. Create new issue with detailed description
3. Contact the development team
4. Refer to individual component READMEs for specific guidance

---

**Built with ❤️ by the AI Grading Platform Team**