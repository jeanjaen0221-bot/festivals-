// JS moderne pour la page horaires de train (iRail) avec affichage split-flap (aéroport)
let suggestionsTimeout = null;
let autoRefreshId = null;
let currentStation = null;
let allStations = [];
let selectedStationId = null;

function showSuggestions(list) {
  const suggDiv = document.getElementById('station-suggestions');
  suggDiv.innerHTML = '';
  if (!list.length) { suggDiv.style.display = 'none'; return; }
  list.forEach(station => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'list-group-item list-group-item-action';
    el.textContent = station.name;
    el.onclick = () => {
      document.getElementById('station-input').value = station.name;
      selectedStationId = station.id || null;
      suggDiv.innerHTML = '';
      suggDiv.style.display = 'none';
    };
    suggDiv.appendChild(el);
  });
  suggDiv.style.display = 'block';
}

function normalizeStr(s){
  if (!s) return '';
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[’'\-]/g,' ').replace(/\s+/g,' ').trim();
}

function localStationSuggestions(query){
  if (!query) return [];
  const nq = normalizeStr(query);
  const starts = allStations.filter(s => normalizeStr(s.name).startsWith(nq));
  const contains = allStations.filter(s => !normalizeStr(s.name).startsWith(nq) && normalizeStr(s.name).includes(nq));
  return [...starts, ...contains].slice(0, 12);
}

function fmtTime(tsSec) {
  return new Date(tsSec * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}

function fmtDateDDMMYYFromEpoch(tsSec){
  const d = new Date(tsSec * 1000);
  const dd = String(d.getDate()).padStart(2,'0');
  const mm = String(d.getMonth()+1).padStart(2,'0');
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd}${mm}${yy}`;
}

function renderFlapBoard(container, stationName, departures, bannerText) {
  let html = `
    <div class='flap-board'>
      <div class='d-flex justify-content-between align-items-center px-1 pb-2'>
        <h2 class='mb-0 station-title'><i class='bi bi-clock-history'></i> Prochains départs de <b>${stationName}</b></h2>
        <div class='train-autorefresh'>MAJ auto 30 s</div>
      </div>
      ${bannerText ? `<div class='px-1 pb-2 text-warning small'>${bannerText}</div>` : ''}
      <div class='flap-header'>
        <div class='flap-cell center muted'>Heure</div>
        <div class='flap-cell muted'>Destination</div>
        <div class='flap-cell center muted'>Voie</div>
        <div class='flap-cell center muted'>Type</div>
        <div class='flap-cell center muted'>Retard</div>
      </div>
  `;
  departures.forEach(dep => {
    const time = fmtTime(dep.time);
    const platform = dep.platform || '-';
    const type = (dep.vehicle || '').replace('BE.NMBS.', '');
    const delay = dep.delay ? '+' + Math.round(dep.delay/60) + ' min' : '';
    const dest = dep.destination || dep.station || '';
    html += `
      <div class='flap-row'>
        <div class='flap-cell center flip'>${time}</div>
        <div class='flap-cell flip'>${dest}</div>
        <div class='flap-cell center flip'>${platform}</div>
        <div class='flap-cell center flip'>${type}</div>
        <div class='flap-cell center flip ${delay ? 'delay' : ''}'>${delay}</div>
      </div>
    `;
  });
  html += `</div>`;
  container.innerHTML = html;
}

async function loadLiveboard(station, resultsDiv) {
  resultsDiv.innerHTML = '<div class="text-center py-4"><div class="spinner-border" role="status"></div> Chargement...</div>';
  try {
    const resp = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(station)}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    const raw = data.departures;
    let list = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.departure) ? raw.departure : []);
    if (!list.length) {
      // Fallback 1: retry with fast=false
      const resp2 = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(station)}&fast=false`);
      const data2 = await resp2.json();
      if (!data2.error) {
        const raw2 = data2.departures;
        const list2 = Array.isArray(raw2) ? raw2 : (raw2 && Array.isArray(raw2.departure) ? raw2.departure : []);
        if (list2 && list2.length) {
          renderFlapBoard(resultsDiv, station, list2.slice(0,3), "Aucun train à l'heure demandée — affichage des 3 prochains départs.");
          return;
        }
      }
      // Fallback 1b: resolve station id using backend stations search, then retry fast=false
      try {
        const typed = (document.getElementById('station-input')?.value || '').trim();
        if (typed) {
          const rs = await fetch(`/api/trains/stations?lang=fr&only_be=1&q=${encodeURIComponent(typed)}`);
          const ds = await rs.json();
          const best = Array.isArray(ds.stations) && ds.stations.length ? ds.stations[0] : null;
          if (best && best.id) {
            const r3 = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(best.id)}&fast=false`);
            const d3 = await r3.json();
            const rw3 = d3.departures;
            const l3 = Array.isArray(rw3) ? rw3 : (rw3 && Array.isArray(rw3.departure) ? rw3.departure : []);
            if (l3 && l3.length) { renderFlapBoard(resultsDiv, best.name || typed, l3.slice(0,3), "Aucun train à l'heure demandée — affichage des 3 prochains départs."); return; }
          }
        }
      } catch(e) {}
      // Fallback 2: probe next hours (+1h .. +6h) with fast=false using epoch time
      const now = Math.floor(Date.now() / 1000);
      for (let h = 1; h <= 6; h++) {
        const t = now + h * 3600;
        try {
          const date = fmtDateDDMMYYFromEpoch(t);
          const rp = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(station)}&fast=false&time=${t}&date=${date}`);
          const dj = await rp.json();
          if (!dj.error) {
            const rw = dj.departures;
            const lst = Array.isArray(rw) ? rw : (rw && Array.isArray(rw.departure) ? rw.departure : []);
            if (lst && lst.length) {
              const when = new Date(t * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
              renderFlapBoard(resultsDiv, station, lst.slice(0,3), `Aucun train à l'heure demandée — prochains départs vers ${when}.`);
              return;
            }
          }
        } catch (e) {}
      }
      resultsDiv.innerHTML = '<div class="alert alert-warning">Aucun départ trouvé pour cette gare.</div>';
      return;
    }
    renderFlapBoard(resultsDiv, station, list.slice(0, 12));
  } catch (err) {
    resultsDiv.innerHTML = `<div class='alert alert-danger'>Erreur : ${err.message || 'Impossible de récupérer les horaires.'}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('station-input');
  const form = document.getElementById('station-search-form');
  const resultsDiv = document.getElementById('train-results');
  const suggDiv = document.getElementById('station-suggestions');

  // Preload stations list (FR, only Belgian stations)
  (async () => {
    try {
      const r = await fetch('/api/trains/stations?lang=fr&only_be=1');
      const d = await r.json();
      if (Array.isArray(d.stations)) allStations = d.stations;
    } catch (e) {}
  })();

  input.addEventListener('input', async e => {
    const val = input.value.trim();
    clearTimeout(suggestionsTimeout);
    if (val.length < 2) { suggDiv.innerHTML=''; suggDiv.style.display='none'; return; }
    suggestionsTimeout = setTimeout(async () => {
      const suggestions = localStationSuggestions(val);
      showSuggestions(suggestions);
    }, 250);
  });

  document.addEventListener('click', (e) => {
    if (!suggDiv.contains(e.target) && e.target !== input) {
      suggDiv.innerHTML = '';
      suggDiv.style.display = 'none';
    }
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const typed = input.value.trim();
    if (!typed) return;
    // if no explicit selection, try to match starts-with suggestion to set id
    if (!selectedStationId) {
      const first = localStationSuggestions(typed)[0];
      if (first) selectedStationId = first.id;
    }
    currentStation = selectedStationId || typed;
    if (autoRefreshId) { clearInterval(autoRefreshId); autoRefreshId = null; }
    await loadLiveboard(currentStation, resultsDiv);
    autoRefreshId = setInterval(() => {
      if (currentStation) loadLiveboard(currentStation, resultsDiv);
    }, 30000);
  });
});
