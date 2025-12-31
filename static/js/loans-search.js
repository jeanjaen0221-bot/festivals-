// Live search for headphone loans (prêts de casques)
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('input[name="q"][placeholder*="nom"], input[name="q"][placeholder*="Filtrer"]');
    if (!searchInput) return;
    let lastValue = searchInput.value;

    let timeout = null;
    searchInput.addEventListener('input', function() {
        const value = searchInput.value;
        if (value === lastValue) return;
        lastValue = value;
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => {
            fetchLoans(value);
        }, 200);
    });

    function fetchLoans(query) {
        const url = new URL(window.location.href);
        url.searchParams.set('q', query);
        url.searchParams.set('ajax', '1');
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(resp => resp.text())
            .then(html => {
                // Replace only the table
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newTable = doc.querySelector('.table-responsive');
                if (newTable) {
                    const container = document.querySelector('.table-responsive');
                    if (container) container.replaceWith(newTable);
                }
            });
    }
});
