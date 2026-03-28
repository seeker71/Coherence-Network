"""Compatibility shim for smart_reaper_service — re-exports from smart_reap_service."""
from app.services.smart_reap_service import *  # noqa: F401,F403

# Re-export diagnose_batch if it exists, otherwise create a stub
try:
    from app.services.smart_reap_service import smart_reap_task as diagnose_batch  # noqa: F401
except ImportError:
    pass


def diagnose_batch(tasks, runners, *, log_dir=None, max_age_minutes=30, max_extensions=2, dry_run=False):
    """Diagnose and reap stuck tasks. Compatibility shim."""
    from app.services import smart_reap_service
    results = []
    for task in tasks:
        result = smart_reap_service.smart_reap_task(
            task,
            runners=runners,
            log_dir=log_dir,
            max_age_minutes=max_age_minutes,
            max_extensions=max_extensions,
            dry_run=dry_run,
        )
        results.append(result)
    return results
