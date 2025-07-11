from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.models.models import User
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db
    
    def set_db(self, db: Session):
        """Set the database session"""
        self.db = db
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        if not self.db:
            raise ValueError("Database session not set")
        return self.db.query(User).filter(User.email == email).first()
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        # Google OAuth users don't have password
        if user.hashed_password is None:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    def create_user(self, user_data: dict) -> User:
        if not self.db:
            raise ValueError("Database session not set")
        hashed_password = self.get_password_hash(user_data["password"])
        db_user = User(
            email=user_data["email"],
            username=user_data["username"],
            hashed_password=hashed_password,
            full_name=user_data["full_name"],
            role=user_data["role"]
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def create_google_user(self, user_data: dict) -> User:
        """Create a user with Google OAuth data"""
        if not self.db:
            raise ValueError("Database session not set")
        db_user = User(
            email=user_data["email"],
            username=user_data["username"],
            hashed_password=None,  # Google authenticated users don't need password
            full_name=user_data["full_name"],
            role=user_data["role"],
            google_id=user_data.get("google_id"),
            google_access_token=user_data.get("google_access_token"),
            google_refresh_token=user_data.get("google_refresh_token"),
            google_token_expires_at=user_data.get("google_token_expires_at")
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def get_current_user(self, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
        except JWTError:
            return None
        
        # If no db session is set, we need to create one for this operation
        if not self.db:
            from app.db.connector import get_postgres_session
            with get_postgres_session() as session:
                return session.query(User).filter(User.email == email).first()
        else:
            return self.get_user_by_email(email)


# Global instance for easy importing
auth_service = AuthService()
