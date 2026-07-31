/**
 * Zone de signature autonome — aucune dépendance externe.
 *
 * Remplace signature_pad chargé depuis cdn.jsdelivr.net : sur le réseau d'un
 * festival, un CDN peut être injoignable, lent ou filtré, et la signature de
 * retour des casques devenait alors impossible sans le moindre message. Une
 * fonction utilisée au guichet ne doit dépendre que de notre propre serveur.
 *
 * API volontairement identique à celle de signature_pad pour les usages du
 * projet : clear(), isEmpty(), toDataURL().
 */
(function (global) {
  'use strict';

  function SignaturePad(canvas, options) {
    options = options || {};
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.penColor = options.penColor || '#111827';
    this.lineWidth = options.lineWidth || 2.2;
    this.backgroundColor = options.backgroundColor || '#ffffff';

    this._dessine = false;
    this._vide = true;
    this._dernier = null;
    this._ratio = 1;

    // Indispensable sur écran tactile : sans cela le navigateur interprète le
    // glissement comme un défilement de page au lieu d'un tracé.
    canvas.style.touchAction = 'none';
    canvas.style.userSelect = 'none';
    canvas.style.cursor = 'crosshair';

    this._brancherEvenements();
    this.ajusterTaille();
  }

  /**
   * Aligne la surface de dessin sur la taille réellement affichée, densité
   * d'écran comprise. Sans cela le bitmap reste à 300x150 par défaut : le trait
   * apparaît décalé par rapport au curseur et déborde de la zone visible.
   * À n'appeler que lorsque le canvas est visible (largeur non nulle).
   */
  SignaturePad.prototype.ajusterTaille = function () {
    var canvas = this.canvas;
    var largeur = canvas.offsetWidth;
    var hauteur = canvas.offsetHeight;
    if (!largeur || !hauteur) return false;

    var ratio = Math.max(global.devicePixelRatio || 1, 1);
    canvas.width = Math.round(largeur * ratio);
    canvas.height = Math.round(hauteur * ratio);
    this._ratio = ratio;

    this.ctx = canvas.getContext('2d');       // redimensionner réinitialise le contexte
    this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';
    this.ctx.lineWidth = this.lineWidth;
    this.ctx.strokeStyle = this.penColor;

    this._peindreFond();
    this._vide = true;
    return true;
  };

  SignaturePad.prototype._peindreFond = function () {
    var ctx = this.ctx;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.fillStyle = this.backgroundColor;      // PNG opaque : lisible à l'export
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.restore();
  };

  SignaturePad.prototype.clear = function () {
    this._peindreFond();
    this._vide = true;
    this._dessine = false;
    this._dernier = null;
  };

  SignaturePad.prototype.isEmpty = function () {
    return this._vide;
  };

  SignaturePad.prototype.toDataURL = function (type) {
    return this.canvas.toDataURL(type || 'image/png');
  };

  /** Coordonnées en pixels CSS : le contexte porte déjà l'échelle de densité. */
  SignaturePad.prototype._point = function (evt) {
    var rect = this.canvas.getBoundingClientRect();
    var source = evt;
    if (evt.touches && evt.touches.length) source = evt.touches[0];
    else if (evt.changedTouches && evt.changedTouches.length) source = evt.changedTouches[0];
    return {
      x: (source.clientX - rect.left) * (this.canvas.offsetWidth / rect.width),
      y: (source.clientY - rect.top) * (this.canvas.offsetHeight / rect.height)
    };
  };

  /** La surface de dessin correspond-elle encore à la taille affichée ? */
  SignaturePad.prototype._tailleObsolete = function () {
    var attendue = Math.round(this.canvas.offsetWidth * this._ratio);
    return !this.canvas.width || Math.abs(this.canvas.width - attendue) > 1;
  };

  SignaturePad.prototype._debut = function (evt) {
    // Souris : ne réagir qu'au bouton gauche.
    if (evt.button !== undefined && evt.button !== 0 && evt.type === 'mousedown') return;
    evt.preventDefault();
    // Le canvas a pu être mesuré avant que sa mise en page ne soit stabilisée
    // (modal en cours d'ouverture, fenêtre redimensionnée). On rattrape ici,
    // mais jamais si un tracé existe déjà : réajuster efface le dessin.
    if (this._vide && this._tailleObsolete()) this.ajusterTaille();
    this._dessine = true;
    this._dernier = this._point(evt);
    // Un simple clic doit laisser un point visible.
    var ctx = this.ctx;
    ctx.beginPath();
    ctx.arc(this._dernier.x, this._dernier.y, this.lineWidth / 2, 0, Math.PI * 2);
    ctx.fillStyle = this.penColor;
    ctx.fill();
    this._vide = false;
  };

  SignaturePad.prototype._deplacement = function (evt) {
    if (!this._dessine) return;
    evt.preventDefault();
    var point = this._point(evt);
    var ctx = this.ctx;
    ctx.beginPath();
    ctx.moveTo(this._dernier.x, this._dernier.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    this._dernier = point;
    this._vide = false;
  };

  SignaturePad.prototype._fin = function () {
    this._dessine = false;
    this._dernier = null;
  };

  SignaturePad.prototype._brancherEvenements = function () {
    var self = this;
    var canvas = this.canvas;

    // Pointer Events couvre souris, doigt et stylet. Repli sur souris + tactile
    // pour les navigateurs anciens, sans jamais brancher les deux à la fois
    // (ce qui doublerait chaque tracé).
    if (global.PointerEvent) {
      canvas.addEventListener('pointerdown', function (e) {
        canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
        self._debut(e);
      });
      canvas.addEventListener('pointermove', function (e) { self._deplacement(e); });
      canvas.addEventListener('pointerup', function () { self._fin(); });
      canvas.addEventListener('pointercancel', function () { self._fin(); });
      canvas.addEventListener('pointerleave', function () { self._fin(); });
    } else {
      canvas.addEventListener('mousedown', function (e) { self._debut(e); });
      canvas.addEventListener('mousemove', function (e) { self._deplacement(e); });
      global.addEventListener('mouseup', function () { self._fin(); });
      canvas.addEventListener('touchstart', function (e) { self._debut(e); }, { passive: false });
      canvas.addEventListener('touchmove', function (e) { self._deplacement(e); }, { passive: false });
      canvas.addEventListener('touchend', function () { self._fin(); });
    }
  };

  global.SignaturePad = global.SignaturePad || SignaturePad;
  global.SignaturePadLocal = SignaturePad;
})(window);
