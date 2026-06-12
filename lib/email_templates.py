"""Templates HTML de e-mail alinhados à identidade DevBrief News."""

from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

BRAND_NAME: Final[str] = "DevBrief News"
SITE_URL: Final[str] = "https://devbrief-news.vercel.app"
LOGO_URL: Final[str] = "https://devbrief-news.vercel.app/assets/logo.png"

COLOR_BLACK: Final[str] = "#0a0a0a"
COLOR_CARD: Final[str] = "#141414"
COLOR_BORDER: Final[str] = "#2a2a2a"
COLOR_ORANGE: Final[str] = "#FFB020"
COLOR_ORANGE_DARK: Final[str] = "#E69500"
COLOR_BLUE: Final[str] = "#4A90E2"
COLOR_RED: Final[str] = "#E53935"
COLOR_TEXT: Final[str] = "#f0f0f0"
COLOR_MUTED: Final[str] = "#9aa3b5"
COLOR_WHITE: Final[str] = "#ffffff"


def _logo_url() -> str:
    return os.getenv("EMAIL_LOGO_URL", LOGO_URL).strip() or LOGO_URL


def _now_label() -> str:
    tz = ZoneInfo(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    now = datetime.now(tz)
    return now.strftime("%d/%m/%Y às %H:%M")


def _base_layout(*, preheader: str, body_html: str) -> str:
    logo = html.escape(_logo_url())
    pre = html.escape(preheader)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark">
  <title>{html.escape(BRAND_NAME)}</title>
</head>
<body style="margin:0;padding:0;background:{COLOR_BLACK};font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{pre}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{COLOR_BLACK};">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;">
          <tr>
            <td style="background:{COLOR_CARD};border:1px solid {COLOR_BORDER};border-radius:16px 16px 0 0;padding:28px 32px 20px;text-align:center;">
              <img src="{logo}" alt="{html.escape(BRAND_NAME)}" width="220" style="max-width:220px;height:auto;margin:0 auto 16px;display:block;">
              <div style="height:3px;background:linear-gradient(90deg,{COLOR_ORANGE},{COLOR_BLUE},{COLOR_ORANGE});border-radius:999px;"></div>
            </td>
          </tr>
          <tr>
            <td style="background:{COLOR_CARD};border-left:1px solid {COLOR_BORDER};border-right:1px solid {COLOR_BORDER};padding:0 32px 28px;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="background:{COLOR_BLACK};border:1px solid {COLOR_BORDER};border-top:none;border-radius:0 0 16px 16px;padding:20px 32px;text-align:center;">
              <p style="margin:0 0 8px;font-size:13px;color:{COLOR_MUTED};">
                <strong style="color:{COLOR_WHITE};">DevBrief</strong>
                <span style="color:{COLOR_ORANGE};">News</span> · Inteligência diária para quem decide
              </p>
              <p style="margin:0;font-size:12px;color:{COLOR_MUTED};">
                <a href="{SITE_URL}" style="color:{COLOR_ORANGE};text-decoration:none;">devbrief-news.vercel.app</a>
                · RM Sys
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _cta_button(label: str, href: str) -> str:
    safe_label = html.escape(label)
    safe_href = html.escape(href)
    return f"""
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin:28px auto 8px;">
        <tr>
          <td style="border-radius:999px;background:linear-gradient(135deg,{COLOR_ORANGE},{COLOR_ORANGE_DARK});">
            <a href="{safe_href}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:700;color:{COLOR_BLACK};text-decoration:none;">
              {safe_label}
            </a>
          </td>
        </tr>
      </table>"""


def render_welcome_email(subscriber_email: str) -> tuple[str, str]:
    """Retorna (subject, html) do e-mail de boas-vindas."""
    email_safe = html.escape(subscriber_email)
    body = f"""
      <h1 style="margin:24px 0 12px;font-size:28px;line-height:1.25;color:{COLOR_WHITE};font-weight:800;">
        Bem-vindo ao <span style="color:{COLOR_ORANGE};">DevBrief News</span>
      </h1>
      <p style="margin:0 0 20px;font-size:16px;line-height:1.7;color:{COLOR_MUTED};">
        Obrigado por assinar, <strong style="color:{COLOR_TEXT};">{email_safe}</strong>.
        A partir de agora você recebe curadoria inteligente de notícias — com foco em mercado, tech e Brasil.
      </p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{COLOR_BLACK};border:1px solid {COLOR_BORDER};border-radius:12px;">
        <tr>
          <td style="padding:20px 22px;">
            <p style="margin:0 0 14px;font-size:13px;font-weight:700;color:{COLOR_ORANGE};text-transform:uppercase;letter-spacing:0.06em;">
              O que você recebe
            </p>
            <p style="margin:0 0 10px;font-size:15px;color:{COLOR_TEXT};">📬 Briefing diário às <strong>07:00</strong> (Brasília)</p>
            <p style="margin:0 0 10px;font-size:15px;color:{COLOR_TEXT};">📈 Cobertura de mercado e economia em tempo real</p>
            <p style="margin:0 0 10px;font-size:15px;color:{COLOR_TEXT};">💻 Destaques de tecnologia e inovação</p>
            <p style="margin:0;font-size:15px;color:{COLOR_TEXT};">🤖 Resumos com IA — só o que importa</p>
          </td>
        </tr>
      </table>
      {_cta_button("Acessar o portal →", SITE_URL)}
      <p style="margin:20px 0 0;font-size:13px;line-height:1.6;color:{COLOR_MUTED};text-align:center;">
        Enquanto isso, explore as últimas notícias no nosso portal.
      </p>"""
    subject = "Bem-vindo ao DevBrief News — sua inteligência diária"
    return subject, _base_layout(preheader="Você entrou na newsletter DevBrief News.", body_html=body)


def render_team_notification_email(subscriber_email: str) -> tuple[str, str]:
    """Retorna (subject, html) do aviso interno de nova inscrição."""
    email_safe = html.escape(subscriber_email)
    when = html.escape(_now_label())
    body = f"""
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
        <tr>
          <td style="background:linear-gradient(135deg,{COLOR_ORANGE}22,{COLOR_BLUE}18);border:1px solid {COLOR_BORDER};border-radius:12px;padding:18px 20px;">
            <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{COLOR_ORANGE};text-transform:uppercase;letter-spacing:0.08em;">
              Nova inscrição
            </p>
            <h1 style="margin:0 0 8px;font-size:24px;color:{COLOR_WHITE};font-weight:800;">
              Mais um leitor no DevBrief 🎉
            </h1>
            <p style="margin:0;font-size:14px;color:{COLOR_MUTED};">Registrado em {when}</p>
          </td>
        </tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:20px;background:{COLOR_BLACK};border:1px solid {COLOR_BORDER};border-radius:12px;">
        <tr>
          <td style="padding:22px;">
            <p style="margin:0 0 8px;font-size:13px;color:{COLOR_MUTED};text-transform:uppercase;letter-spacing:0.05em;">E-mail do assinante</p>
            <p style="margin:0;font-size:22px;font-weight:700;color:{COLOR_ORANGE};word-break:break-all;">{email_safe}</p>
          </td>
        </tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:16px;">
        <tr>
          <td width="50%" style="padding-right:8px;">
            <div style="background:{COLOR_BLACK};border:1px solid {COLOR_BORDER};border-radius:10px;padding:16px;text-align:center;">
              <p style="margin:0 0 4px;font-size:11px;color:{COLOR_MUTED};text-transform:uppercase;">Status</p>
              <p style="margin:0;font-size:15px;font-weight:700;color:#6ee7a0;">Ativo</p>
            </div>
          </td>
          <td width="50%" style="padding-left:8px;">
            <div style="background:{COLOR_BLACK};border:1px solid {COLOR_BORDER};border-radius:10px;padding:16px;text-align:center;">
              <p style="margin:0 0 4px;font-size:11px;color:{COLOR_MUTED};text-transform:uppercase;">Canal</p>
              <p style="margin:0;font-size:15px;font-weight:700;color:{COLOR_BLUE};">Newsletter</p>
            </div>
          </td>
        </tr>
      </table>
      {_cta_button("Abrir portal DevBrief →", SITE_URL)}
      <p style="margin:16px 0 0;font-size:12px;color:{COLOR_MUTED};text-align:center;">
        Assinante salvo no banco PostgreSQL (Neon).
      </p>"""
    subject = f"Nova inscrição DevBrief — {subscriber_email}"
    return subject, _base_layout(preheader=f"Novo assinante: {subscriber_email}", body_html=body)
