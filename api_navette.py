from flask import Blueprint, jsonify
from datetime import date
from models import ShuttleScheduleDay, ShuttleScheduleSlot, ShuttleRouteStop, ShuttleSettings

api_navette_bp = Blueprint('api_navette', __name__)

@api_navette_bp.route('/api/navette/schedule')
def navette_schedule():
    days = ShuttleScheduleDay.query.order_by(ShuttleScheduleDay.date).all()
    result = []
    for day in days:
        slots = [
            {
                'start_time': slot.start_time.strftime('%H:%M'),
                'end_time': slot.end_time.strftime('%H:%M'),
                'from_location': slot.from_location,
                'to_location': slot.to_location,
                'note': slot.note or ''
            }
            for slot in sorted(day.slots, key=lambda s: s.start_time)
        ]
        result.append({
            'date': day.date.isoformat(),
            'label': day.label,
            'note': day.note or '',
            'slots': slots
        })
    return jsonify(result)

@api_navette_bp.route('/api/navette/route')
def navette_route():
    stops = ShuttleRouteStop.query.order_by(ShuttleRouteStop.sequence.asc()).all()
    return jsonify([
        {
            'id': s.id,
            'name': s.name,
            'sequence': s.sequence,
            'dwell_minutes': s.dwell_minutes,
            'note': s.note or ''
        } for s in stops
    ])

@api_navette_bp.route('/api/navette/settings')
def navette_settings():
    settings = ShuttleSettings.query.first()
    if not settings:
        settings = ShuttleSettings(mean_leg_minutes=5)
    return jsonify({
        'mean_leg_minutes': settings.mean_leg_minutes,
        'loop_enabled': bool(getattr(settings, 'loop_enabled', False)),
        'bidirectional_enabled': bool(getattr(settings, 'bidirectional_enabled', False)),
        'constrain_to_today_slots': bool(getattr(settings, 'constrain_to_today_slots', False)),
    })

@api_navette_bp.route('/api/navette/today')
def navette_today():
    today = date.today()
    day = ShuttleScheduleDay.query.filter_by(date=today).first()
    if not day:
        return jsonify({'date': today.isoformat(), 'label': '', 'note': '', 'slots': []})
    slots = [
        {
            'start_time': slot.start_time.strftime('%H:%M'),
            'end_time': slot.end_time.strftime('%H:%M'),
            'from_location': slot.from_location,
            'to_location': slot.to_location,
            'note': slot.note or ''
        }
        for slot in sorted(day.slots, key=lambda s: s.start_time)
    ]
    return jsonify({'date': day.date.isoformat(), 'label': day.label, 'note': day.note or '', 'slots': slots})

# ---
# Pour intégrer ce module :
# 1. Dans ton app Flask principale, fais :
#    from api_navette import api_navette_bp
#    app.register_blueprint(api_navette_bp)
