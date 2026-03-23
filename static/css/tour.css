/* ── Tour guidé bénévoles ─────────────────────────────────────────────────── */

/* Overlay plein écran avec découpe spotlight */
#lf-tour-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  pointer-events: none;
  transition: opacity 0.3s;
}
#lf-tour-overlay.active {
  pointer-events: auto;
}

/* SVG overlay — remplit tout l'écran, la découpe est un <rect> avec clip */
#lf-tour-svg {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 9001;
}

/* Bulle explicative */
#lf-tour-bubble {
  position: fixed;
  z-index: 9100;
  width: 300px;
  max-width: calc(100vw - 24px);
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.22), 0 2px 8px rgba(13,110,253,0.10);
  padding: 0;
  overflow: hidden;
  transition: top 0.28s cubic-bezier(.4,0,.2,1), left 0.28s cubic-bezier(.4,0,.2,1), opacity 0.2s;
  opacity: 0;
}
#lf-tour-bubble.visible {
  opacity: 1;
}

/* En-tête bulle */
.tour-bubble-header {
  background: linear-gradient(90deg, #0d6efd 0%, #6ea8fe 100%);
  color: #fff;
  padding: 10px 14px 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.tour-bubble-header .tour-step-label {
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.85;
  letter-spacing: 0.04em;
}
.tour-bubble-header .tour-close-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  opacity: 0.8;
  transition: opacity 0.15s;
}
.tour-bubble-header .tour-close-btn:hover { opacity: 1; }

/* Corps bulle */
.tour-bubble-body {
  padding: 14px 16px 4px;
  font-size: 0.92rem;
  color: #212529;
  line-height: 1.5;
}
.tour-bubble-body .tour-icon {
  font-size: 1.6rem;
  margin-bottom: 6px;
  display: block;
}

/* Barre de progression */
.tour-progress-bar {
  height: 3px;
  background: #e9ecef;
  margin: 10px 0 0;
}
.tour-progress-bar-inner {
  height: 3px;
  background: linear-gradient(90deg, #0d6efd, #6ea8fe);
  transition: width 0.3s;
}

/* Footer bulle */
.tour-bubble-footer {
  padding: 10px 16px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.tour-bubble-footer .tour-nav {
  display: flex;
  gap: 6px;
}
.tour-btn {
  border: none;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
.tour-btn:active { transform: scale(0.96); }
.tour-btn-prev {
  background: #f1f3f5;
  color: #495057;
}
.tour-btn-prev:hover { background: #dee2e6; }
.tour-btn-next {
  background: #0d6efd;
  color: #fff;
}
.tour-btn-next:hover { background: #0b5ed7; }
.tour-btn-finish {
  background: #198754;
  color: #fff;
}
.tour-btn-finish:hover { background: #157347; }

/* Flèche de la bulle (CSS triangle) */
#lf-tour-bubble::before {
  content: '';
  position: absolute;
  width: 0;
  height: 0;
  border: 9px solid transparent;
}
#lf-tour-bubble.arrow-left::before {
  left: -18px;
  top: 28px;
  border-right-color: #0d6efd;
}
#lf-tour-bubble.arrow-right::before {
  right: -18px;
  top: 28px;
  border-left-color: #0d6efd;
}
#lf-tour-bubble.arrow-top::before {
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  border-bottom-color: #0d6efd;
}
#lf-tour-bubble.arrow-bottom::before {
  bottom: -18px;
  left: 50%;
  transform: translateX(-50%);
  border-top-color: #0d6efd;
}
#lf-tour-bubble.arrow-none::before {
  display: none;
}

/* Highlight ring autour de l'élément ciblé */
.lf-tour-highlight {
  outline: 3px solid #0d6efd !important;
  outline-offset: 4px;
  border-radius: 8px;
  position: relative;
  z-index: 9050;
}

/* Bouton ? relancer le tour */
#lf-tour-help-btn {
  position: fixed;
  bottom: 22px;
  right: 22px;
  z-index: 8999;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #0d6efd;
  color: #fff;
  border: none;
  font-size: 1.2rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(13,110,253,0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, transform 0.15s, box-shadow 0.15s;
}
#lf-tour-help-btn:hover {
  background: #0b5ed7;
  transform: scale(1.08);
  box-shadow: 0 6px 20px rgba(13,110,253,0.45);
}
#lf-tour-help-btn[aria-label]::after {
  content: attr(aria-label);
  position: absolute;
  right: 52px;
  bottom: 8px;
  background: #212529;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 6px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
}
#lf-tour-help-btn:hover::after { opacity: 1; }
