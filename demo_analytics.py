#!/usr/bin/env python3
"""
Demo script showing how to test the analytics system manually.
This can be used when the server is running to test the API endpoints.
"""

import json
import asyncio
import aiohttp
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_analytics_endpoints():
    """Test all analytics endpoints"""
    print("🧪 Testing Analytics Endpoints")
    print("=" * 50)
    
    # Test course_id - replace with actual course ID from your system
    test_course_id = "test_course_123"
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Question Analytics
        print("\n1. Testing Question Analytics...")
        try:
            async with session.get(f"{BASE_URL}/api/analytics/questions?course_id={test_course_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Questions endpoint working - Found {len(data.get('data', {}))} questions")
                else:
                    print(f"   ❌ Questions endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Questions endpoint error: {e}")
        
        # Test 2: Student Analytics
        print("\n2. Testing Student Analytics...")
        try:
            async with session.get(f"{BASE_URL}/api/analytics/students?course_id={test_course_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Students endpoint working - Found {len(data.get('data', {}))} students")
                else:
                    print(f"   ❌ Students endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Students endpoint error: {e}")
        
        # Test 3: Class Analytics
        print("\n3. Testing Class Analytics...")
        try:
            async with session.get(f"{BASE_URL}/api/analytics/class?course_id={test_course_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Class endpoint working - Class average: {data.get('data', {}).get('class_average', 'N/A')}")
                else:
                    print(f"   ❌ Class endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Class endpoint error: {e}")
        
        # Test 4: Teacher Analytics
        print("\n4. Testing Teacher Analytics...")
        try:
            async with session.get(f"{BASE_URL}/api/analytics/teacher?course_id={test_course_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Teacher endpoint working - Total courses: {data.get('data', {}).get('total_courses', 'N/A')}")
                else:
                    print(f"   ❌ Teacher endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Teacher endpoint error: {e}")
        
        # Test 5: Summary Analytics
        print("\n5. Testing Summary Analytics...")
        try:
            async with session.get(f"{BASE_URL}/api/analytics/summary?course_id={test_course_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    insights = data.get('data', {}).get('key_insights', {})
                    print(f"   ✅ Summary endpoint working - Questions analyzed: {insights.get('total_questions_analyzed', 'N/A')}")
                else:
                    print(f"   ❌ Summary endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Summary endpoint error: {e}")
        
        # Test 6: Frontend Page
        print("\n6. Testing Frontend Page...")
        try:
            async with session.get(f"{BASE_URL}/analytics.html") as response:
                if response.status == 200:
                    print("   ✅ Analytics page accessible")
                else:
                    print(f"   ❌ Analytics page failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Analytics page error: {e}")
    
    print("\n🎉 Analytics endpoints testing completed!")
    print("\nTo test with real data:")
    print("1. Start the server: python -m uvicorn main:app --reload")
    print("2. Login and create some courses/assignments")
    print("3. Run some grading tasks")
    print("4. Visit http://localhost:8000/analytics.html")
    print("5. Or use this script with real course IDs")

def print_sample_data():
    """Print sample data structures for reference"""
    print("\n📊 Sample Analytics Data Structures")
    print("=" * 50)
    
    print("\n🔍 Question Analytics Sample:")
    question_sample = {
        "question_1": {
            "average_score": 85.2,
            "difficulty_index": 0.15,
            "correct_response_rate": 92.3,
            "high_failure_rate": 7.7,
            "standard_deviation": 12.5,
            "total_attempts": 150,
            "discrimination_index": 0.45
        }
    }
    print(json.dumps(question_sample, indent=2))
    
    print("\n🎓 Student Analytics Sample:")
    student_sample = {
        "student_123": {
            "average_grade": 78.5,
            "grade_trend": "improving",
            "overall_accuracy": 82.1,
            "learning_growth_rate": 15.3,
            "frequently_missed_questions": {
                "question_5": 45.2,
                "question_8": 38.7
            }
        }
    }
    print(json.dumps(student_sample, indent=2))
    
    print("\n🏫 Class Analytics Sample:")
    class_sample = {
        "class_average": 76.8,
        "class_growth_over_time": 12.4,
        "performance_distribution": {
            "0-50": 8.5,
            "50-70": 23.1,
            "70-85": 45.2,
            "85-100": 23.2
        },
        "pass_rate": 88.6,
        "high_performers_rate": 23.2,
        "low_performers_rate": 8.5
    }
    print(json.dumps(class_sample, indent=2))

if __name__ == "__main__":
    print("🎯 AI Studio Analytics System Demo")
    print("=" * 50)
    
    print("\n1. Testing endpoints (requires server running)...")
    try:
        asyncio.run(test_analytics_endpoints())
    except Exception as e:
        print(f"❌ Server not running or connection failed: {e}")
        print("💡 Start server with: python -m uvicorn main:app --reload")
    
    print_sample_data()
