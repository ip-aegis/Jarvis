from app.tools.base import Tool, tool_registry
from app.database import SessionLocal
from app.models import Project, Server


async def list_projects_handler() -> dict:
    """Get a list of all registered projects with their tech stacks."""
    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        return {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "description": p.description,
                    "tech_stack": p.tech_stack or [],
                    "urls": p.urls or [],
                    "ips": p.ips or [],
                    "last_scanned": p.last_scanned.isoformat() if p.last_scanned else None,
                }
                for p in projects
            ],
            "total": len(projects),
        }
    finally:
        db.close()


async def get_project_details_handler(project_id: int = None, name: str = None) -> dict:
    """Get detailed information about a specific project."""
    db = SessionLocal()
    try:
        # Find project
        if project_id:
            project = db.query(Project).filter_by(id=project_id).first()
        elif name:
            project = db.query(Project).filter(
                Project.name.ilike(f"%{name}%")
            ).first()
        else:
            return {"error": "Must provide either project_id or name"}

        if not project:
            return {"error": "Project not found"}

        # Get server info
        server = db.query(Server).filter_by(id=project.server_id).first()

        return {
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "description": project.description,
            "tech_stack": project.tech_stack or [],
            "urls": project.urls or [],
            "ips": project.ips or [],
            "server": {
                "hostname": server.hostname if server else None,
                "ip_address": server.ip_address if server else None,
            },
            "last_scanned": project.last_scanned.isoformat() if project.last_scanned else None,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }
    finally:
        db.close()


async def search_projects_handler(
    tech: str = None,
    query: str = None
) -> dict:
    """Search projects by technology stack or name/description."""
    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        results = []

        for p in projects:
            match = False

            # Search by tech stack
            if tech:
                tech_lower = tech.lower()
                if p.tech_stack:
                    for t in p.tech_stack:
                        if tech_lower in t.lower():
                            match = True
                            break

            # Search by name/description
            if query:
                query_lower = query.lower()
                if query_lower in (p.name or "").lower():
                    match = True
                if query_lower in (p.description or "").lower():
                    match = True

            # If no search criteria, return all
            if not tech and not query:
                match = True

            if match:
                results.append({
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "description": p.description,
                    "tech_stack": p.tech_stack or [],
                })

        return {
            "results": results,
            "total": len(results),
            "search_criteria": {
                "tech": tech,
                "query": query,
            },
        }
    finally:
        db.close()


# Register the tools
list_projects_tool = Tool(
    name="list_projects",
    description="Get a list of all registered projects with their tech stacks, URLs, and IPs.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=list_projects_handler,
)

get_project_details_tool = Tool(
    name="get_project_details",
    description="Get detailed information about a specific project including its tech stack, URLs, IPs, and server location.",
    parameters={
        "type": "object",
        "properties": {
            "project_id": {
                "type": "integer",
                "description": "The project ID",
            },
            "name": {
                "type": "string",
                "description": "The project name (partial match supported)",
            },
        },
        "required": [],
    },
    handler=get_project_details_handler,
)

search_projects_tool = Tool(
    name="search_projects",
    description="Search for projects by technology (e.g., 'Python', 'React') or by name/description.",
    parameters={
        "type": "object",
        "properties": {
            "tech": {
                "type": "string",
                "description": "Technology to search for (e.g., 'Python', 'FastAPI', 'React')",
            },
            "query": {
                "type": "string",
                "description": "Search term for project name or description",
            },
        },
        "required": [],
    },
    handler=search_projects_handler,
)

# Register all tools
tool_registry.register(list_projects_tool)
tool_registry.register(get_project_details_tool)
tool_registry.register(search_projects_tool)
