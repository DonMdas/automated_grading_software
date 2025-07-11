"""
Results API endpoints for the AI Studio application.
"""

import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from config import SERVER_DATA_DIR
from db_service import db_service

router = APIRouter()

@router.get("/api/results/{coursework_id}")
async def get_coursework_results(
    coursework_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get grading results for all graded submissions in a coursework."""
    try:
        # Get all graded submissions using the new service
        graded_submissions = db_service.get_submissions_by_status(
            coursework_id, ["GRADED"]
        )
        
        if not graded_submissions:
            response_data = {
                "coursework_id": coursework_id,
                "total_graded_submissions": 0,
                "results": [],
                "message": "No graded submissions found. Please complete the grading process first."
            }
            return JSONResponse(content=response_data)
        
        results = []
        
        for submission in graded_submissions:
            try:
                # Get grading results from MongoDB
                grading_results = db_service.get_grading_results(str(submission.id))
                
                if grading_results and 'results' in grading_results:
                    results.append({
                        "student_id": submission.student.google_student_id if submission.student else "Unknown",
                        "student_name": submission.student.name if submission.student else "Unknown Student",
                        "submission_id": submission.google_submission_id,
                        "results": grading_results['results'],
                        "total_questions": grading_results.get('total_questions', len(grading_results['results']) if 'results' in grading_results else 0),
                        "submission_uuid": str(submission.id),
                        "grading_version": grading_results.get('grading_version', 'unknown'),
                        "processed_at": grading_results.get('processed_at', 'unknown')
                    })
                else:
                    # Include submissions without results for debugging
                    results.append({
                        "student_id": submission.student.google_student_id if submission.student else "Unknown",
                        "student_name": submission.student.name if submission.student else "Unknown Student", 
                        "submission_id": submission.google_submission_id,
                        "results": [],
                        "total_questions": 0,
                        "submission_uuid": str(submission.id),
                        "error": "No grading results found in MongoDB"
                    })
            except Exception as e:
                # Include error information for debugging
                results.append({
                    "student_id": submission.student.google_student_id if submission.student else "Unknown",
                    "student_name": submission.student.name if submission.student else "Unknown Student",
                    "submission_id": submission.google_submission_id,
                    "results": [],
                    "total_questions": 0,
                    "submission_uuid": str(submission.id),
                    "error": f"Error retrieving results: {str(e)}"
                })
        
        response_data = {
            "coursework_id": coursework_id,
            "total_graded_submissions": len(results),
            "results": results
        }
        return JSONResponse(content=response_data)
        
    except Exception as e:
        # Return error as JSON instead of raising exception
        response_data = {
            "coursework_id": coursework_id,
            "total_graded_submissions": 0,
            "results": [],
            "error": f"Failed to retrieve results: {str(e)}"
        }
        return JSONResponse(content=response_data)

@router.get("/api/results/{coursework_id}/{student_id}")
async def get_student_results(
    coursework_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed grading results for a specific student."""
    try:
        # Check if the submission exists and is graded
        submission = db_service.get_submission_by_student_and_assignment(
            student_id, coursework_id, status="GRADED"
        )
        
        if not submission:
            response_data = {
                "student_id": student_id,
                "coursework_id": coursework_id,
                "error": "Graded submission not found for this student",
                "results": []
            }
            return JSONResponse(content=response_data)
        
        # Get grading results from MongoDB
        grading_results = db_service.get_grading_results(str(submission.id))
        
        if not grading_results:
            response_data = {
                "student_id": student_id,
                "student_name": submission.student.name if submission.student else "Unknown",
                "coursework_id": coursework_id,
                "error": "Results not found for this student in MongoDB",
                "results": []
            }
            return JSONResponse(content=response_data)
        
        # Get answer key from MongoDB if available
        answer_key_data = None
        if hasattr(submission, 'assignment') and submission.assignment and hasattr(submission.assignment, 'exam_id'):
            answer_key_data = db_service.get_answer_key(submission.assignment.exam_id)
        
        # Fallback: try using coursework_id as exam_id (for backward compatibility)
        if not answer_key_data:
            answer_key_data = db_service.get_answer_key(coursework_id)
        
        # Final fallback: try to load from file system if MongoDB fails
        if not answer_key_data:
            try:
                from pathlib import Path
                processed_file = Path(f"server_data/{coursework_id}/answer_key_processed.json")
                if processed_file.exists():
                    import json
                    with open(processed_file, 'r') as f:
                        answer_key_data = json.load(f)
                    print(f"FALLBACK: Loaded answer key from file system for {coursework_id}")
                else:
                    # Try basic answer key as last resort
                    basic_file = Path(f"server_data/{coursework_id}/answer_key.json")
                    if basic_file.exists():
                        with open(basic_file, 'r') as f:
                            answer_key_data = json.load(f)
                        print(f"FALLBACK: Loaded basic answer key from file system for {coursework_id}")
            except Exception as fallback_error:
                print(f"Fallback loading failed: {fallback_error}")
        
        # Parse the results for better presentation
        parsed_results = []
        results_list = grading_results.get('results', []) if isinstance(grading_results, dict) else grading_results
        
        # Track scores for summary calculation
        total_score = 0
        max_possible_score = 0
        
        if isinstance(results_list, list):
            for result in results_list:
                try:
                    question_id = result.get("meta", {}).get("id", "Unknown") if isinstance(result, dict) else "Unknown"
                    
                    # Get corresponding answer key and structure components
                    answer_key_item = {}
                    expected_structure_components = []
                    expected_answer_text = ""
                    
                    if answer_key_data and isinstance(answer_key_data, dict):
                        answer_key_item = answer_key_data.get(question_id, {})
                        expected_answer_text = answer_key_item.get("answer", "")
                        
                        # Extract structure components if they exist
                        structure_data = answer_key_item.get("structure", {})
                        if isinstance(structure_data, dict):
                            expected_structure_components = []
                            for component_key, component_data in structure_data.items():
                                if isinstance(component_data, dict) and "content" in component_data:
                                    expected_structure_components.append({
                                        "label": component_key,
                                        "content": component_data["content"]
                                    })
                                elif isinstance(component_data, str):
                                    expected_structure_components.append({
                                        "label": component_key,
                                        "content": component_data
                                    })
                    
                    # Extract grade information
                    predicted_grade = result.get("meta", {}).get("predicted_grade", "0") if isinstance(result, dict) else "0"
                    manual_grade = result.get("meta", {}).get("manual_grade", None) if isinstance(result, dict) else None
                    
                    # Use manual grade if available, otherwise use predicted grade
                    final_grade = manual_grade if manual_grade is not None else float(predicted_grade)
                    
                    # Add to totals
                    total_score += final_grade
                    max_possible_score += 10  # Assuming each question is worth 10 points
                    
                    # Extract student answer structure components from spans
                    student_structure_components = []
                    spans = result.get("spans", []) if isinstance(result, dict) else []
                    
                    # Get the student answer text for span extraction
                    student_answer_text = ""
                    if isinstance(result, dict) and "meta" in result:
                        student_answer_text = result["meta"].get("original_answer", "")
                    
                    if isinstance(spans, list) and student_answer_text:
                        for span in spans:
                            if isinstance(span, dict):
                                # Handle different span formats
                                label = span.get("label", "Unknown")
                                
                                # Clean up label - remove confidence scores in parentheses
                                if "(" in label and ")" in label:
                                    label = label.split("(")[0].strip()
                                
                                # Get the text content using start/end positions
                                text = ""
                                if "start" in span and "end" in span:
                                    try:
                                        start = int(span["start"])
                                        end = int(span["end"])
                                        if start >= 0 and end <= len(student_answer_text) and start < end:
                                            text = student_answer_text[start:end].strip()
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Fallback to direct text if available
                                if not text:
                                    text = span.get("text", span.get("content", "")).strip()
                                
                                if text:
                                    student_structure_components.append({
                                        "label": label,
                                        "content": text
                                    })
                    
                    # ALWAYS ensure we have structure components if there's a student answer
                    if not student_structure_components and student_answer_text and student_answer_text.strip():
                        # Create structure components by analyzing the student answer
                        text = student_answer_text.strip()
                        
                        # Split into sentences and create meaningful components
                        sentences = [s.strip() for s in text.split('.') if s.strip() and len(s.strip()) > 5]
                        
                        if len(sentences) >= 3:
                            # Multiple sentences - create thematic components
                            student_structure_components = [
                                {"label": "opening_statement", "content": sentences[0]},
                                {"label": "main_argument", "content": sentences[1]},
                                {"label": "conclusion", "content": sentences[-1]}
                            ]
                        elif len(sentences) == 2:
                            # Two sentences
                            student_structure_components = [
                                {"label": "main_point", "content": sentences[0]},
                                {"label": "supporting_detail", "content": sentences[1]}
                            ]
                        elif len(sentences) == 1:
                            # Single sentence - check if it's long enough to split
                            if len(text) > 100:
                                # Long text - split into logical parts
                                words = text.split()
                                if len(words) > 20:
                                    mid_point = len(words) // 2
                                    first_part = ' '.join(words[:mid_point])
                                    second_part = ' '.join(words[mid_point:])
                                    student_structure_components = [
                                        {"label": "first_part", "content": first_part},
                                        {"label": "second_part", "content": second_part}
                                    ]
                                else:
                                    student_structure_components = [
                                        {"label": "main_response", "content": text}
                                    ]
                            else:
                                # Short text - use as single component
                                student_structure_components = [
                                    {"label": "student_answer", "content": text}
                                ]
                        else:
                            # No proper sentences - split by commas or use as single component
                            parts = [p.strip() for p in text.split(',') if p.strip()]
                            if len(parts) > 1:
                                student_structure_components = [
                                    {"label": f"part_{i+1}", "content": part} 
                                    for i, part in enumerate(parts[:3])
                                ]
                            else:
                                student_structure_components = [
                                    {"label": "student_response", "content": text}
                                ]
                    
                    detailed_result = {
                        "question_id": question_id,
                        "question_text": answer_key_item.get("question", result.get("meta", {}).get("question", "Unknown Question") if isinstance(result, dict) else "Unknown Question"),
                        "expected_answer": expected_answer_text,
                        "expected_structure_components": expected_structure_components,
                        "student_answer": result.get("meta", {}).get("original_answer", "") if isinstance(result, dict) else "",
                        "student_structure_components": student_structure_components,
                        "predicted_grade": predicted_grade,
                        "manual_grade": manual_grade,
                        "final_grade": final_grade,
                        "similarity_scores": {
                            "full_similarity": result.get("meta", {}).get("full_similarity_score", 0) if isinstance(result, dict) else 0,
                            "tfidf_similarity": result.get("meta", {}).get("tfidf_similarity_score", 0) if isinstance(result, dict) else 0,
                            "structure_similarity": result.get("meta", {}).get("mean_structure_similarity_score", 0) if isinstance(result, dict) else 0
                        },
                        "structure_components": result.get("meta", {}).get("total_structure_components", 0) if isinstance(result, dict) else 0,
                        "spans": result.get("spans", []) if isinstance(result, dict) else [],
                        "requires_llm_evaluation": result.get("meta", {}).get("requires_llm_evaluation", []) if isinstance(result, dict) else []
                    }
                    parsed_results.append(parsed_result)
                except Exception as e:
                    # Include problematic result with error info
                    parsed_results.append({
                        "question_id": "error",
                        "error": f"Failed to parse result: {str(e)}",
                        "raw_result": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    })
        
        # Calculate percentage
        percentage = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        
        response_data = {
            "student_id": student_id,
            "student_name": submission.student.name if submission.student else "Unknown",
            "coursework_id": coursework_id,
            "submission_id": submission.google_submission_id,
            "total_questions": len(parsed_results),
            "results": parsed_results,
            "grading_summary": {
                "total_questions": len(parsed_results),
                "total_score": total_score,
                "max_possible_score": max_possible_score,
                "percentage": percentage,
                "average_similarity": sum(r.get("similarity_scores", {}).get("full_similarity", 0) for r in parsed_results if "similarity_scores" in r) / len(parsed_results) if parsed_results else 0,
                "questions_needing_review": len([r for r in parsed_results if r.get("requires_llm_evaluation")])
            },
            "grading_version": grading_results.get('grading_version', 'unknown') if isinstance(grading_results, dict) else 'unknown'
        }
        return JSONResponse(content=response_data)
        
    except Exception as e:
        response_data = {
            "student_id": student_id,
            "coursework_id": coursework_id,
            "error": f"Failed to retrieve student results: {str(e)}",
            "results": []
        }
        return JSONResponse(content=response_data)

@router.get("/api/results/{coursework_id}/{student_id}/detailed")
async def get_detailed_student_results(
    coursework_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed grading results with answer key comparison for a specific student."""
    try:
        # Check if the submission exists and is graded
        submission = db_service.get_submission_by_student_and_assignment(
            student_id, coursework_id, status="GRADED"
        )
        
        if not submission:
            response_data = {
                "student_id": student_id,
                "coursework_id": coursework_id,
                "error": "Graded submission not found for this student",
                "detailed_results": []
            }
            return JSONResponse(content=response_data)
        
        # Get grading results from MongoDB
        grading_results = db_service.get_grading_results(str(submission.id))
        
        if not grading_results:
            # Update the submission status and return error
            db_service.update_submission_status(str(submission.id), "GRADING_FAILED")
            response_data = {
                "student_id": student_id,
                "student_name": submission.student.name if submission.student else "Unknown",
                "coursework_id": coursework_id,
                "error": "Results not found for this student. Submission status has been updated.",
                "detailed_results": []
            }
            return JSONResponse(content=response_data)
        
        # Get answer key from MongoDB
        answer_key_data = None
        if hasattr(submission, 'assignment') and submission.assignment and hasattr(submission.assignment, 'exam_id'):
            answer_key_data = db_service.get_answer_key(submission.assignment.exam_id)
        
        # Fallback: try using coursework_id as exam_id (for backward compatibility)
        if not answer_key_data:
            answer_key_data = db_service.get_answer_key(coursework_id)
        
        # Final fallback: try to load from file system if MongoDB fails
        if not answer_key_data:
            try:
                from pathlib import Path
                processed_file = Path(f"server_data/{coursework_id}/answer_key_processed.json")
                if processed_file.exists():
                    import json
                    with open(processed_file, 'r') as f:
                        answer_key_data = json.load(f)
                    print(f"FALLBACK: Loaded answer key from file system for {coursework_id}")
                else:
                    # Try basic answer key as last resort
                    basic_file = Path(f"server_data/{coursework_id}/answer_key.json")
                    if basic_file.exists():
                        with open(basic_file, 'r') as f:
                            answer_key_data = json.load(f)
                        print(f"FALLBACK: Loaded basic answer key from file system for {coursework_id}")
            except Exception as fallback_error:
                print(f"Fallback loading failed: {fallback_error}")
        
        # Parse the results for detailed presentation
        detailed_results = []
        results_list = grading_results.get('results', []) if isinstance(grading_results, dict) else grading_results
        
        # Track scores for summary calculation
        total_score = 0
        max_possible_score = 0
        
        if isinstance(results_list, list):
            for result in results_list:
                try:
                    question_id = result.get("meta", {}).get("id", "Unknown") if isinstance(result, dict) else "Unknown"
                    
                    # Get corresponding answer key and structure components
                    answer_key_item = {}
                    expected_structure_components = []
                    expected_answer_text = ""
                    
                    if answer_key_data and isinstance(answer_key_data, dict):
                        answer_key_item = answer_key_data.get(question_id, {})
                        expected_answer_text = answer_key_item.get("answer", "")
                        
                        # Extract structure components if they exist
                        structure_data = answer_key_item.get("structure", {})
                        if isinstance(structure_data, dict):
                            expected_structure_components = []
                            for component_key, component_data in structure_data.items():
                                if isinstance(component_data, dict) and "content" in component_data:
                                    expected_structure_components.append({
                                        "label": component_key,
                                        "content": component_data["content"]
                                    })
                                elif isinstance(component_data, str):
                                    expected_structure_components.append({
                                        "label": component_key,
                                        "content": component_data
                                    })
                    
                    # Extract grade information
                    predicted_grade = result.get("meta", {}).get("predicted_grade", "0") if isinstance(result, dict) else "0"
                    manual_grade = result.get("meta", {}).get("manual_grade", None) if isinstance(result, dict) else None
                    
                    # Use manual grade if available, otherwise use predicted grade
                    final_grade = manual_grade if manual_grade is not None else float(predicted_grade)
                    
                    # Add to totals
                    total_score += final_grade
                    max_possible_score += 10  # Assuming each question is worth 10 points
                    
                    # Extract student answer structure components from spans
                    student_structure_components = []
                    spans = result.get("spans", []) if isinstance(result, dict) else []
                    
                    # Get the student answer text for span extraction
                    student_answer_text = ""
                    if isinstance(result, dict) and "meta" in result:
                        student_answer_text = result["meta"].get("original_answer", "")
                    
                    if isinstance(spans, list) and student_answer_text:
                        for span in spans:
                            if isinstance(span, dict):
                                # Handle different span formats
                                label = span.get("label", "Unknown")
                                
                                # Clean up label - remove confidence scores in parentheses
                                if "(" in label and ")" in label:
                                    label = label.split("(")[0].strip()
                                
                                # Get the text content using start/end positions
                                text = ""
                                if "start" in span and "end" in span:
                                    try:
                                        start = int(span["start"])
                                        end = int(span["end"])
                                        if start >= 0 and end <= len(student_answer_text) and start < end:
                                            text = student_answer_text[start:end].strip()
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Fallback to direct text if available
                                if not text:
                                    text = span.get("text", span.get("content", "")).strip()
                                
                                if text:
                                    student_structure_components.append({
                                        "label": label,
                                        "content": text
                                    })
                    
                    # ALWAYS ensure we have structure components if there's a student answer
                    if not student_structure_components and student_answer_text and student_answer_text.strip():
                        # Create structure components by analyzing the student answer
                        text = student_answer_text.strip()
                        
                        # Split into sentences and create meaningful components
                        sentences = [s.strip() for s in text.split('.') if s.strip() and len(s.strip()) > 5]
                        
                        if len(sentences) >= 3:
                            # Multiple sentences - create thematic components
                            student_structure_components = [
                                {"label": "opening_statement", "content": sentences[0]},
                                {"label": "main_argument", "content": sentences[1]},
                                {"label": "conclusion", "content": sentences[-1]}
                            ]
                        elif len(sentences) == 2:
                            # Two sentences
                            student_structure_components = [
                                {"label": "main_point", "content": sentences[0]},
                                {"label": "supporting_detail", "content": sentences[1]}
                            ]
                        elif len(sentences) == 1:
                            # Single sentence - check if it's long enough to split
                            if len(text) > 100:
                                # Long text - split into logical parts
                                words = text.split()
                                if len(words) > 20:
                                    mid_point = len(words) // 2
                                    first_part = ' '.join(words[:mid_point])
                                    second_part = ' '.join(words[mid_point:])
                                    student_structure_components = [
                                        {"label": "first_part", "content": first_part},
                                        {"label": "second_part", "content": second_part}
                                    ]
                                else:
                                    student_structure_components = [
                                        {"label": "main_response", "content": text}
                                    ]
                            else:
                                # Short text - use as single component
                                student_structure_components = [
                                    {"label": "student_answer", "content": text}
                                ]
                        else:
                            # No proper sentences - split by commas or use as single component
                            parts = [p.strip() for p in text.split(',') if p.strip()]
                            if len(parts) > 1:
                                student_structure_components = [
                                    {"label": f"part_{i+1}", "content": part} 
                                    for i, part in enumerate(parts[:3])
                                ]
                            else:
                                student_structure_components = [
                                    {"label": "student_response", "content": text}
                                ]
                    
                    detailed_result = {
                        "question_id": question_id,
                        "question_text": answer_key_item.get("question", result.get("meta", {}).get("question", "Unknown Question") if isinstance(result, dict) else "Unknown Question"),
                        "expected_answer": expected_answer_text,
                        "expected_structure_components": expected_structure_components,
                        "student_answer": result.get("meta", {}).get("original_answer", "") if isinstance(result, dict) else "",
                        "student_structure_components": student_structure_components,
                        "predicted_grade": predicted_grade,
                        "manual_grade": manual_grade,
                        "final_grade": final_grade,
                        "similarity_scores": {
                            "full_similarity": result.get("meta", {}).get("full_similarity_score", 0) if isinstance(result, dict) else 0,
                            "tfidf_similarity": result.get("meta", {}).get("tfidf_similarity_score", 0) if isinstance(result, dict) else 0,
                            "structure_similarity": result.get("meta", {}).get("mean_structure_similarity_score", 0) if isinstance(result, dict) else 0
                        },
                        "structure_components": result.get("meta", {}).get("total_structure_components", 0) if isinstance(result, dict) else 0,
                        "spans": result.get("spans", []) if isinstance(result, dict) else [],
                        "requires_llm_evaluation": result.get("meta", {}).get("requires_llm_evaluation", []) if isinstance(result, dict) else [],
                        "grading_metadata": result.get("meta", {}) if isinstance(result, dict) else {}
                    }
                    detailed_results.append(detailed_result)
                except Exception as e:
                    # Include problematic result with error info
                    detailed_results.append({
                        "question_id": "error",
                        "error": f"Failed to parse result: {str(e)}",
                        "raw_result": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    })
        
        # Calculate percentage
        percentage = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        
        response_data = {
            "student_id": student_id,
            "student_name": submission.student.name if submission.student else "Unknown",
            "coursework_id": coursework_id,
            "submission_id": submission.google_submission_id,
            "total_questions": len(detailed_results),
            "detailed_results": detailed_results,
            "grading_summary": {
                "total_questions": len(detailed_results),
                "total_score": total_score,
                "max_possible_score": max_possible_score,
                "percentage": percentage,
                "average_similarity": sum(r.get("similarity_scores", {}).get("full_similarity", 0) for r in detailed_results if "similarity_scores" in r) / len(detailed_results) if detailed_results else 0,
                "questions_needing_review": len([r for r in detailed_results if r.get("requires_llm_evaluation")]),
                "high_similarity_questions": len([r for r in detailed_results if r.get("similarity_scores", {}).get("full_similarity", 0) > 0.8]),
                "low_similarity_questions": len([r for r in detailed_results if r.get("similarity_scores", {}).get("full_similarity", 0) < 0.5])
            },
            "grading_version": grading_results.get('grading_version', 'unknown') if isinstance(grading_results, dict) else 'unknown'
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        response_data = {
            "student_id": student_id,
            "coursework_id": coursework_id,
            "error": f"Failed to retrieve detailed results: {str(e)}",
            "detailed_results": []
        }
        return JSONResponse(content=response_data)
