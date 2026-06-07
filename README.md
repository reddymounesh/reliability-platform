# Production Reliability Platform

A URL shortener with a complete SRE observability stack — built to demonstrate
reliability engineering practices: SLO-driven monitoring, automated alerting,
chaos engineering, and blameless post-mortems.

## Architecture

[paste your architecture diagram image here]
`app (Flask) ← nginx → prometheus → grafana → alertmanager`
Full stack: NGINX · Flask · PostgreSQL · Redis · Prometheus · Grafana · Alertmanager
+ Node/Redis/Postgres/Blackbox Exporters

## Quick start

```bash
git clone https://github.com/you/reliability-platform
cd reliability-platform
docker compose up --build -d    # starts all 12 containers
python3 scripts/load_generator.py --rps 20   # generate traffic
```

| Service       | URL                        | Credentials    |
|---------------|----------------------------|----------------|
| App (via NGINX)| http://localhost:8080      | —              |
| Prometheus    | http://localhost:9090      | —              |
| Grafana       | http://localhost:3000      | admin/admin123 |
| Alertmanager  | http://localhost:9093      | —              |

## SLOs defined

| SLO | Target | Error budget |
|-----|--------|--------------|
| Redirect availability | 99.9% success rate | 43.8 min/month |
| Redirect latency | p95 ≤ 200ms | per 5-minute window |
| Write availability | 99.5% success rate | per day |

See [docs/SLOs.md](docs/SLOs.md) for full definitions and error budget policy.

## Alert rules

6 alert rules covering: service availability, error rate (warning + critical),
p95 latency, Redis availability, disk usage, and error budget burn rate.
All alerts link to runbooks in [docs/runbooks/](docs/runbooks/).

## Chaos experiments run

| Scenario | SLO impact | MTTD | MTTR |
|----------|-----------|------|------|
| API container killed | Availability breached | ~62s | [your number] |
| Redis killed | Latency breached, availability held | ~90s | [your number] |
| Disk fill | Infrastructure alert fired | ~8min | Immediate |
| 200ms latency injected | Latency breached, 0% errors | ~5min | Immediate |
| 200 req/s spike | Error budget fast burn | ~5min | Auto-resolved |

Post-mortems: [2024-01 API down](docs/postmortems/2024-01-api-down.md)

## Key metrics tracked

- `shorturl_requests_total` — all requests by endpoint, method, status
- `shorturl_request_duration_seconds` — latency histogram by endpoint
- `shorturl_cache_hits_total` — Redis hit/miss ratio
- `shorturl_active_urls_total` — current URL count gauge

## What I learned

Building this project, I discovered that **latency SLOs catch what availability SLOs miss** —
demonstrated in Scenario 2 where Redis failure caused 0% error rate but violated the p95 SLO.
I also learned that inhibition rules in Alertmanager are essential for reducing alert noise:
when the service is completely down, downstream latency warnings are meaningless.
