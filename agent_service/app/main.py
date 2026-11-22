import os
import json
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from agent_service.app.database import init_db, get_db, AgentTask
from agent_service.app.schemas import ResearchRequest, TaskStatusResponse, ResearchReport
from agent_service.app.worker import execute_research_task

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

AGENT_API_KEY = os.getenv("AGENT_API_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup par database tables ensure karein
    init_db()
    yield

app = FastAPI(
    title="Autonomous Research Agent Microservice",
    version="1.0.0",
    lifespan=lifespan
)

# Security Dependency: Har request par x-api-key verify karega
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "agent-gateway"}

@app.post("/research", response_model=TaskStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_research(
    request: ResearchRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    # 1. Supabase mein naya task record banayein (Status: QUEUED)
    new_task = AgentTask(topic=request.topic, status="QUEUED")
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # 2. Upstash Redis Queue mein background job push karein
    execute_research_task.delay(new_task.id)

    # 3. Foran task_id return karein (No waiting / No timeout!)
    return TaskStatusResponse(
        task_id=new_task.id,
        topic=new_task.topic,
        status=new_task.status,
        created_at=new_task.created_at
    )

@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    parsed_report = None
    if task.result:
        parsed_report = ResearchReport(**json.loads(task.result))

    return TaskStatusResponse(
        task_id=task.id,
        topic=task.topic,
        status=task.status,
        report=parsed_report,
        error_message=task.error_message,
        created_at=task.created_at
    )