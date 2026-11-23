from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# 1. API Request Schema (Jo Client App bhejegi)
class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200, example="Groq LPU AI inference architecture")

# 2. Immediate 202 Response Schema (Jo POST /research return karega)
class TaskAcceptedResponse(BaseModel):
    task_id: str
    status: str
    message: str

# 3. Structured Output Schema (Jo Groq LLM enforce karega)
class ResearchReport(BaseModel):
    executive_summary: str = Field(description="High-level summary of the topic or company")
    key_findings: List[str] = Field(description="3 to 5 concrete technical or market insights")
    competitors_or_alternatives: List[str] = Field(description="Main competitors or alternative technologies")
    risks_and_challenges: List[str] = Field(description="Key bottlenecks, limitations, or market risks")
    sources: List[str] = Field(description="URLs used during the research")

# 4. API Status Response Schema (Jo Client App poll karegi)
class TaskStatusResponse(BaseModel):
    task_id: str
    topic: str
    status: str
    report: Optional[ResearchReport] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None