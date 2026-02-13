"""
Multi-User Database Schema with Authentication
Supports PostgreSQL for production and SQLite for development
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, 
    ForeignKey, Float, Boolean, Index
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.pool import StaticPool
from datetime import datetime
from passlib.context import CryptContext
import os
from typing import Optional

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database URL from environment variable or default to SQLite
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./wound_ai_multiuser.db"
)

# Handle PostgreSQL URL format (some platforms use postgres:// instead of postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:
    # PostgreSQL settings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=10,
        max_overflow=20
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================
# USER MANAGEMENT
# =========================

class User(Base):
    """User accounts with authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    
    # Role-based access control
    role = Column(String(20), default="nurse")  # nurse, doctor, admin
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Organization/Hospital
    organization = Column(String(100))
    department = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(password, self.hashed_password)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

# Indexes for common queries
Index('idx_user_email_active', User.email, User.is_active)

# =========================
# WOUND CASES
# =========================

class Case(Base):
    """Wound assessment cases - now linked to users"""
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Case identification
    case_code = Column(String(50), unique=True, index=True, nullable=False)
    patient_mrn = Column(String(50), index=True)  # Medical Record Number (encrypted in production)
    
    # Wound characteristics
    wound_type = Column(String(100))
    location = Column(String(100))  # Anatomical location
    
    # Measurements
    size_cm2 = Column(Float)
    length_cm = Column(Float)
    width_cm = Column(Float)
    depth_cm = Column(Float, nullable=True)
    
    # Clinical assessment
    infection_risk_score = Column(Float)
    infection_risk_level = Column(String(50))
    severity = Column(String(50))
    
    # Braden scale
    braden_score = Column(Integer, nullable=True)
    braden_risk_level = Column(String(50), nullable=True)
    
    # AI outputs
    ai_summary = Column(Text)
    treatment_plan = Column(Text)
    dressing_recommendation = Column(Text)
    
    # Status tracking
    status = Column(String(20), default="active")  # active, healing, healed, referred
    priority = Column(String(20), default="routine")  # routine, urgent, emergency
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    wound_onset_date = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="cases")
    images = relationship("CaseImage", back_populates="case", cascade="all, delete-orphan")
    followups = relationship("FollowUp", back_populates="case", cascade="all, delete-orphan")
    tissue_analysis = relationship("TissueAnalysis", back_populates="case", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Case {self.case_code} - {self.wound_type}>"

# Indexes for efficient queries
Index('idx_case_user_created', Case.user_id, Case.created_at.desc())
Index('idx_case_status', Case.status, Case.priority)
Index('idx_case_patient', Case.patient_mrn, Case.user_id)

# =========================
# CASE IMAGES
# =========================

class CaseImage(Base):
    """Images associated with wound cases"""
    __tablename__ = "case_images"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    
    # Image metadata
    filename = Column(String(255))
    file_path = Column(String(500))  # For cloud storage URLs
    image_type = Column(String(20), default="wound")  # wound, reference, before, after
    
    # Image characteristics
    width_px = Column(Integer)
    height_px = Column(Integer)
    file_size_kb = Column(Integer)
    
    # CLIP embedding for similarity search (stored as JSON string)
    embedding = Column(Text, nullable=True)
    
    # Analysis metadata
    segmentation_confidence = Column(Float, nullable=True)
    
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="images")
    
    def __repr__(self):
        return f"<CaseImage {self.filename}>"

Index('idx_image_case', CaseImage.case_id, CaseImage.uploaded_at.desc())

# =========================
# TISSUE ANALYSIS
# =========================

class TissueAnalysis(Base):
    """Detailed tissue composition analysis"""
    __tablename__ = "tissue_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("case_images.id"), nullable=True)
    
    # Tissue percentages
    granulation_percent = Column(Float, default=0.0)
    epithelial_percent = Column(Float, default=0.0)
    slough_percent = Column(Float, default=0.0)
    necrotic_percent = Column(Float, default=0.0)
    eschar_percent = Column(Float, default=0.0)
    
    # Exudate characteristics
    exudate_level = Column(String(20))  # none, light, moderate, heavy
    exudate_type = Column(String(50))  # serous, serosanguineous, sanguineous, purulent
    
    # Additional observations
    odor_present = Column(Boolean, default=False)
    undermining_present = Column(Boolean, default=False)
    tunneling_present = Column(Boolean, default=False)
    
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="tissue_analysis")
    
    def __repr__(self):
        return f"<TissueAnalysis case={self.case_id}>"

# =========================
# FOLLOW-UPS
# =========================

class FollowUp(Base):
    """Follow-up assessments and notes"""
    __tablename__ = "followups"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    
    # Follow-up details
    followup_type = Column(String(50), default="routine")  # routine, urgent, scheduled
    note = Column(Text)
    
    # Changes observed
    size_change_cm2 = Column(Float, nullable=True)  # + improvement, - deterioration
    healing_progress = Column(String(50))  # improving, stable, deteriorating
    
    # Treatment adjustments
    treatment_changed = Column(Boolean, default=False)
    new_dressing = Column(String(200), nullable=True)
    
    # Next steps
    next_assessment_date = Column(DateTime, nullable=True)
    escalation_needed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    case = relationship("Case", back_populates="followups")
    
    def __repr__(self):
        return f"<FollowUp case={self.case_id} date={self.created_at}>"

Index('idx_followup_case_date', FollowUp.case_id, FollowUp.created_at.desc())

# =========================
# CHAT HISTORY
# =========================

class ChatSession(Base):
    """Chat sessions for continuity"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    
    title = Column(String(200), nullable=True)  # Auto-generated from first message
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatSession {self.session_id}>"

class ChatMessage(Base):
    """Individual chat messages"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    
    role = Column(String(20), nullable=False)  # user, assistant
    message = Column(Text, nullable=False)
    
    # Optional image data (base64)
    image_data = Column(Text, nullable=True)
    image_analysis = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    def __repr__(self):
        return f"<ChatMessage {self.role} at {self.created_at}>"

Index('idx_chat_session_date', ChatMessage.session_id, ChatMessage.created_at.desc())

# =========================
# AUDIT LOG
# =========================

class AuditLog(Base):
    """Track all system actions for compliance"""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    action = Column(String(100), nullable=False)  # create_case, update_case, login, etc.
    resource_type = Column(String(50))  # case, user, chat, etc.
    resource_id = Column(Integer, nullable=True)
    
    details = Column(Text, nullable=True)  # JSON string with additional info
    ip_address = Column(String(45), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditLog {self.action} by user={self.user_id}>"

Index('idx_audit_user_date', AuditLog.user_id, AuditLog.created_at.desc())
Index('idx_audit_action', AuditLog.action, AuditLog.created_at.desc())

# =========================
# DATABASE INITIALIZATION
# =========================

def init_db():
    """Initialize database and create all tables"""
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")

def get_db():
    """Dependency for FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_admin_user(
    username: str,
    email: str,
    password: str,
    full_name: str = "Admin User"
) -> Optional[User]:
    """Create initial admin user"""
    db = SessionLocal()
    try:
        # Check if user exists
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            print(f"⚠ User {username} already exists")
            return None
        
        # Create admin user
        admin = User(
            username=username,
            email=email,
            hashed_password=User.hash_password(password),
            full_name=full_name,
            role="admin",
            is_active=True,
            is_verified=True
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print(f"✓ Admin user created: {username}")
        return admin
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error creating admin user: {e}")
        return None
    finally:
        db.close()

# =========================
# EXAMPLE USAGE
# =========================

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    
    print("\nCreating admin user...")
    create_admin_user(
        username="admin",
        email="admin@woundai.com",
        password="changeme123",  # Change this!
        full_name="System Administrator"
    )
    
    print("\nDatabase setup complete!")
    print(f"Database URL: {DATABASE_URL}")
    print("\nTables created:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
