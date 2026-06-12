(function () {
  "use strict";

  const THEME_KEY = "devbrief-theme";
  const html = document.documentElement;

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    html.setAttribute("data-theme", saved || (prefersDark ? "dark" : "light"));
  }

  function toggleTheme() {
    const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function renderCard(article, large) {
    const img = escapeHtml(article.image || "");
    const title = escapeHtml(article.title || "");
    const summary = escapeHtml(article.summary || "");
    const source = escapeHtml(article.source || "");
    const published = escapeHtml(article.published || "");
    const category = escapeHtml(article.category_label || article.category || "");
    const url = escapeHtml(article.url || "#");

    return `
      <a href="${url}" target="_blank" rel="noopener noreferrer" class="news-card-link">
        <article class="news-card${large ? " large" : ""}">
          <img src="${img}" alt="" loading="lazy" onerror="this.src='/assets/logo.png'">
          <div class="news-card-body">
            <span class="category-tag">${category}</span>
            <h3>${title}</h3>
            ${summary ? `<p>${summary}</p>` : ""}
            <footer>
              <span>${source}</span>
              <span>${published}</span>
            </footer>
          </div>
        </article>
      </a>`;
  }

  function renderHero(featured) {
    const hero = document.getElementById("hero");
    if (!hero || !featured) return;

    const main = hero.querySelector(".hero-main");
    main.classList.remove("skeleton-block");
    main.innerHTML = `
      <a href="${escapeHtml(featured.url)}" target="_blank" rel="noopener noreferrer" class="hero-link">
        <div class="hero-image-wrap" style="background-image:url('${escapeHtml(featured.image)}')"></div>
        <div class="hero-content">
          <span class="chip">${escapeHtml(featured.category_label)}</span>
          <h1>${escapeHtml(featured.title)}</h1>
          <p>${escapeHtml(featured.summary || "")}</p>
          <div class="hero-meta">${escapeHtml(featured.source)} · ${escapeHtml(featured.published)}</div>
        </div>
      </a>`;
  }

  function renderMarket(quotes) {
    const list = document.getElementById("market-list");
    const ticker = document.getElementById("ticker-track");
    if (!quotes || !quotes.length) return;

    list.innerHTML = quotes.map(function (q) {
      const cls = q.positive ? "positive" : "negative";
      return `<li>
        <span>${escapeHtml(String(q.label))}</span>
        <span>
          <strong>R$ ${escapeHtml(String(q.value))}</strong>
          <span class="change ${cls}">${escapeHtml(String(q.change))}</span>
        </span>
      </li>`;
    }).join("");

    const items = quotes.map(function (q) {
      const cls = q.positive ? "positive" : "negative";
      return `<span class="ticker-item ${cls}">${escapeHtml(String(q.label))} R$ ${escapeHtml(String(q.value))} (${escapeHtml(String(q.change))})</span>`;
    }).join("");
    ticker.innerHTML = items + items;
  }

  function renderGrid(containerId, articles) {
    const el = document.getElementById(containerId);
    if (!el || !articles) return;
    el.innerHTML = articles.map(function (a) { return renderCard(a, false); }).join("");
  }

  function renderLatest(articles) {
    const grid = document.getElementById("latest-grid");
    if (!grid) return;
    grid.innerHTML = (articles || []).slice(0, 8).map(function (a) {
      return renderCard(a, false);
    }).join("");
  }

  function showBreaking(featured) {
    const bar = document.getElementById("breaking-bar");
    const text = document.getElementById("breaking-text");
    if (!bar || !text || !featured) return;
    bar.hidden = false;
    text.textContent = featured.title;
  }

  async function loadNews() {
    try {
      const res = await fetch("/api/news");
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Falha ao carregar");

      renderHero(data.featured);
      renderLatest(data.latest);
      renderMarket(data.market);
      showBreaking(data.featured);

      const cats = data.categories || {};
      renderGrid("grid-brasil", cats.brasil);
      renderGrid("grid-mercado", cats.mercado);
      renderGrid("grid-tecnologia", cats.tecnologia);
      renderGrid("grid-mundo", cats.mundo);

      const label = document.getElementById("updated-label");
      if (label && data.updated_at) {
        label.textContent = "Atualizado: " + data.updated_at;
      }
    } catch (err) {
      console.error(err);
      const label = document.getElementById("updated-label");
      if (label) label.textContent = "Notícias temporariamente indisponíveis.";
    }
  }

  async function handleSubscribe(event) {
    event.preventDefault();
    const form = event.target;
    const feedback = document.getElementById("form-feedback");
    const email = form.email.value.trim();
    const button = form.querySelector("button");

    feedback.textContent = "";
    feedback.className = "form-feedback";
    button.disabled = true;
    button.textContent = "Enviando...";

    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Erro ao inscrever");

      feedback.textContent = data.message;
      feedback.classList.add("success");
      form.reset();
    } catch (err) {
      feedback.textContent = err.message || "Não foi possível inscrever. Tente novamente.";
      feedback.classList.add("error");
    } finally {
      button.disabled = false;
      button.textContent = "Assinar grátis";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    loadNews();

    document.getElementById("theme-toggle")?.addEventListener("click", toggleTheme);
    document.getElementById("subscribe-form")?.addEventListener("submit", handleSubscribe);

    document.getElementById("menu-toggle")?.addEventListener("click", function () {
      document.querySelector(".main-nav")?.classList.toggle("open");
    });

    setInterval(loadNews, 5 * 60 * 1000);
  });
})();
