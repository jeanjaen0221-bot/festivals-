import os
import uuid
import json
import base64
import requests
import tempfile
from decimal import Decimal, ROUND_HALF_UP
import matching
import image_text_matcher as itm
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from types import SimpleNamespace
from werkzeug.datastructures import FileStorage
from flask import (
    Blueprint, render_template, redirect, url_for, abort,
    flash, request, current_app, send_from_directory, make_response, jsonify
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from app import app, db, limiter
from models import Item, Category, Status, ItemPhoto, User, ActionLog, HeadphoneLoan, DepositType, LoanStatus, Match, RejectedPair, Product, Sale, SaleItem, PaymentMethod, ZClosure
from forms import ItemForm, ClaimForm, ConfirmReturnForm, MatchForm, LoginForm, RegisterForm, DeleteForm, HeadphoneLoanForm, SimpleCsrfForm
from ocr_utils import extract_id_card_data
from flask_wtf.csrf import validate_csrf
from admin import admin_required

bp = Blueprint('main', __name__)


def vendor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_admin or current_user.is_vendor_goodies):
            flash("Accès réservé aux vendeurs goodies.", "danger")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def _qz(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _round_cash_0_05(amount: Decimal) -> Decimal:
    cents = amount * 20
    return (cents.quantize(Decimal('1'), rounding=ROUND_HALF_UP) / Decimal(20)).quantize(Decimal('0.01'))




@bp.route('/ocr_id_card', methods=['POST'])
@limiter.limit("3 per minute")
@login_required
def ocr_id_card():
    data = request.get_json()
    image_b64 = data.get('image_b64')
    if not image_b64:
        return jsonify({'error': 'Aucune image transmise'}), 400
    # Optionally: credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    try:
        result = extract_id_card_data(image_b64)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def allowed_file(filename):
    allowed_ext = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_ext


def _guess_mime_from_ext(filename: str) -> str | None:
    try:
        ext = os.path.splitext(filename or '')[1].lower()
    except Exception:
        ext = ''
    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg'
    if ext == '.png':
        return 'image/png'
    return None


def _db_image_bytes_by_filename(filename: str):
    """Return (bytes, mime_type) for a known filename stored in DB, else (None, None)."""
    if not filename:
        return None, None
    try:
        p = Product.query.filter_by(image_filename=filename).first()
        if p and p.image_data:
            return bytes(p.image_data), (p.image_mime_type or _guess_mime_from_ext(filename) or 'application/octet-stream')
        ip = ItemPhoto.query.filter_by(filename=filename).first()
        if ip and ip.data:
            return bytes(ip.data), (ip.mime_type or _guess_mime_from_ext(filename) or 'application/octet-stream')
        it = Item.query.filter_by(photo_filename=filename).first()
        if it and it.photo_data:
            return bytes(it.photo_data), (it.photo_mime_type or _guess_mime_from_ext(filename) or 'application/octet-stream')
        it2 = Item.query.filter_by(return_photo_filename=filename).first()
        if it2 and it2.return_photo_data:
            return bytes(it2.return_photo_data), (it2.return_photo_mime_type or _guess_mime_from_ext(filename) or 'application/octet-stream')
    except Exception:
        return None, None
    return None, None


_tmp_files_to_cleanup: list[str] = []


def _ensure_image_on_disk_for_matching(filename: str) -> str | None:
    """Return a readable file path for matching. Uses UPLOAD_FOLDER if present,
    otherwise writes a temp file from DB bytes. Temp paths are registered for cleanup."""
    if not filename:
        return None
    try:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(path):
            return path
    except Exception:
        path = None

    data, _mime = _db_image_bytes_by_filename(filename)
    if not data:
        return None
    try:
        suffix = os.path.splitext(filename)[1].lower() if filename else ''
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.flush()
        tmp.close()
        _tmp_files_to_cleanup.append(tmp.name)
        return tmp.name
    except Exception:
        return None


def _cleanup_tmp_images() -> None:
    """Supprime les fichiers temporaires créés pour le matching."""
    while _tmp_files_to_cleanup:
        path = _tmp_files_to_cleanup.pop()
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

def find_similar_items(titre, category_id, seuil=70):
    """Retourne des objets similaires (même catégorie) triés par score descendant.
    Utilise le score complet (titre + description + lieu) via matching.match_score.
    """
    similaires = []
    probe = SimpleNamespace(title=titre or '', comments='', location='')
    candidats = Item.query.filter(
        Item.category_id == category_id,
        Item.status.in_([Status.LOST, Status.FOUND])
    ).all()
    for obj in candidats:
        loc = obj.found_location if obj.status == Status.FOUND and obj.found_location else (obj.location or '')
        candidate = SimpleNamespace(title=obj.title or '', comments=obj.comments or '', location=loc)
        score = matching.match_score(probe, candidate)
        if score >= seuil:
            if hasattr(obj, 'photos') and obj.photos and len(obj.photos) > 0:
                photo_url = url_for('main.uploaded_file', filename=obj.photos[0].filename)
            elif obj.photo_filename:
                photo_url = url_for('main.uploaded_file', filename=obj.photo_filename)
            else:
                photo_url = None
            cat_icon_url = None
            cat_icon_class = None
            try:
                if obj.category is not None:
                    icon_info = obj.category.get_icon_display()
                    if icon_info and isinstance(icon_info, dict):
                        if icon_info.get('type') == 'image':
                            cat_icon_url = icon_info.get('url')
                        elif icon_info.get('type') == 'bootstrap':
                            cat_icon_class = icon_info.get('class')
            except Exception:
                pass
            similaires.append({
                'id': obj.id,
                'title': obj.title,
                'score': score,
                'category_name': obj.category.name if obj.category else None,
                'photo_url': photo_url,
                'category_icon_url': cat_icon_url,
                'category_icon_class': cat_icon_class,
                'url_detail': url_for('main.detail_item', item_id=obj.id)
            })
    similaires.sort(key=lambda x: x['score'], reverse=True)
    return similaires

@bp.route('/choix-declaration')
def lost_found_landing():
    return render_template('lost_found_landing.html')

@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('main.auth'))
    latest_found_items = Item.query.filter_by(status=Status.FOUND).order_by(Item.date_reported.desc()).limit(10).all()
    return render_template('index.html', latest_found_items=latest_found_items)

@bp.route('/auth', methods=['GET', 'POST'])
@limiter.limit("15 per minute")
def auth():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    login_form = LoginForm()
    register_form = RegisterForm()
    active_tab = request.args.get('tab', 'login')

    # Vérifie s'il existe déjà un admin
    admin_exists = User.query.filter_by(is_admin=True).first() is not None
    show_admin_checkbox = not admin_exists

    # Gestion connexion
    if request.method == 'POST':
        if 'submit_login' in request.form:
            active_tab = 'login'
            if login_form.validate_on_submit():
                user = User.query.filter_by(email=login_form.email.data.lower()).first()
                if user and user.check_password(login_form.password.data):
                    login_user(user, remember=login_form.remember.data)
                    log_action(user.id, 'login', 'Connexion utilisateur')
                    flash('Connexion réussie.', 'success')
                    return redirect(url_for('main.index'))
                flash('Identifiants invalides.', 'danger')
        elif 'submit_register' in request.form:
            active_tab = 'register'
            if register_form.validate_on_submit():
                if User.query.filter_by(email=register_form.email.data.lower()).first():
                    flash('Cet email existe déjà.', 'danger')
                else:
                    user = User(
                        first_name=register_form.first_name.data.strip(),
                        last_name=register_form.last_name.data.strip(),
                        email=register_form.email.data.lower()
                    )
                    user.set_password(register_form.password.data)
                    if register_form.is_admin.data and show_admin_checkbox:
                        user.is_admin = True
                    else:
                        user.is_admin = False
                    db.session.add(user)
                    db.session.commit()
                    log_action(user.id, 'register', f"Inscription utilisateur : {user.first_name} {user.last_name}")
                    flash('Compte créé. Connectez-vous.', 'success')
                    return redirect(url_for('main.auth', tab='login'))
    return render_template('auth.html', login_form=login_form, register_form=register_form, active_tab=active_tab, show_admin_checkbox=show_admin_checkbox)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie.', 'success')
    return redirect(url_for('main.auth'))

# Journalisation d'action
def log_action(user_id, action_type, details=None):
    log = ActionLog(user_id=user_id, action_type=action_type, details=details)
    db.session.add(log)
    db.session.commit()


@bp.route('/lost/new')
def redirect_lost():
    return redirect(url_for('main.report_item'), code=301)

@bp.route('/found/new')
def redirect_found():
    return redirect(url_for('main.report_item'), code=301)

def get_or_create_category(category_id, new_category_name):
    """Récupère une catégorie existante ou en crée une nouvelle si un nom est fourni."""
    if new_category_name and new_category_name.strip():
        # Vérifier si la catégorie existe déjà (insensible à la casse)
        existing_category = Category.query.filter(
            db.func.lower(Category.name) == new_category_name.strip().lower()
        ).first()
        
        if existing_category:
            return existing_category.id
            
        # Créer une nouvelle catégorie
        new_category = Category(name=new_category_name.strip())
        db.session.add(new_category)
        db.session.flush()  # Pour obtenir l'ID de la nouvelle catégorie
        log_action(current_user.id, 'create_category', f'Nouvelle catégorie: {new_category.name}')
        return new_category.id
    return category_id

@bp.route('/items')
@login_required
def list_items():
    status = request.args.get('status', 'lost')
    try:
        st = Status(status)
    except ValueError:
        st = Status.LOST
    cat_filter = request.args.get('category', type=int)
    q = request.args.get('q', '', type=str).strip()
    from_date_str = request.args.get('from_date', type=str)
    to_date_str = request.args.get('to_date', type=str)
    page = request.args.get('page', 1, type=int)
    query = Item.query.filter_by(status=st)
    if cat_filter:
        query = query.filter_by(category_id=cat_filter)
    # Recherche texte basique sur titre/commentaires
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Item.title.ilike(like), Item.comments.ilike(like)))
    # Filtre par date de création
    try:
        if from_date_str:
            df = datetime.strptime(from_date_str, '%Y-%m-%d')
            query = query.filter(Item.date_reported >= df)
        if to_date_str:
            # inclure toute la journée de fin
            dt = datetime.strptime(to_date_str, '%Y-%m-%d')
            dt_end = dt + timedelta(days=1)
            query = query.filter(Item.date_reported < dt_end)
    except Exception:
        pass
    pagination = query.order_by(Item.date_reported.desc()).paginate(page=page, per_page=12, error_out=False)
    items = pagination.items
    categories = Category.query.order_by(Category.name).all()
    # Construction des groupes pour affichage superposé
    seen = set()
    grouped_items = []
    matches = Match.query.filter(
        (Match.lost_id.in_([item.id for item in items])) | (Match.found_id.in_([item.id for item in items]))
    ).all()
    match_map = {}
    for m in matches:
        match_map[m.lost_id] = m.found_id
        match_map[m.found_id] = m.lost_id
    for item in items:
        if item.id in seen:
            continue
        match_id = match_map.get(item.id)
        if match_id and match_id in [i.id for i in items]:
            other = next(i for i in items if i.id == match_id)
            grouped_items.append([item, other])
            seen.add(item.id)
            seen.add(other.id)
        else:
            grouped_items.append([item])
            seen.add(item.id)
    # Optimisation : pré-calcule les ids des items affichés
    all_items = [item for group in grouped_items for item in group]
    item_ids = [item.id for item in all_items]
    matches = Match.query.filter(
        (Match.lost_id.in_(item_ids)) | (Match.found_id.in_(item_ids))
    ).all()
    matched_ids = set()
    for m in matches:
        matched_ids.add(m.lost_id)
        matched_ids.add(m.found_id)
    matches_map = {item.id: (item.id in matched_ids) for item in all_items}
    # Pré-calcul des icônes Bootstrap pour optimiser l'affichage
    for cat in categories:
        _ = cat.icon_bootstrap_class  # force le calcul, utile pour SQLAlchemy lazy loading
    for obj in items:
        if obj.category:
            _ = obj.category.icon_bootstrap_class
    return render_template(
        'list.html',
        items=items,
        grouped_items=grouped_items,
        pagination=pagination,
        status=st.value,
        categories=categories,
        selected_category=cat_filter,
        q=q,
        from_date=from_date_str,
        to_date=to_date_str,
        matches_map=matches_map,
        Status=Status
    )

@bp.route('/report', methods=['GET', 'POST'])
@login_required
def report_item():
    tab = request.args.get('tab')
    if tab not in ('lost', 'found'):
        # Sécurité : toute valeur non valide redirige vers la landing page
        return render_template('lost_found_landing.html')

    lost_form = ItemForm(prefix='lost')
    found_form = ItemForm(prefix='found')

    # Préremplir les champs déclarant pour objets perdus si connecté
    if current_user.is_authenticated:
        lost_form.reporter_name.data = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name and current_user.last_name else current_user.email
        lost_form.reporter_email.data = current_user.email
        if hasattr(current_user, 'phone'):
            lost_form.reporter_phone.data = current_user.phone
        found_form.reporter_name.data = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name and current_user.last_name else current_user.email
        found_form.reporter_email.data = current_user.email
        if hasattr(current_user, 'phone'):
            found_form.reporter_phone.data = current_user.phone

    # Charger les catégories existantes
    categories = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    lost_form.category.choices = [('', 'Sélectionnez une catégorie')] + categories
    found_form.category.choices = [('', 'Sélectionnez une catégorie')] + categories

    # Gestion soumission objet perdu
    if lost_form.validate_on_submit() and 'submit_lost' in request.form:
        category_id = get_or_create_category(
            lost_form.category.data if lost_form.category.data else None,
            request.form.get('lost-new_category')
        )
        if not category_id:
            flash("Veuillez sélectionner une catégorie ou en créer une nouvelle.", "lost")
            return render_template('report.html', lost_form=lost_form, found_form=found_form, active_tab='lost')
        doublons = find_similar_items(lost_form.title.data, category_id, 70)
        if doublons:
            flash("Attention : des objets similaires existent déjà !", "lost")
        item = Item(
            status=Status.LOST,
            title=lost_form.title.data,
            comments=lost_form.comments.data,
            location=lost_form.location_other.data.strip() if lost_form.location.data == 'autre' else dict(lost_form.location.choices).get(lost_form.location.data, ''),
            category_id=category_id,
            reporter_name=f"{current_user.first_name} {current_user.last_name}" if current_user.first_name and current_user.last_name else current_user.email,
            reporter_email=current_user.email,
            reporter_phone=getattr(current_user, 'phone', None)
        )
        db.session.add(item)
        db.session.flush()
        db.session.commit()
        log_action(current_user.id, 'create_item', f'Ajout objet perdu ID:{item.id}')
        flash("Objet perdu enregistré !", "success")
        return redirect(url_for('main.list_items', status='lost'))

    # Gestion soumission objet trouvé
    if found_form.validate_on_submit() and 'submit_found' in request.form:
        category_id = get_or_create_category(
            found_form.category.data if found_form.category.data else None,
            request.form.get('found-new_category')
        )
        if not category_id:
            flash("Veuillez sélectionner une catégorie ou en créer une nouvelle.", "found")
            return render_template('report.html', lost_form=lost_form, found_form=found_form, active_tab='found')
        doublons = find_similar_items(found_form.title.data, category_id, 70)
        if doublons:
            flash("Attention : des objets similaires existent déjà !", "found")
        item = Item(
            status=Status.FOUND,
            title=found_form.title.data,
            comments=found_form.comments.data,
            found_location=(found_form.found_location_other.data.strip() if found_form.found_location_other.data else ''),
            storage_location=found_form.storage_location_other.data.strip() if found_form.storage_location.data == 'autre' else (dict(found_form.storage_location.choices).get(found_form.storage_location.data) if found_form.storage_location.data else ''),
            category_id=category_id,
            reporter_name=f"{current_user.first_name} {current_user.last_name}" if current_user.first_name and current_user.last_name else current_user.email,
            reporter_email=current_user.email,
            reporter_phone=getattr(current_user, 'phone', None)
        )
        db.session.add(item)
        db.session.flush()
        db.session.commit()
        log_action(current_user.id, 'create_item', f'Ajout objet trouvé ID:{item.id}')
        flash("Objet trouvé enregistré !", "success")
        return redirect(url_for('main.list_items', status='found'))

    # Afficher le formulaire avec le bon onglet actif
    # Forcer l'onglet actif et empêcher le switch selon le choix initial
    active_tab = tab if tab in ('lost', 'found') else 'lost'
    return render_template('report.html', lost_form=lost_form, found_form=found_form, active_tab=active_tab, categories=categories)

@bp.route('/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def detail_item(item_id):
    item = db.get_or_404(Item, item_id)
    form = ClaimForm()
    confirm_return_form = ConfirmReturnForm()
    match_form = None
    suggestions = []
    has_more = False
    more_url = None

    # Si l'objet est déjà rendu, pas de correspondance ni réclamation
    delete_form = DeleteForm()
    if item.status == Status.RETURNED:
        has_match = Match.query.filter((Match.lost_id==item.id)|(Match.found_id==item.id)).first() is not None
        return render_template('detail.html', item=item, can_claim=False, Status=Status, delete_form=delete_form, confirm_return_form=confirm_return_form, form=form, match_form=match_form, has_match=has_match, suggestions=suggestions, has_more=has_more, more_url=more_url)

    # Définit toujours has_match par défaut pour tous les autres chemins
    has_match = Match.query.filter((Match.lost_id==item.id)|(Match.found_id==item.id)).first() is not None

    # Restitution : si FOUND, proposer le formulaire de restitution
    if item.status == Status.FOUND and confirm_return_form.validate_on_submit() and 'submit_return' in request.form:
        f = confirm_return_form.return_photo.data
        if f:
            ext = os.path.splitext(f.filename)[1].lower()
            filename = f"rest_{item.id}_{uuid.uuid4().hex}{ext}"
            item.return_photo_filename = secure_filename(filename)
            item.return_photo_data = f.read()
            item.return_photo_original_filename = f.filename
            item.return_photo_mime_type = getattr(f, 'mimetype', None) or _guess_mime_from_ext(item.return_photo_filename)
        item.status = Status.RETURNED
        item.return_date = datetime.utcnow()
        item.return_comment = confirm_return_form.return_comment.data
        db.session.commit()
        flash("Objet marqué comme rendu avec photo de restitution !", "success")
        return redirect(url_for('main.detail_item', item_id=item.id))

    # Préparer les suggestions et formulaire de correspondance pour LOST ↔ FOUND
    if item.status in (Status.LOST, Status.FOUND):
        opposite_status = Status.FOUND if item.status == Status.LOST else Status.LOST
        candidats = Item.query.filter_by(status=opposite_status).all()
        # Construire des suggestions scorées
        def to_matchable(i: Item):
            loc = i.found_location if i.status == Status.FOUND and i.found_location else i.location
            return SimpleNamespace(title=i.title or '', comments=i.comments or '', location=loc or '')
        current_matchable = to_matchable(item)

        def primary_photo_filename(i: Item):
            if hasattr(i, 'photos') and i.photos and len(i.photos) > 0:
                return i.photos[0].filename
            if i.photo_filename:
                return i.photo_filename
            return None

        _cfg = matching.MATCH_CONFIG
        TEXT_WEIGHT   = _cfg['text_weight']
        IMG_WEIGHT    = _cfg['image_weight']
        IMG_IMG_WEIGHT = _cfg['img_img_weight']

        for c in candidats:
            m = to_matchable(c)
            base_score = matching.match_score(current_matchable, m)
            # Bonus/malus
            bonus = _cfg['bonus_same_category'] if (item.category_id and c.category_id == item.category_id) else 0
            try:
                dt = abs((item.date_reported - c.date_reported).total_seconds()) if item.date_reported and c.date_reported else None
                if dt is not None:
                    days = dt / 86400.0
                    if days <= 2:
                        bonus += _cfg['bonus_date_close']
                    elif days > 14:
                        bonus -= _cfg['malus_date_far']
            except Exception:
                pass
            # Chemins d'images (LOST item vs FOUND candidate)
            img_lost_path = None
            img_found_path = None
            if item.status == Status.LOST:
                img_found_path = _ensure_image_on_disk_for_matching(primary_photo_filename(c))
                img_lost_path  = _ensure_image_on_disk_for_matching(primary_photo_filename(item))
            else:
                img_found_path = _ensure_image_on_disk_for_matching(primary_photo_filename(item))
                img_lost_path  = _ensure_image_on_disk_for_matching(primary_photo_filename(c))
            # Similarité texte↔image
            img_sim_pct = 0.0
            try:
                if item.status == Status.LOST and img_found_path:
                    sim = itm.text_image_similarity(f"{current_matchable.title}. {current_matchable.comments}", img_found_path)
                    img_sim_pct = round(100.0 * float(sim), 2)
                elif item.status == Status.FOUND and img_found_path:
                    sim = itm.text_image_similarity(f"{m.title}. {m.comments}", img_found_path)
                    img_sim_pct = round(100.0 * float(sim), 2)
            except Exception:
                img_sim_pct = 0.0
            # Similarité image↔image (quand les deux ont une photo)
            img_img_pct = 0.0
            try:
                if img_lost_path and img_found_path:
                    sim2 = itm.image_image_similarity(img_lost_path, img_found_path)
                    img_img_pct = round(100.0 * float(sim2), 2)
            except Exception:
                img_img_pct = 0.0
            # Score final pondéré
            if img_img_pct > 0:
                combined = TEXT_WEIGHT * base_score + IMG_WEIGHT * img_sim_pct + IMG_IMG_WEIGHT * img_img_pct
            else:
                effective_text = TEXT_WEIGHT + IMG_IMG_WEIGHT
                combined = effective_text * base_score + IMG_WEIGHT * img_sim_pct
            final_score = max(0, min(100, round(combined + bonus, 2)))
            # Photo principale
            if hasattr(c, 'photos') and c.photos and len(c.photos) > 0:
                photo_url = url_for('main.uploaded_file', filename=c.photos[0].filename)
            elif c.photo_filename:
                photo_url = url_for('main.uploaded_file', filename=c.photo_filename)
            else:
                photo_url = None
            # Préparer info d'icône de catégorie (si pas de photo)
            cat_icon_class = None
            cat_icon_url = None
            try:
                if c.category is not None:
                    icon_info = c.category.get_icon_display()
                    if icon_info and isinstance(icon_info, dict):
                        if icon_info.get('type') == 'image':
                            cat_icon_url = icon_info.get('url')
                        elif icon_info.get('type') == 'bootstrap':
                            cat_icon_class = icon_info.get('class')
            except Exception:
                pass

            suggestions.append({
                'id': c.id,
                'title': c.title,
                'score': final_score,
                'url_detail': url_for('main.detail_item', item_id=c.id),
                'photo_url': photo_url,
                'category_name': (c.category.name if c.category else None),
                'meta_location': (c.found_location if c.status == Status.FOUND else c.location),
                'date_reported': c.date_reported,
                'category_icon_class': cat_icon_class,
                'category_icon_url': cat_icon_url
            })
        # Nettoyer les fichiers temporaires créés pour le matching
        _cleanup_tmp_images()
        # Trier desc et limiter à top 10
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        has_more = len(suggestions) > 10
        suggestions = suggestions[:10]
        # Lien "Voir plus" vers la liste opposée filtrée par catégorie
        try:
            more_url = url_for('main.list_items', status=opposite_status.value, category=item.category_id)
        except Exception:
            more_url = None
        # Garder un fallback select si besoin
        if candidats:
            choices = [(0, "— Sélectionner —")] + [(c.id, f"[{c.id}] {c.title} ({c.location or '—'})") for c in candidats]
            match_form = MatchForm()
            match_form.match_with.choices = choices

    # POST : correspondance prioritaire
    if ('submit_match' in request.form) and match_form and match_form.validate_on_submit():
        other_id = request.form.get('match_with_id', type=int) or match_form.match_with.data
        if other_id and other_id != 0:
            other = db.get_or_404(Item, other_id)

            # Créer un match validé
            if not Match.query.filter_by(lost_id=min(item.id, other.id), found_id=max(item.id, other.id)).first():
                new_match = Match(lost_id=min(item.id, other.id), found_id=max(item.id, other.id))
                db.session.add(new_match)
                db.session.commit()
                flash(f"Objets #{item.id} et #{other.id} liés par correspondance.", "success")
            else:
                flash("Cette correspondance existe déjà.", "info")
            return redirect(url_for('main.detail_item', item_id=item.id))
        else:
            flash("Veuillez sélectionner un objet valide pour la correspondance.", "warning")

    # POST : réclamation classique
    if form.validate_on_submit() and 'submit' in request.form:
        item.status = Status.RETURNED
        item.claimant_name = form.claimant_name.data
        item.claimant_email = form.claimant_email.data
        item.claimant_phone = form.claimant_phone.data
        item.return_date = datetime.utcnow()
        if form.photos.data:
            for f in form.photos.data:
                if isinstance(f, FileStorage) and f and allowed_file(f.filename):
                    ext = os.path.splitext(f.filename)[1].lower()
                    filename = f"{uuid.uuid4().hex}{ext}"
                    safe_name = secure_filename(filename)
                    data = f.read()
                    photo = ItemPhoto(
                        item=item,
                        filename=safe_name,
                        data=data,
                        mime_type=getattr(f, 'mimetype', None) or _guess_mime_from_ext(safe_name),
                        original_filename=f.filename,
                    )
                    db.session.add(photo)
        db.session.commit()
        # Synchronisation automatique : si l’objet est lié, on marque aussi l’autre comme rendu
        match = Match.query.filter((Match.lost_id==item.id)|(Match.found_id==item.id)).first()
        if match:
            other_id = match.found_id if match.lost_id == item.id else match.lost_id
            other = db.session.get(Item, other_id)
            if other and other.status != Status.RETURNED:
                other.status = Status.RETURNED
                other.claimant_name = item.claimant_name
                other.claimant_email = item.claimant_email
                other.claimant_phone = item.claimant_phone
                other.return_date = item.return_date
                other.return_comment = f"Synchronisé avec l’objet #{item.id} (restitution liée)"
                db.session.commit()
        flash("Réclamation enregistrée et objet marqué comme rendu !", "success")
        return redirect(url_for('main.list_items', status='returned'))

    delete_form = DeleteForm()
    # Calcul du statut de match pour affichage badge
    has_match = Match.query.filter((Match.lost_id==item.id)|(Match.found_id==item.id)).first() is not None
    return render_template(
        'detail.html',
        item=item,
        form=form,
        can_claim=True,
        Status=Status,
        match_form=match_form,
        delete_form=delete_form,
        has_match=has_match,
        suggestions=suggestions,
        has_more=has_more,
        more_url=more_url,
        confirm_return_form=confirm_return_form
    )

@bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    # Suppression de la restriction admin : tout utilisateur connecté peut modifier
    item = db.get_or_404(Item, item_id)
    form = ItemForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]

    if request.method == 'GET':
        form.title.data = item.title
        form.comments.data = item.comments
        form.location.data = item.location
        form.category.data = item.category_id
        form.reporter_name.data = item.reporter_name
        form.reporter_email.data = item.reporter_email
        form.reporter_phone.data = item.reporter_phone
        if item.status.name == 'FOUND':
            form.found_location_other.data = item.found_location or ''

    if form.validate_on_submit():
        item.title = form.title.data
        item.comments = form.comments.data
        item.location = form.location.data
        item.category_id = form.category.data
        item.reporter_name = form.reporter_name.data
        item.reporter_email = form.reporter_email.data
        item.reporter_phone = form.reporter_phone.data
        # Correction : lieux stockage/découverte
        if item.status.name == 'FOUND':
            item.found_location = form.found_location_other.data.strip() if form.found_location_other.data else ''
            item.storage_location = form.storage_location_other.data.strip() if form.storage_location.data == 'autre' else (dict(form.storage_location.choices).get(form.storage_location.data) if form.storage_location.data else '')
        db.session.commit()
        # Suppression des photos cochées
        photo_ids_to_delete = request.form.getlist('delete_photos')
        if photo_ids_to_delete:
            for pid in photo_ids_to_delete:
                photo = ItemPhoto.query.filter_by(id=pid, item_id=item.id).first()
                if photo:
                    db.session.delete(photo)
            db.session.commit()
        log_action(current_user.id, 'edit_item', f'Modification objet ID:{item.id}')
        flash("Objet mis à jour !", "success")
        return redirect(url_for('main.detail_item', item_id=item.id))

    return render_template('edit_item.html', form=form, item=item)

@bp.route('/item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)
    delete_form = DeleteForm()
    # Si non-admin : demande de suppression
    if not current_user.is_admin:
        # Stocke le statut original si ce n'est pas déjà fait
        if not item.previous_status:
            item.previous_status = item.status
        item.status = Status.PENDING_DELETION
        db.session.commit()
        log_action(current_user.id, 'request_deletion', f'Demande suppression objet: {item.id}')
        flash("Votre demande de suppression a été transmise à l'administrateur.", "info")
        return redirect(url_for('main.detail_item', item_id=item.id))
    # Admin : suppression définitive
    if delete_form.validate_on_submit():
        if not current_user.check_password(delete_form.delete_password.data):
            flash("Mot de passe incorrect.", "danger")
            return redirect(url_for('main.detail_item', item_id=item_id))
        old_status = item.status.value if hasattr(item, 'status') else 'lost'
        item_id_log = item.id
        db.session.delete(item)
        db.session.commit()
        log_action(current_user.id, 'delete_item', f'Item supprimé: {item_id_log}')
        flash('Objet supprimé.', 'success')
        if old_status in ['lost', 'found', 'returned']:
            return redirect(url_for('main.list_items', status=old_status))
        return redirect(url_for('main.index'))
    # Affiche les erreurs du formulaire si la suppression échoue
    if delete_form.errors:
        for field, errors in delete_form.errors.items():
            for error in errors:
                flash(f"Erreur {field} : {error}", 'danger')
    else:
        flash('Erreur lors de la suppression.', 'danger')
    return redirect(url_for('main.detail_item', item_id=item_id))

@bp.route('/export/<status>')
@login_required
@admin_required
def export_items(status):
    try:
        st = Status(status)
    except ValueError:
        st = Status.LOST

    items = Item.query.filter_by(status=st).filter(Item.status != Status.PENDING_DELETION).order_by(Item.date_reported.desc()).all()
    items_export = []
    for item in items:
        photo_b64 = None
        photo_filename = None
        mime = ''

        # Si plusieurs photos (relation), prendre la première sinon utiliser photo_filename
        if hasattr(item, 'photos') and item.photos and len(item.photos) > 0:
            p0 = item.photos[0]
            photo_filename = p0.filename
            if getattr(p0, 'data', None):
                photo_b64 = base64.b64encode(bytes(p0.data)).decode('utf-8')
                mime = p0.mime_type or _guess_mime_from_ext(photo_filename) or ''
        elif item.photo_filename:
            photo_filename = item.photo_filename
            if getattr(item, 'photo_data', None):
                photo_b64 = base64.b64encode(bytes(item.photo_data)).decode('utf-8')
                mime = item.photo_mime_type or _guess_mime_from_ext(photo_filename) or ''

        # Fallback disque (anciennes images)
        if photo_filename and not photo_b64:
            try:
                chemin = os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)
                with open(chemin, 'rb') as img_file:
                    photo_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                mime = _guess_mime_from_ext(photo_filename) or ''
            except Exception:
                photo_b64 = None
                mime = ''
        items_export.append({
            **item.__dict__,
            'category': item.category,
            'photo_filename': photo_filename,
            'photo_base64': photo_b64,
            'photo_mime': mime
        })
    html = render_template('export_template.html', items=items_export, status=st.value)
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=export_{st.value}.html'
    return response


@bp.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
    except Exception:
        pass
    data, mime = _db_image_bytes_by_filename(filename)
    if data:
        resp = make_response(data)
        resp.headers['Content-Type'] = mime or 'application/octet-stream'
        resp.headers['Cache-Control'] = 'public, max-age=31536000'
        return resp
    return '', 404

@bp.route('/api/check_similar', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def api_check_similar():
    titre = request.form.get('title', '')
    cat_id = request.form.get('category_id', type=int)
    if not titre or not cat_id:
        return {'similars': []}
    similars = find_similar_items(titre, cat_id, seuil=70)
    return jsonify({'similars': similars})

@bp.route('/api/match_explain', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def api_match_explain():
    """Explique le matching entre deux items existants.
    Entrée: item_id, candidate_id (form or json). Retourne score pondéré et détails par champ.
    """
    try:
        item_id = request.form.get('item_id', type=int) if request.form else None
        cand_id = request.form.get('candidate_id', type=int) if request.form else None
        if not item_id or not cand_id:
            data = request.get_json(silent=True) or {}
            item_id = item_id or data.get('item_id')
            cand_id = cand_id or data.get('candidate_id')
            if isinstance(item_id, str):
                item_id = int(item_id)
            if isinstance(cand_id, str):
                cand_id = int(cand_id)
        if not item_id or not cand_id:
            return jsonify({'error': 'item_id et candidate_id sont requis'}), 400

        i1 = db.get_or_404(Item, item_id)
        i2 = db.get_or_404(Item, cand_id)

        # Prépare des objets simplifiés avec un champ "location" cohérent selon le statut
        def to_matchable(i: Item) -> SimpleNamespace:
            loc = i.location
            if i.status == Status.FOUND and i.found_location:
                loc = i.found_location
            return SimpleNamespace(
                title=i.title or '',
                comments=i.comments or '',
                location=loc or ''
            )

        m1 = to_matchable(i1)
        m2 = to_matchable(i2)

        _cfg = matching.MATCH_CONFIG
        fields_weights = _cfg['fields_weights']
        TEXT_WEIGHT    = _cfg['text_weight']
        IMG_WEIGHT     = _cfg['image_weight']
        IMG_IMG_WEIGHT = _cfg['img_img_weight']

        score_text = matching.match_score(m1, m2, fields_weights=fields_weights)
        details = matching.match_explanation(m1, m2, fields_weights=fields_weights)

        # Bonus/malus (catégorie identique et proximité temporelle)
        bonus = 0
        if i1.category_id == i2.category_id:
            bonus += _cfg['bonus_same_category']
        try:
            dt = abs((i1.date_reported - i2.date_reported).total_seconds()) if i1.date_reported and i2.date_reported else None
            if dt is not None:
                days = dt / 86400.0
                if days <= 2:
                    bonus += _cfg['bonus_date_close']
                elif days > 14:
                    bonus -= _cfg['malus_date_far']
        except Exception:
            pass

        def primary_photo_filename(i: Item):
            if hasattr(i, 'photos') and i.photos and len(i.photos) > 0:
                return i.photos[0].filename
            if i.photo_filename:
                return i.photo_filename
            return None

        # Déterminer l'image LOST et l'image FOUND
        img_lost_path = None
        img_found_path = None
        if i1.status == Status.LOST and i2.status == Status.FOUND:
            img_lost_path  = _ensure_image_on_disk_for_matching(primary_photo_filename(i1))
            img_found_path = _ensure_image_on_disk_for_matching(primary_photo_filename(i2))
        elif i1.status == Status.FOUND and i2.status == Status.LOST:
            img_found_path = _ensure_image_on_disk_for_matching(primary_photo_filename(i1))
            img_lost_path  = _ensure_image_on_disk_for_matching(primary_photo_filename(i2))

        # Similarité texte↔image
        img_sim_pct = 0.0
        try:
            if i1.status == Status.LOST and img_found_path:
                sim = itm.text_image_similarity(f"{m1.title}. {m1.comments}", img_found_path)
                img_sim_pct = round(100.0 * float(sim), 2)
            elif i1.status == Status.FOUND and img_found_path:
                sim = itm.text_image_similarity(f"{m2.title}. {m2.comments}", img_found_path)
                img_sim_pct = round(100.0 * float(sim), 2)
        except Exception:
            img_sim_pct = 0.0

        # Similarité image↔image
        img_img_pct = 0.0
        try:
            if img_lost_path and img_found_path:
                sim2 = itm.image_image_similarity(img_lost_path, img_found_path)
                img_img_pct = round(100.0 * float(sim2), 2)
        except Exception:
            img_img_pct = 0.0

        _cleanup_tmp_images()

        if img_img_pct > 0:
            combined = TEXT_WEIGHT * score_text + IMG_WEIGHT * img_sim_pct + IMG_IMG_WEIGHT * img_img_pct
        else:
            effective_text = TEXT_WEIGHT + IMG_IMG_WEIGHT
            combined = effective_text * score_text + IMG_WEIGHT * img_sim_pct
        final_score = max(0, min(100, round(combined + bonus, 2)))

        return jsonify({
            'item_id': i1.id,
            'candidate_id': i2.id,
            'score_base': score_text,
            'bonus': bonus,
            'score_final': final_score,
            'image_similarity': img_sim_pct,
            'image_image_similarity': img_img_pct,
            'weights': {'text': TEXT_WEIGHT, 'image': IMG_WEIGHT, 'img_img': IMG_IMG_WEIGHT},
            'details': details
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/loans', methods=['GET', 'POST'])
@login_required
def headphone_loans():
    form = HeadphoneLoanForm()
    search = request.args.get('q', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    query = HeadphoneLoan.query
    sort = request.args.get('sort', 'date')
    if search:
        query = query.filter((HeadphoneLoan.first_name.ilike(f'%{search}%')) | (HeadphoneLoan.last_name.ilike(f'%{search}%')))
    # Exclure les prêts en attente de suppression
    query = query.filter(HeadphoneLoan.status != LoanStatus.PENDING_DELETION)
    if sort == 'name':
        query = query.order_by(HeadphoneLoan.last_name.asc(), HeadphoneLoan.first_name.asc())
    else:
        query = query.order_by(HeadphoneLoan.loan_date.desc())
    pagination = query.paginate(page=page, per_page=25, error_out=False)
    loans = pagination.items
    if form.validate_on_submit():
        id_card_photo_b64 = None
        if form.deposit_type.data == 'id_card' and 'id_card_photo' in request.files:
            file = request.files['id_card_photo']
            if file and file.filename:
                img_bytes = file.read()
                id_card_photo_b64 = 'data:' + file.mimetype + ';base64,' + base64.b64encode(img_bytes).decode('utf-8')
        loan = HeadphoneLoan(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            deposit_type=DepositType(form.deposit_type.data),
            deposit_details=form.deposit_details.data,
            quantity=form.quantity.data or 1,
            deposit_amount=form.deposit_amount.data if form.deposit_type.data == 'cash' else None,
            id_card_photo=id_card_photo_b64
        )
        db.session.add(loan)
        db.session.commit()
        flash("Prêt enregistré !", "success")
        return redirect(url_for('main.headphone_loans'))
    return render_template('loans.html', form=form, loans=loans, search=search, sort=sort, pagination=pagination)

@bp.route('/trains')
def train_schedule():
    return render_template('shuttle_train.html')

@bp.route('/shuttle')
def shuttle_page():
    return render_template('shuttle.html')

@bp.route('/loans/<int:loan_id>/request_deletion', methods=['POST'])
@login_required
def request_loan_deletion(loan_id):
    loan = db.get_or_404(HeadphoneLoan, loan_id)
    # Vérifie que le prêt n'est pas déjà en attente
    if loan.status == LoanStatus.PENDING_DELETION:
        flash("Ce prêt est déjà en attente de suppression.", "warning")
        return redirect(url_for('main.headphone_loans'))
    # CSRF protection
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        abort(400, description="CSRF token invalide.")
    # Stocke le statut original
    if not loan.previous_status:
        loan.previous_status = loan.status
    loan.status = LoanStatus.PENDING_DELETION
    db.session.commit()
    log_action(current_user.id, 'request_loan_deletion', f'Demande suppression prêt casque: {loan.id}')
    flash("Demande de suppression envoyée à l'administration.", "info")
    return redirect(url_for('main.headphone_loans'))

@bp.route('/loans/<int:loan_id>/return', methods=['POST'])
@login_required
def return_headphone_loan(loan_id):
    loan = db.get_or_404(HeadphoneLoan, loan_id)
    data = request.get_json(silent=True)
    if not data or 'signature' not in data:
        return jsonify({'success': False, 'error': 'Signature manquante'}), 400
    signature = data.get('signature')
    loan.signature = signature
    loan.return_date = datetime.utcnow()
    db.session.commit()
    return {'success': True}

# ───────────────────────────────────────────────────────────────────────────────
# Routes de correspondance globale Lost↔Found (nouvelles)
# ───────────────────────────────────────────────────────────────────────────────
def get_all_candidate_pairs(seuil=60):
    pairs = []
    lost_items  = Item.query.filter_by(status=Status.LOST).all()
    found_items = Item.query.filter_by(status=Status.FOUND).all()

    fields_weights = matching.MATCH_CONFIG['fields_weights']
    _cfg = matching.MATCH_CONFIG

    for lost in lost_items:
        for found in found_items:
            score = matching.match_score(lost, found, fields_weights)
            # Bonus catégorie identique (même logique que detail_item)
            if lost.category_id and lost.category_id == found.category_id:
                score = min(100.0, score + _cfg['bonus_same_category'])
            if score >= seuil:
                explanation = matching.match_explanation(lost, found, fields_weights)
                pairs.append((lost, found, round(score, 2), explanation))
    return pairs

@bp.route('/matches')
@login_required
def list_matches():
    try:
        seuil = int(request.args.get('threshold', 60))
    except (TypeError, ValueError):
        seuil = 60
    show_validated = request.args.get('show_validated', '0') == '1'
    show_rejected  = request.args.get('show_rejected',  '0') == '1'

    all_pairs = get_all_candidate_pairs(seuil=seuil)
    all_pairs = sorted(all_pairs, key=lambda x: x[2], reverse=True)

    # Ensembles pour lookup rapide
    validated_set = set()
    for m in Match.query.all():
        validated_set.add((m.lost_id, m.found_id))
        validated_set.add((m.found_id, m.lost_id))

    rejected_set = set()
    for r in RejectedPair.query.all():
        rejected_set.add((r.lost_id, r.found_id))
        rejected_set.add((r.found_id, r.lost_id))

    pairs_with_status = []
    n_pending = n_validated = n_rejected = 0
    for lost, found, score, explanation in all_pairs:
        key = (lost.id, found.id)
        is_validated = key in validated_set
        is_rejected  = key in rejected_set

        if is_validated:
            n_validated += 1
        elif is_rejected:
            n_rejected += 1
        else:
            n_pending += 1

        if is_validated and not show_validated:
            continue
        if is_rejected and not show_rejected:
            continue

        pairs_with_status.append({
            'lost': lost,
            'found': found,
            'score': score,
            'is_validated': is_validated,
            'is_rejected': is_rejected,
            'explanation': explanation,
        })

    stats = {'pending': n_pending, 'validated': n_validated, 'rejected': n_rejected}
    return render_template(
        'matches.html',
        pairs=pairs_with_status,
        threshold=seuil,
        show_validated=show_validated,
        show_rejected=show_rejected,
        stats=stats,
    )


@bp.route('/matches/reject', methods=['POST'])
@login_required
@admin_required
def reject_match():
    try:
        lost_id  = int(request.form.get('lost_id'))
        found_id = int(request.form.get('found_id'))
    except (TypeError, ValueError):
        flash("Identifiants invalides.", "danger")
        return redirect(url_for('main.list_matches'))
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        abort(400, description="CSRF token invalide.")
    existing = RejectedPair.query.filter_by(lost_id=lost_id, found_id=found_id).first()
    if not existing:
        rp = RejectedPair(
            lost_id=lost_id,
            found_id=found_id,
            rejected_by=current_user.id,
        )
        db.session.add(rp)
        db.session.commit()
        log_action(current_user.id, 'reject_match', f'Paire rejetée Lost:{lost_id} Found:{found_id}')
        flash(f"Paire Lost #{lost_id} ↔ Found #{found_id} rejetée.", "info")
    return redirect(url_for('main.list_matches',
                            threshold=request.form.get('threshold', 60),
                            show_validated=request.form.get('show_validated', 0),
                            show_rejected=request.form.get('show_rejected', 0)))


@bp.route('/matches/confirm', methods=['POST'])
@login_required
@admin_required
def confirm_match():
    try:
        lost_id = int(request.form.get('lost_id'))
        found_id = int(request.form.get('found_id'))
    except (TypeError, ValueError):
        flash("Identifiants invalides pour la correspondance.", "danger")
        return redirect(url_for('main.list_matches'))

    lost = db.session.get(Item, lost_id)
    found = db.session.get(Item, found_id)
    if not lost or not found:
        flash("Objet introuvable pour correspondance.", "danger")
        return redirect(url_for('main.list_matches'))

    # Vérifier si déjà validé (champ matched_with_id ou Match existant)
    match_exists = Match.query.filter_by(lost_id=lost_id, found_id=found_id).first()
    if match_exists:
        flash("Cette paire a déjà été validée.", "info")
        return redirect(url_for('main.list_matches'))

    if lost.status != Status.LOST or found.status != Status.FOUND:
        flash("L’objet n’est plus disponible pour correspondance.", "warning")
        return redirect(url_for('main.list_matches'))

    # Créer l'entrée Match
    new_match = Match(lost_id=lost_id, found_id=found_id)
    db.session.add(new_match)

    now = datetime.utcnow()
    # lost.status = Status.RETURNED  # On ne change plus le statut
    lost.claimant_name = found.reporter_name
    lost.claimant_email = found.reporter_email
    lost.claimant_phone = found.reporter_phone
    # found.status = Status.RETURNED  # On ne change plus le statut
    found.claimant_name = lost.reporter_name
    found.claimant_email = lost.reporter_email
    found.claimant_phone = lost.reporter_phone
    found.return_date = now
    found.return_comment = f"Corrélé avec Lost #{lost.id}"

    db.session.commit()
    log_action(current_user.id, 'validate_match', f'Match Lost:{lost.id} Found:{found.id}')
    flash(f"Correspondance validée : Lost #{lost.id} ↔ Found #{found.id}", "success")
    return redirect(url_for('main.list_matches'))


@bp.route('/caisse', methods=['GET', 'POST'])
@login_required
@vendor_required
def caisse():
    csrf_form = SimpleCsrfForm()
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    last = ZClosure.query.order_by(ZClosure.to_ts.desc()).first()
    last_z_iso = last.to_ts.isoformat() if last else ''
    if request.method == 'POST':
        if not csrf_form.validate_on_submit():
            flash('Erreur CSRF.', 'danger')
            return redirect(url_for('main.caisse'))
        try:
            cart_json = request.form.get('cart_json', '[]')
            cart = json.loads(cart_json)
            payment = request.form.get('payment_method')
            if payment not in ('cash', 'card'):
                raise ValueError('Méthode de paiement invalide')
        except Exception as e:
            flash(f'Panier invalide : {e}', 'danger')
            return redirect(url_for('main.caisse'))

        total = Decimal('0.00')
        total_vat = Decimal('0.00')
        items_data = []
        for entry in cart:
            pid = int(entry.get('product_id'))
            qty = int(entry.get('quantity', 1))
            if qty <= 0:
                continue
            p = db.session.get(Product, pid)
            if not p or not p.active:
                flash(f"Article invalide ou inactif (ID {pid}).", 'danger')
                return redirect(url_for('main.caisse'))
            unit = _qz(Decimal(str(p.price)))
            line_total = _qz(unit * qty)
            rate = int(p.vat_rate or 21)
            divisor = Decimal('1') + (Decimal(rate) / Decimal('100'))
            vat = _qz(line_total - line_total / divisor)
            total += line_total
            total_vat += vat
            items_data.append({
                'product': p, 'quantity': qty, 'unit_price': unit,
                'vat_rate': rate, 'line_total': line_total, 'vat_amount': vat,
            })

        if not items_data:
            flash('Le panier est vide.', 'warning')
            return redirect(url_for('main.caisse'))

        sale = Sale(
            payment_method=PaymentMethod.CASH if payment == 'cash' else PaymentMethod.CARD,
            total_amount=_qz(total),
            total_vat_amount=_qz(total_vat),
        )
        if payment == 'cash':
            rounded = _round_cash_0_05(total)
            sale.rounded_total_amount = _qz(rounded)
            sale.rounding_adjustment = _qz(rounded - total)
        db.session.add(sale)
        db.session.flush()
        for d in items_data:
            db.session.add(SaleItem(
                sale_id=sale.id,
                product_id=d['product'].id,
                quantity=d['quantity'],
                unit_price=d['unit_price'],
                vat_rate=d['vat_rate'],
                line_total=d['line_total'],
                vat_amount=d['vat_amount'],
            ))
        db.session.add(ActionLog(
            user_id=current_user.id,
            action_type='sale_goodies',
            details=f'Vente #{sale.id} {payment} {_qz(total)}€ ({len(items_data)} ligne(s)) par vendeur #{current_user.id}'
        ))
        db.session.commit()
        flash(f'Vente #{sale.id} enregistrée — {_qz(total):.2f} € ({payment}).', 'success')
        return redirect(url_for('main.caisse'))

    return render_template('caisse.html', products=products, csrf_form=csrf_form, last_z_iso=last_z_iso)


@bp.route('/caisse/last_z')
@login_required
@vendor_required
def caisse_last_z():
    last = ZClosure.query.order_by(ZClosure.to_ts.desc()).first()
    iso = last.to_ts.isoformat() if last and last.to_ts else ''
    return jsonify({'last_z_iso': iso})
