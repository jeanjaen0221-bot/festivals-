document.addEventListener('DOMContentLoaded', async () => {
  const routeEl = document.getElementById('shuttle-route');
  const todayInfoEl = document.getElementById('shuttle-today');
  const todaySlotsEl = document.getElementById('shuttle-today-slots');
  const etaTableBody = document.querySelector('#shuttle-eta-table tbody');
  const paramsEl = document.getElementById('shuttle-params');
  const clockEl = document.getElementById('shuttle-clock');
  const serviceBadgeEl = document.getElementById('shuttle-service-badge');
  const lineStopsEl = document.getElementById('shuttle-stops');
  const ledEl = document.querySelector('.shuttle-led');
  const trackEl = document.querySelector('.shuttle-line-track');

  let route = [];
  let settings = { mean_leg_minutes: 5, loop_enabled: false, bidirectional_enabled: false, constrain_to_today_slots: false };
  let today = { slots: [] };
  let lastRenderKey = '';
  let lastOrdered = [];
  let lastMappedStartIdx = 0;

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

  function renderShuttleLineStops(ordered, forward, baseSeq) {
    if (!lineStopsEl) return;
    lineStopsEl.innerHTML = '';
    const arr = forward ? ordered : ordered.slice().reverse();
    arr.forEach((s) => {
      const stop = document.createElement('div');
      stop.className = 'shuttle-stop';
      const dot = document.createElement('div');
      dot.className = 'dot';
      const label = document.createElement('div');
      label.className = 'label';
      const isBase = !!(baseSeq && s.sequence === baseSeq);
      label.innerHTML = `${s.name}${isBase ? ' <span class="badge bg-primary">Départ</span>' : ''}`;
      stop.appendChild(dot);
      stop.appendChild(label);
      lineStopsEl.appendChild(stop);
    });
  }

  function updateLEDPosition(ordered, mappedStartIdx) {
    if (!ledEl || !trackEl || !(ordered && ordered.length)) return;
    const now = new Date();
    const nowMin = (now.getHours() * 60) + now.getMinutes();
    if (settings.constrain_to_today_slots && today && Array.isArray(today.slots)) {
      const activeRange = findActiveSlotMinuteRange(today.slots, nowMin);
      if (!activeRange) { ledEl.style.opacity = '0'; return; } else { ledEl.style.opacity = '1'; }
    }
    const trackWidth = trackEl.getBoundingClientRect().width;
    let frac = 0;
    if (settings.loop_enabled) {
      const leg = (settings.mean_leg_minutes || 5);
      const N = ordered.length;
      const segments = [];
      for (let k = 0; k < N; k++) {
        const s = ordered[(mappedStartIdx + k) % N];
        const dwell = (s.dwell_minutes || 0);
        if (dwell > 0) segments.push({len: dwell});
        segments.push({len: leg});
      }
      const cycle = segments.reduce((a,b)=>a + (b.len||0), 0) || 1;
      const t = ((now.getHours() * 60) + now.getMinutes()) % cycle;
      let acc = 0; let done = false;
      for (const seg of segments) {
        if (t <= acc + seg.len) { frac = (acc + (t - acc)) / cycle; done = true; break; }
        acc += seg.len;
      }
      if (!done) frac = 0;
    } else {
      frac = 0;
    }
    const x = Math.max(0, Math.min(trackWidth, frac * trackWidth));
    ledEl.style.transform = `translateX(${x}px)`;
  }

  // Render route list (optional: only if list element exists)
  if (Array.isArray(route) && route.length) {
    route.sort((a,b) => (a.sequence||0) - (b.sequence||0));
    if (routeEl) {
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
    }
    try {
      const eff0 = getEffectiveDirectionAndBase();
      renderShuttleLineStops(route.slice().sort((a,b)=>a.sequence-b.sequence), eff0.forward, eff0.baseSeq);
    } catch (e) {}
  } else {
    if (routeEl) routeEl.innerHTML = '<li class="list-group-item text-muted">Aucun arrêt configuré.</li>';
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
        // Update service badge for volunteers
        try {
          if (serviceBadgeEl) {
            serviceBadgeEl.className = 'badge rounded-pill ms-2';
            if (activeRange) {
              serviceBadgeEl.classList.add('bg-success');
              serviceBadgeEl.textContent = 'En service';
            } else {
              // Find next start
              let nextStart = null;
              (today.slots || []).forEach(s => {
                const sMin = timeToMinutes(s.start_time);
                if (sMin > nowMin && (nextStart === null || sMin < nextStart)) nextStart = sMin;
              });
              if (nextStart !== null) {
                serviceBadgeEl.classList.add('bg-warning', 'text-dark');
                serviceBadgeEl.textContent = `Reprise à ${formatTime(minutesToDate(now, nextStart))}`;
              } else {
                serviceBadgeEl.classList.add('bg-secondary');
                serviceBadgeEl.textContent = 'Hors service';
              }
            }
          }
        } catch (e3) {}
        if (activeRange) {
          header += ` — Service en cours: ${formatTime(minutesToDate(now, activeRange[0]))} - ${formatTime(minutesToDate(now, activeRange[1]))}`;
        }
      } catch (e2) {}
      todayInfoEl.textContent = header;
      todaySlotsEl.innerHTML = '';
      // Determine next slot for concise badge
      const now2 = new Date();
      const nowMin2 = (now2.getHours() * 60) + now2.getMinutes();
      let nextStartMin = null;
      (today.slots || []).forEach(s => {
        const sMin = timeToMinutes(s.start_time);
        if (sMin > nowMin2 && (nextStartMin === null || sMin < nextStartMin)) nextStartMin = sMin;
      });
      (today.slots || []).forEach(slot => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        const note = slot.note ? `<span class="badge bg-info ms-2">${slot.note}</span>` : '';
        const sMin = timeToMinutes(slot.start_time);
        const eMin = timeToMinutes(slot.end_time);
        let statusBadge = '';
        if (sMin <= nowMin2 && nowMin2 <= eMin) {
          statusBadge = ' <span class="badge bg-success ms-2">En cours</span>';
        } else if (nextStartMin !== null && sMin === nextStartMin) {
          statusBadge = ' <span class="badge bg-warning text-dark ms-2">À venir</span>';
        }
        li.innerHTML = `<strong>${slot.start_time} - ${slot.end_time}</strong> · ${slot.from_location} ⇄ ${slot.to_location}${statusBadge} ${note}`;
        todaySlotsEl.appendChild(li);
      });
    }
  } catch (e) {}

  if (paramsEl) {
    try { paramsEl.textContent = ''; } catch (e) {}
  }

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

  function getEffectiveDirectionAndBase() {
    let forward = !(settings.bidirectional_enabled && (settings.display_direction === 'backward'));
    let baseSeq = settings.display_base_stop_sequence || null;

    try {
      const now = new Date();
      const nowMin = (now.getHours() * 60) + now.getMinutes();
      const activeRange = findActiveSlotMinuteRange((today && today.slots) || [], nowMin);
      if (settings && settings.constrain_to_today_slots && activeRange) {
        let activeSlot = null;
        for (const s of (today.slots || [])) {
          const sMin = timeToMinutes(s.start_time);
          const eMin = timeToMinutes(s.end_time);
          if (sMin <= nowMin && nowMin <= eMin) { activeSlot = s; break; }
        }
        if (activeSlot && Array.isArray(route) && route.length) {
          const asc = route.slice().sort((a,b)=> (a.sequence||0) - (b.sequence||0));
          const idxFrom = asc.findIndex(st => st.name === activeSlot.from_location);
          const idxTo = asc.findIndex(st => st.name === activeSlot.to_location);
          if (idxFrom >= 0) { baseSeq = asc[idxFrom].sequence; }
          if (settings && settings.bidirectional_enabled && idxFrom >= 0 && idxTo >= 0 && idxFrom !== idxTo) {
            forward = (idxTo > idxFrom);
          }
        }
      }
    } catch (e) { /* ignore */ }

    return { forward, baseSeq };
  }


  function computeAndRenderBoard() {
    if (!route || !route.length) return;
    const warningEl = document.getElementById('shuttle-eta-warning');
    if (warningEl) { warningEl.classList.add('d-none'); warningEl.textContent = ''; }

    // Base time: now
    const now = new Date();
    const startMin = (now.getHours() * 60) + now.getMinutes();

    // Determine direction from settings
    const eff = getEffectiveDirectionAndBase();
    const forward = eff.forward;
    const baseSeqEff = eff.baseSeq;
    const ordered = forward ? route.slice().sort((a,b)=>a.sequence-b.sequence) : route.slice().sort((a,b)=>b.sequence-a.sequence);

    // Resolve start index from display_base_stop_sequence if provided
    let mappedStartIdx = 0;
    if (baseSeqEff) {
      const seq = baseSeqEff;
      const idx = ordered.findIndex(s => s.sequence === seq);
      if (idx >= 0) mappedStartIdx = idx;
    }

    try {
      const key = JSON.stringify({dir: forward ? 'f' : 'b', base: baseSeqEff || null, seqs: ordered.map(s=>s.sequence)});
      if (key !== lastRenderKey) { renderShuttleLineStops(ordered, forward, baseSeqEff); lastRenderKey = key; }
    } catch (e) {}
    lastOrdered = ordered; lastMappedStartIdx = mappedStartIdx;
    try { updateLEDPosition(ordered, mappedStartIdx); } catch (e) {}

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
      if (k === 0) { tr.classList.add('table-primary'); }
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
    try { if (lastOrdered && lastOrdered.length) updateLEDPosition(lastOrdered, lastMappedStartIdx); } catch (e) {}
  }
  updateClock();
  computeAndRenderBoard();
  setInterval(updateClock, 1000);
  setInterval(computeAndRenderBoard, 30000);
});
