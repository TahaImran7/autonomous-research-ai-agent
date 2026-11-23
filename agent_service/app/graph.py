import os
import json
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from tavily import TavilyClient
from langsmith import traceable

from agent_service.app.schemas import ResearchReport

# 1. Primary + Fallback LLM Setup (JSON Mode enforced on both)
primary_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.2,
    max_retries=2,
    model_kwargs={"response_format": {"type": "json_object"}}
)

fallback_llm = ChatGroq(
    model="qwen/qwen3.8-27b",
    temperature=0.2,
    max_retries=2,
    model_kwargs={"response_format": {"type": "json_object"}}
)

# If primary_llm hits a rate limit (429) or throws an error, fallback_llm will run automatically
llm = primary_llm.with_fallbacks([fallback_llm])

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


class ResearchState(TypedDict):
    topic: str
    search_queries: List[str]
    raw_research: str
    sources: List[str]
    final_report: dict


# Node 1: Planner
def planner_node(state: ResearchState) -> dict:
    prompt = f"""You are a senior technical research planner.
Given the research topic: "{state['topic']}"
Generate 3 focused web search queries to gather current, factual, and comprehensive market/technical intelligence.

Return ONLY a valid JSON object with this exact schema:
{{"queries": ["query 1", "query 2", "query 3"]}}"""

    response = llm.invoke([
        SystemMessage(content="You output strict JSON only."),
        HumanMessage(content=prompt)
    ])
    parsed = json.loads(response.content)
    return {"search_queries": parsed.get("queries", [state["topic"]])}


@traceable(run_type="tool", name="Tavily Web Search")
def search_web(query: str) -> dict:
    return tavily.search(query=query, max_results=3)


# Node 2: Parallel Researcher
def researcher_node(state: ResearchState) -> dict:
    collected_notes = []
    collected_urls = set()
    queries = state["search_queries"]

    # All three queries will run concurrently in parallel (3x faster)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(search_web, queries))

    for search_res in results:
        for item in search_res.get("results", []):
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            if url:
                collected_urls.add(url)
            collected_notes.append(f"Source: {title} ({url})\nSummary: {content}\n")

    return {
        "raw_research": "\n---\n".join(collected_notes),
        "sources": list(collected_urls)
    }


# Node 3: Analyst
def analyst_node(state: ResearchState) -> dict:
    schema_hint = json.dumps(ResearchReport.model_json_schema(), indent=2)
    prompt = f"""You are a principal market and technology analyst.
Synthesize the following raw web research into a high-signal executive report on: "{state['topic']}"

RAW RESEARCH:
{state['raw_research'][:14000]}

AVAILABLE SOURCE URLS:
{json.dumps(state['sources'])}

Return ONLY a valid JSON object strictly matching this Pydantic JSON schema:
{schema_hint}"""

    response = llm.invoke([
        SystemMessage(content="You are an analytical engine that outputs strict valid JSON only."),
        HumanMessage(content=prompt)
    ])

    report_obj = ResearchReport.model_validate_json(response.content)
    return {"final_report": report_obj.model_dump()}


# Build LangGraph
workflow = StateGraph(ResearchState)
workflow.add_node("planner", planner_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("analyst", analyst_node)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "researcher")
workflow.add_edge("researcher", "analyst")
workflow.add_edge("analyst", END)

research_agent = workflow.compile()

# Entrypoint called by worker.py
def run_research_pipeline(topic: str) -> dict:
    initial_state: ResearchState = {
        "topic": topic,
        "search_queries": [],
        "raw_research": "",
        "sources": [],
        "final_report": {}
    }
    final_state = research_agent.invoke(initial_state)
    return final_state["final_report"]