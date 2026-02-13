#!/bin/bash

# ========================================
# Wound AI System - Quick Setup Script
# ========================================

echo "🏥 Wound AI System - Quick Setup"
echo "=================================="
echo ""

# Check Python version
echo "📌 Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "🔧 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up environment variables
echo ""
echo "🔑 Setting up environment variables..."

if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=sqlite:///./wound_ai_multiuser.db
# For production, use PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/woundai_db

# JWT Secrets (CHANGE THESE IN PRODUCTION!)
JWT_SECRET_KEY=development-secret-key-change-in-production-12345678901234567890
JWT_REFRESH_SECRET_KEY=development-refresh-key-change-in-production-12345678901234567890

# OpenAI API Key (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Application Settings
APP_ENV=development
DEBUG=True
UPLOAD_DIR=./uploads

# CORS Origins (adjust for production)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
EOF

    echo "✅ .env file created"
    echo "⚠️  IMPORTANT: Edit .env and add your OPENAI_API_KEY"
else
    echo "✅ .env file already exists"
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Create upload directory
echo ""
echo "📁 Creating upload directory..."
mkdir -p uploads
echo "✅ Upload directory created"

# Initialize database
echo ""
echo "🗄️  Initializing database..."
python3 << 'PYTHON'
from database_schema_multiuser import init_db, create_admin_user

# Create tables
init_db()
print("✅ Database tables created")

# Create admin user
admin = create_admin_user(
    username="admin",
    email="admin@woundai.local",
    password="changeme123",
    full_name="System Administrator"
)

if admin:
    print("✅ Admin user created:")
    print("   Username: admin")
    print("   Password: changeme123")
    print("   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
else:
    print("ℹ️  Admin user already exists")
PYTHON

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Edit .env file and add your OpenAI API key:"
echo "   OPENAI_API_KEY=sk-your-key-here"
echo ""
echo "2. Start the server:"
echo "   python wound_ai_system_integrated.py"
echo "   OR:"
echo "   uvicorn wound_ai_system_integrated:app --reload"
echo ""
echo "3. Access the API:"
echo "   • API Docs: http://localhost:8000/docs"
echo "   • Health Check: http://localhost:8000/health"
echo ""
echo "4. Login with admin credentials:"
echo "   Username: admin"
echo "   Password: changeme123"
echo ""
echo "5. Test the API:"
echo "   curl -X POST http://localhost:8000/token \\"
echo "     -F 'username=admin' \\"
echo "     -F 'password=changeme123'"
echo ""
echo "=================================="
echo ""
echo "📚 Documentation:"
echo "   • Integration Guide: INTEGRATION_GUIDE.md"
echo "   • Deployment Guide: DEPLOYMENT_GUIDE.md"
echo "   • Android Guide: ANDROID_INTEGRATION.md"
echo ""
echo "🆘 Troubleshooting:"
echo "   • If imports fail: pip install -r requirements.txt"
echo "   • If database errors: Check DATABASE_URL in .env"
echo "   • If auth fails: Verify JWT secrets are set"
echo ""
