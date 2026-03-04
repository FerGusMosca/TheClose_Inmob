// ── SIDEBAR TOGGLE ────────────────────────
const sidebar = document.getElementById('sidebar');
const toggle  = document.getElementById('sidebarToggle');

if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });
    // Close on outside click (mobile)
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 &&
            !sidebar.contains(e.target) &&
            !toggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
}

// ── TOPBAR DATE ───────────────────────────
const dateEl = document.getElementById('topbarDate');
if (dateEl) {
    const now = new Date();
    const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    dateEl.textContent = now.toLocaleDateString('es-AR', opts);
}