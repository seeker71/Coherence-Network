# Spec: Sprint 0 — Graph foundation, indexer, basic API skeleton

## Purpose

This spec defines the initial sprint for setting up the Coherence Network's core infrastructure, including the Neo4j graph database foundation, data indexer for processing open source projects, and basic API skeleton to support future development. This sprint establishes the foundational components that will enable the network to map and analyze the open source ecosystem.

## Requirements

- [ ] Set up Neo4j graph database with appropriate schema for projects, contributors, and organizations
- [ ] Implement basic data indexer to process and load open source project data into the graph
- [ ] Create basic API skeleton with FastAPI framework and core routes for projects, contributors, and organizations
- [ ] Establish connection between API and Neo4j database
- [ ] Implement basic authentication and authorization framework
- [ ] Create initial Pydantic models for core data entities
- [ ] Set up database connection management and configuration
- [ ] Implement basic CRUD operations for projects in the API
- [ ] Configure project structure and development environment

## API Contract

### `GET /api/projects`

**Request**
- No parameters required

**Response 200**
```json
{
  "projects": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "created_at": "datetime",
      "updated_at": "datetime",
      "coherence_score": "float"
    }
  ],
  "total": "integer"
}
```

### `POST /api/projects`

**Request**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response 201**
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "coherence_score": "float"
}
```

### `GET /api/projects/{id}`

**Request**
- `id`: string (path)

**Response 200**
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "coherence_score": "float"
}
```

**Response 404**
```json
{ "detail": "Not found" }
```

### `PUT /api/projects/{id}`

**Request**
- `id`: string (path)
```json
{
  "name": "string",
  "description": "string"
}
```

**Response 200**
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "coherence_score": "float"
}
```

### `DELETE /api/projects/{id}`

**Request**
- `id`: string (path)

**Response 200**
```json
{ "message": "Project deleted successfully" }
```

## Data Model

```yaml
Project:
  properties:
    id: { type: string }
    name: { type: string }
    description: { type: string }
    created_at: { type: datetime }
    updated_at: { type: datetime }
    coherence_score: { type: float }

Contributor:
  properties:
    id: { type: string }
    name: { type: string }
    email: { type: string }
    created_at: { type: datetime }

Organization:
  properties:
    id: { type: string }
    name: { type: string }
    description: { type: string }
    created_at: { type: datetime }
```

## Files to Create/Modify

- `api/main.py` — FastAPI application setup
- `api/database.py` — Neo4j connection and setup
- `api/models/project.py` — Project Pydantic model
- `api/models/contributor.py` — Contributor Pydantic model
- `api/models/organization.py` — Organization Pydantic model
- `api/routers/projects.py` — Project routes
- `api/routers/contributors.py` — Contributor routes
- `api/routers/organizations.py` — Organization routes
- `api/services/project_service.py` — Project business logic
- `api/services/contributor_service.py` — Contributor business logic
- `api/services/organization_service.py` — Organization business logic
- `api/indexer/__init__.py` — Indexer package
- `api/indexer/project_indexer.py` — Project indexer
- `api/auth.py` — Authentication and authorization framework
- `api/config.py` — Configuration management
- `requirements.txt` — Dependencies including neo4j driver
- `Dockerfile` — Container setup for API
- `docker-compose.yml` — Multi-container setup including Neo4j

## Acceptance Tests

1. [ ] Neo4j database connection is established successfully
2. [ ] API endpoints return appropriate HTTP status codes (200, 201, 404, etc.)
3. [ ] All API responses follow the specified Pydantic models
4. [ ] CRUD operations for projects work correctly through the API
5. [ ] Indexer can process and load basic project data into the graph
6. [ ] Authentication and authorization framework is properly configured
7. [ ] All routes are properly registered with the FastAPI application
8. [ ] Database connection management works correctly
9. [ ] Docker setup works for both API and Neo4j services
10. [ ] Project structure is correctly organized following the codebase conventions

## Out of Scope

- [ ] Advanced graph queries and analytics
- [ ] Full contributor and organization relationship mapping
- [ ] Complex coherence score calculations
- [ ] Web UI implementation
- [ ] Advanced authentication methods beyond basic setup
- [ ] Full test suite for all functionality (to be added in subsequent sprints)

## Decision Gates

- [ ] Approval required for Neo4j schema design before implementation
- [ ] Approval required for indexer data source selection and processing approach
- [ ] Approval required for API endpoint design and naming conventions
- [ ] Approval required for database connection and configuration approach