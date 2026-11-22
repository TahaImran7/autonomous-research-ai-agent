import os
from typing import TypedDict, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from tavily import TavilyClient
from langgraph.graph import StateGraph, END

from agent_service.app.schemas import ResearchReport

# .env load karein
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Clients initialize karein (Model name apni Groq console ke mutabiq rakhein)
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.2,
    api_key=os.getenv("GROQ_API_KEY")
)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Helper Schema for Planner Node
class SearchQueries(BaseModel):
    queries: List[str] = Field(description="2 to 3 targeted web search queries")

# LangGraph State Definition
class ResearchState(TypedDict):
    topic: str
    search_queries: List[str]
    raw_research: str
    sources: List[str]
    final_report: dict

# Node 1: Search Queries Plan Karna (json_mode ke saath)
def planner_node(state: ResearchState) -> dict:
    structured_planner = llm.with_structured_output(SearchQueries, method="json_mode")
    prompt = (
        f"You are a senior technical & market research planner. "
        f"Generate 3 concise, high-signal web search queries to thoroughly research: '{state['topic']}'. "
        f"Focus on architecture/product details, competitors, and current risks.\n\n"
        f"Respond ONLY in valid JSON matching this exact schema: "
        f'{{"queries": ["query 1", "query 2", "query 3"]}}'
    )
    response = structured_planner.invoke(prompt)
    return {"search_queries": response.queries}

# Node 2: Tavily se Live Web Data Nikalna
def researcher_node(state: ResearchState) -> dict:
    collected_notes = []
    collected_urls = set()

    for query in state["search_queries"]:
        search_res = tavily.search(query=query, max_results=3)
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

# Node 3: Structured Executive Report Banana (json_mode ke saath)
def analyst_node(state: ResearchState) -> dict:
    structured_analyst = llm.with_structured_output(ResearchReport, method="json_mode")
    prompt = (
        f"You are an expert industry analyst. Synthesize the following web research into a structured report "
        f"about '{state['topic']}'. Rely ONLY on the provided research context and include the exact source URLs.\n\n"
        f"RESEARCH CONTEXT:\n{state['raw_research']}\n\n"
        f"AVAILABLE SOURCE URLS:\n{state['sources']}\n\n"
        f"Respond ONLY in valid JSON matching this exact schema:\n"
        f'{{"executive_summary": "string", '
        f'"key_findings": ["string"], '
        f'"competitors_or_alternatives": ["string"], '
        f'"risks_and_challenges": ["string"], '
        f'"sources": ["string"]}}'
    )
    report: ResearchReport = structured_analyst.invoke(prompt)
    return {"final_report": report.model_dump()}

# LangGraph Build & Compile
def build_research_graph():
    workflow = StateGraph(ResearchState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", END)

    return workflow.compile()

# Reusable compiled graph instance
research_agent = build_research_graph()

def run_research_pipeline(topic: str) -> dict:
    initial_state = {
        "topic": topic,
        "search_queries": [],
        "raw_research": "",
        "sources": [],
        "final_report": {}
    }
    final_state = research_agent.invoke(initial_state)
    return final_state["final_report"]