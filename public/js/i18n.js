(function (global) {
  "use strict";

  var LANG_KEY = "devbrief-lang";

  var STRINGS = {
    pt: {
      "brand.tagline": "Inteligência diária para quem decide",
      "nav.brasil": "Brasil",
      "nav.mundo": "Mundo",
      "nav.tecnologia": "Tecnologia",
      "nav.mercado": "Mercado",
      "nav.newsletter": "Newsletter",
      "ticker.label": "Mercado",
      "breaking.badge": "URGENTE",
      "breaking.default": "Monitorando notícias de alto impacto...",
      "hero.chip": "Destaque",
      "market.title": "📈 Mercado agora",
      "newsletter.title": "📬 Receba no e-mail",
      "newsletter.desc": "Briefing diário às 07h, alertas urgentes e resumo de mercado — grátis.",
      "newsletter.placeholder": "seu@email.com",
      "newsletter.submit": "Assinar grátis",
      "newsletter.perk1": "✅ Resumo completo todo dia",
      "newsletter.perk2": "✅ Alertas de breaking news",
      "newsletter.perk3": "✅ Cotações e mercado financeiro",
      "latest.title": "Últimas notícias",
      "section.brasil": "🇧🇷 Brasil",
      "section.brasil.link": "Receber resumo diário →",
      "section.mercado": "📈 Mercado & Economia",
      "section.mercado.link": "Alertas de mercado →",
      "section.tech": "💻 Tecnologia",
      "section.tech.link": "Briefing tech →",
      "section.mundo": "🌍 Mundo",
      "section.mundo.link": "Assinar newsletter →",
      "cta.title": "Seu G1 inteligente, no e-mail e no Telegram",
      "cta.desc": "O DevBrief News cura centenas de fontes, resume com IA e entrega o que importa — com foco em mercado, tech e empreendedorismo.",
      "cta.button": "Quero receber",
      "footer.desc": "DevBrief News — curadoria automatizada de notícias com IA. Briefing diário às 07:00 (Brasília).",
      "footer.sections": "Seções",
      "footer.newsletter": "Newsletter",
      "footer.subscribe": "Assinar grátis",
      "footer.briefing": "Briefing diário 07h",
      "footer.alerts": "Alertas urgentes",
      "footer.sources": "Fontes",
      "footer.updated": "Atualizado em tempo real via RSS",
      "read.more": "Ver mais →",
      "loading.news": "Buscando as últimas notícias...",
      "loading.wait": "Aguarde, estamos coletando RSS em tempo real.",
      "loading.chip": "Atualizando",
      "loading.label": "Buscando notícias agora...",
      "empty.sync": "Sincronizando notícias pela primeira vez...",
      "empty.none": "Nenhuma notícia disponível no momento.",
      "empty.unavailable": "Notícias temporariamente indisponíveis. Recarregue em alguns segundos.",
      "updated.prefix": "Atualizado: ",
      "updated.fallback": "Notícias atualizadas",
      "updated.realtime": " (tempo real)",
      "market.unavailable": "Cotações indisponíveis no momento.",
      "market.loading": "Carregando cotações...",
      "subscribe.sending": "Enviando...",
      "subscribe.error": "Não foi possível inscrever. Tente novamente.",
      "article.back": "← Voltar ao portal",
      "article.loading": "Carregando notícia...",
      "article.source": "Ver na fonte original",
      "article.disclaimer": "Resumo curado pelo DevBrief News a partir de fontes públicas. Assine a newsletter para receber o briefing completo todo dia às 07h.",
      "article.error.title": "Notícia indisponível",
      "article.error.invalid": "Link inválido. Volte ao portal e escolha uma notícia.",
      "category.brasil": "Brasil",
      "category.mundo": "Mundo",
      "category.tecnologia": "Tecnologia",
      "category.mercado": "Mercado",
    },
    en: {
      "brand.tagline": "Daily intelligence for decision makers",
      "nav.brasil": "Brazil",
      "nav.mundo": "World",
      "nav.tecnologia": "Technology",
      "nav.mercado": "Markets",
      "nav.newsletter": "Newsletter",
      "ticker.label": "Markets",
      "breaking.badge": "BREAKING",
      "breaking.default": "Monitoring high-impact news...",
      "hero.chip": "Featured",
      "market.title": "📈 Markets now",
      "newsletter.title": "📬 Get it by email",
      "newsletter.desc": "Daily briefing at 7 AM, breaking alerts and market summary — free.",
      "newsletter.placeholder": "you@email.com",
      "newsletter.submit": "Subscribe free",
      "newsletter.perk1": "✅ Full daily summary",
      "newsletter.perk2": "✅ Breaking news alerts",
      "newsletter.perk3": "✅ Quotes and financial markets",
      "latest.title": "Latest news",
      "section.brasil": "🇧🇷 Brazil",
      "section.brasil.link": "Get daily summary →",
      "section.mercado": "📈 Markets & Economy",
      "section.mercado.link": "Market alerts →",
      "section.tech": "💻 Technology",
      "section.tech.link": "Tech briefing →",
      "section.mundo": "🌍 World",
      "section.mundo.link": "Subscribe to newsletter →",
      "cta.title": "Your smart news digest, by email and Telegram",
      "cta.desc": "DevBrief News curates hundreds of sources, summarizes with AI and delivers what matters — focused on markets, tech and entrepreneurship.",
      "cta.button": "I want to receive",
      "footer.desc": "DevBrief News — AI-powered news curation. Daily briefing at 7:00 AM (Brasília).",
      "footer.sections": "Sections",
      "footer.newsletter": "Newsletter",
      "footer.subscribe": "Subscribe free",
      "footer.briefing": "Daily briefing 7 AM",
      "footer.alerts": "Breaking alerts",
      "footer.sources": "Sources",
      "footer.updated": "Updated in real time via RSS",
      "read.more": "Read more →",
      "loading.news": "Fetching the latest news...",
      "loading.wait": "Please wait, we're collecting RSS feeds in real time.",
      "loading.chip": "Updating",
      "loading.label": "Fetching news now...",
      "empty.sync": "Syncing news for the first time...",
      "empty.none": "No news available at the moment.",
      "empty.unavailable": "News temporarily unavailable. Reload in a few seconds.",
      "updated.prefix": "Updated: ",
      "updated.fallback": "News updated",
      "updated.realtime": " (real time)",
      "market.unavailable": "Quotes unavailable at the moment.",
      "market.loading": "Loading quotes...",
      "subscribe.sending": "Sending...",
      "subscribe.error": "Could not subscribe. Please try again.",
      "article.back": "← Back to portal",
      "article.loading": "Loading article...",
      "article.source": "View original source",
      "article.disclaimer": "Summary curated by DevBrief News from public sources. Subscribe to the newsletter for the full daily briefing at 7 AM.",
      "article.error.title": "Article unavailable",
      "article.error.invalid": "Invalid link. Go back to the portal and pick a story.",
      "category.brasil": "Brazil",
      "category.mundo": "World",
      "category.tecnologia": "Technology",
      "category.mercado": "Markets",
    },
  };

  function getLang() {
    var saved = localStorage.getItem(LANG_KEY);
    return saved === "en" ? "en" : "pt";
  }

  function setLang(lang) {
    var next = lang === "en" ? "en" : "pt";
    localStorage.setItem(LANG_KEY, next);
    document.documentElement.lang = next === "en" ? "en-US" : "pt-BR";
    document.documentElement.setAttribute("data-lang", next);
    return next;
  }

  function t(key) {
    var lang = getLang();
    return (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.pt[key] || key;
  }

  function applyI18n(root) {
    var scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      var attr = el.getAttribute("data-i18n-attr");
      var value = t(key);
      if (attr) {
        el.setAttribute(attr, value);
      } else {
        el.textContent = value;
      }
    });
  }

  function categoryLabel(category) {
    var map = {
      brasil: t("category.brasil"),
      mundo: t("category.mundo"),
      tecnologia: t("category.tecnologia"),
      mercado: t("category.mercado"),
    };
    return map[category] || category;
  }

  function syncLangToggle() {
    var current = getLang();
    document.querySelectorAll("[data-lang-btn]").forEach(function (btn) {
      var active = btn.getAttribute("data-lang-btn") === current;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  global.DevBriefI18n = {
    LANG_KEY: LANG_KEY,
    getLang: getLang,
    setLang: setLang,
    t: t,
    applyI18n: applyI18n,
    categoryLabel: categoryLabel,
    syncLangToggle: syncLangToggle,
  };
})(window);
