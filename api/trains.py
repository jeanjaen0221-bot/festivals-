from flask import Blueprint, jsonify
import requests
from datetime import datetime

bp = Blueprint('trains', __name__, url_prefix='/api/trains')

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
            response = requests.get('https://api.irail.be/connections/', params=params, timeout=6)
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
    from flask import request
    station = request.args.get('station', 'Wavre')
    try:
        params = {
            'station': station,
            'format': 'json',
            'lang': 'fr',
            'fast': 'true',  # recommandé par iRail pour les liveboards
        }
        resp = requests.get('https://api.irail.be/liveboard/', params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json() if resp.headers.get('Content-Type','').startswith('application/json') else {}
        departures = []
        for dep in data.get('departures', {}).get('departure', []) or []:
            departures.append({
                'time': dep.get('time'),
                'delay': int(dep.get('delay', 0) or 0),
                'vehicle': dep.get('vehicle', ''),
                'platform': dep.get('platform', ''),
                'destination': dep.get('station', ''),
                'canceled': str(dep.get('canceled', '0')) == '1'
            })
        return jsonify({'departures': departures})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
