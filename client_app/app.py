import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://127.0.0.1:8000")
AGENT_API_KEY = os.getenv("AGENT_API_KEY")

HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": AGENT_API_KEY
}

st.set_page_config(page_title="AI Research Client", page_icon="🔎", layout="wide")
st.title("🔎 Autonomous Tech & Market Research Client")
st.caption("Decoupled Client App — Communicating via REST API with Background Agent Microservice")

# Input Form
with st.form("research_form"):
    topic = st.text_input("Enter a company, technology, or market topic:", placeholder="e.g., Groq LPU vs Nvidia H100 inference")
    submitted = st.form_submit_button("Start Autonomous Research")

if submitted and topic.strip():
    try:
        # 1. Agent Microservice ko Task Submit Karein
        res = requests.post(
            f"{AGENT_SERVICE_URL}/research",
            json={"topic": topic.strip()},
            headers=HEADERS,
            timeout=30
        )
        res.raise_for_status()
        task_data = res.json()
        task_id = task_data["task_id"]

        st.info(f"Task Queued! ID: `{task_id}` — Waiting for background agent worker...")
        progress_bar = st.progress(10)
        status_placeholder = st.empty()

        # 2. Polling Loop (Har 3 second baad status check karein)
        while True:
            status_res = requests.get(
                f"{AGENT_SERVICE_URL}/tasks/{task_id}",
                headers=HEADERS,
                timeout=10
            )
            status_res.raise_for_status()
            current_data = status_res.json()
            state = current_data["status"]

            if state == "QUEUED":
                status_placeholder.warning("Status: QUEUED (Waiting for available worker...)")
                progress_bar.progress(25)
            elif state == "RUNNING":
                status_placeholder.info("Status: RUNNING (Agent is searching web & synthesizing report...)")
                progress_bar.progress(65)
            elif state == "COMPLETED":
                progress_bar.progress(100)
                status_placeholder.success("Status: COMPLETED!")
                report = current_data["report"]

                st.divider()
                st.subheader("📋 Executive Summary")
                st.write(report["executive_summary"])

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("💡 Key Findings")
                    for item in report["key_findings"]:
                        st.markdown(f"- {item}")

                with col2:
                    st.subheader("⚔️ Competitors / Alternatives")
                    for comp in report["competitors_or_alternatives"]:
                        st.markdown(f"- {comp}")

                st.subheader("⚠️ Risks & Challenges")
                for risk in report["risks_and_challenges"]:
                    st.markdown(f"- {risk}")

                st.subheader("🔗 Verified Sources")
                for src in report["sources"]:
                    st.markdown(f"- [{src}]({src})")
                break

            elif state == "FAILED":
                progress_bar.empty()
                status_placeholder.error(f"Agent Failed: {current_data.get('error_message')}")
                break

            time.sleep(3)

    except requests.exceptions.RequestException as e:
        st.error(f"Connection Error with Agent Microservice: {e}")