// Auto-submit form when select filters change (neighborhood, rooms, portal)
document.querySelectorAll('.filter-select').forEach(select => {
    select.addEventListener('change', () => {
        select.closest('form').submit();
    });
});