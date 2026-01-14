"""Settings API routes."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.services.llm_usage import log_llm_usage
from app.services.openai_service import OpenAIService
from app.services.settings import CHAT_CONTEXTS, SettingsService

logger = get_logger(__name__)
router = APIRouter()

# Context descriptions for AI recommendations
CONTEXT_DESCRIPTIONS = {
    "general": "Full lab management assistant with access to all tools - servers, metrics, projects, web search. Handles diverse queries requiring broad capabilities.",
    "monitoring": "Server infrastructure monitoring - CPU, memory, GPU, disk usage, temperatures. Interprets metrics and alerts on issues.",
    "projects": "Project management and code analysis - tech stack detection, code review, repository scanning. Requires understanding of programming concepts.",
    "network": "Network device management - switches, routers, access points, VLANs, port configurations. Technical networking focus.",
    "actions": "Infrastructure automation with confirmation workflows for destructive operations. Executes service restarts, reboots, scheduled tasks.",
    "home": "Home automation assistant - Ring doorbells, appliances (washer/dishwasher), thermostats, Apple TV/HomePod media control.",
    "journal": "Personal journaling companion for reflection and life tracking. Uses semantic search through past entries.",
    "work": "Professional work assistant for customer account management, meeting notes, follow-ups, and work activity tracking.",
}


class SettingsUpdate(BaseModel):
    """Request body for updating settings."""

    settings: dict[str, str]


class ModelDefaultsUpdate(BaseModel):
    """Request body for updating model defaults."""

    defaults: dict[str, str]


@router.get("")
async def get_all_settings(db: Session = Depends(get_db)):
    """Get all user settings."""
    service = SettingsService(db)
    return service.get_all_settings()


@router.get("/{key}")
async def get_setting(key: str, db: Session = Depends(get_db)):
    """Get a single setting value."""
    service = SettingsService(db)
    value = service.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": key, "value": value}


@router.put("")
async def update_settings(request: SettingsUpdate, db: Session = Depends(get_db)):
    """Update multiple settings."""
    service = SettingsService(db)
    service.set_multiple_settings(request.settings)
    return {"status": "updated", "count": len(request.settings)}


@router.get("/defaults/models")
async def get_model_defaults(db: Session = Depends(get_db)):
    """Get default models for all chat contexts."""
    service = SettingsService(db)
    return service.get_all_model_defaults()


@router.put("/defaults/models")
async def update_model_defaults(request: ModelDefaultsUpdate, db: Session = Depends(get_db)):
    """Update default models for chat contexts."""
    service = SettingsService(db)

    # Validate contexts
    for context in request.defaults.keys():
        if context not in CHAT_CONTEXTS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid context: {context}. Valid contexts: {CHAT_CONTEXTS}",
            )

    # Update each default
    for context, model in request.defaults.items():
        service.set_model_default(context, model)

    return {"status": "updated", "defaults": service.get_all_model_defaults()}


@router.get("/defaults/models/{context}")
async def get_model_default_for_context(context: str, db: Session = Depends(get_db)):
    """Get the default model for a specific chat context."""
    if context not in CHAT_CONTEXTS:
        raise HTTPException(
            status_code=400, detail=f"Invalid context: {context}. Valid contexts: {CHAT_CONTEXTS}"
        )
    service = SettingsService(db)
    return {"context": context, "model": service.get_default_model_for_context(context)}


@router.post("/recommend-models")
async def recommend_models():
    """Use AI to recommend the best model for each chat context."""
    openai_service = OpenAIService()

    # Get available models
    try:
        models_list = await openai_service.list_models()
        # Filter to chat models only (exclude embeddings, etc.)
        chat_models = [
            m["id"]
            for m in models_list
            if "gpt" in m["id"].lower() and "embedding" not in m["id"].lower()
        ]
    except Exception as e:
        logger.error("failed_to_list_models", error=str(e))
        chat_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    # Build the recommendation prompt
    prompt = f"""You are an AI assistant helping to configure an application called Jarvis.
Jarvis has multiple chat contexts, each with a different purpose. Your task is to recommend the best OpenAI model for each context.

Available models: {', '.join(chat_models)}

Chat contexts and their purposes:
"""
    for context, description in CONTEXT_DESCRIPTIONS.items():
        prompt += f"\n- **{context}**: {description}"

    prompt += """

Consider these factors when recommending:
1. Task complexity - complex reasoning needs more capable models
2. Cost efficiency - simpler tasks can use smaller/cheaper models
3. Speed requirements - some contexts may benefit from faster models
4. The most recent/capable models available (gpt-4o is currently the flagship)

Respond with a JSON object in this exact format (no markdown, just raw JSON):
{
  "general": {"model": "model-name", "reason": "brief reason"},
  "monitoring": {"model": "model-name", "reason": "brief reason"},
  "projects": {"model": "model-name", "reason": "brief reason"},
  "network": {"model": "model-name", "reason": "brief reason"},
  "actions": {"model": "model-name", "reason": "brief reason"},
  "home": {"model": "model-name", "reason": "brief reason"},
  "journal": {"model": "model-name", "reason": "brief reason"},
  "work": {"model": "model-name", "reason": "brief reason"}
}"""

    try:
        # Use gpt-4o for the recommendation (most capable, up-to-date knowledge)
        response, usage = await openai_service.chat_with_usage(
            messages=[{"role": "user", "content": prompt}], model="gpt-4o"
        )

        # Log usage
        log_llm_usage(
            feature="settings",
            model=usage.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            function_name="recommend_models",
        )

        # Parse the JSON response
        recommendations = json.loads(response.strip())

        return {"recommendations": recommendations, "model_used": "gpt-4o"}
    except json.JSONDecodeError as e:
        logger.error("failed_to_parse_recommendations", error=str(e), response=response)
        raise HTTPException(
            status_code=500, detail="Failed to parse AI recommendations. Please try again."
        )
    except Exception as e:
        logger.error("recommendation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")
