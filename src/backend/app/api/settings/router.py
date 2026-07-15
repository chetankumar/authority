"""Settings router (doc 04 §3). Validates via Pydantic, delegates to
SettingsService; holds no business logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_settings_service
from app.models.settings import (
    AIJobCreate,
    AIJobDefinition,
    AIJobPatch,
    AISettings,
    AISettingsPatch,
    ModelConfigOut,
    ModelCreate,
    ModelPatch,
    Placeholder,
    UserPatch,
    UserSettings,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

Service = Depends(get_settings_service)


# -- user -------------------------------------------------------------------


@router.get("/user", response_model=UserSettings)
async def get_user(svc: SettingsService = Service) -> UserSettings:
    return svc.get_user()


@router.patch("/user", response_model=UserSettings)
async def patch_user(patch: UserPatch, svc: SettingsService = Service) -> UserSettings:
    return await svc.patch_user(patch)


# -- models -----------------------------------------------------------------


@router.get("/models", response_model=list[ModelConfigOut])
async def list_models(svc: SettingsService = Service) -> list[ModelConfigOut]:
    return svc.list_models()


@router.post("/models", response_model=ModelConfigOut, status_code=201)
async def create_model(body: ModelCreate, svc: SettingsService = Service) -> ModelConfigOut:
    return await svc.create_model(body)


@router.patch("/models/{model_id}", response_model=ModelConfigOut)
async def patch_model(model_id: str, patch: ModelPatch, svc: SettingsService = Service) -> ModelConfigOut:
    return await svc.patch_model(model_id, patch)


@router.delete("/models/{model_id}", status_code=204, response_class=Response)
async def delete_model(model_id: str, svc: SettingsService = Service) -> Response:
    await svc.delete_model(model_id)
    return Response(status_code=204)


# -- ai (utility model) -----------------------------------------------------


@router.get("/ai", response_model=AISettings)
async def get_ai(svc: SettingsService = Service) -> AISettings:
    return svc.get_ai()


@router.patch("/ai", response_model=AISettings)
async def patch_ai(patch: AISettingsPatch, svc: SettingsService = Service) -> AISettings:
    return await svc.patch_ai(patch)


# -- ai-jobs ----------------------------------------------------------------


@router.get("/ai-jobs", response_model=list[AIJobDefinition])
async def list_jobs(svc: SettingsService = Service) -> list[AIJobDefinition]:
    return svc.list_jobs()


@router.post("/ai-jobs", response_model=AIJobDefinition, status_code=201)
async def create_job(body: AIJobCreate, svc: SettingsService = Service) -> AIJobDefinition:
    return await svc.create_job(body)


@router.patch("/ai-jobs/{job_id}", response_model=AIJobDefinition)
async def patch_job(job_id: str, patch: AIJobPatch, svc: SettingsService = Service) -> AIJobDefinition:
    return await svc.patch_job(job_id, patch)


@router.delete("/ai-jobs/{job_id}", status_code=204, response_class=Response)
async def delete_job(job_id: str, svc: SettingsService = Service) -> Response:
    await svc.delete_job(job_id)
    return Response(status_code=204)


# -- placeholders -----------------------------------------------------------


@router.get("/placeholders", response_model=list[Placeholder])
async def list_placeholders(svc: SettingsService = Service) -> list[Placeholder]:
    return svc.placeholders()
