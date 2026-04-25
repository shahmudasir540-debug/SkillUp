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
st.markdown("""<div class="app-header"><h1 class="app-title">Skill<span class="title-accent">Up</span></h1><p class="app-subtitle">The AI-Augmented Career Navigator</p></div>""", unsafe_allow_html=True)

# ============================================================
# RENDERING ENGINE: PREMIUM MASTERY CARDS
# ============================================================
def render_mastery_phase(phase_text, number):
    try:
        # Improved Extraction Logic for High Value
        title = re.search(r"Phase \d+: (.*)", phase_text).group(1).strip()
        
        # Helper to extract and clean content
        def get_item(pattern, text):
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1).strip() if match else "Access in Pro Profile"

        watch = get_item(r"Watch: (.*)", phase_text)
        study = get_item(r"Study: (.*)", phase_text)
        ai_tool = get_item(r"AI Advantage: (.*)", phase_text)
        build = get_item(r"Build: (.*)", phase_text)

        st.markdown(f"""
        <div class="phase-container">
            <div class="phase-sidebar">
                <div class="phase-badge">{number}</div>
                <div class="phase-line"></div>
            </div>
            <div class="phase-content-card">
                <h3 class="phase-title">{title}</h3>
                
                <div class="resource-grid">
                    <div class="mastery-item">
                        <span class="m-icon">📺</span>
                        <div class="m-info">
                            <div class="m-label">VIDEO PATHWAY</div>
                            <div class="m-link">{watch}</div>
                        </div>
                    </div>
                    <div class="mastery-item">
                        <span class="m-icon">🎓</span>
                        <div class="m-info">
                            <div class="m-label">PROFESSIONAL STUDY</div>
                            <div class="m-link">{study}</div>
                        </div>
                    </div>
                </div>

                <div class="ai-burst-box">
                    <div class="ai-icon">🤖</div>
                    <div class="ai-content">
                        <div class="ai-label">AI UPSKILLING POWER-UP</div>
                        <p class="ai-desc">{ai_tool}</p>
                    </div>
                </div>

                <div class="build-track">
                    <div class="build-label">🛠️ PORTFOLIO CAPSTONE</div>
                    <p class="build-text">{build}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"<div class='phase-card'>{phase_text}</div>", unsafe_allow_html=True)

# ============================================================
# CORE APP FLOW
# ============================================================
if st.session_state.current_step == "onboarding":
    st.markdown("""<div class="hero-section"><h1>The Ultimate AI-Powered Escape Plan</h1><p>SkillUp doesn't just roadmap your skills; it integrates the <b>latest AI tools</b> into your workflow so you stay ahead of the curve. Get an expert-curated curriculum worth ₹2999+ for just ₹299.</p></div>""", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if st.button("🚀 Begin My AI-Powered Transformation", use_container_width=True, type="primary"):
            st.session_state.current_step = "selection"; st.rerun()

elif st.session_state.current_step == "selection":
    st.markdown("<h2 style='text-align:center;'>📄 Profile Intelligence Phase</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.role = st.selectbox("Define Your Target Path", ["", "Data Analyst", "Project Manager", "Operations Leader", "BPO Manager", "WFM Strategist", "Quality Lead", "Other"])
            st.session_state.goal = st.text_input("Career Objective", placeholder="e.g., Transitioning to AI-assisted Project Management")
        with col2:
            st.caption("Upload CV to detect your baseline skills.")
            up_file = st.file_uploader("Upload Profile (PDF/JSON)")
            if up_file:
                with st.spinner("Decoding Skills..."):
                    if up_file.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                            t.write(up_file.read()); temp_p = t.name
                        st.session_state.resume_text = parse_resume(temp_p)
                        if os.path.exists(temp_p): os.remove(temp_p)
                    else: st.session_state.resume_text = json.dumps(json.load(up_file))
                    st.success("✅ Profile Decoded")

    if st.button("🗺️ Architect My Mastery Roadmap", use_container_width=True, type="primary"):
        if st.session_state.resume_text and st.session_state.role:
            with st.spinner("Curating Your Path (AI-Augmented)..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                
                # Model Fallback System
                models_to_try = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-exp", "gemini-1.0-pro"]
                success = False
                for m_name in models_to_try:
                    try:
                        m = genai.GenerativeModel(m_name)
                        p = (f"User Resume: {st.session_state.resume_text[:1500]}\nTarget: {st.session_state.role}\n"
                             "Task: Create a highly valuable 6-phase learning roadmap. \n"
                             "FOR EACH PHASE, PROVIDE:\n"
                             "Phase X: [Name]\n"
                             "Watch: [ONE SPECIFIC CLICKABLE LINK TO YOUTUBE PLAYLIST]\n"
                             "Study: [ONE CLICKABLE LINK TO OFFICIAL DOC OR COURSERA COURSE]\n"
                             "AI Advantage: [SPECIFIC AI TOOLS AND WORKFLOWS THE USER MUST LEARN FOR THIS ROLE]\n"
                             "Build: [STEP-BY-STEP PROJECT BLUEPRINT]\n\n"
                             "MANDATORY: NO MARKDOWN BOLDING (**) IN CONTENT. PROVIDE REAL LINKS.")
                        st.session_state.roadmap = m.generate_content(p).text
                        success = True; break
                    except: continue
                
                if not success:
                    st.info("💡 Entering High-Value Demo Mode (API Quota Hit)")
                    st.session_state.roadmap = """
Phase 1: AI-Augmented Foundations
Watch: https://www.youtube.com/results?search_query=ai+fundamentals+for+work
Study: Coursera - Generative AI for Everyone
AI Advantage: Master ChatGPT for drafting and Claude for data summarization.
Build: Automate a weekly reporting task using AI and Python.

Phase 2: Technical Mastery & AI Integration
Watch: https://www.youtube.com/results?search_query=excel+plus+ai+tutorial
Study: Microsoft Learn - AI Builder
AI Advantage: Learn to use Github Copilot and AI-driven data cleaners.
Build: Create a predictive seat-occupancy model for BPO operations.
"""
                st.session_state.current_step = "journey"; st.rerun()

elif st.session_state.current_step == "journey":
    tab_r, tab_a = st.tabs(["🗺️ Mastery Journey", "🔬 Skills Matrix"])
    with tab_r:
        if st.session_state.roadmap:
            parts = re.split(r"Phase \d+:", st.session_state.roadmap); total = len(parts)-1
            if "completed_phases" not in st.session_state: st.session_state.completed_phases = {}
            done = sum(1 for v in st.session_state.completed_phases.values() if v)
            prog = (done / total) if total > 0 else 0
            st.markdown(f"### 📈 Your Career Mastery: {int(prog * 100)}%"); st.progress(prog); st.markdown("---")
            
            show = total if st.session_state.is_paid else 1
            for i, p_text in enumerate(parts[1:show+1]):
                render_mastery_phase(p_text, i+1)
                st.session_state.completed_phases[f"pc_{i+1}"] = st.checkbox(f"✅ Mark Phase {i+1} as Mastered", key=f"pc_{i+1}")
            
            if not st.session_state.is_paid:
                st.markdown("<div class='locked-box'><h3>🔒 Unlock Your AI-Augmented Future</h3><p>Unlock the remaining phases, AI toolkits, and the full Resource Bible.</p></div>", unsafe_allow_html=True)
                if st.button("Unlock Pro Mastery (₹299)", use_container_width=True, type="primary"):
                    st.session_state.is_paid = True; st.balloons(); st.rerun()
            else:
                st.button("📥 Download My Professional Mastery Bible")

if st.button("🔄 Start New Path", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.rerun()
