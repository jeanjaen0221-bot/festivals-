document.addEventListener('DOMContentLoaded', async () => {
  const routeEl = document.getElementById('shuttle-route');
  const todayInfoEl = document.getElementById('shuttle-today');
  const todaySlotsEl = document.getElementById('shuttle-today-slots');
  const etaTableBody = document.querySelector('#shuttle-eta-table tbody');
  const paramsEl = document.getElementById('shuttle-params');
  const clockEl = document.getElementById('shuttle-clock');

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
    route.forEach((s) => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      const isBase = !!(settings && settings.display_base_stop_sequence && s.sequence === settings.display_base_stop_sequence);
      const left = document.createElement('div');
      left.className = 'd-flex flex-column';
      const title = document.createElement('div');
      title.innerHTML = `${s.name}${isBase ? ' <span class="badge bg-primary ms-2">Départ</span>' : ''}`;
      left.appendChild(title);
      if (s.note) {
        const note = document.createElement('small');
        note.className = 'text-muted';
        note.textContent = s.note;
        left.appendChild(note);
      }
      const right = document.createElement('span');
      right.className = 'badge bg-secondary';
      right.textContent = `+${s.dwell_minutes || 0} min`;
      li.appendChild(left);
      li.appendChild(right);
      routeEl.appendChild(li);
    });
  } else {
    routeEl.innerHTML = '<li class="list-group-item text-muted">Aucun arrêt configuré.</li>';
  }

  // Render today schedule
  try {
    if (today && today.date) {
      const label = today.label || new Date(today.date).toLocaleDateString();
      let header = `${label}${today.note ? ' — ' + today.note : ''}`;
      try {
        const now = new Date();
        const nowMin = (now.getHours() * 60) + now.getMinutes();
        const activeRange = findActiveSlotMinuteRange(today.slots, nowMin);
        if (activeRange) {
          header += ` — Service en cours: ${formatTime(minutesToDate(now, activeRange[0]))} - ${formatTime(minutesToDate(now, activeRange[1]))}`;
        }
      } catch (e2) {}
      todayInfoEl.textContent = header;
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

  try {
    const parts = [];
    parts.push(`~${settings.mean_leg_minutes || 5} min entre arrêts`);
    parts.push(`temps d'arrêt selon parcours`);
    parts.push(settings.loop_enabled ? 'mode boucle activé' : 'mode non bouclé');
    parts.push(settings.bidirectional_enabled ? 'bidirectionnel' : 'sens unique');
    if (settings.bidirectional_enabled) {
      const dirLabel = (settings.display_direction === 'backward' ? 'Retour' : 'Aller');
      parts.push(`affichage: ${dirLabel}`);
    }
    if (settings.display_base_stop_sequence) {
      parts.push(`départ séquence ${settings.display_base_stop_sequence}`);
    }
    if (settings.constrain_to_today_slots) {
      parts.push('limité aux créneaux du jour');
    }
    paramsEl.textContent = `Paramètres: ${parts.join(', ')}`;
  } catch (e) {}

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


  function computeAndRenderBoard() {
    if (!route || !route.length) return;
    const warningEl = document.getElementById('shuttle-eta-warning');
    if (warningEl) { warningEl.classList.add('d-none'); warningEl.textContent = ''; }

    // Base time: now
    const now = new Date();
    const startMin = (now.getHours() * 60) + now.getMinutes();

    // Determine direction from settings
    const forward = !(settings.bidirectional_enabled && (settings.display_direction === 'backward'));
    const ordered = forward ? route.slice().sort((a,b)=>a.sequence-b.sequence) : route.slice().sort((a,b)=>b.sequence-a.sequence);

    // Resolve start index from display_base_stop_sequence if provided
    let mappedStartIdx = 0;
    if (settings.display_base_stop_sequence) {
      const seq = settings.display_base_stop_sequence;
      const idx = ordered.findIndex(s => s.sequence === seq);
      if (idx >= 0) mappedStartIdx = idx;
    }

    // Constrain to today's active slot (optional)
    let activeRange = null;
    if (settings.constrain_to_today_slots && today && Array.isArray(today.slots)) {
      activeRange = findActiveSlotMinuteRange(today.slots, startMin);
      if (!activeRange && warningEl) {
        warningEl.textContent = "La navette est hors service à cette heure (hors des créneaux du jour).";
        warningEl.classList.remove('d-none');
        etaTableBody.innerHTML = '';
        return;
      }
    }

    const N = ordered.length;
    etaTableBody.innerHTML = '';
    let currentMin = startMin;
    for (let k = 0; k < N; k++) {
      const idx = settings.loop_enabled ? ((mappedStartIdx + k) % N) : (mappedStartIdx + k);
      if (!settings.loop_enabled && idx >= N) break;
      if (k > 0) currentMin += (settings.mean_leg_minutes || 5);
      const stop = ordered[idx];
      currentMin += (stop.dwell_minutes || 0);

      if (activeRange && currentMin > activeRange[1]) {
        if (warningEl) {
          warningEl.textContent = "Calcul limité à la fin du créneau en cours.";
          warningEl.classList.remove('d-none');
        }
        break;
      }

      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${stop.name}</td><td>${formatTime(minutesToDate(now, currentMin))}</td>`;
      etaTableBody.appendChild(tr);
    }
  }

  // Clock and auto-refresh
  function updateClock() {
    if (clockEl) {
      const now = new Date();
      clockEl.textContent = formatTime(now);
    }
  }
  updateClock();
  computeAndRenderBoard();
  setInterval(updateClock, 1000);
  setInterval(computeAndRenderBoard, 30000);
});
