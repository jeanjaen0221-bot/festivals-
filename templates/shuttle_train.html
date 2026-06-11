{% extends "base.html" %}
{% block title %}Horaires des trains{% endblock %}
{% block extra_head %}
<style>
  .flap-board { background:#0b0d10; color:#e9ecef; border-radius:12px; padding:12px; box-shadow:0 6px 20px rgba(0,0,0,.15); }
  .flap-header, .flap-row { display:grid; grid-template-columns: 90px 1fr 80px 90px 90px; gap:8px; align-items:center; }
  .flap-header { font-weight:700; letter-spacing:.06em; color:#adb5bd; text-transform:uppercase; padding:8px 6px; }
  .flap-row { padding:6px; border-top:1px solid rgba(255,255,255,.06); }
  .flap-cell { background:#11151a; border:1px solid #1b222a; border-radius:6px; padding:8px 10px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size:1.05rem; min-height:40px; display:flex; align-items:center; box-shadow: inset 0 -2px 0 rgba(255,255,255,.04), 0 2px 8px rgba(0,0,0,.25); }
  .flap-cell.muted { color:#93a1b0; }
  .flap-cell.center { justify-content:center; }
  .flap-cell.delay { color:#ffd166; }
  .flip { animation: flap-in .6s ease; transform-origin: top; }
  @keyframes flap-in { 0% { transform: rotateX(90deg); opacity:.2;} 100% { transform: rotateX(0deg); opacity:1; } }
  @media (max-width: 576px) { .flap-header, .flap-row { grid-template-columns: 74px 1fr 64px 64px 74px; } .flap-cell { font-size:.95rem; padding:6px 8px; } }
  .train-autorefresh { color:#6c757d; font-size:.9rem; margin-top:6px; }
  .station-title { color:#e9ecef; }
  .clickable-dest { cursor:pointer; text-decoration:underline dotted #6c757d; transition:background .15s; }
  .clickable-dest:hover { background:#1c2535 !important; }
  .stops-row { background:#0d1117; padding:10px 14px; border-top:1px solid rgba(255,255,255,.05); animation:flap-in .25s ease; }
  .stops-inline { display:flex; flex-wrap:wrap; gap:4px; align-items:center; font-size:.85rem; }
  .stop-arrow { color:#4a5568; padding:0 2px; }
  .stop-chip { background:#11151a; border:1px solid #2b3340; border-radius:6px; padding:3px 10px; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Courier New",monospace; white-space:nowrap; }
  .stop-chip b { color:#e9ecef; }
  .stop-chip .stop-time { color:#6c757d; font-size:.8em; margin-left:4px; }
  .stop-chip .stop-delay { color:#ffd166; font-size:.8em; margin-left:2px; }
  .stop-chip.passed { opacity:.4; }
  .stop-chip.origin { border-color:#0dcaf0; }
  .stop-chip.dest { border-color:#198754; }
  .stops-label { color:#6c757d; font-size:.8rem; margin-right:4px; white-space:nowrap; }
  .stops-err { color:#ffd166; font-size:.85rem; }
</style>
{% endblock %}
{% block content %}
<div class="container py-4">
  <h1 class="mb-4"><i class="bi bi-train-front"></i> Horaires des trains</h1>
  <div class="alert alert-info small py-2 mb-3">
    <i class="bi bi-info-circle"></i> Affichage type tableau d'aéroport. Les lignes se mettent à jour automatiquement.
  </div>
  <form id="station-search-form" class="row g-3 mb-4">
    <div class="col-md-8">
      <div class="position-relative">
        <input type="text" class="form-control form-control-lg" id="station-input" placeholder="Rechercher une gare (ex: Wavre)" autocomplete="off">
        <div id="station-suggestions" class="list-group position-absolute w-100" style="z-index:10;"></div>
      </div>
    </div>
    <div class="col-md-4">
      <button type="submit" class="btn btn-primary btn-lg w-100"><i class="bi bi-search"></i> Rechercher</button>
    </div>
  </form>
  <div id="train-results">
    <div class="alert alert-info">Veuillez rechercher une gare pour afficher les prochains départs.</div>
  </div>
</div>
<script src="{{ url_for('static', filename='js/train_schedule.js') }}?v=20260611-1"></script>
{% endblock %}
