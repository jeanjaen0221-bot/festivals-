from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
from app import db
import sqlalchemy as sa
from models import (User, Conversation, ConversationParticipant, Message,
                    ConvType, ParticipantRole)

bp_msg = Blueprint('messaging', __name__, url_prefix='/messages')


def _get_participant(conv_id, user_id):
    return ConversationParticipant.query.filter_by(
        conversation_id=conv_id, user_id=user_id).first()


def _mark_read(conv_id, user_id):
    part = _get_participant(conv_id, user_id)
    if part:
        part.last_read_at = datetime.utcnow()
        db.session.commit()


def total_unread(user_id):
    """Nombre total de messages non lus — une seule requête SQL agrégée."""
    result = db.session.execute(
        sa.text('''
            SELECT COUNT(m.id)
            FROM messages m
            JOIN conversation_participants cp
                ON cp.conversation_id = m.conversation_id
                AND cp.user_id = :uid
            JOIN conversations c
                ON c.id = m.conversation_id
                AND c.is_archived = false
            WHERE m.is_deleted = false
              AND m.sender_id != :uid
              AND (cp.last_read_at IS NULL OR m.created_at > cp.last_read_at)
        '''),
        {'uid': user_id}
    ).scalar()
    return int(result or 0)


# ── Inbox ────────────────────────────────────────────────────────────────────

@bp_msg.route('/')
@login_required
def inbox():
    uid = current_user.id

    parts = (ConversationParticipant.query
             .filter_by(user_id=uid)
             .join(Conversation)
             .filter(Conversation.is_archived == False)
             .all())

    if not parts:
        all_users = User.query.filter(User.id != uid).order_by(User.first_name).all()
        return render_template('messages/inbox.html', convs=[], all_users=all_users)

    conv_ids = [p.conversation_id for p in parts]

    last_msg_sq = (db.session.query(
        Message.conversation_id,
        sa.func.max(Message.id).label('max_id')
    ).filter(
        Message.conversation_id.in_(conv_ids),
        Message.is_deleted == False
    ).group_by(Message.conversation_id).subquery())

    last_msgs_rows = (db.session.query(Message)
                      .join(last_msg_sq, Message.id == last_msg_sq.c.max_id)
                      .all())
    last_msgs = {m.conversation_id: m for m in last_msgs_rows}

    unread_rows = db.session.execute(
        sa.text('''
            SELECT m.conversation_id, COUNT(m.id) as cnt
            FROM messages m
            JOIN conversation_participants cp
                ON cp.conversation_id = m.conversation_id AND cp.user_id = :uid
            WHERE m.conversation_id = ANY(:ids)
              AND m.is_deleted = false
              AND m.sender_id != :uid
              AND (cp.last_read_at IS NULL OR m.created_at > cp.last_read_at)
            GROUP BY m.conversation_id
        '''),
        {'uid': uid, 'ids': conv_ids}
    ).fetchall()
    unread_map = {row[0]: row[1] for row in unread_rows}

    convs = []
    for p in parts:
        conv = p.conversation
        last_msg = last_msgs.get(conv.id)
        convs.append({
            'conv': conv,
            'unread': unread_map.get(conv.id, 0),
            'last_msg': last_msg,
            'display_name': conv.display_name(uid),
            'last_ts': last_msg.created_at if last_msg else conv.created_at,
        })
    convs.sort(key=lambda x: x['last_ts'], reverse=True)
    all_users = User.query.filter(User.id != uid).order_by(User.first_name).all()
    return render_template('messages/inbox.html', convs=convs, all_users=all_users)


# ── Nouvelle conv directe ────────────────────────────────────────────────────

@bp_msg.route('/direct/new', methods=['POST'])
@login_required
def new_direct():
    target_id = request.form.get('target_user_id', type=int)
    if not target_id or target_id == current_user.id:
        flash("Destinataire invalide.", "danger")
        return redirect(url_for('messaging.inbox'))
    target = User.query.get_or_404(target_id)

    existing = (Conversation.query
                .filter_by(type=ConvType.DIRECT, is_archived=False)
                .join(ConversationParticipant)
                .filter(ConversationParticipant.user_id == current_user.id)
                .all())
    for c in existing:
        ids = {p.user_id for p in c.participants}
        if ids == {current_user.id, target_id}:
            return redirect(url_for('messaging.conversation', conv_id=c.id))

    conv = Conversation(type=ConvType.DIRECT, created_by_id=current_user.id)
    db.session.add(conv)
    db.session.flush()
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=current_user.id,
                                           role=ParticipantRole.ADMIN))
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=target_id,
                                           role=ParticipantRole.MEMBER))
    db.session.commit()
    return redirect(url_for('messaging.conversation', conv_id=conv.id))


# ── Nouveau groupe ───────────────────────────────────────────────────────────

@bp_msg.route('/group/new', methods=['GET', 'POST'])
@login_required
def new_group():
    all_users = User.query.filter(User.id != current_user.id).order_by(User.first_name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        member_ids = request.form.getlist('members', type=int)
        if not name:
            flash("Le nom du groupe est obligatoire.", "danger")
            return render_template('messages/new_group.html', all_users=all_users,
                                   name_val=name, selected_ids=member_ids), 400
        if not member_ids:
            flash("Ajoutez au moins un autre membre.", "danger")
            return render_template('messages/new_group.html', all_users=all_users,
                                   name_val=name, selected_ids=member_ids), 400

        conv = Conversation(type=ConvType.GROUP, name=name, created_by_id=current_user.id)
        db.session.add(conv)
        db.session.flush()
        db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=current_user.id,
                                               role=ParticipantRole.ADMIN))
        for uid in member_ids:
            if uid != current_user.id:
                db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=uid,
                                                       role=ParticipantRole.MEMBER))
        db.session.commit()
        flash(f"Groupe « {name} » créé.", "success")
        return redirect(url_for('messaging.conversation', conv_id=conv.id))
    return render_template('messages/new_group.html', all_users=all_users)


# ── Thread conversation ──────────────────────────────────────────────────────

MSG_PAGE_SIZE = 50

@bp_msg.route('/<int:conv_id>')
@login_required
def conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    part = _get_participant(conv_id, current_user.id)
    if not part and not current_user.is_admin:
        abort(403)
    _mark_read(conv_id, current_user.id)

    before_id = request.args.get('before', type=int)
    q = Message.query.filter_by(conversation_id=conv_id)
    if before_id:
        q = q.filter(Message.id < before_id)
    messages = q.order_by(Message.created_at.desc()).limit(MSG_PAGE_SIZE).all()
    messages = list(reversed(messages))
    has_more = len(messages) == MSG_PAGE_SIZE and (
        Message.query.filter_by(conversation_id=conv_id)
        .filter(Message.id < messages[0].id if messages else 0)
        .count() > 0
    )

    pinned = [m for m in Message.query.filter_by(
        conversation_id=conv_id, pinned=True, is_deleted=False).all()]
    participants = conv.participants
    all_users = User.query.filter(User.id != current_user.id).order_by(User.first_name).all()
    my_role = part.role if part else None
    visible = [m for m in messages if not m.is_deleted]
    last_msg_id = visible[-1].id if visible else (messages[-1].id if messages else 0)
    return render_template('messages/conversation.html',
                           conv=conv,
                           messages=messages,
                           has_more=has_more,
                           last_msg_id=last_msg_id,
                           pinned=pinned,
                           participants=participants,
                           all_users=all_users,
                           my_role=my_role,
                           ParticipantRole=ParticipantRole,
                           ConvType=ConvType)


# ── Envoyer un message ───────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/send', methods=['POST'])
@login_required
def send_message(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    part = _get_participant(conv_id, current_user.id)
    if not part and not current_user.is_admin:
        abort(403)
    body = request.form.get('body', '').strip()
    if not body:
        flash("Le message ne peut pas être vide.", "warning")
        return redirect(url_for('messaging.conversation', conv_id=conv_id))
    if len(body) > 2000:
        flash("Message trop long (max 2000 caractères).", "warning")
        return redirect(url_for('messaging.conversation', conv_id=conv_id))
    if conv.is_archived:
        flash("Cette conversation est archivée, l'envoi de messages est désactivé.", "warning")
        return redirect(url_for('messaging.conversation', conv_id=conv_id))
    msg = Message(conversation_id=conv_id, sender_id=current_user.id, body=body)
    db.session.add(msg)
    db.session.commit()
    _mark_read(conv_id, current_user.id)
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── Supprimer un message ─────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/delete/<int:msg_id>', methods=['POST'])
@login_required
def delete_message(conv_id, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.conversation_id != conv_id:
        abort(404)
    part = _get_participant(conv_id, current_user.id)
    is_group_admin = part and part.role == ParticipantRole.ADMIN
    if msg.sender_id != current_user.id and not current_user.is_admin and not is_group_admin:
        abort(403)
    msg.is_deleted = True
    db.session.commit()
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── Épingler / désépingler ───────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/pin/<int:msg_id>', methods=['POST'])
@login_required
def pin_message(conv_id, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.conversation_id != conv_id:
        abort(404)
    part = _get_participant(conv_id, current_user.id)
    if not part and not current_user.is_admin:
        abort(403)
    msg.pinned = not msg.pinned
    msg.pinned_by_id = current_user.id if msg.pinned else None
    db.session.commit()
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── Quitter un groupe ────────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/leave', methods=['POST'])
@login_required
def leave_group(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.type != ConvType.GROUP:
        abort(400)
    part = _get_participant(conv_id, current_user.id)
    if part and part.role == ParticipantRole.ADMIN:
        other_admins = [p for p in conv.participants
                        if p.user_id != current_user.id and p.role == ParticipantRole.ADMIN]
        if not other_admins:
            other_members = [p for p in conv.participants if p.user_id != current_user.id]
            if other_members:
                flash("Vous êtes le seul admin. Promouvez d'abord un autre membre avant de quitter.", "warning")
                return redirect(url_for('messaging.conversation', conv_id=conv_id))
    if part:
        db.session.delete(part)
        db.session.commit()
    flash("Vous avez quitté le groupe.", "info")
    return redirect(url_for('messaging.inbox'))


# ── Ajouter un membre ────────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/add-member', methods=['POST'])
@login_required
def add_member(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.type != ConvType.GROUP:
        abort(400)
    part = _get_participant(conv_id, current_user.id)
    if not part or (part.role != ParticipantRole.ADMIN and not current_user.is_admin):
        abort(403)
    uid = request.form.get('user_id', type=int)
    if not uid:
        flash("Utilisateur invalide.", "danger")
        return redirect(url_for('messaging.conversation', conv_id=conv_id))
    existing = _get_participant(conv_id, uid)
    if existing:
        flash("Cet utilisateur est déjà membre.", "warning")
        return redirect(url_for('messaging.conversation', conv_id=conv_id))
    db.session.add(ConversationParticipant(conversation_id=conv_id, user_id=uid,
                                           role=ParticipantRole.MEMBER))
    db.session.commit()
    flash("Membre ajouté.", "success")
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── Retirer un membre ────────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/remove-member/<int:uid>', methods=['POST'])
@login_required
def remove_member(conv_id, uid):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.type != ConvType.GROUP:
        abort(400)
    part = _get_participant(conv_id, current_user.id)
    if not part or (part.role != ParticipantRole.ADMIN and not current_user.is_admin):
        abort(403)
    target_part = _get_participant(conv_id, uid)
    if target_part:
        db.session.delete(target_part)
        db.session.commit()
        flash("Membre retiré.", "success")
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── Renommer un groupe ───────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/rename', methods=['POST'])
@login_required
def rename_group(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.type != ConvType.GROUP:
        abort(400)
    part = _get_participant(conv_id, current_user.id)
    if not part or (part.role != ParticipantRole.ADMIN and not current_user.is_admin):
        abort(403)
    name = request.form.get('name', '').strip()
    if not name:
        flash("Le nom ne peut pas être vide.", "danger")
        return redirect(url_for('messaging.conversation', conv_id=conv_id))
    conv.name = name
    db.session.commit()
    flash("Groupe renommé.", "success")
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── Promouvoir un membre ─────────────────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/promote/<int:uid>', methods=['POST'])
@login_required
def promote_member(conv_id, uid):
    conv = Conversation.query.get_or_404(conv_id)
    part = _get_participant(conv_id, current_user.id)
    if not part or (part.role != ParticipantRole.ADMIN and not current_user.is_admin):
        abort(403)
    target = _get_participant(conv_id, uid)
    if target:
        if target.role == ParticipantRole.ADMIN:
            all_admins = [p for p in conv.participants if p.role == ParticipantRole.ADMIN]
            if len(all_admins) <= 1:
                flash("Impossible : ce membre est le seul admin du groupe.", "warning")
                return redirect(url_for('messaging.conversation', conv_id=conv_id))
        target.role = ParticipantRole.ADMIN if target.role == ParticipantRole.MEMBER else ParticipantRole.MEMBER
        db.session.commit()
        flash("Rôle mis à jour.", "success")
    return redirect(url_for('messaging.conversation', conv_id=conv_id))


# ── API unread count ─────────────────────────────────────────────────────────

@bp_msg.route('/api/unread')
@login_required
def api_unread():
    return jsonify({'unread': total_unread(current_user.id)})


# ── API nouveaux messages (polling) ──────────────────────────────────────────

@bp_msg.route('/<int:conv_id>/api/since/<int:last_id>')
@login_required
def api_since(conv_id, last_id):
    part = _get_participant(conv_id, current_user.id)
    if not part and not current_user.is_admin:
        abort(403)
    msgs = (Message.query
            .filter_by(conversation_id=conv_id, is_deleted=False)
            .filter(Message.id > last_id)
            .order_by(Message.created_at.asc())
            .all())
    if msgs:
        _mark_read(conv_id, current_user.id)
    data = []
    for m in msgs:
        data.append({
            'id': m.id,
            'body': m.body,
            'sender_id': m.sender_id,
            'sender_name': f"{m.sender.first_name} {m.sender.last_name}" if m.sender else '?',
            'created_at': m.created_at.strftime('%d/%m/%Y %H:%M'),
            'is_me': m.sender_id == current_user.id,
            'pinned': m.pinned,
        })
    return jsonify({'messages': data})
