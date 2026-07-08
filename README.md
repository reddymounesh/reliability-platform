# Reliability Platform v2

A production-style observability and resilience platform built around a URL shortener 
service — demonstrating SRE practices: connection pooling, structured logging with log 
aggregation, SLO-driven alerting, and tested backup/recovery procedures.

## Architecture

[Paste the full diagram from above as a code block or export as an image]

**14 containers**, one Docker network:
NGINX → Flask (pooled connections) → PostgreSQL + Redis
→ Prometheus (6 scrape targets) → Grafana + Alertmanager
→ Promtail → Loki (log aggregation)

## Quick Start

```bash
git clone https://github.com/YOURUSERNAME/reliability-platform
cd reliability-platform
docker compose up --build -d
python3 scripts/load_generator.py --rps 20
```

| Service | URL |
|---|---|
| App | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin123) |
| Alertmanager | http://localhost:9093 |
| Loki | http://localhost:3100 |

## Key Features (v2)

| Feature | Problem it Solves |
|---|---|
| Connection pooling (2-20 conns) | Fixed connection exhaustion observed at 300 req/s in v1 |
| Structured JSON logging + Loki | Added the "logs" pillar — v1 only had metrics |
| Automated backup + restore drill | Validated real Recovery Time Objective, not assumed |

## A Real Bug Found and Fixed During Development

While wiring up Alertmanager, alerts were firing correctly in Prometheus but never 
appearing in Alertmanager's UI. Debugging via `docker logs prometheus | grep alertmanager` 
revealed a DNS resolution failure: `dial tcp: lookup alert_manager: no such host`. 
The Prometheus config referenced `alert_manager` (underscore) while the actual Docker 
Compose service was named `alertmanager`. Fixed by aligning the two, confirmed via 
`curl localhost:9093/api/v2/alerts` returning the alert object instead of an empty array.

## Experiments Run

| # | Experiment | Result | MTTD/MTTR |
|---|---|---|---|
| 1 | Kill API container | Alert fired, service auto-restarted | [fill in] |
| 2 | Kill Redis | Availability held, latency SLO breached | [fill in] |
| 3 | Fill disk | Infrastructure alert fired at 80% | [fill in] |
| 4 | 200ms network latency injection | 0% errors, latency SLO breached | [fill in] |
| 5 | 300 req/s spike | Pool absorbed load, no connection errors | [fill in] |

## Dashboards

![RED Dashboard](docs/screenshots/red-dashboard.png)
![Cache Hit Ratio + Latency](docs/screenshots/redis-failure-comparison.png)
![Alertmanager Firing](docs/screenshots/alertmanager-firing.png)

## Repository Structure

```
reliability-platform/
├── app/                    # Flask app, pooling, circuit breaker, structured logging
├── monitoring/             # Prometheus, Alertmanager, Loki configs
├── scripts/                # Load generator, chaos injection, backup
├── backups/                # pg_dump output (gitignored, structure only)
└── docs/
    ├── evidence/           # Raw test output
    ├── screenshots/        # Grafana/Alertmanager proof
    ├── observations/       # Per-experiment analysis
    └── postmortems/        # Blameless post-mortems
```
