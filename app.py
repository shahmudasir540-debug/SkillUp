import streamlit as st
import tempfile
import os
import json
import re
import time
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from resume_parser import parse_resume, parse_linkedin_json
from roadmap_generator import generate_roadmap
from goal_analyzer import analyze_goals
import google.generativeai as genai
import plotly.express as px
from datetime import timedelta
from smart_gap_analyzer import get_smart_gap_analysis, SmartGapAnalysisError
import hashlib
from dotenv import load_dotenv

load_dotenv()

# --- Database & ID Helper ---
ROADMAPS_DB_PATH = os.path.join(os.path.dirname(__file__), "roadmaps_db.json")

def load_roadmaps_db():
    if os.path.exists(ROADMAPS_DB_PATH):
        with open(ROADMAPS_DB_PATH, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_roadmaps_db(roadmaps):
    with open(ROADMAPS_DB_PATH, "w") as f:
        json.dump(roadmaps, f, indent=2)

def roadmap_id(resume, goal, role):
    base = (resume.strip() + goal.strip() + role.strip()).encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:16]

# --- Config & Session ---
st.set_page_config(page_title="SkillUp", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")

# Load CSS
with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

if "roadmaps_db" not in st.session_state:
    st.session_state.roadmaps_db = load_roadmaps_db()
if "roadmap" not in st.session_state:
    st.session_state.roadmap = ""
if "is_paid" not in st.session_state:
    st.session_state.is_paid = False
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "first_visit" not in st.session_state:
    st.session_state.first_visit = True

# --- Branding & Header ---
st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Skill<span class="title-accent">Up</span></h1>
        <p class="app-subtitle">The Complete Career Acceleration Platform</p>
    </div>
""", unsafe_allow_html=True)

# Onboarding (restored)
if st.session_state.first_visit:
    st.markdown("""
    <div class="stInfo section-card" style="margin-bottom: 2rem;">
        <h3 style="margin-top:0">🎉 Welcome to SkillUp!</h3>
        <ul style="margin-bottom:0">
            <li><b>1. ⚙️ Configuration:</b> Ensure your API key is set in the sidebar.</li>
            <li><b>2. 📄 Resume:</b> Upload your CV and define your career goals.</li>
            <li><b>3. ⚡ Unlock:</b> Get a free preview or upgrade to <b>Pro</b> for the full experience.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Got it!"):
        st.session_state.first_visit = False
        st.rerun()

# --- Sidebar (Recent Roadmaps - Restored & Styled) ---
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    if not st.session_state.gemini_api_key:
        api_key_input = st.text_input("Enter Gemini API Key", type="password")
        if st.button("Save Key"):
            st.session_state.gemini_api_key = api_key_input
            st.rerun()
    else:
        st.success("✅ Connected")
        if st.button("🔄 Change Key"):
            st.session_state.gemini_api_key = ""
            st.rerun()

    st.markdown("---")
    st.markdown("### 🗂️ Recent Journey")
    for r in sorted(st.session_state.roadmaps_db, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]:
        if st.button(f"🚀 {r['role']}\n({r['goal'][:20]}...)", key=f"sidebar_{r['id']}", use_container_width=True):
            st.session_state.roadmap = r["roadmap"]
            st.session_state.goal = r["goal"]
            st.session_state.role = r["role"]
            st.session_state.resume_text = r["resume"]
            st.rerun()

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["📄 Resume & Analysis", "🗺️ Your Roadmap", "💎 SkillUp Pro"])

# Resume Tab
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("### 🎯 Career Goals")
        st.session_state.goal = st.text_input("Target Goal", placeholder="e.g., Senior Full Stack Dev", value=st.session_state.get('goal', ''))
        
        roles = ["Select a tech role", "AI Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer", "Product Manager", "Data Analyst", "Cybersecurity Expert", "DevOps Engineer", "UI/UX Designer", "Other"]
        st.session_state.role = st.selectbox("Current Role focus", roles, index=roles.index(st.session_state.get('role', 'Select a tech role')) if st.session_state.get('role') in roles else 0)
        
    with col2:
        st.markdown("### 📄 Resume Upload")
        uploaded_file = st.file_uploader("Upload PDF or LinkedIn JSON", type=["pdf", "json"])
        if uploaded_file and not st.session_state.is_processing:
            with st.spinner("Processing..."):
                if uploaded_file.type == "application/pdf":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                        t.write(uploaded_file.read())
                        st.session_state.resume_text = parse_resume(t.name)
                        os.remove(t.name)
                elif uploaded_file.type == "application/json":
                    st.session_state.resume_text = parse_linkedin_json(json.load(uploaded_file))
                st.success("✅ Resume Parsed!")

    if st.button("⚡ Generate SkillUp Roadmap", use_container_width=True):
        if st.session_state.get('resume_text'):
            with st.spinner("Generating..."):
                try:
                    genai.configure(api_key=st.session_state.gemini_api_key)
                    prompt = f"Resume:\n{st.session_state.resume_text}\nRole: {st.session_state.role}\nGoal: {st.session_state.goal}\nGenerate a 6-month learning roadmap with phases, modules, and project tasks."
                    st.session_state.roadmap = generate_roadmap(prompt)
                    # Save to DB
                    rid = roadmap_id(st.session_state.resume_text, st.session_state.goal, st.session_state.role)
                    if not any(r['id'] == rid for r in st.session_state.roadmaps_db):
                        st.session_state.roadmaps_db.insert(0, {"id": rid, "role": st.session_state.role, "goal": st.session_state.goal, "roadmap": st.session_state.roadmap, "resume": st.session_state.resume_text, "timestamp": datetime.now().isoformat()})
                        save_roadmaps_db(st.session_state.roadmaps_db)
                    st.success("✅ Roadmap Ready! Go to the 'Roadmap' tab.")
                except Exception as e:
                    st.error(f"Error: {e}")

    # Job Simulator (Restored)
    st.markdown("---")
    with st.expander("🎯 Job Fit Simulator", expanded=False):
        jd_text = st.text_area("Paste a Job Description to check fit", height=150)
        if st.button("Analyze Match"):
            if st.session_state.get('resume_text') and jd_text:
                with st.spinner("Simulating..."):
                    model = genai.GenerativeModel("gemini-2.0-flash-lite")
                    res = model.generate_content(f"Resume: {st.session_state.resume_text}\nJD: {jd_text}\nAnalyze match score and list gaps.")
                    st.markdown(res.text)

# Roadmap Tab
with tab2:
    if st.session_state.roadmap:
        # Full content or Preview logic
        if not st.session_state.is_paid:
            st.info("💡 You are viewing the **Free Preview**. Upgrade to Pro to see the full 6-month roadmap, timeline, and export.")
            st.markdown("\n".join(st.session_state.roadmap.splitlines()[:20])) # Show first 20 lines
            st.markdown("""<div class="locked-content" style="padding: 2rem; text-align: center; border: 1px solid var(--border-accent); border-radius: 20px;">
                <h3 style="margin-top:0">🔒 Rest of Journey Locked</h3>
                <p>Unlock for ₹299 to get the full timeline and export options.</p>
                <div class="stButton"><button>✨ Unlock Now</button></div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(st.session_state.roadmap)
            
            # --- Q&A (Restored) ---
            st.markdown("---")
            st.subheader("❓ Ask About this Roadmap")
            q = st.text_input("How specifically can I improve X?")
            if st.button("Ask AI"):
                model = genai.GenerativeModel("gemini-2.0-flash-lite")
                ans = model.generate_content(f"Based on roadmap: {st.session_state.roadmap}\nQuestion: {q}")
                st.write(ans.text)

    else:
        st.markdown("""<div class="empty-state">
            <p>Your journey hasn't started yet. Upload a resume in the first tab!</p>
        </div>""", unsafe_allow_html=True)

# Pricing Tab
with tab3:
    st.markdown("### 💎 Choose Your Plan")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""<div class="pricing-card">
            <div class="pricing-badge">Free</div>
            <h2 class="pricing-price">₹0</h2>
            <ul>
                <li>✅ Resume Parsing</li>
                <li>✅ Goal Analysis</li>
                <li>✅ Roadmap Preview (1 month)</li>
            </ul>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="pricing-card pricing-card-pro">
            <div class="pricing-badge-pro">Pro</div>
            <h2 class="pricing-price pricing-price-pro">₹299</h2>
            <ul>
                <li>✅ Full 6-Month Roadmap</li>
                <li>✅ Smart AI Gap Analysis</li>
                <li>✅ Job Fit Simulator</li>
                <li>✅ PDF & JSON Export</li>
                <li>✅ Priority Roadmap Q&A</li>
            </ul>
        </div>""", unsafe_allow_html=True)
    
    # Payment UI
    st.markdown("---")
    if not st.session_state.is_paid:
        st.subheader("💳 Secure Payment")
        pay_method = st.radio("Method", ["UPI", "Credit/Debit Card"], horizontal=True)
        with st.form("pay_form"):
            if pay_method == "UPI":
                upi = st.text_input("UPI ID", placeholder="user@paytm")
            else:
                st.text_input("Card Number", placeholder="XXXX XXXX XXXX XXXX")
                c1, c2 = st.columns(2)
                c1.text_input("Name")
                c2.text_input("CVV", type="password")
            
            if st.form_submit_button("💰 Pay ₹299 & Unlock Pro"):
                st.session_state.is_paid = True
                st.balloons()
                st.success("✨ Welcome to SkillUp Pro!")
                st.rerun()
    else:
        st.success("💎 You're a SkillUp Pro member!")

# Footer (Minimal)
st.markdown("""
<div class="footer">
    <p>© 2025 SkillUp. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
