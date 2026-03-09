"""DB-backed telemetry persistence for automation usage and friction events.

Implementation lives in app.services.telemetry_persistence; this module re-exports
the public API so existing imports remain valid.
"""

from __future__ import annotations

from app.services.telemetry_persistence import (
    append_automation_snapshot,
    append_external_tool_usage_event,
    append_friction_event,
    append_task_metric,
    backend_info,
    checkpoint,
    database_url,
    get_meta_value,
    import_automation_snapshots_from_file,
    import_friction_events_from_file,
    import_task_metrics_from_file,
    list_automation_snapshots,
    list_external_tool_usage_events,
    list_friction_events,
    list_task_metrics,
    set_meta_value,
    ensure_schema,
)

__all__ = [
    "append_automation_snapshot",
    "append_external_tool_usage_event",
    "append_friction_event",
    "append_task_metric",
    "backend_info",
    "checkpoint",
    "database_url",
    "ensure_schema",
    "get_meta_value",
    "import_automation_snapshots_from_file",
    "import_friction_events_from_file",
    "import_task_metrics_from_file",
    "list_automation_snapshots",
    "list_external_tool_usage_events",
    "list_friction_events",
    "list_task_metrics",
    "set_meta_value",
]
