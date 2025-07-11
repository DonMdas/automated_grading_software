# AI Grading Software

This repository contains the source code for an AI-powered grading software that automates the evaluation of student submissions. The platform integrates with Google Classroom, uses various machine learning models for grading, and provides a web-based interface for instructors.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Deployment](#deployment)
- [Scripts and Utilities](#scripts-and-utilities)

## Features

- **Google Classroom Integration**: Fetches assignments and student submissions directly from Google Classroom.
- **Automated Grading**: Utilizes machine learning models to grade submissions automatically.
- **Multiple ML Models**: Supports a variety of models, including KNN, SVM, Logistic Regression, and more.
- **Web-Based UI**: A simple interface for instructors to manage courses, view submissions, and trigger grading.
- **RESTful API**: A comprehensive API for programmatic access to the system's features.
- **Dockerized Deployment**: Comes with Docker and Docker Compose configurations for easy setup and deployment.
- **OCR Capabilities**: Extracts text from PDF submissions for analysis.

## Architecture

The application is composed of several services, orchestrated using Docker Compose:

- **`ai-grading-app`**: The main FastAPI application that serves the web interface and handles user interactions.
- **`grading-service`**: A separate FastAPI service dedicated to running the grading pipeline and machine learning models.
- **`nginx`**: A reverse proxy for the application.

The system uses a PostgreSQL database for storing metadata and a MongoDB database for storing grading results.

## Project Structure

Here's a high-level overview of the most important files and directories:

```
.
├── api/                  # API endpoint definitions
├── grading-fastapi/      # Code for the grading service
│   ├── main_pipeline/    # The core grading pipeline
│   ├── Model_files/      # Files for the ML models
│   └── Saved_models/     # Trained ML models
├── ocr_code/             # Optical Character Recognition (OCR) scripts
├── services/             # Business logic and services
├── static/               # Static assets (CSS, JS)
├── templates/            # HTML templates for the web UI
├── main.py               # Main application entry point
├── requirements.txt      # Python dependencies
├── Dockerfile            # Dockerfile for the main application
├── Dockerfile.grading    # Dockerfile for the grading service
└── docker-compose.yml    # Docker Compose configuration
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- A Google Cloud project with the Google Classroom API enabled

### Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd ai_grading_software
   ```

2. **Set up the environment:**

   Create a `.env` file by copying the `.env.example` file and filling in the required values, including your Google API credentials.

3. **Build and run the application using Docker Compose:**

   ```bash
   docker-compose up --build
   ```

   This will start all the services, including the main application, the grading service, and the database.

### Configuration

The application is configured through environment variables. Key variables include:

- `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: PostgreSQL connection details.
- `MONGODB_HOST`, `MONGODB_DATABASE`: MongoDB connection details.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`: Google OAuth credentials.
- `SECRET_KEY`: A secret key for signing sessions.

## Usage

Once the application is running, you can access the web interface at `http://localhost:8000`. From there, you can:

1.  Log in with your Google account.
2.  Select a course from your Google Classroom.
3.  View the assignments and student submissions.
4.  Trigger the grading process for individual or all submissions.
5.  View the grading results.

## API Endpoints

The application provides a RESTful API for interacting with the system. The API is documented using Swagger UI, which is available at `http://localhost:8000/docs`.

Key endpoints include:

- `/api/classroom/courses`: Get a list of courses.
- `/api/submissions/load/{course_id}/{coursework_id}`: Load submissions for an assignment.
- `/api/grading/start-grading/{coursework_id}`: Start the grading process.
- `/api/results/{coursework_id}`: Get the grading results.

## Deployment

The included `docker-compose.yml` file is suitable for a production-like deployment. For a full production setup, you may need to adjust the configuration, such as setting up a more robust database and handling SSL termination at the `nginx` level.

The `deploy.sh` and `setup-server.sh` scripts provide a starting point for automating deployment.

## Scripts and Utilities

The repository includes several utility scripts for various tasks:

- `init_db.py`: Initializes the database schema.
- `check_mongo_results.py`: Checks the results in the MongoDB database.
- `diagnose_grading.py`: Helps diagnose issues with the grading process.
- `migrate_data.py`: A script for migrating data.
- `backup.sh`: A simple script for backing up data.