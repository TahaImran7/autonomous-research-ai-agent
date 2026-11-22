import os
import json
import ssl
from dotenv import load_dotenv
from celery import Celery

from agent_service.app.database import SessionLocal, AgentTask
from agent_service.app.graph import run_research_pipeline

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REDIS_URL = os.getenv("REDIS_URL")

# Celery app initialize karein Upstash Redis ke saath
celery_app = Celery(
    "research_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Upstash TLS/SSL (rediss://) compatibility settings
if REDIS_URL and REDIS_URL.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.broker_use_ssl = ssl_options
    celery_app.conf.redis_backend_use_ssl = ssl_options

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    broker_transport_options={
        "socket_timeout": 15,
        "socket_connect_timeout": 15,
        "retry_on_timeout": True,
    },
    broker_connection_retry_on_startup=True,
)

@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def execute_research_task(self, task_id: str):
    db = SessionLocal()
    try:
        # 1. Database se task fetch karein
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return {"status": "error", "message": "Task not found"}

        # 2. Status RUNNING update karein
        task.status = "RUNNING"
        db.commit()

        # 3. LangGraph + Groq Research Pipeline chalayein
        report_dict = run_research_pipeline(task.topic)

        # 4. Result save karein aur status COMPLETED karein
        task.result = json.dumps(report_dict)
        task.status = "COMPLETED"
        db.commit()

        return {"status": "COMPLETED", "task_id": task_id}

    except Exception as exc:
        db.rollback()
        # Agar retries bachi hain to retry karein
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        # Final failure par database mein error record karein
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(exc)
            db.commit()
        raise exc

    finally:
        db.close()