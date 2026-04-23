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
    <p class="app-subtitle">The World's Most Sophisticated Career Navigation Engine</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### 🗂️ Managed Career Plans")
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
        <h1>Stop Information Overload. Start Your Mastery.</h1>
        <p style='font-size: 1.4rem;'>SkillUp analyzes your current skill profile and builds a <b>Sophisticated 6-Month Curriculum</b> 
        designed to get you hired or promoted. No random searching. Just the absolute best resources in exact sequence.</p>
        <div style='margin-top: 2.5rem; display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;'>
            <div class="feature-tag">🎯 Skills Gap Matrix</div>
            <div class="feature-tag">📺 Clickable Video Paths</div>
            <div class="feature-tag">🛠️ Project Blueprints</div>
            <div class="feature-tag">📄 Professional PDF Bible</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([1,2,1])
    with col_c2:
        if st.button("🚀 Start My Professional Analysis", use_container_width=True, type="primary"):
            st.session_state.current_step = "selection"; st.rerun()

# ============================================================
# STEP 2: PROFILE DISCOVERY
# ============================================================
elif st.session_state.current_step == "selection":
    st.markdown("<h2 class='step-title'>🧠 Architecture Phase: Set Your Target</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            suggested_roles = [
                "Data Analyst", "Project Manager", "Operations Manager", "Full Stack Developer", "AI Engineer",
                "Customer Support Executive", "Soft Skills Trainer", "Quality Analyst (QA)", "Workforce Management (WFM)",
                "MIS Manager", "Marketing Manager", "Director of Operations", "VP Operations", "Performance Marketer"
            ]
            st.session_state.role = st.selectbox("Define Your Target Destination", options=[""] + suggested_roles + ["Other"])
            if st.session_state.role == "Other": st.session_state.role = st.text_input("Specify Role Details")
            st.session_state.goal = st.text_input("Ultimate Career Ambition", placeholder="e.g., Senior Management in International Tech BPO")

        with col2:
            st.caption("We compare your resume against 100,000+ job data points to find your exact Skill Delta.")
            up_file = st.file_uploader("Upload Professional Profile (PDF/JSON)", type=["pdf", "json"])
            if up_file:
                with st.spinner("Decoding Professional Profile..."):
                    if up_file.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                            t.write(up_file.read()); temp_p = t.name
                        st.session_state.resume_text = parse_resume(temp_p)
                        if os.path.exists(temp_p): os.remove(temp_p)
                    else: st.session_state.resume_text = parse_linkedin_json(json.load(up_file))
                    st.success("✅ Profile Decoded Successfully")

    if st.button("🗺️ Build My Sophisticated Roadmap", use_container_width=True, type="primary"):
        if not st.session_state.resume_text or not st.session_state.role:
            st.error("Identification required.")
        else:
            with st.spinner("Architecting Your Mastery Path..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                prompt = (f"ACT AS A GLOBAL CURRICULUM ARCHITECT. Analyze this User Case:\n"
                          f"CURRENT PROFILE: {st.session_state.resume_text[:2000]}\n"
                          f"TARGET ROLE: {st.session_state.role}\n"
                          f"CAREER GOAL: {st.session_state.goal}\n\n"
                          "1. **DETAILED GAP ANALYSIS**: Identify the exact 5-7 skills/tools the user lacks for this role.\n"
                          "2. **HYPER-SPECIFIC SEQUENCED ROADMAP**: Generate a 6-month curriculum (Months 1-6).\n"
                          "For each month (## Phase X: Month Y), include EXACTLY:\n"
                          "- **Watch**: Specific YouTube Search Link (e.g., https://www.youtube.com/results?search_query=mastering+X).\n"
                          "- **Study**: Official Doc or Course Name (e.g., 'Google Data Analytics Certificate on Coursera').\n"
                          "- **Build**: A sophisticated, step-by-step project blueprint.\n\n"
                          "3. **THE RESOURCE BIBLE**: At the end, include a section ## THE RESOURCE BIBLE with all direct links mentioned.")
                st.session_state.roadmap = generate_roadmap(prompt)
                st.session_state.current_step = "journey"; st.rerun()

# ============================================================
# STEP 3: THE MASTERPLAN
# ============================================================
elif st.session_state.current_step == "journey":
    tab_r, tab_a, tab_p = st.tabs(["🗺️ Mastery Roadmap", "🔍 Skill Match Matrix", "💎 SkillUp Pro"])
    
    with tab_r:
        if st.session_state.roadmap:
            # Structuring Logic
            sections = st.session_state.roadmap.split("##")
            roadmap_intro = sections[0]
            roadmap_phases = [s for s in sections if "Phase" in s]
            
            st.markdown(roadmap_intro)
            
            # Show Analysis Header
            st.markdown("<div class='analysis-header'>🎯 6-Month Growth Roadmap</div>", unsafe_allow_html=True)

            show_count = len(roadmap_phases) if st.session_state.is_paid else 1
            
            for i, phase in enumerate(roadmap_phases[:show_count]):
                st.markdown(f"""
                <div class="phase-card">
                    <div class="phase-number">PHASE {i+1}</div>
                    {phase.replace('Watch:', '📺 <b>Watch:</b>').replace('Study:', '🎓 <b>Study:</b>').replace('Build:', '🛠️ <b>Build:</b>').replace('\n', '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            if not st.session_state.is_paid:
                st.markdown("<div class='locked-container'><h3>🔒 Your Premium Path is Encrypted</h3><p>Upgrade to Pro to unlock the remaining 5 phases, the Skill Match Matrix, and the full Resource Bible.</p></div>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.subheader("💳 Instant Career Unlock")
                    m = st.radio("Access Method", ["UPI", "Credit/Debit Card"], horizontal=True)
                    if st.button("Unlock Pro Mastery (₹299)", use_container_width=True, type="primary"):
                        st.session_state.is_paid = True; st.balloons(); st.rerun()
            else:
                bible = ""
                if "RESOURCE BIBLE" in st.session_state.roadmap:
                    bible = st.session_state.roadmap.split("##")[-1]
                    st.markdown(f"<div class='resource-vault'><h2>📦 THE RESOURCE BIBLE</h2>{bible.replace('**', '<b>').replace('\n', '<br>')}</div>", unsafe_allow_html=True)

                st.markdown("---")
                def create_master_pdf(text, role):
                    fn = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                    c = canvas.Canvas(fn, pagesize=letter); w, h = letter
                    # Styled Header
                    c.setFillColor(HexColor("#6366f1")); c.rect(0, h-1.2*inch, w, 1.2*inch, fill=True, stroke=False)
                    c.setFillColor(white); c.setFont("Helvetica-Bold", 26); c.drawString(inch, h-0.8*inch, "SkillUp: The Ultimate Roadmap")
                    c.setFont("Helvetica", 14); c.drawString(inch, h-1.1*inch, f"Target Role: {role}")
                    # Divider
                    c.setStrokeColor(gray); c.line(inch, h-1.5*inch, w-inch, h-1.5*inch)
                    # Text Body
                    c.setFillColor(black); c.setFont("Helvetica", 11); t_obj = c.beginText(inch, h-1.8*inch); t_obj.setLeading(15)
                    for line in text.split('\n'):
                        if t_obj.getY() < 1.2*inch: c.drawText(t_obj); c.showPage(); t_obj = c.beginText(inch, h-inch); t_obj.setFont("Helvetica", 11)
                        if "##" in line: t_obj.setFont("Helvetica-Bold", 14); t_obj.setFillColor(HexColor("#6366f1")); t_obj.textLine(line); t_obj.setFont("Helvetica", 11); t_obj.setFillColor(black)
                        else: t_obj.textOut(line[:100]); t_obj.textLine("")
                    c.drawText(t_obj); c.save(); return fn

                if st.button("📄 Download Your Professional Upskilling Bible", use_container_width=True):
                    path = create_master_pdf(st.session_state.roadmap, st.session_state.role)
                    with open(path, "rb") as f: st.download_button("Save Final Roadmap PDF", f, file_name=f"SkillUp_Bible_{st.session_state.role}.pdf")
                    os.remove(path)

    with tab_a:
        st.markdown("### 🔍 The Skill Match Matrix")
        if not st.session_state.is_paid:
            st.warning("Locked for Pro Users. Pay ₹299 to see your full gap analysis.")
        else:
            with st.spinner("Analyzing Skill Delta..."):
                try:
                    gap_data = get_smart_gap_analysis(st.session_state.resume_text, st.session_state.role, st.session_state.goal)
                    st.info("Top recommendations based on your profile:")
                    st.markdown(gap_data)
                except Exception as e: st.error(f"Error: {e}")

    with tab_p:
        st.markdown("### 🚀 Subscription Center")
        if st.session_state.is_paid: st.success("💎 PRO ACCESS ACTIVE")
        else: st.info("Basic Tier")

if st.button("🔄 Reset Navigation", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.rerun()
