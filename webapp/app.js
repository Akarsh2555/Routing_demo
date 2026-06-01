/* ═══════════════════════════════════════════════════════════
   EV ROUTING ENGINE — App Logic
   ═══════════════════════════════════════════════════════════ */

const API = '';  // proxied through local server (server.py)
const VEHICLE = 'IN-2025-0007';
const DELHI = [77.209, 28.6139];

const PRESETS = [
  { name: 'India Gate → Qutub Minar', o: [28.6129, 77.2295], d: [28.5244, 77.1855] },
  { name: 'CP → IGI Airport T3', o: [28.6315, 77.2167], d: [28.5562, 77.1000] },
  { name: 'Red Fort → Lotus Temple', o: [28.6562, 77.2410], d: [28.5535, 77.2588] },
  { name: 'Rohini → Greater Kailash', o: [28.7158, 77.1221], d: [28.5425, 77.2426] },
  { name: 'Narela → Mehrauli', o: [28.8524, 77.0928], d: [28.5110, 77.1780] },
  { name: 'Dwarka → Saket', o: [28.5921, 77.0460], d: [28.5244, 77.2066] },
];

let map, origin = null, destination = null, mode = 'recommend';
let originMarker = null, destMarker = null, chargerMarkers = [];

// ── DOM refs ───────────────────────────────────────────────
const $ = id => document.getElementById(id);
const originText = $('origin-text'), destText = $('dest-text');
const clearOriginBtn = $('clear-origin'), clearDestBtn = $('clear-dest');
const calcBtn = $('calc-btn'), resultsPanel = $('results-panel');
const socSlider = $('soc-slider'), protSlider = $('prot-slider'), tempSlider = $('temp-slider');
const socVal = $('soc-val'), protVal = $('prot-val'), tempVal = $('temp-val');
const healthBadge = $('health-badge'), instructions = $('map-instructions');
const toast = $('toast');

// ── Token Modal ────────────────────────────────────────────
const savedToken = localStorage.getItem('mapbox_token');
if (savedToken) { initApp(savedToken); $('token-modal').classList.add('hidden'); }

$('token-submit').addEventListener('click', () => {
  const t = $('token-input').value.trim();
  if (t && t.startsWith('pk.')) {
    localStorage.setItem('mapbox_token', t);
    $('token-modal').classList.add('hidden');
    initApp(t);
  }
});
$('token-input').addEventListener('keydown', e => { if (e.key === 'Enter') $('token-submit').click(); });

function initApp(token) {
  mapboxgl.accessToken = token;
  map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/dark-v11',
    center: DELHI,
    zoom: 11,
    pitch: 0
  });
  map.addControl(new mapboxgl.NavigationControl(), 'top-left');
  map.on('load', () => { map.resize(); });
  map.on('click', onMapClick);
  checkHealth();
  setupUI();
}

// ── Health ─────────────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(8000) });
    const d = await r.json();
    healthBadge.classList.remove('offline');
    healthBadge.innerHTML = '<span class="dot"></span>Online · ' + (d.checks?.runtime || 'ok');
  } catch {
    healthBadge.classList.add('offline');
    healthBadge.innerHTML = '<span class="dot"></span>Offline';
  }
}

// ── UI Setup ───────────────────────────────────────────────
function setupUI() {
  // Sliders
  socSlider.oninput = () => { socVal.textContent = socSlider.value + '%'; };
  protSlider.oninput = () => { protVal.textContent = protSlider.value + '%'; };
  tempSlider.oninput = () => { tempVal.textContent = tempSlider.value + '°C'; };

  // Mode toggle
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      mode = btn.dataset.mode;
    });
  });

  // Presets
  const grid = $('preset-grid');
  PRESETS.forEach(p => {
    const chip = document.createElement('button');
    chip.className = 'preset-chip';
    chip.textContent = p.name;
    chip.addEventListener('click', () => {
      setOrigin(p.o[0], p.o[1]);
      setDestination(p.d[0], p.d[1]);
    });
    grid.appendChild(chip);
  });

  // Clear buttons
  clearOriginBtn.addEventListener('click', e => { e.stopPropagation(); clearOrigin(); });
  clearDestBtn.addEventListener('click', e => { e.stopPropagation(); clearDest(); });

  // Calculate
  calcBtn.addEventListener('click', calculateRoute);
}

// ── Map Clicks ─────────────────────────────────────────────
function onMapClick(e) {
  const { lat, lng } = e.lngLat;
  if (!origin) { setOrigin(lat, lng); }
  else if (!destination) { setDestination(lat, lng); }
}

function setOrigin(lat, lng) {
  origin = { lat, lon: lng };
  originText.textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  originText.classList.add('set');
  clearOriginBtn.classList.add('visible');
  if (originMarker) originMarker.remove();
  originMarker = createMarker(lat, lng, 'origin').addTo(map);
  updateCalcBtn();
  if (!destination) instructions.innerHTML = 'Now <span>click</span> to set destination';
  else instructions.classList.add('hidden');
}

function setDestination(lat, lng) {
  destination = { lat, lon: lng };
  destText.textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  destText.classList.add('set');
  clearDestBtn.classList.add('visible');
  if (destMarker) destMarker.remove();
  destMarker = createMarker(lat, lng, 'destination').addTo(map);
  updateCalcBtn();
  instructions.classList.add('hidden');
}

function clearOrigin() {
  origin = null;
  originText.textContent = 'Click map to set origin';
  originText.classList.remove('set');
  clearOriginBtn.classList.remove('visible');
  if (originMarker) { originMarker.remove(); originMarker = null; }
  updateCalcBtn();
  instructions.innerHTML = '<span>Click</span> on the map to set origin';
  instructions.classList.remove('hidden');
}

function clearDest() {
  destination = null;
  destText.textContent = 'Click map to set destination';
  destText.classList.remove('set');
  clearDestBtn.classList.remove('visible');
  if (destMarker) { destMarker.remove(); destMarker = null; }
  updateCalcBtn();
}

function updateCalcBtn() {
  calcBtn.disabled = !(origin && destination);
}

function createMarker(lat, lng, type) {
  const el = document.createElement('div');
  el.className = `custom-marker ${type}`;
  el.innerHTML = `<span class="marker-inner">${type === 'origin' ? '▶' : '◉'}</span>`;
  const m = new mapboxgl.Marker({ element: el, draggable: true }).setLngLat([lng, lat]);
  m.on('dragend', () => {
    const ll = m.getLngLat();
    if (type === 'origin') { origin = { lat: ll.lat, lon: ll.lng }; originText.textContent = `${ll.lat.toFixed(4)}, ${ll.lng.toFixed(4)}`; }
    else { destination = { lat: ll.lat, lon: ll.lng }; destText.textContent = `${ll.lat.toFixed(4)}, ${ll.lng.toFixed(4)}`; }
  });
  return m;
}

// ── API Calls ──────────────────────────────────────────────
async function calculateRoute() {
  if (!origin || !destination) return;
  calcBtn.classList.add('loading');
  calcBtn.disabled = true;
  clearResults();
  hideToast();

  const soc = parseInt(socSlider.value) / 100;
  const prot = parseInt(protSlider.value) / 100;
  const temp = parseInt(tempSlider.value);

  try {
    const t0 = performance.now();
    let data, endpoint;

    if (mode === 'recommend') {
      endpoint = '/api/v1/routing/recommend';
      const payload = {
        vehicle_id: VEHICLE,
        start: { lat: origin.lat, lon: origin.lon },
        end: { lat: destination.lat, lon: destination.lon },
        environment: { ambient_temp_c: temp },
        vehicle_state: { starting_soc: soc, protection_soc: prot },
        charger_radius_km: 25, charger_limit: 5,
        compatible_only: true, include_charger_routes: true,
      };
      const r = await fetch(`${API}${endpoint}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: AbortSignal.timeout(30000)
      });
      if (!r.ok) { const e = await r.text(); throw new Error(`${r.status}: ${e.slice(0, 200)}`); }
      data = await r.json();
    } else {
      endpoint = '/api/v1/routing/plan';
      const payload = {
        vehicle_id: VEHICLE,
        start: { lat: origin.lat, lon: origin.lon },
        end: { lat: destination.lat, lon: destination.lon },
        vehicle_state: { starting_soc: soc, protection_soc: prot },
        target_soc_after_charge: 0.7, max_charging_stops: 3,
        charger_radius_km: 25, charger_limit: 5,
        fallback_charger_power_kw: 22, include_leg_edges: true,
      };
      const r = await fetch(`${API}${endpoint}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: AbortSignal.timeout(60000)
      });
      if (!r.ok) { const e = await r.text(); throw new Error(`${r.status}: ${e.slice(0, 200)}`); }
      data = await r.json();
    }

    const latency = Math.round(performance.now() - t0);
    if (mode === 'recommend') renderRecommendResult(data, latency, soc);
    else renderPlanResult(data, latency, soc);

  } catch (err) {
    showToast(err.message || 'Request failed');
  } finally {
    calcBtn.classList.remove('loading');
    calcBtn.disabled = false;
  }
}

// ── Render: Recommend ──────────────────────────────────────
function renderRecommendResult(data, latency, startSoc) {
  const edges = data.primary_route_edges || [];
  const sim = data.simulation || {};
  const chargers = data.recommended_chargers || [];
  const finalSoc = sim.final_soc;
  const socDrop = finalSoc != null ? (startSoc - finalSoc) * 100 : null;
  const energy = sim.energy_kwh || sim.total_energy_kwh;

  // Draw route
  if (edges.length > 0) drawRouteFromEdges(edges, finalSoc, startSoc);

  // Draw chargers
  drawChargers(chargers);

  // Fit bounds (include charger positions)
  fitToRoute(edges, chargers);

  // Build results HTML
  const socColor = getSocColor(finalSoc);
  const circumference = 2 * Math.PI * 48;
  const offset = finalSoc != null ? circumference * (1 - finalSoc) : circumference;

  let distKm = 0;
  edges.forEach(e => { distKm += (e.distance_m || 0) / 1000; });

  let html = `
    <div class="soc-gauge-wrap">
      <div class="soc-gauge">
        <svg viewBox="0 0 120 120">
          <circle class="gauge-bg" cx="60" cy="60" r="48"/>
          <circle class="gauge-fill" cx="60" cy="60" r="48"
            stroke="${socColor}"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${offset}"/>
        </svg>
        <div class="gauge-center">
          <div class="gauge-value" style="color:${socColor}">${finalSoc != null ? (finalSoc * 100).toFixed(1) : '?'}%</div>
          <div class="gauge-label">Final SOC</div>
        </div>
      </div>
    </div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">Distance</div><div class="stat-value">${distKm.toFixed(1)} km</div></div>
      <div class="stat-card"><div class="stat-label">SOC Drop</div><div class="stat-value" style="color:${socDrop > 10 ? '#fb923c' : '#38bdf8'}">${socDrop != null ? socDrop.toFixed(2) + 'pp' : '?'}</div></div>
      <div class="stat-card"><div class="stat-label">Edges</div><div class="stat-value">${edges.length}</div></div>
      <div class="stat-card"><div class="stat-label">Latency</div><div class="stat-value">${latency}ms</div></div>
    </div>`;

  if (chargers.length > 0) {
    html += `<div class="charger-section-title">⚡ Nearby Chargers (${chargers.length})</div>`;
    chargers.forEach(c => {
      const conf = c.confidence?.confidence;
      const cls = conf > 0.75 ? 'high' : conf > 0.6 ? 'med' : 'low';
      html += `
        <div class="charger-item" data-lat="${c.lat || c.location?.lat}" data-lon="${c.lon || c.location?.lon}">
          <div class="charger-name">${esc(c.station_name || '?')}</div>
          <div class="charger-meta">
            <span>${(c.distance_from_anchor_km || 0).toFixed(1)} km</span>
            <span>${formatConnectors(c.connector_types)}</span>
            <span class="confidence-badge confidence-${cls}">${conf != null ? (conf * 100).toFixed(0) + '%' : '?'}</span>
          </div>
        </div>`;
    });
  }

  resultsPanel.innerHTML = html;
  resultsPanel.classList.add('visible');

  // Click charger item → fly to it
  resultsPanel.querySelectorAll('.charger-item').forEach(el => {
    el.addEventListener('click', () => {
      const lat = parseFloat(el.dataset.lat), lon = parseFloat(el.dataset.lon);
      if (lat && lon) map.flyTo({ center: [lon, lat], zoom: 15 });
    });
  });
}

// ── Render: Plan ───────────────────────────────────────────
function renderPlanResult(data, latency, startSoc) {
  const steps = data.plan_steps || [];
  const chargeSteps = steps.filter(s => s.step_type === 'charge');
  const driveSteps = steps.filter(s => s.step_type === 'drive');

  // Compute totals from simulations
  let totalDist = 0, lastSoc = null;
  let totalChargeMin = 0;
  const allCoords = [];
  const LEG_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fbbf24'];

  driveSteps.forEach((step, legIdx) => {
    const sim = step.simulation || {};
    totalDist += (sim.route_distance_m || 0) / 1000;
    lastSoc = sim.final_soc;
    const edges = step.route_edges || [];
    const legCoords = [];
    // Connect first leg to origin marker, last leg to destination marker
    if (legIdx === 0 && origin) {
      legCoords.push([origin.lon, origin.lat]);
      allCoords.push([origin.lon, origin.lat]);
    }
    edges.forEach(e => {
      if (e.start_coordinate) {
        const c = [e.start_coordinate.lon, e.start_coordinate.lat];
        legCoords.push(c);
        allCoords.push(c);
      }
    });
    const lastEdge = edges[edges.length - 1];
    if (lastEdge?.end_coordinate) {
      const c = [lastEdge.end_coordinate.lon, lastEdge.end_coordinate.lat];
      legCoords.push(c);
      allCoords.push(c);
    }
    if (legIdx === driveSteps.length - 1 && destination) {
      legCoords.push([destination.lon, destination.lat]);
      allCoords.push([destination.lon, destination.lat]);
    }
    // Draw each leg as a separate colored line
    if (legCoords.length > 1) {
      drawLegRoute(legCoords, LEG_COLORS[legIdx % LEG_COLORS.length], `plan-leg-${legIdx}`);
    }
  });

  chargeSteps.forEach(step => {
    totalChargeMin += step.estimated_charge_minutes || 0;
  });

  const finalSoc = lastSoc ?? data.final_soc;

  // Mark charge stops
  clearChargerMarkers();
  chargeSteps.forEach(step => {
    const coord = step.coordinate;
    if (!coord) return;
    const el = document.createElement('div');
    el.className = 'charger-marker high';
    el.innerHTML = '⚡';
    const marker = new mapboxgl.Marker({ element: el })
      .setLngLat([coord.lon, coord.lat])
      .setPopup(new mapboxgl.Popup({ offset: 15 }).setHTML(
        `<b>${esc(step.station_name || 'Charge Stop')}</b><br>` +
        `${(step.arrival_soc * 100).toFixed(1)}% → ${(step.departure_soc * 100).toFixed(1)}%<br>` +
        `${(step.estimated_charge_minutes || 0).toFixed(0)} min`
      ))
      .addTo(map);
    chargerMarkers.push(marker);
  });

  // Fit bounds
  if (allCoords.length > 1) {
    const bounds = allCoords.reduce((b, c) => b.extend(c), new mapboxgl.LngLatBounds(allCoords[0], allCoords[0]));
    chargeSteps.forEach(s => { if (s.coordinate) bounds.extend([s.coordinate.lon, s.coordinate.lat]); });
    map.fitBounds(bounds, { padding: { top: 60, bottom: 60, left: 40, right: 380 } });
  }

  // Results panel
  const socColor = getSocColor(finalSoc);
  const circumference = 2 * Math.PI * 48;
  const offset = finalSoc != null ? circumference * (1 - finalSoc) : circumference;

  let html = `
    <div class="soc-gauge-wrap">
      <div class="soc-gauge">
        <svg viewBox="0 0 120 120">
          <circle class="gauge-bg" cx="60" cy="60" r="48"/>
          <circle class="gauge-fill" cx="60" cy="60" r="48"
            stroke="${socColor}" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"/>
        </svg>
        <div class="gauge-center">
          <div class="gauge-value" style="color:${socColor}">${finalSoc != null ? (finalSoc * 100).toFixed(1) : '?'}%</div>
          <div class="gauge-label">Final SOC</div>
        </div>
      </div>
    </div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">Distance</div><div class="stat-value">${totalDist.toFixed(1)} km</div></div>
      <div class="stat-card"><div class="stat-label">Charge Stops</div><div class="stat-value" style="color:${chargeSteps.length > 0 ? '#fbbf24' : '#34d399'}">${chargeSteps.length}</div></div>
      <div class="stat-card"><div class="stat-label">Charge Time</div><div class="stat-value">${totalChargeMin.toFixed(0)} min</div></div>
      <div class="stat-card"><div class="stat-label">Latency</div><div class="stat-value">${latency}ms</div></div>
    </div>
    <div class="charger-section-title">📋 Trip Plan (${steps.length} steps)</div>
    <div class="plan-timeline">`;

  steps.forEach(step => {
    if (step.step_type === 'drive') {
      const sim = step.simulation || {};
      const d = ((sim.route_distance_m || 0) / 1000).toFixed(1);
      const timeline = sim.soc_timeline || [];
      const sSoc = timeline.length > 0 ? timeline[0] : null;
      const eSoc = sim.final_soc;
      html += `
        <div class="timeline-step">
          <div class="timeline-icon drive">🚗</div>
          <div class="timeline-body">
            <div class="timeline-title">Drive ${d} km</div>
            <div class="timeline-detail">${sSoc != null ? (sSoc * 100).toFixed(1) : '?'}% → ${eSoc != null ? (eSoc * 100).toFixed(1) : '?'}%</div>
          </div>
        </div>`;
    } else if (step.step_type === 'charge') {
      html += `
        <div class="timeline-step">
          <div class="timeline-icon charge">⚡</div>
          <div class="timeline-body">
            <div class="timeline-title">${esc(step.station_name || 'Charge Stop')}</div>
            <div class="timeline-detail">${(step.arrival_soc * 100).toFixed(1)}% → ${(step.departure_soc * 100).toFixed(1)}% · ${(step.estimated_charge_minutes || 0).toFixed(0)} min</div>
          </div>
        </div>`;
    }
  });

  html += '</div>';
  resultsPanel.innerHTML = html;
  resultsPanel.classList.add('visible');
}

// ── Map Drawing ────────────────────────────────────────────
function drawRouteFromEdges(edges, finalSoc, startSoc) {
  const coords = [];
  // Connect from user's origin marker to first road-snapped point
  if (origin) coords.push([origin.lon, origin.lat]);
  edges.forEach(e => {
    if (e.start_coordinate) coords.push([e.start_coordinate.lon, e.start_coordinate.lat]);
  });
  const last = edges[edges.length - 1];
  if (last?.end_coordinate) coords.push([last.end_coordinate.lon, last.end_coordinate.lat]);
  // Connect to user's destination marker
  if (destination) coords.push([destination.lon, destination.lat]);
  if (coords.length < 2) return;

  // Animated route line
  drawRoute(coords, '#38bdf8');

  // SOC gradient overlay
  if (edges.length > 2) drawSocGradient(edges, startSoc);
}

function drawRoute(coords, color) {
  const id = 'route-line';
  if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(id)) map.removeSource(id);

  map.addSource(id, { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } } });
  // Glow layer
  if (map.getLayer('route-glow')) map.removeLayer('route-glow');
  if (map.getSource('route-glow')) map.removeSource('route-glow');
  map.addSource('route-glow', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } } });
  map.addLayer({ id: 'route-glow', type: 'line', source: 'route-glow', paint: { 'line-color': color, 'line-width': 12, 'line-opacity': 0.15, 'line-blur': 8 } });
  map.addLayer({ id, type: 'line', source: id, layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': color, 'line-width': 4, 'line-opacity': 0.9 } });
}

function drawLegRoute(coords, color, id) {
  const glowId = id + '-glow';
  if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(id)) map.removeSource(id);
  if (map.getLayer(glowId)) map.removeLayer(glowId);
  if (map.getSource(glowId)) map.removeSource(glowId);

  const geojson = { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } };
  map.addSource(glowId, { type: 'geojson', data: geojson });
  map.addLayer({ id: glowId, type: 'line', source: glowId, paint: { 'line-color': color, 'line-width': 12, 'line-opacity': 0.15, 'line-blur': 8 } });
  map.addSource(id, { type: 'geojson', data: geojson });
  map.addLayer({ id, type: 'line', source: id, layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': color, 'line-width': 4, 'line-opacity': 0.9 } });
}

function drawSocGradient(edges, startSoc) {
  // Create colored segments showing SOC depletion along route
  const features = [];
  const totalEdges = edges.length;
  for (let i = 0; i < totalEdges - 1; i++) {
    const e = edges[i];
    const next = edges[i + 1];
    if (!e.start_coordinate || !next.start_coordinate) continue;
    const frac = i / totalEdges;
    features.push({
      type: 'Feature',
      properties: { frac },
      geometry: { type: 'LineString', coordinates: [
        [e.start_coordinate.lon, e.start_coordinate.lat],
        [next.start_coordinate.lon, next.start_coordinate.lat]
      ]}
    });
  }

  const srcId = 'soc-gradient';
  if (map.getLayer(srcId)) map.removeLayer(srcId);
  if (map.getSource(srcId)) map.removeSource(srcId);

  map.addSource(srcId, { type: 'geojson', data: { type: 'FeatureCollection', features } });
  map.addLayer({
    id: srcId, type: 'line', source: srcId,
    paint: {
      'line-color': ['interpolate', ['linear'], ['get', 'frac'],
        0, '#34d399', 0.4, '#fbbf24', 0.7, '#fb923c', 1.0, '#f87171'
      ],
      'line-width': 5, 'line-opacity': 0.7
    }
  });
}

function drawChargers(chargers) {
  clearChargerMarkers();
  chargers.forEach(c => {
    const lat = c.lat || c.location?.lat;
    const lon = c.lon || c.location?.lon;
    if (!lat || !lon) return;
    const conf = c.confidence?.confidence || 0;
    const cls = conf > 0.75 ? 'high' : conf > 0.6 ? 'med' : 'low';
    const el = document.createElement('div');
    el.className = `charger-marker ${cls}`;
    el.innerHTML = '⚡';
    const marker = new mapboxgl.Marker({ element: el })
      .setLngLat([lon, lat])
      .setPopup(new mapboxgl.Popup({ offset: 15, maxWidth: '260px' }).setHTML(
        `<b style="font-size:13px">${esc(c.station_name || '?')}</b><br>` +
        `<span style="color:#94a3b8;font-size:11px">${formatConnectors(c.connector_types)}</span><br>` +
        `<span style="font-family:monospace;font-size:11px">Confidence: ${(conf * 100).toFixed(0)}% · p_fail: ${((c.confidence?.p_fail || 0) * 100).toFixed(0)}%</span><br>` +
        `<span style="font-family:monospace;font-size:11px">Distance: ${(c.distance_from_anchor_km || 0).toFixed(1)} km</span>`
      ))
      .addTo(map);
    chargerMarkers.push(marker);
  });
}

function fitToRoute(edges, chargers) {
  if (edges.length < 2) return;
  const bounds = new mapboxgl.LngLatBounds();
  edges.forEach(e => {
    if (e.start_coordinate) bounds.extend([e.start_coordinate.lon, e.start_coordinate.lat]);
    if (e.end_coordinate) bounds.extend([e.end_coordinate.lon, e.end_coordinate.lat]);
  });
  // Include charger locations so all markers are visible
  if (chargers) {
    chargers.forEach(c => {
      const lat = c.lat || c.location?.lat;
      const lon = c.lon || c.location?.lon;
      if (lat && lon) bounds.extend([lon, lat]);
    });
  }
  map.fitBounds(bounds, { padding: { top: 60, bottom: 60, left: 40, right: 380 } });
}

// ── Cleanup ────────────────────────────────────────────────
function clearResults() {
  resultsPanel.classList.remove('visible');
  resultsPanel.innerHTML = '';
  // Remove recommend mode layers
  ['route-line', 'route-glow', 'soc-gradient'].forEach(id => {
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(id)) map.removeSource(id);
  });
  // Remove plan mode leg layers
  for (let i = 0; i < 10; i++) {
    [`plan-leg-${i}`, `plan-leg-${i}-glow`].forEach(id => {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    });
  }
  clearChargerMarkers();
}

function clearChargerMarkers() {
  chargerMarkers.forEach(m => { if (m.remove) m.remove(); });
  chargerMarkers = [];
}

// ── Helpers ────────────────────────────────────────────────
function getSocColor(soc) {
  if (soc == null) return '#64748b';
  if (soc > 0.6) return '#34d399';
  if (soc > 0.35) return '#fbbf24';
  if (soc > 0.2) return '#fb923c';
  return '#f87171';
}

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('visible');
  setTimeout(() => toast.classList.remove('visible'), 6000);
}
function hideToast() { toast.classList.remove('visible'); }

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function formatConnectors(ct) {
  if (!ct) return '—';
  if (Array.isArray(ct)) return ct.join(', ');
  return ct.replace(/;/g, ', ');
}
