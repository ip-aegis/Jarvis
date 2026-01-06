from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import Project, Server
from app.services.ollama import OllamaService
from app.services.ssh import SSHService

logger = get_logger(__name__)

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    server_id: int
    path: str
    description: Optional[str] = None
    urls: Optional[list[str]] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    server_id: int
    path: str
    description: Optional[str] = None
    tech_stack: Optional[list[str]] = None
    urls: Optional[list[str]] = None
    ips: Optional[list[str]] = None
    last_scanned: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/")
async def list_projects(db: Session = Depends(get_db)):
    """List all registered projects."""
    projects = db.query(Project).all()
    result = []
    for p in projects:
        result.append(
            {
                "id": p.id,
                "name": p.name,
                "server_id": p.server_id,
                "path": p.path,
                "description": p.description,
                "tech_stack": p.tech_stack,
                "urls": p.urls,
                "ips": p.ips,
                "last_scanned": p.last_scanned.isoformat() if p.last_scanned else None,
            }
        )
    return {"projects": result}


@router.post("/")
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Register a new project for monitoring."""
    # Verify server exists
    server = db.query(Server).filter(Server.id == project.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Create project
    db_project = Project(
        name=project.name,
        server_id=project.server_id,
        path=project.path,
        description=project.description,
        urls=project.urls,
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return {
        "id": db_project.id,
        "name": db_project.name,
        "server_id": db_project.server_id,
        "path": db_project.path,
        "description": db_project.description,
        "urls": db_project.urls,
    }


@router.get("/{project_id}")
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get details for a specific project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "id": project.id,
        "name": project.name,
        "server_id": project.server_id,
        "path": project.path,
        "description": project.description,
        "tech_stack": project.tech_stack,
        "urls": project.urls,
        "ips": project.ips,
        "last_scanned": project.last_scanned.isoformat() if project.last_scanned else None,
    }


async def perform_project_scan(project_id: int, db: Session):
    """Background task to scan a project using LLM."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return

    server = db.query(Server).filter(Server.id == project.server_id).first()
    if not server:
        return

    ssh_service = SSHService()
    ollama_service = OllamaService()

    try:
        # Connect to server
        connected = await ssh_service.connect(
            host=server.ip_address,
            username=server.username,
            key_path=server.ssh_key_path,
            port=server.port,
        )

        if not connected:
            return

        # Get directory listing
        result = await ssh_service.execute(
            f"find {project.path} -maxdepth 3 -type f -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.go' -o -name '*.rs' -o -name '*.java' -o -name 'package.json' -o -name 'requirements.txt' -o -name 'Cargo.toml' -o -name 'go.mod' -o -name 'pom.xml' -o -name 'Dockerfile' -o -name 'docker-compose.yml' 2>/dev/null | head -50"
        )

        # Get README if exists
        readme_result = await ssh_service.execute(
            f"cat {project.path}/README.md 2>/dev/null | head -100"
        )

        await ssh_service.disconnect()

        # Build prompt for LLM
        prompt = f"""Analyze this project and extract:
1. Tech stack (programming languages, frameworks, tools)
2. Any URLs mentioned (API endpoints, external services)
3. Any IP addresses mentioned
4. A brief description of what this project does

Project files:
{result}

README content:
{readme_result if readme_result else 'No README found'}

Respond in this exact JSON format:
{{
  "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
  "urls": ["https://example.com/api"],
  "ips": ["10.10.20.62"],
  "description": "Brief description of the project"
}}

Only respond with valid JSON, no other text."""

        # Call LLM
        response = await ollama_service.generate(prompt)

        # Parse response
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                project.tech_stack = data.get("tech_stack", [])
                project.urls = data.get("urls", [])
                project.ips = data.get("ips", [])
                if data.get("description"):
                    project.description = data["description"]
                project.last_scanned = datetime.utcnow()
                db.commit()
            except json.JSONDecodeError:
                pass

    except Exception as e:
        logger.error("project_scan_failed", project_id=project_id, error=str(e))


@router.post("/{project_id}/scan")
async def scan_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger an LLM-powered scan of the project to extract:
    - Tech stack (languages, frameworks)
    - URLs and IPs
    - Project description
    - Dependencies
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Run scan in background
    background_tasks.add_task(perform_project_scan, project_id, db)

    return {"status": "scanning", "project_id": project_id}


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Remove a project from monitoring."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return {"status": "deleted", "project_id": project_id}
