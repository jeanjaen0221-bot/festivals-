from flask import Blueprint, jsonify, request
import requests
from datetime import datetime
import time
import unicodedata

bp = Blueprint('trains', __name__, url_prefix='/api/trains')

STATIONS_CACHE = {
    'data': None,
    'ts': 0,
    'lang': None,
}

# Simple in-memory cache for liveboard/departures responses to avoid hammering iRail
LIVEBOARD_CACHE = {}

# As recommended by iRail docs, set a descriptive User-Agent to facilitate communication
IRAIL_HEADERS = {
    'User-Agent': 'FestivalsNavette/1.0 (https://example.org; contact@example.org)'
}

def _cache_get(key: str):
    try:
        item = LIVEBOARD_CACHE.get(key)
        if not item:
            return None
        ts, ttl, data = item
        if (time.time() - ts) <= ttl:
            return data
        else:
            LIVEBOARD_CACHE.pop(key, None)
    except Exception:
        pass
    return None

def _cache_set(key: str, data, ttl: int):
    try:
        LIVEBOARD_CACHE[key] = (time.time(), ttl, data)
    except Exception:
        pass

def _normalize(s: str) -> str:
    if not s:
        return ''
    s2 = unicodedata.normalize('NFD', s)
    s2 = ''.join(c for c in s2 if unicodedata.category(c) != 'Mn')
    s2 = s2.lower().replace("'", ' ').replace('-', ' ').replace('’', ' ')
    s2 = ' '.join(s2.split())
    return s2

def get_stations(lang: str = 'fr'):
    now = time.time()
    if STATIONS_CACHE['data'] is not None and (now - STATIONS_CACHE['ts'] < 6*3600) and STATIONS_CACHE['lang'] == lang:
        return STATIONS_CACHE['data']
    url = 'https://api.irail.be/stations/'
    params = {'format': 'json', 'lang': lang}
    r = requests.get(url, params=params, headers=IRAIL_HEADERS, timeout=10)
    r.raise_for_status()
    js = r.json()
    stations = []
    for st in js.get('station', []) or []:
        # iRail typically returns { name, id, locationX, locationY, ... }
        x = st.get('locationX'); y = st.get('locationY')
        try:
            x = float(x) if x is not None else None
            y = float(y) if y is not None else None
        except Exception:
            x = None; y = None
        stations.append({
            'id': st.get('id') or st.get('@id') or st.get('uri') or st.get('code') or '',
            'name': st.get('name') or '',
            'standardname': st.get('standardname') or st.get('name') or '',
            'x': x,
            'y': y,
        })
    # enrich with normalized name
    for st in stations:
        st['norm'] = _normalize(st['name'] or st['standardname'])
        # Belgian bounding box approx: lon 2.5..6.5, lat 49.3..51.6
        if st['x'] is not None and st['y'] is not None:
            st['is_be'] = (2.2 <= st['x'] <= 6.6) and (49.2 <= st['y'] <= 51.7)
        else:
            st['is_be'] = False
    STATIONS_CACHE.update({'data': stations, 'ts': now, 'lang': lang})
    return stations

@bp.route('/stations')
def stations_endpoint():
    try:
        lang = request.args.get('lang', 'fr')
        q = request.args.get('q', '')
        stations = get_stations(lang)
        only_be = request.args.get('only_be') in ('1','true','yes','on')
        if q:
            nq = _normalize(q)
            base = [s for s in stations if (s['is_be'] or not only_be)]
            starts = [s for s in base if s['norm'].startswith(nq)]
            contains = [s for s in base if (nq in s['norm'] and not s['norm'].startswith(nq))]
            res = starts + contains
        else:
            res = [s for s in stations if (s['is_be'] or not only_be)]
        # Return lean payload
        return jsonify({'stations': [{'id': s['id'], 'name': s['name']} for s in res]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
 

# CORS pour API Railway
@bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response


@bp.route('/departures')
def get_departures():
    try:
        from flask import request
        # Paramètres de base
        from_station = request.args.get('from', 'Floreffe')
        destinations = ['Jambe', 'Wavre']
        all_connections = []
        for dest in destinations:
            params = {
                'from': from_station,
                'to': dest,
                'format': 'json',
                'results': 5,
                'timesel': 'departure',  # conforme à la doc
                'lang': 'fr',
            }
            response = requests.get('https://api.irail.be/connections/', params=params, headers=IRAIL_HEADERS, timeout=6)
            response.raise_for_status()
            data = response.json() if response.headers.get('Content-Type','').startswith('application/json') else {}
            if data.get('connection'):
                all_connections.extend(data['connection'])
        # Séparer les connexions par destination
        jambe = [c for c in all_connections if c.get('arrival', {}).get('station', '').lower() == 'jambe']
        wavre = [c for c in all_connections if c.get('arrival', {}).get('station', '').lower() == 'wavre']
        # Intercaler (alterner) les deux directions
        alternated = []
        i, j = 0, 0
        while i < len(jambe) or j < len(wavre):
            if i < len(jambe):
                alternated.append(jambe[i])
                i += 1
            if j < len(wavre):
                alternated.append(wavre[j])
                j += 1
        # Enrichir les données avec les retards (départs, arrivées, correspondances)
        def enrich_conn(conn):
            dep = conn.get('departure', {})
            arr = conn.get('arrival', {})
            vias = conn.get('vias', {}).get('via', []) if conn.get('vias') else []
            return {
                'departure_time': dep.get('time'),
                'departure_delay': int(dep.get('delay', 0)),
                'departure_station': dep.get('station'),
                'departure_platform': dep.get('platform'),
                'arrival_time': arr.get('time'),
                'arrival_delay': int(arr.get('delay', 0)),
                'arrival_station': arr.get('station'),
                'vehicle': dep.get('vehicleinfo', {}).get('shortname', ''),
                'vias': [
                    {
                        'station': v.get('station'),
                        'time': v.get('time'),
                        'delay': int(v.get('delay', 0)),
                        'platform': v.get('platform'),
                        'vehicle': v.get('vehicle', '')
                    } for v in vias
                ]
            }
        alternated_enriched = [enrich_conn(c) for c in alternated]
        return jsonify({'connection': alternated_enriched})
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': 'Impossible de récupérer les horaires',
            'details': str(e)
        }), 500

@bp.route('/liveboard')
def get_liveboard():
    station = request.args.get('station', 'Wavre')
    fast = request.args.get('fast', 'true')
    time_param = request.args.get('time')
    date_param = request.args.get('date')
    try:
        # If station looks like a plain name (no NMBS id), try to resolve to id for robustness
        if station and ('irail.be/stations' not in station and 'NMBS' not in station and not station.isdigit()):
            try:
                # language default fr for name resolution
                sts = get_stations('fr')
                n = _normalize(station)
                # Prefer startswith then contains
                match = next((s for s in sts if s['norm'].startswith(n)), None)
                if not match:
                    match = next((s for s in sts if n in s['norm']), None)
                if match and match.get('id'):
                    station = match['id']
            except Exception:
                pass
        def _build_station_params(st_value: str):
            # iRail supports either 'station' (name) or 'id' (NMBS id/URI)
            if st_value and (st_value.startswith('BE.NMBS.') or 'irail.be/stations' in st_value):
                return {'id': st_value}
            return {'station': st_value}

        def fetch_liveboard_once(use_fast: str):
            p = {
                'format': 'json',
                'lang': 'fr',
                'fast': use_fast,
            }
            p.update(_build_station_params(station))
            if time_param: p['time'] = time_param
            if date_param: p['date'] = date_param
            cache_key = f"lb|{use_fast}|{p.get('id') or p.get('station')}|{p.get('time','now')}|{p.get('date','')}"
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached
            try:
                r = requests.get('https://api.irail.be/liveboard/', params=p, headers=IRAIL_HEADERS, timeout=6)
                if r.status_code == 429:
                    # bubble up a rate-limit signal
                    return {'_rate_limited': True, 'retry_after': int(r.headers.get('Retry-After', '30') or 30)}
                r.raise_for_status()
            except requests.exceptions.HTTPError as he:
                if getattr(he, 'response', None) is not None and he.response.status_code == 429:
                    return {'_rate_limited': True, 'retry_after': int(he.response.headers.get('Retry-After', '30') or 30)}
                raise
            js = r.json() if r.headers.get('Content-Type','').startswith('application/json') else {}
            items = []
            for dep in js.get('departures', {}).get('departure', []) or []:
                items.append({
                    'time': dep.get('time'),
                    'delay': int(dep.get('delay', 0) or 0),
                    'vehicle': dep.get('vehicle', ''),
                    'platform': dep.get('platform', ''),
                    'destination': dep.get('station', ''),
                    'canceled': str(dep.get('canceled', '0')) == '1'
                })
            # Cache: 'now' ttl ~ 20s; historical queries ttl longer
            _cache_set(cache_key, items, 20 if not time_param else 60)
            return items

        def fetch_departures_api():
            p2 = {
                'format': 'json',
                'lang': 'fr',
            }
            p2.update(_build_station_params(station))
            if time_param: p2['time'] = time_param
            if date_param: p2['date'] = date_param
            cache_key = f"dep|{p2.get('id') or p2.get('station')}|{p2.get('time','now')}|{p2.get('date','')}"
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached
            try:
                r2 = requests.get('https://api.irail.be/departures/', params=p2, headers=IRAIL_HEADERS, timeout=6)
                if r2.status_code == 429:
                    return {'_rate_limited': True, 'retry_after': int(r2.headers.get('Retry-After', '30') or 30)}
                r2.raise_for_status()
            except requests.exceptions.HTTPError as he:
                if getattr(he, 'response', None) is not None and he.response.status_code == 429:
                    return {'_rate_limited': True, 'retry_after': int(he.response.headers.get('Retry-After', '30') or 30)}
                raise
            js2 = r2.json() if r2.headers.get('Content-Type','').startswith('application/json') else {}
            items2 = []
            for dep in js2.get('departures', {}).get('departure', []) or []:
                items2.append({
                    'time': dep.get('time'),
                    'delay': int(dep.get('delay', 0) or 0),
                    'vehicle': dep.get('vehicle', ''),
                    'platform': dep.get('platform', ''),
                    'destination': dep.get('station', ''),
                    'canceled': str(dep.get('canceled', '0')) == '1'
                })
            _cache_set(cache_key, items2, 20 if not time_param else 60)
            return items2

        # Prefer departures API first (it returns next trains)
        departures = []
        try:
            departures = fetch_departures_api()
            if isinstance(departures, dict) and departures.get('_rate_limited'):
                return jsonify({'error': 'rate_limited', 'retry_after': departures.get('retry_after', 30)}), 429
        except Exception:
            departures = []
        # Fallback to liveboard fast/false
        if not departures:
            try:
                departures = fetch_liveboard_once(fast)
                if isinstance(departures, dict) and departures.get('_rate_limited'):
                    return jsonify({'error': 'rate_limited', 'retry_after': departures.get('retry_after', 30)}), 429
            except Exception:
                departures = []
        if not departures and fast == 'true':
            try:
                departures = fetch_liveboard_once('false')
                if isinstance(departures, dict) and departures.get('_rate_limited'):
                    return jsonify({'error': 'rate_limited', 'retry_after': departures.get('retry_after', 30)}), 429
            except Exception:
                departures = []
        # Final fallback: departures again without time/date
        if not departures and (time_param or date_param):
            try:
                # Clear time/date to get "now" board
                time_param = None; date_param = None
                departures = fetch_departures_api()
            except Exception:
                pass
        return jsonify({'departures': departures})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
