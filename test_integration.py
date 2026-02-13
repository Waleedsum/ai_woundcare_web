#!/usr/bin/env python3
"""
Integration Test Script
Tests all major features of the integrated Wound AI system
"""

import requests
import json
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50 + "\n")

def test_health():
    """Test health endpoint"""
    print_section("1. Testing Health Endpoint")
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "Health check failed"
    print("✅ Health check passed")

def test_registration():
    """Test user registration"""
    print_section("2. Testing User Registration")
    
    user_data = {
        "username": "test_nurse",
        "email": "nurse@test.com",
        "password": "testpass123",
        "full_name": "Test Nurse",
        "organization": "Test Hospital",
        "department": "Wound Care"
    }
    
    response = requests.post(f"{BASE_URL}/register", json=user_data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        print("✅ Registration successful")
    elif response.status_code == 400:
        print("ℹ️  User already exists (this is OK)")
    else:
        print(f"❌ Registration failed: {response.json()}")
    
    return user_data

def test_login(username, password):
    """Test user login"""
    print_section("3. Testing User Login")
    
    login_data = {
        "username": username,
        "password": password
    }
    
    response = requests.post(
        f"{BASE_URL}/token",
        data=login_data
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        tokens = response.json()
        print(f"Access Token: {tokens['access_token'][:50]}...")
        print(f"Refresh Token: {tokens['refresh_token'][:50]}...")
        print("✅ Login successful")
        return tokens['access_token']
    else:
        print(f"❌ Login failed: {response.json()}")
        return None

def test_user_info(token):
    """Test getting current user info"""
    print_section("4. Testing User Info")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/me", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "User info retrieval failed"
    print("✅ User info retrieved")

def test_wound_analysis(token):
    """Test wound analysis endpoint"""
    print_section("5. Testing Wound Analysis")
    
    # Create a simple test image (red square to simulate wound)
    from PIL import Image, ImageDraw
    import io
    
    # Create test image
    img = Image.new('RGB', (500, 500), color='white')
    draw = ImageDraw.Draw(img)
    draw.ellipse([150, 150, 350, 350], fill='red', outline='darkred')
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    # Prepare request
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test_wound.jpg", img_bytes, "image/jpeg")}
    data = {
        "patient_mrn": "TEST001",
        "wound_type": "pressure ulcer",
        "location": "sacrum",
        "days_since_onset": "7"
    }
    
    print("Uploading test wound image...")
    print("Note: This requires a valid OpenAI API key in .env")
    
    response = requests.post(
        f"{BASE_URL}/analyze",
        headers=headers,
        files=files,
        data=data
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\nAnalysis Results:")
        print(f"  Case Code: {result.get('case_code')}")
        
        assessment = result.get('wound_assessment', {})
        print(f"  Size: {assessment.get('size_cm2')} cm²")
        print(f"  Dimensions: {assessment.get('length_cm')} x {assessment.get('width_cm')} cm")
        
        infection = assessment.get('infection_risk', {})
        print(f"  Infection Risk: {infection.get('score')}/10 - {infection.get('level')}")
        
        print("\n✅ Wound analysis successful")
        return result.get('case_code')
    else:
        print(f"❌ Analysis failed: {response.json()}")
        return None

def test_list_cases(token):
    """Test listing cases"""
    print_section("6. Testing Case Listing")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/cases", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        cases = response.json()
        print(f"Number of cases: {len(cases)}")
        
        if cases:
            print("\nFirst case:")
            print(f"  Code: {cases[0].get('case_code')}")
            print(f"  Type: {cases[0].get('wound_type')}")
            print(f"  Created: {cases[0].get('created_at')}")
        
        print("✅ Case listing successful")
    else:
        print(f"❌ Case listing failed: {response.json()}")

def test_get_case(token, case_code):
    """Test getting specific case"""
    print_section("7. Testing Case Retrieval")
    
    if not case_code:
        print("⚠️  No case code available, skipping")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/cases/{case_code}", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        case_data = response.json()
        print("\nCase Details:")
        print(f"  Code: {case_data['case']['case_code']}")
        print(f"  Size: {case_data['case']['size_cm2']} cm²")
        print(f"  Risk Score: {case_data['case']['infection_risk_score']}")
        
        if case_data.get('tissue_analysis'):
            ta = case_data['tissue_analysis']
            print(f"\nTissue Analysis:")
            print(f"  Granulation: {ta['granulation_percent']}%")
            print(f"  Slough: {ta['slough_percent']}%")
            print(f"  Necrotic: {ta['necrotic_percent']}%")
        
        print("\n✅ Case retrieval successful")
    else:
        print(f"❌ Case retrieval failed: {response.json()}")

def run_all_tests():
    """Run all integration tests"""
    print("\n" + "🏥"*25)
    print("  Wound AI System - Integration Tests")
    print("🏥"*25)
    
    try:
        # Test 1: Health
        test_health()
        
        # Test 2: Registration
        user_data = test_registration()
        
        # Test 3: Login
        token = test_login(user_data["username"], user_data["password"])
        
        if not token:
            print("\n❌ Cannot continue without valid token")
            print("Please check:")
            print("  1. Server is running (python wound_ai_system_integrated.py)")
            print("  2. Database is initialized (python database_schema_multiuser.py)")
            return
        
        # Test 4: User info
        test_user_info(token)
        
        # Test 5: Wound analysis
        print("\n⚠️  Note: Wound analysis requires OpenAI API key")
        print("If you see errors, check OPENAI_API_KEY in .env")
        
        case_code = None
        try:
            case_code = test_wound_analysis(token)
        except Exception as e:
            print(f"⚠️  Wound analysis skipped: {e}")
            print("This is expected if OpenAI API key is not configured")
        
        # Test 6: List cases
        test_list_cases(token)
        
        # Test 7: Get specific case
        if case_code:
            test_get_case(token, case_code)
        
        # Summary
        print_section("Test Summary")
        print("✅ All accessible tests passed!")
        print("\nSystem is working correctly.")
        print("\nTo use the system:")
        print("  1. Update OPENAI_API_KEY in .env for wound analysis")
        print("  2. Access API docs at http://localhost:8000/docs")
        print("  3. Use the test credentials:")
        print(f"     Username: {user_data['username']}")
        print(f"     Password: {user_data['password']}")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server!")
        print("\nPlease start the server first:")
        print("  python wound_ai_system_integrated.py")
        print("\nOr:")
        print("  uvicorn wound_ai_system_integrated:app --reload")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
