import enum
from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum

class DepositType(enum.Enum):
    ID_CARD = 'id_card'
    CASH = 'cash'

class LoanStatus(enum.Enum):
    ACTIVE = 'active'
    PENDING_DELETION = 'pending_deletion'
    DELETED = 'deleted'

class HeadphoneLoan(db.Model):
    __tablename__ = 'headphone_loans'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    deposit_type = db.Column(db.Enum(DepositType), nullable=False)
    deposit_details = db.Column(db.String(200), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    deposit_amount = db.Column(db.Numeric(10, 2), nullable=True)
    loan_date = db.Column(db.DateTime, nullable=False, default=db.func.now())
    return_date = db.Column(db.DateTime, nullable=True)
    signature = db.Column(db.Text, nullable=True)  # Image base64 de la signature
    id_card_photo = db.Column(db.Text, nullable=True)  # Image base64 de la CI
    status = db.Column(db.Enum(LoanStatus), nullable=False, default=LoanStatus.ACTIVE, index=True)
    previous_status = db.Column(db.Enum(LoanStatus), nullable=True)

    def __repr__(self):
        return f'<HeadphoneLoan {self.first_name} {self.last_name} ({self.status.value})>'

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    # Système hybride d'icônes
    icon_class = db.Column(db.String(50), nullable=True)  # Classe Bootstrap Icon (ex: 'bi bi-wallet')
    icon_data = db.Column(db.LargeBinary, nullable=True)  # Image personnalisée (binaire)
    icon_mime_type = db.Column(db.String(50), nullable=True)  # Type MIME de l'image
    icon_filename = db.Column(db.String(100), nullable=True)  # Nom du fichier original
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    @property
    def has_custom_icon(self):
        """Vérifie si cette catégorie a une image personnalisée."""
        return self.icon_data is not None and self.icon_mime_type is not None
    
    @property
    def icon_bootstrap_class(self):
        """Retourne la classe Bootstrap Icon pour cette catégorie (si pas d'image personnalisée)."""
        # Priorité 1: Image personnalisée (pas d'icône Bootstrap si image présente)
        if self.has_custom_icon:
            return None
        
        # Priorité 2: Classe Bootstrap définie
        if self.icon_class:
            return self.icon_class
        
        # Priorité 3: Auto-assignment basé sur le nom avec gestion d'erreur
        try:
            from category_icons import get_icon_for_category
            return get_icon_for_category(self.name)
        except ImportError:
            # Fallback si category_icons.py n'est pas disponible
            return 'bi bi-box-seam'
        except Exception:
            # Fallback pour toute autre erreur
            return 'bi bi-box-seam'
    
    @property
    def icon_url(self):
        """Retourne l'URL de l'image personnalisée si elle existe."""
        if self.has_custom_icon:
            from flask import url_for
            return url_for('admin.category_icon_data', category_id=self.id)
        return None
    
    def get_icon_display(self):
        """Retourne les informations d'affichage de l'icône (type et valeur)."""
        if self.has_custom_icon:
            return {
                'type': 'image',
                'url': self.icon_url,
                'filename': self.icon_filename
            }
        else:
            return {
                'type': 'bootstrap',
                'class': self.icon_bootstrap_class
            }

class ShuttleScheduleDay(db.Model):
    __tablename__ = 'shuttle_schedule_days'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(100), nullable=False)  # Ex : "Vendredi 25 juillet 2025"
    note = db.Column(db.Text, nullable=True)
    slots = db.relationship('ShuttleScheduleSlot', backref='day', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<ShuttleScheduleDay {self.label}>'

class ShuttleScheduleSlot(db.Model):
    __tablename__ = 'shuttle_schedule_slots'
    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey('shuttle_schedule_days.id'), nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    from_location = db.Column(db.String(100), nullable=False)
    to_location = db.Column(db.String(100), nullable=False)
    note = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<ShuttleScheduleSlot {self.from_location} → {self.to_location}>'

# --- Navette: parcours & réglages ---
class ShuttleRouteStop(db.Model):
    __tablename__ = 'shuttle_route_stops'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sequence = db.Column(db.Integer, nullable=False, index=True)  # ordre sur le parcours
    dwell_minutes = db.Column(db.Integer, nullable=False, default=0)  # arrêt moyen au stop
    note = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<ShuttleRouteStop {self.sequence} - {self.name}>'

class ShuttleSettings(db.Model):
    __tablename__ = 'shuttle_settings'
    id = db.Column(db.Integer, primary_key=True)
    mean_leg_minutes = db.Column(db.Integer, nullable=False, default=5)  # temps moyen entre deux arrêts
    loop_enabled = db.Column(db.Boolean, nullable=False, default=False)
    bidirectional_enabled = db.Column(db.Boolean, nullable=False, default=False)
    constrain_to_today_slots = db.Column(db.Boolean, nullable=False, default=False)
    display_direction = db.Column(db.String(10), nullable=False, default='forward')  # 'forward'|'backward'
    display_base_stop_sequence = db.Column(db.Integer, nullable=True)  # sequence du stop de départ
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ShuttleSettings mean_leg_minutes={self.mean_leg_minutes}>'

class Status(enum.Enum):
    LOST = 'lost'
    FOUND = 'found'
    RETURNED = 'returned'
    PENDING_DELETION = 'pending_deletion'  # En attente de suppression

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(Status), nullable=False, default=Status.LOST, index=True)
    previous_status = db.Column(db.Enum(Status), nullable=True)  # Statut original avant demande suppression
    title = db.Column(db.String(100), nullable=False)
    comments = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=True)  # Lieu de perte (pour objets perdus)
    found_location = db.Column(db.String(100), nullable=True)  # Lieu où l'objet a été trouvé (pour objets trouvés)
    storage_location = db.Column(db.String(100), nullable=True)  # Lieu où l'objet est stocké (pour objets trouvés)
    date_reported = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    category = db.relationship('Category', backref=db.backref('items', lazy=True))
    reporter_name = db.Column(db.String(100), nullable=False)
    reporter_email = db.Column(db.String(150), nullable=True)
    reporter_phone = db.Column(db.String(50), nullable=True)
    photo_filename = db.Column(db.String(200), nullable=True)  # Pour compatibilité
    claimant_name = db.Column(db.String(100), nullable=True)
    claimant_email = db.Column(db.String(150), nullable=True)
    claimant_phone = db.Column(db.String(50), nullable=True)
    return_date = db.Column(db.DateTime, nullable=True)
    return_comment = db.Column(db.Text, nullable=True)
    return_photo_filename = db.Column(db.String(200), nullable=True)  # Photo prise lors de la restitution
    photos = db.relationship('ItemPhoto', backref='item', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Item {self.id} {self.title} ({self.status.value})>'


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    lost_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True)
    found_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True)
    date_validated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lost = db.relationship('Item', foreign_keys=[lost_id])
    found = db.relationship('Item', foreign_keys=[found_id])

    def __repr__(self):
        return f'<Match Lost:{self.lost_id} Found:{self.found_id}>'

class ItemPhoto(db.Model):
    __tablename__ = 'item_photos'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    actions = db.relationship('ActionLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ActionLog(db.Model):
    __tablename__ = 'action_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# --- Goodies sales (Belgium-ready TVA) ---
class PaymentMethod(enum.Enum):
    CASH = 'cash'
    CARD = 'card'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # prix TTC par unité
    vat_rate = db.Column(db.Integer, nullable=False, default=21)  # taux TVA en % (0,6,12,21)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Product {self.name} {self.price}€ TVA {self.vat_rate}%>'

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)  # total TTC avant arrondi cash
    total_vat_amount = db.Column(db.Numeric(10, 2), nullable=False)  # somme des TVA lignes
    rounded_total_amount = db.Column(db.Numeric(10, 2), nullable=True)  # total TTC arrondi (cash, règle 0.05)
    rounding_adjustment = db.Column(db.Numeric(10, 2), nullable=True)  # ajustement arrondi (cash)
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<Sale {self.id} {self.payment_method.value} {self.total_amount}€>'

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    product = db.relationship('Product')
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)  # prix TTC
    vat_rate = db.Column(db.Integer, nullable=False)  # taux % au moment de la vente
    line_total = db.Column(db.Numeric(10, 2), nullable=False)  # TTC
    vat_amount = db.Column(db.Numeric(10, 2), nullable=False)  # TVA incluse

    def __repr__(self):
        return f'<SaleItem sale={self.sale_id} product={self.product_id} qty={self.quantity}>'

class ZClosure(db.Model):
    __tablename__ = 'z_closures'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    from_ts = db.Column(db.DateTime, nullable=True)
    to_ts = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<ZClosure #{self.id} {self.from_ts}→{self.to_ts}>'
