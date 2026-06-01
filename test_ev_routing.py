"""
Comprehensive EV Routing Model - Efficiency & Accuracy Test Suite
Tests: /api/v1/routing/recommend, /api/v1/routing/plan, /api/v1/routing/simulate
Vehicle: Mahindra Electric BE 6 (IN-2025-0007)
"""
import requests, json, time, math, sys, os
from datetime import datetime

BASE = "http://139.59.81.193"
VEHICLE = "IN-2025-0007"
RESULTS = []  # collect all results for final report

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def post(endpoint, payload, timeout=120):
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}{endpoint}", json=payload, timeout=timeout)
        ms = int((time.time()-t0)*1000)
        try:    return r.status_code, r.json(), ms
        except: return r.status_code, r.text[:500], ms
    except Exception as e:
        return -1, str(e)[:300], int((time.time()-t0)*1000)

def section(title):
    print(f"\n{'='*100}\n{title}\n{'='*100}")

# ============================================================
# 1. HEALTH CHECK
# ============================================================
section("1. HEALTH CHECK")
r = requests.get(f"{BASE}/health", timeout=10)
h = r.json()
print(f"  Status: {r.status_code}")
print(f"  Node: {h['checks']['node']}  |  Python: {h['checks']['python']}  |  Runtime: {h['checks']['runtime']}  |  Valhalla: {h['checks']['valhalla']}")

# ============================================================
# 2. RECOMMEND ENDPOINT - Core Route Tests (Delhi pairs)
# ============================================================
section("2. ROUTE ACCURACY - /api/v1/routing/recommend")

def make_recommend_payload(slat, slon, elat, elon, soc=0.8, prot=0.15, temp=25.0,
                           radius=25.0, limit=5, compat=True, charger_routes=False):
    return {
        "vehicle_id": VEHICLE,
        "start": {"lat": slat, "lon": slon},
        "end": {"lat": elat, "lon": elon},
        "environment": {"ambient_temp_c": temp},
        "vehicle_state": {"starting_soc": soc, "protection_soc": prot},
        "charger_radius_km": radius,
        "charger_limit": limit,
        "compatible_only": compat,
        "include_charger_routes": charger_routes,
    }

delhi_routes = [
    # (name, start_lat, start_lon, end_lat, end_lon, approx_road_km)
    ("Dwarka -> Saket (med)",           28.5921, 77.0460, 28.5244, 77.2066, 22),
    ("India Gate -> Qutub Minar",       28.6129, 77.2295, 28.5244, 77.1855, 16),
    ("CP -> IGI Airport T3",            28.6315, 77.2167, 28.5562, 77.1000, 18),
    ("Red Fort -> Lotus Temple",        28.6562, 77.2410, 28.5535, 77.2588, 14),
    ("Rohini -> Greater Kailash",       28.7158, 77.1221, 28.5425, 77.2426, 25),
    ("Dwarka -> Noida Sec 18 (long)",   28.5921, 77.0460, 28.5706, 77.3219, 38),
    ("Narela -> Mehrauli (cross-city)", 28.8524, 77.0928, 28.5110, 77.1780, 42),
    ("Short: CP circle",               28.6315, 77.2167, 28.6350, 77.2200, 1),
]

print(f"  {'Route':<40s} | {'St':>4s} | {'ms':>7s} | {'Edges':>5s} | {'Final SOC':>9s} | {'SOC Drop':>8s} | {'Energy':>8s} | {'Depletion':>10s} | {'Chargers':>8s}")
print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*7}-+-{'-'*5}-+-{'-'*9}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}-+-{'-'*8}")

for name, slat, slon, elat, elon, approx_km in delhi_routes:
    payload = make_recommend_payload(slat, slon, elat, elon)
    status, body, ms = post("/api/v1/routing/recommend", payload)

    if status == 200 and isinstance(body, dict):
        sim = body.get("simulation", {})
        edges = len(body.get("primary_route_edges", []))
        final_soc = sim.get("final_soc")
        soc_drop = (0.8 - final_soc) * 100 if final_soc else None
        energy = sim.get("energy_kwh", sim.get("total_energy_kwh", "?"))
        depl = sim.get("depletion_coordinate")
        depl_str = f"({depl['lat']:.4f},{depl['lon']:.4f})" if depl else "none"
        chargers = len(body.get("recommended_chargers", []))

        final_str = f"{final_soc*100:.2f}%" if final_soc else "?"
        drop_str = f"{soc_drop:.2f}pp" if soc_drop is not None else "?"
        energy_str = f"{energy:.3f}kWh" if isinstance(energy, (int,float)) else str(energy)

        print(f"  {name:<40s} | {status:>4d} | {ms:>6d}ms | {edges:>5d} | {final_str:>9s} | {drop_str:>8s} | {energy_str:>8s} | {depl_str:>10s} | {chargers:>8d}")
        RESULTS.append({"test": name, "status": status, "ms": ms, "edges": edges,
                        "final_soc": final_soc, "soc_drop_pp": soc_drop, "chargers": chargers,
                        "depletion": depl_str, "endpoint": "recommend"})
    else:
        body_str = json.dumps(body)[:150] if isinstance(body, (dict,list)) else str(body)[:150]
        print(f"  {name:<40s} | {status:>4d} | {ms:>6d}ms | {body_str}")
        RESULTS.append({"test": name, "status": status, "ms": ms, "error": body_str, "endpoint": "recommend"})

# ============================================================
# 3. SOC SENSITIVITY - Same route, different starting SOC
# ============================================================
section("3. SOC SENSITIVITY - Dwarka->Saket at different SOC levels")
print(f"  {'SOC Start':>10s} | {'St':>4s} | {'ms':>7s} | {'Final SOC':>9s} | {'SOC Drop':>8s} | {'Depleted?':>10s}")
print(f"  {'-'*10}-+-{'-'*4}-+-{'-'*7}-+-{'-'*9}-+-{'-'*8}-+-{'-'*10}")

for soc in [1.0, 0.8, 0.5, 0.3, 0.2, 0.16, 0.10]:
    payload = make_recommend_payload(28.5921, 77.0460, 28.5244, 77.2066, soc=soc)
    status, body, ms = post("/api/v1/routing/recommend", payload)
    if status == 200 and isinstance(body, dict):
        sim = body.get("simulation", {})
        fs = sim.get("final_soc")
        drop = (soc - fs)*100 if fs else None
        depl = "YES" if sim.get("depletion_coordinate") else "no"
        print(f"  {soc*100:>9.0f}% | {status:>4d} | {ms:>6d}ms | {fs*100:.2f}% | {drop:.2f}pp | {depl:>10s}" if fs else
              f"  {soc*100:>9.0f}% | {status:>4d} | {ms:>6d}ms | {'?':>9s} | {'?':>8s} | {'?':>10s}")
    else:
        print(f"  {soc*100:>9.0f}% | {status:>4d} | {ms:>6d}ms | ERROR")

# ============================================================
# 4. TEMPERATURE SENSITIVITY - Same route, different ambient temps
# ============================================================
section("4. TEMPERATURE SENSITIVITY - Dwarka->Saket at different temps")
print(f"  {'Temp':>6s} | {'St':>4s} | {'ms':>7s} | {'Final SOC':>9s} | {'SOC Drop':>8s} | Thermal effect")
print(f"  {'-'*6}-+-{'-'*4}-+-{'-'*7}-+-{'-'*9}-+-{'-'*8}-+-{'-'*20}")

for temp in [-10, 0, 10, 25, 35, 45]:
    payload = make_recommend_payload(28.5921, 77.0460, 28.5244, 77.2066, temp=temp)
    status, body, ms = post("/api/v1/routing/recommend", payload)
    if status == 200 and isinstance(body, dict):
        sim = body.get("simulation", {})
        fs = sim.get("final_soc")
        drop = (0.8 - fs)*100 if fs else None
        note = "baseline" if temp == 25 else ("cold penalty" if temp < 25 else "hot/nominal")
        print(f"  {temp:>5d}C | {status:>4d} | {ms:>6d}ms | {fs*100:.2f}% | {drop:.2f}pp | {note}" if fs else
              f"  {temp:>5d}C | {status:>4d} | {ms:>6d}ms | ERROR")
    else:
        print(f"  {temp:>5d}C | {status:>4d} | {ms:>6d}ms | ERROR")

# ============================================================
# 5. MULTI-STOP PLANNER - /api/v1/routing/plan
# ============================================================
section("5. MULTI-STOP PLANNER - /api/v1/routing/plan")

plan_tests = [
    ("Normal (80% SOC, short)", {
        "vehicle_id": VEHICLE,
        "start": {"lat": 28.5921, "lon": 77.0460},
        "end": {"lat": 28.5244, "lon": 77.2066},
        "vehicle_state": {"starting_soc": 0.8, "protection_soc": 0.15},
        "target_soc_after_charge": 0.7,
        "max_charging_stops": 3,
        "charger_radius_km": 25,
        "charger_limit": 5,
        "fallback_charger_power_kw": 22,
        "include_leg_edges": False,
    }),
    ("Low SOC (20%) cross-city", {
        "vehicle_id": VEHICLE,
        "start": {"lat": 28.7158, "lon": 77.1221},
        "end": {"lat": 28.5244, "lon": 77.2066},
        "vehicle_state": {"starting_soc": 0.20, "protection_soc": 0.15},
        "target_soc_after_charge": 0.7,
        "max_charging_stops": 3,
        "charger_radius_km": 25,
        "charger_limit": 5,
        "fallback_charger_power_kw": 22,
        "include_leg_edges": False,
    }),
    ("Long route Narela->Mehrauli", {
        "vehicle_id": VEHICLE,
        "start": {"lat": 28.8524, "lon": 77.0928},
        "end": {"lat": 28.5110, "lon": 77.1780},
        "vehicle_state": {"starting_soc": 0.8, "protection_soc": 0.15},
        "target_soc_after_charge": 0.7,
        "max_charging_stops": 3,
        "charger_radius_km": 25,
        "charger_limit": 5,
        "fallback_charger_power_kw": 22,
        "include_leg_edges": False,
    }),
]

for label, payload in plan_tests:
    status, body, ms = post("/api/v1/routing/plan", payload)
    if status == 200 and isinstance(body, dict):
        plan_status = body.get("status", "?")
        steps = body.get("plan_steps", [])
        drive_steps = [s for s in steps if s.get("step_type") == "drive"]
        charge_steps = [s for s in steps if s.get("step_type") == "charge"]
        final_soc = body.get("final_soc")
        total_dist = body.get("total_distance_m", 0)
        total_charge = body.get("total_estimated_charge_minutes", 0)
        print(f"  [{label}]")
        print(f"    Status: {plan_status} | {ms}ms | Final SOC: {final_soc*100:.1f}%" if final_soc else f"    Status: {plan_status} | {ms}ms")
        print(f"    Drive legs: {len(drive_steps)} | Charge stops: {len(charge_steps)} | Dist: {total_dist/1000:.1f}km | Charge time: {total_charge:.0f}min")
        for i, step in enumerate(steps):
            if step["step_type"] == "charge":
                print(f"    -> Charge @ {step.get('station_name','?')}: {step.get('arrival_soc',0)*100:.1f}% -> {step.get('departure_soc',0)*100:.1f}% ({step.get('estimated_charge_minutes',0):.0f}min)")
    else:
        body_str = json.dumps(body)[:200] if isinstance(body, (dict,list)) else str(body)[:200]
        print(f"  [{label}] -> {status} | {ms}ms | {body_str}")

# ============================================================
# 6. CHARGER CONFIDENCE - /api/v1/confidence endpoints
# ============================================================
section("6. CHARGER CONFIDENCE ENDPOINTS")

# Nearby chargers
for ep_label, method, url, kwargs in [
    ("Nearby chargers (CP area)", "GET", f"{BASE}/api/v1/confidence/nearby",
     {"params": {"lat": 28.6315, "lon": 77.2167, "radius_km": 15}}),
    ("Station 557560", "GET", f"{BASE}/api/v1/confidence/stations/557560", {}),
    ("Rank chargers", "POST", f"{BASE}/api/v1/confidence/rank",
     {"json": {"lat": 28.6315, "lon": 77.2167, "radius_km": 15, "compatible_only": True}}),
]:
    try:
        t0 = time.time()
        if method == "GET":
            r = requests.get(url, timeout=30, **kwargs)
        else:
            r = requests.request(method, url, timeout=30, **kwargs)
        ms = int((time.time()-t0)*1000)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                print(f"  {ep_label}: {r.status_code} | {ms}ms | {len(data)} items")
                for item in data[:3]:
                    name = item.get("station_name", item.get("name", "?"))
                    conf = item.get("confidence", {})
                    if isinstance(conf, dict):
                        print(f"    - {name}: confidence={conf.get('confidence','?')}, p_fail={conf.get('p_fail','?')}")
                    else:
                        print(f"    - {name}: confidence={conf}")
            elif isinstance(data, dict):
                print(f"  {ep_label}: {r.status_code} | {ms}ms | {json.dumps(data)[:200]}")
        else:
            print(f"  {ep_label}: {r.status_code} | {ms}ms | {r.text[:200]}")
    except Exception as e:
        print(f"  {ep_label}: ERROR | {str(e)[:150]}")

# ============================================================
# 7. INPUT VALIDATION & EDGE CASES
# ============================================================
section("7. INPUT VALIDATION & EDGE CASES")

validation_tests = [
    ("Missing vehicle_id", "/api/v1/routing/recommend",
     {"start":{"lat":28.6,"lon":77.2},"end":{"lat":28.5,"lon":77.3},
      "environment":{"ambient_temp_c":25},"vehicle_state":{"starting_soc":0.8,"protection_soc":0.15}}),
    ("Invalid vehicle_id", "/api/v1/routing/recommend",
     {"vehicle_id":"FAKE-9999","start":{"lat":28.6,"lon":77.2},"end":{"lat":28.5,"lon":77.3},
      "environment":{"ambient_temp_c":25},"vehicle_state":{"starting_soc":0.8,"protection_soc":0.15}}),
    ("Same start & end", "/api/v1/routing/recommend",
     make_recommend_payload(28.6139, 77.209, 28.6139, 77.209)),
    ("Ocean coordinates", "/api/v1/routing/recommend",
     make_recommend_payload(0.0, 0.0, 1.0, 1.0)),
    ("SOC = 0%", "/api/v1/routing/recommend",
     make_recommend_payload(28.5921, 77.046, 28.5244, 77.2066, soc=0.0)),
    ("SOC = 100%", "/api/v1/routing/recommend",
     make_recommend_payload(28.5921, 77.046, 28.5244, 77.2066, soc=1.0)),
    ("Extreme cold -25C", "/api/v1/routing/recommend",
     make_recommend_payload(28.5921, 77.046, 28.5244, 77.2066, temp=-25.0)),
    ("Extreme hot 50C", "/api/v1/routing/recommend",
     make_recommend_payload(28.5921, 77.046, 28.5244, 77.2066, temp=50.0)),
]

for label, ep, payload in validation_tests:
    status, body, ms = post(ep, payload, timeout=30)
    body_str = json.dumps(body)[:150] if isinstance(body, (dict,list)) else str(body)[:150]
    print(f"  {label:<25s} | {status:>4d} | {ms:>6d}ms | {body_str}")

# ============================================================
# 8. PERFORMANCE / LATENCY BENCHMARKS
# ============================================================
section("8. PERFORMANCE BENCHMARKS")

# Health endpoint baseline
health_times = []
for _ in range(10):
    t0 = time.time()
    requests.get(f"{BASE}/health", timeout=10)
    health_times.append((time.time()-t0)*1000)
print(f"  Health (10x): avg={sum(health_times)/len(health_times):.0f}ms  min={min(health_times):.0f}ms  max={max(health_times):.0f}ms  p95={sorted(health_times)[8]:.0f}ms")

# Route recommendation latency (same route 5x)
rec_times = []
for _ in range(5):
    payload = make_recommend_payload(28.5921, 77.046, 28.5244, 77.2066)
    _, _, ms = post("/api/v1/routing/recommend", payload)
    rec_times.append(ms)
if rec_times:
    print(f"  Recommend (5x): avg={sum(rec_times)/len(rec_times):.0f}ms  min={min(rec_times)}ms  max={max(rec_times)}ms")

# Concurrent test (3 simultaneous requests)
import concurrent.futures
def fire_request(idx):
    routes = [(28.6129,77.2295,28.5244,77.1855),(28.6315,77.2167,28.5562,77.1),(28.5921,77.046,28.5244,77.2066)]
    slat,slon,elat,elon = routes[idx % len(routes)]
    return post("/api/v1/routing/recommend", make_recommend_payload(slat,slon,elat,elon))

t_conc = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    futures = [ex.submit(fire_request, i) for i in range(3)]
    conc_results = [f.result() for f in futures]
conc_total = int((time.time()-t_conc)*1000)
conc_statuses = [r[0] for r in conc_results]
conc_times = [r[2] for r in conc_results]
print(f"  Concurrent (3x): total={conc_total}ms  individual={conc_times}  statuses={conc_statuses}")

# ============================================================
# 9. ROUTE PHYSICS SANITY CHECKS
# ============================================================
section("9. ROUTE PHYSICS SANITY CHECKS")

# Get a detailed response to validate physics
payload = make_recommend_payload(28.5921, 77.046, 28.5244, 77.2066, charger_routes=True)
status, body, ms = post("/api/v1/routing/recommend", payload)

if status == 200 and isinstance(body, dict):
    edges = body.get("primary_route_edges", [])
    sim = body.get("simulation", {})
    chargers = body.get("recommended_chargers", [])
    anchor = body.get("charger_search_anchor", {})

    # Route edge analysis
    if edges:
        total_dist = sum(e.get("distance_m", 0) for e in edges)
        speeds = [e.get("speed_kph", 0) for e in edges if e.get("speed_kph", 0) > 0]
        grades = [e.get("grade_pct", 0) for e in edges if "grade_pct" in e]
        start_coord = edges[0].get("start_coordinate", {})
        end_coord = edges[-1].get("end_coordinate", {})
        straight_km = haversine_km(28.5921, 77.046, 28.5244, 77.2066)
        detour_ratio = (total_dist/1000) / straight_km if straight_km > 0 else 0

        print(f"  Route edges: {len(edges)}")
        print(f"  Total distance: {total_dist/1000:.2f} km (straight-line: {straight_km:.2f} km, detour ratio: {detour_ratio:.2f}x)")
        print(f"  Speed range: {min(speeds):.1f} - {max(speeds):.1f} km/h (avg: {sum(speeds)/len(speeds):.1f})" if speeds else "  No speed data")
        print(f"  Grade range: {min(grades):.2f}% - {max(grades):.2f}% (avg: {sum(grades)/len(grades):.3f}%)" if grades else "  No grade data")
        print(f"  Route start: ({start_coord.get('lat','?')}, {start_coord.get('lon','?')})")
        print(f"  Route end:   ({end_coord.get('lat','?')}, {end_coord.get('lon','?')})")

        # Physics check: detour ratio should be 1.0-2.0 for urban routes
        if 1.0 <= detour_ratio <= 2.5:
            print(f"  [PASS] Detour ratio {detour_ratio:.2f}x is reasonable for urban routing")
        else:
            print(f"  [WARN] Detour ratio {detour_ratio:.2f}x seems unusual")

    # Simulation checks
    final_soc = sim.get("final_soc")
    if final_soc is not None:
        soc_drop = 0.8 - final_soc
        print(f"\n  Simulation: final_soc={final_soc*100:.2f}%, drop={soc_drop*100:.2f}pp")
        print(f"  Status: {sim.get('status', '?')}")

        # Sanity: for ~22km Delhi route, energy ~2-5 kWh, SOC drop ~3-10%
        if 0.005 <= soc_drop <= 0.15:
            print(f"  [PASS] SOC drop {soc_drop*100:.2f}pp is physically plausible for ~22km urban route")
        else:
            print(f"  [WARN] SOC drop {soc_drop*100:.2f}pp may be unusual for a ~22km route")

    # Charger analysis
    print(f"\n  Charger search anchor: {anchor.get('reason', '?')} at {anchor.get('coordinate', '?')}")
    print(f"  Recommended chargers: {len(chargers)}")
    for c in chargers[:5]:
        print(f"    - {c.get('station_name','?')[:45]:45s} | dist={c.get('distance_from_anchor_km',0):.1f}km | "
              f"connectors={c.get('connector_types','?')} | "
              f"conf={c.get('confidence',{}).get('confidence','?')} | p_fail={c.get('confidence',{}).get('p_fail','?')} | "
              f"route={c.get('route_status','?')}")
else:
    body_str = json.dumps(body)[:300] if isinstance(body, (dict,list)) else str(body)[:300]
    print(f"  FAILED to get detailed response: {status} | {body_str}")

# ============================================================
# 10. SUMMARY
# ============================================================
section("10. FINAL SUMMARY")

total = len(RESULTS)
passed = sum(1 for r in RESULTS if r.get("status") == 200)
failed = total - passed
avg_ms = sum(r.get("ms", 0) for r in RESULTS) / total if total else 0

print(f"  Recommend endpoint tests: {total} total, {passed} passed, {failed} failed")
print(f"  Average response time: {avg_ms:.0f}ms")
if passed > 0:
    soc_drops = [r["soc_drop_pp"] for r in RESULTS if r.get("soc_drop_pp") is not None]
    if soc_drops:
        print(f"  SOC drop range: {min(soc_drops):.2f}pp - {max(soc_drops):.2f}pp")
    edge_counts = [r["edges"] for r in RESULTS if r.get("edges")]
    if edge_counts:
        print(f"  Edge count range: {min(edge_counts)} - {max(edge_counts)}")

# Save results to JSON
output_path = os.path.join(os.path.dirname(__file__), "test_results.json")
with open(output_path, "w") as f:
    json.dump({"timestamp": datetime.now().isoformat(), "results": RESULTS}, f, indent=2)
print(f"\n  Results saved to: {output_path}")
print(f"  Completed at: {datetime.now().isoformat()}")
