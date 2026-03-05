// static/js/search.js

function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitQuery(); }
}
function submitSuggestion(btn) {
    document.getElementById("search-input").value = btn.textContent.trim();
    submitQuery();
}
function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

function submitQuery() {
    const input = document.getElementById("search-input");
    const query = input.value.trim();
    if (!query) return;

    const btn      = document.getElementById("search-btn");
    const box      = document.getElementById("search-box");
    const resultsW = document.getElementById("results-wrap");
    const echo     = document.getElementById("query-echo");
    const answerEl = document.getElementById("answer-text");
    const cardsS   = document.getElementById("cards-section");
    const grid     = document.getElementById("search-cards-grid");

    // Reset UI
    btn.disabled           = true;
    box.classList.add("loading");
    resultsW.style.display = "flex";
    echo.textContent       = `"${query}"`;
    answerEl.textContent   = "Buscando...";
    cardsS.style.display   = "none";
    grid.innerHTML         = "";
    document.getElementById("suggestions-row").style.display = "none";

    fetch("/search/query", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ query }),
    })
    .then(r => r.json())
    .then(data => {
        answerEl.textContent = data.answer || "Sin respuesta.";
        if (data.cards && data.cards.length > 0) {
            renderCards(data.cards, grid);
            cardsS.style.display = "block";
        }
    })
    .catch(() => { answerEl.textContent = "Error al conectar con el servidor."; })
    .finally(() => {
        btn.disabled = false;
        box.classList.remove("loading");
    });
}

function renderCards(cards, grid) {
    cards.forEach((card, i) => {
        const el = document.createElement("div");
        el.className = "s-card";
        el.style.animationDelay = `${i * 50}ms`;
        if (card.url) el.onclick = () => window.open(card.url, "_blank");

        const priceHTML = card.price
            ? `<div class="s-card-price"><span>${card.currency || "USD"}</span>${fmt(card.price)}</div>`
            : `<div class="s-card-price-na">Sin precio</div>`;

        const chips = [];
        if (card.ambientes)   chips.push(`${card.ambientes} amb.`);
        if (card.dormitorios) chips.push(`${card.dormitorios} dorm.`);
        if (card.banos)       chips.push(`${card.banos} baños`);
        if (card.m2_total)    chips.push(`${Math.round(card.m2_total)} m²`);

        el.innerHTML = `
            ${card.source ? `<span class="s-badge s-badge--${card.source}">${card.source}</span>` : ""}
            <div class="s-neighborhood">${card.neighborhood || "—"}</div>
            ${priceHTML}
            ${card.address ? `<div class="s-address">${card.address}</div>` : ""}
            ${chips.length ? `<div class="s-chips">${chips.map(c=>`<span class="s-chip">${c}</span>`).join("")}</div>` : ""}
        `;
        grid.appendChild(el);
    });
}

function fmt(n) { return Math.round(n).toLocaleString("es-AR"); }