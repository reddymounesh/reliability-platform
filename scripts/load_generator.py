"""
Load generator — creates realistic traffic patterns for the URL shortener.
Run this during chaos experiments to see metrics change in real time.

Usage:
  python3 load_generator.py               # 10 req/s, runs forever
  python3 load_generator.py --rps 50      # 50 req/s
  python3 load_generator.py --rps 5 --duration 60  # 5 req/s for 60 seconds
"""
import argparse
import random
import time
import requests
import threading
import signal
import sys
from datetime import datetime

BASE_URL = "http://localhost:8080"

# URLs to shorten — we pre-seed some so redirects also work
SEED_URLS = [
    "https://nutanix.com",
    "https://prometheus.io",
    "https://grafana.com",
    "https://kubernetes.io",
    "https://python.org",
    "https://github.com",
    "https://linux.org",
]

# Will be populated after seeding
short_codes = []

# Stats
stats = {"total": 0, "ok": 0, "errors": 0, "start": time.time()}
running = True


def seed_urls():
    """Create some URLs upfront so we have short_codes to redirect."""
    print("Seeding URLs...", flush=True)
    for url in SEED_URLS:
        try:
            r = requests.post(
                f"{BASE_URL}/shorten",
                json={"url": url},
                timeout=5
            )
            if r.status_code == 201:
                code = r.json().get("short_code")
                if code:
                    short_codes.append(code)
                    print(f"  Seeded: {url[:40]} → {code}", flush=True)
        except Exception as e:
            print(f"  Seed failed for {url}: {e}", flush=True)
    print(f"Seeded {len(short_codes)} URLs\n", flush=True)


def make_request():
    """Make one request. 70% redirects, 20% shortens, 10% invalid."""
    roll = random.random()

    try:
        if roll < 0.70 and short_codes:
            # Redirect request — the hot path
            code = random.choice(short_codes)
            r = requests.get(
                f"{BASE_URL}/r/{code}",
                timeout=5,
                allow_redirects=False   # don't follow the redirect
            )

        elif roll < 0.90:
            # Shorten a new URL
            url = f"https://example.com/page/{random.randint(1, 10000)}"
            r = requests.post(
                f"{BASE_URL}/shorten",
                json={"url": url},
                timeout=5
            )
            if r.status_code == 201:
                code = r.json().get("short_code")
                if code and code not in short_codes:
                    short_codes.append(code)

        else:
            # Invalid request — generates 404s and 400s
            r = requests.get(
                f"{BASE_URL}/r/invalid_code_xyz",
                timeout=5
            )

        stats["total"] += 1
        if r.status_code < 500:
            stats["ok"] += 1
        else:
            stats["errors"] += 1

    except requests.exceptions.ConnectionError:
        stats["total"] += 1
        stats["errors"] += 1
        print("  [CONNECTION ERROR] — service may be down", flush=True)
    except requests.exceptions.Timeout:
        stats["total"] += 1
        stats["errors"] += 1


def print_stats():
    """Print a stats summary every 10 seconds."""
    while running:
        time.sleep(10)
        elapsed = time.time() - stats["start"]
        rps = stats["total"] / max(elapsed, 1)
        error_pct = (stats["errors"] / max(stats["total"], 1)) * 100
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"Total: {stats['total']:,} | "
            f"RPS: {rps:.1f} | "
            f"Errors: {stats['errors']} ({error_pct:.1f}%)",
            flush=True
        )


def signal_handler(sig, frame):
    global running
    print("\nStopping load generator...", flush=True)
    running = False
    sys.exit(0)


def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="URL Shortener load generator")
    parser.add_argument("--rps",      type=int,   default=10,  help="Requests per second")
    parser.add_argument("--duration", type=float, default=0,   help="Duration in seconds (0=forever)")
    parser.add_argument("--base-url", type=str,   default=BASE_URL)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)

    
    BASE_URL = args.base_url

    print(f"Load Generator starting — {args.rps} req/s", flush=True)
    if args.duration:
        print(f"Running for {args.duration} seconds", flush=True)
    else:
        print("Running until Ctrl+C", flush=True)
    print()

    seed_urls()

    # Start stats printer in background
    threading.Thread(target=print_stats, daemon=True).start()

    interval = 1.0 / args.rps
    start = time.time()

    while running:
        if args.duration and (time.time() - start) > args.duration:
            break
        make_request()
        time.sleep(interval)

    print(f"\nDone. Total requests: {stats['total']}", flush=True)


if __name__ == "__main__":
    main()