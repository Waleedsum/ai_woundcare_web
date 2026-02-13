"""
Wound AI System - Integrated Version with All Enhancements
Combines: Multi-user auth, enhanced infection scoring, improved size estimation
"""

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
import os
from datetime import datetime, timedelta
from PIL import Image
import io
import base64
import uuid

# Import database models
from database_schema_multiuser import (
    User, Case, CaseImage, TissueAnalysis, FollowUp, ChatSession, ChatMessage,
    get_db, SessionLocal
)

# Import authentication
from auth_system import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_active_user,
    authenticate_user,
    require_role,
    log_action,
    verify_token
)

# Import enhanced calculators
from infection_risk_enhanced import InfectionRiskCalculator
from wound_size_enhanced import WoundSizeEstimator

# Import OpenAI for AI analysis
from openai import OpenAI

# =========================
# APP CONFIGURATION
# =========================

app = FastAPI(
    title="Wound AI System",
    description="AI-powered wound assessment with multi-user support",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize calculators
infection_calculator = InfectionRiskCalculator()
size_estimator = WoundSizeEstimator()

# Upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =========================
# PYDANTIC MODELS
# =========================

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    organization: Optional[str] = None
    department: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class CaseCreate(BaseModel):
    patient_mrn: Optional[str] = None
    wound_type: Optional[str] = None
    location: Optional[str] = None
    wound_onset_date: Optional[datetime] = None

class CaseResponse(BaseModel):
    id: int
    case_code: str
    patient_mrn: Optional[str]
    wound_type: Optional[str]
    location: Optional[str]
    size_cm2: Optional[float]
    infection_risk_score: Optional[float]
    infection_risk_level: Optional[str]
    ai_summary: Optional[str]
    created_at: datetime
    status: str

class FollowUpCreate(BaseModel):
    note: str
    followup_type: str = "routine"
    healing_progress: Optional[str] = None
    treatment_changed: bool = False
    new_dressing: Optional[str] = None

# =========================
# HELPER FUNCTIONS
# =========================

def generate_case_code() -> str:
    """Generate unique case code"""
    return f"CASE{uuid.uuid4().hex[:8].upper()}"

def save_image(file: UploadFile, case_code: str) -> str:
    """Save uploaded image and return path"""
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{case_code}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    
    return filepath

def image_to_base64(filepath: str) -> str:
    """Convert image to base64 for AI analysis"""
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode()

def analyze_wound_with_ai(image_base64: str, wound_context: str) -> Dict:
    """
    Analyze wound using GPT-4 Vision
    Returns tissue composition and clinical observations
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Analyze this wound image and provide detailed assessment.

Context: {wound_context}

Please provide:
1. Tissue composition (granulation %, slough %, necrotic %, epithelial %)
2. Wound characteristics (color, texture, edges)
3. Exudate level (none/light/moderate/heavy) and type
4. Signs of infection or complications
5. Healing stage assessment
6. Clinical recommendations

Format your response as JSON with these keys:
- tissue_percentages: dict with granulation_percent, slough_percent, necrotic_percent, epithelial_percent
- wound_characteristics: string description
- exudate_level: string (none/light/moderate/heavy)
- exudate_type: string
- infection_signs: list of observed signs
- healing_stage: string
- recommendations: list of clinical recommendations
- summary: brief overall assessment
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # Parse AI response
        import json
        ai_text = response.choices[0].message.content
        
        # Extract JSON from response
        json_start = ai_text.find("{")
        json_end = ai_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            ai_analysis = json.loads(ai_text[json_start:json_end])
        else:
            # Fallback if JSON not properly formatted
            ai_analysis = {
                "summary": ai_text,
                "tissue_percentages": {
                    "granulation_percent": 50,
                    "slough_percent": 30,
                    "necrotic_percent": 10,
                    "epithelial_percent": 10
                },
                "exudate_level": "moderate",
                "exudate_type": "serous",
                "infection_signs": [],
                "recommendations": ["Monitor wound progress", "Continue current treatment"]
            }
        
        return ai_analysis
        
    except Exception as e:
        print(f"AI analysis error: {e}")
        return {
            "summary": "AI analysis unavailable",
            "tissue_percentages": {
                "granulation_percent": 0,
                "slough_percent": 0,
                "necrotic_percent": 0,
                "epithelial_percent": 0
            },
            "exudate_level": "unknown",
            "recommendations": []
        }

# =========================
# AUTHENTICATION ENDPOINTS
# =========================

@app.post("/register", status_code=201)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """Register new user"""
    # Check if user exists
    existing = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Username or email already registered"
        )
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=User.hash_password(user_data.password),
        full_name=user_data.full_name,
        organization=user_data.organization,
        department=user_data.department,
        role="nurse",
        is_active=True,
        is_verified=False
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log action
    log_action(db, user.id, "register", "user", user.id)
    
    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "username": user.username
    }

@app.post("/token", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """User login - returns JWT tokens"""
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    })
    
    refresh_token = create_refresh_token({"user_id": user.id})
    
    # Log login
    log_action(db, user.id, "login")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@app.post("/token/refresh")
async def refresh_access_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    payload = verify_token(refresh_token, token_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    })
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "organization": current_user.organization,
        "department": current_user.department,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }

# =========================
# WOUND ANALYSIS ENDPOINTS
# =========================

@app.post("/analyze")
async def analyze_wound(
    file: UploadFile = File(...),
    patient_mrn: Optional[str] = Form(None),
    wound_type: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    days_since_onset: Optional[int] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Analyze wound image with enhanced AI
    Returns comprehensive assessment with infection risk and size estimation
    """
    
    # Generate case code
    case_code = generate_case_code()
    
    # Save image
    image_path = save_image(file, case_code)
    
    try:
        # Load image
        image = Image.open(image_path)
        
        # 1. ENHANCED WOUND SIZE ESTIMATION
        size_result = size_estimator.estimate_wound_size(
            image=image,
            calibration_type="smartphone_close",
            return_mask=True
        )
        
        wound_size_cm2 = size_result["size_cm2"]
        wound_length = size_result["length_cm"]
        wound_width = size_result["width_cm"]
        size_confidence = size_result["confidence"]
        
        # 2. AI VISION ANALYSIS
        image_base64 = image_to_base64(image_path)
        wound_context = f"Wound type: {wound_type or 'unknown'}, Location: {location or 'unknown'}"
        
        ai_analysis = analyze_wound_with_ai(image_base64, wound_context)
        
        tissue_percentages = ai_analysis.get("tissue_percentages", {})
        exudate_level = ai_analysis.get("exudate_level", "moderate")
        infection_signs = ai_analysis.get("infection_signs", [])
        
        # 3. ENHANCED INFECTION RISK SCORING
        clinical_text = f"{wound_type or ''} {' '.join(infection_signs)} {ai_analysis.get('summary', '')}"
        
        # Prepare patient factors (can be expanded)
        patient_factors = {
            "diabetes": False,  # Would come from patient records
            "immunosuppressed": False,
            "poor_circulation": False
        }
        
        risk_result = infection_calculator.calculate_risk(
            clinical_text=clinical_text,
            tissue_counts=tissue_percentages,
            wound_size_cm2=wound_size_cm2,
            exudate_level=exudate_level,
            days_since_onset=days_since_onset,
            patient_factors=patient_factors
        )
        
        infection_risk_score = risk_result["total_score"]
        infection_risk_level = risk_result["risk_level"]
        
        # 4. CREATE CASE IN DATABASE
        case = Case(
            user_id=current_user.id,
            case_code=case_code,
            patient_mrn=patient_mrn,
            wound_type=wound_type,
            location=location,
            size_cm2=wound_size_cm2,
            length_cm=wound_length,
            width_cm=wound_width,
            infection_risk_score=infection_risk_score,
            infection_risk_level=infection_risk_level,
            ai_summary=ai_analysis.get("summary", ""),
            treatment_plan="\n".join(ai_analysis.get("recommendations", [])),
            status="active",
            wound_onset_date=datetime.utcnow() - timedelta(days=days_since_onset) if days_since_onset else None
        )
        
        db.add(case)
        db.flush()  # Get case ID
        
        # 5. SAVE IMAGE RECORD
        case_image = CaseImage(
            case_id=case.id,
            filename=os.path.basename(image_path),
            file_path=image_path,
            image_type="wound",
            width_px=image.width,
            height_px=image.height,
            segmentation_confidence=size_confidence
        )
        
        db.add(case_image)
        
        # 6. SAVE TISSUE ANALYSIS
        tissue_analysis = TissueAnalysis(
            case_id=case.id,
            image_id=case_image.id,
            granulation_percent=tissue_percentages.get("granulation_percent", 0),
            epithelial_percent=tissue_percentages.get("epithelial_percent", 0),
            slough_percent=tissue_percentages.get("slough_percent", 0),
            necrotic_percent=tissue_percentages.get("necrotic_percent", 0),
            exudate_level=exudate_level,
            exudate_type=ai_analysis.get("exudate_type", "serous")
        )
        
        db.add(tissue_analysis)
        db.commit()
        
        # Log action
        log_action(db, current_user.id, "analyze_wound", "case", case.id)
        
        # 7. RETURN COMPREHENSIVE RESPONSE
        return {
            "success": True,
            "case_code": case_code,
            "case_id": case.id,
            "wound_assessment": {
                "size_cm2": wound_size_cm2,
                "length_cm": wound_length,
                "width_cm": wound_width,
                "size_confidence": size_confidence,
                "infection_risk": {
                    "score": infection_risk_score,
                    "level": infection_risk_level,
                    "subscores": risk_result["subscores"],
                    "interpretation": risk_result["interpretation"]
                },
                "tissue_composition": tissue_percentages,
                "exudate": {
                    "level": exudate_level,
                    "type": ai_analysis.get("exudate_type", "")
                },
                "healing_stage": ai_analysis.get("healing_stage", ""),
                "ai_summary": ai_analysis.get("summary", ""),
                "recommendations": ai_analysis.get("recommendations", [])
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )

# =========================
# CASE MANAGEMENT ENDPOINTS
# =========================

@app.get("/cases", response_model=List[CaseResponse])
async def list_cases(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's cases"""
    query = db.query(Case).filter(Case.user_id == current_user.id)
    
    if status:
        query = query.filter(Case.status == status)
    
    cases = query.order_by(Case.created_at.desc()).limit(limit).all()
    
    return cases

@app.get("/cases/{case_code}")
async def get_case(
    case_code: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed case information"""
    case = db.query(Case).filter(
        Case.case_code == case_code,
        Case.user_id == current_user.id
    ).first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get related data
    images = db.query(CaseImage).filter(CaseImage.case_id == case.id).all()
    tissue_analysis = db.query(TissueAnalysis).filter(
        TissueAnalysis.case_id == case.id
    ).order_by(TissueAnalysis.analyzed_at.desc()).first()
    followups = db.query(FollowUp).filter(
        FollowUp.case_id == case.id
    ).order_by(FollowUp.created_at.desc()).all()
    
    return {
        "case": {
            "id": case.id,
            "case_code": case.case_code,
            "patient_mrn": case.patient_mrn,
            "wound_type": case.wound_type,
            "location": case.location,
            "size_cm2": case.size_cm2,
            "length_cm": case.length_cm,
            "width_cm": case.width_cm,
            "infection_risk_score": case.infection_risk_score,
            "infection_risk_level": case.infection_risk_level,
            "ai_summary": case.ai_summary,
            "treatment_plan": case.treatment_plan,
            "status": case.status,
            "created_at": case.created_at,
            "updated_at": case.updated_at
        },
        "images": [
            {
                "id": img.id,
                "filename": img.filename,
                "uploaded_at": img.uploaded_at,
                "confidence": img.segmentation_confidence
            } for img in images
        ],
        "tissue_analysis": {
            "granulation_percent": tissue_analysis.granulation_percent,
            "slough_percent": tissue_analysis.slough_percent,
            "necrotic_percent": tissue_analysis.necrotic_percent,
            "epithelial_percent": tissue_analysis.epithelial_percent,
            "exudate_level": tissue_analysis.exudate_level,
            "exudate_type": tissue_analysis.exudate_type
        } if tissue_analysis else None,
        "followups": [
            {
                "id": fu.id,
                "note": fu.note,
                "healing_progress": fu.healing_progress,
                "created_at": fu.created_at
            } for fu in followups
        ]
    }

@app.post("/cases/{case_code}/followup")
async def add_followup(
    case_code: str,
    followup_data: FollowUpCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add follow-up note to case"""
    case = db.query(Case).filter(
        Case.case_code == case_code,
        Case.user_id == current_user.id
    ).first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    followup = FollowUp(
        case_id=case.id,
        followup_type=followup_data.followup_type,
        note=followup_data.note,
        healing_progress=followup_data.healing_progress,
        treatment_changed=followup_data.treatment_changed,
        new_dressing=followup_data.new_dressing
    )
    
    db.add(followup)
    db.commit()
    
    log_action(db, current_user.id, "add_followup", "case", case.id)
    
    return {"message": "Follow-up added successfully", "followup_id": followup.id}

# =========================
# HEALTH & INFO ENDPOINTS
# =========================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Wound AI System",
        "version": "2.0.0",
        "description": "AI-powered wound assessment with multi-user support",
        "features": [
            "Multi-user authentication",
            "Enhanced infection risk scoring",
            "Improved wound size estimation",
            "AI-powered tissue analysis",
            "Case management",
            "Follow-up tracking"
        ],
        "endpoints": {
            "auth": ["/register", "/token", "/token/refresh", "/me"],
            "analysis": ["/analyze"],
            "cases": ["/cases", "/cases/{code}", "/cases/{code}/followup"],
            "health": ["/health", "/docs"]
        }
    }

# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":
    import uvicorn
    
    # Initialize database
    print("🔧 Initializing database...")
    from database_schema_multiuser import init_db
    init_db()
    
    print("✅ Database initialized")
    print("🚀 Starting Wound AI System...")
    print("📡 API Documentation: http://localhost:8000/docs")
    print("🔐 Authentication required for all endpoints except /register and /token")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
