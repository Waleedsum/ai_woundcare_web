import streamlit as st
import requests
from PIL import Image
import io
import json

# Page config
st.set_page_config(
    page_title="AI Wound Care System",
    page_icon="🏥",
    layout="wide"
)

# API URL
API_URL = "https://ai-woundcare-web.onrender.com"

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
    }
</style>
""", unsafe_allow_html=True)

# Session state for auth
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user_info' not in st.session_state:
    st.session_state.user_info = None

# Header
st.markdown('<h1 class="main-header">🏥 AI Wound Care System</h1>', unsafe_allow_html=True)
st.markdown("### AI-Powered Wound Assessment & Analysis")

# Sidebar for authentication
with st.sidebar:
    st.header("🔐 Authentication")

    if st.session_state.token is None:
        # Login/Register tabs
        auth_tab = st.radio("Choose action:", ["Login", "Register"])

        if auth_tab == "Register":
            st.subheader("Create New Account")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_name = st.text_input("Full Name", key="reg_name")
            reg_role = st.selectbox("Role", ["nurse", "doctor", "admin"])
            reg_department = st.text_input("Department (optional)", key="reg_dept")

            if st.button("Register", type="primary"):
                try:
                    response = requests.post(
                        f"{API_URL}/register",
                        json={
                            "email": reg_email,
                            "password": reg_password,
                            "full_name": reg_name,
                            "role": reg_role,
                            "department": reg_department if reg_department else None
                        }
                    )
                    if response.status_code == 200:
                        st.success("✅ Registration successful! Please login.")
                    else:
                        st.error(f"❌ Registration failed: {response.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

        else:  # Login
            st.subheader("Login")
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login", type="primary"):
                try:
                    response = requests.post(
                        f"{API_URL}/token",
                        data={
                            "username": login_email,
                            "password": login_password
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.token = data['access_token']

                        # Get user info
                        headers = {"Authorization": f"Bearer {st.session_state.token}"}
                        user_response = requests.get(f"{API_URL}/me", headers=headers)
                        if user_response.status_code == 200:
                            st.session_state.user_info = user_response.json()
                            st.success("✅ Login successful!")
                            st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    else:
        # Logged in
        st.success(f"✅ Logged in as:")
        st.write(f"**{st.session_state.user_info['full_name']}**")
        st.write(f"Role: {st.session_state.user_info['role']}")
        if st.session_state.user_info.get('department'):
            st.write(f"Dept: {st.session_state.user_info['department']}")

        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.user_info = None
            st.rerun()

# Main content
if st.session_state.token is None:
    st.info("👈 Please login or register to use the wound analysis system")

    # Show demo info
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📸 Image Analysis")
        st.write("Upload wound images for AI-powered assessment")

    with col2:
        st.markdown("### 📊 Detailed Reports")
        st.write("Get comprehensive wound analysis with metrics")

    with col3:
        st.markdown("### 📈 Track Progress")
        st.write("Monitor healing progress over time")

else:
    # Wound Analysis Interface
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📸 New Analysis", "📋 My Cases", "ℹ️ System Info"])

    with tab1:
        st.header("Upload Wound Image for Analysis")

        col1, col2 = st.columns([1, 1])

        with col1:
            uploaded_file = st.file_uploader(
                "Choose a wound image...",
                type=['jpg', 'jpeg', 'png'],
                help="Upload a clear image of the wound"
            )

            if uploaded_file is not None:
                # Display image
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Image", use_container_width=True)

                # Analyze button
                if st.button("🔍 Analyze Wound", type="primary"):
                    with st.spinner("Analyzing wound..."):
                        try:
                            # Prepare file for upload
                            files = {
                                'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                            }
                            headers = {"Authorization": f"Bearer {st.session_state.token}"}

                            # Call API
                            response = requests.post(
                                f"{API_URL}/analyze",
                                files=files,
                                headers=headers
                            )

                            if response.status_code == 200:
                                result = response.json()

                                # Store in session state
                                st.session_state.analysis_result = result
                                st.success("✅ Analysis complete!")
                                st.rerun()
                            else:
                                st.error(f"❌ Analysis failed: {response.json().get('detail', 'Unknown error')}")

                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

        with col2:
            # Display results if available
            if 'analysis_result' in st.session_state:
                result = st.session_state.analysis_result

                st.subheader("📊 Analysis Results")

                # Main metrics
                metrics_col1, metrics_col2 = st.columns(2)

                with metrics_col1:
                    st.metric(
                        "Case Code",
                        result.get('case_code', 'N/A')
                    )
                    st.metric(
                        "Wound Type",
                        result.get('wound_type', 'N/A')
                    )

                with metrics_col2:
                    st.metric(
                        "Severity",
                        result.get('severity', 'N/A')
                    )
                    st.metric(
                        "Confidence",
                        f"{result.get('confidence_score', 0) * 100:.1f}%"
                    )

                # Tissue analysis
                if 'tissue_analysis' in result:
                    st.markdown("#### 🔬 Tissue Composition")
                    tissue = result['tissue_analysis']

                    t_col1, t_col2, t_col3 = st.columns(3)
                    with t_col1:
                        st.metric("Healthy", f"{tissue.get('healthy_percentage', 0):.1f}%")
                    with t_col2:
                        st.metric("Granulation", f"{tissue.get('granulation_percentage', 0):.1f}%")
                    with t_col3:
                        st.metric("Necrotic", f"{tissue.get('necrotic_percentage', 0):.1f}%")

                # Infection risk
                if 'infection_risk' in result:
                    st.markdown("#### ⚠️ Infection Risk Assessment")
                    risk = result['infection_risk']

                    if risk.get('risk_level') == 'high':
                        st.error(f"**High Risk**: {risk.get('score', 0):.1f}/10")
                    elif risk.get('risk_level') == 'moderate':
                        st.warning(f"**Moderate Risk**: {risk.get('score', 0):.1f}/10")
                    else:
                        st.success(f"**Low Risk**: {risk.get('score', 0):.1f}/10")

                    if 'factors' in risk:
                        st.write("**Risk Factors:**")
                        for factor in risk['factors']:
                            st.write(f"- {factor}")

                # Measurements
                if 'measurements' in result:
                    st.markdown("#### 📏 Wound Measurements")
                    meas = result['measurements']

                    m_col1, m_col2, m_col3 = st.columns(3)
                    with m_col1:
                        st.metric("Length", f"{meas.get('length_cm', 0):.1f} cm")
                    with m_col2:
                        st.metric("Width", f"{meas.get('width_cm', 0):.1f} cm")
                    with m_col3:
                        st.metric("Area", f"{meas.get('area_cm2', 0):.1f} cm²")

                # Recommendations
                if 'recommendations' in result:
                    st.markdown("#### 💡 Treatment Recommendations")
                    for i, rec in enumerate(result['recommendations'], 1):
                        st.info(f"{i}. {rec}")

                # Raw JSON (collapsible)
                with st.expander("🔍 View Raw Analysis Data"):
                    st.json(result)

    with tab2:
        st.header("📋 My Cases")
        st.info("Case management feature - coming soon!")

        # You can add case listing here
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = requests.get(f"{API_URL}/cases", headers=headers)

            if response.status_code == 200:
                cases = response.json()
                if cases:
                    for case in cases:
                        with st.expander(f"Case {case.get('case_code', 'N/A')} - {case.get('created_at', '')}"):
                            st.json(case)
                else:
                    st.write("No cases found. Analyze your first wound to create a case!")
        except Exception as e:
            st.error(f"Error loading cases: {str(e)}")

    with tab3:
        st.header("ℹ️ System Information")

        # API Health Check
        try:
            response = requests.get(f"{API_URL}/health")
            if response.status_code == 200:
                health = response.json()
                st.success("✅ API is healthy and running")
                st.json(health)
        except Exception as e:
            st.error(f"❌ API connection error: {str(e)}")

        st.markdown("---")
        st.markdown("""
        ### Features
        - 🔐 Multi-user authentication
        - 📸 AI-powered wound image analysis
        - 🔬 Tissue composition analysis
        - ⚠️ Infection risk assessment
        - 📏 Automated wound measurements
        - 💡 Treatment recommendations
        - 📊 Case management
        - 📈 Progress tracking

        ### About
        This system uses advanced AI and computer vision to analyze wound images
        and provide healthcare professionals with detailed assessments and
        treatment recommendations.

        **Version**: 2.0.0  
        **API**: FastAPI + PyTorch  
        **UI**: Streamlit
        """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "AI Wound Care System v2.0 | Built with ❤️ for Healthcare Professionals"
    "</div>",
    unsafe_allow_html=True
)