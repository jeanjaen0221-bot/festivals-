// JS moderne pour la page horaires de train (iRail) avec affichage split-flap (aéroport)
let suggestionsTimeout = null;
let autoRefreshId = null;
let currentStationId = null;
let currentStationName = null;
let stationsAll = [];
let selectedStation = null;

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
      selectedStation = station;
      suggDiv.innerHTML = '';
      suggDiv.style.display = 'none';
    };
    suggDiv.appendChild(el);
  });
  suggDiv.style.display = 'block';
}

function normalizeName(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

async function fetchAllStations() {
  try {
    const url = `https://api.irail.be/stations/?format=json&lang=fr`;
    const resp = await fetch(url);
    const data = await resp.json();
    const raw = data.station || [];
    stationsAll = raw
      .filter(s => s.name && s.id)
      .map(s => ({ name: s.name, id: s.id, norm: normalizeName(s.name) }))
      .sort((a,b) => a.name.localeCompare(b.name, 'fr'));
  } catch (e) { stationsAll = []; }
}

function fmtTime(tsSec) {
  return new Date(tsSec * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
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
    html += `
      <div class='flap-row'>
        <div class='flap-cell center flip'>${time}</div>
        <div class='flap-cell flip'>${dep.station}</div>
        <div class='flap-cell center flip'>${platform}</div>
        <div class='flap-cell center flip'>${type}</div>
        <div class='flap-cell center flip ${delay ? 'delay' : ''}'>${delay}</div>
      </div>
    `;
  });
  html += `</div>`;
  container.innerHTML = html;
}

async function loadLiveboard(stationIdOrName, resultsDiv, displayName) {
  resultsDiv.innerHTML = '<div class="text-center py-4"><div class="spinner-border" role="status"></div> Chargement...</div>';
  try {
    const resp = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(stationIdOrName)}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    const raw = data.departures;
    let list = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.departure) ? raw.departure : []);
    if (!list.length) {
      // Fallback 1: retry with fast=false
      const resp2 = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(stationIdOrName)}&fast=false`);
      const data2 = await resp2.json();
      if (!data2.error) {
        const raw2 = data2.departures;
        const list2 = Array.isArray(raw2) ? raw2 : (raw2 && Array.isArray(raw2.departure) ? raw2.departure : []);
        if (list2 && list2.length) {
          renderFlapBoard(resultsDiv, displayName || stationIdOrName, list2.slice(0,3), "Aucun train à l'heure demandée — affichage des 3 prochains départs.");
          return;
        }
      }
      // Fallback 2: probe next hours (+1h .. +6h) with fast=false using epoch time
      const now = Math.floor(Date.now() / 1000);
      for (let h = 1; h <= 6; h++) {
        const t = now + h * 3600;
        try {
          const rp = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(stationIdOrName)}&fast=false&time=${t}`);
          const dj = await rp.json();
          if (!dj.error) {
            const rw = dj.departures;
            const lst = Array.isArray(rw) ? rw : (rw && Array.isArray(rw.departure) ? rw.departure : []);
            if (lst && lst.length) {
              const when = new Date(t * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
              renderFlapBoard(resultsDiv, displayName || stationIdOrName, lst.slice(0,3), `Aucun train à l'heure demandée — prochains départs vers ${when}.`);
              return;
            }
          }
        } catch (e) {}
      }
      resultsDiv.innerHTML = '<div class="alert alert-warning">Aucun départ trouvé pour cette gare.</div>';
      return;
    }
    renderFlapBoard(resultsDiv, displayName || stationIdOrName, list.slice(0, 12));
  } catch (err) {
    resultsDiv.innerHTML = `<div class='alert alert-danger'>Erreur : ${err.message || 'Impossible de récupérer les horaires.'}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const input = document.getElementById('station-input');
  const form = document.getElementById('station-search-form');
  const resultsDiv = document.getElementById('train-results');
  const suggDiv = document.getElementById('station-suggestions');

  // Load full list of Belgian stations once
  await fetchAllStations();

  input.addEventListener('input', async e => {
    const val = input.value.trim();
    selectedStation = null;
    clearTimeout(suggestionsTimeout);
    if (val.length < 1) { suggDiv.innerHTML=''; suggDiv.style.display='none'; return; }
    suggestionsTimeout = setTimeout(() => {
      const norm = normalizeName(val);
      const suggestions = stationsAll.filter(s => s.norm.startsWith(norm)).slice(0, 20);
      showSuggestions(suggestions);
    }, 120);
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
    // Resolve selected station -> prefer explicit selection, else best match
    let st = selectedStation;
    if (!st || st.name !== typed) {
      const norm = normalizeName(typed);
      st = stationsAll.find(s => s.norm === norm) || stationsAll.find(s => s.norm.startsWith(norm));
    }
    if (!st) { resultsDiv.innerHTML = '<div class="alert alert-warning">Gare introuvable. Tapez les premières lettres (ex: "Namur").</div>'; return; }
    currentStationId = st.id;
    currentStationName = st.name;
    if (autoRefreshId) { clearInterval(autoRefreshId); autoRefreshId = null; }
    await loadLiveboard(currentStationId, resultsDiv, currentStationName);
    autoRefreshId = setInterval(() => {
      if (currentStationId) loadLiveboard(currentStationId, resultsDiv, currentStationName);
    }, 30000);
  });
});
