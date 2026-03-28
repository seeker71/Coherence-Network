#!/usr/bin/env bash
# Optional: verify a Python file with DIF (Merly). Usage: bash scripts/dif_verify_file.sh api/app/routers/discovery.py
set -euo pipefail
FILE="${1:?file path}"
CODE=$(python3 -c "import json,sys; print(json.dumps(open(sys.argv[1],encoding='utf-8').read()))" "$FILE")
curl -s -X POST https://dif.merly.ai/api/v2/dif/verify \
  -H 'Content-Type: application/json' \
  -d "{\"language\": \"python\", \"code\": $CODE}"
