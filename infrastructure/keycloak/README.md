# Keycloak — Mood-IoT identity provider

Keycloak est la **source de vérité d'identité** pour Mood-IoT : email/mot de
passe, Google Sign-In, Apple Sign-In, MFA TOTP, reset password, vérification
email. Le backend FastAPI ne fait que vérifier les access tokens RS256 émis
par Keycloak.

## Local dev

Le service `keycloak` est démarré par `docker compose up` (port 8080).

Au premier démarrage, le realm `moodiot` est importé depuis
`realm-moodiot.json` (volume monté en lecture seule).

- Console admin : <http://localhost:8080>
  - login : `admin` / `change-me-keycloak-admin` (variables `KC_BOOTSTRAP_ADMIN_*`)
- OIDC discovery : <http://localhost:8080/realms/moodiot/.well-known/openid-configuration>
- JWKS : <http://localhost:8080/realms/moodiot/protocol/openid-connect/certs>

### Variables d'env du backend pointant vers ce Keycloak

```env
KEYCLOAK_ISSUER=http://keycloak:8080/realms/moodiot
KEYCLOAK_JWKS_URI=http://keycloak:8080/realms/moodiot/protocol/openid-connect/certs
KEYCLOAK_TOKEN_ENDPOINT=http://keycloak:8080/realms/moodiot/protocol/openid-connect/token
KEYCLOAK_AUDIENCE=mobile-app,dashboard-medecin,backend-services
```

## Clients OIDC configurés

| Client ID | Type | PKCE | Usage |
|---|---|---|---|
| `mobile-app` | public | requis (S256) | App mobile Expo (`mood-iot://callback`) |
| `dashboard-medecin` | public | requis (S256) | Dashboard Next.js médecin |
| `backend-services` | confidential (service account) | n/a | Appels Admin API depuis le backend (sync user, webhooks) |

## Identity providers à configurer en console (out-of-band)

Le realm de base **n'inclut pas** les credentials Google/Apple pour des
raisons de sécurité. À configurer manuellement via la console admin :

1. **Google** : Identity Providers → Add provider → Google
   - Créer un OAuth client côté <https://console.cloud.google.com/apis/credentials>
   - Authorized redirect URI : `http://localhost:8080/realms/moodiot/broker/google/endpoint`
     (prod : `https://auth.moodiot.fr/realms/moodiot/broker/google/endpoint`)
2. **Apple** : Identity Providers → Add provider → OpenID Connect v1.0 (Apple)
   - Apple Developer team ID + Services ID + private key (.p8)
   - Authorized redirect URI : `http://localhost:8080/realms/moodiot/broker/apple/endpoint`

## SMTP (reset password, email verify)

Le SMTP du realm est configuré pour pointer vers **Resend**
(`smtp.resend.com:587`, STARTTLS). En local, mettez votre `RESEND_API_KEY`
dans `.env` — Keycloak l'utilisera via la variable `${env.RESEND_API_KEY}`.

## Production OVH HDS

En production, Keycloak est déployé sur le cluster OVH Managed Kubernetes
HDS via le Helm chart `codecentric/keycloakx` ou `bitnami/keycloak`. La
config realm est importée au boot via un init container qui monte ce
même `realm-moodiot.json` depuis un ConfigMap.

Voir `DEPLOY.md` (créé en Phase 2.8) pour la procédure complète.
