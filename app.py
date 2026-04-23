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
from reportlab.lib.colors import HexColor, black, white
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
    <p class="app-subtitle">The Precision Upskilling & Career Navigation System</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### 🗂️ Your Saved Escape Plans")
    if not st.session_state.roadmaps_db:
        st.caption("No recent journeys found.")
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
        <h1>Your Personalized Escape Plan to Your Dream Role</h1>
        <p style='font-size: 1.4rem;'>SkillUp is your ultimate <b>upskilling navigation system</b>. Stop the information overload. 
        We curate the <i>best</i> resources, projects, and books to get you job-ready for your next promotion or career switch.</p>
        <div style='margin-top: 2rem; display: flex; gap: 1rem; justify-content: center;'>
            <div class="feature-tag">✅ Exact YouTube Links</div>
            <div class="feature-tag">✅ Curated Course Picks</div>
            <div class="feature-tag">✅ Step-by-Step Projects</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([1,2,1])
    with col_c2:
        if st.button("🚀 Build My Custom Roadmap", use_container_width=True, type="primary"):
            st.session_state.current_step = "selection"; st.rerun()

# ============================================================
# STEP 2: PROFILE & GOALS
# ============================================================
elif st.session_state.current_step == "selection":
    st.markdown("<h2 class='step-title'>📄 Set Your Destination</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            suggested_roles = [
                "Data Analyst", "Project Manager", "Operations Manager", "Full Stack Developer", "AI Engineer",
                "Customer Support Executive", "Soft Skills Trainer", "Quality Analyst (QA)", "Workforce Management (WFM)",
                "MIS Manager", "Marketing Manager", "Director of Operations", "VP Operations", "Edtech Sales Manager"
            ]
            st.session_state.role = st.selectbox("Search your Dream Role / Target Path", options=[""] + suggested_roles + ["Other"])
            if st.session_state.role == "Other": st.session_state.role = st.text_input("Enter your custom role")
            st.session_state.goal = st.text_input("Immediate Goal (Promotion, Switch, etc.)", placeholder="e.g., Transition from BPO to Data Analytics")

        with col2:
            st.caption("Upload your current resume so we can detect your starting point.")
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

    if st.button("🗺️ Create My Navigation Path", use_container_width=True, type="primary"):
        if not st.session_state.resume_text or not st.session_state.role:
            st.error("Missing Profile or Role selection.")
        else:
            with st.spinner("Curating the Ultimate Escape Plan..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                prompt = (f"ACT AS A CAREER NAVIGATOR. Resume: {st.session_state.resume_text}\n"
                          f"Target: {st.session_state.role}\n"
                          f"Objective: {st.session_state.goal}\n\n"
                          "ELIMINATE INFORMATION OVERLOAD. Provide a hyper-specific, strictly sequenced 6-month learning path."
                          "Format carefully with ## Phase X: [Name]. Within each phase, use:\n"
                          "1. **The 'One Best' Resource**: (One YouTube link, One Book, or One Article only - no lists!)\n"
                          "2. **Mastery Tasks**: What to do First, What to do Next.\n"
                          "3. **Capstone Project**: One high-impact portfolio project blueprint.\n\n"
                          "Include a final section: ## THE RESOURCE DIRECTORY\n"
                          "List every resource mentioned with its direct clickable link.")
                st.session_state.roadmap = generate_roadmap(prompt)
                st.session_state.current_step = "journey"; st.rerun()

# ============================================================
# STEP 3: THE JOURNEY
# ============================================================
elif st.session_state.current_step == "journey":
    tab_r, tab_a, tab_p = st.tabs(["🗺️ Navigation Roadmap", "🔬 Skill Gap Detection", "💎 SkillUp Pro"])
    
    with tab_r:
        if st.session_state.roadmap:
            phases = re.split(r'## Phase \d+:', st.session_state.roadmap)
            roadmap_header = phases[0]; actual_phases = phases[1:]
            
            st.markdown(roadmap_header)
            show_count = len(actual_phases) if st.session_state.is_paid else 1
            
            for i, phase in enumerate(actual_phases[:show_count]):
                st.markdown(f"<div class='phase-card'><div class='phase-number'>PHASE {i+1}</div>{phase.replace('**', '<b>').replace('\n', '<br>')}</div>", unsafe_allow_html=True)
            
            if not st.session_state.is_paid:
                st.markdown("<div class='locked-container'><h3>🔒 Complete Your Navigation Plan</h3><p>Pro members get the full 6-month sequenced path and the Resource Directory.</p></div>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.subheader("💳 Instant Unlock")
                    m = st.radio("Pay via", ["UPI", "Card"], horizontal=True)
                    if st.button("Unlock Unlimited Access (₹299)", use_container_width=True, type="primary"):
                        st.session_state.is_paid = True; st.balloons(); st.rerun()
            else:
                if "DIRECTOR" in st.session_state.roadmap or "DIRECTORY" in st.session_state.roadmap:
                    vault = st.session_state.roadmap.split("##")[-1]
                    st.markdown(f"<div class='resource-vault'><h2>📚 THE RESOURCE DIRECTORY</h2>{vault.replace('**', '<b>').replace('\n', '<br>')}</div>", unsafe_allow_html=True)

                st.markdown("---")
                def create_final_pdf(text, role):
                    fn = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                    c = canvas.Canvas(fn, pagesize=letter); w, h = letter
                    c.setFillColor(HexColor("#6366f1")); c.rect(0, h-inch, w, inch, fill=True, stroke=False)
                    c.setFillColor(white); c.setFont("Helvetica-Bold", 24); c.drawString(inch, h-0.7*inch, "SkillUp: The Escape Plan")
                    c.setFillColor(black); c.setFont("Helvetica", 11); text_obj = c.beginText(inch, h-1.5*inch); text_obj.setLeading(14)
                    for line in text.split('\n'):
                        if text_obj.getY() < inch: c.drawText(text_obj); c.showPage(); text_obj = c.beginText(inch, h-inch); text_obj.setFont("Helvetica", 11)
                        if "##" in line: text_obj.setFont("Helvetica-Bold", 14); text_obj.textLine(line); text_obj.setFont("Helvetica", 11)
                        else: text_obj.textLine(line[:95])
                    c.drawText(text_obj); c.save(); return fn

                if st.button("📄 Download Your Upskilling PDF Bible", use_container_width=True):
                    path = create_final_pdf(st.session_state.roadmap, st.session_state.role)
                    with open(path, "rb") as f: st.download_button("Save Navigation PDF", f, file_name=f"SkillUp_Plan.pdf")
                    os.remove(path)

    with tab_a:
        st.markdown("### 🔬 Career Intelligence Analysis")
        with st.expander("🤖 Smart AI Gap Analysis", expanded=True):
            if st.button("Analyze Current Gaps"): st.write(get_smart_gap_analysis(st.session_state.resume_text, st.session_state.role, st.session_state.goal))

    with tab_p:
        st.markdown("### 💎 Subscription")
        if st.session_state.is_paid: st.success("PRO - Full Access")
        else: st.warning("Basic Preview")

if st.button("🔄 Start Over", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.rerun()
