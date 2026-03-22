document.addEventListener('DOMContentLoaded', function() {
  const itemForm = document.getElementById('itemForm');
  if (!itemForm) return;

  var submitted = false;
  itemForm.addEventListener('submit', function(e) {
    if (submitted) return;
    e.preventDefault();
    const form = this;
    const titre = (form.querySelector('input[name="title"]') || {}).value || '';
    const categoryId = (form.querySelector('select[name="category"]') || {}).value || '';

    if (!titre || !categoryId) {
      submitted = true;
      form.submit();
      return;
    }

    const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).getAttribute('content') || '';
    const body = new URLSearchParams({ title: titre, category_id: categoryId });
    fetch('/api/check_similar', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: body })
      .then(r => r.json())
      .then(function(response) {
        const doublonList = document.getElementById('doublonList');
        doublonList.innerHTML = '';
        const hasResults = response.similars && response.similars.length > 0;

        if (hasResults) {
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
          document.getElementById('doublonListContainer').style.display = '';
          document.getElementById('noDoublon').classList.add('d-none');
        } else {
          document.getElementById('doublonListContainer').style.display = 'none';
          document.getElementById('noDoublon').classList.remove('d-none');
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
