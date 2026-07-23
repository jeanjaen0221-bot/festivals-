from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, SubmitField, PasswordField, BooleanField, DateField, TimeField, MultipleFileField, RadioField, DecimalField, IntegerField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import DataRequired, Length, Email, Optional, EqualTo, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired

class HeadphoneLoanForm(FlaskForm):
    first_name = StringField('Prénom', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Nom', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Téléphone', validators=[DataRequired(), Length(max=50)])
    deposit_type = RadioField('Type de caution', choices=[('id_card', "Carte d'identité"), ('cash', 'Caution en argent')], validators=[DataRequired()])
    deposit_amount = DecimalField('Montant de la caution (€)', places=2, validators=[Optional(), NumberRange(min=0)])
    quantity = IntegerField('Nombre de casques prêtés', default=1, validators=[DataRequired(), NumberRange(min=1)])
    deposit_details = StringField('Détails de la caution', validators=[Length(max=200)])
    id_card_photo = FileField("Photo de la carte d'identité", validators=[FileAllowed(['jpg', 'jpeg', 'png'], "Images uniquement")])
    submit = SubmitField('Enregistrer le prêt')

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)
        if self.deposit_type.data == 'cash' and self.deposit_amount.data is None:
            self.deposit_amount.errors.append('Le montant de la caution est requis pour une caution en argent.')
            return False
        return valid

class SimpleCsrfForm(FlaskForm):
    pass

class ItemForm(FlaskForm):
    photos = MultipleFileField('Photos (jpg/png)', validators=[FileAllowed(['jpg', 'jpeg', 'png'], "Images uniquement")])
    title = StringField('Titre', validators=[DataRequired(), Length(max=100)])
    comments = TextAreaField('Description / Commentaires', validators=[Length(max=500)])
    LIEUX_CHOIX = [
        ('', 'Sélectionnez un lieu'),
        ('camping_famille', 'Camping Famille'),
        ('point_info', 'Point info Festival'),
        ('festivalier', 'Camping Festivalier'),
        ('autre', 'Autre (précisez)')
    ]
    # Pour objets perdus
    location = SelectField('Lieu de perte', choices=LIEUX_CHOIX, validators=[Optional()])
    location_other = StringField('Précisez le lieu de perte', validators=[Optional(), Length(max=100)])
    # Pour objets trouvés
    found_location = SelectField('Lieu de découverte', choices=LIEUX_CHOIX, validators=[Optional()])
    found_location_other = StringField('Précisez le lieu de découverte', validators=[Optional(), Length(max=100)])
    storage_location = SelectField('Lieu de stockage', choices=LIEUX_CHOIX, validators=[Optional()])
    storage_location_other = StringField('Précisez le lieu de stockage', validators=[Optional(), Length(max=100)])
    category = SelectField('Catégorie', coerce=lambda x: int(x) if x else None, validators=[], choices=[])
    new_category = StringField('Nouvelle catégorie', validators=[
        Optional(),
        Length(max=50, message='Le nom de la catégorie ne doit pas dépasser 50 caractères')
    ])
    # ── Champs structurés pour matching infaillible ─────────────────────────
    COLORS_CHOICES = [
        ('noir',    'Noir'),
        ('blanc',   'Blanc'),
        ('gris',    'Gris'),
        ('rouge',   'Rouge'),
        ('rose',    'Rose'),
        ('orange',  'Orange'),
        ('jaune',   'Jaune'),
        ('vert',    'Vert'),
        ('bleu',    'Bleu'),
        ('violet',  'Violet'),
        ('marron',  'Marron / Beige'),
        ('dore',    'Doré / Or'),
        ('argent',  'Argenté / Gris métal'),
        ('multicolore', 'Multicolore'),
        ('inconnu', 'Je ne sais pas'),
    ]
    DISTINCTIVE_CHOICES = [
        ('a_document_id',  "Contient un document d'identité (carte ID, passeport…)"),
        ('a_carte_bancaire', 'Contient une carte bancaire'),
        ('a_argent',       'Contient de l’argent liquide'),
        ('a_badge',        'Contient/est un badge festival'),
        ('a_cle',          'Contient des clés'),
        ('a_medicament',   'Contient des médicaments'),
        ('personnalise',   'Personnalisé / gravé / unique'),
        ('a_photo_enfant', 'Lié à un enfant'),
    ]
    item_color = SelectMultipleField(
        'Couleur(s) principale(s)',
        choices=COLORS_CHOICES,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    item_brand = StringField('Marque / Modèle visible', validators=[Optional(), Length(max=100)])
    item_distinctive = SelectMultipleField(
        'Signes distinctifs / Contenu particulier',
        choices=DISTINCTIVE_CHOICES,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    # ─────────────────────────────────────────────────────────────────────────
    reporter_name = StringField('Nom du déclarant', validators=[DataRequired(), Length(max=100)])
    reporter_email = StringField('Email du déclarant', validators=[Optional(), Email(), Length(max=150)])
    reporter_phone = StringField('Téléphone du déclarant', validators=[Length(max=50)])

    submit = SubmitField('Valider')
    
    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        # Charger les catégories existantes
        from models import Category
        # Définir les familles de catégories (doivent correspondre à la seed)
        FAMILLES = [
            ("Objets personnels", [
                "Téléphone", "Clés", "Portefeuille", "Carte bancaire", "Carte d'identité", "Permis de conduire", "Badge d'accès", "Papiers d’identité"
            ]),
            ("Accessoires", [
                "Sac à dos", "Sac à main", "Banane", "Pochette", "Trousseau"
            ]),
            ("Vêtements", [
                "Veste", "Pull", "Sweat", "T-shirt", "Pantalon", "Short", "Jupe", "Robe", "Casquette", "Chapeau", "Bonnet", "Écharpe", "Gants", "Chaussures", "Sandales"
            ]),
            ("Lunettes & optique", [
                "Lunettes de soleil", "Lunettes de vue"
            ]),
            ("Bijoux", [
                "Bijoux", "Bague", "Collier", "Bracelet", "Boucles d’oreilles"
            ]),
            ("Audio & tech", [
                "Écouteurs", "Casque audio", "Batterie externe", "Chargeur", "Câble USB"
            ]),
            ("Festival & camping", [
                "Tente", "Sac de couchage", "Matelas gonflable", "Lampe frontale", "Gourde", "Bouteille", "Verre réutilisable", "Badge festival", "Bracelet festival", "Pochette étanche", "Gobelet réutilisable", "Poncho pluie", "Bouchons d’oreille", "Crème solaire", "Plaid", "Tapis de sol", "Cendrier de poche"
            ]),
            ("Divers précieux", [
                "Argent liquide", "Carte cadeau"
            ]),
            ("Objets de transport", [
                "Vélo", "Trottinette", "Skateboard", "Clé de voiture", "Clé de moto"
            ]),
            ("Santé", [
                "Médicaments", "Boîte à médicaments", "Inhalateur", "Appareil auditif"
            ]),
            ("Autres", [
                "Livre", "Carnet", "Stylo", "Parapluie", "Briquet", "Jeu de cartes", "Doudou", "Peluche", "Jouet", "Accessoire animalier", "Accessoire de déguisement", "Maillot de bain"
            ]),
        ]
        # Charger toutes les catégories existantes
        categories = Category.query.order_by('name').all()
        # Regrouper par famille
        grouped = []
        for famille, noms in FAMILLES:
            groupe = [(str(c.id), c.name) for c in categories if c.name in noms]
            if groupe:
                grouped.append((famille, groupe))
        self.category.choices = [('', 'Sélectionnez une catégorie')] + grouped

    def validate(self, extra_validators=None):
        initial = super().validate(extra_validators=extra_validators)
        # Validation catégorie : au moins une des deux doit être remplie
        cat_selected = self.category.data and str(self.category.data).strip()
        new_cat_filled = self.new_category.data and self.new_category.data.strip()
        if not cat_selected and not new_cat_filled:
            self.category.errors.append("Veuillez sélectionner une catégorie ou en créer une nouvelle.")
            self.new_category.errors.append("Veuillez sélectionner une catégorie ou en créer une nouvelle.")
            return False
        # Validation spécifique selon le contexte (perdu/trouvé)
        if self._prefix == 'lost':
            if not self.location.data:
                self.location.errors.append('Merci de préciser le lieu de perte.')
                return False
            if self.location.data == 'autre' and (not self.location_other.data or not self.location_other.data.strip()):
                self.location_other.errors.append('Merci de préciser le lieu de perte.')
                return False
        elif self._prefix == 'found':
            # Désormais, lieu de découverte saisi en texte libre
            if not self.found_location_other.data or not self.found_location_other.data.strip():
                self.found_location_other.errors.append('Merci de préciser le lieu de découverte.')
                return False
            # storage_location obligatoire
            if not self.storage_location.data:
                self.storage_location.errors.append('Merci de préciser le lieu de stockage.')
                return False
            if self.storage_location.data == 'autre' and (not self.storage_location_other.data or not self.storage_location_other.data.strip()):
                self.storage_location_other.errors.append('Merci de préciser le lieu de stockage.')
                return False
        return initial

class ClaimForm(FlaskForm):
    claimant_name = StringField('Votre nom', validators=[DataRequired(), Length(max=100)])
    claimant_email = StringField('Votre email', validators=[DataRequired(), Email(), Length(max=150)])
    claimant_phone = StringField('Votre téléphone', validators=[Length(max=50)])
    photos = MultipleFileField('Photos de restitution (jpg/png)', validators=[FileAllowed(['jpg','jpeg','png'])])
    submit = SubmitField('Réclamer')

class ConfirmReturnForm(FlaskForm):
    return_photo = FileField('Photo de restitution (optionnelle)', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png'], "Images uniquement")])
    return_comment = TextAreaField('Commentaire de restitution', validators=[Length(max=500)])
    submit = SubmitField('Confirmer restitution')

class MatchForm(FlaskForm):
    match_with = SelectField(
        "Objet correspondant",
        coerce=int,
        validators=[DataRequired()]
    )
    submit_match = SubmitField("Confirmer correspondance")

class DeleteForm(FlaskForm):
    delete_password = StringField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Supprimer définitivement')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    remember = BooleanField('Se souvenir de moi')
    submit = SubmitField('Connexion')

class CategoryIconForm(FlaskForm):
    # Type d'icône : Bootstrap ou Image personnalisée
    icon_type = RadioField('Type d\'icône', choices=[
        ('bootstrap', 'Icône Bootstrap (vectorielle)'),
        ('custom', 'Image personnalisée (upload)')
    ], default='bootstrap', validators=[DataRequired()])
    
    # Champ pour icône Bootstrap
    icon_class = StringField('Classe d\'icône Bootstrap', validators=[
        Optional(),
        Length(min=3, max=50, message='La classe doit contenir entre 3 et 50 caractères')
    ], render_kw={'placeholder': 'Ex: bi bi-phone, bi bi-laptop, bi bi-bag'})
    
    # Champ pour image personnalisée
    custom_icon = FileField('Image personnalisée', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'svg'], 'Seuls les fichiers JPG, PNG et SVG sont autorisés')
    ])
    
    submit = SubmitField('Mettre à jour l\'icône')
    
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        
        # Validation conditionnelle selon le type choisi
        if self.icon_type.data == 'bootstrap':
            if not self.icon_class.data or not self.icon_class.data.strip():
                self.icon_class.errors.append('La classe d\'icône Bootstrap est requise')
                return False
            if not self.icon_class.data.startswith('bi '):
                self.icon_class.errors.append('La classe doit commencer par "bi " (ex: "bi bi-phone")')
                return False
        elif self.icon_type.data == 'custom':
            if not self.custom_icon.data:
                self.custom_icon.errors.append('Veuillez sélectionner une image')
                return False
        
        return True

class RegisterForm(FlaskForm):
    first_name = StringField('Prénom', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Nom', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Mot de passe', validators=[
        DataRequired(),
        Length(min=8, message='Le mot de passe doit contenir au moins 8 caractères.')
    ])
    password2 = PasswordField('Confirmer le mot de passe', validators=[DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Créer un compte administrateur')
    submit = SubmitField('Créer le compte')


class ShuttleScheduleDayForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()], format='%Y-%m-%d')
    label = StringField('Libellé du jour', validators=[DataRequired(), Length(max=100)])
    note = TextAreaField('Note (optionnelle)', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Enregistrer le jour')

class ShuttleScheduleSlotForm(FlaskForm):
    start_time = TimeField('Heure de début', validators=[DataRequired()])
    end_time = TimeField('Heure de fin', validators=[DataRequired()])
    from_location = StringField('Lieu de départ', validators=[DataRequired(), Length(max=100)])
    to_location = StringField('Lieu d\'arrivée', validators=[DataRequired(), Length(max=100)])
    note = StringField('Note (optionnelle)', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Enregistrer le créneau')

class ShuttleRouteStopForm(FlaskForm):
    name = StringField('Nom de l\'arrêt', validators=[DataRequired(), Length(max=120)])
    sequence = IntegerField('Ordre sur le parcours', validators=[DataRequired(), NumberRange(min=1)])
    dwell_minutes = IntegerField('Temps d\'arrêt (minutes)', default=0, validators=[DataRequired(), NumberRange(min=0)])
    note = StringField('Note (optionnelle)', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Enregistrer l\'arrêt')

class ShuttleSettingsForm(FlaskForm):
    mean_leg_minutes = IntegerField('Temps moyen entre 2 arrêts (minutes)', validators=[DataRequired(), NumberRange(min=1)])
    loop_enabled = BooleanField('Activer le mode boucle (repart de l\'arrêt final vers le premier)')
    bidirectional_enabled = BooleanField('Activer le sens bidirectionnel (aller/retour)')
    constrain_to_today_slots = BooleanField('Limiter le calcul aux créneaux du jour')
    display_direction = SelectField('Direction d\'affichage', choices=[('forward', 'Aller'), ('backward', 'Retour')])
    display_base_stop_sequence = IntegerField('Séquence de l\'arrêt de départ pour l\'affichage', validators=[Optional(), NumberRange(min=1)])
    submit = SubmitField('Enregistrer les réglages')

class ProductForm(FlaskForm):
    name = StringField('Nom de l\'article', validators=[DataRequired(), Length(max=120)])
    price = DecimalField('Prix TTC (€)', places=2, validators=[DataRequired(), NumberRange(min=0)])
    vat_rate = SelectField('TVA (%)', choices=[('21', '21%'), ('12', '12%'), ('6', '6%'), ('0', '0%')], validators=[DataRequired()])
    active = BooleanField('Actif', default=True)
    image = FileField('Image (jpg/png)', validators=[Optional(), FileAllowed(['jpg','jpeg','png'], 'Images uniquement')])
    submit = SubmitField('Enregistrer')
