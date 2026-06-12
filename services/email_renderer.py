"""Renderização do resumo de notícias em HTML compatível com clientes de e-mail."""

from __future__ import annotations

import base64
import html
import mimetypes
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Final

BRAND_NAME: Final[str] = "DevBrief News"
LOGO_CID: Final[str] = "devbrief-logo"
ACCENT_GOLD: Final[str] = "#FFC107"
ACCENT_RED: Final[str] = "#E91E63"
ACCENT_BLUE: Final[str] = "#4A90E2"


def _get_assets_dir() -> Path:
    """Retorna o diretório de assets (compatível com PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "assets"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent.parent / "assets"


def _get_template_path() -> Path:
    """Retorna o caminho do template HTML (compatível com PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "templates" / "email_template.html"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent.parent / "templates" / "email_template.html"


def get_logo_bytes() -> bytes | None:
    """Retorna bytes da logo local ou None se não existir."""
    logo_path = _get_assets_dir() / "logo.png"
    if logo_path.exists():
        return logo_path.read_bytes()
    return None


def _get_logo_data_uri() -> str:
    """
    Carrega a logo e retorna como data URI para embed no e-mail.

    Returns:
        String data:image/png;base64,... ou string vazia se não encontrada.
    """
    logo_path = _get_assets_dir() / "logo.png"
    if not logo_path.exists():
        return ""

    mime_type = mimetypes.guess_type(logo_path.name)[0] or "image/png"
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


SECTION_ICONS: Final[dict[str, str]] = {
    "resumo executivo": "📋",
    "brasil": "🇧🇷",
    "mundo": "🌍",
    "tecnologia": "💻",
    "mercado": "📈",
    "investimentos": "📈",
    "desenvolvimento": "⚙️",
    "empreendedores": "🚀",
    "curiosidades": "✨",
    "atenção": "📌",
    "bordão": "💬",
    "bordao": "💬",
    "default": "📰",
}


def _detect_section_icon(title: str) -> str:
    """Retorna emoji de acordo com o título da seção."""
    lowered = title.lower()
    for keyword, icon in SECTION_ICONS.items():
        if keyword in lowered:
            return icon
    return SECTION_ICONS["default"]


LINK_STYLE: Final[str] = (
    "color:#FFC107;text-decoration:underline;font-weight:600;"
)
LINK_BUTTON_STYLE: Final[str] = (
    "display:inline-block;margin-top:8px;padding:8px 16px;"
    "background-color:#1a1a1a;border:1px solid #FFC107;border-radius:6px;"
    "font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:700;"
    "color:#FFC107;text-decoration:none;"
)


def _format_inline(text: str) -> str:
    """Aplica formatação inline: negrito, itálico e links markdown/URL."""
    placeholders: dict[str, str] = {}
    counter = 0

    def _store_anchor(match: re.Match[str]) -> str:
        nonlocal counter
        label, url = match.group(1), match.group(2)
        key = f"@@LINK{counter}@@"
        counter += 1
        safe_url = html.escape(url, quote=True)
        safe_label = html.escape(label)
        placeholders[key] = (
            f'<a href="{safe_url}" target="_blank" style="{LINK_STYLE}">{safe_label}</a>'
        )
        return key

    processed = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", _store_anchor, text)
    escaped = html.escape(processed)

    for key, anchor in placeholders.items():
        escaped = escaped.replace(html.escape(key), anchor)

    escaped = re.sub(
        r"(https?://[^\s<&]+)",
        rf'<a href="\1" target="_blank" style="{LINK_STYLE}">\1</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong style='color:#ffffff;'>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    return escaped


def _extract_article_url(text: str) -> str | None:
    """Extrai primeira URL markdown ou plain do texto."""
    md_match = re.search(r"\[([^\]]+)\]\((https?://[^\)]+)\)", text)
    if md_match:
        return md_match.group(2)
    url_match = re.search(r"(https?://[^\s\)]+)", text)
    return url_match.group(1) if url_match else None


def _is_main_section_header(line: str) -> bool:
    """Identifica cabeçalhos principais (1. Resumo Executivo, 2. Brasil...)."""
    stripped = line.strip()
    if re.match(r"^\d+[\.\)]\s+", stripped):
        return True
    if stripped.startswith("📰 DevBrief"):
        return True
    return False


def _is_subsection_header(line: str) -> bool:
    """Identifica subseções temáticas (🇧🇷 IA, 🤖 OpenAI, Oportunidades...)."""
    stripped = line.strip()
    if not stripped or stripped.startswith(("* ", "- ", "• ", "✅", "⚠️")):
        return False
    if re.match(r"^[\U0001F300-\U0001FAFF\U00002700-\U000027BF]", stripped):
        return True
    if stripped in (
        "Oportunidades", "Alertas",
        "Oportunidades:", "Alertas:",
        "Principais tendências observadas:",
    ):
        return True
    if re.match(r"^(🔥|📊|💡|📈|👨‍💻|🔒|💬)\s", stripped):
        return True
    if stripped.endswith(":") and len(stripped) < 60 and not stripped.startswith("http"):
        return True
    return False


def _is_short_line(line: str) -> bool:
    """Linhas curtas de fato (tendências, prioridades) sem marcador."""
    if len(line) > 110 or line.count(".") > 2:
        return False
    if line.startswith("http") or "](http" in line:
        return False
    return True


def _clean_header(line: str) -> str:
    """Remove marcadores de cabeçalho."""
    stripped = line.strip()
    stripped = re.sub(r"^#{1,3}\s+", "", stripped)
    stripped = re.sub(r"^\d+[\.\)]\s+", "", stripped)
    return stripped.rstrip(":").strip()


def parse_summary_to_sections(summary: str) -> list[dict[str, str | list[str]]]:
    """
    Converte o texto do resumo em seções estruturadas.

    Args:
        summary: Texto gerado pela IA.

    Returns:
        Lista de seções com título e itens de conteúdo.
    """
    sections: list[dict[str, str | list[str]]] = []
    current_title = "Resumo do Dia"
    current_items: list[str] = []

    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("📰 DevBrief"):
            continue

        if _is_main_section_header(line):
            if current_items:
                sections.append({"title": current_title, "items": current_items})
            current_title = _clean_header(line)
            current_items = []
            continue

        if line.startswith(("* ", "- ", "• ")):
            current_items.append(f"bullet:{line[2:].strip()}")
        elif _is_subsection_header(line):
            current_items.append(f"sub:{line}")
        elif line.startswith(("✅", "⚠️", "🔥", "📊", "💡", "💬")):
            current_items.append(f"special:{line}")
        elif _is_short_line(line):
            current_items.append(f"line:{line}")
        else:
            current_items.append(f"para:{line}")

    if current_items:
        sections.append({"title": current_title, "items": current_items})

    if not sections:
        sections.append({"title": "Resumo do Dia", "items": [summary]})

    return sections


def _render_news_item(raw_item: str) -> str:
    """Renderiza parágrafo, subseção, bullet ou item especial com dark mode."""
    item_type, _, content = raw_item.partition(":")
    if not content:
        content = raw_item
        item_type = "para"

    formatted = _format_inline(content)
    article_url = _extract_article_url(content)

    if item_type == "sub":
        return f"""
            <tr>
              <td style="padding:18px 0 6px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#FFC107;line-height:22px;">
                {_format_inline(content)}
              </td>
            </tr>"""

    if item_type == "special":
        accent = ACCENT_GOLD
        if content.startswith("⚠️"):
            accent = ACCENT_RED
        elif content.startswith("✅"):
            accent = "#4CAF50"
        elif content.startswith("🔥"):
            accent = "#FF5722"
        elif content.startswith("💬"):
            accent = ACCENT_GOLD
        return f"""
            <tr>
              <td style="padding:6px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#d4d4d4;line-height:22px;border-left:3px solid {accent};padding-left:12px;">
                {formatted}
              </td>
            </tr>"""

    if item_type in ("bullet", "line"):
        return f"""
            <tr>
              <td style="padding:5px 0 5px 14px;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#d4d4d4;line-height:22px;">
                <span style="color:{ACCENT_GOLD};margin-right:6px;">•</span>{formatted}
              </td>
            </tr>"""

    link_suffix = ""
    if article_url and "[Fonte]" not in content:
        safe_url = html.escape(article_url, quote=True)
        link_suffix = (
            f'<br/><a href="{safe_url}" target="_blank" style="{LINK_STYLE}font-size:12px;">↗ Fonte</a>'
        )

    return f"""
            <tr>
              <td style="padding:6px 0 14px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#d4d4d4;line-height:24px;">
                {formatted}{link_suffix}
              </td>
            </tr>"""


def _render_bordao_card(title: str, items: list[str]) -> str:
    """Renderiza o bordão do dia em destaque."""
    raw = " ".join(
        (item.partition(":")[2] or item) for item in items
    ).strip()
    quote = raw.strip('"').strip("'").strip()
    if quote.lower().startswith("bordão") or quote.lower().startswith("bordao"):
        quote = ""
    quote_html = _format_inline(quote) if quote else "Fique por dentro. O futuro não espera."

    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:24px;">
      <tr>
        <td style="background-color:#1a1a1a;border:2px solid {ACCENT_GOLD};border-radius:12px;padding:24px 28px;text-align:center;">
          <p style="margin:0 0 10px;font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;color:#FFC107;text-transform:uppercase;letter-spacing:1px;">
            💬 Bordão do Dia
          </p>
          <p style="margin:0;font-family:Georgia,serif;font-size:17px;font-style:italic;color:#ffffff;line-height:26px;">
            "{quote_html}"
          </p>
        </td>
      </tr>
    </table>"""


def _render_section_card(title: str, items: list[str]) -> str:
    """Renderiza um card de seção com layout em tabela."""
    if "bordão" in title.lower() or "bordao" in title.lower():
        return _render_bordao_card(title, items)

    icon = _detect_section_icon(title)
    items_html = "".join(_render_news_item(item) for item in items)

    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:28px;">
      <tr>
        <td style="background-color:#111111;border-radius:12px;border:1px solid #2a2a2a;overflow:hidden;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="background-color:#1a1a1a;padding:14px 20px;border-bottom:2px solid {ACCENT_GOLD};">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td width="36" style="font-size:22px;line-height:22px;vertical-align:middle;">{icon}</td>
                    <td style="font-family:Arial,Helvetica,sans-serif;font-size:17px;font-weight:700;color:#ffffff;line-height:22px;vertical-align:middle;">
                      {html.escape(title)}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 20px 20px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  {items_html}
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>"""


def _is_logo_url_reachable(logo_url: str) -> bool:
    """Verifica se a URL da logo está acessível."""
    try:
        import requests

        response = requests.head(logo_url.strip(), timeout=8, allow_redirects=True)
        return response.status_code < 400
    except Exception:
        return False


def _logo_img_tag(src: str) -> str:
    """Gera tag img da logo com estilos inline para e-mail."""
    return (
        f'<img src="{src}" alt="{BRAND_NAME}" width="280" '
        f'style="display:block;margin:0 auto;max-width:280px;width:280px;height:auto;border:0;" />'
    )


def _build_logo_html(logo_url: str = "", use_cid: bool = False, for_preview: bool = False) -> str:
    """
    Monta tag da logo.

    Prioridade no envio real: CID inline > URL pública > texto.
    Preview local: base64 embutido (funciona no navegador).
    """
    if use_cid and get_logo_bytes():
        return _logo_img_tag(f"cid:{LOGO_CID}")

    if logo_url.strip() and _is_logo_url_reachable(logo_url):
        safe_url = html.escape(logo_url.strip(), quote=True)
        return _logo_img_tag(safe_url)

    if for_preview:
        logo_uri = _get_logo_data_uri()
        if logo_uri:
            return _logo_img_tag(logo_uri)

    if get_logo_bytes():
        return _logo_img_tag(f"cid:{LOGO_CID}")

    return (
        f'<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:28px;'
        f'font-weight:800;color:#ffffff;line-height:34px;">Dev<span style="color:{ACCENT_GOLD};">Brief</span> News</p>'
    )


def render_email_html(
    summary: str,
    reference_date: datetime | None = None,
    logo_url: str = "",
    use_inline_logo: bool = False,
    for_preview: bool = False,
) -> str:
    """
    Gera o HTML completo do e-mail a partir do resumo.

    Args:
        summary: Texto do resumo de notícias.
        reference_date: Data de referência exibida no cabeçalho.
        logo_url: URL pública da logo (fallback).
        use_inline_logo: Usa cid: para anexo inline no Resend (Gmail/Outlook).
        for_preview: Usa base64 para preview no navegador.

    Returns:
        Documento HTML pronto para envio.
    """
    reference_date = reference_date or datetime.now()
    date_label = reference_date.strftime("%d de %B de %Y").replace(
        "January", "Janeiro"
    ).replace("February", "Fevereiro").replace("March", "Março").replace(
        "April", "Abril"
    ).replace("May", "Maio").replace("June", "Junho").replace(
        "July", "Julho"
    ).replace("August", "Agosto").replace("September", "Setembro").replace(
        "October", "Outubro"
    ).replace("November", "Novembro").replace("December", "Dezembro")
    weekday = reference_date.strftime("%A")
    weekdays = {
        "Monday": "Segunda-feira",
        "Tuesday": "Terça-feira",
        "Wednesday": "Quarta-feira",
        "Thursday": "Quinta-feira",
        "Friday": "Sexta-feira",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }
    weekday_label = weekdays.get(weekday, weekday)

    sections = parse_summary_to_sections(summary)
    sections_html = "".join(
        _render_section_card(str(section["title"]), list(section["items"]))
        for section in sections
    )

    template = _get_template_path().read_text(encoding="utf-8")
    logo_html = _build_logo_html(logo_url, use_cid=use_inline_logo, for_preview=for_preview)

    return (
        template.replace("{{PREHEADER}}", html.escape(f"DevBrief News — briefing de {date_label}"))
        .replace("{{BRAND_NAME}}", BRAND_NAME)
        .replace("{{LOGO_HTML}}", logo_html)
        .replace("{{DATE_LABEL}}", html.escape(date_label))
        .replace("{{WEEKDAY_LABEL}}", html.escape(weekday_label))
        .replace("{{SECTIONS_HTML}}", sections_html)
        .replace("{{YEAR}}", str(reference_date.year))
    )
