# Database Schemas

## PostgreSQL Tables

### contributors

```sql
CREATE TABLE contributors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  type VARCHAR(10) NOT NULL CHECK (type IN ('HUMAN', 'SYSTEM')),
  
  -- Human fields
  user_id VARCHAR(255),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255),
  wallet_address VARCHAR(66),
  
  -- System fields
  system_type VARCHAR(50),
  provider VARCHAR(100),
  
  -- Aggregates
  total_cost_contributed NUMERIC(20, 8) DEFAULT 0.0,
  total_value_earned NUMERIC(20, 8) DEFAULT 0.0,
  
  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_contributors_type ON contributors(type);
CREATE INDEX idx_contributors_email ON contributors(email);
```

### assets

```sql
CREATE TABLE assets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  type VARCHAR(50) NOT NULL CHECK (type IN ('CODE', 'MODEL', 'CONTENT', 'DATA')),
  
  name VARCHAR(255) NOT NULL,
  version VARCHAR(50) NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  storage_uri TEXT,
  
  -- Lineage
  creation_cost_total NUMERIC(20, 8) DEFAULT 0.0,
  contributor_count INTEGER DEFAULT 0,
  depth INTEGER DEFAULT 0,
  
  -- Value
  total_value_generated NUMERIC(20, 8) DEFAULT 0.0,
  total_value_distributed NUMERIC(20, 8) DEFAULT 0.0,
  
  status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  CONSTRAINT unique_asset_version UNIQUE (name, version)
);

CREATE INDEX idx_assets_type ON assets(type);
CREATE INDEX idx_assets_status ON assets(status);
```

### contribution_events_ledger

```sql
CREATE TABLE contribution_events_ledger (
  event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  contributor_id UUID NOT NULL REFERENCES contributors(id),
  asset_id UUID NOT NULL REFERENCES assets(id),
  
  event_sequence BIGSERIAL,
  event_type VARCHAR(50) NOT NULL,
  
  cost_amount NUMERIC(20, 8) NOT NULL CHECK (cost_amount >= 0),
  resonance_data JSONB DEFAULT '{}'::jsonb,
  
  tool_profile_id UUID,
  triggered_by_contributor_id UUID REFERENCES contributors(id),
  
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_hash VARCHAR(64) NOT NULL,
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_events_asset ON contribution_events_ledger(asset_id, event_sequence);
CREATE INDEX idx_events_contributor ON contribution_events_ledger(contributor_id);
```

## Neo4j Graph Schema

### Nodes

```cypher
// Contributor Node
CREATE (c:Contributor {
  id: "uuid",
  type: "HUMAN",
  name: "seeker71",
  total_cost_contributed: 2413.19,
  total_value_earned: 0.0
})

// Asset Node  
CREATE (a:Asset {
  id: "uuid",
  name: "Coherence-Network",
  version: "1.0.0",
  creation_cost_total: 2413.19,
  contributor_count: 1
})
```

### Relationships

```cypher
// CONTRIBUTED_TO relationship
CREATE (c:Contributor)-[:CONTRIBUTED_TO {
  event_id: "uuid",
  cost_amount: 2413.19,
  coherence_score: 0.92,
  weight: 1.0,
  timestamp: datetime()
}]->(a:Asset)
```

### Common Queries

```cypher
// Get asset lineage
MATCH path = (c:Contributor)-[:CONTRIBUTED_TO*]->(a:Asset {id: $asset_id})
RETURN c, relationships(path), 
       reduce(cost = 0, r in relationships(path) | cost + r.cost_amount) as total

// Find top contributors
MATCH (c:Contributor)-[r:CONTRIBUTED_TO]->(a:Asset)
RETURN c.name, sum(r.cost_amount) as total_cost, count(a) as assets_count
ORDER BY total_cost DESC
LIMIT 10
```

## Sample Data

### seeker71's Initial Contribution

```sql
-- PostgreSQL
INSERT INTO contributors (id, type, name, email, wallet_address)
VALUES ('uuid-seeker71', 'HUMAN', 'seeker71', 'seeker71@example.com', '0x...');

INSERT INTO assets (id, type, name, version, content_hash)
VALUES ('uuid-ccn', 'CODE', 'Coherence-Network', '0.1.0', 'sha256:...');

INSERT INTO contribution_events_ledger 
(event_id, contributor_id, asset_id, event_type, cost_amount, resonance_data)
VALUES 
('uuid-event1', 'uuid-seeker71', 'uuid-ccn', 'PROJECT_INCEPTION', 2413.19,
 '{"code_quality_score": 0.85, "architecture_alignment": 1.0, "coherence_score": 0.92}'::jsonb);
```

```cypher
// Neo4j
CREATE (seeker:Contributor {id: 'uuid-seeker71', name: 'seeker71'})
CREATE (ccn:Asset {id: 'uuid-ccn', name: 'Coherence-Network'})
CREATE (seeker)-[:CONTRIBUTED_TO {
  event_id: 'uuid-event1',
  cost_amount: 2413.19,
  coherence_score: 0.92
}]->(ccn)
```
