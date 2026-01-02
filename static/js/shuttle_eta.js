document.addEventListener('DOMContentLoaded', async () => {
  const routeEl = document.getElementById('shuttle-route');
  const todayInfoEl = document.getElementById('shuttle-today');
  const todaySlotsEl = document.getElementById('shuttle-today-slots');
  const selectStopEl = document.getElementById('shuttle-current-stop');
  const startTimeEl = document.getElementById('shuttle-start-time');
  const etaTableBody = document.querySelector('#shuttle-eta-table tbody');
  const paramsEl = document.getElementById('shuttle-params');

  let route = [];
  let settings = { mean_leg_minutes: 5, loop_enabled: false, bidirectional_enabled: false, constrain_to_today_slots: false };
  let today = { slots: [] };

  try {
    const [routeResp, settingsResp, todayResp] = await Promise.all([
      fetch('/api/navette/route'),
      fetch('/api/navette/settings'),
      fetch('/api/navette/today')
    ]);
    route = await routeResp.json();
    settings = await settingsResp.json();
    today = await todayResp.json();
  } catch (e) {
    // fail silently
  }

  // Render route list
  if (Array.isArray(route) && route.length) {
    route.sort((a,b) => (a.sequence||0) - (b.sequence||0));
    routeEl.innerHTML = '';
    selectStopEl.innerHTML = '';
    route.forEach((s, idx) => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.innerHTML = `<span>${s.name}</span><span class="badge bg-secondary">+${s.dwell_minutes || 0} min</span>`;
      routeEl.appendChild(li);
      const opt = document.createElement('option');
      opt.value = idx;
      opt.textContent = `${s.sequence}. ${s.name}`;
      selectStopEl.appendChild(opt);
    });
  } else {
    routeEl.innerHTML = '<li class="list-group-item text-muted">Aucun arrêt configuré.</li>';
    selectStopEl.innerHTML = '<option value="0">—</option>';
  }

  // Render today schedule
  try {
    if (today && today.date) {
      const label = today.label || new Date(today.date).toLocaleDateString();
      todayInfoEl.textContent = `${label}${today.note ? ' — ' + today.note : ''}`;
      todaySlotsEl.innerHTML = '';
      (today.slots || []).forEach(slot => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        const note = slot.note ? `<span class="badge bg-info ms-2">${slot.note}</span>` : '';
        li.innerHTML = `<strong>${slot.start_time} - ${slot.end_time}</strong> · ${slot.from_location} ⇄ ${slot.to_location} ${note}`;
        todaySlotsEl.appendChild(li);
      });
    }
  } catch (e) {}

  // Default start time to current HH:mm
  try {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    startTimeEl.value = `${hh}:${mm}`;
  } catch (e) {}

  // Toggle direction selector depending on settings
  const dirGroup = document.getElementById('shuttle-direction-group');
  const dirSelect = document.getElementById('shuttle-direction');
  if (settings.bidirectional_enabled && dirGroup) {
    dirGroup.style.display = '';
  } else if (dirGroup) {
    dirGroup.style.display = 'none';
  }

  paramsEl.textContent = `Paramètres: ~${settings.mean_leg_minutes || 5} min entre arrêts, temps d'arrêt selon parcours, ` +
    `${settings.loop_enabled ? 'mode boucle activé' : 'mode non bouclé'}, ` +
    `${settings.bidirectional_enabled ? 'bidirectionnel' : 'sens unique'}` +
    `${settings.constrain_to_today_slots ? ' (limité aux créneaux du jour)' : ''}`;

  function addMinutes(base, minutes) {
    const d = new Date(base.getTime());
    d.setMinutes(d.getMinutes() + minutes);
    return d;
  }

  function formatTime(d) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function timeToMinutes(hhmm) {
    const [hh, mm] = (hhmm || '00:00').split(':').map(x => parseInt(x, 10) || 0);
    return (hh * 60) + mm;
  }

  function minutesToDate(base, minutesFromMidnight) {
    const d = new Date(base.getTime());
    const hh = Math.floor(minutesFromMidnight / 60) % 24;
    const mm = minutesFromMidnight % 60;
    d.setHours(hh, mm, 0, 0);
    return d;
  }

  function findActiveSlotMinuteRange(slots, startMin) {
    // slots: [{start_time:"HH:MM", end_time:"HH:MM"}]
    for (const s of (slots || [])) {
      const sMin = timeToMinutes(s.start_time);
      const eMin = timeToMinutes(s.end_time);
      if (sMin <= startMin && startMin <= eMin) return [sMin, eMin];
    }
    return null;
  }

  document.getElementById('shuttle-eta-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!route || !route.length) return;
    const startIdx = parseInt(selectStopEl.value || '0', 10) || 0;
    const timeVal = startTimeEl.value || '00:00';
    const warningEl = document.getElementById('shuttle-eta-warning');
    if (warningEl) { warningEl.classList.add('d-none'); warningEl.textContent = ''; }

    const base = new Date();
    const startMin = timeToMinutes(timeVal);

    // Constrain to today's active slot (optional)
    let activeRange = null;
    if (settings.constrain_to_today_slots && today && Array.isArray(today.slots)) {
      activeRange = findActiveSlotMinuteRange(today.slots, startMin);
      if (!activeRange && warningEl) {
        warningEl.textContent = "La navette est hors service à cette heure (hors des créneaux du jour).";
        warningEl.classList.remove('d-none');
        etaTableBody.innerHTML = '';
        return; // stop calculation
      }
    }

    // Determine order and starting index depending on direction
    const forward = !(settings.bidirectional_enabled && dirSelect && dirSelect.value === 'backward');
    const ordered = forward ? route.slice() : route.slice().reverse();
    const mappedStartIdx = forward ? startIdx : (route.length - 1 - startIdx);

    // Build list of N stops to display
    const N = ordered.length;
    etaTableBody.innerHTML = '';
    let currentMin = startMin;
    for (let k = 0; k < N; k++) {
      const idx = settings.loop_enabled ? ((mappedStartIdx + k) % N) : (mappedStartIdx + k);
      if (!settings.loop_enabled && idx >= N) break;
      if (k > 0) {
        currentMin += (settings.mean_leg_minutes || 5);
      }
      // dwell
      const stop = ordered[idx];
      currentMin += (stop.dwell_minutes || 0);

      // If constrained to slot, stop if we exceed the slot end
      if (activeRange && currentMin > activeRange[1]) {
        if (warningEl) {
          warningEl.textContent = "Calcul limité à la fin du créneau en cours.";
          warningEl.classList.remove('d-none');
        }
        break;
      }

      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${stop.name}</td><td>${formatTime(minutesToDate(base, currentMin))}</td>`;
      etaTableBody.appendChild(tr);
    }
  });
});
