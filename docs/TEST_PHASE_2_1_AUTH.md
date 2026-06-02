# Guide de test — Phase 2.1 : Authentification Keycloak

> Objectif : valider le flux complet d'authentification (Keycloak local +
> backend FastAPI + app mobile Expo) avant de passer à la Phase 2.2.
>
> Temps estimé : **30 à 45 minutes** en suivant la liste de A à Z.

## Pré-requis

À installer / vérifier sur la machine de dev avant de commencer :

- [ ] **Docker Desktop** (WSL2 activé sous Windows) en cours d'exécution
- [ ] **Node.js 22.x** + `npm` (ou `pnpm`)
- [ ] **Android Studio** avec **un AVD (Android Virtual Device) API 34+**
- [ ] Une application TOTP installée sur le téléphone ou en desktop :
      Google Authenticator, 1Password, Bitwarden, ou Authy
- [ ] (Optionnel) Le simulateur iOS si la machine est un Mac

Commandes de vérification :

```bash
docker --version           # Docker version 24+ attendu
node --version             # v22.x attendu
adb devices                # liste les émulateurs Android disponibles
```

---

## Étape 1 — Préparer les variables d'environnement

Depuis la racine du repo :

```bash
cp .env.example .env
```

Éditer le fichier `.env` et compléter au minimum :

```env
# Resend (pour les emails de reset password de Keycloak)
RESEND_API_KEY=re_xxxxxxxxxxxx     # ta clé Resend
SES_FROM_EMAIL=noreply@ton-domaine-de-test.fr

# Anthropic (déjà utilisée par le backend, à conserver)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# Bootstrap Keycloak (mot de passe console admin)
KC_BOOTSTRAP_ADMIN_USERNAME=admin
KC_BOOTSTRAP_ADMIN_PASSWORD=ChangeMe2026!
```

> **Note SMTP** : si tu n'as pas encore validé un domaine chez Resend, mets
> ton domaine de test (ex. `onresend.dev` t'en fournit un). Sinon, le test
> de reset password ne marchera pas mais le reste du flux fonctionnera.

---

## Étape 2 — Lancer la stack locale (Postgres + Redis + Keycloak + backend)

```bash
docker compose up -d postgres redis
```

Attendre 10 secondes puis vérifier que Postgres est sain :

```bash
docker compose ps postgres
# postgres ... healthy
```

Lancer Keycloak :

```bash
docker compose up -d keycloak
# Le premier démarrage prend ~60 secondes (création de tables + import realm)
docker compose logs -f keycloak
# Attendre la ligne : "Keycloak ... started in ..."
# Ctrl+C pour quitter les logs
```

Vérifier que Keycloak répond :

```bash
curl -fsS http://localhost:8080/health/ready
# Doit retourner un JSON avec "status": "UP"
```

Lancer les microservices backend :

```bash
docker compose up -d auth-service patient-service ml-scoring notification-service teleconsult-service doctor-service api-gateway
docker compose ps
# Tous doivent être "running" ou "healthy"
```

Vérifier que le gateway répond :

```bash
curl -fsS http://localhost:8010/api/v1/health
# Doit retourner {"status": "ok", "services": {...}}
```

---

## Étape 3 — Vérifier que le realm Keycloak `moodiot` est bien importé

Ouvrir dans le navigateur : <http://localhost:8080>

- Cliquer sur **Administration Console**
- Login avec `admin` / la valeur de `KC_BOOTSTRAP_ADMIN_PASSWORD`
- En haut à gauche, **changer le realm** de `master` à `moodiot`
- Onglet **Realm settings** : vérifier `Display name = Mood-IoT`, `Frontend URL` vide, `Default locale = fr`
- Onglet **Clients** : tu dois voir `mobile-app`, `dashboard-medecin`, `backend-services`
- Onglet **Realm roles** : tu dois voir `patient`, `psychiatre`, `admin`
- Onglet **Authentication → Required actions** : `Configure OTP` doit être enabled

✅ Si tout y est, le realm est bien importé.

---

## Étape 4 — Créer un utilisateur patient de test

Toujours dans la console Keycloak, realm `moodiot` :

1. **Users → Add user**
   - Username : `marie.dupont@example.test` (laisser le champ comme l'email)
   - Email : `marie.dupont@example.test`
   - First name : `Marie`
   - Last name : `Dupont`
   - Email verified : **ON** (sinon il faudra valider par email avant le 1er login)
   - **Create**
2. Onglet **Credentials** de cet utilisateur :
   - **Set password** : `Patient2026!` (mdp respectant la policy)
   - Temporary : **OFF**
   - **Save**
3. Onglet **Role mapping** de cet utilisateur :
   - **Assign role** → cocher `patient` → **Assign**

✅ L'utilisateur `marie.dupont@example.test` peut maintenant se connecter.

---

## Étape 5 — Tester le flux backend avec curl

Récupérer un access token via le Resource Owner Password Grant
(uniquement pour le test, en prod le mobile passe par PKCE) :

```bash
curl -X POST "http://localhost:8080/realms/moodiot/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mobile-app" \
  -d "username=marie.dupont@example.test" \
  -d "password=Patient2026!" \
  -d "scope=openid profile email"
```

> **Si tu reçois `unauthorized_client`** : il faut activer `Direct access grants`
> sur le client `mobile-app` côté console Keycloak (Clients → mobile-app →
> Settings → Direct access grants enabled = ON). On désactivera ça en prod.

Récupérer `access_token` depuis la réponse JSON, puis :

```bash
ACCESS_TOKEN="..."  # le coller ici

# Test 1 : /auth/me doit retourner 404 (profil pas encore créé)
curl -fsS -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8010/api/v1/auth/me
# Attendu : 404 avec detail "Profil utilisateur introuvable..."

# Test 2 : créer le profil interne
curl -fsS -X POST -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"patient","first_name":"Marie","last_name":"Dupont","gender":"F"}' \
  http://localhost:8010/api/v1/auth/register-profile
# Attendu : 201 avec le profil créé (id UUID + keycloak_id + role=patient)

# Test 3 : /auth/me doit maintenant marcher
curl -fsS -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8010/api/v1/auth/me
# Attendu : 200 avec le profil
```

✅ Si les 3 appels marchent, le backend est OK.

---

## Étape 6 — Lancer l'app mobile Expo

Dans un nouveau terminal :

```bash
cd frontend/mobile
npm install
```

Configurer l'URL du backend pour que l'émulateur Android puisse atteindre
ta machine hôte. Créer `frontend/mobile/.env.local` :

```env
# 10.0.2.2 = adresse de l'hôte vu depuis l'émulateur Android
EXPO_PUBLIC_API_URL=http://10.0.2.2:8010/api/v1
EXPO_PUBLIC_KEYCLOAK_DISCOVERY=http://10.0.2.2:8080/realms/moodiot/.well-known/openid-configuration
EXPO_PUBLIC_KEYCLOAK_CLIENT_ID=mobile-app
```

> **Pour le simulateur iOS** : remplacer `10.0.2.2` par `localhost`.

Démarrer Expo et l'émulateur Android (ouvrir AVD Manager d'Android Studio
au préalable et lancer un émulateur) :

```bash
npm run android
# ou : npx expo start, puis presser `a`
```

---

## Étape 7 — Test du flux UI complet

Sur l'émulateur, dans l'app Mood-IoT Patient :

### A. Login email/password

1. L'écran de connexion s'affiche avec le bouton **Se connecter**
2. Appuyer dessus → un navigateur in-app s'ouvre sur la page Keycloak
3. Saisir `marie.dupont@example.test` / `Patient2026!` → **Sign In**
4. Au premier login Keycloak demande d'**activer Configure OTP** :
   - Scanner le QR code avec ton app TOTP (Google Authenticator / 1Password)
   - Saisir le code à 6 chiffres
   - **Submit**
5. Le navigateur se ferme, retour dans l'app
6. **Écran Welcome FR** : remplir Prénom = `Marie`, Nom = `Dupont`, sélectionner Genre = `Femme`
7. **Créer mon profil** → redirection vers les onglets (Accueil)

✅ Si tu arrives à l'écran d'accueil, le flux complet marche.

### B. Vérifier la persistance / refresh token

1. Tuer l'app (swipe up dans les apps récentes)
2. Relancer l'app
3. Attendu : tu arrives **directement sur l'Accueil** sans repasser par login

### C. Test du refresh transparent

Forcer l'expiration en attendant 5 min (TTL access token configuré dans le
realm `accessTokenLifespan: 300`). Tirer pour rafraîchir l'écran ou
naviguer entre onglets. Attendu : aucune erreur 401, l'app rafraîchit
silencieusement.

### D. Test logout

1. Onglet **Réglages** → bas de page → **Se déconnecter**
2. Confirmer
3. Attendu : retour à l'écran de login

### E. Test MFA TOTP au 2ᵉ login

1. Refaire un login (Se connecter)
2. Après email/password, Keycloak demande le **code OTP**
3. Saisir le code de ton app TOTP
4. Attendu : login OK

### F. (Optionnel) Test reset password

1. Sur la page Keycloak, cliquer **Forgot Password?**
2. Saisir l'email → **Submit**
3. Si SMTP Resend configuré : tu reçois un email FR avec un lien
4. Cliquer le lien, définir un nouveau mot de passe

---

## Étape 8 — Lancer les tests unitaires backend

```bash
docker compose exec auth-service pytest tests/test_keycloak_auth.py -v
# Attendu : 7 tests passent
```

Ou en local sans Docker :

```bash
cd backend
pip install -r requirements.txt
pytest tests/test_keycloak_auth.py -v
```

---

## Résolution des problèmes courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| `docker compose up keycloak` échoue, schema `keycloak` introuvable | Le volume `pgdata` contient une vieille base sans le schéma | `docker compose down -v` puis recommencer |
| L'app Expo n'arrive pas à joindre Keycloak (`Network request failed`) | Mauvaise IP dans `EXPO_PUBLIC_KEYCLOAK_DISCOVERY` | Vérifier `10.0.2.2` pour Android emulator, `localhost` pour iOS sim |
| Keycloak login renvoie sur une URL `mood-iot://callback` qui ne s'ouvre pas | Le scheme deep link n'est pas reconnu par l'OS | Rebuild dev client avec `npx expo prebuild --clean` |
| `/auth/me` retourne 401 alors que le token semble OK | `KEYCLOAK_ISSUER` mal configuré côté backend | Doit valoir exactement `http://keycloak:8080/realms/moodiot` (pas `localhost`) en Docker |
| Bouton **Se connecter** ne fait rien | `expo-web-browser` pas dans les plugins | Confirmer la présence dans `app.json` puis `npx expo install --check` |

---

## Critères de réussite Phase 2.1

À cocher avant de passer à Phase 2.2 :

- [ ] `docker compose up` démarre tous les services sans erreur
- [ ] Realm `moodiot` importé avec ses 3 clients et 3 rôles
- [ ] `curl /api/v1/auth/me` avec un token Keycloak retourne 200 (après register-profile)
- [ ] L'app mobile ouvre la hosted UI Keycloak via OIDC PKCE
- [ ] Login email/password fonctionne
- [ ] Enrôlement TOTP MFA marche au 1er login
- [ ] Écran Welcome FR s'affiche et crée le profil interne
- [ ] Persistance OK après kill + relaunch de l'app
- [ ] Logout révoque la session
- [ ] Les 7 tests pytest `test_keycloak_auth.py` passent

---

## Ce qui n'est PAS encore testable et pourquoi

- ❌ **Google Sign-In** : il faut créer un client OAuth dans Google Cloud
  Console et brancher l'Identity Provider côté Keycloak. À faire dans la
  Phase 2.8 (deploy) quand on aura un domaine `auth.moodiot.fr`.
- ❌ **Apple Sign-In** : nécessite un compte Apple Developer ($99/an) et
  une Service ID. À faire idem en Phase 2.8.
- ❌ **Reset password email FR réel** : marche si tu as une clé Resend et
  un domaine vérifié. Sinon le mail est rejeté par Resend.

Tout ça est **non bloquant pour Phase 2.2** — on continuera avec les autres
features et on branchera les IdPs sociaux en prod.
