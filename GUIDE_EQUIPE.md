# 🚀 Guide de l'équipe — Mood-IoT (pas à pas, depuis zéro)

> Guide d'onboarding pour quelqu'un qui travaille sur le projet **pour la première fois**.
> Si tu veux seulement toucher au **dashboard médecin**, saute directement à
> l'[Option A](#-option-a-recommandée--dashboard-local--backend-déployé).

---

## 1. C'est quoi Mood-IoT ?

Système de **détection précoce des rechutes dépressives**. Il a 3 parties :

| Partie | Technologie | Qui l'utilise |
|---|---|---|
| **App mobile (patient)** | Expo / React Native | Le patient enregistre son humeur et les capteurs |
| **Dashboard (médecin)** | Next.js 14 + NextAuth v5 | Le psychiatre voit patients, scores, alertes, téléconsultations |
| **Backend** | FastAPI (microservices) + PostgreSQL + Redis + Keycloak | API + authentification + scoring + notifications |

**Le backend est déjà déployé** sur un serveur (Hetzner Cloud), donc tu **n'as PAS
besoin de le lancer** pour travailler sur le dashboard ou l'app mobile :

- API : `https://api.mood-iot.fr`  (doc Swagger : `https://api.mood-iot.fr/docs`)
- Auth (Keycloak) : `https://auth.mood-iot.fr`
- Dashboard en production : `https://dashboard.mood-iot.fr`

---

## 2. Prérequis (à installer une fois)

| Outil | Version | Pour quoi |
|---|---|---|
| **Git** | récente | cloner le dépôt |
| **Node.js** | **18+** (recommandé 20 LTS) | dashboard et app mobile |
| **npm** | livré avec Node | dépendances |
| **Python** | **3.11+** | simulateur de données et scripts de QA |
| **Docker Desktop** | récente | _seulement_ pour l'Option B (backend local) |
| **App Expo Go** | sur ton téléphone | _seulement_ pour tester l'app mobile |

Vérifie que tu as l'essentiel :
```bash
git --version
node --version    # doit afficher v18 ou plus
npm --version
python --version  # 3.11+
```

---

## 3. Cloner le dépôt

Le projet vit dans **deux dépôts** (maintenus identiques) : `origin` (Cinthya) et
`team` (équipe). Clone celui de l'équipe :

```bash
git clone https://github.com/saraahsarah-ops/mood-iot.git
cd mood-iot
git checkout audit/modernization     # <-- branche de travail (PAS main)
git pull
```

> ⚠️ **On travaille toujours sur la branche `audit/modernization`**, pas sur `main`.

### Structure du projet
```
mood-iot/
├── backend/              # microservices FastAPI (gateway, auth, patient, scoring,
│   │                     #   notification, teleconsult, doctor) + modèles + scripts
│   ├── src/
│   └── scripts/          # migrations SQL ponctuelles
├── frontend/
│   ├── dashboard/        # dashboard médecin (Next.js)  <- ici travaille Hawa
│   └── mobile/           # app patient (Expo)            <- ici travaille Cinthya
├── qa/                   # scripts de tests E2E (Playwright + API)
├── docker-compose.yml        # stack LOCALE (Option B)
├── docker-compose.prod.yml   # stack du serveur (ne pas toucher pour le dev)
└── GUIDE_EQUIPE.md       # ce guide
```

---

## 4. ✅ Option A (recommandée) — Dashboard local + backend déployé

**La plus simple.** Tu ne lances ni backend ni base de données : ton dashboard sur
`localhost:3000` parle à l'API et au Keycloak **déjà déployés**. Tu vois les
**données réelles** (à jour) et le login fonctionne de bout en bout.

```bash
cd frontend/dashboard
cp .env.example .env.local      # puis éditer .env.local (voir ci-dessous)
npm install
npm run dev                     # ouvre http://localhost:3000
```

### Quoi remplir dans `.env.local`
Presque tout est déjà prêt dans `.env.example` (pointe vers le backend déployé).
Tu dois seulement remplir **2 valeurs** :

```ini
# 1) Secret qui signe ta session locale. Génère-le avec :
#    openssl rand -base64 32      (sous Windows : Git Bash, ou https://generate-secret.vercel.app/32)
AUTH_SECRET=colle-ici-une-valeur-aleatoire-de-32-octets

# 2) Secret du client Keycloak `dashboard-medecin`. PAS dans le dépôt (sensible).
#    Demande-le à Cinthya / à l'équipe via un canal privé.
AUTH_KEYCLOAK_SECRET=demande-cette-valeur-a-l-equipe
```

Les autres valeurs du `.env.example` sont déjà correctes pour l'Option A :
- `NEXT_PUBLIC_API_URL=https://api.mood-iot.fr/api/v1`
- `AUTH_URL=http://localhost:3000`
- `AUTH_TRUST_HOST=true`
- `AUTH_KEYCLOAK_ID=dashboard-medecin`
- `AUTH_KEYCLOAK_ISSUER=https://auth.mood-iot.fr/realms/moodiot`

### Tester
1. Ouvre `http://localhost:3000`.
2. Clique sur **« Se connecter »**.
3. Connecte-toi avec un utilisateur de test (voir [section 7](#7-identifiants-de-test)) :
   `dr.martin@example.test` / `Martin2026!`.

### Éditer
- Édite les fichiers dans `frontend/dashboard/src/...`.
- `npm run dev` **recharge à chaud** automatiquement à l'enregistrement.

---

## 5. 📱 App mobile (patient) — Expo

```bash
cd frontend/mobile
cp .env.example .env.local      # pointe déjà vers le backend déployé, rien à changer
npm install
npx expo start                  # affiche un QR code
```

- Ouvre **Expo Go** sur ton téléphone et **scanne le QR**.
- Le client Keycloak `mobile-app` est **public (PKCE)** → aucun secret à mettre.
- Login de test (patient) : `marie.dupont@example.test` / `Marie2026!`.

> 💡 **Note importante :** Expo Go charge le JavaScript depuis ton PC (il faut être
> sur le même WiFi, ou utiliser `npx expo start --tunnel`). Pour une app qui tourne
> **seule sur le téléphone sans PC**, on génère un **APK** avec EAS
> (`eas build -p android --profile preview`). Les fonctions natives comme
> **Health Connect** et le **push** ne se testent bien que sur l'APK, pas sur Expo Go.

---

## 6. 🐳 Option B — Tout en local avec Docker (avancé)

Seulement si tu as besoin du **backend qui tourne sur ta machine** (par ex. pour
modifier un microservice).

```bash
# Depuis la racine du dépôt :
docker compose up -d            # lance postgres, redis, keycloak et les 7 microservices
docker compose ps               # vérifie que tout est « healthy »
```

Ports locaux (hôte) :

| Service | Port local |
|---|---|
| API Gateway | `8010` |
| Keycloak | `8080` |
| PostgreSQL | `5433` |
| Redis | `6380` |
| auth / patient / scoring / notification / teleconsult / doctor | `8011`–`8016` |

Ensuite, pointe le dashboard vers le backend local : dans
`frontend/dashboard/.env.local`, **commente** la ligne déployée et utilise :
```ini
NEXT_PUBLIC_API_URL=http://localhost:8010/api/v1
AUTH_KEYCLOAK_ISSUER=http://localhost:8080/realms/moodiot
```

> ⚠️ **À propos de la base de données locale :**
> - Si c'est la **première fois** (`docker compose up`), la BD est créée avec le bon
>   schéma mais **vide**. Pour avoir des patients de test, lance le simulateur :
>   `python qa/simulate_patients.py` (voir le script pour les options).
> - Si tu avais un volume **ancien** et que quelque chose casse avec des
>   colonnes/tables nouvelles, **recrée la BD depuis zéro** :
>   ```bash
>   docker compose down -v       # ⚠️ efface les données locales
>   docker compose up -d
>   ```

---

## 7. Identifiants de test

| Rôle | Email | Mot de passe |
|---|---|---|
| Médecin (psychiatre) | `dr.martin@example.test` | `Martin2026!` |
| Patient | `marie.dupont@example.test` | `Marie2026!` |

---

## 8. Lancer les tests de QA (optionnel)

Dans `qa/` il y a des scripts de tests E2E contre le système **déployé** :

```bash
# Tests du dashboard (navigateur, Playwright) :
pip install playwright && playwright install chromium
# PowerShell :
$env:MOODIOT_PASS = "Martin2026!"; python qa/e2e_dashboard.py
# Git Bash :
MOODIOT_PASS='Martin2026!' python qa/e2e_dashboard.py

# Tests des flux médecin (API) :
MOODIOT_PASS='Martin2026!' python qa/e2e_backend.py
```

Le mot de passe est passé par variable d'environnement (jamais écrit dans le code).
La matrice de cas et les preuves vivent sur Google Drive (dossier *QA Evidencias*),
pas dans le dépôt.

---

## 9. Flux Git (important)

- On travaille sur la branche **`audit/modernization`**.
- Il y a **deux remotes** et ils doivent rester **identiques** (homologués) :

```bash
git remote -v
# origin -> CinthyaCBGON/mood-iot
# team   -> saraahsarah-ops/mood-iot

# Avant de commencer à travailler, récupère la dernière version :
git pull team audit/modernization

# En finissant un changement :
git add .
git commit -m "type: description brève"       # types : feat, fix, refactor, docs, test, chore
git push origin audit/modernization
git push team   audit/modernization           # <-- n'oublie pas de pousser sur LES DEUX !
```

> Si tu as un conflit au pull, préviens l'équipe avant de forcer quoi que ce soit.

---

## 10. Erreurs fréquentes et solution

| Symptôme | Cause probable | Solution |
|---|---|---|
| Login redirige vers `0.0.0.0:3000` | `AUTH_URL` / `AUTH_TRUST_HOST` manquants dans `.env.local` | les ajouter (voir section 4) |
| `InvalidEndpoints: ... missing issuer` | `AUTH_KEYCLOAK_ISSUER` manquant | l'ajouter |
| Login donne une erreur de client/secret | `AUTH_KEYCLOAK_SECRET` vide ou incorrect | demande le secret à l'équipe |
| `npm run dev` ne démarre pas | dépendances obsolètes | refais `npm install` |
| (Option B) erreur de colonnes/tables dans le backend | BD locale ancienne sans les migrations | `docker compose down -v && docker compose up -d` (recrée la BD) |
| L'app mobile ne joint pas le backend local | tu as utilisé `localhost` au lieu de l'IP LAN | utilise l'IP de ton PC (`ipconfig`) — voir `frontend/mobile/.env.example` |

> Si l'erreur n'est pas ici : **copie le message d'erreur complet** et partage-le
> avec l'équipe. Ne reviens pas à une version antérieure sans prévenir — la version
> actuelle inclut des corrections importantes (dont un correctif du login du dashboard).

---

## 11. Documentation de l'API

- **Swagger UI** (interactif) : `https://api.mood-iot.fr/docs`
- **OpenAPI JSON** : `https://api.mood-iot.fr/openapi.json`
- En local (Option B), chaque microservice expose sa propre doc sur `/docs`.
