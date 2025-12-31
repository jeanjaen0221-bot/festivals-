from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory
import os
import sys
import traceback
from werkzeug.utils import secure_filename

ALLOWED_ICON_EXTENSIONS = {"svg", "png", "jpg", "jpeg"}
ICONS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'icons')

# Ancien système d'icônes supprimé - plus besoin d'importer fetch_category_icons
from flask_login import login_required, current_user
from app import db
from models import User, ActionLog, Item, Status, HeadphoneLoan
from forms import SimpleCsrfForm, HeadphoneLoanForm
from datetime import datetime, timedelta

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Accès réservé à l'administrateur.", "danger")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

bp_admin = Blueprint('admin', __name__, url_prefix='/admin')

# Fonction fetch_icons supprimée - plus nécessaire avec Bootstrap Icons

@bp_admin.route('/category-icons')
@login_required
@admin_required
def category_icons():
    from models import Category
    from forms import CategoryIconForm
    
    categories = Category.query.order_by(Category.name).all()
    csrf_form = SimpleCsrfForm()
    icon_form = CategoryIconForm()
    
    return render_template('admin/category_icons.html', 
                         categories=categories, 
                         csrf_form=csrf_form,
                         icon_form=icon_form)

@bp_admin.route('/category-icons/<int:category_id>/delete-category', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    from models import Category
    category = Category.query.get_or_404(category_id)
    csrf_form = SimpleCsrfForm()
    if not csrf_form.validate_on_submit():
        flash("Erreur de validation du formulaire.", "danger")
        return redirect(url_for('admin.category_icons'))
    db.session.delete(category)
    db.session.commit()
    flash("Catégorie supprimée.", "success")
    return redirect(url_for('admin.category_icons'))

# Route pour servir les images personnalisées
@bp_admin.route('/category-icons/<int:category_id>/icon')
def category_icon_data(category_id):
    from models import Category
    category = Category.query.get_or_404(category_id)
    if not category.has_custom_icon:
        return '', 404
    return (category.icon_data, 200, {'Content-Type': category.icon_mime_type})

@bp_admin.route('/category-icons/<int:category_id>/update-icon', methods=['POST'])
@login_required
@admin_required
def update_category_icon(category_id):
    from models import Category
    from forms import CategoryIconForm
    import os
    
    category = Category.query.get_or_404(category_id)
    form = CategoryIconForm()
    
    if form.validate_on_submit():
        icon_type = form.icon_type.data
        
        if icon_type == 'bootstrap':
            # Utiliser une icône Bootstrap
            icon_class = form.icon_class.data.strip()
            
            # Supprimer l'image personnalisée si elle existe
            category.icon_data = None
            category.icon_mime_type = None
            category.icon_filename = None
            
            # Définir la classe Bootstrap
            category.icon_class = icon_class
            
            flash(f"Icône Bootstrap '{icon_class}' appliquée à la catégorie '{category.name}'", "success")
            
        elif icon_type == 'custom':
            # Utiliser une image personnalisée
            file = form.custom_icon.data
            
            if file and file.filename:
                # Validation de la taille (max 2MB)
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > 2 * 1024 * 1024:  # 2MB
                    flash("L'image ne doit pas dépasser 2MB", "danger")
                    return redirect(url_for('admin.category_icons'))
                
                # Lire et stocker l'image
                category.icon_data = file.read()
                category.icon_filename = file.filename
                
                # Déterminer le type MIME
                ext = file.filename.rsplit('.', 1)[-1].lower()
                mime_types = {
                    'png': 'image/png',
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'svg': 'image/svg+xml'
                }
                category.icon_mime_type = mime_types.get(ext, 'application/octet-stream')
                
                # Supprimer la classe Bootstrap (priorité à l'image)
                category.icon_class = None
                
                flash(f"Image personnalisée '{file.filename}' appliquée à la catégorie '{category.name}'", "success")
        
        db.session.commit()
        
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erreur dans {field}: {error}", "danger")
    
    return redirect(url_for('admin.category_icons'))

@bp_admin.route('/category-icons/<int:category_id>/remove-custom-icon', methods=['POST'])
@login_required
@admin_required
def remove_custom_icon(category_id):
    from models import Category
    
    category = Category.query.get_or_404(category_id)
    csrf_form = SimpleCsrfForm()
    
    if not csrf_form.validate_on_submit():
        flash("Erreur de validation du formulaire.", "danger")
        return redirect(url_for('admin.category_icons'))
    
    if category.has_custom_icon:
        category.icon_data = None
        category.icon_mime_type = None
        category.icon_filename = None
        db.session.commit()
        flash(f"Image personnalisée supprimée pour la catégorie '{category.name}'", "success")
    else:
        flash("Aucune image personnalisée à supprimer", "info")
    
    return redirect(url_for('admin.category_icons'))

# Route delete_category_icon supprimée - plus nécessaire avec Bootstrap Icons (toutes les catégories ont une icône par défaut)

@bp_admin.route('/')
@login_required
@admin_required
def admin_dashboard():
    nb_found = Item.query.filter_by(status=Status.FOUND).count()
    nb_lost = Item.query.filter_by(status=Status.LOST).count()
    nb_users = User.query.count()
    nb_deletions = Item.query.filter_by(status=Status.PENDING_DELETION).count()
    csrf_form = SimpleCsrfForm()
    return render_template(
        'admin/dashboard.html',
        nb_found=nb_found,
        nb_lost=nb_lost,
        nb_users=nb_users,
        nb_deletions=nb_deletions,
        csrf_form=csrf_form
    )

from forms import SimpleCsrfForm, HeadphoneLoanForm

@bp_admin.route('/deletion-requests')
@login_required
@admin_required
def deletion_requests():
    items = Item.query.filter_by(status=Status.PENDING_DELETION).order_by(Item.date_reported.desc()).all()
    from models import HeadphoneLoan, LoanStatus
    loans = HeadphoneLoan.query.filter_by(status=LoanStatus.PENDING_DELETION).order_by(HeadphoneLoan.loan_date.desc()).all()
    csrf_form = SimpleCsrfForm()
    return render_template('admin/deletion_requests.html', items=items, loans=loans, csrf_form=csrf_form)

@bp_admin.route('/deletion-requests/<int:item_id>/confirm', methods=['POST'])
@login_required
@admin_required
def confirm_deletion(item_id):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    ActionLog.query.session.add(ActionLog(user_id=current_user.id, action_type='confirm_deletion', details=f'Suppression validée pour objet {item_id}'))
    db.session.commit()
    flash("Suppression définitive effectuée.", "success")
    return redirect(url_for('admin.deletion_requests'))

@bp_admin.route('/deletion-requests/<int:loan_id>/confirm-loan', methods=['POST'])
@login_required
@admin_required
def confirm_loan_deletion(loan_id):
    from models import HeadphoneLoan
    from forms import SimpleCsrfForm
    form = SimpleCsrfForm()
    loan = HeadphoneLoan.query.get_or_404(loan_id)
    if form.validate_on_submit():
        ActionLog.query.session.add(ActionLog(
            user_id=current_user.id,
            action_type='confirm_loan_deletion',
            details=f'Suppression validée pour prêt casque {loan.id}'
        ))
        db.session.delete(loan)
        db.session.commit()
        flash("Prêt de casque supprimé définitivement.", "success")
    else:
        flash("Erreur de validation du formulaire.", "danger")
    return redirect(url_for('admin.deletion_requests'))

@bp_admin.route('/deletion-requests/<int:loan_id>/reject-loan', methods=['POST'])
@login_required
@admin_required
def reject_loan_deletion(loan_id):
    from models import HeadphoneLoan, LoanStatus
    from forms import SimpleCsrfForm
    form = SimpleCsrfForm()
    loan = HeadphoneLoan.query.get_or_404(loan_id)
    if form.validate_on_submit():
        # Restaure le statut original si connu, sinon ACTIVE par défaut
        if loan.previous_status:
            loan.status = loan.previous_status
            loan.previous_status = None
        else:
            loan.status = LoanStatus.ACTIVE
        db.session.commit()
        ActionLog.query.session.add(ActionLog(
            user_id=current_user.id,
            action_type='reject_loan_deletion',
            details=f'Restauration prêt casque {loan.id}'
        ))
        db.session.commit()
        flash("Demande de suppression rejetée. Le prêt est de nouveau visible.", "info")
    else:
        flash("Erreur de validation du formulaire.", "danger")
    return redirect(url_for('admin.deletion_requests'))

@bp_admin.route('/deletion-requests/<int:item_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_deletion(item_id):
    item = Item.query.get_or_404(item_id)
    # Restaure le statut original si connu, sinon LOST par défaut
    if item.previous_status:
        item.status = item.previous_status
        item.previous_status = None
    else:
        item.status = Status.LOST
    db.session.commit()
    ActionLog.query.session.add(ActionLog(user_id=current_user.id, action_type='reject_deletion', details=f'Rejet suppression objet {item_id}'))
    db.session.commit()
    flash("Demande de suppression rejetée. L'objet est de nouveau visible.", "info")
    return redirect(url_for('admin.deletion_requests'))

@bp_admin.route('/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@bp_admin.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    from forms import SimpleCsrfForm, HeadphoneLoanForm
    user = User.query.get_or_404(user_id)
    csrf_form = SimpleCsrfForm()
    return render_template('admin/user_detail.html', user=user, csrf_form=csrf_form)

@bp_admin.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    from forms import SimpleCsrfForm, HeadphoneLoanForm
    form = SimpleCsrfForm()
    user = User.query.get_or_404(user_id)
    if form.validate_on_submit():
        if user.id == current_user.id:
            flash("Vous ne pouvez pas modifier votre propre statut admin.", "danger")
        else:
            user.is_admin = not user.is_admin
            db.session.commit()
            flash("Statut administrateur modifié.", "success")
    else:
        flash("Erreur de validation du formulaire.", "danger")
    return redirect(url_for('admin.user_detail', user_id=user_id))

@bp_admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    from forms import SimpleCsrfForm, HeadphoneLoanForm
    form = SimpleCsrfForm()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for('admin.user_detail', user_id=user_id))
    if form.validate_on_submit():
        db.session.delete(user)
        db.session.commit()
        flash("Utilisateur supprimé.", "success")
        return redirect(url_for('admin.admin_users'))
    else:
        flash("Erreur de validation du formulaire.", "danger")
        return redirect(url_for('admin.user_detail', user_id=user_id))

@bp_admin.route('/loans')
@login_required
@admin_required  
def admin_loans():
    loans = HeadphoneLoan.query.order_by(HeadphoneLoan.loan_date.desc()).all()
    csrf_form = SimpleCsrfForm()
    return render_template('admin/loans.html', loans=loans, csrf_form=csrf_form)

@bp_admin.route('/helmet-rentals')
@login_required
@admin_required
def helmet_rentals():
    rentals = HeadphoneLoan.query.order_by(HeadphoneLoan.loan_date.desc()).all()
    csrf_form = SimpleCsrfForm()
    return render_template('admin/helmet_rentals.html', rentals=rentals, csrf_form=csrf_form)

@bp_admin.route('/helmet-rentals/export')
@login_required
@admin_required
def export_helmet_rentals():
    rentals = HeadphoneLoan.query.order_by(HeadphoneLoan.loan_date.desc()).all()
    # Format HTML (peut être adapté pour CSV)
    html = render_template('export_helmet_rentals.html', rentals=rentals)
    from flask import make_response
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=export_locations_casques.html'
    return response

@bp_admin.route('/helmet-rentals/<int:rental_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_rental(rental_id):
    form = SimpleCsrfForm()
    rental = HeadphoneLoan.query.get_or_404(rental_id)
    
    if form.validate_on_submit():
        # Enregistrer l'action dans les logs
        ActionLog.query.session.add(ActionLog(
            user_id=current_user.id, 
            action_type='delete_rental', 
            details=f'Suppression location casque {rental.first_name} {rental.last_name} (ID: {rental_id})'
        ))
        
        # Supprimer la location
        db.session.delete(rental)
        db.session.commit()
        
        flash("Location de casque supprimée avec succès.", "success")
    else:
        flash("Erreur de validation du formulaire.", "danger")
    
    return redirect(url_for('admin.helmet_rentals'))

@bp_admin.route('/logs')
@login_required
@admin_required
def admin_logs():
    # Configuration de la pagination et des filtres
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Augmenté de 25 à 50 pour plus de commodité
    search = request.args.get('search', '').strip()
    action_type = request.args.get('action_type', '').strip()
    
    # Construction de la requête de base avec jointure pour le chargement efficace
    query = ActionLog.query.join(User, ActionLog.user_id == User.id, isouter=True)
    
    # Filtrage par recherche
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                ActionLog.details.ilike(search_term),
                ActionLog.action_type.ilike(search_term),
                User.email.ilike(search_term)  # Recherche par email utilisateur
            )
        )
    
    # Filtrage par type d'action
    if action_type:
        query = query.filter(ActionLog.action_type == action_type)
    
    # Tri et pagination
    logs = query.order_by(ActionLog.timestamp.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)
    
    # Récupération des types d'actions uniques pour le filtre
    action_types = db.session.query(ActionLog.action_type)\
                           .distinct()\
                           .order_by(ActionLog.action_type)\
                           .all()
    action_types = [at[0] for at in action_types if at[0]]
    
    return render_template(
        'admin/logs.html', 
        logs=logs, 
        search=search,
        action_type=action_type,
        action_types=action_types
    )

@bp_admin.route('/logs/<int:log_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_log(log_id):
    print(f"[DEBUG] Appel de delete_log pour log_id={log_id}")
    print(f"[DEBUG] Méthode: {request.method}, is_json: {request.is_json}")
    try:
        print(f"[DEBUG] Données reçues: {request.get_json()}")
    except Exception as ex:
        print(f"[DEBUG] Impossible de parser le JSON: {ex}")
    if not request.is_json:
        print("[DEBUG] Requête non JSON, rejetée.")
        return jsonify({'error': 'Invalid request'}), 400
    
    log = ActionLog.query.get_or_404(log_id)
    print(f"[DEBUG] Log trouvé: id={log.id}, timestamp={log.timestamp}")
    # Ne pas permettre de supprimer des logs de moins d'une heure
    diff = datetime.utcnow() - log.timestamp
    print(f"[DEBUG] Différence UTCnow - log.timestamp: {diff}")
    if diff < timedelta(hours=1):
        print("[DEBUG] Log trop récent pour être supprimé.")
        return jsonify({
            'success': False,
            'message': 'Impossible de supprimer un log de moins d\'une heure'
        }), 400
    
    try:
        db.session.delete(log)
        db.session.commit()
        print("[DEBUG] Log supprimé avec succès.")
        return jsonify({
            'success': True,
            'message': 'Log supprimé avec succès'
        })
    except Exception as e:
        db.session.rollback()
        print(f"[DEBUG] Exception lors de la suppression: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la suppression du log: {str(e)}'
        }), 500
