from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import ServerOnboardingError
from app.core.logging import get_logger
from app.database import get_db
from app.models import Metric, Project, Server
from app.services.agent import AgentService
from app.services.ollama import OllamaService
from app.services.ssh import SSHService

logger = get_logger(__name__)

router = APIRouter()


class ServerCredentials(BaseModel):
    hostname: str
    ip_address: str
    username: str
    password: str
    port: int = 22


class ServerOnboardRequest(BaseModel):
    credentials: ServerCredentials
    install_agent: bool = True


class ServerResponse(BaseModel):
    id: int
    hostname: str
    ip_address: str
    status: str
    os_info: Optional[str] = None
    cpu_info: Optional[str] = None
    cpu_cores: Optional[int] = None
    memory_total: Optional[str] = None
    disk_total: Optional[str] = None
    gpu_info: Optional[str] = None
    agent_installed: bool = False

    class Config:
        from_attributes = True


@router.get("/")
async def list_servers(db: Session = Depends(get_db)):
    """List all registered servers."""
    servers = db.query(Server).all()
    return {"servers": [ServerResponse.model_validate(s) for s in servers]}


@router.post("/onboard")
async def onboard_server(
    request: ServerOnboardRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Onboard a new server:
    1. Connect with provided credentials
    2. Exchange SSH keys
    3. Install monitoring agent
    4. Gather system information
    5. Save to database
    """
    # Check if server already exists
    existing = db.query(Server).filter(Server.ip_address == request.credentials.ip_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="Server with this IP already exists")

    ssh_service = SSHService()
    agent_service = AgentService()

    try:
        # Step 1: Test connection with password
        connected = await ssh_service.connect(
            host=request.credentials.ip_address,
            username=request.credentials.username,
            password=request.credentials.password,
            port=request.credentials.port,
        )

        if not connected:
            raise HTTPException(status_code=400, detail="Failed to connect to server")

        # Step 2: Exchange SSH keys
        key_exchanged = await ssh_service.exchange_keys(
            host=request.credentials.ip_address,
            username=request.credentials.username,
        )

        # Step 3: Gather system information
        system_info = await ssh_service.get_system_info()

        # Step 4: Save server to database first (to get ID for agent)
        server = Server(
            hostname=request.credentials.hostname,
            ip_address=request.credentials.ip_address,
            port=request.credentials.port,
            username=request.credentials.username,
            ssh_key_path=ssh_service.key_path if key_exchanged else None,
            status="online",
            os_info=system_info.get("os"),
            cpu_info=system_info.get("cpu"),
            cpu_cores=system_info.get("cpu_cores"),
            memory_total=system_info.get("memory_total"),
            disk_total=system_info.get("disk_total"),
            gpu_info=system_info.get("gpu"),
            agent_installed=False,
        )
        db.add(server)
        db.commit()
        db.refresh(server)

        # Step 5: Install agent if requested (now we have server.id)
        agent_installed = False
        if request.install_agent:
            agent_installed = await agent_service.install(
                ssh_service=ssh_service,
                server_id=server.id,
            )
            # Update server with agent status
            server.agent_installed = agent_installed
            db.commit()

        await ssh_service.disconnect()

        # Step 6: Generate LLM analysis of the server
        llm_analysis = None
        try:
            ollama = OllamaService()
            analysis_prompt = f"""Analyze this server and provide a brief, helpful summary for a lab administrator.

Server Information:
- Hostname: {request.credentials.hostname}
- IP Address: {request.credentials.ip_address}
- Operating System: {system_info.get('os', 'Unknown')}
- CPU: {system_info.get('cpu', 'Unknown')} ({system_info.get('cpu_cores', 'Unknown')} cores)
- Memory: {system_info.get('memory_total', 'Unknown')}
- Disk: {system_info.get('disk_total', 'Unknown')}
- GPU: {system_info.get('gpu', 'None detected')}

Please provide:
1. **Server Profile**: What type of workload is this server likely suited for? (e.g., general purpose, compute-intensive, GPU workstation, storage server, etc.)
2. **Notable Specifications**: Highlight any standout hardware features (high core count, large memory, GPU presence, etc.)
3. **Monitoring Recommendations**: Suggest 2-3 specific metrics to watch based on the hardware profile.

Keep the response concise (under 200 words) and practical."""

            llm_analysis = await ollama.generate(analysis_prompt)
        except Exception as e:
            # LLM analysis is optional, don't fail onboarding if it fails
            llm_analysis = f"Analysis unavailable: {str(e)}"

        return {
            "status": "success",
            "server_id": server.id,
            "hostname": request.credentials.hostname,
            "ip_address": request.credentials.ip_address,
            "key_exchanged": key_exchanged,
            "agent_installed": agent_installed,
            "system_info": system_info,
            "llm_analysis": llm_analysis,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "server_onboarding_failed",
            hostname=request.credentials.hostname,
            ip_address=request.credentials.ip_address,
        )
        raise ServerOnboardingError(
            "Server onboarding failed. Please check server connectivity and credentials."
        )


@router.get("/{server_id}")
async def get_server(server_id: int, db: Session = Depends(get_db)):
    """Get details for a specific server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return ServerResponse.model_validate(server)


@router.delete("/{server_id}")
async def remove_server(server_id: int, db: Session = Depends(get_db)):
    """Remove a server from monitoring."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    try:
        # Delete related records first (metrics, projects)
        db.query(Metric).filter(Metric.server_id == server_id).delete()
        db.query(Project).filter(Project.server_id == server_id).delete()

        db.delete(server)
        db.commit()
        logger.info("server_deleted", server_id=server_id, hostname=server.hostname)
        return {"status": "deleted", "server_id": server_id}
    except Exception as e:
        db.rollback()
        logger.exception("server_delete_failed", server_id=server_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete server: {str(e)}")


@router.post("/{server_id}/test-connection")
async def test_connection(server_id: int, db: Session = Depends(get_db)):
    """Test SSH connection to a server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    ssh_service = SSHService()
    try:
        # Try to connect using stored SSH key
        connected = await ssh_service.connect(
            host=server.ip_address,
            username=server.username,
            key_path=server.ssh_key_path,
            port=server.port,
        )
        await ssh_service.disconnect()

        if connected:
            # Update status to online
            server.status = "online"
            db.commit()
            return {"status": "connected", "server_id": server_id}
        else:
            server.status = "offline"
            db.commit()
            return {"status": "failed", "server_id": server_id}
    except Exception as e:
        server.status = "offline"
        db.commit()
        return {"status": "failed", "server_id": server_id, "error": str(e)}
