import streamlit as st
import tempfile
import os
import json
import re
import time
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, gray
from resume_parser import parse_resume, parse_linkedin_json
from roadmap_generator import generate_roadmap
from goal_analyzer import analyze_goals
import google.generativeai as genai
import plotly.express as px
import pandas as pd
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

# --- Page Configuration ---
st.set_page_config(page_title="SkillUp", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")

# Load CSS
with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Session State Initialization
if "roadmaps_db" not in st.session_state: st.session_state.roadmaps_db = load_roadmaps_db()
if "roadmap" not in st.session_state: st.session_state.roadmap = ""
if "resume_text" not in st.session_state: st.session_state.resume_text = ""
if "goal" not in st.session_state: st.session_state.goal = ""
if "role" not in st.session_state: st.session_state.role = ""
if "is_paid" not in st.session_state: st.session_state.is_paid = False
if "current_step" not in st.session_state: st.session_state.current_step = "onboarding"

# --- Header ---
st.markdown("""
<div class="app-header">
    <h1 class="app-title">Skill<span class="title-accent">Up</span></h1>
    <p class="app-subtitle">Ultimate Career Navigation & Mastery Platform</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### 🗂️ Career Archives")
    for r in st.session_state.roadmaps_db[:5]:
        if st.button(f"📌 {r['role'][:20]}...", key=f"sb_{r['id']}", use_container_width=True):
            st.session_state.roadmap = r["roadmap"]; st.session_state.goal = r["goal"]
            st.session_state.role = r["role"]; st.session_state.resume_text = r["resume"]
            st.session_state.current_step = "journey"; st.rerun()

# ============================================================
# STEP 1: HERO HOME
# ============================================================
if st.session_state.current_step == "onboarding":
    st.markdown("""
    <div class="hero-section">
        <h1>Transform Your Career with Precision</h1>
        <p style='font-size: 1.4rem;'>SkillUp analyzes your profile and builds a <b>High-Impact 6-Month Roadmap</b> 
        designed for your next promotion or role. No noise. Just the best curated resources in exact sequence.</p>
        <div style='margin-top: 2.5rem; display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;'>
            <div class="feature-tag">🎯 Precision Gap Analysis</div>
            <div class="feature-tag">📺 Direct Resource Links</div>
            <div class="feature-tag">🛠️ Portfolio Blueprints</div>
            <div class="feature-tag">📄 Exportable Mastery PDF</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([1,2,1])
    with col_c2:
        if st.button("🚀 Begin My Journey", use_container_width=True, type="primary"):
            st.session_state.current_step = "selection"; st.rerun()

# ============================================================
# STEP 2: PROFILE DISCOVERY
# ============================================================
elif st.session_state.current_step == "selection":
    st.markdown("<h2 class='step-title'>📄 Build Your Profile</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            suggested_roles = [
                "Data Analyst", "Project Manager", "Operations Manager", "Full Stack Developer", "AI Engineer",
                "Customer Support Executive", "Soft Skills Trainer", "Quality Analyst (QA)", "Workforce Management (WFM)",
                "MIS Manager", "Marketing Manager", "Director of Operations", "VP Operations"
            ]
            st.session_state.role = st.selectbox("Your Target Role", options=[""] + suggested_roles + ["Other"])
            if st.session_state.role == "Other": st.session_state.role = st.text_input("Enter Role Name")
            st.session_state.goal = st.text_input("Immediate Goal", placeholder="e.g., Get promoted to Manager")

        with col2:
            up_file = st.file_uploader("Upload Profile (PDF/JSON)", type=["pdf", "json"])
            if up_file:
                with st.spinner("Analyzing Experience..."):
                    if up_file.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                            t.write(up_file.read()); temp_p = t.name
                        st.session_state.resume_text = parse_resume(temp_p)
                        if os.path.exists(temp_p): os.remove(temp_p)
                    else: st.session_state.resume_text = parse_linkedin_json(json.load(up_file))
                    st.success("✅ Profile Verified")

    if st.button("🗺️ Generate My Roadmap", use_container_width=True, type="primary"):
        if not st.session_state.resume_text or not st.session_state.role: st.error("Missing Data.")
        else:
            with st.spinner("Generating High-Speed Roadmap..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                # Switching to 2.0-flash-lite for MAX SPEED
                m = genai.GenerativeModel("gemini-2.0-flash-lite")
                prompt = (f"Act as a Career Architect. Resume: {st.session_state.resume_text[:2000]}\n"
                          f"Target: {st.session_state.role}\n"
                          "Generate a 6-month learning roadmap. Be concise but high-value.\n"
                          "Format: ## Phase X (Month Y). Include:\n"
                          "- **Watch**: Specific YouTube link or search.\n"
                          "- **Study**: One course or guide.\n"
                          "- **Build**: One project spec.\n\n"
                          "End with ## RESOURCE BIBLE.")
                st.session_state.roadmap = m.generate_content(prompt).text
                st.session_state.current_step = "journey"; st.rerun()

# ============================================================
# STEP 3: THE JOURNEY
# ============================================================
elif st.session_state.current_step == "journey":
    tab_r, tab_a, tab_p = st.tabs(["🗺️ Roadmap", "🔬 Skills Matrix", "💎 SkillUp Pro"])
    
    with tab_r:
        if st.session_state.roadmap:
            sections = st.session_state.roadmap.split("##")
            st.markdown(sections[0])
            roadmap_phases = [s for s in sections if "Phase" in s]
            
            show_count = len(roadmap_phases) if st.session_state.is_paid else 1
            for i, phase in enumerate(roadmap_phases[:show_count]):
                st.markdown(f"<div class='phase-card'><div class='phase-number'>PHASE {i+1}</div>{phase.replace('**', '<b>').replace('\n', '<br>')}</div>", unsafe_allow_html=True)
            
            if not st.session_state.is_paid:
                st.markdown("<div class='locked-container'><h3>🔒 Roadmap Locked</h3><p>Get full 6-month access and the Resource Bible for ₹299.</p></div>", unsafe_allow_html=True)
                if st.button("Unlock Unlimited Access (₹299)", use_container_width=True, type="primary"):
                    st.session_state.is_paid = True; st.balloons(); st.rerun()
            else:
                if "BIBLE" in st.session_state.roadmap.upper():
                    bible = st.session_state.roadmap.split("##")[-1]
                    st.markdown(f"<div class='resource-vault'><h2>📦 THE RESOURCE BIBLE</h2>{bible.replace('**', '<b>').replace('\n', '<br>')}</div>", unsafe_allow_html=True)

                st.markdown("---")
                def create_pdf_bible(text, role):
                    fn = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                    c = canvas.Canvas(fn, pagesize=letter); w, h = letter
                    c.setFillColor(HexColor("#6366f1")); c.rect(0, h-inch, w, inch, fill=True, stroke=False)
                    c.setFillColor(white); c.setFont("Helvetica-Bold", 24); c.drawString(inch, h-0.7*inch, "SkillUp Mastery Guide")
                    c.setFillColor(black); c.setFont("Helvetica", 11); t_obj = c.beginText(inch, h-1.5*inch); t_obj.setLeading(14)
                    for line in text.split('\n'):
                        if t_obj.getY() < inch: c.drawText(t_obj); c.showPage(); t_obj = c.beginText(inch, h-inch); t_obj.setFont("Helvetica", 11)
                        if "##" in line: t_obj.setFont("Helvetica-Bold", 14); t_obj.textLine(line); t_obj.setFont("Helvetica", 11)
                        else: t_obj.textLine(line[:95])
                    c.drawText(t_obj); c.save(); return fn

                if st.button("📄 Download Master PDF", use_container_width=True):
                    path = create_pdf_bible(st.session_state.roadmap, st.session_state.role)
                    with open(path, "rb") as f: st.download_button("Save PDF", f, file_name="SkillUp_Roadmap.pdf")
                    os.remove(path)

    with tab_a:
        st.markdown("### 🔬 Career Analysis")
        if not st.session_state.is_paid: st.warning("Upgrade to Pro to see your gap analysis.")
        else:
            with st.spinner("Analyzing..."):
                st.write(get_smart_gap_analysis(st.session_state.resume_text, st.session_state.role, st.session_state.goal))

    with tab_p:
        st.markdown("### 💎 Pro Status")
        if st.session_state.is_paid: st.success("💎 PRO ACTIVE")
        else: st.info("Basic Tier")

if st.button("🔄 Reset", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.rerun()
