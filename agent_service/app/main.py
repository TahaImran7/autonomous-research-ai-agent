import os
import ssl
import uuid
import json
import redis
from fastapi import FastAPI, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from agent_service.app.database import init_db, get_db, AgentTask
from agent_service.app.schemas import ResearchRequest, TaskAcceptedResponse, TaskStatusResponse
from agent_service.app.worker import execute_research_task

app = FastAPI(
    title="Autonomous Research Agent Microservice",
    description="Decoupled asynchronous AI agent gateway",
    version="1.1.0"
)

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "secret-agent-key-9098")
REDIS_URL = os.getenv("REDIS_URL")

if REDIS_URL and REDIS_URL.startswith("rediss://"):
    redis_client = redis.from_url(REDIS_URL, ssl_cert_reqs=ssl.CERT_NONE)
else:
    redis_client = redis.from_url(REDIS_URL)

RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60


@app.on_event("startup")
def on_startup():
    init_db()


def verify_api_key_and_rate_limit(x_api_key: str = Header(...)):
    if x_api_key != AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    rate_key = f"rate_limit:{x_api_key}"
    current_count = redis_client.incr(rate_key)
    if current_count == 1:
        redis_client.expire(rate_key, RATE_LIMIT_WINDOW_SECONDS)

    if current_count > RATE_LIMIT_MAX_REQUESTS:
        ttl = redis_client.ttl(rate_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({RATE_LIMIT_MAX_REQUESTS} requests/min). Try again in {ttl}s."
        )


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "agent-gateway"}


@app.post(
    "/research",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key_and_rate_limit)]
)
def trigger_research(request: ResearchRequest, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())

    new_task = AgentTask(
        id=task_id,
        topic=request.topic,
        status="QUEUED"
    )
    db.add(new_task)
    db.commit()

    execute_research_task.delay(task_id)

    return TaskAcceptedResponse(
        task_id=task_id,
        status="QUEUED",
        message="Research task accepted and queued for background execution."
    )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    if x_api_key != AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    parsed_report = json.loads(task.result) if task.result else None

    return TaskStatusResponse(
        task_id=task.id,
        topic=task.topic,
        status=task.status,
        report=parsed_report,
        error_message=task.error_message,
        created_at=task.created_at,
        completed_at=task.updated_at if task.status in ("COMPLETED", "FAILED") else None
    )