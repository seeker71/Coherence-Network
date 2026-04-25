"""Task execution provider routes."""

from fastapi import APIRouter

from app.models.agent import TaskExecutionProvider, TaskExecutionProviderList
from app.services import agent_service

router = APIRouter()


@router.get("/providers", response_model=TaskExecutionProviderList, summary="Get Providers")
async def get_providers() -> TaskExecutionProviderList:
    providers = agent_service.list_available_task_execution_providers()
    return TaskExecutionProviderList(
        providers=[TaskExecutionProvider(id=provider) for provider in providers]
    )
