"""
JWT Authentication System for Wound AI
Secure token-based authentication with refresh tokens
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os

# Database imports (adjust path as needed)
from database_schema_multiuser import User, AuditLog, get_db

# =========================
# CONFIGURATION
# =========================

# Secret keys (MUST be set via environment variables in production)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "your-refresh-secret-key-change-in-production")

# Token settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Short-lived access token
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Longer-lived refresh token

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# =========================
# TOKEN FUNCTIONS
# =========================

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    Args:
        data: Dictionary containing user information (user_id, username, role)
        expires_delta: Custom expiration time (optional)
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict) -> str:
    """
    Create JWT refresh token
    
    Args:
        data: Dictionary containing user_id
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Optional[Dict]:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
        token_type: "access" or "refresh"
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        secret_key = REFRESH_SECRET_KEY if token_type == "refresh" else SECRET_KEY
        
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            return None
        
        return payload
        
    except JWTError:
        return None

# =========================
# AUTHENTICATION FUNCTIONS
# =========================

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username/email and password
    
    Args:
        db: Database session
        username: Username or email
        password: Plain text password
        
    Returns:
        User object if authenticated, None otherwise
    """
    # Try to find user by username or email
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()
    
    if not user:
        return None
    
    if not user.is_active:
        return None
    
    if not user.verify_password(password):
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from token
    
    Args:
        token: JWT access token from Authorization header
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify user is active
    
    Args:
        current_user: User from get_current_user dependency
        
    Returns:
        Active user object
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

def require_role(required_roles: list):
    """
    Dependency factory for role-based access control
    
    Args:
        required_roles: List of allowed roles (e.g., ["admin", "doctor"])
        
    Returns:
        Dependency function
        
    Example:
        @app.get("/admin")
        async def admin_only(user: User = Depends(require_role(["admin"]))):
            return {"message": "Admin access"}
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {required_roles}"
            )
        return current_user
    
    return role_checker

# =========================
# AUDIT LOGGING
# =========================

def log_action(
    db: Session,
    user_id: Optional[int],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """
    Log user action to audit trail
    
    Args:
        db: Database session
        user_id: ID of user performing action
        action: Action performed (e.g., "login", "create_case")
        resource_type: Type of resource affected (e.g., "case", "user")
        resource_id: ID of affected resource
        details: Additional details as JSON string
        ip_address: IP address of request
    """
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        print(f"⚠ Audit logging failed: {e}")
        db.rollback()

# =========================
# PASSWORD RESET (OPTIONAL)
# =========================

def create_password_reset_token(user_id: int) -> str:
    """
    Create time-limited password reset token
    
    Args:
        user_id: ID of user requesting reset
        
    Returns:
        Encoded token string
    """
    expire = datetime.utcnow() + timedelta(hours=1)  # 1 hour validity
    
    data = {
        "user_id": user_id,
        "type": "password_reset",
        "exp": expire
    }
    
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_password_reset_token(token: str) -> Optional[int]:
    """
    Verify password reset token
    
    Args:
        token: Reset token string
        
    Returns:
        User ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != "password_reset":
            return None
        
        return payload.get("user_id")
        
    except JWTError:
        return None

# =========================
# EMAIL VERIFICATION (OPTIONAL)
# =========================

def create_verification_token(user_id: int, email: str) -> str:
    """
    Create email verification token
    
    Args:
        user_id: ID of user
        email: Email to verify
        
    Returns:
        Encoded token string
    """
    expire = datetime.utcnow() + timedelta(days=7)  # 7 days validity
    
    data = {
        "user_id": user_id,
        "email": email,
        "type": "email_verification",
        "exp": expire
    }
    
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_email_token(token: str) -> Optional[Dict]:
    """
    Verify email verification token
    
    Args:
        token: Verification token string
        
    Returns:
        Dict with user_id and email if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != "email_verification":
            return None
        
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email")
        }
        
    except JWTError:
        return None

# =========================
# EXAMPLE USAGE
# =========================

if __name__ == "__main__":
    print("JWT Authentication System")
    print("=" * 50)
    
    # Example: Create tokens
    user_data = {
        "user_id": 1,
        "username": "john_doe",
        "role": "nurse"
    }
    
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token({"user_id": 1})
    
    print(f"\nAccess Token: {access_token[:50]}...")
    print(f"Refresh Token: {refresh_token[:50]}...")
    
    # Example: Verify token
    payload = verify_token(access_token, "access")
    print(f"\nDecoded Payload: {payload}")
    
    # Example: Password reset token
    reset_token = create_password_reset_token(1)
    print(f"\nPassword Reset Token: {reset_token[:50]}...")
    
    user_id = verify_password_reset_token(reset_token)
    print(f"Reset Token Valid for User ID: {user_id}")
    
    print("\n✓ JWT system initialized")
    print(f"Access token expires in: {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    print(f"Refresh token expires in: {REFRESH_TOKEN_EXPIRE_DAYS} days")
