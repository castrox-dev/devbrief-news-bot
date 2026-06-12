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
        <span class="category-tag">${escapeHtml(article.category_label || article.category)}</span>
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
          Ver na fonte original (${escapeHtml(article.source)}) →
        </a>
      </div>
      <p class="article-disclaimer">
        Resumo curado pelo DevBrief News a partir de fontes públicas.
        Assine a newsletter para receber o briefing completo todo dia às 07h.
      </p>`;
  }

  function renderError(message) {
    const root = document.getElementById("article-root");
    if (!root) return;
    root.classList.remove("loading");
    root.innerHTML = `
      <div class="article-error">
        <h1>Notícia indisponível</h1>
        <p>${escapeHtml(message)}</p>
        <a href="/" class="read-more">← Voltar ao portal</a>
      </div>`;
  }

  async function loadArticle() {
    const articleUrl = getArticleUrl();
    if (!articleUrl) {
      renderError("Link inválido. Volte ao portal e escolha uma notícia.");
      return;
    }

    try {
      const res = await fetch("/api/article?u=" + encodeURIComponent(articleUrl), { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || !data.ok || !data.article) {
        throw new Error(data.error || "Notícia não encontrada.");
      }
      renderArticle(data.article);
    } catch (err) {
      renderError(err.message || "Erro ao carregar a notícia.");
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
      feedback.textContent = err.message || "Não foi possível inscrever.";
      feedback.classList.add("error");
    } finally {
      button.disabled = false;
      button.textContent = "Assinar grátis";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    loadArticle();
    document.getElementById("theme-toggle")?.addEventListener("click", toggleTheme);
    document.getElementById("subscribe-form")?.addEventListener("submit", handleSubscribe);
  });
})();
