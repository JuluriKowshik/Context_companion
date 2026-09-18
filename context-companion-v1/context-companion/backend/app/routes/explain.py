from fastapi import APIRouter, Depends, Request

from ..config import Settings, get_settings
from ..schemas import ExplainRequest, ExplainResponse, ShownRequest
from ..services import explain_service
from ..services.explain_service import Services

router = APIRouter()


def get_services(request: Request) -> Services:
    return request.app.state.services


@router.post("/explain", response_model=ExplainResponse)
async def explain(req: ExplainRequest, svc: Services = Depends(get_services)) -> ExplainResponse:
    return await explain_service.explain(req, svc)


@router.post("/shown")
async def shown(req: ShownRequest, svc: Services = Depends(get_services)) -> dict:
    """Called by the extension after a card is actually displayed."""
    entry = svc.index.get(req.concept)
    key = entry.key if entry else req.concept.strip().lower()
    svc.sessions.mark_explained(req.video_id, key, req.cue_start)
    return {"ok": True}


@router.get("/config")
async def config(settings: Settings = Depends(get_settings)) -> dict:
    """Display policy for the extension. One place to tune: .env."""
    return {
        "prefetch_window_seconds": settings.prefetch_window_seconds,
        "auto_show_confidence": settings.auto_show_confidence,
        "auto_hint_cooldown_seconds": settings.auto_hint_cooldown_seconds,
        "max_hints_per_minute": settings.max_hints_per_minute,
        "recent_concept_ttl_seconds": settings.recent_concept_ttl_seconds,
        "late_display_grace_seconds": settings.late_display_grace_seconds,
        "card_lifetime_seconds": settings.card_lifetime_seconds,
        "max_card_queue_size": settings.max_card_queue_size,
        "max_cards_per_cue": settings.max_cards_per_cue,
    }


@router.get("/")
async def root() -> dict:
    return {
        "service": "Context Companion backend",
        "check_status": "/health",
        "stats": "/stats",
        "config": "/config",
        "explain": "POST /explain (used by the extension)",
    }


@router.get("/health")
async def health(svc: Services = Depends(get_services), settings: Settings = Depends(get_settings)) -> dict:
    model = {
        "gemini": settings.gemini_model,
        "groq": settings.groq_model,
        "grok": settings.grok_model,
    }.get(svc.provider.name, "none")
    return {
        "ok": True,
        "provider": svc.provider.name,
        "model": model,
        "model_configured": svc.provider.name != "mock",
        "bundled_concepts": len(svc.index),
    }


@router.get("/stats")
async def stats(svc: Services = Depends(get_services)) -> dict:
    return {"index_size": len(svc.index), **svc.learned.stats(), **svc.sessions.stats()}
