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
    const params = new URLSearchParams(window.location.search);
    const urlLang = params.get("lang");
    if (urlLang) {
      i18n.setLang(urlLang);
    } else {
      i18n.setLang(i18n.getLang());
    }
    i18n.applyI18n();
    i18n.syncLangToggle();
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function getArticleUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("u") || params.get("url") || "";
  }

  function renderArticle(article) {
    const root = document.getElementById("article-root");
    if (!root) return;

    document.title = article.title + " — DevBrief News";

    root.classList.remove("loading");
    root.innerHTML = `
      <div class="article-hero-image">
        <img src="${escapeHtml(article.image)}" alt="" loading="eager"
          onerror="this.src='/assets/logo.png'">
      </div>
      <div class="article-meta">
        <span class="category-tag">${escapeHtml(i18n.categoryLabel(article.category) || article.category_label || article.category)}</span>
        <span>${escapeHtml(article.source)} · ${escapeHtml(article.published)}</span>
      </div>
      <h1>${escapeHtml(article.title)}</h1>
      <div class="article-body">
        <p class="article-lead">${escapeHtml(article.summary || "")}</p>
        ${article.body && article.body.length > (article.summary || "").length
          ? "<p>" + escapeHtml(article.body).replace(/\n/g, "</p><p>") + "</p>"
          : ""}
      </div>
      <div class="article-actions">
        <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer" class="source-button">
          ${escapeHtml(i18n.t("article.source"))} (${escapeHtml(article.source)}) →
        </a>
      </div>
      <p class="article-disclaimer">
        ${escapeHtml(i18n.t("article.disclaimer"))}
      </p>`;
  }

  function renderError(message) {
    const root = document.getElementById("article-root");
    if (!root) return;
    root.classList.remove("loading");
    root.innerHTML = `
      <div class="article-error">
        <h1>${escapeHtml(i18n.t("article.error.title"))}</h1>
        <p>${escapeHtml(message)}</p>
        <a href="/" class="read-more">${escapeHtml(i18n.t("article.back"))}</a>
      </div>`;
  }

  async function loadArticle() {
    const articleUrl = getArticleUrl();
    if (!articleUrl) {
      renderError(i18n.t("article.error.invalid"));
      return;
    }

    try {
      const lang = i18n.getLang();
      const res = await fetch(
        "/api/article?u=" + encodeURIComponent(articleUrl) + "&lang=" + lang,
        { cache: "no-store" }
      );
      const data = await res.json();
      if (!res.ok || !data.ok || !data.article) {
        throw new Error(data.error || "Notícia não encontrada.");
      }
      renderArticle(data.article);
    } catch (err) {
      renderError(err.message || i18n.t("article.error.title"));
    }
  }

  function handleLangChange(lang) {
    i18n.setLang(lang);
    i18n.applyI18n();
    i18n.syncLangToggle();
    loadArticle();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initLang();
    loadArticle();
    document.getElementById("theme-toggle")?.addEventListener("click", toggleTheme);
    document.querySelectorAll("[data-lang-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        handleLangChange(btn.getAttribute("data-lang-btn"));
      });
    });
  });
})();
