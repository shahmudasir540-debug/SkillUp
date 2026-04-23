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
    <p class="app-subtitle">Elevate Your Career with AI Precision</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar (Clean & Modern) ---
with st.sidebar:
    st.markdown("### 🗂️ Your Journey Archive")
    if not st.session_state.roadmaps_db:
        st.caption("No recent journeys found.")
    for r in st.session_state.roadmaps_db[:5]:
        if st.button(f"📌 {r['role'][:20]}...", key=f"sb_{r['id']}", use_container_width=True):
            st.session_state.roadmap = r["roadmap"]
            st.session_state.goal = r["goal"]
            st.session_state.role = r["role"]
            st.session_state.resume_text = r["resume"]
            st.session_state.current_step = "journey"
            st.rerun()
    st.markdown("---")
    st.caption("SkillUp Pro v2.5 | Powered by Gemini")

# ============================================================
# STEP 1: ONBOARDING
# ============================================================
if st.session_state.current_step == "onboarding":
    st.markdown("""
    <div class="hero-section">
        <h1>Transform Your Professional Future</h1>
        <p>Get a personalized 6-month upskilling roadmap with direct resource links and project blueprints.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([1,2,1])
    with col_c2:
        if st.button("🚀 Begin My Transformation", use_container_width=True, type="primary"):
            st.session_state.current_step = "selection"
            st.rerun()

# ============================================================
# STEP 2: DATA DISCOVERY (The Selection Page)
# ============================================================
elif st.session_state.current_step == "selection":
    st.markdown("<h2 class='step-title'>📄 Build Your Profile</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            # Auto-suggestion Role List
            suggested_roles = [
                "AI Engineer", "Full Stack Developer", "Data Scientist", "DevOps Engineer", "Cloud Architect",
                "Customer Support Executive", "Soft Skills Trainer", "Quality Analyst (QA)", "Operations Manager",
                "Workforce Management (WFM)", "MIS Manager", "Marketing Campaign Manager", "Instructional Designer",
                "Director (Operations)", "VP Operations"
            ]
            st.session_state.role = st.selectbox(
                "Target Role (Auto-suggestions)",
                options=[""] + suggested_roles + ["Other"],
                placeholder="Search or Select your dream role..."
            )
            if st.session_state.role == "Other":
                st.session_state.role = st.text_input("Enter your custom role")
            
            st.session_state.goal = st.text_input("Career Ambition", placeholder="e.g., Lead an International BPO center")

        with col2:
            up_file = st.file_uploader("Upload Resume (PDF/JSON)", type=["pdf", "json"])
            if up_file:
                with st.spinner("Analyzing Experience..."):
                    if up_file.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                            t.write(up_file.read()); temp_p = t.name
                        st.session_state.resume_text = parse_resume(temp_p)
                        if os.path.exists(temp_p): os.remove(temp_p)
                    else:
                        st.session_state.resume_text = parse_linkedin_json(json.load(up_file))
                    st.success("✅ Profile Verified")

    if st.button("🗺️ Generate High-Value Roadmap", use_container_width=True, type="primary"):
        if not st.session_state.resume_text or not st.session_state.role:
            st.error("Please provide both your target role and resume.")
        else:
            with st.spinner("Building Your 6-Month Success Path..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                prompt = (f"Act as a high-level Career Strategist. Resume: {st.session_state.resume_text}\n"
                          f"Target: {st.session_state.role}\nGoal: {st.session_state.goal}\n\n"
                          "Generate a structure for a 6-month roadmap. "
                          "For each Phase (## Phase X), include a bolded header and then bullet points for modules. "
                          "Strictly use this format:\n\n"
                          "## Phase 1: [Name]\n"
                          "**Focus**: ...\n"
                          "**Project**: ...\n"
                          "**Resources**: ...\n\n"
                          "Include a final section: ## RESOURCE VAULT\n"
                          "Provide specific URLs and names for YouTube, Documentation, and Courses.")
                st.session_state.roadmap = generate_roadmap(prompt)
                st.session_state.current_step = "journey"
                st.rerun()

# ============================================================
# STEP 3: THE JOURNEY (All other tabs visible)
# ============================================================
elif st.session_state.current_step == "journey":
    tab_r, tab_a, tab_p = st.tabs(["🗺️ Your Roadmap", "🔬 Deep Analysis", "💎 SkillUp Pro"])
    
    with tab_r:
        if st.session_state.roadmap:
            # Structuring the messy text into beautiful cards
            phases = re.split(r'## Phase \d+:', st.session_state.roadmap)
            roadmap_header = phases[0]
            actual_phases = phases[1:]
            
            # Show Header
            st.markdown(roadmap_header)
            
            # Show Phases as Cards
            show_count = len(actual_phases) if st.session_state.is_paid else 1
            
            for i, phase in enumerate(actual_phases[:show_count]):
                st.markdown(f"""
                <div class="phase-card">
                    <div class="phase-number">PHASE {i+1}</div>
                    {phase.replace('**', '<b>').replace('\n', '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            if not st.session_state.is_paid:
                st.markdown("""
                <div class="locked-container">
                    <h3>🔒 Your Path is Gated</h3>
                    <p>Unlock the remaining 5 phases, project blueprints, and the Resource Vault for just ₹299.</p>
                </div>
                """, unsafe_allow_html=True)
                
                # In-line Payment
                with st.container(border=True):
                    st.subheader("💳 Instant Unlock")
                    m = st.radio("Select Method", ["UPI", "Card"], horizontal=True, key="inline_pay_method")
                    with st.form("inline_pay"):
                        if m == "Card": st.text_input("Card Details")
                        else: st.text_input("UPI ID")
                        if st.form_submit_button("💰 Pay ₹299 & Unlock Now", use_container_width=True):
                            st.session_state.is_paid = True
                            st.balloons(); st.rerun()
            else:
                # Show Resources Vault at the end
                if "RESOURCE VAULT" in st.session_state.roadmap:
                    vault = st.session_state.roadmap.split("## RESOURCE VAULT")[-1]
                    st.markdown(f"""
                    <div class="resource-vault">
                        <h2 style='margin-top:0'>📚 RESOURCE VAULT</h2>
                        {vault.replace('**', '<b>').replace('\n', '<br>')}
                    </div>
                    """, unsafe_allow_html=True)

                # PDF Export (Upgraded)
                st.markdown("---")
                def create_premium_pdf(text, role):
                    fn = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                    c = canvas.Canvas(fn, pagesize=letter)
                    w, h = letter
                    # Header
                    c.setFillColor(HexColor("#6366f1")); c.rect(0, h-inch, w, inch, fill=True, stroke=False)
                    c.setFillColor(white); c.setFont("Helvetica-Bold", 24); c.drawString(inch, h-0.7*inch, "SkillUp Roadmap")
                    c.setFont("Helvetica", 12); c.drawString(w-3*inch, h-0.7*inch, role)
                    # Body
                    c.setFillColor(black); c.setFont("Helvetica", 11)
                    text_obj = c.beginText(inch, h-1.5*inch)
                    text_obj.setLeading(14)
                    for line in text.split('\n'):
                        if text_obj.getY() < inch:
                            c.drawText(text_obj); c.showPage()
                            text_obj = c.beginText(inch, h-inch); text_obj.setFont("Helvetica", 11)
                        if "##" in line: text_obj.setFont("Helvetica-Bold", 14); text_obj.textLine(line); text_obj.setFont("Helvetica", 11)
                        else: text_obj.textLine(line[:95])
                    c.drawText(text_obj); c.save()
                    return fn

                if st.button("📄 Download Professional PDF Guide", use_container_width=True):
                    path = create_premium_pdf(st.session_state.roadmap, st.session_state.role)
                    with open(path, "rb") as f:
                        st.download_button("Save PDF to Device", f, file_name=f"SkillUp_{st.session_state.role}.pdf")
                    os.remove(path)

    with tab_a:
        st.markdown("### 🔬 Career Intelligence Analysis")
        with st.expander("🤖 AI Gap Analysis", expanded=True):
            if st.button("Detect My Skills Gaps"):
                st.write(get_smart_gap_analysis(st.session_state.resume_text, st.session_state.role, st.session_state.goal))
        with st.expander("🎯 Job Match Simulation"):
            jd = st.text_area("JD Content")
            if st.button("Simulate Match"):
                m = genai.GenerativeModel("gemini-2.5-flash"); st.write(m.generate_content(f"Resume: {st.session_state.resume_text}\nJD: {jd}").text)

    with tab_p:
        st.markdown("### 💎 Subscription Status")
        if st.session_state.is_paid: st.success("PRO Active")
        else: st.warning("Basic User")

if st.button("🔄 Start Over", use_container_width=True):
    st.session_state.current_step = "onboarding"; st.session_state.roadmap = ""; st.rerun()
