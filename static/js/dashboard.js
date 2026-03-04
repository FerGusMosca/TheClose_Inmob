// ── NAVIGATE TO SEARCH WITH PREFILL ───────
function goToSearch(btn) {
    const text = btn.textContent.replace(/^💬\s*/, '').trim();
    window.location.href = `/busqueda?q=${encodeURIComponent(text)}`;
}

// ── ANIMATE KPI COUNTERS ──────────────────
document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    const target = parseInt(el.dataset.target, 10);
    if (target === 0) return; // nothing to animate yet
    let current = 0;
    const step = Math.ceil(target / 40);
    const timer = setInterval(() => {
        current = Math.min(current + step, target);
        el.textContent = current.toLocaleString('es-AR');
        if (current >= target) clearInterval(timer);
    }, 30);
});