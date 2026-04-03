"""Content indexer service — auto-link nodes to repo files."""

from __future__ import annotations

import os
import hashlib
import logging
from app.services import spec_registry_service, idea_service

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def scan_and_index_specs() -> dict:
    """Scan the specs/ directory and link Spec nodes to their markdown files."""
    specs_dir = os.path.join(REPO_ROOT, "specs")
    if not os.path.exists(specs_dir):
        return {"indexed": 0, "errors": 1}

    # Fetch all registered specs
    specs = spec_registry_service.list_specs(limit=1000)
    
    indexed = 0
    # Map of spec_id (normalized) to full Spec model
    spec_map = {s.spec_id.lower(): s for s in specs}
    
    for filename in os.listdir(specs_dir):
        if not filename.endswith(".md"):
            continue
            
        # Strategy: find spec_id in filename (e.g. 169-procedural-memory.md -> 169)
        # Handle formats like '169-foo', 'spec-169', etc.
        parts = filename.split("-")
        potential_ids = [parts[0].lower()]
        if len(parts) > 1:
            potential_ids.append(f"spec-{parts[0].lower()}")
            
        found_spec = None
        for pid in potential_ids:
            if pid in spec_map:
                found_spec = spec_map[pid]
                break
        
        if found_spec:
            rel_path = f"specs/{filename}"
            full_path = os.path.join(specs_dir, filename)
            
            # Compute hash
            with open(full_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Update spec if path or hash changed
            if found_spec.content_path != rel_path or found_spec.content_hash != content_hash:
                from app.models.spec_registry import SpecRegistryUpdate
                spec_registry_service.update_spec(
                    found_spec.spec_id, 
                    SpecRegistryUpdate(content_path=rel_path, content_hash=content_hash)
                )
                indexed += 1
                
    return {"indexed": indexed, "total_scanned": len(specs)}
