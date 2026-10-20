from __future__ import annotations

from app.routers.kernel_shared import (
    router,
)

# Importing the family modules registers their routes on the shared router.
from app.routers import (  # noqa: F401  (imported for decorator side effects)
    kernel_breath,
    kernel_grounded_cv,
    kernel_grounding,
    kernel_matching,
    kernel_nodeid,
    kernel_scoring,
)
