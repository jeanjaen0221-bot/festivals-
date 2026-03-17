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
        url.searchParams.delete('page');
        fetch(url)
            .then(resp => resp.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newResults = doc.querySelector('#loans-results');
                if (newResults) {
                    const container = document.querySelector('#loans-results');
                    if (container) container.replaceWith(newResults);
                }
            });
    }
});
