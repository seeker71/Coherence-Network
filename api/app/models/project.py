"""Project models for graph/store — spec 008, 019."""

from pydantic import BaseModel


class Project(BaseModel):
    """Full project data for GET /api/projects/{ecosystem}/{name}."""

    name: str
    ecosystem: str
    version: str
    description: str
    dependency_count: int = 0


class ProjectSummary(BaseModel):
    """Summary for search results."""

    name: str
    ecosystem: str
    description: str
