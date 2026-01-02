from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from admin import admin_required
from app import db
from models import ShuttleScheduleDay, ShuttleScheduleSlot, ShuttleRouteStop, ShuttleSettings
from forms import ShuttleScheduleDayForm, ShuttleScheduleSlotForm, ShuttleRouteStopForm, ShuttleSettingsForm
from datetime import datetime

bp = Blueprint('admin_shuttle', __name__, url_prefix='/admin/shuttle')

@bp.route('/')
@login_required
@admin_required
def shuttle_schedule():
    days = ShuttleScheduleDay.query.order_by(ShuttleScheduleDay.date.asc()).all()
    return render_template('admin/shuttle_schedule.html', days=days)

# Days
@bp.route('/days/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_shuttle_day():
    form = ShuttleScheduleDayForm()
    if form.validate_on_submit():
        day = ShuttleScheduleDay(date=form.date.data, label=form.label.data.strip(), note=form.note.data or None)
        db.session.add(day)
        db.session.commit()
        flash('Jour navette ajouté.', 'success')
        return redirect(url_for('admin_shuttle.shuttle_schedule'))
    return render_template('admin/shuttle_day_form.html', form=form, title='Ajouter un jour')

@bp.route('/days/<int:day_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_shuttle_day(day_id):
    day = ShuttleScheduleDay.query.get_or_404(day_id)
    form = ShuttleScheduleDayForm(obj=day)
    if form.validate_on_submit():
        day.date = form.date.data
        day.label = form.label.data.strip()
        day.note = form.note.data or None
        db.session.commit()
        flash('Jour navette mis à jour.', 'success')
        return redirect(url_for('admin_shuttle.shuttle_schedule'))
    return render_template('admin/shuttle_day_form.html', form=form, title='Modifier le jour')

@bp.route('/days/<int:day_id>/delete')
@login_required
@admin_required
def delete_shuttle_day(day_id):
    day = ShuttleScheduleDay.query.get_or_404(day_id)
    db.session.delete(day)
    db.session.commit()
    flash('Jour navette supprimé.', 'success')
    return redirect(url_for('admin_shuttle.shuttle_schedule'))

# Slots
@bp.route('/days/<int:day_id>/slots/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_shuttle_slot(day_id):
    day = ShuttleScheduleDay.query.get_or_404(day_id)
    form = ShuttleScheduleSlotForm()
    if form.validate_on_submit():
        slot = ShuttleScheduleSlot(
            day=day,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            from_location=form.from_location.data.strip(),
            to_location=form.to_location.data.strip(),
            note=form.note.data or None,
        )
        db.session.add(slot)
        db.session.commit()
        flash('Créneau ajouté.', 'success')
        return redirect(url_for('admin_shuttle.shuttle_schedule'))
    return render_template('admin/shuttle_slot_form.html', form=form, title='Ajouter un créneau')

@bp.route('/slots/<int:slot_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_shuttle_slot(slot_id):
    slot = ShuttleScheduleSlot.query.get_or_404(slot_id)
    form = ShuttleScheduleSlotForm(obj=slot)
    if form.validate_on_submit():
        slot.start_time = form.start_time.data
        slot.end_time = form.end_time.data
        slot.from_location = form.from_location.data.strip()
        slot.to_location = form.to_location.data.strip()
        slot.note = form.note.data or None
        db.session.commit()
        flash('Créneau mis à jour.', 'success')
        return redirect(url_for('admin_shuttle.shuttle_schedule'))
    return render_template('admin/shuttle_slot_form.html', form=form, title='Modifier le créneau')

@bp.route('/slots/<int:slot_id>/delete')
@login_required
@admin_required
def delete_shuttle_slot(slot_id):
    slot = ShuttleScheduleSlot.query.get_or_404(slot_id)
    db.session.delete(slot)
    db.session.commit()
    flash('Créneau supprimé.', 'success')
    return redirect(url_for('admin_shuttle.shuttle_schedule'))

# Route (parcours)
@bp.route('/route')
@login_required
@admin_required
def shuttle_route():
    stops = ShuttleRouteStop.query.order_by(ShuttleRouteStop.sequence.asc()).all()
    return render_template('admin/shuttle_route.html', stops=stops)

@bp.route('/route/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_route_stop():
    form = ShuttleRouteStopForm()
    if form.validate_on_submit():
        stop = ShuttleRouteStop(
            name=form.name.data.strip(),
            sequence=form.sequence.data,
            dwell_minutes=form.dwell_minutes.data,
            note=form.note.data or None,
        )
        db.session.add(stop)
        db.session.commit()
        flash("Arrêt ajouté.", 'success')
        return redirect(url_for('admin_shuttle.shuttle_route'))
    return render_template('admin/shuttle_route_form.html', form=form, title='Ajouter un arrêt')

@bp.route('/route/<int:stop_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_route_stop(stop_id):
    stop = ShuttleRouteStop.query.get_or_404(stop_id)
    form = ShuttleRouteStopForm(obj=stop)
    if form.validate_on_submit():
        stop.name = form.name.data.strip()
        stop.sequence = form.sequence.data
        stop.dwell_minutes = form.dwell_minutes.data
        stop.note = form.note.data or None
        db.session.commit()
        flash('Arrêt mis à jour.', 'success')
        return redirect(url_for('admin_shuttle.shuttle_route'))
    return render_template('admin/shuttle_route_form.html', form=form, title='Modifier un arrêt')

@bp.route('/route/<int:stop_id>/delete')
@login_required
@admin_required
def delete_route_stop(stop_id):
    stop = ShuttleRouteStop.query.get_or_404(stop_id)
    db.session.delete(stop)
    db.session.commit()
    flash('Arrêt supprimé.', 'success')
    return redirect(url_for('admin_shuttle.shuttle_route'))

# Réglages navette
@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def shuttle_settings():
    settings = ShuttleSettings.query.first()
    if not settings:
        settings = ShuttleSettings(mean_leg_minutes=5)
        db.session.add(settings)
        db.session.commit()
    form = ShuttleSettingsForm(obj=settings)
    if form.validate_on_submit():
        settings.mean_leg_minutes = form.mean_leg_minutes.data
        settings.loop_enabled = bool(form.loop_enabled.data)
        settings.bidirectional_enabled = bool(form.bidirectional_enabled.data)
        settings.constrain_to_today_slots = bool(form.constrain_to_today_slots.data)
        db.session.commit()
        flash('Réglages navette enregistrés.', 'success')
        return redirect(url_for('admin_shuttle.shuttle_settings'))
    return render_template('admin/shuttle_settings.html', form=form)
