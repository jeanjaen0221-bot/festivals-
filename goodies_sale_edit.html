/* ── Tour guidé bénévoles — Lost & Found Festival ────────────────────────── */
(function () {
  'use strict';

  var STORAGE_KEY = 'lf_tour_done';

  /* ── Définition des étapes ─────────────────────────────────────────────── */
  var STEPS = [
    {
      target: null,
      icon: '👋',
      title: 'Bienvenue !',
      text: 'Ce guide rapide te présente tous les outils disponibles. Navigation libre : tu n\'as rien à faire, juste lire et suivre les flèches.',
    },
    {
      target: '[data-tour="signaler"]',
      icon: '🚩',
      title: 'Signaler un objet',
      text: 'Clique ici pour déclarer un objet <strong>perdu</strong> ou <strong>trouvé</strong>. Remplis le formulaire avec un maximum de détails et, si possible, une photo.',
    },
    {
      target: '[data-tour="perdus"]',
      icon: '🔍',
      title: 'Objets perdus',
      text: 'Liste de tous les objets perdus déclarés. Filtre par catégorie, mot-clé ou date. Clique sur une fiche pour voir le détail complet.',
    },
    {
      target: '[data-tour="trouves"]',
      icon: '✅',
      title: 'Objets trouvés',
      text: 'Objets ramenés au point de dépôt. Un <strong>ruban vert</strong> indique qu\'une correspondance automatique a déjà été détectée.',
    },
    {
      target: '[data-tour="rendus"]',
      icon: '🔄',
      title: 'Objets rendus',
      text: 'Historique des objets restitués à leur propriétaire. Utile pour vérifier qu\'un objet a déjà bien été rendu.',
    },
    {
      target: '[data-tour="correspondances"]',
      icon: '🤖',
      title: 'Correspondances',
      text: 'Le système compare automatiquement perdus ↔ trouvés par IA. Un score coloré indique la probabilité. Clique sur <strong>Détails</strong> pour voir l\'analyse complète.',
    },
    {
      target: '[data-tour="messagerie"]',
      icon: '💬',
      title: 'Messagerie interne',
      text: 'Chat entre bénévoles. Envoie un message privé à un collègue directement depuis ici, sans quitter le site.',
    },
    {
      target: '[data-tour="trains"]',
      icon: '🚆',
      title: 'Horaires trains',
      text: 'Consulte les horaires de trains proches du festival pour informer les festivaliers qui demandent comment rentrer.',
    },
    {
      target: '[data-tour="navette"]',
      icon: '🚌',
      title: 'Navette festival',
      text: 'Horaires et arrêts de la navette festival. Mis à jour par l\'administration en temps réel.',
    },
    {
      target: '[data-tour="casques"]',
      icon: '🎧',
      title: 'Prêts de casques',
      text: 'Enregistre les prêts de casques audio avec caution (espèces, CB, pièce d\'identité). Retrouve les prêts en cours ou clôture un retour.',
    },
    {
      target: null,
      icon: '🎉',
      title: 'C\'est parti !',
      text: 'Tu connais maintenant tous les outils. Le bouton <strong>?</strong> en bas à droite te permet de relancer ce guide à tout moment.',
    },
  ];

  /* ── État ──────────────────────────────────────────────────────────────── */
  var current = 0;
  var overlay, svg, bubble, helpBtn;
  var activeHighlight = null;

  /* ── Init DOM ──────────────────────────────────────────────────────────── */
  function buildDOM() {
    /* Overlay SVG */
    overlay = document.createElement('div');
    overlay.id = 'lf-tour-overlay';

    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.id = 'lf-tour-svg';
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    overlay.appendChild(svg);
    document.body.appendChild(overlay);

    /* Bulle */
    bubble = document.createElement('div');
    bubble.id = 'lf-tour-bubble';
    bubble.setAttribute('role', 'dialog');
    bubble.setAttribute('aria-modal', 'false');
    bubble.setAttribute('aria-live', 'polite');
    document.body.appendChild(bubble);

    /* Bouton ? */
    helpBtn = document.createElement('button');
    helpBtn.id = 'lf-tour-help-btn';
    helpBtn.setAttribute('aria-label', 'Relancer le guide');
    helpBtn.innerHTML = '?';
    helpBtn.addEventListener('click', restartTour);
    document.body.appendChild(helpBtn);
  }

  /* ── SVG overlay avec découpe spotlight ───────────────────────────────── */
  function drawOverlay(rect) {
    var W = window.innerWidth;
    var H = window.innerHeight;
    var pad = 10;

    if (!rect) {
      /* Pas d'élément ciblé : fond plein semi-transparent */
      svg.innerHTML =
        '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="rgba(0,0,0,0.55)"/>';
      return;
    }

    var x = Math.max(0, rect.left - pad);
    var y = Math.max(0, rect.top - pad);
    var w = Math.min(W, rect.width + pad * 2);
    var h = Math.min(H, rect.height + pad * 2);
    var r = 10; /* border-radius du spotlight */

    /* Masque : rectangle plein moins la découpe arrondie */
    var id = 'lf-tour-clip-' + Date.now();
    svg.innerHTML =
      '<defs>' +
        '<clipPath id="' + id + '">' +
          '<path d="M0 0 H' + W + ' V' + H + ' H0 Z' +
            ' M' + (x + r) + ' ' + y +
            ' H' + (x + w - r) +
            ' Q' + (x + w) + ' ' + y + ' ' + (x + w) + ' ' + (y + r) +
            ' V' + (y + h - r) +
            ' Q' + (x + w) + ' ' + (y + h) + ' ' + (x + w - r) + ' ' + (y + h) +
            ' H' + (x + r) +
            ' Q' + x + ' ' + (y + h) + ' ' + x + ' ' + (y + h - r) +
            ' V' + (y + r) +
            ' Q' + x + ' ' + y + ' ' + (x + r) + ' ' + y +
            ' Z" fill-rule="evenodd"/>' +
        '</clipPath>' +
      '</defs>' +
      '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="rgba(0,0,0,0.55)" clip-path="url(#' + id + ')"/>';
  }

  /* ── Positionnement de la bulle ────────────────────────────────────────── */
  function positionBubble(rect) {
    var W = window.innerWidth;
    var H = window.innerHeight;
    var bw = 300;
    var margin = 18;

    /* Reset flèche */
    bubble.className = 'visible';

    if (!rect) {
      /* Centré */
      bubble.style.left = Math.max(8, (W - bw) / 2) + 'px';
      bubble.style.top  = Math.max(8, (H - bubble.offsetHeight) / 2) + 'px';
      bubble.classList.add('arrow-none');
      return;
    }

    var left, top, arrow;

    /* Essayer à droite */
    if (rect.right + margin + bw < W) {
      left  = rect.right + margin;
      top   = rect.top;
      arrow = 'arrow-left';
    }
    /* Essayer à gauche */
    else if (rect.left - margin - bw > 0) {
      left  = rect.left - margin - bw;
      top   = rect.top;
      arrow = 'arrow-right';
    }
    /* Essayer en bas */
    else if (rect.bottom + margin + 180 < H) {
      left  = Math.max(8, rect.left + rect.width / 2 - bw / 2);
      top   = rect.bottom + margin;
      arrow = 'arrow-top';
    }
    /* En haut sinon */
    else {
      left  = Math.max(8, rect.left + rect.width / 2 - bw / 2);
      top   = rect.top - margin - bubble.offsetHeight;
      arrow = 'arrow-bottom';
    }

    /* Clamper dans l'écran */
    left = Math.max(8, Math.min(left, W - bw - 8));
    top  = Math.max(8, Math.min(top, H - 200));

    bubble.style.left = left + 'px';
    bubble.style.top  = top + 'px';
    bubble.classList.add(arrow);
  }

  /* ── Rendu d'une étape ─────────────────────────────────────────────────── */
  function renderStep(idx) {
    var step = STEPS[idx];
    var total = STEPS.length;
    var pct = Math.round(((idx + 1) / total) * 100);

    var prevDisabled = idx === 0 ? 'disabled' : '';
    var isLast = idx === total - 1;
    var nextBtn = isLast
      ? '<button class="tour-btn tour-btn-finish" id="tour-btn-next">Terminer ✓</button>'
      : '<button class="tour-btn tour-btn-next" id="tour-btn-next">Suivant →</button>';

    bubble.innerHTML =
      '<div class="tour-bubble-header">' +
        '<span class="tour-step-label">Étape ' + (idx + 1) + ' / ' + total + '</span>' +
        '<button class="tour-close-btn" id="tour-btn-close" aria-label="Fermer le guide">✕</button>' +
      '</div>' +
      '<div class="tour-bubble-body">' +
        '<span class="tour-icon">' + step.icon + '</span>' +
        '<strong>' + step.title + '</strong><br>' +
        '<span>' + step.text + '</span>' +
        '<div class="tour-progress-bar"><div class="tour-progress-bar-inner" style="width:' + pct + '%"></div></div>' +
      '</div>' +
      '<div class="tour-bubble-footer">' +
        '<button class="tour-btn tour-btn-prev" id="tour-btn-prev" ' + prevDisabled + '>← Précédent</button>' +
        '<div class="tour-nav">' + nextBtn + '</div>' +
      '</div>';

    document.getElementById('tour-btn-close').addEventListener('click', endTour);
    document.getElementById('tour-btn-prev').addEventListener('click', function () { goTo(idx - 1); });
    document.getElementById('tour-btn-next').addEventListener('click', function () {
      if (isLast) { endTour(); } else { goTo(idx + 1); }
    });
  }

  /* ── Afficher une étape ────────────────────────────────────────────────── */
  function goTo(idx) {
    if (idx < 0 || idx >= STEPS.length) return;
    current = idx;

    /* Retirer highlight précédent */
    if (activeHighlight) {
      activeHighlight.classList.remove('lf-tour-highlight');
      activeHighlight = null;
    }

    var step = STEPS[idx];
    var target = step.target ? document.querySelector(step.target) : null;

    /* Sur mobile la sidebar est cachée — chercher l'équivalent offcanvas */
    if (!target && step.target) {
      var mobileAttr = step.target.replace('[data-tour=', '[data-tour-mobile=');
      target = document.querySelector(mobileAttr);
    }

    var rect = null;
    if (target) {
      /* Scroll vers l'élément si nécessaire */
      target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      target.classList.add('lf-tour-highlight');
      activeHighlight = target;
      rect = target.getBoundingClientRect();
    }

    overlay.classList.add('active');
    drawOverlay(rect);
    renderStep(idx);

    /* Positionner après rendu */
    requestAnimationFrame(function () {
      positionBubble(rect);
      bubble.classList.add('visible');
    });
  }

  /* ── Fin du tour ────────────────────────────────────────────────────────── */
  function endTour() {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) {}
    overlay.classList.remove('active');
    bubble.classList.remove('visible');
    svg.innerHTML = '';
    if (activeHighlight) {
      activeHighlight.classList.remove('lf-tour-highlight');
      activeHighlight = null;
    }
  }

  /* ── Relancer le tour ──────────────────────────────────────────────────── */
  function restartTour() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
    current = 0;
    bubble.classList.remove('visible');
    goTo(0);
  }

  /* ── Démarrage ─────────────────────────────────────────────────────────── */
  function startIfNeeded() {
    var done = false;
    try { done = localStorage.getItem(STORAGE_KEY) === '1'; } catch (e) {}
    if (!done) {
      setTimeout(function () { goTo(0); }, 600);
    }
  }

  /* ── Recalcul au resize ────────────────────────────────────────────────── */
  window.addEventListener('resize', function () {
    if (!overlay.classList.contains('active')) return;
    var step = STEPS[current];
    var target = step.target ? document.querySelector(step.target) : null;
    if (!target && step.target) {
      target = document.querySelector(step.target.replace('[data-tour=', '[data-tour-mobile='));
    }
    var rect = target ? target.getBoundingClientRect() : null;
    drawOverlay(rect);
    positionBubble(rect);
  });

  /* ── Point d'entrée ────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    buildDOM();
    startIfNeeded();
  });

})();
