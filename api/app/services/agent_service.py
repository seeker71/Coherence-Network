"""Agent orchestration: routing and task tracking.

This module is now a facade that imports and re-exports from specialized modules:
- agent_config: Configuration, routing, model selection
- task_store: In-memory store and CRUD operations
- task_analytics: Analytics, counts, summaries, usage
- pipeline_monitor: Pipeline status and attention flags
"""

# Configuration and routing
from app.services.agent_config import (
    AGENT_BY_TASK_TYPE,
    COMMAND_TEMPLATES,
    ROUTING,
)

# Task store operations
from app.services.task_store import (
    clear_store,
    create_task,
    get_task,
    list_tasks,
    update_task,
)

# Analytics and summaries
from app.services.task_analytics import (
    get_attention_tasks,
    get_review_summary,
    get_route,
    get_task_count,
    get_usage_summary,
)

# Pipeline monitoring
from app.services.pipeline_monitor import get_pipeline_status

__all__ = [
    # Configuration
    "ROUTING",
    "AGENT_BY_TASK_TYPE",
    "COMMAND_TEMPLATES",
    # Store operations
    "create_task",
    "get_task",
    "list_tasks",
    "update_task",
    "clear_store",
    # Analytics
    "get_attention_tasks",
    "get_task_count",
    "get_review_summary",
    "get_route",
    "get_usage_summary",
    # Monitoring
    "get_pipeline_status",
]
