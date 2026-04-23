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
from reportlab.lib.colors import HexColor
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
if "roadmaps_db" not in st.session_state:
    st.session_state.roadmaps_db = load_roadmaps_db()
if "roadmap" not in st.session_state:
    st.session_state.roadmap = ""
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "goal" not in st.session_state:
    st.session_state.goal = ""
if "role" not in st.session_state:
    st.session_state.role = "Select a tech role"
if "is_paid" not in st.session_state:
    st.session_state.is_paid = False
if "first_visit" not in st.session_state:
    st.session_state.first_visit = True

# Ensure API Key is configured globally if present
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- Header ---
st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Skill<span class="title-accent">Up</span></h1>
        <p class="app-subtitle">The Complete AI Career Acceleration Platform</p>
    </div>
""", unsafe_allow_html=True)

# Onboarding Banner (Restored & Updated)
if st.session_state.first_visit:
    st.info("""
    ### 🚀 Welcome to SkillUp!
    Your all-in-one platform to bridge the gap between your skills and your dream career.
    1. **📄 Resume:** Upload your CV and set your target.
    2. **⚡ Transform:** Generate your roadmap and take control of your learning.
    """)
    if st.button("Get Started", use_container_width=True):
        st.session_state.first_visit = False
        st.rerun()

# --- Sidebar (Recent Roadmaps - Restored) ---
with st.sidebar:
    st.markdown("### 🗂️ Recent Journeys")
    if not st.session_state.roadmaps_db:
        st.caption("No recent journeys found.")
    
    for r in st.session_state.roadmaps_db[:5]:
        if st.button(f"📌 {r['role']}\n{r['goal'][:25]}...", key=f"sb_{r['id']}", use_container_width=True):
            st.session_state.roadmap = r["roadmap"]
            st.session_state.goal = r["goal"]
            st.session_state.role = r["role"]
            st.session_state.resume_text = r["resume"]
            st.rerun()

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["📄 Resume & Analysis", "🗺️ Your Roadmap", "💎 SkillUp Pro"])

# Resume Tab
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎯 Career Targets")
        st.session_state.goal = st.text_input("What is your dream role?", placeholder="e.g., Lead AI Researcher", value=st.session_state.goal)
        roles = ["Select a tech role", "AI Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer", "Product Manager", "Data Analyst", "Cybersecurity Expert", "DevOps Engineer", "UI/UX Designer", "Other"]
        st.session_state.role = st.selectbox("Industry Focus", roles, index=roles.index(st.session_state.role) if st.session_state.role in roles else 0)

    with col2:
        st.markdown("### 📄 Resume Discovery")
        up = st.file_uploader("Upload CV (PDF/JSON)", type=["pdf", "json"])
        if up:
            with st.spinner("Analyzing..."):
                if up.type == "application/pdf":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                        t.write(up.read())
                        temp_path = t.name
                    # File is now closed, safe to parse
                    st.session_state.resume_text = parse_resume(temp_path)
                    # parse_resume handles its own cleanup, but we'll ensure it's gone
                    if os.path.exists(temp_path):
                        try: os.remove(temp_path)
                        except: pass
                else:
                    st.session_state.resume_text = parse_linkedin_json(json.load(up))
                st.success("✅ Resume Analyzed")

    if st.button("🚀 Generate SkillUp Journey", use_container_width=True):
        if not st.session_state.resume_text: st.warning("Please upload a resume")
        elif st.session_state.role == "Select a tech role": st.warning("Please select a role")
        else:
            with st.spinner("Generating Journey..."):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                p = f"Resume: {st.session_state.resume_text}\nTarget: {st.session_state.role}\nGoal: {st.session_state.goal}\nGenerate a 6-month roadmap with phases, modules, and projects."
                st.session_state.roadmap = generate_roadmap(p)
                rid = roadmap_id(st.session_state.resume_text, st.session_state.goal, st.session_state.role)
                if not any(x['id'] == rid for x in st.session_state.roadmaps_db):
                    st.session_state.roadmaps_db.insert(0, {"id": rid, "role": st.session_state.role, "goal": st.session_state.goal, "roadmap": st.session_state.roadmap, "resume": st.session_state.resume_text, "timestamp": datetime.now().isoformat()})
                    save_roadmaps_db(st.session_state.roadmaps_db)
                st.success("✅ Roadmap Ready!")

    # Job Simulator (Restored)
    st.markdown("---")
    with st.expander("🎯 Job Fit Simulator", expanded=False):
        jd = st.text_area("Paste a Job Description here", height=150)
        if st.button("Simulate Interview Fit"):
            if st.session_state.resume_text and jd:
                with st.spinner("Simulating..."):
                    m = genai.GenerativeModel("gemini-2.5-flash")
                    res = m.generate_content(f"Match resume to JD:\nResume: {st.session_state.resume_text}\nJD: {jd}")
                    st.markdown(res.text)

# Roadmap Tab
with tab2:
    if st.session_state.roadmap:
        # Smart AI Gap Analysis (Restored)
        with st.expander("🔬 Smart AI Gap Analysis", expanded=True):
            if st.button("Analyze Current Gaps"):
                with st.spinner("Analyzing Gaps..."):
                    try:
                        gap = get_smart_gap_analysis(st.session_state.resume_text, st.session_state.role, st.session_state.goal)
                        st.markdown(gap)
                    except Exception as e: st.error(f"Error: {e}")

        # Live Roadmap Editing (Restored)
        st.markdown("### 🗺️ Your Learning Journey")
        if st.session_state.is_paid:
            edited_roadmap = st.text_area("Edit your journey", value=st.session_state.roadmap, height=400)
            if edited_roadmap != st.session_state.roadmap:
                st.session_state.roadmap = edited_roadmap
                # Update in DB
                rid = roadmap_id(st.session_state.resume_text, st.session_state.goal, st.session_state.role)
                for r in st.session_state.roadmaps_db:
                    if r['id'] == rid: r['roadmap'] = edited_roadmap; break
                save_roadmaps_db(st.session_state.roadmaps_db)
        else:
            st.info("💡 Pro members can edit and export their roadmap. Showing first 3 weeks...")
            st.markdown("\n".join(st.session_state.roadmap.splitlines()[:20]))
            st.markdown("""<div class="locked-content" style="padding: 2rem; text-align: center;">
                <h3>🔒 Unlock Full 6-Month Path</h3>
                <p>Pro members get the full journey, timeline, and export functions.</p>
            </div>""", unsafe_allow_html=True)

        # Timeline (Restored Functionality)
        if st.session_state.is_paid:
            st.markdown("### 🗓️ Visual Timeline")
            # Simplified Gantt Logic for speed
            lines = st.session_state.roadmap.splitlines()
            tasks = []
            curr_date = datetime.now()
            for l in lines:
                if l.strip().startswith("##"):
                    tasks.append({"Task": l[2:].strip(), "Start": curr_date, "Finish": curr_date + timedelta(weeks=4), "Type": "Phase"})
                    curr_date += timedelta(weeks=4)
            if tasks:
                df = pd.DataFrame(tasks)
                fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Type")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)

            # Q&A (Restored)
            st.markdown("### ❓ Journey Q&A")
            q = st.text_input("Ask about this path...")
            if st.button("Ask SkillUp AI"):
                m = genai.GenerativeModel("gemini-2.5-flash")
                ans = m.generate_content(f"Context: {st.session_state.roadmap}\nQ: {q}")
                st.info(ans.text)

            # Export (Restored)
            col1, col2 = st.columns(2)
            col1.download_button("📥 Export as TXT", st.session_state.roadmap, "roadmap.txt", use_container_width=True)
            col2.download_button("💾 Backup as JSON", json.dumps({"role": st.session_state.role, "roadmap": st.session_state.roadmap}), "roadmap.json", use_container_width=True)

    else:
        st.markdown("<div class='empty-state'><p>Start by uploading your resume!</p></div>", unsafe_allow_html=True)

# Pricing Tab
with tab3:
    st.markdown("### 💎 Go Pro with SkillUp")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='pricing-card'><div class='pricing-badge'>Free</div><h2>₹0</h2><p>Basic Access</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='pricing-card pricing-card-pro'><div class='pricing-badge-pro'>Pro</div><h2>₹299</h2><p>Full Journey Access</p></div>", unsafe_allow_html=True)
    
    if not st.session_state.is_paid:
        st.markdown("---")
        st.subheader("💳 Secure Payment Portal")
        m = st.radio("Pay with:", ["UPI (PhonePe/GPay)", "Card"], horizontal=True)
        with st.form("pay_f"):
            if m == "Card": 
                st.text_input("Card Num"); c_1, c_2 = st.columns(2); c_1.text_input("Exp"); c_2.text_input("CVV")
            else: st.text_input("UPI ID")
            if st.form_submit_button("💰 Pay ₹299 & Unlock All Features"):
                st.session_state.is_paid = True
                st.balloons(); st.success("✅ Welcome to the Pro family!"); st.rerun()
    else: st.success("💎 You have full Pro access.")

# Footer
st.markdown("<div class='footer'><p>© 2025 SkillUp. All rights reserved.</p></div>", unsafe_allow_html=True)
