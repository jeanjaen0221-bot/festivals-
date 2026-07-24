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
from datetime import datetime, timedelta, timezone
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
import imagehash
from PIL import Image, UnidentifiedImageError

from app import app, db, limiter
from models import Item, Category, Status, ItemPhoto, User, ActionLog, HeadphoneLoan, DepositType, LoanStatus, Match, RejectedPair, Product, Sale, SaleItem, PaymentMethod, ZClosure
from forms import ItemForm, ClaimForm, ConfirmReturnForm, MatchForm, LoginForm, RegisterForm, DeleteForm, HeadphoneLoanForm, SimpleCsrfForm
from ocr_utils import extract_id_card_data
from admin import admin_required

bp = Blueprint('main', __name__)


@bp.before_request
def restrict_vendor_only():
    """Les utilisateurs vendor-only (goodies, non-admin) n'ont accès qu'à /caisse."""
    if not current_user.is_authenticated:
        return
    if current_user.is_admin:
        return
    if not getattr(current_user, 'is_vendor_goodies', False):
        return
    allowed = {'main.caisse', 'main.caisse_last_z', 'main.logout', 'main.auth'}
    if request.endpoint and request.endpoint not in allowed:
        return redirect(url_for('main.caisse'))


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
    data = request.get_json(silent=True) or {}
    image_b64 = data.get('image_b64')
    if not image_b64:
        return jsonify({'error': 'Aucune image transmise'}), 400
    # Optionally: credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    try:
        result = extract_id_card_data(image_b64)
        return jsonify(result)
    except Exception:
        current_app.logger.exception('Échec du traitement OCR')
        return jsonify({'error': 'Le traitement OCR a échoué. Réessayez plus tard.'}), 500

def allowed_file(filename):
    allowed_ext = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_ext


def _check_image_magic_bytes(file_stream) -> bool:
    """Vérifie les magic bytes pour s'assurer que le fichier est bien une image JPEG ou PNG."""
    header = file_stream.read(16)
    file_stream.seek(0)
    if header[:3] == b'\xff\xd8\xff':
        return True
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    return False


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


# 256 bits garde une bonne tolérance aux recompressions tout en limitant les
# faux positifs. Une distance <= 18 signale les copies, recadrages légers et
# photos quasi identiques ; ce n'est volontairement jamais un blocage.
PERCEPTUAL_HASH_DISTANCE = 18


def _perceptual_hash(image_bytes: bytes) -> str | None:
    """Calcule un pHash stable sans charger de modèle ML."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            return str(imagehash.phash(image.convert('RGB'), hash_size=16))
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _hamming_distance(hash_a: str | None, hash_b: str | None) -> int | None:
    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        return None
    try:
        return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()
    except ValueError:
        return None


def find_visual_duplicates(perceptual_hash: str | None, limit: int = 10):
    """Retourne les ItemPhoto proches, triés par distance de Hamming."""
    if not perceptual_hash:
        return []
    # L'index réduit le coût des cas exactement identiques. Les autres hashes
    # sont ensuite comparés en mémoire, car PostgreSQL n'offre pas un opérateur
    # Hamming portable pour cette colonne hexadécimale.
    photos = ItemPhoto.query.filter(ItemPhoto.perceptual_hash.isnot(None)).all()
    matches = []
    for photo in photos:
        distance = _hamming_distance(perceptual_hash, photo.perceptual_hash)
        if distance is not None and distance <= PERCEPTUAL_HASH_DISTANCE:
            matches.append((photo, distance))
    matches.sort(key=lambda entry: entry[1])
    return matches[:limit]


def _primary_perceptual_hash(item: Item) -> str | None:
    """Hash de la photo principale, s'il a été calculé à l'import."""
    return item.photos[0].perceptual_hash if item.photos else None


def _persist_item_photo(item: Item, file: FileStorage) -> ItemPhoto | None:
    """Persiste toute ItemPhoto au même endroit, avec son hash perceptuel."""
    if not (file and file.filename and allowed_file(file.filename) and _check_image_magic_bytes(file)):
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    filename = secure_filename(f"{uuid.uuid4().hex}{ext}")
    data = file.read()
    photo = ItemPhoto(
        item=item,
        filename=filename,
        data=data,
        mime_type=_guess_mime_from_ext(filename),
        original_filename=file.filename,
        perceptual_hash=_perceptual_hash(data),
    )
    db.session.add(photo)
    return photo


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


def _item_pair_bonus(lost, found) -> float:
    """Bonus/malus catégorie + date + champs structurés pour une paire Lost↔Found."""
    _cfg = matching.MATCH_CONFIG
    bonus = 0.0
    if lost.category_id and lost.category_id == found.category_id:
        bonus += _cfg['bonus_same_category']
    try:
        if lost.date_reported and found.date_reported:
            days = abs((lost.date_reported - found.date_reported).total_seconds()) / 86400.0
            if days <= 2:
                bonus += _cfg['bonus_date_close']
            elif days > 14:
                bonus -= _cfg['malus_date_far']
    except Exception:
        pass
    bonus += matching.structured_field_bonus(lost, found)
    return bonus


def _compute_weighted_score(base_score: float, img_sim_pct: float,
                            img_img_pct: float, bonus: float) -> float:
    """Formule de pondération unifiée — identique dans detail_item, list_matches et api_match_explain."""
    _cfg = matching.MATCH_CONFIG
    tw, iw, iiw = _cfg['text_weight'], _cfg['image_weight'], _cfg['img_img_weight']
    if img_img_pct > 0:
        combined = tw * base_score + iw * img_sim_pct + iiw * img_img_pct
    else:
        combined = (tw + iiw) * base_score + iw * img_sim_pct
    return max(0.0, min(100.0, round(combined + bonus, 2)))


def find_similar_items(titre, category_id, seuil=70, location=''):
    """Retourne des objets similaires (même catégorie) triés par score descendant.
    Utilise le score complet (titre + description + lieu) via matching.match_score.
    """
    similaires = []
    probe = SimpleNamespace(title=titre or '', comments='', location=location or '')
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
    registration_open = not admin_exists  # L'inscription publique est fermée dès qu'un admin existe

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
                    if not user.is_admin and getattr(user, 'is_vendor_goodies', False):
                        return redirect(url_for('main.caisse'))
                    return redirect(url_for('main.index'))
                flash('Identifiants invalides.', 'danger')
        elif 'submit_register' in request.form:
            active_tab = 'register'
            if not registration_open:
                flash("L'inscription est fermée. Contactez un administrateur pour obtenir un compte.", 'danger')
            elif register_form.validate_on_submit():
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
    return render_template('auth.html', login_form=login_form, register_form=register_form, active_tab=active_tab, show_admin_checkbox=show_admin_checkbox, registration_open=registration_open)


@bp.route('/logout', methods=['POST'])
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
        found_form.reporter_name.data = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name and current_user.last_name else current_user.email
        found_form.reporter_email.data = current_user.email

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
            reporter_phone=(lost_form.reporter_phone.data or '').strip() or None,
            item_color=','.join(lost_form.item_color.data) if lost_form.item_color.data else None,
            item_brand=(lost_form.item_brand.data or '').strip() or None,
            item_distinctive=','.join(lost_form.item_distinctive.data) if lost_form.item_distinctive.data else None,
        )
        db.session.add(item)
        # Les objets perdus ne proposent pas de photo dans le formulaire, mais
        # garder ce chemin rend la persistance cohérente si le champ évolue.
        for photo_file in lost_form.photos.data or []:
            _persist_item_photo(item, photo_file)
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
            found_location=(found_form.found_location_other.data.strip() if found_form.found_location.data == 'autre' else dict(found_form.found_location.choices).get(found_form.found_location.data, '')),
            storage_location=found_form.storage_location_other.data.strip() if found_form.storage_location.data == 'autre' else (dict(found_form.storage_location.choices).get(found_form.storage_location.data) if found_form.storage_location.data else ''),
            category_id=category_id,
            reporter_name=f"{current_user.first_name} {current_user.last_name}" if current_user.first_name and current_user.last_name else current_user.email,
            reporter_email=current_user.email,
            reporter_phone=(found_form.reporter_phone.data or '').strip() or None,
            item_color=','.join(found_form.item_color.data) if found_form.item_color.data else None,
            item_brand=(found_form.item_brand.data or '').strip() or None,
            item_distinctive=','.join(found_form.item_distinctive.data) if found_form.item_distinctive.data else None,
        )
        db.session.add(item)
        for photo_file in found_form.photos.data or []:
            _persist_item_photo(item, photo_file)
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

    # POST prioritaire : correspondance directe (court-circuite le calcul des suggestions)
    if request.method == 'POST' and 'submit_match' in request.form:
        csrf_guard = SimpleCsrfForm()
        if not csrf_guard.validate_on_submit():
            flash("Formulaire invalide.", "danger")
            return redirect(url_for('main.detail_item', item_id=item.id))
        other_id = request.form.get('match_with_id', type=int) or request.form.get('match_with', type=int)
        if other_id and other_id != 0:
            other = db.get_or_404(Item, other_id)
            if {item.status, other.status} != {Status.LOST, Status.FOUND}:
                flash("Une correspondance doit associer un objet perdu et un objet trouvé disponibles.", "warning")
                return redirect(url_for('main.detail_item', item_id=item.id))
            if Match.query.filter(
                (Match.lost_id.in_([item.id, other.id])) |
                (Match.found_id.in_([item.id, other.id]))
            ).first():
                flash("L'un de ces objets est déjà associé à une autre fiche.", "warning")
                return redirect(url_for('main.detail_item', item_id=item.id))
            # Assigner lost_id/found_id selon le statut réel.
            if item.status == Status.LOST:
                lid, fid = item.id, other.id
            else:
                lid, fid = other.id, item.id
            # B5 : vérifier les deux ordres pour éviter les doublons
            exists = Match.query.filter(
                ((Match.lost_id == lid) & (Match.found_id == fid)) |
                ((Match.lost_id == fid) & (Match.found_id == lid))
            ).first()
            if not exists:
                db.session.add(Match(lost_id=lid, found_id=fid))
                db.session.commit()
                flash(f"Objets #{item.id} et #{other.id} liés par correspondance.", "success")
            else:
                flash("Cette correspondance existe déjà.", "info")
        else:
            flash("Veuillez sélectionner un objet valide pour la correspondance.", "warning")
        return redirect(url_for('main.detail_item', item_id=item.id))

    # Restitution : si FOUND, proposer le formulaire de restitution
    if item.status == Status.FOUND and confirm_return_form.validate_on_submit() and 'submit_return' in request.form:
        f = confirm_return_form.return_photo.data
        if f and f.filename:
            if not allowed_file(f.filename) or not _check_image_magic_bytes(f):
                flash("Le fichier photo doit être une image JPEG ou PNG valide.", "danger")
                return redirect(url_for('main.detail_item', item_id=item.id))
            ext = os.path.splitext(f.filename)[1].lower()
            filename = f"rest_{item.id}_{uuid.uuid4().hex}{ext}"
            item.return_photo_filename = secure_filename(filename)
            item.return_photo_data = f.read()
            item.return_photo_original_filename = f.filename
            item.return_photo_mime_type = _guess_mime_from_ext(item.return_photo_filename)
        item.status = Status.RETURNED
        item.return_date = datetime.now(timezone.utc)
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

        for c in candidats:
            m = to_matchable(c)
            base_score = matching.match_score(current_matchable, m)
            # Bonus catégorie + date via helper partagé
            lost_item  = item if item.status == Status.LOST else c
            found_item = c    if item.status == Status.LOST else item
            bonus = _item_pair_bonus(lost_item, found_item)
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
            # Le hash est le préfiltre du modèle visuel : les copies évidentes
            # sont résolues immédiatement, les autres paires seulement sont
            # envoyées à l'embedding image↔image.
            img_img_pct = 0.0
            try:
                if img_lost_path and img_found_path:
                    hash_distance = _hamming_distance(
                        _primary_perceptual_hash(lost_item), _primary_perceptual_hash(found_item)
                    )
                    if hash_distance is not None and hash_distance <= PERCEPTUAL_HASH_DISTANCE:
                        img_img_pct = 100.0
                    else:
                        sim2 = itm.image_image_similarity(img_lost_path, img_found_path)
                        img_img_pct = round(100.0 * float(sim2), 2)
            except Exception:
                img_img_pct = 0.0
            # Score final pondéré via helper partagé
            final_score = _compute_weighted_score(base_score, img_sim_pct, img_img_pct, bonus)
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

    # POST : réclamation classique
    if form.validate_on_submit() and 'submit' in request.form:
        item.status = Status.RETURNED
        item.claimant_name = form.claimant_name.data
        item.claimant_email = form.claimant_email.data
        item.claimant_phone = form.claimant_phone.data
        item.return_date = datetime.now(timezone.utc)
        if form.photos.data:
            for f in form.photos.data:
                if isinstance(f, FileStorage):
                    _persist_item_photo(item, f)
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
@admin_required
def edit_item(item_id):
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
        form.item_color.data = item.item_color.split(',') if item.item_color else []
        form.item_brand.data = item.item_brand or ''
        form.item_distinctive.data = item.item_distinctive.split(',') if item.item_distinctive else []

    if form.validate_on_submit():
        item.title = form.title.data
        item.comments = form.comments.data
        item.location = form.location.data
        item.category_id = form.category.data
        item.reporter_name = form.reporter_name.data
        item.reporter_email = form.reporter_email.data
        item.reporter_phone = form.reporter_phone.data
        # Correction : lieux stockage/découverte
        item.item_color = ','.join(form.item_color.data) if form.item_color.data else None
        item.item_brand = (form.item_brand.data or '').strip() or None
        item.item_distinctive = ','.join(form.item_distinctive.data) if form.item_distinctive.data else None
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
    flash('Formulaire invalide. Vérifiez les champs saisis.', 'danger')
    return redirect(url_for('main.detail_item', item_id=item_id))

@bp.route('/export/<status>')
@login_required
@admin_required
def export_items(status):
    try:
        st = Status(status)
    except ValueError:
        st = Status.LOST

    EXPORT_LIMIT = 1000
    items = Item.query.filter_by(status=st).filter(Item.status != Status.PENDING_DELETION).order_by(Item.date_reported.desc()).limit(EXPORT_LIMIT).all()
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
@login_required
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
        return {'similars': [], 'candidates': []}
    location = request.form.get('location', '')
    colors_raw = request.form.get('colors', '')
    brand_raw  = request.form.get('brand', '').strip()
    dist_raw   = request.form.get('distinctive', '')
    current_status = request.form.get('status', '')  # 'lost' ou 'found'

    # Doublons (même statut)
    similars = find_similar_items(titre, cat_id, seuil=70, location=location)

    # Correspondances croisées (statut opposé) — preview temps réel
    candidates = []
    if current_status in ('lost', 'found'):
        opposite = Status.FOUND if current_status == 'lost' else Status.LOST
        probe = SimpleNamespace(
            title=titre, comments='', location=location or '',
            item_color=colors_raw, item_brand=brand_raw, item_distinctive=dist_raw
        )
        opp_items = Item.query.filter(
            Item.category_id == cat_id,
            Item.status == opposite,
        ).order_by(Item.date_reported.desc()).limit(200).all()
        for obj in opp_items:
            struct_b = matching.structured_field_bonus(probe, obj)
            threshold = matching.effective_threshold(struct_b)
            base = matching.match_score(probe, obj)
            score = max(0.0, min(100.0, round(base + struct_b, 2)))
            if score >= threshold:
                candidates.append({
                    'id': obj.id,
                    'title': obj.title,
                    'category': obj.category.name if obj.category else '',
                    'score': score,
                    'date': obj.date_reported.strftime('%d/%m/%Y') if obj.date_reported else '',
                    'item_color': obj.item_color or '',
                    'item_brand': obj.item_brand or '',
                })
        candidates.sort(key=lambda x: -x['score'])
        candidates = candidates[:5]

    return jsonify({'similars': similars, 'candidates': candidates})


@bp.route('/api/check_visual_duplicates', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def api_check_visual_duplicates():
    """Prévisualise les doublons photo avant la création d'une déclaration."""
    matches = []
    for uploaded in request.files.getlist('photos'):
        if not (uploaded and uploaded.filename and allowed_file(uploaded.filename)
                and _check_image_magic_bytes(uploaded)):
            continue
        perceptual_hash = _perceptual_hash(uploaded.read())
        uploaded.seek(0)
        for photo, distance in find_visual_duplicates(perceptual_hash):
            item = photo.item
            if item is None or any(row['photo_id'] == photo.id for row in matches):
                continue
            matches.append({
                'photo_id': photo.id,
                'item_id': item.id,
                'title': item.title,
                'distance': distance,
                'url_detail': url_for('main.detail_item', item_id=item.id),
                'photo_url': url_for('main.uploaded_file', filename=photo.filename),
            })
    matches.sort(key=lambda row: row['distance'])
    return jsonify({'duplicates': matches[:10]})

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
        if item_id == cand_id:
            return jsonify({'error': 'Les deux identifiants doivent être différents.'}), 400

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

        fields_weights = matching.MATCH_CONFIG['fields_weights']
        _cfg = matching.MATCH_CONFIG

        score_text = matching.match_score(m1, m2, fields_weights=fields_weights)
        details = matching.match_explanation(m1, m2, fields_weights=fields_weights)

        # Bonus catégorie + date via helper partagé (même logique que detail_item)
        lost_i  = i1 if i1.status == Status.LOST else i2
        found_i = i2 if i1.status == Status.LOST else i1
        bonus = _item_pair_bonus(lost_i, found_i)

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
                hash_distance = _hamming_distance(
                    _primary_perceptual_hash(lost_i), _primary_perceptual_hash(found_i)
                )
                if hash_distance is not None and hash_distance <= PERCEPTUAL_HASH_DISTANCE:
                    img_img_pct = 100.0
                else:
                    sim2 = itm.image_image_similarity(img_lost_path, img_found_path)
                    img_img_pct = round(100.0 * float(sim2), 2)
        except Exception:
            img_img_pct = 0.0

        _cleanup_tmp_images()

        # Score final via helper partagé (formule identique à detail_item)
        final_score = _compute_weighted_score(score_text, img_sim_pct, img_img_pct, bonus)

        return jsonify({
            'item_id': i1.id,
            'candidate_id': i2.id,
            'score_base': score_text,
            'bonus': bonus,
            'score_final': final_score,
            'image_similarity': img_sim_pct,
            'image_image_similarity': img_img_pct,
            'weights': {
                'text': _cfg['text_weight'],
                'image': _cfg['image_weight'],
                'img_img': _cfg['img_img_weight'],
            },
            'details': details
        })
    except Exception:
        current_app.logger.exception('Échec de l’explication de correspondance')
        return jsonify({'error': 'Impossible de calculer l’explication demandée.'}), 500

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
                if not allowed_file(file.filename) or not _check_image_magic_bytes(file):
                    flash("La photo de carte d'identité doit être une image JPEG ou PNG valide.", "danger")
                    return redirect(url_for('main.headphone_loans'))
                img_bytes = file.read()
                mime_type = _guess_mime_from_ext(file.filename)
                id_card_photo_b64 = f'data:{mime_type};base64,' + base64.b64encode(img_bytes).decode('utf-8')
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
    if loan.return_date:
        return jsonify({'success': False, 'error': 'Ce prêt a déjà été retourné.'}), 409
    data = request.get_json(silent=True)
    if not data or 'signature' not in data:
        return jsonify({'success': False, 'error': 'Signature manquante'}), 400
    signature = data.get('signature')
    prefix = 'data:image/png;base64,'
    if not isinstance(signature, str) or not signature.startswith(prefix):
        return jsonify({'success': False, 'error': 'Format de signature invalide'}), 400
    try:
        signature_bytes = base64.b64decode(signature[len(prefix):], validate=True)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Signature invalide'}), 400
    if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n') or len(signature_bytes) > 2 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'Signature invalide ou trop volumineuse'}), 400
    loan.signature = signature
    loan.return_date = datetime.now(timezone.utc)
    db.session.commit()
    return {'success': True}

# ───────────────────────────────────────────────────────────────────────────────
# Routes de correspondance globale Lost↔Found (nouvelles)
# ───────────────────────────────────────────────────────────────────────────────
def get_all_candidate_pairs(seuil=60, skip_set=None):
    """Calcule toutes les paires Lost↔Found dont le score >= seuil.
    skip_set: ensemble de tuples (lost_id, found_id) à ignorer (déjà validés/rejetés si non affichés).
    Utilise _compute_weighted_score pour que les scores soient identiques à ceux de detail_item.
    """
    pairs = []
    lost_items  = Item.query.filter_by(status=Status.LOST).all()
    found_items = Item.query.filter_by(status=Status.FOUND).all()
    fields_weights = matching.MATCH_CONFIG['fields_weights']

    for lost in lost_items:
        for found in found_items:
            if skip_set and (lost.id, found.id) in skip_set:
                continue
            base_score = matching.match_score(lost, found, fields_weights)
            bonus = _item_pair_bonus(lost, found)
            score = _compute_weighted_score(base_score, 0.0, 0.0, bonus)
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

    # Précharger les sets validés/rejetés AVANT le scoring pour éviter les calculs inutiles
    validated_set = set()
    for m in Match.query.all():
        validated_set.add((m.lost_id, m.found_id))
        validated_set.add((m.found_id, m.lost_id))

    rejected_set = set()
    for r in RejectedPair.query.all():
        rejected_set.add((r.lost_id, r.found_id))
        rejected_set.add((r.found_id, r.lost_id))

    # Sauter les paires masquées (non affichées) pour éviter O(N×M) inutile
    skip_set: set[tuple] = set()
    if not show_validated:
        skip_set |= {(lid, fid) for lid, fid in validated_set if lid < fid}
    if not show_rejected:
        skip_set |= {(lid, fid) for lid, fid in rejected_set if lid < fid}

    all_pairs = get_all_candidate_pairs(seuil=seuil, skip_set=skip_set if skip_set else None)
    all_pairs = sorted(all_pairs, key=lambda x: x[2], reverse=True)

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
    lost = db.session.get(Item, lost_id)
    found = db.session.get(Item, found_id)
    if not lost or not found or lost.status != Status.LOST or found.status != Status.FOUND:
        flash("La paire à rejeter doit contenir un objet perdu et un objet trouvé disponibles.", "warning")
        return redirect(url_for('main.list_matches'))
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

    # Vérifier si déjà validé (les deux ordres, pour robustesse)
    match_exists = Match.query.filter(
        ((Match.lost_id == lost_id) & (Match.found_id == found_id)) |
        ((Match.lost_id == found_id) & (Match.found_id == lost_id))
    ).first()
    if match_exists:
        flash("Cette paire a déjà été validée.", "info")
        return redirect(url_for('main.list_matches'))

    if lost.status != Status.LOST or found.status != Status.FOUND:
        flash("L’objet n’est plus disponible pour correspondance.", "warning")
        return redirect(url_for('main.list_matches'))

    item_already_matched = Match.query.filter(
        (Match.lost_id.in_([lost_id, found_id])) |
        (Match.found_id.in_([lost_id, found_id]))
    ).first()
    if item_already_matched:
        flash("L’un des objets est déjà associé à une autre fiche.", "warning")
        return redirect(url_for('main.list_matches'))

    # Supprimer le RejectedPair s'il existait (la paire ne doit pas être à la fois rejetée et validée)
    stale_rejection = RejectedPair.query.filter(
        ((RejectedPair.lost_id == lost_id) & (RejectedPair.found_id == found_id)) |
        ((RejectedPair.lost_id == found_id) & (RejectedPair.found_id == lost_id))
    ).first()
    if stale_rejection:
        db.session.delete(stale_rejection)

    # Créer l'entrée Match
    new_match = Match(lost_id=lost_id, found_id=found_id)
    db.session.add(new_match)

    now = datetime.now(timezone.utc)
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
