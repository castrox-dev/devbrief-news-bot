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

  function showLoadingState() {
    const label = document.getElementById("updated-label");
    if (label) label.textContent = "Buscando notícias agora...";

    const hero = document.querySelector(".hero-main");
    if (hero && hero.classList.contains("skeleton-block")) {
      hero.classList.remove("skeleton-block");
      hero.innerHTML = `
        <div class="hero-content empty-hero loading-hero">
          <span class="chip">Atualizando</span>
          <h1>Buscando as últimas notícias...</h1>
          <p>Aguarde, estamos coletando RSS em tempo real.</p>
          <div class="loading-spinner" aria-hidden="true"></div>
        </div>`;
    }
  }

  function showEmptyState(message) {
    const label = document.getElementById("updated-label");
    if (label) label.textContent = message || "Nenhuma notícia disponível no momento.";

    const hero = document.querySelector(".hero-main");
    if (hero) {
      hero.classList.remove("skeleton-block");
      hero.innerHTML = `
        <div class="hero-content empty-hero">
          <span class="chip">Aguarde</span>
          <h1>Carregando as últimas notícias...</h1>
          <p>O site atualiza a cada 5 minutos. Se persistir, recarregue a página.</p>
        </div>`;
    }
  }

  async function loadNews() {
    showLoadingState();
    try {
      const res = await fetch("/api/news?t=" + Date.now(), { cache: "no-store" });
      const raw = await res.text();
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error("Servidor retornou resposta inválida. Aguarde o redeploy.");
      }
      if (!res.ok || !data.ok) throw new Error(data.error || "Falha ao carregar");

      if (!data.featured && (!data.latest || !data.latest.length)) {
        showEmptyState("Sincronizando notícias pela primeira vez...");
        return;
      }

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
      if (label) {
        const source = data.source === "database" ? "" : " (tempo real)";
        label.textContent = data.updated_at
          ? "Atualizado: " + data.updated_at + source
          : "Notícias atualizadas";
      }
    } catch (err) {
      console.error(err);
      showEmptyState("Notícias temporariamente indisponíveis. Recarregue em alguns segundos.");
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
    showLoadingState();
    loadNews();

    document.getElementById("theme-toggle")?.addEventListener("click", toggleTheme);
    document.getElementById("subscribe-form")?.addEventListener("submit", handleSubscribe);

    document.getElementById("menu-toggle")?.addEventListener("click", function () {
      document.querySelector(".main-nav")?.classList.toggle("open");
    });

    setInterval(loadNews, 5 * 60 * 1000);
  });
})();
