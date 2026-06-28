"""
Mood-IoT : client d'administration Keycloak (création de comptes patients).

Utilise le client confidentiel `backend-services` (grant client_credentials,
config `KEYCLOAK_ADMIN_CLIENT_ID` / `KEYCLOAK_ADMIN_CLIENT_SECRET`) pour :
  - créer un utilisateur (rôle `patient`),
  - déclencher l'email « définir votre mot de passe » (action UPDATE_PASSWORD)
    envoyé via le SMTP du realm (Resend).

Le service account doit posséder le rôle `realm-management:manage-users`.
"""

from __future__ import annotations

import logging

import httpx

from src.shared.config import settings

logger = logging.getLogger("mood_iot.keycloak_admin")

# Lifespan du lien « définir mot de passe » : 24 h (en secondes).
_ACTION_LINK_LIFESPAN = 24 * 3600
_HTTP_TIMEOUT = 15.0


class KeycloakAdminError(Exception):
    """Erreur lors d'un appel à l'API d'administration Keycloak."""


def _base_and_realm() -> tuple[str, str]:
    """Déduit (base_url, realm) depuis KEYCLOAK_TOKEN_ENDPOINT.

    Ex : http://keycloak:8080/realms/moodiot/protocol/openid-connect/token
         -> ("http://keycloak:8080", "moodiot")
    """
    ep = settings.KEYCLOAK_TOKEN_ENDPOINT
    if "/realms/" not in ep:
        raise KeycloakAdminError("KEYCLOAK_TOKEN_ENDPOINT mal configuré")
    base, rest = ep.split("/realms/", 1)
    realm = rest.split("/", 1)[0]
    return base.rstrip("/"), realm


async def _get_admin_token(client: httpx.AsyncClient) -> str:
    """Récupère un token d'admin via le grant client_credentials."""
    if not settings.KEYCLOAK_ADMIN_CLIENT_ID or not settings.KEYCLOAK_ADMIN_CLIENT_SECRET:
        raise KeycloakAdminError("KEYCLOAK_ADMIN_CLIENT_ID/SECRET non configurés")
    resp = await client.post(
        settings.KEYCLOAK_TOKEN_ENDPOINT,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
        },
    )
    if resp.status_code != 200:
        raise KeycloakAdminError(f"token admin échoué : {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


async def create_patient_account(
    email: str,
    first_name: str,
    last_name: str,
) -> str:
    """Crée un compte patient dans Keycloak et envoie l'email de mot de passe.

    Retourne l'identifiant Keycloak (`sub`) du nouvel utilisateur.
    Lève KeycloakAdminError en cas d'échec (ex : email déjà utilisé -> 409).
    """
    base, realm = _base_and_realm()
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        token = await _get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 1) Créer l'utilisateur (email = username ; non vérifié -> il le fera).
        create_resp = await client.post(
            f"{base}/admin/realms/{realm}/users",
            headers=headers,
            json={
                "username": email,
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": False,
            },
        )
        if create_resp.status_code == 409:
            raise KeycloakAdminError("email_deja_utilise")
        if create_resp.status_code not in (201, 204):
            raise KeycloakAdminError(
                f"création utilisateur échouée : {create_resp.status_code} {create_resp.text}"
            )

        # L'id est dans l'en-tête Location : .../users/{id}
        location = create_resp.headers.get("Location", "")
        kc_user_id = location.rstrip("/").split("/")[-1]
        if not kc_user_id:
            raise KeycloakAdminError("id utilisateur Keycloak introuvable (Location vide)")

        # 2) Assigner le rôle realm `patient`.
        await _assign_realm_role(client, base, realm, headers, kc_user_id, "patient")

        # 3) Envoyer l'email « définir votre mot de passe » (+ vérifier l'email).
        await _send_set_password_email(client, base, realm, headers, kc_user_id)

        logger.info("Compte patient Keycloak créé (%s) pour %s", kc_user_id, email)
        return kc_user_id


async def _assign_realm_role(
    client: httpx.AsyncClient,
    base: str,
    realm: str,
    headers: dict,
    user_id: str,
    role_name: str,
) -> None:
    role_resp = await client.get(
        f"{base}/admin/realms/{realm}/roles/{role_name}", headers=headers
    )
    if role_resp.status_code != 200:
        # Non bloquant : on log mais on ne casse pas la création.
        logger.warning("Rôle realm '%s' introuvable (%s)", role_name, role_resp.status_code)
        return
    role = role_resp.json()
    assign_resp = await client.post(
        f"{base}/admin/realms/{realm}/users/{user_id}/role-mappings/realm",
        headers=headers,
        json=[{"id": role["id"], "name": role["name"]}],
    )
    if assign_resp.status_code not in (204, 200):
        logger.warning(
            "Assignation du rôle '%s' échouée : %s", role_name, assign_resp.status_code
        )


async def _send_set_password_email(
    client: httpx.AsyncClient,
    base: str,
    realm: str,
    headers: dict,
    user_id: str,
) -> None:
    resp = await client.put(
        f"{base}/admin/realms/{realm}/users/{user_id}/execute-actions-email",
        headers=headers,
        params={"lifespan": _ACTION_LINK_LIFESPAN},
        json=["UPDATE_PASSWORD", "VERIFY_EMAIL"],
    )
    if resp.status_code not in (204, 200):
        # Non bloquant : le compte existe, l'email pourra être renvoyé.
        logger.warning(
            "Envoi de l'email de mot de passe échoué : %s %s",
            resp.status_code,
            resp.text,
        )


async def delete_account(kc_user_id: str) -> None:
    """Supprime un compte Keycloak (best-effort, ne lève pas)."""
    try:
        base, realm = _base_and_realm()
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            token = await _get_admin_token(client)
            await client.delete(
                f"{base}/admin/realms/{realm}/users/{kc_user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception:  # noqa: BLE001
        logger.exception("Échec suppression compte Keycloak %s", kc_user_id)
