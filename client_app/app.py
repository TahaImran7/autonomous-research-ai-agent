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

st.set_page_config(page_title="AI Research Client", page_icon=":material/search:", layout="wide")
st.title(":material/query_stats: Autonomous Tech & Market Research Client")
st.caption("Decoupled Client App — Communicating via REST API with Background Agent Microservice")

# Input Form
with st.form("research_form"):
    topic = st.text_input("Enter a company, technology, or market topic:", placeholder="e.g., Groq LPU vs Nvidia H100 inference")
    submitted = st.form_submit_button("Start Autonomous Research", icon=":material/rocket_launch:")

if submitted and topic.strip():
    try:
        # 1. submit task to Agent Microservice
        res = requests.post(
            f"{AGENT_SERVICE_URL}/research",
            json={"topic": topic.strip()},
            headers=HEADERS,
            timeout=60
        )
        res.raise_for_status()
        task_data = res.json()
        task_id = task_data["task_id"]

        st.info(f"Task Queued! ID: `{task_id}` — Waiting for background agent worker...", icon=":material/schedule:")
        progress_bar = st.progress(10)
        status_placeholder = st.empty()

        # 2. Polling Loop (check status every 3 seconds)
        while True:
            status_res = requests.get(
                f"{AGENT_SERVICE_URL}/tasks/{task_id}",
                headers=HEADERS,
                timeout=60
            )
            status_res.raise_for_status()
            current_data = status_res.json()
            state = current_data["status"]

            if state == "QUEUED":
                status_placeholder.warning("Status: QUEUED (Waiting for available worker...)", icon=":material/hourglass_empty:")
                progress_bar.progress(25)
            elif state == "RUNNING":
                status_placeholder.info("Status: RUNNING (Agent is searching web & synthesizing report...)", icon=":material/sync:")
                progress_bar.progress(65)
            elif state == "COMPLETED":
                progress_bar.progress(100)
                status_placeholder.success("Status: COMPLETED!", icon=":material/check_circle:")
                report = current_data["report"]

                st.divider()
                st.subheader(":material/summarize: Executive Summary")
                st.write(report["executive_summary"])

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader(":material/lightbulb: Key Findings")
                    for item in report["key_findings"]:
                        st.markdown(f"- {item}")

                with col2:
                    st.subheader(":material/compare_arrows: Competitors / Alternatives")
                    for comp in report["competitors_or_alternatives"]:
                        st.markdown(f"- {comp}")

                st.subheader(":material/warning: Risks & Challenges")
                for risk in report["risks_and_challenges"]:
                    st.markdown(f"- {risk}")

                st.subheader(":material/link: Verified Sources")
                for src in report["sources"]:
                    st.markdown(f"- [{src}]({src})")
                break

            elif state == "FAILED":
                progress_bar.empty()
                status_placeholder.error(f"Agent Failed: {current_data.get('error_message')}", icon=":material/error:")
                break

            time.sleep(3)

    except requests.exceptions.RequestException as e:
        st.error(f"Connection Error with Agent Microservice: {e}", icon=":material/wifi_off:")