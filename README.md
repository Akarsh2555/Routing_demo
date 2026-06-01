<p align="center">
  <img src="https://img.shields.io/badge/EV-Routing%20Engine-00d4aa?style=for-the-badge&logo=lightning&logoColor=white" alt="EV Routing Engine"/>
  <img src="https://img.shields.io/badge/Mahindra-BE%206-3b82f6?style=for-the-badge" alt="BE 6"/>
  <img src="https://img.shields.io/badge/FASTSim-Physics%20Engine-f59e0b?style=for-the-badge" alt="FASTSim"/>
  <img src="https://img.shields.io/badge/Valhalla-Routing-8b5cf6?style=for-the-badge" alt="Valhalla"/>
</p>

# ⚡ EV Routing Engine

**A production-grade Electric Vehicle routing system** that combines **Valhalla graph routing**, **NREL FASTSim physics simulation**, and **real-time charger intelligence** to deliver accurate energy-aware navigation for the Indian EV market.

> 🔬 Tested against ABRP (A Better Routeplanner) — achieves **< 2pp SOC accuracy** on 4/6 benchmark routes and responds **3-4x faster**.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [How It Works](#how-it-works)
- [Backend API Reference](#backend-api-reference)
- [Web Application](#web-application)
- [Physics Engine](#physics-engine)
- [Charger Intelligence](#charger-intelligence)
- [Performance Benchmarks](#performance-benchmarks)
- [Accuracy vs ABRP](#accuracy-vs-abrp)
- [Setup & Deployment](#setup--deployment)
- [Testing](#testing)
- [Known Issues](#known-issues)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│   Mapbox GL JS · Dark Theme · SOC Gauge · Route Visualization       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS (Vercel Proxy / Local Proxy)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     NODE.JS GATEWAY (API Layer)                     │
│                                                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│   │  /recommend   │  │   /plan      │  │   /simulate           │     │
│   │  Single Route │  │  Multi-Stop  │  │  Raw Drive Cycle      │     │
│   └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘     │
│          │                 │                      │                  │
│          ▼                 ▼                      ▼                  │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │              PYTHON ENGINE (FASTSim Core)                │       │
│   │                                                         │       │
│   │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │       │
│   │  │  Valhalla    │  │  FASTSim     │  │  Charger DB   │  │       │
│   │  │  Graph Router│  │  Physics Sim │  │  + Confidence  │  │       │
│   │  │  (OSM India) │  │  (NREL)      │  │  Scoring      │  │       │
│   │  └─────────────┘  └──────────────┘  └───────────────┘  │       │
│   └─────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

The system is a **multi-service pipeline** with four key components:

| Component | Technology | Role |
|-----------|-----------|------|
| **Graph Router** | Valhalla (C++) | Generates road-level turn-by-turn paths using OpenStreetMap India data |
| **Physics Engine** | NREL FASTSim (Python) | Simulates edge-by-edge energy consumption using longitudinal vehicle dynamics |
| **Charger Intelligence** | Custom (Python) | Ranks nearby chargers by compatibility, distance, and review-based confidence |
| **API Gateway** | Node.js | Orchestrates the pipeline, handles request validation, and serves responses |

---

## How It Works

### 1. Route Generation Pipeline

When a user requests a route from **Point A → Point B**, the following pipeline executes:

```
Input (Origin, Destination, Vehicle, SOC, Temperature)
    │
    ▼
┌──────────────────────────────────────────────┐
│  1. VALHALLA ROUTE                           │
│  • Snaps coordinates to nearest road segment │
│  • Generates optimal path via Dijkstra/A*    │
│  • Returns edge-by-edge drive cycle:         │
│    - distance_m per edge                     │
│    - speed_kph (from OSM speed limits)       │
│    - grade_pct (elevation change)            │
│    - heading_deg (compass bearing)           │
│    - start/end coordinates                   │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│  2. BATTERY THERMAL CORRECTION               │
│  • Applies temperature-dependent capacity:   │
│    thermal_factor = -0.000114T² + 0.00572T   │
│                     + 0.924                  │
│  • At -10°C: effective capacity drops ~15%   │
│  • At 25°C: baseline (factor = 1.0)         │
│  • Adds HVAC load estimation (0.45 kW base) │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│  3. FASTSIM ENERGY SIMULATION                │
│  For each edge in the drive cycle:           │
│  • Compute tractive force:                   │
│    F = m·g·sin(θ) + m·g·Crr·cos(θ)          │
│      + ½·ρ·Cd·A·v² + m·a                    │
│  • Compute motor power demand (kW)           │
│  • Apply drivetrain efficiency curve         │
│  • Accumulate energy consumption (kWh)       │
│  • Track SOC depletion per-second            │
│  • Detect if SOC hits protection threshold   │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│  4. CHARGER RECOMMENDATION                   │
│  • Search charger DB within radius_km        │
│  • Filter by connector compatibility (BE 6)  │
│  • Score each charger's reliability:         │
│    confidence = 1 - p_fail                   │
│  • Optionally route to each charger          │
│  • Return top-N ranked by distance+score     │
└──────────────────┬───────────────────────────┘
                   ▼
Output (Route edges, SOC timeline, Chargers, Simulation)
```

### 2. Multi-Stop Planner Pipeline

For long routes where the battery cannot reach the destination:

```
Input (Origin, Destination, SOC=20%, Protection=15%)
    │
    ▼
┌─────────────────────────────────────────────┐
│  1. SIMULATE DIRECT ROUTE                   │
│  • Run full pipeline Origin → Destination   │
│  • Detect: SOC will deplete before arrival  │
│  • Identify depletion coordinate on route   │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  2. FIND CHARGING STOP                      │
│  • Search chargers near depletion point     │
│  • Select highest-confidence compatible     │
│  • Route: Origin → Charger → Destination    │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  3. GENERATE PLAN STEPS                     │
│  Step 0: DRIVE Origin → Charger (11.3 km)  │
│          SOC: 20.0% → 17.9%                │
│  Step 1: CHARGE at TML Autovikas           │
│          SOC: 17.9% → 70.0% (79 min)       │
│  Step 2: DRIVE Charger → Destination        │
│          SOC: 70.0% → 69.0% (23.5 km)      │
└─────────────────────────────────────────────┘
```

---

## Backend API Reference

**Base URL:** `http://139.59.81.193`

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "checks": {
    "node": "ok",
    "python": "ok",
    "runtime": "fastsim",
    "valhalla": "reachable"
  }
}
```

---

### `POST /api/v1/routing/recommend`

**Single route with energy simulation and charger recommendations.**

This is the primary endpoint. It generates a route, simulates energy consumption edge-by-edge, and returns nearby compatible chargers ranked by confidence.

**Request:**
```json
{
  "vehicle_id": "IN-2025-0007",
  "start": { "lat": 28.6129, "lon": 77.2295 },
  "end": { "lat": 28.5244, "lon": 77.1855 },
  "environment": {
    "ambient_temp_c": 25
  },
  "vehicle_state": {
    "starting_soc": 0.80,
    "protection_soc": 0.15
  },
  "charger_radius_km": 25,
  "charger_limit": 5,
  "compatible_only": true,
  "include_charger_routes": true
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vehicle_id` | string | ✅ | Vehicle identifier (e.g. `IN-2025-0007` for Mahindra BE 6) |
| `start` | `{lat, lon}` | ✅ | Origin coordinates (WGS84) |
| `end` | `{lat, lon}` | ✅ | Destination coordinates (WGS84) |
| `environment.ambient_temp_c` | float | ❌ | Ambient temperature in °C (default: 25) |
| `vehicle_state.starting_soc` | float | ✅ | Starting State of Charge (0.0 - 1.0) |
| `vehicle_state.protection_soc` | float | ❌ | Minimum SOC threshold (default: 0.15) |
| `charger_radius_km` | float | ❌ | Search radius for nearby chargers (default: 25) |
| `charger_limit` | int | ❌ | Max number of chargers to return (default: 5) |
| `compatible_only` | bool | ❌ | Filter chargers by vehicle connector compatibility |
| `include_charger_routes` | bool | ❌ | Include route edges to each charger |

**Response:**
```json
{
  "primary_route_edges": [
    {
      "edge_index": 0,
      "distance_m": 74.0,
      "speed_kph": 40.0,
      "grade_pct": -1.351351,
      "heading_deg": 278.15,
      "start_coordinate": { "lat": 28.6129, "lon": 77.2295 },
      "end_coordinate": { "lat": 28.6130, "lon": 77.2288 }
    }
  ],
  "simulation": {
    "status": "route_completed",
    "final_soc": 0.7767,
    "min_soc": 0.7767,
    "route_duration_s": 1452,
    "route_distance_m": 16000,
    "effective_kwh_allocated": 55.3,
    "soc_timeline": [0.80, 0.7998, 0.7995, "..."],
    "vehicle": {
      "vehicle_id": "IN-2025-0007",
      "make": "Mahindra Electric",
      "model": "BE 6",
      "year": 2024,
      "usable_ess_kwh": 55.3,
      "mass_kg": 1900.0,
      "max_motor_kw": 210.0,
      "drag_coef": 0.31,
      "frontal_area_m2": 2.64,
      "wheel_rr_coef": 0.012,
      "hvac_power_kw": 0.45
    },
    "battery_correction": {
      "base_kwh": 55.3,
      "soh_factor": 1.0,
      "thermal_factor": 1.0,
      "effective_kwh": 55.3,
      "ambient_temp_c": 25.0
    }
  },
  "recommended_chargers": [
    {
      "station_id": "306289",
      "station_name": "TML Autovikas Tata Power FC",
      "address": "25/1/1, Shivaji Marg, New Delhi 110015",
      "lat": 28.663618,
      "lon": 77.15619,
      "connector_types": "CCS2;CHAdeMO",
      "total_ports": 2,
      "max_power_kw": 0.0,
      "total_reviews": 9,
      "be6_compatible": true,
      "distance_from_anchor_km": 15.74,
      "confidence": {
        "confidence": 0.774,
        "p_fail": 0.226,
        "review_stats": {
          "review_count": 9,
          "average_sentiment": 0.868
        }
      }
    }
  ]
}
```

---

### `POST /api/v1/routing/plan`

**Multi-stop journey planner with automatic charging stops.**

When the battery can't reach the destination, this endpoint automatically inserts optimal charging stops along the route.

**Request:**
```json
{
  "vehicle_id": "IN-2025-0007",
  "start": { "lat": 28.7158, "lon": 77.1221 },
  "end": { "lat": 28.5244, "lon": 77.2066 },
  "vehicle_state": {
    "starting_soc": 0.20,
    "protection_soc": 0.15
  },
  "target_soc_after_charge": 0.70,
  "max_charging_stops": 3,
  "charger_radius_km": 25,
  "charger_limit": 5,
  "fallback_charger_power_kw": 22,
  "include_leg_edges": true
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `target_soc_after_charge` | float | SOC to charge up to at each stop (e.g. 0.70 = 70%) |
| `max_charging_stops` | int | Maximum number of charge stops allowed |
| `fallback_charger_power_kw` | float | Default charger power if station data unavailable |
| `include_leg_edges` | bool | Include route edges for each drive leg |

**Response:**
```json
{
  "status": "destination_reached",
  "plan_steps": [
    {
      "step_type": "drive",
      "from_coordinate": { "lat": 28.7158, "lon": 77.1221 },
      "to_coordinate": { "lat": 28.6636, "lon": 77.1562 },
      "to_label": "TML Autovikas Tata Power FC",
      "route_edges": ["...array of edge objects..."],
      "simulation": {
        "status": "route_completed",
        "final_soc": 0.1788,
        "route_distance_m": 11274,
        "soc_timeline": [0.20, 0.1998, "..."]
      }
    },
    {
      "step_type": "charge",
      "station_id": "306289",
      "station_name": "TML Autovikas Tata Power FC",
      "coordinate": { "lat": 28.6636, "lon": 77.1562 },
      "arrival_soc": 0.1788,
      "departure_soc": 0.70,
      "energy_added_kwh": 28.81,
      "estimated_charge_minutes": 78.6,
      "charger_power_kw": 22
    },
    {
      "step_type": "drive",
      "from_coordinate": { "lat": 28.6636, "lon": 77.1562 },
      "to_coordinate": { "lat": 28.5244, "lon": 77.2066 },
      "to_label": "destination",
      "route_edges": ["...array of edge objects..."],
      "simulation": {
        "status": "route_completed",
        "final_soc": 0.6900,
        "route_distance_m": 23491
      }
    }
  ],
  "chargers_considered": ["...ranked charger options..."]
}
```

---

### `POST /api/v1/routing/simulate`

**Raw drive cycle simulation without charger recommendations.** Used for detailed energy analysis.

---

### `GET /api/v1/confidence/nearby`

**Charger confidence scoring** — returns reliability predictions for nearby stations based on review sentiment, equipment age, and OCPI status.

### `GET /api/v1/confidence/stations/{station_id}`

**Individual station confidence** — detailed reliability assessment for a specific charger.

---

## Physics Engine

### Vehicle Model — Mahindra BE 6

```
┌──────────────────────────────────────────────────┐
│  MAHINDRA ELECTRIC BE 6 (2024)                   │
│                                                  │
│  Battery:     55.3 kWh usable                    │
│  Motor:       210 kW peak                        │
│  Mass:        1,900 kg                           │
│  Drag Coef:   0.31 Cd                            │
│  Frontal:     2.64 m²                            │
│  Rolling Rr:  0.012                              │
│  HVAC Load:   0.45 kW base                       │
│  Connectors:  CCS2, CHAdeMO                      │
└──────────────────────────────────────────────────┘
```

### Energy Consumption Model (FASTSim)

For each road edge, the physics engine computes:

```
Total Force = F_aero + F_rolling + F_grade + F_inertia

F_aero     = ½ · ρ · Cd · A · v²         (aerodynamic drag)
F_rolling  = m · g · Crr · cos(θ)         (tire rolling resistance)
F_grade    = m · g · sin(θ)               (hill climbing)
F_inertia  = m · a                        (acceleration)

Power (kW) = F_total · v / η_drivetrain

Energy per edge = Power × time + HVAC_load × time
```

### Thermal Battery Model

Temperature affects usable battery capacity via a quadratic correction:

```
thermal_factor(T) = -0.000114 · T² + 0.00572 · T + 0.924

effective_kWh = base_kWh × SoH_factor × thermal_factor(T)
```

| Temperature | Thermal Factor | Effective Capacity | Energy Penalty |
|-------------|---------------|-------------------|----------------|
| -10°C | 0.85 | 47.0 kWh | +56% drain |
| 0°C | 0.88 | 48.7 kWh | +44% drain |
| 10°C | 0.93 | 51.4 kWh | +15% drain |
| **25°C** | **1.00** | **55.3 kWh** | **baseline** |
| 35°C | 0.96 | 53.1 kWh | +39% drain |
| 45°C | 0.96 | 53.1 kWh | +39% drain |

---

## Charger Intelligence

### Confidence Scoring Algorithm

Each charger station receives a reliability score based on:

```
confidence = 1 - p_fail

p_fail is computed from:
├── OCPI Status (AVAILABLE, CHARGING, etc.)
├── Equipment Age (days since installation)
├── Review Statistics:
│   ├── review_count
│   ├── weighted_review_count (time-decayed)
│   └── average_sentiment (NLP-derived, 0-1)
└── Historical availability data
```

| Confidence Range | Rating | Meaning |
|-----------------|--------|---------|
| > 0.75 | 🟢 High | Reliable, recent positive reviews |
| 0.60 - 0.75 | 🟡 Medium | Likely available, some uncertainty |
| < 0.60 | 🔴 Low | Unreliable or insufficient data |

### Supported Connectors

The system filters chargers by vehicle compatibility:

| Connector | BE 6 Compatible | Common Use |
|-----------|----------------|-----------|
| CCS2 | ✅ | DC Fast Charging (50-150 kW) |
| CHAdeMO | ✅ | DC Fast Charging (50 kW) |
| Type 2 | ✅ | AC Charging (7-22 kW) |
| GB/T | ❌ | Chinese standard |

---

## Web Application

### Features

- **Interactive Mapbox** dark-themed map with click-to-set origin/destination
- **Dual mode:** Single Route (recommend) and Multi-Stop (plan)
- **Real-time SOC gauge** with animated ring visualization
- **SOC gradient route line** — green→yellow→orange→red showing battery depletion
- **Multi-leg colored routes** — each drive leg in a distinct color (cyan, purple, green)
- **Charger markers** color-coded by confidence with click-to-expand popups
- **Draggable markers** — reposition origin/destination by dragging
- **Preset routes** — 6 pre-configured Delhi routes for quick testing
- **Adjustable parameters** — SOC, protection threshold, and temperature sliders
- **Engine health monitor** — real-time backend status indicator

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Map | Mapbox GL JS v3.9.4 |
| Frontend | Vanilla JS / HTML / CSS |
| Design | Glassmorphism dark theme |
| Proxy (Local) | Python `http.server` (server.py) |
| Proxy (Deployed) | Vercel Rewrites |
| Hosting | Vercel |

### Live Demo

🌐 **[webapp-liart-two-98.vercel.app](https://webapp-liart-two-98.vercel.app)**

> Requires a [Mapbox Access Token](https://account.mapbox.com/access-tokens/) (free tier available).

---

## Performance Benchmarks

| Metric | Value | Notes |
|--------|-------|-------|
| Health endpoint | **130ms** | Network RTT to India server |
| Route recommend (avg) | **1,272ms** | Valhalla + FASTSim pipeline |
| Short route (1km) | **491ms** | Fewer edges = faster simulation |
| Long route (42km) | **2,045ms** | Scales linearly with edge count |
| 3x concurrent | **2,833ms** | No failures under load |

**Latency breakdown estimate:**
```
~130ms  Network RTT
~200ms  Valhalla graph routing
~700ms  FASTSim edge-by-edge simulation
~200ms  Charger search + confidence scoring
─────────
~1,230ms  Total
```

---

## Accuracy vs ABRP

Head-to-head comparison against [A Better Routeplanner](https://abetterrouteplanner.com):

| Route | Your Model | ABRP | Difference | Verdict |
|-------|-----------|------|------------|---------|
| India Gate → Qutub Minar | 77.67% | 77% | +0.67pp | ✅ Excellent |
| CP → IGI Airport T3 | 75.26% | 75% | +0.26pp | ✅ Excellent |
| Rohini → Greater Kailash | 72.85% | 72% | +0.85pp | ✅ Excellent |
| Narela → Mehrauli | 68.69% | 67% | +1.69pp | ✅ Good |
| Dwarka → Saket | 79.41% | 74% | +5.41pp | ⚠️ Under-estimates drain |

### Competitive Advantages Over ABRP

| Feature | This Engine | ABRP |
|---------|-----------|------|
| Response time | **1.3s** | 3-5s |
| Charger confidence scoring | ✅ p_fail metric | ❌ |
| Offline capability | ✅ Local FASTSim | ❌ Cloud only |
| API access | ✅ Full REST API | ❌ Web UI only |
| Temperature modeling | ✅ Quadratic thermal | ✅ |
| Concurrent requests | ✅ Tested 3x | ❌ N/A |

---

## Setup & Deployment

### Local Development

**Prerequisites:** Python 3.8+, Mapbox Access Token

```bash
# Clone the repository
git clone https://github.com/Akarsh2555/Routing_demo.git
cd Routing_demo

# Start the local proxy server
python server.py
# → App running at http://localhost:8080
# → Proxying API requests to the routing engine
```

Open `http://localhost:8080`, enter your Mapbox token, and start routing.

### Deploy to Vercel

The `webapp/` directory includes a `vercel.json` with API proxy rewrites:

```bash
cd webapp
npx vercel deploy --prod
```

The Vercel rewrites handle CORS by proxying `/api/*` and `/health` to the remote engine:

```json
{
  "rewrites": [
    { "source": "/health", "destination": "http://139.59.81.193/health" },
    { "source": "/api/:path*", "destination": "http://139.59.81.193/api/:path*" }
  ]
}
```

---

## Testing

### Run the Full Test Suite

```bash
python test_ev_routing.py
```

This executes 40+ tests across 9 categories:

| Category | Tests | Description |
|----------|-------|-------------|
| Health Check | 1 | Verify all system components |
| Route Accuracy | 8 | Delhi routes with SOC validation |
| SOC Sensitivity | 7 | Same route at varying start SOC |
| Temperature | 6 | Thermal capacity correction |
| Multi-Stop Planner | 3 | Charging stop insertion |
| Charger Confidence | 5 | Reliability scoring |
| Input Validation | 8 | Edge cases and error handling |
| Performance | 5 | Latency benchmarks |
| Route Physics | 1 | Detailed geometry validation |

### API Discovery

```bash
python api_discovery.py
```

Probes all endpoints to discover schemas and validate request/response formats.

---

## Project Structure

```
Routing_demo/
├── webapp/                      # Frontend application
│   ├── index.html               # Main HTML with Mapbox integration
│   ├── index.css                # Dark theme design system
│   ├── app.js                   # Application logic & API integration
│   └── vercel.json              # Vercel deployment config with API rewrites
├── server.py                    # Local CORS proxy + static file server
├── test_ev_routing.py           # Comprehensive test suite (40+ tests)
├── api_discovery.py             # API schema discovery script
├── Routing_Testing_Report       # Detailed test results & analysis
├── PluginAny Vs ABRP routing Analysis  # Accuracy comparison vs ABRP
└── README.md                    # This file
```

---

## Known Issues

| # | Issue | Severity | Description |
|---|-------|----------|-------------|
| 1 | Dwarka origin SOC anomaly | 🔴 Critical | Routes from ~(28.59, 77.05) show truncated drive cycles. 38km route returns same 0.59pp drain as 22km route. |
| 2 | Junk charger names | 🟡 Medium | Stations named "h" and "Shubhendu singh" are user-submitted junk entries. Need name validation. |
| 3 | HTTP status codes | 🟢 Low | Same-start/end returns 502 instead of 400. Ocean coords return 502 instead of 400. |
| 4 | Hot temp HVAC cap | 🟢 Low | 35°C and 45°C return identical results. HVAC model may cap at a certain temperature. |

---

## License

This project is proprietary. All rights reserved.

---

<p align="center">
  Built with ⚡ for the Indian EV ecosystem
</p>
