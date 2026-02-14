# Coherence Network Automation

Automation now targets managed hosting and avoids VM-specific provisioning.

## Hosting baseline

- API: Railway
- Web: Vercel
- PostgreSQL: Neon/Supabase
- Neo4j: AuraDB Free
- Optional DNS/WAF: Cloudflare

## What this changes

- No SSH-based host setup flows.
- No VM firewall or key management steps.
- Deployment verification focuses on public endpoints and service health.

## Verify deployed stack

```bash
./verify_deployment.sh
```

Set optional env vars to validate your live URLs:

```bash
export API_BASE_URL="https://<api-domain>"
export WEB_BASE_URL="https://<web-domain>"
./verify_deployment.sh
```

## Continuous checks

```bash
cd api && pytest -v --ignore=tests/holdout
```

## Notes

Legacy VM-oriented deployment paths were intentionally removed to keep operations simple and reproducible on managed services.
