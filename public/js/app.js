(function () {
  "use strict";

  const THEME_KEY = "devbrief-theme";
  const html = document.documentElement;
  const i18n = window.DevBriefI18n;

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

  function initLang() {
    i18n.setLang(i18n.getLang());
    i18n.applyI18n();
    i18n.syncLangToggle();
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function articlePageUrl(url) {
    return "/noticia.html?u=" + encodeURIComponent(url || "") + "&lang=" + i18n.getLang();
  }

  function renderCard(article) {
    const img = escapeHtml(article.image || "");
    const title = escapeHtml(article.title || "");
    const summary = escapeHtml(article.summary || "");
    const source = escapeHtml(article.source || "");
    const published = escapeHtml(article.published || "");
    const category = escapeHtml(i18n.categoryLabel(article.category) || article.category_label || article.category || "");
    const internalUrl = escapeHtml(articlePageUrl(article.url));

    return `
      <article class="news-card">
        <a href="${internalUrl}" class="news-card-image-link">
          <img src="${img}" alt="" loading="lazy" onerror="this.onerror=null;this.src='/assets/logo.png'">
        </a>
        <div class="news-card-body">
          <span class="category-tag">${category}</span>
          <h3><a href="${internalUrl}" class="news-card-title-link">${title}</a></h3>
          ${summary ? `<p>${summary}</p>` : ""}
          <footer>
            <span>${source}</span>
            <span>${published}</span>
          </footer>
          <a href="${internalUrl}" class="read-more">${escapeHtml(i18n.t("read.more"))}</a>
        </div>
      </article>`;
  }

  function renderHero(featured) {
    const hero = document.getElementById("hero");
    if (!hero || !featured) return;

    const internalUrl = escapeHtml(articlePageUrl(featured.url));
    const main = hero.querySelector(".hero-main");
    main.classList.remove("skeleton-block");
    main.innerHTML = `
      <div class="hero-link">
        <a href="${internalUrl}" class="hero-image-wrap" style="background-image:url('${escapeHtml(featured.image)}')"></a>
        <div class="hero-content">
          <span class="chip">${escapeHtml(i18n.categoryLabel(featured.category) || featured.category_label)}</span>
          <h1><a href="${internalUrl}" class="hero-title-link">${escapeHtml(featured.title)}</a></h1>
          <p>${escapeHtml(featured.summary || "")}</p>
          <div class="hero-meta">${escapeHtml(featured.source)} · ${escapeHtml(featured.published)}</div>
          <a href="${internalUrl}" class="read-more hero-read-more">${escapeHtml(i18n.t("read.more"))}</a>
        </div>
      </div>`;
  }

  function parseAwesomeQuotes(data) {
    const map = { USDBRL: "USD/BRL", EURBRL: "EUR/BRL", BTCBRL: "BTC/BRL" };
    const quotes = [];
    Object.keys(map).forEach(function (key) {
      const item = data[key];
      if (!item) return;
      const pctRaw = String(item.pctChange || "0").replace(",", ".");
      const pctValue = parseFloat(pctRaw) || 0;
      quotes.push({
        label: map[key],
        value: String(item.bid || "—"),
        change: (pctValue >= 0 ? "+" : "") + pctValue.toFixed(2) + "%",
        positive: pctValue >= 0,
      });
    });
    return quotes;
  }

  async function fetchMarketClientFallback() {
    try {
      const res = await fetch(
        "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL",
        { cache: "no-store" }
      );
      if (!res.ok) return [];
      const data = await res.json();
      return parseAwesomeQuotes(data);
    } catch (err) {
      console.warn("Fallback cliente de cotações falhou:", err);
      return [];
    }
  }

  async function renderMarket(quotes) {
    const list = document.getElementById("market-list");
    const ticker = document.getElementById("ticker-track");
    if (!list || !ticker) return;

    if (!quotes || !quotes.length) {
      quotes = await fetchMarketClientFallback();
    }

    if (!quotes || !quotes.length) {
      const msg = escapeHtml(i18n.t("market.unavailable"));
      list.innerHTML = "<li><span>" + msg + "</span></li>";
      ticker.innerHTML = '<span class="ticker-item ticker-muted">—</span>';
      document.getElementById("market-ticker")?.classList.add("ticker-empty");
      return;
    }

    document.getElementById("market-ticker")?.classList.remove("ticker-empty");

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
    el.innerHTML = articles.map(function (a) { return renderCard(a); }).join("");
  }

  function renderLatest(articles) {
    const grid = document.getElementById("latest-grid");
    if (!grid) return;
    grid.innerHTML = (articles || []).slice(0, 8).map(function (a) {
      return renderCard(a);
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
    if (label) label.textContent = i18n.t("loading.label");

    const hero = document.querySelector(".hero-main");
    if (hero && hero.classList.contains("skeleton-block")) {
      hero.classList.remove("skeleton-block");
      hero.innerHTML = `
        <div class="hero-content empty-hero loading-hero">
          <span class="chip">${escapeHtml(i18n.t("loading.chip"))}</span>
          <h1>${escapeHtml(i18n.t("loading.news"))}</h1>
          <p>${escapeHtml(i18n.t("loading.wait"))}</p>
          <div class="loading-spinner" aria-hidden="true"></div>
        </div>`;
    }
  }

  function showEmptyState(message) {
    const label = document.getElementById("updated-label");
    if (label) label.textContent = message || i18n.t("empty.none");

    const hero = document.querySelector(".hero-main");
    if (hero) {
      hero.classList.remove("skeleton-block");
      hero.innerHTML = `
        <div class="hero-content empty-hero">
          <span class="chip">${escapeHtml(i18n.t("loading.chip"))}</span>
          <h1>${escapeHtml(i18n.t("loading.news"))}</h1>
          <p>${escapeHtml(i18n.t("empty.unavailable"))}</p>
        </div>`;
    }
  }

  async function loadNews() {
    showLoadingState();
    try {
      const lang = i18n.getLang();
      const res = await fetch("/api/news?lang=" + lang + "&t=" + Date.now(), { cache: "no-store" });
      const raw = await res.text();
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error("Servidor retornou resposta inválida. Aguarde o redeploy.");
      }
      if (!res.ok || !data.ok) throw new Error(data.error || "Falha ao carregar");

      if (!data.featured && (!data.latest || !data.latest.length)) {
        showEmptyState(i18n.t("empty.sync"));
        return;
      }

      renderHero(data.featured);
      renderLatest(data.latest);
      await renderMarket(data.market);
      showBreaking(data.featured);

      const cats = data.categories || {};
      renderGrid("grid-brasil", cats.brasil);
      renderGrid("grid-mercado", cats.mercado);
      renderGrid("grid-tecnologia", cats.tecnologia);
      renderGrid("grid-mundo", cats.mundo);

      const label = document.getElementById("updated-label");
      if (label) {
        const source = data.source === "database" ? "" : i18n.t("updated.realtime");
        label.textContent = data.updated_at
          ? i18n.t("updated.prefix") + data.updated_at + source
          : i18n.t("updated.fallback");
      }
    } catch (err) {
      console.error(err);
      showEmptyState(i18n.t("empty.unavailable"));
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
    button.textContent = i18n.t("subscribe.sending");

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
      feedback.textContent = err.message || i18n.t("subscribe.error");
      feedback.classList.add("error");
    } finally {
      button.disabled = false;
      button.textContent = i18n.t("newsletter.submit");
    }
  }

  function handleLangChange(lang) {
    i18n.setLang(lang);
    i18n.applyI18n();
    i18n.syncLangToggle();
    loadNews();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initLang();
    showLoadingState();
    loadNews();

    document.getElementById("theme-toggle")?.addEventListener("click", toggleTheme);
    document.getElementById("subscribe-form")?.addEventListener("submit", handleSubscribe);

    document.getElementById("menu-toggle")?.addEventListener("click", function () {
      document.querySelector(".main-nav")?.classList.toggle("open");
    });

    document.querySelectorAll("[data-lang-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        handleLangChange(btn.getAttribute("data-lang-btn"));
      });
    });

    setInterval(loadNews, 5 * 60 * 1000);
  });
})();
