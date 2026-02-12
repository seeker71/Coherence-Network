#!/usr/bin/env python3
"""Index npm packages into GraphStore from deps.dev — spec 019.

Usage:
  python scripts/index_npm.py [--limit N] [--packages a,b,c]
  python scripts/index_npm.py --limit 100   # index first 100 from default list
"""

import argparse
import logging
import os
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"))
except ImportError:
    pass

from app.adapters.graph_store import InMemoryGraphStore
from app.services.indexer_service import index_npm_packages

# Top npm packages by popularity (subset for CI/test; extend for 5K)
DEFAULT_PACKAGES = [
    "react", "lodash", "express", "axios", "moment", "chalk", "commander",
    "debug", "typescript", "webpack", "vue", "react-dom", "next", "jquery",
    "async", "uuid", "dotenv", "eslint", "prettier", "jest", "yargs",
    "prop-types", "body-parser", "cookie-parser", "cors", "morgan",
    "jsonwebtoken", "bcryptjs", "mongoose", "pg", "redis", "ioredis",
]

log = logging.getLogger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser(description="Index npm packages into GraphStore")
    ap.add_argument("--limit", type=int, default=None, help="Max packages to index")
    ap.add_argument(
        "--target",
        type=int,
        default=None,
        help="Grow graph until N projects (adds discovered deps to queue)",
    )
    ap.add_argument(
        "--packages",
        default=None,
        help="Comma-separated package names (default: built-in list)",
    )
    ap.add_argument(
        "--persist",
        default=None,
        help="Path to persist JSON (default: api/logs/graph_store.json)",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.packages:
        packages = [s.strip() for s in args.packages.split(",") if s.strip()]
    else:
        packages = DEFAULT_PACKAGES

    persist = args.persist or os.path.join(_api_dir, "logs", "graph_store.json")
    store = InMemoryGraphStore(persist_path=persist)

    n = index_npm_packages(
        store, packages, limit=args.limit, target=args.target
    )
    store.save()
    log.info("Indexed %d packages; total in store: %d", n, store.count_projects())
    print(f"Indexed {n} packages; total: {store.count_projects()}")


if __name__ == "__main__":
    main()
