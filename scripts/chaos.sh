#!/bin/bash
# Chaos injection script for the reliability platform
# Run load generator first: python3 scripts/load_generator.py --rps 20

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[CHAOS]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${AMBER}[WARN]${NC} $1"; }

usage() {
  echo "Usage: $0 "
  echo ""
  echo "Scenarios:"
  echo "  1  kill-api       Kill the Flask API container"
  echo "  2  kill-redis     Kill the Redis container"
  echo "  3  fill-disk      Fill /tmp inside the app container"
  echo "  4  slow-network   Add 200ms latency to app's network"
  echo "  5  traffic-spike  Ramp to 200 req/s for 60 seconds"
  echo ""
  echo "Recovery:"
  echo "  recover-api       Restart the Flask API"
  echo "  recover-redis     Restart Redis"
  echo "  recover-disk      Remove the disk fill file"
  echo "  recover-network   Remove network latency"
}

case "${1}" in

  # ── SCENARIO 1: Kill the API ──────────────────────────────
  kill-api | 1)
    log "SCENARIO 1: Killing Flask API container"
    log "Watch Prometheus targets: http://localhost:9090/targets"
    log "Watch Grafana error rate panel"
    echo ""
    KILL_TIME=$(date '+%H:%M:%S')
    log "Kill time: ${KILL_TIME} — record this for post-mortem timeline"
    docker compose stop app
    success "API stopped. ShortURLServiceDown should fire within 1 minute."
    warn "MTTD: watch Alertmanager at http://localhost:9093 for the alert."
    ;;

  recover-api)
    log "Recovering API..."
    START_TIME=$(date '+%H:%M:%S')
    docker compose start app
    sleep 5
    curl -sf http://localhost:8080/health > /dev/null && \
      success "API recovered at ${START_TIME}. Calculate MTTD and MTTR." || \
      warn "API not yet healthy. Wait 10 more seconds."
    ;;

  # ── SCENARIO 2: Kill Redis ─────────────────────────────────
  kill-redis | 2)
    log "SCENARIO 2: Killing Redis"
    log "Observe: cache miss rate should spike to 100%"
    log "Observe: latency should increase (all reads hit DB)"
    log "Observe: availability SLO should NOT be breached (graceful degradation)"
    docker compose stop redis
    success "Redis stopped. Watch cache hit ratio panel in Grafana."
    ;;

  recover-redis)
    docker compose start redis
    sleep 3
    success "Redis restarted. Cache hit ratio will recover as hot URLs are re-cached."
    ;;

  # ── SCENARIO 3: Fill disk ──────────────────────────────────
  fill-disk | 3)
    log "SCENARIO 3: Filling disk inside app container"
    log "Observe: DiskUsageHigh alert should fire when >80% full"
    docker compose exec app bash -c "dd if=/dev/zero of=/tmp/diskfill bs=1M count=500 2>&1 | tail -1"
    USED=$(docker compose exec app df /tmp | tail -1 | awk '{print $5}')
    success "Disk fill complete. Usage: ${USED}"
    warn "Check DiskUsageHigh alert in Alertmanager."
    ;;

  recover-disk)
    docker compose exec app rm -f /tmp/diskfill
    success "Disk fill removed. Alert should resolve within 10 minutes."
    ;;

  # ── SCENARIO 4: Network latency ───────────────────────────
  slow-network | 4)
    log "SCENARIO 4: Adding 200ms network latency to app container"
    log "Observe: p95 latency alert should fire"
    log "Observe: availability SLO should NOT be breached"
    docker compose exec -u root app bash -c "
      apt-get install -y iproute2 -qq 2>/dev/null
      tc qdisc add dev eth0 root netem delay 200ms 20ms
    " 2>/dev/null || \
    docker compose exec -u root app tc qdisc add dev eth0 root netem delay 200ms 20ms
    success "200ms latency injected. Watch p95 latency in Grafana."
    ;;

  recover-network)
    docker compose exec -u root app tc qdisc del dev eth0 root 2>/dev/null || true
    success "Network latency removed."
    ;;

  # ── SCENARIO 5: Traffic spike ──────────────────────────────
  traffic-spike | 5)
    log "SCENARIO 5: Sending traffic spike — ramping to 200 req/s for 60 seconds"
    log "Observe: error budget burn rate alert should fire"
    log "Observe: watch error rate, latency, and request rate panels"
    python3 "$(dirname "$0")/load_generator.py" --rps 200 --duration 60 &
    SPIKE_PID=$!
    success "Spike started (PID: ${SPIKE_PID}). Running for 60 seconds."
    ;;

  *)
    usage
    ;;
esac
