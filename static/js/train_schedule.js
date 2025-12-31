// JS moderne pour la page horaires de train (iRail)
let suggestionsTimeout = null;

function showSuggestions(list) {
    const suggDiv = document.getElementById('station-suggestions');
    suggDiv.innerHTML = '';
    if (!list.length) {
        suggDiv.style.display = 'none';
        return;
    }
    list.forEach(station => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'list-group-item list-group-item-action';
        el.textContent = station.name;
        el.onclick = () => {
            document.getElementById('station-input').value = station.name;
            suggDiv.innerHTML = '';
            suggDiv.style.display = 'none';
        };
        suggDiv.appendChild(el);
    });
    suggDiv.style.display = 'block';
}

async function fetchStationSuggestions(query) {
    if (!query) return [];
    // Utilise l'API iRail pour suggestions de gares
    const url = `https://api.irail.be/stations/?format=json&lang=fr&query=${encodeURIComponent(query)}`;
    try {
        const resp = await fetch(url);
        const data = await resp.json();
        if (data.station) {
            return data.station.slice(0, 8); // max 8 suggestions
        }
    } catch (e) {}
    return [];
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('station-input');
    const form = document.getElementById('station-search-form');
    const resultsDiv = document.getElementById('train-results');
    const suggDiv = document.getElementById('station-suggestions');

    input.addEventListener('input', async e => {
        const val = input.value.trim();
        clearTimeout(suggestionsTimeout);
        if (val.length < 2) {
            suggDiv.innerHTML = '';
            suggDiv.style.display = 'none';
            return;
        }
        suggestionsTimeout = setTimeout(async () => {
            const suggestions = await fetchStationSuggestions(val);
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
        const station = input.value.trim();
        if (!station) return;
        resultsDiv.innerHTML = '<div class="text-center py-4"><div class="spinner-border" role="status"></div> Chargement...</div>';
        try {
            const resp = await fetch(`/api/trains/liveboard?station=${encodeURIComponent(station)}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            if (!data.departures || !data.departures.departure || !data.departures.departure.length) {
                resultsDiv.innerHTML = '<div class="alert alert-warning">Aucun départ trouvé pour cette gare.</div>';
                return;
            }
            let html = `<h2 class='mb-3'><i class='bi bi-clock-history'></i> Prochains départs de <b>${data.station}</b></h2>`;
            html += `<div class='table-responsive'><table class='table table-striped table-hover'><thead><tr><th>Heure</th><th>Destination</th><th>Voie</th><th>Type</th><th>Retard</th></tr></thead><tbody>`;
            data.departures.departure.forEach(dep => {
                const time = new Date(dep.time * 1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
                html += `<tr><td>${time}</td><td>${dep.station}</td><td>${dep.platform || '-'}</td><td>${dep.vehicle.replace('BE.NMBS.', '')}</td><td>${dep.delay ? '+'+Math.round(dep.delay/60)+' min' : ''}</td></tr>`;
            });
            html += '</tbody></table></div>';
            resultsDiv.innerHTML = html;
        } catch (err) {
            resultsDiv.innerHTML = `<div class='alert alert-danger'>Erreur : ${err.message || 'Impossible de récupérer les horaires.'}</div>`;
        }
    });
});
