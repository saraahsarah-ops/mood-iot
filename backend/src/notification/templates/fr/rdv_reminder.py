"""
Templates FR pour les rappels de rendez-vous.

3 timings (J-1, H-1, H0) × 3 canaux (push, SMS, email) = 9 messages.
Variables substituées : {first_name}, {doctor_name}, {date_fr}, {time_fr},
{speciality}, {jitsi_url}.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReminderKind = Literal["24h", "1h", "now"]


@dataclass(frozen=True)
class RdvContext:
    """Context d'un rappel de RDV pour le rendu des templates."""

    first_name: str
    doctor_name: str
    scheduled_at: datetime
    speciality: str
    jitsi_url: str
    reason: str = ""

    @property
    def date_fr(self) -> str:
        """Date au format FR : 'jeudi 15 mai 2026'."""
        # Mois en FR pour rester indépendant de la locale système du conteneur
        months_fr = [
            "", "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        ]
        days_fr = [
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"
        ]
        d = self.scheduled_at
        return f"{days_fr[d.weekday()]} {d.day} {months_fr[d.month]} {d.year}"

    @property
    def time_fr(self) -> str:
        """Heure au format FR : '14h30' ou '09h00'."""
        return self.scheduled_at.strftime("%Hh%M")


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def push_title(kind: ReminderKind, ctx: RdvContext) -> str:
    return {
        "24h": f"Rendez-vous demain à {ctx.time_fr}",
        "1h":  f"Rendez-vous dans 1 heure",
        "now": f"Votre rendez-vous commence",
    }[kind]


def push_body(kind: ReminderKind, ctx: RdvContext) -> str:
    if kind == "24h":
        return (
            f"Bonjour {ctx.first_name}, n'oubliez pas votre rendez-vous "
            f"{ctx.date_fr} à {ctx.time_fr} avec le Dr {ctx.doctor_name}."
        )
    if kind == "1h":
        return (
            f"Votre rendez-vous avec le Dr {ctx.doctor_name} "
            f"commence à {ctx.time_fr}. Préparez-vous !"
        )
    return (
        f"Votre téléconsultation avec le Dr {ctx.doctor_name} est en cours. "
        f"Touchez pour rejoindre."
    )


def sms_body(kind: ReminderKind, ctx: RdvContext) -> str:
    """SMS doivent rester < 160 caractères pour éviter le multipart facturé 2x."""
    if kind == "24h":
        return (
            f"Mood-IoT : rappel — RDV {ctx.date_fr} à {ctx.time_fr} avec "
            f"Dr {ctx.doctor_name}. Pour annuler : appelez le cabinet."
        )
    if kind == "1h":
        return (
            f"Mood-IoT : votre RDV avec Dr {ctx.doctor_name} commence à "
            f"{ctx.time_fr}. Lien : {ctx.jitsi_url}"
        )
    return (
        f"Mood-IoT : votre téléconsultation commence maintenant. "
        f"Rejoignez : {ctx.jitsi_url}"
    )


def email_subject(kind: ReminderKind, ctx: RdvContext) -> str:
    return {
        "24h": f"Rappel : votre rendez-vous demain {ctx.date_fr} à {ctx.time_fr}",
        "1h":  f"Votre rendez-vous commence dans 1 heure",
        "now": f"Votre téléconsultation commence maintenant",
    }[kind]


def email_html(kind: ReminderKind, ctx: RdvContext) -> str:
    """HTML simple, sans framework — compatible Gmail / Outlook / Hotmail."""
    intro = {
        "24h": (
            f"Ce message est un rappel : vous avez rendez-vous "
            f"<strong>{ctx.date_fr} à {ctx.time_fr}</strong>."
        ),
        "1h": (
            f"Votre rendez-vous commence dans 1 heure, à "
            f"<strong>{ctx.time_fr}</strong>."
        ),
        "now": "Votre téléconsultation commence maintenant.",
    }[kind]

    cta = (
        f'<a href="{ctx.jitsi_url}" '
        f'style="display:inline-block;background:#0288d1;color:#fff;'
        f'padding:12px 24px;border-radius:8px;text-decoration:none;'
        f'font-weight:600;margin-top:16px;">'
        f"Rejoindre la téléconsultation</a>"
    )

    reason_block = (
        f'<p style="color:#666;font-size:13px;">Motif : {ctx.reason}</p>'
        if ctx.reason
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
      <p>{intro}</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;
                    background:#f4f6fb;border-radius:8px;">
        <tr>
          <td style="padding:12px;color:#666;width:120px;">Praticien</td>
          <td style="padding:12px;font-weight:600;">Dr {ctx.doctor_name}</td>
        </tr>
        <tr>
          <td style="padding:12px;color:#666;">Spécialité</td>
          <td style="padding:12px;">{ctx.speciality}</td>
        </tr>
        <tr>
          <td style="padding:12px;color:#666;">Date</td>
          <td style="padding:12px;">{ctx.date_fr}</td>
        </tr>
        <tr>
          <td style="padding:12px;color:#666;">Heure</td>
          <td style="padding:12px;font-weight:600;">{ctx.time_fr}</td>
        </tr>
      </table>
      {reason_block}
      <div style="text-align:center;">{cta}</div>
      <p style="color:#888;font-size:13px;margin-top:24px;
                border-top:1px solid #eee;padding-top:16px;">
        Mood-IoT — Suivi du bien-être<br/>
        Pour modifier vos préférences de notification, ouvrez l'application
        et rendez-vous dans Réglages → Notifications.
      </p>
    </div>
    """
