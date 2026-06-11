document.addEventListener('DOMContentLoaded', function() {
  const itemForm = document.getElementById('itemForm');
  if (!itemForm) return;

  var submitted = false;

  function getCheckedValues(nameAttr) {
    return Array.from(itemForm.querySelectorAll('input[type="checkbox"][name="' + nameAttr + '"]:checked'))
      .map(function(cb) { return cb.value; }).join(',');
  }
  function getFormStatus() {
    if (itemForm.querySelector('[name="submit_lost"]')) return 'lost';
    if (itemForm.querySelector('[name="submit_found"]')) return 'found';
    return '';
  }
  function buildBody(titre, categoryId) {
    var colorCb = itemForm.querySelector('input[type="checkbox"][value="noir"]');
    var distCb  = itemForm.querySelector('input.distinctive-check');
    var brandEl = itemForm.querySelector('[id$="item-brand"]');
    return new URLSearchParams({
      title: titre,
      category_id: categoryId,
      status: getFormStatus(),
      colors: colorCb ? getCheckedValues(colorCb.getAttribute('name')) : '',
      brand: brandEl ? brandEl.value.trim() : '',
      distinctive: distCb ? getCheckedValues(distCb.getAttribute('name')) : '',
    });
  }

  var previewTimer = null;
  var lastPreviewKey = '';
  function renderPreview(candidates) {
    var panel = document.getElementById('live-candidates-panel');
    if (!panel) return;
    if (!candidates || !candidates.length) { panel.innerHTML = ''; panel.style.display = 'none'; return; }
    var lbl = getFormStatus() === 'found' ? 'perdu' : 'trouv\u00e9';
    var lbp = candidates.length > 1 ? lbl + 's' : lbl;
    var html = '<div class="alert alert-warning border-2 mb-3 p-2">'
      + '<div class="fw-bold mb-1"><i class="bi bi-search-heart me-1"></i>' + candidates.length + ' objet(s) ' + lbp + ' potentiellement correspondant(s)</div>'
      + '<ul class="list-unstyled mb-1">';
    candidates.forEach(function(c) {
      html += '<li class="py-1 border-bottom"><strong>' + c.title + '</strong>'
        + ' <span class="badge bg-secondary">' + c.category + '</span>'
        + ' <span class="text-muted small">' + c.date + '</span>'
        + ' <span class="badge bg-warning text-dark ms-1">' + c.score + '%</span></li>';
    });
    html += '</ul><div class="small text-muted"><i class="bi bi-info-circle"></i> V\u00e9rifiez si c\'est le m\u00eame objet avant d\'enregistrer.</div></div>';
    panel.innerHTML = html;
    panel.style.display = '';
  }
  function triggerLivePreview() {
    var titreEl = itemForm.querySelector('input[name$="-title"], input[name="title"]');
    var catEl   = itemForm.querySelector('select[name$="-category"], select[name="category"]');
    var titre = titreEl ? titreEl.value : '';
    var cat   = catEl   ? catEl.value   : '';
    if (!titre || !cat) { renderPreview([]); return; }
    var key = titre + '|' + cat + '|' + getFormStatus();
    if (key === lastPreviewKey) return;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function() {
      lastPreviewKey = key;
      var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).getAttribute('content') || '';
      fetch('/api/check_similar', { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: buildBody(titre, cat) })
        .then(function(r) { return r.json(); })
        .then(function(resp) { renderPreview(resp.candidates || []); })
        .catch(function() {});
    }, 700);
  }
  var titreInput = itemForm.querySelector('input[name$="-title"], input[name="title"]');
  var catSelect  = itemForm.querySelector('select[name$="-category"], select[name="category"]');
  if (titreInput) titreInput.addEventListener('input', triggerLivePreview);
  if (catSelect)  catSelect.addEventListener('change', triggerLivePreview);
  document.addEventListener('structuredFieldChange', triggerLivePreview);
  if (titreInput && titreInput.closest('.mb-3')) {
    var panel = document.createElement('div');
    panel.id = 'live-candidates-panel';
    panel.style.display = 'none';
    titreInput.closest('.mb-3').insertAdjacentElement('afterend', panel);
  }

  itemForm.addEventListener('submit', function(e) {
    if (submitted) return;
    e.preventDefault();
    const form = this;
    const titre = (form.querySelector('input[name$="-title"], input[name="title"]') || {}).value || '';
    const categoryId = (form.querySelector('select[name$="-category"], select[name="category"]') || {}).value || '';

    if (!titre || !categoryId) {
      submitted = true;
      form.submit();
      return;
    }

    const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).getAttribute('content') || '';
    fetch('/api/check_similar', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: buildBody(titre, categoryId) })
      .then(r => r.json())
      .then(function(response) {
        const doublonList = document.getElementById('doublonList');
        doublonList.innerHTML = '';
        const hasSimilars   = response.similars   && response.similars.length   > 0;
        const hasCandidates = response.candidates && response.candidates.length > 0;

        if (hasSimilars) {
          var hdr = document.createElement('li');
          hdr.className = 'fw-semibold text-warning mb-1';
          hdr.innerHTML = '<i class="bi bi-copy me-1"></i>D\u00e9clarations similaires (possible doublon) :';
          doublonList.appendChild(hdr);
          response.similars.forEach(function(item) {
            let thumbHtml = '';
            if (item.photo_url) {
              thumbHtml = `<img src="${item.photo_url}" alt="Photo" class="rounded me-3" style="width:56px;height:56px;object-fit:cover;">`;
            } else if (item.category_icon_url) {
              thumbHtml = `<img src="${item.category_icon_url}" alt="Ic\u00f4ne" class="rounded me-3" style="width:56px;height:56px;object-fit:cover;">`;
            } else if (item.category_icon_class) {
              thumbHtml = `<div class="bg-light d-inline-flex align-items-center justify-content-center text-muted me-3" style="width:56px;height:56px;border-radius:0.375rem;"><i class="${item.category_icon_class}" style="font-size:1.5rem;"></i></div>`;
            } else {
              thumbHtml = `<div class="bg-light d-inline-flex align-items-center justify-content-center text-muted me-3" style="width:56px;height:56px;border-radius:0.375rem;"><i class="bi bi-box-seam"></i></div>`;
            }
            const cat = item.category_name ? `<span class="badge bg-secondary ms-2">${item.category_name}</span>` : '';
            const li = document.createElement('li');
            li.className = 'd-flex align-items-center mb-3';
            li.innerHTML = `${thumbHtml}<div class="flex-grow-1"><a href="${item.url_detail}" target="_blank" class="fw-bold text-decoration-none">${item.title}</a>${cat}<br><span class="text-muted small">Score : ${item.score}%</span></div>`;
            doublonList.appendChild(li);
          });
        }

        if (hasCandidates) {
          var hdr2 = document.createElement('li');
          hdr2.className = 'fw-semibold text-success mb-1 mt-2';
          var oppLbl = getFormStatus() === 'found' ? 'perdu(s)' : 'trouv\u00e9(s)';
          hdr2.innerHTML = '<i class="bi bi-link-45deg me-1"></i>Objet(s) ' + oppLbl + ' correspondant(s) \u2014 v\u00e9rifiez si c\'est le m\u00eame objet :';
          doublonList.appendChild(hdr2);
          response.candidates.forEach(function(c) {
            var li2 = document.createElement('li');
            li2.className = 'd-flex align-items-center mb-2';
            li2.innerHTML = '<div class="bg-success-subtle d-inline-flex align-items-center justify-content-center me-3 rounded" style="width:56px;height:56px;"><i class="bi bi-check-circle text-success" style="font-size:1.5rem;"></i></div>'
              + '<div class="flex-grow-1"><strong>' + c.title + '</strong> <span class="badge bg-secondary">' + c.category + '</span>'
              + '<br><span class="text-muted small">' + c.date + ' \u2014 Score\u00a0: ' + c.score + '%</span></div>';
            doublonList.appendChild(li2);
          });
        }

        if (hasSimilars || hasCandidates) {
          document.getElementById('doublonListContainer').style.display = '';
          document.getElementById('noDoublon').classList.add('d-none');
        } else {
          document.getElementById('doublonListContainer').style.display = 'none';
          document.getElementById('noDoublon').classList.remove('d-none');
        }

        var titleEl = document.getElementById('doublonModalTitle');
        var confirmBtn2 = document.getElementById('confirmSubmit');
        if (titleEl) {
          if (hasSimilars && hasCandidates) {
            titleEl.textContent = 'Doublons et correspondances d\u00e9tect\u00e9s';
            if (confirmBtn2) confirmBtn2.textContent = 'Signaler quand m\u00eame';
          } else if (hasSimilars) {
            titleEl.textContent = 'D\u00e9claration similaire d\u00e9tect\u00e9e';
            if (confirmBtn2) confirmBtn2.textContent = 'Signaler quand m\u00eame';
          } else if (hasCandidates) {
            titleEl.textContent = 'Correspondance potentielle trouv\u00e9e';
            if (confirmBtn2) confirmBtn2.textContent = 'C\'est un autre objet, continuer';
          } else {
            titleEl.textContent = 'V\u00e9rification avant envoi';
            if (confirmBtn2) confirmBtn2.textContent = 'Confirmer et enregistrer';
          }
        }

        const modal = new bootstrap.Modal(document.getElementById('doublonModal'));
        modal.show();
        const confirmBtn = document.getElementById('confirmSubmit');
        const confirmHandler = function() {
          modal.hide();
          confirmBtn.removeEventListener('click', confirmHandler);
          submitted = true;
          form.submit();
        };
        confirmBtn.addEventListener('click', confirmHandler);
      })
      .catch(function() { form.submit(); });
  });
});
