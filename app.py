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

# --- Visual Component: Header ---
st.markdown("""
<div class="app-header">
    <h1 class="app-title">Skill<span class="title-accent">Up</span></h1>
    <p class="app-subtitle">Precision Career Navigation</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# RENDERING ENGINE: TO-CLEAN-UI
# ============================================================
def render_clean_phase(phase_text, number):
    # Regex to clean out AI "markdown mess" and extract pillars
    try:
        title_match = re.search(r"Phase \d+: (.*)", phase_text)
        title = title_match.group(1) if title_match else f"Mastery Phase {number}"
        
        # Clean the text of excessive ** or *
        clean_text = phase_text.replace("**", "").replace("*", "")
        
        watch = re.search(r"Watch: (.*)", clean_text)
        study = re.search(r"Study: (.*)", clean_text)
        build = re.search(r"Build: (.*)", clean_text)
        
        st.markdown(f"""
        <div class="phase-container">
            <div class="phase-sidebar">
                <div class="phase-badge">{number}</div>
                <div class="phase-line"></div>
            </div>
            <div class="phase-content-card">
                <h3 class="phase-title">{title.strip()}</h3>
                <div class="resource-row">
                    <div class="resource-pill watch-pill">📺 Watch: {watch.group(1).strip() if watch else "Curated Playlist"}</div>
                    <div class="resource-pill study-pill">🎓 Study: {study.group(1).strip() if study else "Mastery Guide"}</div>
                </div>
                <div class="project-box">
                    <div class="project-label">🛠️ CAPSTONE PROJECT</div>
                    <p class="project-desc">{build.group(1).strip() if build else "Portfolio-worthy Application"}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown(f"<div class='phase-card'>{phase_text}</div>", unsafe_allow_html=True)

# ============================================================
# FLOW LOGIC
# ============================================================
if st.session_state.current_step == "onboarding":
    st.markdown("""
    <div class="hero-section">
        <h1>The Direct Path to Your Dream Role</h1>
        <p>No fluff. No information overload. Just a personalized blueprint for your next move.</p>
        <button class="hero-btn" onclick="document.getElementById('start-btn').click()">🚀 Take the First Step</button>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Start Now", key="start-btn"):
        st.session_state.current_step = "selection"; st.rerun()

elif st.session_state.current_step == "selection":
    st.markdown("<h2 style='text-align:center;'>📄 Building Your Profile</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.role = st.selectbox("Your Target Role", ["", "Data Analyst", "Operations Manager", "Full Stack Dev", "WFM Specialist", "Quality Analyst", "UI Designer", "Other"])
            st.session_state.goal = st.text_input("Immediate Goal", placeholder="e.g., Switch from Support to Analytics")
        with c2:
            f = st.file_uploader("Upload CV (PDF/JSON)")
            if f:
                with st.spinner("Analyzing..."):
                    if f.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                            t.write(f.read()); tp = t.name
                        st.session_state.resume_text = parse_resume(tp)
                        if os.path.exists(tp): os.remove(tp)
                    else: st.session_state.resume_text = json.dumps(json.load(f))
                    st.success("✅ Profile Verified")
                    
    if st.button("📦 Generate My Guide", use_container_width=True, type="primary"):
        if st.session_state.resume_text and st.session_state.role:
            with st.spinner("Curating Your Path..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                m = genai.GenerativeModel("gemini-2.0-flash-lite")
                p = (f"User Resume: {st.session_state.resume_text[:1500]}\nTarget: {st.session_state.role}\n"
                     "Task: Create a 6-phase learning roadmap. \n"
                     "Format strictly per phase: Phase X: [Name]\nWatch: [Resource Name/Link]\nStudy: [Course/Guide]\nBuild: [Project Description]\n"
                     "DO NOT use markdown bolding (**) in the content parts. Keep it plain text for parsing.")
                st.session_state.roadmap = m.generate_content(p).text
                st.session_state.current_step = "journey"; st.rerun()

elif st.session_state.current_step == "journey":
    t1, t2 = st.tabs(["🗺️ Your Roadmap", "🔬 Profile Gap"])
    with t1:
        if st.session_state.roadmap:
            # --- Progress Tracking (Dopamine Hits) ---
            parts = re.split(r"Phase \d+:", st.session_state.roadmap)
            total_phases = len(parts) - 1
            
            if "completed_phases" not in st.session_state:
                st.session_state.completed_phases = {}

            # Calculated Progress
            completed_count = sum(1 for v in st.session_state.completed_phases.values() if v)
            progress_pct = (completed_count / total_phases) if total_phases > 0 else 0
            
            st.markdown(f"### 📈 Your Mastery Progress: {int(progress_pct * 100)}%")
            st.progress(progress_pct)
            
            st.markdown("---")
            st.markdown("### Your Custom Career Path")
            
            show_size = total_phases if st.session_state.is_paid else 1
            for i, p_text in enumerate(parts[1:show_size+1]):
                # Render the UI card
                render_clean_phase(p_text, i+1)
                
                # Interactivty for dopamine hit
                col_btn, _ = st.columns([1, 2])
                with col_btn:
                    cb_key = f"phase_cb_{i+1}"
                    st.session_state.completed_phases[cb_key] = st.checkbox(f"✅ Mark Phase {i+1} as Mastered", key=cb_key)
            
            if not st.session_state.is_paid:
                st.markdown("""
                <div class="locked-box">
                    <h3>🔒 Complete Your 6-Month Journey</h3>
                    <p>Unlock all 6 phases, specific resource links, and your personalized Mastery PDF.</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Unlock Now - ₹299", use_container_width=True, type="primary"):
                    st.session_state.is_paid = True; st.balloons(); st.rerun()
            else:
                st.success("💎 Full Access Enabled")
                # PDF & Resources below...
                if st.button("📥 Download PDF Bible"):
                    st.info("Preparing Professional PDF...")

if st.button("🔄 Start New Search", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.rerun()
