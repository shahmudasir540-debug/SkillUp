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
from reportlab.lib.colors import HexColor, black, white, gray
from resume_parser import parse_resume, parse_linkedin_json
from roadmap_generator import generate_roadmap
import google.generativeai as genai
import plotly.express as px
import pandas as pd
from smart_gap_analyzer import get_smart_gap_analysis
import hashlib
from dotenv import load_dotenv

load_dotenv()

# --- Helpers ---
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

# --- Page Config ---
st.set_page_config(page_title="SkillUp", page_icon="🚀", layout="wide")

# Load CSS
with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# State
if "roadmaps_db" not in st.session_state: st.session_state.roadmaps_db = load_roadmaps_db()
if "roadmap" not in st.session_state: st.session_state.roadmap = ""
if "resume_text" not in st.session_state: st.session_state.resume_text = ""
if "goal" not in st.session_state: st.session_state.goal = ""
if "role" not in st.session_state: st.session_state.role = ""
if "is_paid" not in st.session_state: st.session_state.is_paid = False
if "current_step" not in st.session_state: st.session_state.current_step = "onboarding"

# --- Visual Header ---
st.markdown("""<div class="app-header"><h1 class="app-title">Skill<span class="title-accent">Up</span></h1><p class="app-subtitle">The Final Career Navigation System</p></div>""", unsafe_allow_html=True)

# --- Role Library (Massive Expansion) ---
ROLE_LIBRARY = [
    "--- BPO & BPS ---",
    "Customer Support Associate (Domestic)", "Customer Support Associate (International)", "Voice Process Executive", "Non-Voice / Backoffice Specialist",
    "Customer Success Manager", "Technical Support Engineer", "Operations Team Leader", "Operations Manager", "Senior Operations Manager",
    "Quality Analyst (QA)", "Quality Manager", "Trainer (Process/Soft Skills)", "Training Manager",
    "Workforce Management (WFM) Analyst", "WFM Manager", "MIS Executive", "MIS Manager", "RTA (Real Time Analyst)",
    "Director of Operations", "VP Operations",
    "--- IT, DATA & DEV ---",
    "Data Analyst", "Senior Data Analyst", "Data Scientist", "Data Engineer", "AI/ML Engineer", "Business Intelligence (BI) Developer",
    "Backend Developer", "Frontend Developer", "Full Stack Developer", "Mobile App Developer", "DevOps Engineer", "Cloud Solutions Architect",
    "Cybersecurity Specialist", "IT Support Specialist", "System Administrator", "Database Administrator",
    "--- SALES & MARKETING ---",
    "Business Development Associate", "Business Development Manager", "Sales Executive", "Corporate Sales Head",
    "Performance Marketing Specialist", "Digital Marketing Manager", "SEO/SEM Specialist", "Content Strategist", "Social Media Manager",
    "Product Marketing Manager", "Ad Operations Specialist", "Campaign Manager",
    "--- EDTECH & DESIGN ---",
    "Instructional Designer", "Curriculum Developer", "Academic Consultant", "Edtech Product Manager", "Learning Experience Designer",
    "UI/UX Designer", "Product Designer", "Graphic Designer", "Video Editor",
    "--- MGMT & OTHER ---",
    "Project Manager", "Program Manager", "Product Manager", "HR Generalist", "Recruitment Specialist", "Financial Analyst", "Other"
]

# --- Rendering ---
def render_clean_phase(phase_text, number):
    try:
        title_match = re.search(r"Phase \d+: (.*)", phase_text)
        title = title_match.group(1) if title_match else f"Mastery Phase {number}"
        clean_text = phase_text.replace("**", "").replace("*", "")
        watch = re.search(r"Watch: (.*)", clean_text)
        study = re.search(r"Study: (.*)", clean_text)
        build = re.search(r"Build: (.*)", clean_text)
        st.markdown(f"""<div class="phase-container"><div class="phase-sidebar"><div class="phase-badge">{number}</div><div class="phase-line"></div></div><div class="phase-content-card"><h3 class="phase-title">{title.strip()}</h3><div class="resource-row"><div class="resource-pill watch-pill">📺 Watch: {watch.group(1).strip() if watch else "Curated Playlist"}</div><div class="resource-pill study-pill">🎓 Study: {study.group(1).strip() if study else "Mastery Guide"}</div></div><div class="project-box"><div class="project-label">🛠️ CAPSTONE PROJECT</div><p class="project-desc">{build.group(1).strip() if build else "Portfolio Application"}</p></div></div></div>""", unsafe_allow_html=True)
    except: st.markdown(f"<div class='phase-card'>{phase_text}</div>", unsafe_allow_html=True)

if st.session_state.current_step == "onboarding":
    st.markdown("""<div class="hero-section"><h1>Your Personalized 6-Month Escape Plan</h1><p>SkillUp builds an expert-curated upskilling roadmap to get you ready for your next promotion or career switch. Stop searching, start mastering.</p></div>""", unsafe_allow_html=True)
    col_c1, col_c2, col_c3 = st.columns([1,2,1])
    with col_c2:
        if st.button("🚀 Begin My Transformation", use_container_width=True, type="primary"):
            st.session_state.current_step = "selection"; st.rerun()

elif st.session_state.current_step == "selection":
    st.markdown("<h2 style='text-align:center;'>📄 Set Your Destination</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.role = st.selectbox("Search & Select Your Dream Role", options=[""] + ROLE_LIBRARY)
            if st.session_state.role == "Other": st.session_state.role = st.text_input("Enter Custom Role")
            st.session_state.goal = st.text_input("What is your Immediate Goal?", placeholder="e.g. Move from Domestic to International BPO")
        with c2:
            st.caption("Upload your current resume/profile detail")
            f = st.file_uploader("Upload Profile (PDF/JSON)")
            if f:
                with st.spinner("Analyzing..."):
                    if f.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                            t.write(f.read()); tp = t.name
                        st.session_state.resume_text = parse_resume(tp)
                        if os.path.exists(tp): os.remove(tp)
                    else: st.session_state.resume_text = json.dumps(json.load(f))
                    st.success("✅ Profile Verified")
                    
    if st.button("🗺️ Create My Mastery Roadmap", use_container_width=True, type="primary"):
        if st.session_state.resume_text and st.session_state.role:
            with st.spinner("Curating Your Path (searching for available AI engine)..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                
                # High-Velocity Fallback System
                models_to_try = [
                    "gemini-1.5-flash", 
                    "gemini-1.5-flash-8b", 
                    "gemini-2.0-flash-exp", 
                    "gemini-1.0-pro",
                    "gemini-1.5-pro"
                ]
                success = False
                for model_name in models_to_try:
                    try:
                        m = genai.GenerativeModel(model_name)
                        p = (f"User Resume: {st.session_state.resume_text[:1500]}\nTarget: {st.session_state.role}\n"
                             "Task: Create a 6-phase learning roadmap. \n"
                             "Format strictly per phase: Phase X: [Name]\nWatch: [Resource Name/Link]\nStudy: [Course/Guide]\nBuild: [Project Description]\n"
                             "DO NOT use markdown bolding (**) in the content parts. Keep it plain text for parsing.")
                        st.session_state.roadmap = m.generate_content(p).text
                        success = True
                        break
                    except Exception as e:
                        continue
                
                if not success:
                    st.error("All AI models are currently busy or reached their quota. Please try again in 1 minute.")
                else:
                    st.session_state.current_step = "journey"; st.rerun()

elif st.session_state.current_step == "journey":
    t1, t2 = st.tabs(["🗺️ Your Roadmap", "🔬 Deep Analysis"])
    with t1:
        if st.session_state.roadmap:
            parts = re.split(r"Phase \d+:", st.session_state.roadmap); total = len(parts)-1
            if "completed_phases" not in st.session_state: st.session_state.completed_phases = {}
            done = sum(1 for v in st.session_state.completed_phases.values() if v)
            prog = (done / total) if total > 0 else 0
            st.markdown(f"### 📈 Your Mastery: {int(prog * 100)}%"); st.progress(prog); st.markdown("---")
            show = total if st.session_state.is_paid else 1
            for i, p_text in enumerate(parts[1:show+1]):
                render_clean_phase(p_text, i+1)
                cb_key = f"pc_{i+1}"
                st.session_state.completed_phases[cb_key] = st.checkbox(f"✅ Mark Phase {i+1} as Done", key=cb_key)
            if not st.session_state.is_paid:
                st.markdown("<div class='locked-box'><h3>🔒 Access the Full 6-Month Plan</h3><p>Unlock all phases and the complete Resource Bible for ₹299.</p></div>", unsafe_allow_html=True)
                if st.button("💰 Upgrade to Pro", use_container_width=True, type="primary"):
                    st.session_state.is_paid = True; st.balloons(); st.rerun()
            else:
                st.success("💎 Pro Membership Active")
                if st.button("📥 Download My PDF Bible", use_container_width=True): st.info("Generating...")

if st.button("🔄 Reset & Start New", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.session_state.completed_phases = {}; st.rerun()
