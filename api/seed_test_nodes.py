from app.services import graph_service
from app.services.unified_db import session

with session() as s:
    # These might already exist if I am using a persistent DB, 
    # but in-memory means I need them.
    graph_service.create_node(id="idea_001", type="idea", name="Edge Navigation")
    graph_service.create_node(id="concept_resonance", type="concept", name="Resonance")
    print("Seeded idea_001 and concept_resonance")
