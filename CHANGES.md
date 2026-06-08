# CHANGES.md — Audit & modernisation Mood-IoT

> Branche : `audit/modernization` → 21 commits, **101 fichiers**, **+29 281 / −1 841** lignes
> Période : audit complet + 8 phases de refonte feature par feature
> Cible : application mobile **Patient** (Expo SDK 52 / React Native 0.76)
> Backend : 7 microservices FastAPI + Postgres 15 + Redis 7 + Keycloak 26
> Déploiement cible : **OVH Public Cloud HDS** (santé, France)

---

## Phase 1 — Audit initial

**Livrable** : [`AUDIT.md`](./AUDIT.md)

Cartographie de l'existant feature par feature avec preuves (fichier:ligne) :
- Auth Keycloak ❌, JWT refresh ⚠️, password reset ❌
- HealthKit iOS 🔧 (TODO), Health Connect Android ✅
- Notifications push ⚠️ (endpoint câblé mais pas de setup mobile)
- Messagerie médecin→patient ❌
- Humeur emoji ⚠️ (PHQ-9 clinique au lieu d'emoji simple)
- Humeur voix ❌
- Consentements explicites ❌, dark mode ❌, i18n framework ⚠️

Incohérences identifiées : commentaires espagnol résiduels, TODOs orphelins,
3 deps inutilisées (`safe-area-context`, `screens`, `reanimated`).

3 IDOR critiques backend documentés dans `proposals/rbac_fixes.md`.

---

## Phase 2.1 — `feature/auth-keycloak`

### Infra
- Helm chart Bitnami `keycloak` + Postgres dédié schéma `keycloak`
- Realm `moodiot` avec clients `mobile-app`, `dashboard-medecin`, `backend-services`
- Identity providers Google + Apple Sign-In (configuration documentée)
- Authentication flows + Required Action OTP
- SMTP Keycloak → Resend (`info@mood-iot.fr` vérifié DKIM)
- Templates email FR custom (`themes/moodiot/email/`)

### Backend (`backend/src/auth/`)
- **Suppression** : `/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/mfa/*`, `/auth/logout`
- **Conservé** : `/auth/me`, `/auth/register-profile`, `/auth/sync`
- **Nouveau** : `src/shared/keycloak.py` (JWKS fetcher avec cache cachetools 1h)
- **Nouveau** : `verify_keycloak_token()` middleware (RS256, aud, iss, exp)
- Migration `06-keycloak-migration.sql` : ajout `users.keycloak_user_id`, drop `password_hash`, `mfa_secret`, `refresh_tokens`
- Variables d'env : `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URI`, `KEYCLOAK_AUDIENCE`
- Wiring : tous les 7 services backend reçoivent les vars Keycloak

### Mobile (`frontend/mobile/`)
- D'abord OIDC PKCE via `expo-auth-session` puis **switch vers Direct Access Grants** suite au feedback "el browser redirect parece obsoleto" — form natif email+password
- `authStore` : tokens (access 5 min + refresh) en `expo-secure-store`
- Refresh transparent sur 401 + clear store sur échec refresh
- Écran `(auth)/login.tsx` : form natif FR
- Écran `(auth)/welcome.tsx` : complétion profil patient post-1er-login

### Dashboard médecin (Antigravity, coord)
- Migration auth vers NextAuth.js v5 + Keycloak provider
- Fix blank page `/register/doctor/complete`
- Sidebar : nom du médecin connecté

---

## Phase 2.2 — `feature/messagerie` médecin → patient

### Backend
- Nouvelle table `messages` (id, sender_doctor_id, recipient_patient_id, body Fernet, sent_at, read_at)
- `GET /patients/me/messages?unread_only=…`
- `GET /patients/me/messages/unread-count` (badge mobile)
- `GET /patients/me/messages/:id`
- `PATCH /patients/me/messages/:id/read`
- Endpoint dashboard : `POST /doctor/patients/:id/messages` (réutilise contrat existant si présent)

### Mobile
- Onglet **Messages** (`app/(tabs)/messages.tsx`) avec inbox + badge non-lus
- Refresh auto toutes les 60s dans `_layout.tsx`
- `messagesStore` zustand

---

## Phase 2.3 — `feature/notifications-rdv` multicanal

### Backend
- APScheduler dans `notification` service pour rappels **J-1 / H-1 / H0**
- Templates FR paramétrés dans `backend/src/notification/templates/fr/`
  (push, SMS, email — variables date/heure/médecin/Jitsi link)
- `PATCH /patients/me/notification-preferences` avec persistance Postgres
  (`push_enabled, sms_enabled, email_enabled, rdv_reminder_24h, rdv_reminder_1h, rdv_reminder_now, phone_e164`)

### Mobile
- Sub-screen `(tabs)/notifications-settings.tsx` (caché de la tab bar via `href: null`)
- Switches optimistic + rollback sur erreur, validation E.164 du téléphone
- Settings → "Gérer mes notifications" link vers le sub-screen

---

## Phase 2.4 — `feature/health-sensors`

### Backend
- 3 nouveaux endpoints **anti-IDOR** sous `/patients/me/health-data/*` :
  `GET /status`, `POST` (1 jour), `POST /batch` (≤ 90 jours)
- Le patient est résolu via JWT, plus besoin de passer `patient_id` côté client
- Endpoints legacy `/{patient_id}/` conservés (dashboard médecin)
- `SyncStatusResponse` retourne `last_sync_at`, `last_date_synced`, `source_platform`, `days_synced_last_30`

### Mobile
- **Fix bug silencieux** : backend attend `step_count`, mobile envoyait `steps`
  → les pas étaient perdus
- `healthSync.ts` réécrit :
  - Permissions persistées dans SecureStore (`granted` + `hasAsked`)
  - Lecture étendue : HR, HRV, sommeil, pas, **+ tension artérielle, + SpO₂**
  - Helpers `getLastSyncAt` / `setLastSyncAt`
  - Stub iOS HealthKit documenté (activation Mac + Xcode dans une étape ultérieure)
- Plugin Expo `react-native-health-connect` activé dans `app.json` →
  injection automatique de `PERMISSIONS_RATIONALE` intent-filter dans AndroidManifest
- 6 `android.permission.health.*` déclarées
- Nouvel écran `(auth)/health-permissions.tsx` : justifications FR par capteur,
  mention OVH HDS, bouton "Plus tard"
- Lancé 1 seule fois après le 1er login (`getPermissionsState().hasAsked`)
- Settings → carte "Données de santé" :
  - Statut Health Connect (Autorisé / Non autorisé)
  - Dernière sync (relative — "il y a 5 min")
  - Bouton "Synchroniser maintenant" qui redemande les permissions si manquantes

---

## Phase 2.5 — `feature/humeur` emoji + voix + agrégat

### Backend
- Nouvelle table `humeur_entries` (séparée de `mood_entries` PHQ-9 clinique)
  `{id, patient_id, source ∈ ('emoji','voix'), emoji_level (0-6), note, audio_url, transcription, humeur_globale, intensité, émotions_détectées JSONB, mots_clés JSONB, resumé, created_at}`
- Endpoints `/patients/me/humeur/*` :
  - `POST /emoji` (level 0-6 + note FR optionnelle)
  - `POST /voice` (multipart audio → Whisper STT → Claude Haiku sentiment → persist)
  - `GET ?limit=N` (historique)
  - `PATCH /latest` (édition uniquement de la dernière entrée du jour)
  - `DELETE /latest`
- `GET /patients/:id/humeur/aggregate?period=7d|30d|90d` :
  `{moyenne_emotionnelle, fréquence_par_emotion, tendance ∈ ('améliorant','stable','dégradant'), jours_avec_registres, alerte_pattern_négatif (bool), période}`
- Module `backend/src/voice_mood/` : `transcribe()` (Whisper) + `analyze()` (Claude Haiku, prompt structuré JSON)
- `backend/src/shared/storage.py` : abstraction S3 (LocalStack en dev, OVH Object Storage HDS en prod)

### Mobile
- **Refonte humeur** suite au feedback "PHQ-9 demasiado complejo" : **sélecteur emoji 5 niveaux** simple (Très bien / Bien / Neutre / Mal / Très mal) + note texte courte
- Pas encore d'écran voix (différé)
- "Mes tendances" différée (sub-screen non implémentée)
- Consentement explicite voix/IA via `ConsentModal` (Phase 2.7)

---

## Phase 2.6 — `feature/ai-recos` notifications IA

### Backend
- `backend/src/notification/ai_coach.py` :
  - `SYSTEM_PROMPT` bannit les mots de diagnostic
  - `RISK_HARD_CEILING = 80` : au-delà, l'IA ne suggère rien et l'app affiche un message d'urgence FR
  - `send_ai_coaching()` orchestrateur : appelle Claude Haiku 4.5 → persiste `Notification` rows
- Templates FR `backend/src/notification/templates/fr/ai_coaching.py` (push + email) avec disclaimer obligatoire :
  > « Ceci est une suggestion informative et bienveillante. Elle ne remplace pas l'avis d'un professionnel de santé. »
- Email envoyé vérifié end-to-end via Resend (`cinthya_ldb@hotmail.com`, status=sent)

---

## Phase 2.7 — `feature/ux-ui` refonte + consentements

### Identité visuelle
- `frontend/mobile/assets/icon.png` (1024×1024, dégradé bleu clair + cœur stéthoscope)
- `frontend/mobile/assets/adaptive-icon.png` (foreground Android)
- `frontend/mobile/assets/splash.png` (1242×2208, backgroundColor `#f0f7ff`)
- `frontend/dashboard/public/favicon.ico` + icon-192/512 + apple-touch-icon
- `frontend/dashboard/public/manifest.webmanifest` (PWA)
- Dashboard `<head>` : title FR, OG tags, theme-color, manifest link

### Design system
- `frontend/mobile/src/theme/tokens.ts` :
  - Palette `primary50–900`, success/warning/danger/neutral
  - Color schemes `light` + `dark`
  - `space` (xs–5xl), `radius` (sm–pill), `font` (size + weight + lineHeight)
  - Helper `getColors(scheme)` pour switch dark/light

### Composants nouveaux
- `app/(auth)/onboarding.tsx` : 3 slides ScrollView pagingEnabled, dots indicator, flag `onboarding_seen_v1` en SecureStore + helper `hasSeenOnboarding()` exporté
- `src/components/ConsentModal.tsx` : bottom-sheet modal 4 checkboxes (CGU/RGPD requis, Health/AI optionnels), liens vers `mood-iot.fr/cgu` + `/rgpd`
- Cablé dans `(tabs)/_layout.tsx` : se montre si `fetchMyConsents()` retourne `cgu=false || rgpd=false`. Refus → Alert + signOut

### Backend consentements
- `GET / PUT /patients/me/consents` (mapping CGU/RGPD/HealthSensors/AI → `ConsentType` existant)
- Déclaré AVANT `/{patient_id}/consents` pour éviter le conflit de route FastAPI

### Fix UX
- `_layout.tsx` re-lit `hasSeenOnboarding()` à chaque changement de segment → corrige la boucle infinie sur slide 3 d'onboarding
- `useSafeAreaInsets()` sur onboarding + health-permissions → boutons ne sont plus masqués par la barre de navigation Android

---

## Phase 2.8 — `feature/deploy` OVH HDS

### Dockerfile multi-stage
- `backend/infrastructure/docker/Dockerfile` refactoré :
  - Stage `builder` (avec gcc, libpq-dev, build deps)
  - Stage `runtime` minimal (curl + libpq5 seulement)
  - User non-root `mood:1001` (compat PodSecurityPolicy OVH HDS)
  - Healthcheck HTTP `curl -fsS http://localhost:PORT/health`
  - CMD sans `--reload` (prod), avec `--proxy-headers --forwarded-allow-ips='*'`

### Variables d'environnement
- `.env.example` exhaustif : Keycloak, JWT legacy, Object Storage S3-compat (OVH/LocalStack), Anthropic, Whisper OpenAI, Resend, Twilio, FCM, Jitsi, **`ENCRYPTION_KEY` Fernet**, OTel, Sentry, marquage `change-me-*` sur tous les secrets

### Documentation déploiement
- `DEPLOY.md` complet :
  - Pré-requis légaux (DPA OVH HDS, AIPD CNIL, registre RGPD)
  - Commandes OVH (Public Cloud HDS, Managed K8s GRA9, Postgres Essential HDS, Redis, Object Storage HDS, Container Registry)
  - Coût estimé 100 patients : ~345 €/mois HT
  - Keycloak via Helm Bitnami + Helm cert-manager + ingress-nginx + Let's Encrypt
  - Secrets via Sealed Secrets (recommandé) ou HashiCorp Vault
  - Ordre des 8 migrations Postgres (sans `04-fixtures-dev.sql` en prod)
  - Conservation 6 ans `audit_log` (Code santé publique L.1111-7), 20 ans données patient (L.1112-7)
  - PRA : RTO 4h, RPO 1h, région bascule RBX si prod GRA
  - Environnement low-cost staging non-PHI (GCP Cloud Run + Neon + Cloudflare R2 gratis)
  - Checklist go-live 17 points

### CI/CD
- `.github/workflows/ci.yml` :
  - **lint** : ruff (backend) + tsc (mobile)
  - **test-backend** : pytest avec services postgres 15 + redis 7
  - **build-images** : matrix des 7 microservices, push vers OVH Container Registry, cache GHA, tag `latest` + `sha`
  - **deploy-prod** : `workflow_dispatch` manuel, helm upgrade + smoke test sur `api.moodiot.fr`

---

## Récapitulatif des fichiers

### Créés
- `AUDIT.md`, `CHANGES.md`, `DEPLOY.md`
- `.github/workflows/ci.yml`
- `backend/src/voice_mood/` (transcribe + analyze)
- `backend/src/shared/keycloak.py`, `backend/src/shared/storage.py`
- `backend/src/notification/ai_coach.py`, `backend/src/notification/templates/fr/*.py`
- `backend/migrations/06-keycloak-migration.sql`, `06-humeur-messages-prefs.sql`, `07-humeur-emoji-voix.sql`
- `frontend/mobile/src/theme/tokens.ts`
- `frontend/mobile/src/components/ConsentModal.tsx`
- `frontend/mobile/app/(auth)/welcome.tsx`, `onboarding.tsx`, `health-permissions.tsx`
- `frontend/mobile/app/(tabs)/messages.tsx`, `notifications-settings.tsx`
- `frontend/mobile/assets/icon.png`, `adaptive-icon.png`, `splash.png`
- `frontend/dashboard/public/manifest.webmanifest` + icons

### Modifiés (majeurs)
- `backend/src/auth/main.py` (refactor Keycloak)
- `backend/src/patient/main.py` (+11 endpoints /me/*, fix IDOR, voix, consents, prefs)
- `backend/src/notification/main.py` (scheduler RDV + AI coaching dispatcher)
- `backend/src/shared/auth.py` (verify Keycloak token)
- `backend/infrastructure/docker/Dockerfile` (multi-stage)
- `frontend/mobile/app.json` (plugin health-connect, permissions, icons)
- `frontend/mobile/app/_layout.tsx` (routing onboarding + health perms + SafeArea)
- `frontend/mobile/app/(tabs)/_layout.tsx` (ConsentModal post-login)
- `frontend/mobile/app/(tabs)/settings.tsx` (Health card + nav vers notif-settings)
- `frontend/mobile/app/(tabs)/mood.tsx` (refonte emoji)
- `frontend/mobile/src/services/api.ts` (4 nouvelles APIs : consents, notif prefs, health status, etc.)
- `frontend/mobile/src/services/healthSync.ts` (permissions persistées, BP/SpO2, fix step_count)
- `frontend/mobile/src/stores/authStore.ts` (Direct Access Grants + refresh)
- `frontend/mobile/src/stores/messagesStore.ts`, `humeurStore.ts` (nouveaux)
- `frontend/dashboard/src/app/layout.tsx` (brand head)
- `.env.example` (exhaustif)
- `docker-compose.yml` (Keycloak + KEYCLOAK_* env propagation)

### Supprimés / archivés
- `mobile-hub/SanteConnect/` → archivé dans `attic/SanteConnect/` (cf. AUDIT.md)
- Endpoints `/auth/login`, `/register`, `/refresh`, `/mfa/*`, `/logout` (Keycloak les remplace)
- Tables `refresh_tokens` (Keycloak gère côté serveur)
- Colonnes `users.password_hash`, `users.mfa_secret`

---

## Vérifications effectuées

| Vérification | Résultat |
|---|---|
| `npx tsc --noEmit` côté mobile | ✅ 0 erreur |
| `docker compose up` (8 services) | ✅ tous healthy |
| Backend OpenAPI expose tous les nouveaux endpoints | ✅ vérifié via `/openapi.json` |
| Token Keycloak (Marie) → `GET /auth/me` | ✅ retourne profil avec `realm_access.roles` |
| `PUT /patients/me/consents` | ✅ 200 OK + INSERT consents + audit_log |
| Email AI coaching dispatché via Resend | ✅ `cinthya_ldb@hotmail.com`, status=sent |
| EAS build Android APK | ✅ build #2 lancé (build #1 = `5b99c931`, build #2 = `6645cbe8`) |
| Test physique sur Samsung Android | ⚠️ Onboarding loop + SafeArea → corrigé dans `8006723` |

---

## Décisions et trade-offs

| Décision | Alternative écartée | Justification |
|---|---|---|
| Keycloak self-hosted | Firebase Auth | Souveraineté FR + HDS, pas de lock-in, MFA TOTP gratuit |
| Direct Access Grants (native login) | OIDC PKCE browser redirect | Feedback patient : "el redirect parece obsoleto" |
| Emoji selector 5 niveaux | PHQ-9 clinique conservé | Feedback : "demasiado complejo" — PHQ-9 reste mais via humeur_entries séparé |
| OVH Public Cloud HDS | GCP / AWS | Légal : HDS obligatoire en France pour PHI |
| Anthropic Claude Haiku 4.5 | OpenAI GPT-4o | EU data residency, coût ~1 €/mois |
| Whisper API OpenAI | whisper.cpp self-hosted | Coût ~3€/mois vs complexité ops + latence GPU |
| Resend SMTP | AWS SES | Domaine `mood-iot.fr` déjà vérifié, prix similaire |
| `react-native-health-connect` | `react-native-health` (HealthKit) | Cible Android d'abord (test physique), iOS différé |

---

## Points encore ouverts (post-livraison)

- [ ] HealthKit iOS (stub documenté, activation requiert Mac + Xcode + EAS iOS)
- [ ] Humeur voix côté mobile (backend prêt, écran d'enregistrement à créer)
- [ ] "Mes tendances" sub-screen mobile
- [ ] i18n framework (`i18next` + `react-i18next`) — strings FR hardcodées actuellement
- [ ] Dark mode toggle dans Réglages (tokens prêts, switch UI à câbler)
- [ ] Skeleton loaders + offline banner
- [ ] Migration Twilio SMS → OVH SMS (souveraineté)
- [ ] Tests Jest mobile + extension couverture pytest backend
- [ ] AIPD CNIL + registre traitements RGPD (Phase légale)

---

*Version : 1.0 — 2026-06-08*
