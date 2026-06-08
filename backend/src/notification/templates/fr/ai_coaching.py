"""
Templates FR pour les notifications de coaching IA (Phase 2.6).

3 canaux : push / SMS / email. Tous incluent un disclaimer obligatoire
RGPD/santé : "Suggestion informative — ne remplace pas un avis médical."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoachingContext:
    first_name: str
    coaching_text: str       # texte généré par Claude
    explanation: str = ""    # 1 phrase explicative ("vous avez moins dormi ces 3 derniers jours")


DISCLAIMER_FR = (
    "Ceci est une suggestion informative et bienveillante. "
    "Elle ne remplace pas l'avis d'un professionnel de santé."
)


def push_title(_ctx: CoachingContext) -> str:
    return "Mood-IoT : un conseil pour vous"


def push_body(ctx: CoachingContext) -> str:
    # Push notifs sont coupées à ~120 chars sur Android, on garde court.
    text = ctx.coaching_text.strip()
    if len(text) > 110:
        text = text[:107].rstrip() + "…"
    return text


def email_subject(_ctx: CoachingContext) -> str:
    return "Mood-IoT — un conseil personnalisé pour votre journée"


def email_html(ctx: CoachingContext) -> str:
    """HTML simple compatible Gmail/Outlook/Hotmail."""
    explanation_block = (
        f'<p style="color:#666;font-size:13px;font-style:italic;">'
        f"{ctx.explanation}</p>"
        if ctx.explanation
        else ""
    )
    return f"""
    <div style="font-family:-apple-system,sans-serif;max-width:520px;
                margin:auto;padding:24px;background:#fff;border-radius:12px;">
      <div style="text-align:center;margin-bottom:24px">
        <span style="font-size:32px">💙</span>
        <h2 style="color:#0288d1;margin:8px 0 0">Mood-IoT</h2>
      </div>
      <p>Bonjour {ctx.first_name},</p>
      {explanation_block}
      <div style="background:#f4f6fb;padding:20px;border-radius:12px;
                  border-left:4px solid #0288d1;margin:16px 0;">
        <p style="margin:0;font-size:15px;line-height:1.55;color:#222;">
          {ctx.coaching_text}
        </p>
      </div>
      <p style="font-size:12px;color:#888;border-top:1px solid #eee;
                padding-top:16px;margin-top:24px;">
        ⚠️ <strong>{DISCLAIMER_FR}</strong>
      </p>
      <p style="font-size:11px;color:#aaa;text-align:center;margin-top:16px;">
        Mood-IoT — Suivi du bien-être<br/>
        Vous pouvez désactiver ces messages depuis l'application
        (Réglages → Notifications).
      </p>
    </div>
    """
