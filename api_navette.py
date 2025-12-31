from flask import Blueprint, jsonify
from models import ShuttleScheduleDay, ShuttleScheduleSlot

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

# ---
# Pour intégrer ce module :
# 1. Dans ton app Flask principale, fais :
#    from api_navette import api_navette_bp
#    app.register_blueprint(api_navette_bp)
