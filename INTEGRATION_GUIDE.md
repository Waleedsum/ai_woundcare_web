# 🔧 Complete Integration Guide
## Merging Enhanced Features with Your Existing Wound AI System

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Integration Strategy](#integration-strategy)
3. [Step-by-Step Integration](#step-by-step-integration)
4. [Modified Files Reference](#modified-files-reference)
5. [Testing After Integration](#testing-after-integration)
6. [Deployment Options](#deployment-options)

---

## 🎯 Overview

### What You Have Now
- Original `wound_ai_system_full_fixed.py` (your main FastAPI application)
- SQLite database (single-user)
- Basic infection scoring
- Simple wound size estimation

### What You're Adding
1. **Enhanced Infection Risk Scoring** (`infection_risk_enhanced.py`)
2. **Improved Wound Size Estimation** (`wound_size_enhanced.py`)
3. **Multi-User Database** (`database_schema_multiuser.py`)
4. **JWT Authentication** (`auth_system.py`)
5. **Production Deployment Setup** (Docker, configs, guides)

### Integration Approach
**You have 2 options:**

#### Option A: Full Migration (Recommended)
Migrate everything to the new multi-user system with all enhancements. Best for new deployments or if you haven't deployed yet.

#### Option B: Gradual Integration
Add enhancements one-by-one to your existing system. Good if you already have data in production.

---

## 🔀 Integration Strategy

### Option A: Full Migration (Start Fresh)

**Best for:** New projects or pre-production systems

**Steps:**
1. Replace database with multi-user schema
2. Add authentication layer
3. Update API endpoints for authentication
4. Integrate enhanced infection scoring
5. Integrate improved wound size estimation
6. Deploy

**Timeline:** 1-2 days
**Complexity:** Medium
**Result:** Complete production-ready system

---

### Option B: Gradual Integration (Keep Existing)

**Best for:** Systems already in production with data

**Steps:**
1. Add enhanced modules without breaking existing code
2. Migrate data from SQLite to PostgreSQL
3. Add authentication gradually
4. Test each component before moving to next

**Timeline:** 3-5 days
**Complexity:** Higher (requires careful testing)
**Result:** Backward-compatible migration

---

## 📝 Step-by-Step Integration

### OPTION A: FULL MIGRATION (Recommended)

#### Step 1: Prepare Your Environment

```bash
# Create new directory for integrated system
mkdir wound-ai-integrated
cd wound-ai-integrated

# Copy your existing main file
cp /path/to/wound_ai_system_full_fixed.py .

# Copy new enhancement files
cp infection_risk_enhanced.py .
cp wound_size_enhanced.py .
cp database_schema_multiuser.py .
cp auth_system.py .
cp requirements.txt .
cp Dockerfile .
cp docker-compose.yml .
```

#### Step 2: Update Requirements

Add to your `requirements.txt` (if not already present):

```txt
# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9  # For PostgreSQL
```

Install:
```bash
pip install -r requirements.txt
```

#### Step 3: Modify Your Main Application File

I'll create a **new integrated version** of your main file that includes all enhancements.

**File:** `wound_ai_system_integrated.py`

This file will:
- Import from `database_schema_multiuser.py`
- Import from `auth_system.py`
- Use `InfectionRiskCalculator` from `infection_risk_enhanced.py`
- Use `WoundSizeEstimator` from `wound_size_enhanced.py`
- Add authentication to all endpoints
- Support multi-user cases

#### Step 4: Initialize Database

```bash
# Set environment variable for PostgreSQL (or keep SQLite for development)
export DATABASE_URL="postgresql://woundai_user:password@localhost:5432/woundai_db"
# OR for development/testing:
export DATABASE_URL="sqlite:///./wound_ai_multiuser.db"

# Initialize database
python database_schema_multiuser.py

# Create admin user
python -c "
from database_schema_multiuser import create_admin_user
create_admin_user(
    username='admin',
    email='admin@example.com',
    password='changeme123',
    full_name='System Admin'
)
"
```

#### Step 5: Test the Integrated System

```bash
# Run the application
python wound_ai_system_integrated.py
# OR with uvicorn:
uvicorn wound_ai_system_integrated:app --reload --host 0.0.0.0 --port 8000
```

Test endpoints:
```bash
# 1. Register a user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nurse1",
    "email": "nurse1@example.com",
    "password": "password123",
    "full_name": "Jane Nurse"
  }'

# 2. Login
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nurse1&password=password123"

# Save the access_token from response

# 3. Create a case (with authentication)
curl -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_mrn": "12345",
    "wound_type": "pressure ulcer",
    "location": "sacrum"
  }'
```

---

### OPTION B: GRADUAL INTEGRATION

#### Phase 1: Add Enhanced Modules (No Breaking Changes)

**Step 1:** Add new files alongside existing ones

```bash
# Keep your original file unchanged
# Add new modules:
cp infection_risk_enhanced.py /your/project/
cp wound_size_enhanced.py /your/project/
```

**Step 2:** Update your existing `wound_ai_system_full_fixed.py` to use new modules

Add these imports at the top:
```python
from infection_risk_enhanced import InfectionRiskCalculator
from wound_size_enhanced import WoundSizeEstimator
```

Replace infection scoring section (around line where you calculate infection risk):

**OLD CODE:**
```python
# Your original infection scoring
infection_keywords = ["purulent", "necrotic", ...]
infection_risk = sum(keyword in text.lower() for keyword in infection_keywords)
```

**NEW CODE:**
```python
# Enhanced infection scoring
risk_calculator = InfectionRiskCalculator()
risk_result = risk_calculator.calculate_risk(
    clinical_text=f"{wound_type} {tissue_types} {exudate}",
    tissue_counts={
        "granulation_percent": tissue_counts.get("granulation", 0),
        "slough_percent": tissue_counts.get("slough", 0),
        "necrotic_percent": tissue_counts.get("necrotic", 0)
    },
    wound_size_cm2=wound_size,
    exudate_level=exudate,
    days_since_onset=None,  # Add if you track this
    patient_factors=None    # Add patient risk factors if available
)

infection_risk_score = risk_result["total_score"]
infection_risk_level = risk_result["risk_level"]
```

Replace wound size estimation:

**OLD CODE:**
```python
# Your original size estimation
wound_size = pixel_count * 0.015
```

**NEW CODE:**
```python
# Enhanced wound size estimation
size_estimator = WoundSizeEstimator()
size_result = size_estimator.estimate_wound_size(
    image=image,
    calibration_type="smartphone_close",
    return_mask=True
)

wound_size = size_result["size_cm2"]
wound_length = size_result["length_cm"]
wound_width = size_result["width_cm"]
segmentation_confidence = size_result["confidence"]
```

**Step 3:** Test the enhanced features

```bash
# Run your existing system with new enhancements
python wound_ai_system_full_fixed.py
```

Test by uploading wound images and verifying improved accuracy.

---

#### Phase 2: Migrate to Multi-User Database

**Step 1:** Export existing data

```bash
# If using SQLite
sqlite3 wound_ai.db .dump > data_backup.sql
```

**Step 2:** Set up PostgreSQL

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE woundai_db;
CREATE USER woundai_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE woundai_db TO woundai_user;
\q
```

**Step 3:** Initialize new schema

```bash
# Set environment variable
export DATABASE_URL="postgresql://woundai_user:your_password@localhost:5432/woundai_db"

# Run new schema
python database_schema_multiuser.py
```

**Step 4:** Migrate your data

Create a migration script: `migrate_data.py`

```python
"""
Data migration script from old SQLite to new PostgreSQL
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlite3

# Old database
old_db = sqlite3.connect("wound_ai.db")
old_cursor = old_db.cursor()

# New database
from database_schema_multiuser import SessionLocal, User, Case

new_db = SessionLocal()

try:
    # Create default user for old cases
    default_user = User(
        username="legacy_user",
        email="legacy@example.com",
        hashed_password=User.hash_password("changeme"),
        full_name="Legacy User",
        role="nurse",
        is_active=True
    )
    new_db.add(default_user)
    new_db.commit()
    
    # Migrate cases
    old_cursor.execute("SELECT * FROM cases")  # Adjust to your table name
    old_cases = old_cursor.fetchall()
    
    for old_case in old_cases:
        # Map old fields to new schema
        new_case = Case(
            user_id=default_user.id,
            case_code=old_case[1],  # Adjust indices based on your schema
            wound_type=old_case[2],
            # ... map other fields
        )
        new_db.add(new_case)
    
    new_db.commit()
    print(f"✅ Migrated {len(old_cases)} cases")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    new_db.rollback()
finally:
    new_db.close()
    old_db.close()
```

Run migration:
```bash
python migrate_data.py
```

---

#### Phase 3: Add Authentication

**Step 1:** Import authentication modules

Add to your main file:
```python
from auth_system import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_active_user,
    authenticate_user,
    require_role,
    log_action
)
from fastapi.security import OAuth2PasswordRequestForm
```

**Step 2:** Add authentication endpoints

```python
@app.post("/register")
async def register(
    username: str,
    email: str,
    password: str,
    full_name: str,
    db: Session = Depends(get_db)
):
    """Register new user"""
    # Check if user exists
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    user = User(
        username=username,
        email=email,
        hashed_password=User.hash_password(password),
        full_name=full_name,
        role="nurse",
        is_active=True
    )
    
    db.add(user)
    db.commit()
    
    # Log action
    log_action(db, user.id, "register", "user", user.id)
    
    return {"message": "User registered successfully"}


@app.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """User login - returns JWT tokens"""
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
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
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
```

**Step 3:** Protect existing endpoints

Update case creation endpoint:

**OLD:**
```python
@app.post("/analyze")
async def analyze_wound(file: UploadFile):
    # ... existing code
```

**NEW:**
```python
@app.post("/analyze")
async def analyze_wound(
    file: UploadFile,
    current_user: User = Depends(get_current_active_user),  # ADD THIS
    db: Session = Depends(get_db)
):
    # ... existing code
    
    # When creating case, link to user:
    case = Case(
        user_id=current_user.id,  # ADD THIS
        case_code=generate_case_code(),
        wound_type=wound_type,
        # ... other fields
    )
    db.add(case)
    db.commit()
```

---

## 📁 Modified Files Reference

Here's what changes in each file:

### 1. `requirements.txt`
**Action:** Replace or merge with new version
- Adds authentication dependencies
- Adds PostgreSQL support
- Updates to latest compatible versions

### 2. `wound_ai_system_full_fixed.py` → `wound_ai_system_integrated.py`
**Action:** Use new integrated version OR modify existing file

**Key Changes:**
- Import from `database_schema_multiuser`
- Import from `auth_system`
- Import enhanced calculators
- Add authentication decorators to endpoints
- Link cases to users
- Use enhanced infection and size calculations

### 3. New Files to Add:
- `infection_risk_enhanced.py` - Drop in, use as module
- `wound_size_enhanced.py` - Drop in, use as module
- `database_schema_multiuser.py` - Replace old schema
- `auth_system.py` - Add authentication layer

### 4. Configuration Files:
- `Dockerfile` - For containerized deployment
- `docker-compose.yml` - Multi-container orchestration
- `.env` - Environment variables (create this)

---

## 🧪 Testing After Integration

### Test Checklist

#### 1. Basic Functionality
```bash
# Health check
curl http://localhost:8000/health

# Should return 200 OK
```

#### 2. Authentication Flow
```bash
# Register
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"test123","full_name":"Test User"}'

# Login
curl -X POST http://localhost:8000/token \
  -F "username=test" \
  -F "password=test123"

# Save token
TOKEN="<access_token_from_response>"
```

#### 3. Wound Analysis
```bash
# Upload image with authentication
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@wound_image.jpg"
```

#### 4. Case Management
```bash
# List cases
curl http://localhost:8000/cases \
  -H "Authorization: Bearer $TOKEN"

# Get specific case
curl http://localhost:8000/cases/CASE001 \
  -H "Authorization: Bearer $TOKEN"
```

#### 5. Enhanced Features
- Upload wound images and verify infection scores use new multi-factor system
- Check that wound sizes are more accurate with enhanced estimator
- Verify confidence scores are included in responses

---

## 🚀 Deployment Options

### Option 1: Quick Deploy with Render (Easiest)

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "Integrated wound AI system"
git remote add origin https://github.com/yourusername/wound-ai.git
git push -u origin main
```

2. **Set up on Render:**
- Go to https://render.com
- Click "New +" → "PostgreSQL"
  - Name: `woundai-db`
  - Save the Internal Database URL

- Click "New +" → "Web Service"
  - Connect GitHub repository
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT wound_ai_system_integrated:app`
  
- **Environment Variables:**
  ```
  DATABASE_URL=<from PostgreSQL service>
  JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
  JWT_REFRESH_SECRET_KEY=<generate with: openssl rand -hex 32>
  OPENAI_API_KEY=sk-your-key
  ```

3. **Deploy:**
- Click "Create Web Service"
- Wait for deployment (5-10 minutes)
- Access at `https://your-app-name.onrender.com`

---

### Option 2: Docker Deployment

```bash
# Build and run with docker-compose
docker-compose up -d

# Initialize database
docker-compose exec app python database_schema_multiuser.py

# Create admin user
docker-compose exec app python -c "
from database_schema_multiuser import create_admin_user
create_admin_user('admin', 'admin@example.com', 'changeme', 'Admin')
"

# Check logs
docker-compose logs -f
```

Access at `http://localhost:8000`

---

### Option 3: Traditional Server

Follow the complete `DEPLOYMENT_GUIDE.md` for Ubuntu/Linux deployment with:
- Nginx reverse proxy
- SSL certificates
- Systemd service
- Automated backups

---

## 🎯 Recommended Integration Path

### For New Projects:
**Use Option A (Full Migration)**
1. Day 1: Set up integrated system
2. Day 1: Test locally with SQLite
3. Day 2: Deploy to Render with PostgreSQL
4. Day 2-3: Develop Android app (optional)

### For Existing Projects:
**Use Option B (Gradual Integration)**
1. Week 1: Add enhanced modules, test
2. Week 2: Migrate to PostgreSQL, test
3. Week 3: Add authentication, test
4. Week 4: Deploy to production

---

## 🆘 Troubleshooting

### Problem: Import errors
**Solution:**
```bash
pip install -r requirements.txt --force-reinstall
```

### Problem: Database connection errors
**Solution:**
```bash
# Check DATABASE_URL format
echo $DATABASE_URL

# For PostgreSQL, should be:
# postgresql://user:password@host:port/database

# Test connection
python -c "from database_schema_multiuser import engine; print(engine.url)"
```

### Problem: Authentication not working
**Solution:**
```bash
# Verify JWT secrets are set
echo $JWT_SECRET_KEY
echo $JWT_REFRESH_SECRET_KEY

# Generate new ones if needed
openssl rand -hex 32
```

### Problem: Old endpoints don't work with auth
**Solution:** Add authentication bypass for testing:
```python
# Temporary - for testing only
from typing import Optional

async def get_optional_user(
    token: Optional[str] = None
) -> Optional[User]:
    if token:
        return get_current_user(token)
    return None

# Use in endpoint
@app.get("/test")
async def test(user: Optional[User] = Depends(get_optional_user)):
    if user:
        return {"authenticated": True, "user": user.username}
    return {"authenticated": False}
```

---

## 📞 Next Steps

1. **Choose your integration path** (A or B)
2. **Follow the steps** for your chosen path
3. **Test thoroughly** with the test checklist
4. **Deploy** using your preferred method
5. **Monitor** and adjust as needed

---

## 📚 Additional Resources

- **Full Deployment Guide:** See `DEPLOYMENT_GUIDE.md`
- **Android Integration:** See `ANDROID_INTEGRATION.md`
- **System Architecture:** See `SYSTEM_ARCHITECTURE.md`
- **Database Schema:** See `database_schema_multiuser.py` docstrings
- **Auth System:** See `auth_system.py` docstrings

---

**Questions or Issues?**

Common integration issues and solutions are documented above. For deployment-specific issues, refer to the DEPLOYMENT_GUIDE.md troubleshooting section.

---

**Version:** 2.0.0  
**Last Updated:** February 2026  
**Status:** Production Ready ✅
