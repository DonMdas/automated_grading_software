"""
Google Classroom Service for AI Grading Platform
Handles authentication and data retrieval from Google Classroom API
"""

import os
import secrets
from typing import Dict, Any, Tuple, List
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

# Import the necessary Google libraries upfront
try:
    import json
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
except ImportError:
    print("WARNING: Google OAuth libraries not available. Using mock authentication.")
    # Define a minimal logger to avoid errors
    import logging
    logger = logging.getLogger(__name__)
else:
    import logging
    logger = logging.getLogger(__name__)

# Path to client secrets file
SECRETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "client_secrets.json")

# Scopes required for Google Classroom integration
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly'
]

# Simple in-memory storage for demo
OAUTH_SESSIONS = {}

def get_oauth_redirect(signup: bool = False) -> RedirectResponse:
    """Generate a Google OAuth redirect URL"""
    try:
        # Set environment variables for OAuth
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'
        
        # Generate state token
        state = secrets.token_urlsafe(16)
        if signup:
            state = f"signup_{state}"
        
        # Generate authorization URL manually if Google libraries aren't available
        try:
            # Read client info from secrets file
            import json
            with open(SECRETS_FILE, 'r') as f:
                client_info = json.load(f)['web']
            
            client_id = client_info['client_id']
            redirect_uri = "http://localhost:8001/api/auth/google/callback"
            
            # Construct the authorization URL
            scope_str = '+'.join([s.replace(':', '%3A').replace('/', '%2F') for s in SCOPES])
            auth_url = f"{client_info['auth_uri']}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&state={state}&access_type=offline&include_granted_scopes=true&prompt=consent"
            
            print(f"Authorization URL: {auth_url[:100]}...")
            return RedirectResponse(url=auth_url)
        except Exception as e:
            print(f"Error generating auth URL manually: {e}")
            # Fall back to demo mode
            return RedirectResponse(url="/evaluation?token=demo-token&google_connected=true&demo=true")
            
    except Exception as e:
        print(f"OAuth Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url="/evaluation?token=error-token&google_connected=false&demo=true")

def process_oauth_callback(code: str, state: str = None) -> Tuple[str, bool]:
    """Process OAuth callback and return a token"""
    # Check if it's a signup
    is_signup = False
    if state and state.startswith("signup_"):
        is_signup = True
    
    try:
        # Set environment variables for OAuth
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'
        
        # Create a Flow object
        try:
            import json
            with open(SECRETS_FILE, 'r') as f:
                client_info = json.load(f)['web']
            
            # Create a flow using the client secrets file
            flow = Flow.from_client_secrets_file(
                SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri="http://localhost:8001/api/auth/google/callback"
            )
            
            # Exchange the authorization code for credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Create a user-friendly token instead of exposing the real token
            token = secrets.token_urlsafe(32)
            
            # In a real implementation, you would store the actual credentials
            # associated with this token in a secure database
            print("✅ Successfully processed OAuth callback")
            return token, is_signup
            
        except Exception as e:
            print(f"Error processing OAuth flow: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to demo mode
            token = f"demo-token-{secrets.token_urlsafe(8)}"
            print("🔑 Generated fallback authentication token for demo mode")
            return token, is_signup
            
    except Exception as e:
        print(f"Unhandled OAuth Error: {str(e)}")
        import traceback
        traceback.print_exc()
        token = f"error-token-{secrets.token_urlsafe(8)}"
        print("⚠️ Generated error token due to exception")
        return token, is_signup

class GoogleClassroomService:
    """Service for Google Classroom API integration"""
    
    # Use the same scopes as defined at the top level
    SCOPES = SCOPES
    
    def __init__(self):
        self.client_secrets_file = os.getenv('GOOGLE_CLIENT_SECRETS_FILE', 'client_secrets.json')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/api/auth/google/callback')
        
    def create_auth_url(self, state: str = None) -> str:
        """Create Google OAuth authorization URL"""
        try:
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=state
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Error creating auth URL: {e}")
            raise
    
    def exchange_code_for_token(self, code: str, state: str = None) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri,
                state=state
            )
            
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Get user info
            user_info = self.get_user_info(credentials)
            
            return {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'expires_at': credentials.expiry.isoformat() if credentials.expiry else None,
                'user_info': user_info
            }
            
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            raise
    
    def get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Get user information from Google"""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            raise
    
    def get_courses(self, credentials: Credentials) -> List[Dict[str, Any]]:
        """Get list of courses from Google Classroom"""
        try:
            service = build('classroom', 'v1', credentials=credentials)
            
            results = service.courses().list(
                pageSize=100,
                courseStates=['ACTIVE', 'ARCHIVED']
            ).execute()
            
            courses = results.get('courses', [])
            
            formatted_courses = []
            for course in courses:
                formatted_course = {
                    'id': course.get('id'),
                    'name': course.get('name'),
                    'description': course.get('description', ''),
                    'state': course.get('courseState'),
                    'creation_time': course.get('creationTime'),
                    'update_time': course.get('updateTime'),
                    'enrollment_code': course.get('enrollmentCode'),
                    'teacher_folder': course.get('teacherFolder', {}).get('title', ''),
                    'calendar_id': course.get('calendarId'),
                    'guardiansEnabled': course.get('guardiansEnabled', False),
                    'teacher_group_email': course.get('teacherGroupEmail'),
                    'course_group_email': course.get('courseGroupEmail')
                }
                formatted_courses.append(formatted_course)
            
            return formatted_courses
            
        except HttpError as e:
            logger.error(f"HTTP error getting courses: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting courses: {e}")
            raise
    
    def get_course_work(self, credentials: Credentials, course_id: str) -> List[Dict[str, Any]]:
        """Get coursework for a specific course"""
        try:
            service = build('classroom', 'v1', credentials=credentials)
            
            results = service.courses().courseWork().list(
                courseId=course_id,
                pageSize=100
            ).execute()
            
            coursework = results.get('courseWork', [])
            
            formatted_coursework = []
            for work in coursework:
                formatted_work = {
                    'id': work.get('id'),
                    'course_id': work.get('courseId'),
                    'title': work.get('title'),
                    'description': work.get('description', ''),
                    'state': work.get('state'),
                    'creation_time': work.get('creationTime'),
                    'update_time': work.get('updateTime'),
                    'due_date': work.get('dueDate'),
                    'due_time': work.get('dueTime'),
                    'max_points': work.get('maxPoints'),
                    'work_type': work.get('workType'),
                    'submission_modification_mode': work.get('submissionModificationMode'),
                    'creator_user_id': work.get('creatorUserId'),
                    'topic_id': work.get('topicId')
                }
                formatted_coursework.append(formatted_work)
            
            return formatted_coursework
            
        except HttpError as e:
            logger.error(f"HTTP error getting coursework: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting coursework: {e}")
            raise
    
    def get_students(self, credentials: Credentials, course_id: str) -> List[Dict[str, Any]]:
        """Get students enrolled in a course"""
        try:
            service = build('classroom', 'v1', credentials=credentials)
            
            results = service.courses().students().list(
                courseId=course_id,
                pageSize=100
            ).execute()
            
            students = results.get('students', [])
            
            formatted_students = []
            for student in students:
                profile = student.get('profile', {})
                formatted_student = {
                    'course_id': student.get('courseId'),
                    'user_id': student.get('userId'),
                    'profile': {
                        'id': profile.get('id'),
                        'name': profile.get('name', {}).get('fullName', ''),
                        'given_name': profile.get('name', {}).get('givenName', ''),
                        'family_name': profile.get('name', {}).get('familyName', ''),
                        'email': profile.get('emailAddress', ''),
                        'photo_url': profile.get('photoUrl', '')
                    }
                }
                formatted_students.append(formatted_student)
            
            return formatted_students
            
        except HttpError as e:
            logger.error(f"HTTP error getting students: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting students: {e}")
            raise
    
    def get_submissions(self, credentials: Credentials, course_id: str, coursework_id: str) -> List[Dict[str, Any]]:
        """Get student submissions for a specific coursework"""
        try:
            service = build('classroom', 'v1', credentials=credentials)
            
            results = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=coursework_id,
                pageSize=100
            ).execute()
            
            submissions = results.get('studentSubmissions', [])
            
            formatted_submissions = []
            for submission in submissions:
                formatted_submission = {
                    'id': submission.get('id'),
                    'course_id': submission.get('courseId'),
                    'coursework_id': submission.get('courseWorkId'),
                    'user_id': submission.get('userId'),
                    'creation_time': submission.get('creationTime'),
                    'update_time': submission.get('updateTime'),
                    'state': submission.get('state'),
                    'late': submission.get('late', False),
                    'draft_grade': submission.get('draftGrade'),
                    'assigned_grade': submission.get('assignedGrade'),
                    'alternate_link': submission.get('alternateLink'),
                    'course_work_type': submission.get('courseWorkType'),
                    'submission_history': submission.get('submissionHistory', [])
                }
                formatted_submissions.append(formatted_submission)
            
            return formatted_submissions
            
        except HttpError as e:
            logger.error(f"HTTP error getting submissions: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting submissions: {e}")
            raise
    
    def refresh_credentials(self, refresh_token: str) -> Credentials:
        """Refresh expired credentials"""
        try:
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                scopes=self.SCOPES
            )
            
            credentials.refresh(Request())
            return credentials
            
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            raise
    
    def create_credentials_from_token(self, access_token: str, refresh_token: str = None) -> Credentials:
        """Create credentials object from tokens"""
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            scopes=self.SCOPES
        )
