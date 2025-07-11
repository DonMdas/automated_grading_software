

# AI-Powered Exam Grading FastAPI - Don

This project provides a robust FastAPI application for automated exam grading, leveraging AI and machine learning to streamline the assessment process. It's designed to handle the entire workflow, from managing exam data to processing submissions and predicting grades.

## Key Features

- **Exam Management:** Create and manage exams through a simple and intuitive API.
- **Flexible Data Upload:** Easily upload answer keys and student submissions.
- **Automated Grading Pipeline:** A powerful, multi-stage pipeline processes and grades exams automatically.
- **Machine Learning-Powered Grading:** Utilizes a variety of machine learning models to predict grades, ensuring accuracy and consistency.
- **Prodigy Integration:** Seamlessly integrates with Prodigy for viewing and annotating grading data.
- **Background Processing:** Handles intensive grading tasks in the background to prevent API timeouts and ensure a smooth user experience.
- **Dual Pipeline Versions:** Offers two versions of the grading pipeline (v1 and v2) one for running the LLM locally for grading and the other is access the LLM via API calls.
## Project Structure

The project is organized into the following key directories:

- **`main_api.py`:** The core FastAPI application, defining all API endpoints.
- **`exam_data_storage/`:** Contains sample exam data, including answer keys and student answers.
- **`main_pipeline/`:** The heart of the grading engine, with two distinct pipeline versions:
    - **`v1/`:** The original grading pipeline.
    - **`v2/`:** The latest and recommended version of the grading pipeline.
- **`Model_files/`:** Stores essential files for the machine learning models.
- **`Saved_models/`:** Contains pre-trained machine learning models for grade prediction.
- **`Training_models/`:** A suite of scripts for training various grading models.

# Viewing Annotations with Prodigy - Satwik

This project includes a command-line tool, `main_pipeline/view_annotations.py`, for viewing annotation data in Prodigy. This tool allows you to inspect the processed answer keys and student answers in a user-friendly interface.

### How it Works

The `view_annotations.py` script provides an interactive menu to select and view annotation files. You can choose to view the annotations for the answer key or for individual student submissions. When you select a file, the script automatically launches a Prodigy instance and opens a web browser to display the annotations.

### Usage

To use the annotation viewer, run the following command from the root directory of the project:

```bash
python main_pipeline/view_annotations.py <path_to_data_folder>
```

Replace `<path_to_data_folder>` with the path to the directory containing the annotation files (e.g., `exam_data_storage/mid_term`).

## Getting Started

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the FastAPI Application:**
    ```bash
    uvicorn main_api:app --reload
    ```

3.  **Interact with the API:**
    Use a tool like Swagger UI (available at `http://localhost:8000/docs`) or `curl` to interact with the API endpoints.
