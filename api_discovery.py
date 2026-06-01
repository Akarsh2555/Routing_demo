"""
API Discovery Script - Probe the EV Routing Model to understand schema & capabilities.
"""
import requests
import json
import time

BASE = "http://139.59.81.193"

# ── 1. Health check ──────────────────────────────────────────────
print("=" * 60)
print("1. HEALTH CHECK")
print("=" * 60)
r = requests.get(f"{BASE}/health", timeout=10)
print(f"   Status: {r.status_code}")
print(f"   Body:   {r.json()}")

# ── 2. Discover endpoints via OPTIONS & common paths ─────────────
print("\n" + "=" * 60)
print("2. ENDPOINT DISCOVERY")
print("=" * 60)

paths = [
    "/", "/api", "/api/calculate-ev-route", "/api/v1/routing/recommend",
    "/api/v1/routing", "/api/v1", "/api/chargers", "/api/stations",
    "/api/v1/chargers", "/api/v1/stations", "/api/v1/vehicles",
    "/api/v1/health", "/docs", "/redoc", "/openapi.json",
    "/api/v1/routing/route", "/api/route", "/api/ev-route",
    "/api/v1/routing/calculate", "/api/calculate",
]

for path in paths:
    for method in ["GET", "POST", "OPTIONS"]:
        try:
            r = requests.request(method, f"{BASE}{path}", timeout=5,
                                 json={} if method == "POST" else None)
            if r.status_code != 404:
                body_preview = r.text[:200] if r.text else "(empty)"
                print(f"   {method:7s} {path:45s} -> {r.status_code}  {body_preview}")
        except Exception as e:
            pass

# ── 3. Probe /api/calculate-ev-route schema iteratively ──────────
print("\n" + "=" * 60)
print("3. SCHEMA DISCOVERY: /api/calculate-ev-route")
print("=" * 60)

payloads = [
    ("empty", {}),
    ("coords only", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391}),
    ("+ vehicle_id", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "test"}),
    ("+ env empty", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "test", "environment": {}}),
    ("+ vs empty", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "test", "environment": {}, "vehicle_state": {}}),
    ("full minimal", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "test", "environment": {"temperature_c": 30}, "vehicle_state": {"soc": 80}}),
    ("full nexon", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "tata_nexon_ev", "environment": {"temperature_c": 30}, "vehicle_state": {"soc": 80}}),
    ("soc_pct", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "tata_nexon_ev", "environment": {"temperature_c": 30}, "vehicle_state": {"soc_pct": 80}}),
    ("soc as float", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "tata_nexon_ev", "environment": {"temperature_c": 30}, "vehicle_state": {"soc": 0.8}}),
    ("big env", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391, "vehicle_id": "tata_nexon_ev",
                 "environment": {"temperature_c": 30, "ac_on": True, "elevation_m": 220, "wind_speed_kmh": 10, "humidity_pct": 60},
                 "vehicle_state": {"soc": 0.8, "battery_capacity_kwh": 40.5, "max_range_km": 312}}),
]

for label, payload in payloads:
    try:
        t0 = time.time()
        r = requests.post(f"{BASE}/api/calculate-ev-route", json=payload, timeout=30)
        elapsed = time.time() - t0
        body = r.text[:300]
        print(f"   [{label:20s}] -> {r.status_code} ({elapsed:.2f}s)  {body}")
    except Exception as e:
        print(f"   [{label:20s}] -> EXCEPTION: {e}")

# ── 4. Probe /api/v1/routing/recommend schema ────────────────────
print("\n" + "=" * 60)
print("4. SCHEMA DISCOVERY: /api/v1/routing/recommend")
print("=" * 60)

recommend_payloads = [
    ("empty", {}),
    ("start/end nested", {"start": {"lat": 28.6139, "lon": 77.209}, "end": {"lat": 28.5355, "lon": 77.391}}),
    ("start/end + vid", {"start": {"lat": 28.6139, "lon": 77.209}, "end": {"lat": 28.5355, "lon": 77.391}, "vehicle_id": "test"}),
    ("full nested", {"start": {"lat": 28.6139, "lon": 77.209}, "end": {"lat": 28.5355, "lon": 77.391},
                     "vehicle_id": "tata_nexon_ev", "environment": {"temperature_c": 30},
                     "vehicle_state": {"soc": 0.8, "battery_capacity_kwh": 40.5}}),
    ("origin/dest", {"origin": {"lat": 28.6139, "lon": 77.209}, "destination": {"lat": 28.5355, "lon": 77.391},
                     "vehicle_id": "test"}),
    ("flat coords", {"start_lat": 28.6139, "start_lon": 77.209, "end_lat": 28.5355, "end_lon": 77.391,
                     "vehicle_id": "test", "environment": {}, "vehicle_state": {}}),
]

for label, payload in recommend_payloads:
    try:
        t0 = time.time()
        r = requests.post(f"{BASE}/api/v1/routing/recommend", json=payload, timeout=30)
        elapsed = time.time() - t0
        body = r.text[:300]
        print(f"   [{label:20s}] -> {r.status_code} ({elapsed:.2f}s)  {body}")
    except Exception as e:
        print(f"   [{label:20s}] -> EXCEPTION: {e}")

print("\n" + "=" * 60)
print("DISCOVERY COMPLETE")
print("=" * 60)
