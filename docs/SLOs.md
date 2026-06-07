# Service Level Objectives — URL Shortener

## SLI Definitions (what we measure)

| SLI | Measurement |
|-----|-------------|
| Availability | % of redirect requests that return non-5xx response |
| Latency      | p95 of redirect request duration in seconds |
| Write success| % of /shorten requests that return 201 |

## SLOs (what we commit to)

### SLO 1 — Redirect Availability
- **SLI**: `rate(shorturl_requests_total{endpoint="/r",status_code!~"5.."}[5m]) / rate(shorturl_requests_total{endpoint="/r"}[5m])`
- **Target**: 99.9% of redirect requests succeed over any 30-day window
- **Error budget**: 0.1% = 43.8 minutes per 30-day period
- **Rationale**: Redirect is the critical user-facing operation. Most traffic hits this endpoint.

### SLO 2 — Redirect Latency
- **SLI**: `histogram_quantile(0.95, rate(shorturl_request_duration_seconds_bucket{endpoint="/r"}[5m]))`
- **Target**: p95 latency ≤ 200ms over any 5-minute window
- **Rationale**: Slow redirects are a bad user experience even if technically successful.

### SLO 3 — Write Availability
- **SLI**: `rate(shorturl_requests_total{endpoint="/shorten",status_code="201"}[5m]) / rate(shorturl_requests_total{endpoint="/shorten"}[5m])`
- **Target**: 99.5% of shorten requests succeed per day
- **Rationale**: Write path is less critical than read path. Lower SLO reflects lower traffic.

## Error Budget Policy
- Budget > 50% remaining: no restrictions on deployments
- Budget 10–50% remaining: require extra testing before deploy
- Budget < 10% remaining: freeze all non-critical changes
- Budget exhausted: stop feature work, focus entirely on reliability