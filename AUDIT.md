# AUDIT — App Patient Mood-IoT

> **Périmètre** : audit consolidé de l'app mobile Patient (`frontend/mobile/`) et des contrats backend qu'elle consomme, en préparation de la livraison des 8 capacités fonctionnelles (login Keycloak, capteurs santé, UX/UI, notifications multicanal, recos IA, messagerie, humeur emoji+voix, déploiement OVH HDS).
>
> Ce document complète `AUDIT_REPORT.md` (audit Antigravity antérieur, axé backend microservices et sécurité). Il **ne le remplace pas** : les conclusions IDOR et CVEs y restent valides et sont reprises ci-dessous.
>
> **Statut** : rapport d'entrée — **aucune modification de code n'a été appliquée**. Approbation requise avant Phase 2.

---

## 1. Stack & versions confirmées

### Mobile (`frontend/mobile/`)
- **Framework** : Expo SDK 52, React Native 0.76, React 18.3
- **Navigation** : `expo-router` 4.0 (file-based, structure `app/(auth)` + `app/(tabs)`)
- **State** : `zustand` 5.0 (2 stores : `authStore`, `healthStore`)
- **Secure storage** : `expo-secure-store` 14.0 (token + user blob)
- **Santé** : `react-native-health-connect` 3.5 (Android uniquement utilisé ; iOS = TODO)
- **Babel** : `react-native-reanimated/plugin` chargé mais **package non importé** dans le code → babel échoue silencieusement
- **Lint script** : `expo lint` (ESLint via expo) — **aucune config Prettier ni règle custom**
- **Tests** : **aucun** (pas de Jest, pas de `__tests__/`, pas de script `test` dans `package.json`)
- **TypeScript** : 5.6, strict mode à vérifier (`tsconfig.json` minimal)
- **i18n** : **aucun framework** — strings FR hardcodées directement dans les `.tsx`

### Backend (`backend/`)
- **Framework** : FastAPI 0.115, Pydantic 2.x, SQLAlchemy 2.x async + asyncpg + Alembic 1.14
- **Python** : 3.11 (Dockerfile base)
- **Auth actuel** : PyJWT 2.x (HS256), `bcrypt` 4.0.1, `pyotp` 2.9 (TOTP MFA), `passlib` (résiduel — abandonné selon `AUDIT_REPORT.md`)
- **ML** : XGBoost 2.x + scikit-learn 1.6 + SHAP 0.46 (fallback heuristique si modèle absent)
- **Notifications** : Anthropic 0.49 (Claude Haiku coaching IA), Twilio 9.x (SMS), `firebase-admin` 6.x (FCM push)
- **AWS** : `boto3` 1.35 + LocalStack en dev (S3 pour modèles ML)
- **Cache** : Redis 5.x
- **Email transactionnel** : `RESEND_API_KEY` déclaré dans `.env.example`, intégration mentionnée commit `3a170eb` — à vérifier dans le code
- **Logging** : `structlog` (JSON stdout, audit log Postgres en parallèle)
- **6 services + gateway** : auth (8001), patient (8002), scoring (8003), notification (8004), teleconsult (8005), doctor (8006), gateway (8000) — exposés sur ports 8010-8016 en local via Docker
- **App unifié** : `src/app_unified.py` monte tous les services sous `/api/v1` (cible Render free tier)

### Frontend dashboard médecin (`frontend/dashboard/`) — hors périmètre, mentionné pour contrats
- Next.js 14, TypeScript, Tailwind, déployé sur Vercel (`vercel.json` présent)
- Consomme 40+ endpoints backend (cf. section 7)

### Infrastructure
- Postgres 15 + Redis 7 + LocalStack via `docker-compose.yml`
- Migrations SQL dans `backend/infrastructure/database/` (01-extensions, 02-schema, 03-indexes, 04-seed, 05-doctor-institution-migration, 05-seed-aggregates, supabase-full-init)
- **Aucune CI/CD** : pas de `.github/workflows/`, pas de `.gitlab-ci.yml`. Traces de Render via `Dockerfile.render` et `render.yaml`

---

## 2. Architecture observée

### Mobile — pattern feature-based + service layer
```
frontend/mobile/
├── app/                       # expo-router (routes)
│   ├── _layout.tsx            # racine, redirect basé token
│   ├── (auth)/
│   │   ├── _layout.tsx
│   │   └── login.tsx
│   └── (tabs)/
│       ├── _layout.tsx        # tabs : Accueil / Humeur / Historique / Réglages
│       ├── index.tsx          # Accueil (gauge + coaching + 4 metrics)
│       ├── mood.tsx           # PHQ-9 (9 questions, emoji 4 niveaux)
│       ├── history.tsx        # historique 21j
│       └── settings.tsx       # profil, sync, notif switch, logout
└── src/
    ├── stores/                # Zustand
    │   ├── authStore.ts       # login/logout, SecureStore
    │   └── healthStore.ts     # fetchLatest, syncHealthData, PHQ-9
    ├── services/
    │   ├── api.ts             # fetch wrapper + 7 endpoints
    │   └── healthSync.ts      # HC (Android OK) / HealthKit (iOS TODO)
    └── components/
        ├── WellbeingGauge.tsx
        ├── CoachingBanner.tsx
        └── MetricCard.tsx
```

Architecture **propre et lisible**. Une seule incohérence majeure : la séparation `app/` (routes) vs `src/` (logique) est appliquée correctement mais `app/(tabs)/mood.tsx` (206 lignes) et `app/(tabs)/settings.tsx` (192 lignes) commencent à porter trop de logique métier — à extraire vers `src/` lors de la refonte.

### Backend — microservices FastAPI
```
backend/src/
├── app_unified.py        # monte tous les services sous /api/v1 (Render free)
├── auth/                 # PyJWT + TOTP MFA + bcrypt + refresh blacklist mémoire
├── patient/              # CRUD patients, mood (PHQ-9), health-data, consents
├── doctor/               # CRUD médecins, institutions, approbation admin
├── scoring/              # XGBoost + fallback heuristique + SHAP
├── notification/         # Anthropic coaching, Twilio SMS, FCM, WebSocket
├── teleconsult/          # Jitsi JWT sessions + notes
├── gateway/              # routing + auth middleware
└── shared/               # models SQLAlchemy, auth helpers, audit log
```

Architecture **mature** : 16 tables Postgres, 40+ endpoints, audit log structuré, Fernet encryption pour PHI sensibles (RPPS, license). Le service `auth` va être considérablement **réduit** par la migration Keycloak (suppression de login/register/refresh/MFA — seuls `/auth/me` + `/auth/register-profile` resteront).

---

## 3. État feature par feature (8 capacités)

Légende : ✅ implémentée & fonctionnelle / ⚠️ partielle / ❌ absente / 🔧 buggy.

### Capacité 1 — Login & session

| Élément | État | Preuve |
|---|---|---|
| Login email/password | ✅ | `app/(auth)/login.tsx:21-35`, `src/stores/authStore.ts:30-58` |
| Register | ❌ | aucun écran, endpoint `POST /auth/register` existe backend mais non câblé mobile |
| Apple Sign-In iOS | ❌ | zéro dépendance, zéro UI |
| Google Sign-In Android | ❌ | zéro dépendance, zéro UI |
| JWT access | ⚠️ | stocké en SecureStore (`authStore.ts:49`), envoyé via Bearer (`api.ts:18`) |
| **JWT refresh** | 🔧 | **aucune logique** : pas d'expiry check, pas de refresh endpoint appelé, table backend `refresh_tokens` existe mais blacklist en mémoire perdue au restart |
| Recovery password | ❌ | aucune route mobile, aucun endpoint backend `/auth/forgot-password` |
| MFA TOTP | ⚠️ | backend complet (`/auth/mfa/setup`, `/auth/mfa/verify`), **mais aucune UI mobile** |
| Logout complet (révocation backend) | ⚠️ | endpoint `DELETE /auth/logout` blacklist token, mais blacklist non persistée |
| Gestion session expirée sans perdre nav | ❌ | pas d'interceptor 401 dans `api.ts` |

**Verdict** : tout sauf email/password à reconstruire. La migration Keycloak (Phase 2.1) règle tout en une fois (Google + Apple + MFA + reset + refresh handled out-of-the-box par Keycloak).

### Capacité 2 — Connexion capteurs santé

| Élément | État | Preuve |
|---|---|---|
| Health Connect (Android) | ✅ | `src/services/healthSync.ts:24-96` — HR, Steps, Sleep, HRV |
| **HealthKit (iOS)** | 🔧 | `services/healthSync.ts:98-113` retourne `null` avec `console.warn("HealthKit non implémenté")` |
| Permissions granulaires + justification FR | ⚠️ | `app.json` `NSHealthShareUsageDescription` = "Mood-IoT utilise HealthKit pour suivre votre bien-etre." (sans accents) — à enrichir + écran in-app avant prompt natif |
| Métriques requises (BP, SpO2, glycémie) | ❌ | absent côté Android et iOS |
| Sync incrémentale | 🔧 | code lit toujours les 7 derniers jours (`healthSync.ts:48-55`) sans `lastSyncTimestamp` |
| Schéma unifié backend | ✅ | endpoint `POST /patients/{id}/health-data/batch` accepte le format unifié (`api.ts:112`) |
| BackgroundFetch | ❌ | aucun setup |

### Capacité 3 — UX/UI

| Élément | État | Preuve |
|---|---|---|
| Design tokens / système | ❌ | tout en `StyleSheet.create` inline, palette dispersée |
| Light + Dark mode | ❌ | `app.json` force `"userInterfaceStyle": "light"` |
| WCAG AA labels | ❌ | aucun `accessibilityLabel` / `accessibilityRole` dans les composants |
| États vide / erreur / offline | ⚠️ | quelques messages d'erreur basiques (`login.tsx:51`), pas de gestion offline |
| Skeleton loaders | ❌ | spinners basiques uniquement |
| Microinteractions / haptique | ❌ | aucun feedback haptique |
| Typo cohérente | ⚠️ | tailles dispersées (16, 18, 20, 24, 28...) sans échelle systématique |
| Material 3 / HIG | ❌ | composants génériques, pas alignés natifs |

### Capacité 4 — Notifications multicanal RDV

| Élément | État | Preuve |
|---|---|---|
| Backend modèle notification multi-canal | ✅ | table `notifications` avec enum `channel ∈ {push_fcm, sms, email, websocket, call}` |
| Twilio SMS | ✅ | `requirements.txt` + variables `TWILIO_*` dans `.env.example` |
| Resend email | ⚠️ | `RESEND_API_KEY` dans `.env.example`, intégration mentionnée commit `3a170eb` — à valider via grep |
| FCM push | ⚠️ | `firebase-admin` importé, `FCM_CREDENTIALS_JSON` déclaré, **mais aucun expo-notifications côté mobile**, aucun token FCM enregistré |
| Templates FR paramétrés | ❌ | aucun fichier de template dans `backend/src/notification/` |
| Préférences canal | ⚠️ | toggle `notifEnabled` (`settings.tsx:10`) en useState local, **non persisté backend** |
| Scheduler J-1 / H-1 / H0 | ❌ | aucun worker ni APScheduler/cron pour RDV |
| Deep linking détail RDV | ❌ | `scheme: "mood-iot"` configuré mais pas exploité |

### Capacité 5 — Notifications recos IA

| Élément | État | Preuve |
|---|---|---|
| Anthropic Claude branché | ✅ | déjà utilisé pour coaching L1 dans le service `notification` |
| Endpoint déclencheur depuis scoring | ⚠️ | logique d'escalade L1→L2→L3 existe, mais pas de génération de reco textuelle dédiée mobile |
| Push avec disclaimer FR | ❌ | aucune UI mobile |
| Écran reco détaillée + explication "pourquoi" | ❌ | absent |

### Capacité 6 — Messagerie médecin → patient

| Élément | État | Preuve |
|---|---|---|
| Table `messages` Postgres | ❌ | inexistante dans `02-schema.sql` |
| Endpoints backend | ❌ | aucun endpoint inbox/messages |
| Inbox mobile | ❌ | aucun écran, aucun store |
| Lu/non-lu, recherche, push | ❌ | absent |

**Note** : la table existante `notifications` couvre les notifications mais pas la messagerie persistante médecin↔patient — il faut bien une table dédiée.

### Capacité 7 — Humeur (emoji + voix)

| Élément | État | Preuve |
|---|---|---|
| Mood entry PHQ-9 (questionnaire clinique 9 questions) | ✅ | `app/(tabs)/mood.tsx:25-180`, table `mood_entries` Postgres |
| **Sélecteur emoji simple (5-7 niveaux)** | ❌ | n'existe pas — PHQ-9 n'est pas un substitut |
| Note texte courte avec entrée emoji | ❌ | absent |
| **Enregistrement voix** | ❌ | aucun `expo-av`, aucune UI |
| Transcription + analyse sentiment IA | ❌ | aucun module backend `voice_mood/` |
| Consentement voix horodaté | ❌ | absent |
| Endpoint agrégat ponderé | ❌ | absent |
| Édition/suppression dernière entrée seulement | ❌ | absent |

### Capacité 8 — Préparation déploiement

| Élément | État | Preuve |
|---|---|---|
| Dockerfile multi-stage | ⚠️ | `backend/Dockerfile.render` mono-stage, base `python:3.11-slim`, **root user**, **pas de healthcheck** |
| Dockerfile générique (non-Render) | ⚠️ | `backend/infrastructure/docker/Dockerfile` existe (utilisé par compose) — à inspecter et harmoniser |
| 12-factor / env vars | ✅ | `.env.example` complet, services lisent via `os.environ` / `pydantic-settings` |
| Secrets dans code | 🔧 | fallbacks par défaut dans `docker-compose.yml` (`mood_secret_2026`, `change-me-in-production`) — à retirer pour prod |
| Abstraction storage S3-compatible | ⚠️ | `boto3` utilisé pour LocalStack — à valider qu'il fonctionne tel quel sur OVH Object Storage (S3-compatible) |
| Logging JSON stdout | ✅ | `structlog` |
| CI/CD pipeline | ❌ | aucun `.github/workflows/` |
| `DEPLOY.md` | ❌ | absent |
| Helm chart ou manifests K8s | ❌ | absent |

---

## 4. Incohérences inter-sessions (Claude Code antérieur)

1. **Plugin Babel orphelin** — `babel.config.js` inclut `react-native-reanimated/plugin` mais `react-native-reanimated` n'est jamais importé dans le code (toujours dans `package.json`)
2. **Commentaires non français** — `src/components/WellbeingGauge.tsx:4-11` contient des bouts d'espagnol ("Muestra el bienestar") mélangés à du FR. Pas critique mais à uniformiser
3. **Permissions iOS sans accents** — `app.json` `NSHealthShareUsageDescription` : "bien-etre" au lieu de "bien-être"
4. **3 dépendances déclarées non importées** : `react-native-safe-area-context`, `react-native-screens`, `react-native-reanimated` (toutes peuvent être requises implicitement par Expo Router — à vérifier avant suppression)
5. **TODOs non résolus** :
   - `services/healthSync.ts:102` "TODO: implementer avec react-native-health (HealthKit)"
   - `services/healthSync.ts:185` "iOS: TODO"
6. **Architecture du backend** — `app_unified.py` mount-all + microservices séparés coexistent. Render free vise unified, OVH HDS K8s vise microservices. À documenter explicitement dans `DEPLOY.md`
7. **Migrations 05 dupliquées** : `05-doctor-institution-migration.sql` ET `05-seed-aggregates.sql` (deux fichiers avec préfixe `05`)
8. **Variables d'env DB en clair dans `docker-compose.yml`** : fallback `mood_secret_2026`. OK en dev, **interdit en prod**

---

## 5. Strings non-françaises visibles dans l'UI

Recherche grep exhaustive (`Text>`, `title:`, `placeholder=`, `label=`, etc.) dans `frontend/mobile/`:

✅ **Aucune string anglaise ou espagnole rendue à l'utilisateur final** dans les `.tsx`. L'app est 100% FR.

**Mais** : zéro framework i18n → toute string est un littéral dans le composant. La refonte UX/UI (Phase 2.7) extraira tout vers `src/i18n/fr.json`.

Commentaires en espagnol présents uniquement dans `WellbeingGauge.tsx` (cf. section 4 point 2) — pas visibles utilisateur.

---

## 6. Dépendances duplicates / mortes / obsolètes

### Mobile
- `react-native-reanimated` — déclaré dans `package.json` + plugin Babel chargé, **jamais importé** dans le code
- `react-native-safe-area-context` — déclaré mais aucun import
- `react-native-screens` — déclaré mais aucun import

→ Les 3 sont fréquemment requises implicitement par `expo-router` / Expo runtime. **Ne pas supprimer sans test build** : vérifier après `npx expo install` si Expo les considère encore nécessaires.

### Backend
- `python-jose` — mentionné dans `AUDIT_REPORT.md` comme **abandonné + CVE-2024-33663**. À retirer si présent (à confirmer dans `requirements.txt`, je vois seulement `PyJWT` dans le grep actuel — il a peut-être déjà été retiré)
- `passlib` — abandonné. À retirer si non utilisé (le code a migré vers bcrypt natif)
- `bcrypt`, `pyotp`, `python-jose` (si présent) **deviennent inutiles** après migration Keycloak

---

## 7. Risques sécurité prioritaires

### Critique
1. **IDOR `POST /mood`** : un patient peut injecter des entrées mood pour un autre `patient_id` en falsifiant le UUID. Fix prévu dans `proposals/rbac_fixes.md` (vérifier `patient_id == current_user.patient_id`). À appliquer **dans la feature Humeur**.
2. **IDOR `POST /health-data`** : même problème, un patient peut injecter des données santé pour un autre. À appliquer **dans la feature health-sensors**.
3. **IDOR `PUT /consents`** : un patient peut révoquer les consentements d'un autre. À fixer **dans la feature Humeur** (où on touche le consentement).
4. **IDOR `PUT /patients/{id}`** : un psychiatre peut modifier un patient sans vérification de la relation `patient_psychiatrist`. À fixer dans la migration Keycloak (les claims `realm_access.roles` ne suffisent pas — il faut joindre la table d'assignation).

### Élevé
5. **Refresh token blacklist en mémoire** — perdu à chaque restart du service auth. Devient un non-problème après Keycloak (Keycloak gère ses propres tokens persistants).
6. **JWT mobile sans expiry/refresh** — token actuel ne s'invalide jamais côté client. Réglé par Keycloak (`offline_access` scope + refresh PKCE).
7. **`console.warn` peut logger PII** (`healthSync.ts:93`, `healthStore.ts:60,94`) : si l'erreur API contient des champs utilisateur, ça atterrit dans les logs natifs. Mitigation : wrapper logger avec sanitisation, à inclure dans Phase 2.7.
8. **`docker-compose.yml` fallbacks de prod en clair** (`mood_secret_2026`, `change-me-in-production`) : OK dev, **à supprimer** pour les manifests prod K8s.

### Moyen
9. **Permissions Android Health surdimensionnées ?** — actuellement HR, Steps, Sleep, HRV. L'extension prévue (BP, SpO2, glucose) doit être justifiée use case par use case, RGPD principe de minimisation.
10. **Pas d'enforcement HTTPS côté mobile** — `fetch(baseUrl + ...)` accepte `http://` si `EXPO_PUBLIC_API_URL` mal configurée. À documenter / fixer en prod.

### Bas
11. **`EXPO_PUBLIC_*` vars sont publiques** par design — pas un risque, juste à rappeler qu'aucun secret n'y aille (l'API URL c'est OK).

---

## 8. Readiness déploiement OVH HDS

### Ce qui est déjà bon
- Logging structuré JSON stdout (`structlog`) → compatible OVH Logs Data Platform
- Pydantic Settings 2.x avec validation au boot → pattern 12-factor
- Postgres + Redis → services Managed disponibles chez OVH HDS
- S3-compatible storage abstraction (`boto3`) → fonctionne avec OVH Object Storage HDS
- Chiffrement Fernet pour PHI sensibles (RPPS, license) déjà en place
- `audit_log` table Postgres + logs structurés → preuve auditabilité HDS

### Gap pour OVH HDS production
| Item | Manque | Effort |
|---|---|---|
| **Certification HDS** | Souscription Public Cloud HDS + DPA signé OVH | externe, ~1 jour admin |
| **Kubernetes manifests / Helm charts** | Aucun déploiement K8s décrit | Phase 2.8 — 1 jour |
| **CI/CD pipeline** | Aucun `.github/workflows/` | Phase 2.8 — 0.5 jour |
| **Dockerfile multi-stage avec user non-root + healthcheck** | `Dockerfile.render` mono-stage en root | Phase 2.8 — 0.5 jour |
| **Secret manager wiring** | Tout passe par env vars en clair (OK avec K8s Secrets) | Phase 2.8 — documenté dans DEPLOY.md |
| **Keycloak (auth ID provider)** | À déployer + configurer realm | Phase 2.1 — 1 jour |
| **Backup automatique Postgres** | OVH Managed Postgres a backup auto, mais à documenter dans DEPLOY.md | Phase 2.8 |
| **Conservation audit_log 6 ans (HDS)** | Table existe, retention policy à formaliser | Phase 2.8 doc |
| **Procédure de réversibilité HDS** | À documenter (obligatoire HDS) | Phase 2.8 doc |
| **Registre des traitements RGPD** | À fournir hors code (compliance officer) | Phase 2.8 référence |
| **TLS bout-en-bout** | À configurer via cert-manager + Let's Encrypt sur Ingress | Phase 2.8 |
| **`DEPLOY.md`** | Absent | Phase 2.8 |

### Readiness GCP — pour information
GCP a été **éliminé pour la production** car non certifié HDS par la CNIL en 2026. Il reste viable comme cible **dev/staging avec données fictives uniquement** (Cloud Run free tier + Neon Postgres free). À mentionner brièvement dans `DEPLOY.md` section "Environnements low-cost dev/staging".

---

## 9. Résumé exécutif & recommandation

### Synthèse
- **L'app mobile Patient est une fondation propre mais largement incomplète** : 1464 lignes, architecture saine, 100% FR (sans framework i18n), mais **6 des 8 capacités du brief sont absentes ou partielles**.
- **Le backend est nettement plus mature** : 40+ endpoints, providers externes câblés (Twilio, Anthropic, FCM, Resend déclaré), modèles riches. La migration Keycloak permet de **supprimer beaucoup de code custom** (login, refresh, MFA, password reset) plutôt que d'ajouter.
- **3 IDOR critiques** identifiés dans `AUDIT_REPORT.md` ne sont **toujours pas corrigés**. Ils sont bloqueurs sécurité et seront fixés dans les features `health-sensors` et `humeur`.
- **0 test backend ou mobile** (sauf `test_scoring_regression.py`). Phase 2 inclura systématiquement des tests pour chaque feature.
- **0 CI/CD**. Phase 2.8 met en place GitHub Actions paramétré pour OVH Managed K8s.

### Recommandation d'ordre d'exécution (rappel du plan)
1. Phase 2.1 **`feature/auth-keycloak`** — fondation identité, débloque tout le reste
2. Phase 2.2 **`feature/messagerie`** — relativement isolée, validation rapide du flow push
3. Phase 2.3 **`feature/notifications-rdv`** — réutilise scheduler + canaux pour la suite
4. Phase 2.4 **`feature/health-sensors`** — fix HealthKit iOS + IDOR `/health-data`
5. Phase 2.5 **`feature/humeur`** — gros morceau (emoji + voix + IA + agrégat) + IDOR `/mood` et `/consents`
6. Phase 2.6 **`feature/ai-recos`** — réutilise notification + Anthropic
7. Phase 2.7 **`feature/ux-ui`** — refonte design tokens + i18n extraction + WCAG (touche presque tous les fichiers .tsx)
8. Phase 2.8 **`feature/deploy`** — clôture infra + DEPLOY.md

### Approbation requise
**Aucune modification de code n'a été effectuée à ce stade.** Merci de valider ce rapport (ou de demander des ajustements) avant que je démarre la Phase 2.1 `feature/auth-keycloak`.
