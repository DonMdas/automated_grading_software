"""
Analytics API endpoints for the AI Studio application.
Provides comprehensive analytics for questions, students, classes, and teachers.
"""

import json
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from database import get_db, get_mongo_db, Submission, Student, Assignment, Course, Exam, GradingTask
from auth import get_current_user
from db_service import get_db_service

router = APIRouter()

# Helper functions for analytics calculations

def calculate_question_analytics(db: Session, mongo_db, coursework_id: str = None, course_id: str = None):
    """Calculate question-level analytics"""
    db_service = get_db_service(db)
    
    # Get all grading results
    query = {}
    if coursework_id:
        # Get submissions for specific coursework
        assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
        if assignment:
            submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
            submission_ids = [str(s.id) for s in submissions]
            query = {"submission_id": {"$in": submission_ids}}
    elif course_id:
        # Get submissions for entire course
        course = db.query(Course).filter(Course.google_course_id == course_id).first()
        if course:
            assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
            submission_ids = []
            for assignment in assignments:
                submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
                submission_ids.extend([str(s.id) for s in submissions])
            query = {"submission_id": {"$in": submission_ids}}
    
    grading_results = list(mongo_db.grading_results.find(query))
    
    if not grading_results:
        return {}
    
    # Aggregate question data
    question_data = {}
    
    for result in grading_results:
        results_list = result.get('grading_results', {}).get('results', [])
        for question_result in results_list:
            question_id = question_result.get('question_id', question_result.get('text', 'Unknown'))
            score = float(question_result.get('score', 0))
            max_score = float(question_result.get('max_score', 1))
            
            if question_id not in question_data:
                question_data[question_id] = {
                    'scores': [],
                    'max_score': max_score,
                    'attempts': 0,
                    'correct_responses': 0
                }
            
            question_data[question_id]['scores'].append(score)
            question_data[question_id]['attempts'] += 1
            if score >= max_score * 0.8:  # Consider 80% as correct
                question_data[question_id]['correct_responses'] += 1
    
    # Calculate analytics
    analytics = {}
    
    for question_id, data in question_data.items():
        scores = data['scores']
        if not scores:
            continue
            
        avg_score = statistics.mean(scores)
        max_score = data['max_score']
        attempts = data['attempts']
        correct_responses = data['correct_responses']
        
        analytics[question_id] = {
            'average_score': round(avg_score, 2),
            'difficulty_index': round(1 - (avg_score / max_score), 2),
            'correct_response_rate': round((correct_responses / attempts) * 100, 2),
            'high_failure_rate': round(((attempts - correct_responses) / attempts) * 100, 2),
            'standard_deviation': round(statistics.stdev(scores) if len(scores) > 1 else 0, 2),
            'total_attempts': attempts,
            'discrimination_index': calculate_discrimination_index(scores)
        }
    
    return analytics

def calculate_discrimination_index(scores):
    """Calculate how well a question discriminates between high and low performers"""
    if len(scores) < 6:
        return 0
    
    sorted_scores = sorted(scores, reverse=True)
    top_27 = sorted_scores[:max(1, len(sorted_scores) // 4)]
    bottom_27 = sorted_scores[-max(1, len(sorted_scores) // 4):]
    
    top_avg = statistics.mean(top_27)
    bottom_avg = statistics.mean(bottom_27)
    
    return round(top_avg - bottom_avg, 2)

def calculate_student_analytics(db: Session, mongo_db, student_id: str = None, course_id: str = None):
    """Calculate student-level analytics"""
    
    query = {}
    if student_id and course_id:
        # Get specific student in specific course
        student = db.query(Student).filter(
            Student.google_student_id == student_id,
            Student.course_id == db.query(Course).filter(Course.google_course_id == course_id).first().id
        ).first()
        if student:
            submissions = db.query(Submission).filter(Submission.student_id == student.id).all()
            submission_ids = [str(s.id) for s in submissions]
            query = {"submission_id": {"$in": submission_ids}}
    elif course_id:
        # Get all students in course
        course = db.query(Course).filter(Course.google_course_id == course_id).first()
        if course:
            students = db.query(Student).filter(Student.course_id == course.id).all()
            submission_ids = []
            for student in students:
                submissions = db.query(Submission).filter(Submission.student_id == student.id).all()
                submission_ids.extend([str(s.id) for s in submissions])
            query = {"submission_id": {"$in": submission_ids}}
    
    grading_results = list(mongo_db.grading_results.find(query))
    
    if not grading_results:
        return {}
    
    # Aggregate student data
    student_data = {}
    
    for result in grading_results:
        submission_id = result.get('submission_id')
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission or not submission.student:
            continue
            
        student_key = submission.student.google_student_id
        if student_key not in student_data:
            student_data[student_key] = {
                'exam_scores': [],
                'question_scores': {},
                'total_questions': 0,
                'correct_answers': 0
            }
        
        # Calculate exam score
        results_list = result.get('grading_results', {}).get('results', [])
        total_score = sum(float(q.get('score', 0)) for q in results_list)
        max_possible = sum(float(q.get('max_score', 1)) for q in results_list)
        
        if max_possible > 0:
            exam_percentage = (total_score / max_possible) * 100
            student_data[student_key]['exam_scores'].append(exam_percentage)
        
        # Process individual questions
        for question_result in results_list:
            question_id = question_result.get('question_id', question_result.get('text', 'Unknown'))
            score = float(question_result.get('score', 0))
            max_score = float(question_result.get('max_score', 1))
            
            if question_id not in student_data[student_key]['question_scores']:
                student_data[student_key]['question_scores'][question_id] = []
            
            student_data[student_key]['question_scores'][question_id].append(score / max_score * 100)
            student_data[student_key]['total_questions'] += 1
            
            if score >= max_score * 0.8:  # 80% considered correct
                student_data[student_key]['correct_answers'] += 1
    
    # Calculate analytics
    analytics = {}
    
    for student_key, data in student_data.items():
        exam_scores = data['exam_scores']
        if not exam_scores:
            continue
            
        # Calculate question-wise accuracy
        question_accuracies = {}
        missed_questions = {}
        
        for question_id, scores in data['question_scores'].items():
            avg_score = statistics.mean(scores)
            question_accuracies[question_id] = round(avg_score, 2)
            
            if avg_score < 60:  # Below 60% considered frequently missed
                missed_questions[question_id] = round(avg_score, 2)
        
        analytics[student_key] = {
            'average_grade': round(statistics.mean(exam_scores), 2),
            'grade_trend': calculate_trend(exam_scores),
            'overall_accuracy': round((data['correct_answers'] / data['total_questions']) * 100, 2) if data['total_questions'] > 0 else 0,
            'question_wise_accuracy': question_accuracies,
            'frequently_missed_questions': dict(sorted(missed_questions.items(), key=lambda x: x[1])),
            'learning_growth_rate': calculate_growth_rate(exam_scores),
            'standard_deviation': round(statistics.stdev(exam_scores) if len(exam_scores) > 1 else 0, 2),
            'total_exams': len(exam_scores)
        }
    
    return analytics

def calculate_trend(scores):
    """Calculate if scores are trending up, down, or stable"""
    if len(scores) < 2:
        return "insufficient_data"
    
    # Simple linear trend
    x = list(range(len(scores)))
    n = len(scores)
    
    sum_x = sum(x)
    sum_y = sum(scores)
    sum_xy = sum(x[i] * scores[i] for i in range(n))
    sum_x2 = sum(x[i] ** 2 for i in range(n))
    
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    
    if slope > 1:
        return "improving"
    elif slope < -1:
        return "declining"
    else:
        return "stable"

def calculate_growth_rate(scores):
    """Calculate learning growth rate"""
    if len(scores) < 2:
        return 0
    
    first_half = scores[:len(scores)//2] if len(scores) > 2 else [scores[0]]
    second_half = scores[len(scores)//2:] if len(scores) > 2 else [scores[-1]]
    
    avg_first = statistics.mean(first_half)
    avg_second = statistics.mean(second_half)
    
    if avg_first == 0:
        return 0
    
    return round(((avg_second - avg_first) / avg_first) * 100, 2)

def calculate_class_analytics(db: Session, mongo_db, course_id: str = None):
    """Calculate class-level analytics"""
    
    if course_id:
        course = db.query(Course).filter(Course.google_course_id == course_id).first()
        if not course:
            return {}
        
        # Get all students and assignments in course
        students = db.query(Student).filter(Student.course_id == course.id).all()
        assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
    else:
        # Get all students and assignments across all courses
        students = db.query(Student).all()
        assignments = db.query(Assignment).all()
    
    # Get all submissions for the course(s)
    all_submissions = []
    for assignment in assignments:
        submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
        all_submissions.extend(submissions)
    
    if not all_submissions:
        return {}
    
    submission_ids = [str(s.id) for s in all_submissions]
    grading_results = list(mongo_db.grading_results.find({"submission_id": {"$in": submission_ids}}))
    
    # Calculate analytics
    exam_scores = {}  # exam_id -> [scores]
    all_scores = []
    passing_threshold = 60
    high_performance_threshold = 85
    low_performance_threshold = 50
    
    for result in grading_results:
        submission_id = result.get('submission_id')
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            continue
            
        assignment_id = submission.assignment_id
        
        # Calculate exam score
        results_list = result.get('grading_results', {}).get('results', [])
        total_score = sum(float(q.get('score', 0)) for q in results_list)
        max_possible = sum(float(q.get('max_score', 1)) for q in results_list)
        
        if max_possible > 0:
            exam_percentage = (total_score / max_possible) * 100
            
            if assignment_id not in exam_scores:
                exam_scores[assignment_id] = []
            exam_scores[assignment_id].append(exam_percentage)
            all_scores.append(exam_percentage)
    
    if not all_scores:
        return {}
    
    # Calculate completion and engagement rates
    total_students = len(students)
    completed_assignments = {}
    
    for assignment in assignments:
        completed = db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.status.in_(["GRADED", "OCR_COMPLETE"])
        ).count()
        completed_assignments[assignment.id] = completed
    
    analytics = {
        'class_average': round(statistics.mean(all_scores), 2),
        'class_growth_over_time': calculate_class_growth(exam_scores),
        'performance_distribution': calculate_performance_distribution(all_scores),
        'standard_deviation': round(statistics.stdev(all_scores) if len(all_scores) > 1 else 0, 2),
        'pass_rate': round((sum(1 for score in all_scores if score >= passing_threshold) / len(all_scores)) * 100, 2),
        'high_performers_rate': round((sum(1 for score in all_scores if score >= high_performance_threshold) / len(all_scores)) * 100, 2),
        'low_performers_rate': round((sum(1 for score in all_scores if score < low_performance_threshold) / len(all_scores)) * 100, 2),
        'assignment_completion_rate': round(statistics.mean(list(completed_assignments.values())) / total_students * 100, 2) if total_students > 0 else 0,
        'top_bottom_gap': calculate_top_bottom_gap(all_scores),
        'total_students': total_students,
        'total_assignments': len(assignments)
    }
    
    return analytics

def calculate_class_growth(exam_scores):
    """Calculate class average growth over time"""
    if len(exam_scores) < 2:
        return 0
    
    exam_averages = []
    for assignment_id in sorted(exam_scores.keys()):
        scores = exam_scores[assignment_id]
        if scores:
            exam_averages.append(statistics.mean(scores))
    
    if len(exam_averages) < 2:
        return 0
    
    first_avg = exam_averages[0]
    last_avg = exam_averages[-1]
    
    if first_avg == 0:
        return 0
    
    return round(((last_avg - first_avg) / first_avg) * 100, 2)

def calculate_performance_distribution(scores):
    """Calculate performance distribution in ranges"""
    ranges = {
        '0-50': 0,
        '50-70': 0,
        '70-85': 0,
        '85-100': 0
    }
    
    for score in scores:
        if score < 50:
            ranges['0-50'] += 1
        elif score < 70:
            ranges['50-70'] += 1
        elif score < 85:
            ranges['70-85'] += 1
        else:
            ranges['85-100'] += 1
    
    total = len(scores)
    return {k: round((v / total) * 100, 2) for k, v in ranges.items()}

def calculate_top_bottom_gap(scores):
    """Calculate gap between top 10% and bottom 10%"""
    if len(scores) < 10:
        return 0
    
    sorted_scores = sorted(scores, reverse=True)
    top_10_percent = sorted_scores[:max(1, len(sorted_scores) // 10)]
    bottom_10_percent = sorted_scores[-max(1, len(sorted_scores) // 10):]
    
    top_avg = statistics.mean(top_10_percent)
    bottom_avg = statistics.mean(bottom_10_percent)
    
    return round(top_avg - bottom_avg, 2)

def calculate_teacher_analytics(db: Session, mongo_db, course_id: str = None):
    """Calculate teacher-level analytics"""
    
    if course_id:
        course = db.query(Course).filter(Course.google_course_id == course_id).first()
        if not course:
            return {}
        courses = [course]
    else:
        courses = db.query(Course).all()
    
    if not courses:
        return {}
    
    # Aggregate teacher metrics
    total_grading_tasks = 0
    completed_tasks = 0
    total_response_time = 0
    response_time_count = 0
    
    for course in courses:
        # Get grading tasks for this course
        assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
        for assignment in assignments:
            tasks = db.query(GradingTask).filter(GradingTask.assignment_id == assignment.id).all()
            total_grading_tasks += len(tasks)
            
            for task in tasks:
                if task.status == "COMPLETED":
                    completed_tasks += 1
                    
                    # Calculate response time if available
                    if task.created_at and task.updated_at:
                        response_time = (task.updated_at - task.created_at).total_seconds() / 3600  # hours
                        total_response_time += response_time
                        response_time_count += 1
    
    # Calculate metrics
    grading_efficiency = (completed_tasks / total_grading_tasks * 100) if total_grading_tasks > 0 else 0
    average_response_time = (total_response_time / response_time_count) if response_time_count > 0 else 0
    
    return {
        "grading_efficiency": grading_efficiency,
        "average_response_time": average_response_time,
        "total_grading_tasks": total_grading_tasks,
        "completed_tasks": completed_tasks,
        "total_courses": len(courses)
    }

def calculate_teacher_analytics_enhanced(db: Session, mongo_db, teacher_id: str = None):
    """Enhanced teacher analytics with additional KPIs"""
    
    if teacher_id:
        courses = db.query(Course).filter(Course.teacher_id == teacher_id).all()
    else:
        courses = db.query(Course).all()
    
    if not courses:
        return {}
    
    teacher_metrics = {
        "total_courses": len(courses),
        "courses": {},
        "overall_metrics": {},
        "grading_efficiency": {},
        "student_support": {}
    }
    
    all_class_analytics = []
    total_students = 0
    total_assignments = 0
    total_grading_tasks = 0
    completed_grading_tasks = 0
    
    for course in courses:
        class_analytics = calculate_class_analytics(db, mongo_db, course.google_course_id)
        
        if class_analytics:
            teacher_metrics["courses"][course.google_course_id] = {
                "course_name": course.name,
                "analytics": class_analytics
            }
            all_class_analytics.append(class_analytics)
            total_students += class_analytics.get('total_students', 0)
            total_assignments += class_analytics.get('total_assignments', 0)
        
        # Get grading task metrics for this course
        assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
        for assignment in assignments:
            grading_tasks = db.query(GradingTask).filter(GradingTask.assignment_id == assignment.id).all()
            total_grading_tasks += len(grading_tasks)
            completed_grading_tasks += len([task for task in grading_tasks if task.status == "COMPLETED"])
    
    # Calculate overall teacher metrics
    if all_class_analytics:
        avg_class_performance = statistics.mean([a.get('class_average', 0) for a in all_class_analytics])
        avg_pass_rate = statistics.mean([a.get('pass_rate', 0) for a in all_class_analytics])
        avg_high_performers = statistics.mean([a.get('high_performers_rate', 0) for a in all_class_analytics])
        
        # Calculate students needing support
        students_needing_support = 0
        for analytics in all_class_analytics:
            low_performers_rate = analytics.get('low_performers_rate', 0)
            total_students_in_class = analytics.get('total_students', 0)
            students_needing_support += int((low_performers_rate / 100) * total_students_in_class)
        
        teacher_metrics["overall_metrics"] = {
            "average_class_performance": round(avg_class_performance, 2),
            "average_pass_rate": round(avg_pass_rate, 2),
            "average_high_performers_rate": round(avg_high_performers, 2),
            "total_students_taught": total_students,
            "total_assignments_created": total_assignments,
            "class_average_growth": calculate_teacher_growth_rate(all_class_analytics),
            "performance_consistency": round(statistics.stdev([a.get('class_average', 0) for a in all_class_analytics]), 2) if len(all_class_analytics) > 1 else 0
        }
        
        # Grading efficiency metrics
        grading_completion_rate = (completed_grading_tasks / total_grading_tasks * 100) if total_grading_tasks > 0 else 0
        teacher_metrics["grading_efficiency"] = {
            "total_grading_tasks": total_grading_tasks,
            "completed_grading_tasks": completed_grading_tasks,
            "grading_completion_rate": round(grading_completion_rate, 2),
            "average_time_saved": estimate_time_saved(completed_grading_tasks, total_students)
        }
        
        # Student support metrics
        teacher_metrics["student_support"] = {
            "students_needing_support": students_needing_support,
            "support_intervention_rate": round((students_needing_support / total_students * 100), 2) if total_students > 0 else 0,
            "early_intervention_opportunities": len([a for a in all_class_analytics if a.get('class_average', 0) < 70])
        }
    
    return teacher_metrics

def calculate_teacher_growth_rate(all_class_analytics):
    """Calculate overall teacher growth rate across all classes"""
    if len(all_class_analytics) < 2:
        return 0
    
    growth_rates = [analytics.get('class_growth_over_time', 0) for analytics in all_class_analytics]
    return round(statistics.mean(growth_rates), 2)

def estimate_time_saved(completed_tasks, total_students):
    """Estimate time saved by AI-assisted grading"""
    # Assume 10 minutes per student for manual grading
    # AI grading saves approximately 80% of this time
    manual_grading_time = completed_tasks * total_students * 10  # minutes
    time_saved = manual_grading_time * 0.8  # 80% time savings
    return round(time_saved / 60, 2)  # Convert to hours

def calculate_engagement_metrics(db: Session, mongo_db, course_id: str):
    """Calculate detailed engagement metrics for a course"""
    
    course = db.query(Course).filter(Course.google_course_id == course_id).first()
    if not course:
        return {}
    
    assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
    students = db.query(Student).filter(Student.course_id == course.id).all()
    
    if not assignments or not students:
        return {}
    
    total_possible_submissions = len(assignments) * len(students)
    
    engagement_metrics = {
        "total_students": len(students),
        "total_assignments": len(assignments),
        "assignment_metrics": {},
        "student_engagement": {},
        "overall_engagement": {}
    }
    
    total_submissions = 0
    on_time_submissions = 0
    
    for assignment in assignments:
        submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
        completed_submissions = len([s for s in submissions if s.status in ["GRADED", "OCR_COMPLETE"]])
        
        assignment_completion_rate = (completed_submissions / len(students) * 100) if len(students) > 0 else 0
        
        engagement_metrics["assignment_metrics"][assignment.google_assignment_id] = {
            "title": assignment.title,
            "total_submissions": len(submissions),
            "completed_submissions": completed_submissions,
            "completion_rate": round(assignment_completion_rate, 2),
            "engagement_score": calculate_engagement_score(submissions, len(students))
        }
        
        total_submissions += completed_submissions
        # For now, assume all completed submissions are on time (can be enhanced with actual deadline data)
        on_time_submissions += completed_submissions
    
    # Calculate overall engagement
    overall_completion_rate = (total_submissions / total_possible_submissions * 100) if total_possible_submissions > 0 else 0
    on_time_rate = (on_time_submissions / total_submissions * 100) if total_submissions > 0 else 0
    
    engagement_metrics["overall_engagement"] = {
        "overall_completion_rate": round(overall_completion_rate, 2),
        "on_time_submission_rate": round(on_time_rate, 2),
        "average_engagement_score": round(statistics.mean([
            metrics["engagement_score"] for metrics in engagement_metrics["assignment_metrics"].values()
        ]), 2) if engagement_metrics["assignment_metrics"] else 0,
        "engagement_trend": calculate_engagement_trend(engagement_metrics["assignment_metrics"])
    }
    
    return engagement_metrics

def calculate_engagement_score(submissions, total_students):
    """Calculate engagement score for an assignment"""
    if total_students == 0:
        return 0
    
    completion_rate = len(submissions) / total_students
    quality_score = len([s for s in submissions if s.status == "GRADED"]) / len(submissions) if submissions else 0
    
    # Combined score (50% completion, 50% quality)
    engagement_score = (completion_rate * 0.5 + quality_score * 0.5) * 100
    return round(engagement_score, 2)

def calculate_engagement_trend(assignment_metrics):
    """Calculate if engagement is improving or declining"""
    if len(assignment_metrics) < 2:
        return "insufficient_data"
    
    scores = [metrics["engagement_score"] for metrics in assignment_metrics.values()]
    
    # Simple trend analysis
    first_half = scores[:len(scores)//2] if len(scores) > 2 else [scores[0]]
    second_half = scores[len(scores)//2:] if len(scores) > 2 else [scores[-1]]
    
    avg_first = statistics.mean(first_half)
    avg_second = statistics.mean(second_half)
    
    if avg_second > avg_first + 5:
        return "improving"
    elif avg_second < avg_first - 5:
        return "declining"
    else:
        return "stable"

# API Endpoints

@router.get("/api/analytics/questions")
async def get_question_analytics(
    coursework_id: Optional[str] = Query(None, description="Specific coursework ID"),
    course_id: Optional[str] = Query(None, description="Course ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get question-level analytics"""
    try:
        analytics = calculate_question_analytics(db, mongo_db.db, coursework_id, course_id)
        return {
            "status": "success",
            "data": analytics,
            "metadata": {
                "total_questions": len(analytics),
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate question analytics: {str(e)}")

@router.get("/api/analytics/students")
async def get_student_analytics(
    course_id: Optional[str] = Query(None, description="Course ID"),
    student_id: Optional[str] = Query(None, description="Specific student ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get student-level analytics"""
    try:
        analytics = calculate_student_analytics(db, mongo_db.db, student_id, course_id)
        return {
            "status": "success",
            "data": analytics,
            "metadata": {
                "total_students": len(analytics),
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate student analytics: {str(e)}")

@router.get("/api/analytics/class")
async def get_class_analytics(
    course_id: Optional[str] = Query(None, description="Course ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get class-level analytics"""
    try:
        analytics = calculate_class_analytics(db, mongo_db.db, course_id)
        return {
            "status": "success",
            "data": analytics,
            "metadata": {
                "course_id": course_id,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate class analytics: {str(e)}")

@router.get("/api/analytics/teacher")
async def get_teacher_analytics(
    course_id: Optional[str] = Query(None, description="Specific course ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get teacher-level analytics"""
    try:
        # Get teacher's courses
        if course_id:
            courses = db.query(Course).filter(Course.google_course_id == course_id).all()
        else:
            courses = db.query(Course).filter(Course.teacher_id == str(current_user.id)).all()
        
        teacher_analytics = {
            "total_courses": len(courses),
            "courses": {},
            "overall_metrics": {}
        }
        
        all_class_analytics = []
        total_students = 0
        
        for course in courses:
            class_analytics = calculate_class_analytics(db, mongo_db.db, course.google_course_id)
            if class_analytics:
                teacher_analytics["courses"][course.google_course_id] = {
                    "course_name": course.name,
                    "analytics": class_analytics
                }
                all_class_analytics.append(class_analytics)
                total_students += class_analytics.get('total_students', 0)
        
        # Calculate overall teacher metrics
        if all_class_analytics:
            avg_class_performance = statistics.mean([a.get('class_average', 0) for a in all_class_analytics])
            avg_pass_rate = statistics.mean([a.get('pass_rate', 0) for a in all_class_analytics])
            
            teacher_analytics["overall_metrics"] = {
                "average_class_performance": round(avg_class_performance, 2),
                "average_pass_rate": round(avg_pass_rate, 2),
                "total_students_taught": total_students,
                "student_support_needed": sum(1 for a in all_class_analytics for _ in range(int(a.get('low_performers_rate', 0) * a.get('total_students', 0) / 100)))
            }
        
        return {
            "status": "success",
            "data": teacher_analytics,
            "metadata": {
                "teacher_id": str(current_user.id),
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate teacher analytics: {str(e)}")

@router.get("/api/analytics/teacher/enhanced")
async def get_enhanced_teacher_analytics(
    teacher_id: Optional[str] = Query(None, description="Specific teacher ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get enhanced teacher analytics with additional KPIs"""
    try:
        # Use current user's ID if no teacher_id provided
        target_teacher_id = teacher_id or str(current_user.id)
        
        analytics = calculate_teacher_analytics_enhanced(db, mongo_db.db, target_teacher_id)
        
        return {
            "status": "success",
            "data": analytics,
            "metadata": {
                "teacher_id": target_teacher_id,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate enhanced teacher analytics: {str(e)}")

@router.get("/api/analytics/engagement")
async def get_engagement_analytics(
    course_id: str = Query(..., description="Course ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get detailed engagement metrics for a course"""
    try:
        analytics = calculate_engagement_metrics(db, mongo_db.db, course_id)
        
        return {
            "status": "success",
            "data": analytics,
            "metadata": {
                "course_id": course_id,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate engagement analytics: {str(e)}")

@router.get("/api/analytics/comprehensive")
async def get_comprehensive_analytics(
    course_id: str = Query(..., description="Course ID"),
    include_engagement: bool = Query(True, description="Include engagement metrics"),
    include_predictions: bool = Query(False, description="Include predictive analytics"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get comprehensive analytics combining all available metrics"""
    try:
        # Get all standard analytics
        question_analytics = calculate_question_analytics(db, mongo_db.db, None, course_id)
        student_analytics = calculate_student_analytics(db, mongo_db.db, None, course_id)
        class_analytics = calculate_class_analytics(db, mongo_db.db, course_id)
        
        comprehensive_data = {
            "questions": question_analytics,
            "students": student_analytics,
            "class": class_analytics,
            "summary": {
                "total_questions": len(question_analytics),
                "total_students": len(student_analytics),
                "class_average": class_analytics.get("class_average", 0),
                "pass_rate": class_analytics.get("pass_rate", 0)
            }
        }
        
        # Add engagement metrics if requested
        if include_engagement:
            engagement_analytics = calculate_engagement_metrics(db, mongo_db.db, course_id)
            comprehensive_data["engagement"] = engagement_analytics
        
        # Add predictive analytics if requested (placeholder for future implementation)
        if include_predictions:
            comprehensive_data["predictions"] = {
                "next_exam_performance": "Coming soon",
                "at_risk_students": "Coming soon",
                "topic_difficulty_forecast": "Coming soon"
            }
        
        # Generate insights
        insights = generate_actionable_insights(comprehensive_data)
        comprehensive_data["insights"] = insights
        
        return {
            "status": "success",
            "data": comprehensive_data,
            "metadata": {
                "course_id": course_id,
                "generated_at": datetime.utcnow().isoformat(),
                "includes_engagement": include_engagement,
                "includes_predictions": include_predictions
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate comprehensive analytics: {str(e)}")

def generate_actionable_insights(data):
    """Generate actionable insights from comprehensive analytics data"""
    insights = {
        "critical_actions": [],
        "improvements": [],
        "strengths": [],
        "recommendations": []
    }
    
    class_data = data.get("class", {})
    question_data = data.get("questions", {})
    student_data = data.get("students", {})
    
    # Critical actions (red flags)
    class_average = class_data.get("class_average", 0)
    if class_average < 60:
        insights["critical_actions"].append({
            "type": "low_performance",
            "message": f"Class average is critically low at {class_average}%",
            "action": "Consider reviewing teaching methods and providing additional support"
        })
    
    pass_rate = class_data.get("pass_rate", 0)
    if pass_rate < 70:
        insights["critical_actions"].append({
            "type": "low_pass_rate",
            "message": f"Pass rate is concerning at {pass_rate}%",
            "action": "Identify struggling students and provide targeted intervention"
        })
    
    # Identify difficult questions
    difficult_questions = [(q, data) for q, data in question_data.items() if data.get("difficulty_index", 0) > 0.7]
    if difficult_questions:
        insights["critical_actions"].append({
            "type": "difficult_questions",
            "message": f"Found {len(difficult_questions)} very difficult questions",
            "action": "Review question clarity and consider providing additional examples"
        })
    
    # Improvement opportunities
    low_performers_rate = class_data.get("low_performers_rate", 0)
    if low_performers_rate > 20:
        insights["improvements"].append({
            "type": "high_low_performers",
            "message": f"{low_performers_rate}% of students are underperforming",
            "action": "Implement peer tutoring or additional practice sessions"
        })
    
    # Identify strengths
    high_performers_rate = class_data.get("high_performers_rate", 0)
    if high_performers_rate > 30:
        insights["strengths"].append({
            "type": "high_achievers",
            "message": f"{high_performers_rate}% of students are high performers",
            "action": "Consider advanced challenges for these students"
        })
    
    growth_rate = class_data.get("class_growth_over_time", 0)
    if growth_rate > 10:
        insights["strengths"].append({
            "type": "positive_growth",
            "message": f"Class showing strong growth at {growth_rate}%",
            "action": "Continue current teaching strategies"
        })
    
    # General recommendations
    if question_data:
        avg_difficulty = statistics.mean([data.get("difficulty_index", 0) for data in question_data.values()])
        if avg_difficulty > 0.6:
            insights["recommendations"].append({
                "type": "question_difficulty",
                "message": "Questions may be too difficult overall",
                "action": "Consider adjusting question difficulty or providing more preparation"
            })
    
    if student_data:
        struggling_students = len([s for s, data in student_data.items() if data.get("average_grade", 0) < 60])
        if struggling_students > 0:
            insights["recommendations"].append({
                "type": "individual_support",
                "message": f"{struggling_students} students need individual attention",
                "action": "Schedule one-on-one sessions with struggling students"
            })
    
    return insights

@router.get("/api/analytics/demo")
async def get_demo_analytics():
    """Get demo analytics data for testing the interface - no authentication required"""
    """Get demo analytics data for testing the interface"""
    demo_data = {
        "summary": {
            "class_overview": {
                "class_average": 78.5,
                "pass_rate": 85.2,
                "total_students": 25,
                "total_assignments": 8,
                "high_performers_rate": 32.0,
                "low_performers_rate": 8.0,
                "standard_deviation": 18.3,
                "assignment_completion_rate": 96.0,
                "top_bottom_gap": 45.8,
                "class_growth_over_time": 12.4,
                "performance_distribution": {
                    "0-50": 8.0,
                    "50-70": 20.0,
                    "70-85": 40.0,
                    "85-100": 32.0
                }
            },
            "most_missed_questions": [
                {"question": "Question 3: Advanced Calculus Integration", "failure_rate": 45.2},
                {"question": "Question 7: Complex Analysis Theorems", "failure_rate": 38.7},
                {"question": "Question 12: Differential Equations", "failure_rate": 35.1},
                {"question": "Question 15: Linear Algebra Proofs", "failure_rate": 32.4},
                {"question": "Question 9: Probability Distributions", "failure_rate": 28.9}
            ],
            "top_performers": [
                {"student": "Alice Johnson", "average_grade": 95.2},
                {"student": "Bob Chen", "average_grade": 92.8},
                {"student": "Carol Davis", "average_grade": 89.5},
                {"student": "David Wilson", "average_grade": 87.3},
                {"student": "Emma Rodriguez", "average_grade": 85.9}
            ],
            "key_insights": {
                "total_questions_analyzed": 20,
                "total_students_analyzed": 25,
                "average_question_difficulty": 0.35,
                "students_needing_support": 4
            }
        },
        "questions": {
            "Question 1: Basic Algebraic Operations": {
                "average_score": 88.5,
                "difficulty_index": 0.12,
                "correct_response_rate": 92.0,
                "high_failure_rate": 8.0,
                "standard_deviation": 12.3,
                "total_attempts": 25,
                "discrimination_index": 0.45
            },
            "Question 2: Geometric Proofs": {
                "average_score": 76.3,
                "difficulty_index": 0.24,
                "correct_response_rate": 80.0,
                "high_failure_rate": 20.0,
                "standard_deviation": 18.7,
                "total_attempts": 25,
                "discrimination_index": 0.38
            },
            "Question 3: Advanced Calculus Integration": {
                "average_score": 54.8,
                "difficulty_index": 0.45,
                "correct_response_rate": 55.0,
                "high_failure_rate": 45.0,
                "standard_deviation": 22.1,
                "total_attempts": 25,
                "discrimination_index": 0.52
            },
            "Question 4: Statistics and Probability": {
                "average_score": 82.1,
                "difficulty_index": 0.18,
                "correct_response_rate": 84.0,
                "high_failure_rate": 16.0,
                "standard_deviation": 15.4,
                "total_attempts": 25,
                "discrimination_index": 0.41
            },
            "Question 5: Matrix Operations": {
                "average_score": 71.2,
                "difficulty_index": 0.29,
                "correct_response_rate": 72.0,
                "high_failure_rate": 28.0,
                "standard_deviation": 19.8,
                "total_attempts": 25,
                "discrimination_index": 0.47
            }
        },
        "students": {
            "Alice Johnson": {
                "average_grade": 95.2,
                "grade_trend": "improving",
                "overall_accuracy": 94.5,
                "learning_growth_rate": 12.3,
                "standard_deviation": 4.2,
                "total_exams": 8,
                "question_wise_accuracy": {
                    "Question 1": 98.0,
                    "Question 2": 95.0,
                    "Question 3": 88.0,
                    "Question 4": 97.0,
                    "Question 5": 92.0
                },
                "frequently_missed_questions": {}
            },
            "Bob Chen": {
                "average_grade": 92.8,
                "grade_trend": "stable",
                "overall_accuracy": 91.2,
                "learning_growth_rate": 8.7,
                "standard_deviation": 6.1,
                "total_exams": 8,
                "question_wise_accuracy": {
                    "Question 1": 95.0,
                    "Question 2": 90.0,
                    "Question 3": 85.0,
                    "Question 4": 94.0,
                    "Question 5": 89.0
                },
                "frequently_missed_questions": {
                    "Question 3": 85.0
                }
            },
            "Carol Davis": {
                "average_grade": 89.5,
                "grade_trend": "improving",
                "overall_accuracy": 87.9,
                "learning_growth_rate": 15.2,
                "standard_deviation": 8.3,
                "total_exams": 8,
                "question_wise_accuracy": {
                    "Question 1": 92.0,
                    "Question 2": 88.0,
                    "Question 3": 78.0,
                    "Question 4": 91.0,
                    "Question 5": 86.0
                },
                "frequently_missed_questions": {
                    "Question 3": 78.0
                }
            },
            "David Wilson": {
                "average_grade": 87.3,
                "grade_trend": "stable",
                "overall_accuracy": 85.1,
                "learning_growth_rate": 6.8,
                "standard_deviation": 9.7,
                "total_exams": 8,
                "question_wise_accuracy": {
                    "Question 1": 89.0,
                    "Question 2": 85.0,
                    "Question 3": 75.0,
                    "Question 4": 88.0,
                    "Question 5": 82.0
                },
                "frequently_missed_questions": {
                    "Question 3": 75.0
                }
            },
            "Emma Rodriguez": {
                "average_grade": 85.9,
                "grade_trend": "improving",
                "overall_accuracy": 83.4,
                "learning_growth_rate": 18.9,
                "standard_deviation": 11.2,
                "total_exams": 8,
                "question_wise_accuracy": {
                    "Question 1": 87.0,
                    "Question 2": 83.0,
                    "Question 3": 72.0,
                    "Question 4": 86.0,
                    "Question 5": 80.0
                },
                "frequently_missed_questions": {
                    "Question 3": 72.0
                }
            },
            "Frank Miller": {
                "average_grade": 45.2,
                "grade_trend": "declining",
                "overall_accuracy": 42.1,
                "learning_growth_rate": -5.3,
                "standard_deviation": 16.8,
                "total_exams": 8,
                "question_wise_accuracy": {
                    "Question 1": 52.0,
                    "Question 2": 38.0,
                    "Question 3": 25.0,
                    "Question 4": 48.0,
                    "Question 5": 35.0
                },
                "frequently_missed_questions": {
                    "Question 2": 38.0,
                    "Question 3": 25.0,
                    "Question 5": 35.0
                }
            }
        },
        "class": {
            "class_average": 78.5,
            "class_growth_over_time": 12.4,
            "performance_distribution": {
                "0-50": 8.0,
                "50-70": 20.0,
                "70-85": 40.0,
                "85-100": 32.0
            },
            "standard_deviation": 18.3,
            "pass_rate": 85.2,
            "high_performers_rate": 32.0,
            "low_performers_rate": 8.0,
            "assignment_completion_rate": 96.0,
            "top_bottom_gap": 45.8,
            "total_students": 25,
            "total_assignments": 8
        },
        "teacher": {
            "total_courses": 3,
            "overall_metrics": {
                "average_class_performance": 78.5,
                "average_pass_rate": 82.3,
                "average_high_performers_rate": 28.7,
                "total_students_taught": 75,
                "total_assignments_created": 24,
                "class_average_growth": 11.2,
                "performance_consistency": 15.8,
                "student_support_needed": 12
            },
            "grading_efficiency": {
                "total_grading_tasks": 24,
                "completed_grading_tasks": 23,
                "grading_completion_rate": 95.8,
                "average_time_saved": 48.5
            },
            "student_support": {
                "students_needing_support": 12,
                "support_intervention_rate": 16.0,
                "early_intervention_opportunities": 2
            },
            "courses": {
                "course_1": {
                    "course_name": "Advanced Mathematics",
                    "analytics": {"class_average": 78.5}
                },
                "course_2": {
                    "course_name": "Statistics & Probability",
                    "analytics": {"class_average": 82.1}
                },
                "course_3": {
                    "course_name": "Linear Algebra",
                    "analytics": {"class_average": 74.8}
                }
            }
        }
    }
    
    return {
        "status": "success",
        "data": demo_data,
        "metadata": {
            "is_demo": True,
            "generated_at": datetime.utcnow().isoformat(),
            "message": "This is sample analytics data for demonstration purposes"
        }
    }

@router.get("/api/analytics/summary")
async def get_summary_analytics(
    coursework_id: Optional[str] = Query(None, description="Specific coursework ID"),
    course_id: Optional[str] = Query(None, description="Course ID"),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user = Depends(get_current_user)
):
    """Get summary analytics combining all data"""
    try:
        # Get analytics from all components
        question_analytics = calculate_question_analytics(db, mongo_db.db, coursework_id, course_id)
        student_analytics = calculate_student_analytics(db, mongo_db.db, course_id)
        class_analytics = calculate_class_analytics(db, mongo_db.db, course_id)
        teacher_analytics = calculate_teacher_analytics(db, mongo_db.db, course_id)
        
        # Create summary combining key metrics
        summary = {
            "class_average": class_analytics.get("class_average", 0),
            "pass_rate": class_analytics.get("pass_rate", 0),
            "total_students": class_analytics.get("total_students", 0),
            "total_questions": len(question_analytics),
            "total_assignments": class_analytics.get("total_assignments", 0),
            "high_performers": class_analytics.get("high_performers", 0),
            "low_performers": class_analytics.get("low_performers", 0),
            "grading_efficiency": teacher_analytics.get("grading_efficiency", 0),
            "response_time": teacher_analytics.get("average_response_time", 0)
        }
        
        return {
            "status": "success",
            "data": summary,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "course_id": course_id,
                "coursework_id": coursework_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary analytics: {str(e)}")
