# Guide pas-à-pas — Déployer Mood-IoT sur Hetzner Cloud

> **Coût** : **€4,51/mois** (CX22 — 2 vCPU x86, 4 GB RAM, 40 GB NVMe).
> **Annulable à tout moment**, facturation à l'heure.
>
> **⚠️ Pas de PHI réel ici** — uniquement staging / démo / validation.
> Pour des patients FR réels → OVH HDS (cf. [`DEPLOY.md`](./DEPLOY.md)).

---

## Vue d'ensemble

| Composant | Hébergement | Coût |
|---|---|---|
| Backend (7 microservices + Postgres + Redis + Keycloak + Caddy) | Hetzner Cloud CX22 | **€4,51/mois** |
| Dashboard Next.js | Vercel Hobby | 0 € |
| Domaine | mood-iot.fr (déjà payé chez OVH) | — |
| **Total** | | **€4,51/mois** |

Temps total estimé : **~45 min** (compte + provision + bootstrap + DNS).

---

## Pourquoi Hetzner et pas Oracle / DigitalOcean / Render

- **Cartes de crédit acceptées sans drame** (contrairement à Oracle qui rejette systématiquement)
- **Datacenter européen** (Falkenstein DE ou Helsinki FI) → latence < 30 ms depuis la France
- **GDPR-friendly** (DPA disponible côté Hetzner, important même pour staging)
- **Facturation à l'heure** : si tu testes 3h → tu paies €0,007. Si tu laisses 1 mois → €4,51 plafond.
- **Annulation 1-clic** : supprimes le serveur → fin de la facturation

---

## Phase 1 — Compte Hetzner Cloud (5-10 min)

### 1.1 Inscription

1. Rends-toi sur <https://accounts.hetzner.com/signUp>
2. Renseigne :
   - Email + mot de passe
   - Nom, adresse, pays (France)
   - **Téléphone** (vérification SMS)
3. Confirme l'email reçu

### 1.2 Méthode de paiement

1. Une fois connecté, vas dans **"Hetzner Cloud Console"** : <https://console.hetzner.cloud>
2. **Settings → Billing → Add payment method**
3. **Carte de crédit** (Visa/Mastercard acceptées) ou **PayPal**
4. ⚠️ Hetzner peut demander un **dépôt initial de €20** pour les nouveaux comptes (anti-fraude) → ce dépôt sert de pré-paiement, **il sera consommé** au fur et à mesure de ta facturation. Tu ne perds rien.

✅ **Phase 1 OK** → tu vois "Payment method verified" dans Settings.

---

## Phase 2 — Créer le projet + le serveur (10 min)

### 2.1 Nouveau projet

1. **Cloud Console** → en haut à droite : `+ Add Project`
2. Nom : `mood-iot`
3. Click **Create**

### 2.2 Ajouter une SSH key (recommandé, évite mot de passe par email)

1. Dans le projet → **Security → SSH Keys → Add SSH Key**
2. Sur ta PC, génère une clé si tu n'en as pas :
   ```powershell
   # PowerShell Windows
   ssh-keygen -t ed25519 -C "hetzner-mood-iot" -f $env:USERPROFILE\.ssh\hetzner_mood_iot
   ```
3. Affiche la clé publique :
   ```powershell
   Get-Content $env:USERPROFILE\.ssh\hetzner_mood_iot.pub
   ```
4. Copie tout le contenu (commence par `ssh-ed25519 ...`)
5. Colle-le dans Hetzner → **Name : `cinthya-pc`** → **Add SSH Key**

### 2.3 Créer le serveur

1. **Servers → Add Server**
2. Renseigne :
   - **Location** : **Falkenstein (fsn1)** ou **Helsinki (hel1)** — peu importe lequel, latence similaire depuis FR
   - **Image** : **Ubuntu 22.04**
   - **Type** : onglet **"Shared vCPU" → "x86 (Intel/AMD)" → CX22**
     - 2 vCPU, 4 GB RAM, 40 GB NVMe
     - **€4,51/mois (€0,007/heure)** ✅
   - **Networking** : laisse IPv4 + IPv6 cochés (par défaut)
   - **SSH Keys** : sélectionne `cinthya-pc` (créée en 2.2)
   - **Volumes / Firewalls / Backups** : ignore pour l'instant
   - **Cloud config (user data)** : section dépliante en bas. Colle le contenu de [`infrastructure/cloud-init.sh`](./infrastructure/cloud-init.sh) **après avoir modifié la ligne `REPO_URL`** avec l'URL HTTPS de ton repo GitHub :
     ```bash
     REPO_URL="https://github.com/TON-USERNAME/mood-iot.git"
     ```
     > Le script détecte automatiquement Hetzner (pas de user `ubuntu` par défaut) et crée un user `mood` avec sudo + SSH keys héritées de root.
   - **Name** : `mood-iot-prod`
3. Click **Create & Buy now** (vérifie qu'il indique bien €4,51/mois)

### 2.4 Récupérer l'IP du serveur

Une fois créé (30 secondes), le serveur apparaît dans la liste avec une **IPv4 publique** type `5.75.xxx.xxx`. Note-la, tu l'utiliseras pour le DNS et le SSH.

✅ **Phase 2 OK** → serveur `mood-iot-prod` actif avec une IP publique.

---

## Phase 3 — Configurer le DNS chez OVH (10 min)

Ton domaine `mood-iot.fr` est chez OVH. Ajoute 3 enregistrements **A** pointant vers l'IP Hetzner.

1. Vas sur <https://www.ovh.com/manager/> → **Web Cloud → Domaines → mood-iot.fr**
2. Onglet **"Zone DNS"**
3. **"Ajouter une entrée"** (3 fois) :

| Sous-domaine | Type | Cible | TTL |
|---|---|---|---|
| `api` | A | `<IP_HETZNER>` | 300 |
| `auth` | A | `<IP_HETZNER>` | 300 |
| `dashboard` | CNAME | `cname.vercel-dns.com` | 300 |

> Le `dashboard` pointe vers Vercel — on le configure en Phase 6.

4. Valide chaque entrée

### Vérifier la propagation

```bash
# Sur ta PC (PowerShell ou WSL)
nslookup api.mood-iot.fr
```

Doit retourner l'IP Hetzner. Si ça retourne autre chose ou rien, attends 5-15 min de propagation DNS.

✅ **Phase 3 OK** → DNS pointe vers Hetzner.

---

## Phase 4 — Première connexion SSH + `.env.prod` (15 min)

### 4.1 SSH vers le serveur

```powershell
# PowerShell Windows — connexion initiale en root
ssh -i $env:USERPROFILE\.ssh\hetzner_mood_iot root@<IP_HETZNER>
```

Si c'est la première connexion : `yes` pour accepter le fingerprint.

> Le `cloud-init.sh` a créé un user `mood` avec sudo et héritage des SSH keys.
> Une fois que tu as vérifié que tout fonctionne en root, tu peux te reconnecter en `mood@<IP>` pour les opérations courantes — c'est plus propre.

### 4.2 Vérifier que cloud-init a tourné

```bash
# Tu dois voir Docker installé
docker --version
docker compose version

# Le repo doit être cloné
ls /opt/mood-iot

# Suivre les logs de cloud-init s'il y a eu un souci
tail -100 /var/log/cloud-init-output.log
```

Si quelque chose a planté, dis-moi quel message d'erreur tu vois.

### 4.3 Éditer `.env.prod` avec les secrets

```bash
sudo nano /opt/mood-iot/.env.prod
```

Champs OBLIGATOIRES à remplacer (parmi tous les `change-me-*`) :

```bash
# Postgres — génère avec : openssl rand -base64 32
POSTGRES_PASSWORD=<32 chars random>
DATABASE_URL=postgresql://mood_user:<même password>@postgres:5432/mood_iot

# JWT inter-services — openssl rand -hex 32
JWT_SECRET_KEY=<32 chars random hex>

# Keycloak
KEYCLOAK_HOSTNAME=auth.mood-iot.fr
KEYCLOAK_ISSUER=https://auth.mood-iot.fr/realms/moodiot
KEYCLOAK_JWKS_URI=http://keycloak:8080/realms/moodiot/protocol/openid-connect/certs
KEYCLOAK_TOKEN_ENDPOINT=http://keycloak:8080/realms/moodiot/protocol/openid-connect/token
KC_BOOTSTRAP_ADMIN_USERNAME=admin
KC_BOOTSTRAP_ADMIN_PASSWORD=<mot de passe admin fort>

# Chiffrement Fernet — sur ta PC :
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=<clé Fernet base64>

# Resend (déjà configuré côté domaine mood-iot.fr)
RESEND_API_KEY=re_<ta clé existante>

# Anthropic Claude Haiku
ANTHROPIC_API_KEY=sk-ant-<ta clé>

# Environnement
ENVIRONMENT=production
LOG_LEVEL=INFO
STRUCTLOG_JSON=true
```

Sauvegarde avec `Ctrl+O`, `Enter`, `Ctrl+X`.

### 4.4 Démarrer la stack

```bash
sudo systemctl start mood-iot
```

Suis les logs en temps réel :

```bash
cd /opt/mood-iot
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f --tail 50
```

Au bout de 2-3 min, tu dois voir :
- ✅ `postgres` : `database system is ready to accept connections`
- ✅ `redis` : `Ready to accept connections`
- ✅ `keycloak` : `Listening on http://0.0.0.0:8080`
- ✅ `caddy` : `obtained certificate` (Let's Encrypt OK)
- ✅ `gateway-service`, `auth-service`, etc. : `Application startup complete`

`Ctrl+C` pour sortir des logs (les containers continuent de tourner).

### 4.5 Smoke test depuis ta PC

```bash
# Backend
curl https://api.mood-iot.fr/api/v1/health
# Doit retourner : {"status":"healthy",...}

# Keycloak
curl -I https://auth.mood-iot.fr/realms/master/
# Doit retourner : HTTP/2 200
```

✅ **Phase 4 OK** → backend accessible publiquement avec TLS Let's Encrypt valide.

---

## Phase 5 — Initialiser Keycloak (10 min)

Le realm `moodiot` n'existe pas encore — il faut l'importer.

### 5.1 Accéder à la console admin

1. Ouvre <https://auth.mood-iot.fr/admin> dans ton navigateur
2. Login avec `admin` + le `KC_BOOTSTRAP_ADMIN_PASSWORD` que tu as défini

### 5.2 Importer le realm

1. Top-left : dropdown du realm → **"Create Realm"**
2. **Resource file → Browse** → sélectionne `infrastructure/keycloak/realm-moodiot.json` (depuis ton repo local)
3. **Create**

> En prod le realm est importé automatiquement au boot via `start --import-realm`
> (le fichier est monté dans le conteneur). L'import manuel ci-dessus n'est utile
> que pour un Keycloak géré hors compose.

### 5.3 ⚠️ OBLIGATOIRE — Régénérer les secrets des clients

Le `realm-moodiot.json` contient des secrets **placeholder** publics
(`"secret": "REPLACE_ME_..."`). Si tu ne les régénères pas, le secret OAuth de
production est un string connu de quiconque lit le dépôt. Pour chaque client
confidentiel (`dashboard-medecin`, `backend-services`) :

1. Realm `moodiot` → **Clients → `dashboard-medecin` → Credentials → Regenerate**
2. Copie le nouveau secret dans `/opt/mood-iot/.env.prod` :
   - `dashboard-medecin`  → `AUTH_KEYCLOAK_SECRET=...`
   - `backend-services`   → `KEYCLOAK_ADMIN_CLIENT_SECRET=...`
3. Recharge les conteneurs concernés (⚠️ `up -d`, pas `restart`, pour relire le
   fichier d'env) :

```bash
cd /opt/mood-iot
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d \
  dashboard gateway-service auth-service patient-service ml-scoring \
  notification-service doctor-service teleconsult-service
```

> Vérif : `client_credentials` avec `backend-services` doit renvoyer un
> `access_token` (secret valide). Régénérer un secret n'invalide PAS les
> sessions en cours.

### 5.4 Créer le user de test Marie

1. Realm `moodiot` → **Users → Add user**
   - Username : `marie.dupont@example.test`
   - Email verified : ON
2. **Save → Credentials → Set password**
   - Password : `Marie2026!`
   - Temporary : OFF
3. **Role Mapping → Assign role** → `patient`

✅ **Phase 5 OK** → Keycloak prêt à recevoir des logins.

---

## Phase 6 — Dashboard médecin sur Hetzner (PAS Vercel)

Pour la cohérence de souveraineté RGPD, le dashboard est hébergé sur le **même
serveur Hetzner** (et non sur Vercel/USA). C'est un service du
`docker-compose.prod.yml` (`dashboard`, Next.js standalone) servi par Caddy sur
`dashboard.mood-iot.fr`.

1. DNS : enregistrement A `dashboard.mood-iot.fr` → IP du serveur (chez OVH).
2. Variables d'env dans `/opt/mood-iot/.env.prod` (NextAuth v5 — noms `AUTH_*`,
   pas les anciens `NEXTAUTH_*`) :

| Clé (.env.prod) | Valeur |
|---|---|
| `AUTH_SECRET` | `<openssl rand -base64 32>` |
| `AUTH_KEYCLOAK_SECRET` | secret régénéré du client `dashboard-medecin` (cf. Phase 5.3) |

> `AUTH_KEYCLOAK_ID`, `AUTH_KEYCLOAK_ISSUER`, `AUTH_URL`, `AUTH_TRUST_HOST` et
> `NEXT_PUBLIC_API_URL` sont déjà fixés dans le service `dashboard` du
> `docker-compose.prod.yml` (pas besoin de les mettre dans `.env.prod`).

3. Build + démarrage :

```bash
cd /opt/mood-iot
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build dashboard
```

4. Caddy expose déjà `dashboard.mood-iot.fr`. **Après tout ajout de domaine au
   Caddyfile, `restart` le conteneur caddy** (un `reload` ne suffit pas) pour
   qu'il émette le certificat Let's Encrypt :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy
```

> **Dev d'équipe** : pour lancer le dashboard en local (`npm run dev`) contre ce
> backend déployé, `ALLOWED_ORIGINS` dans `.env.prod` doit inclure
> `http://localhost:3000` (en plus de `https://dashboard.mood-iot.fr`). À
> retirer avant la mise en production avec de vrais patients. Voir
> `frontend/dashboard/.env.example`.

✅ **Phase 6 OK** → dashboard sur <https://dashboard.mood-iot.fr>

---

## Phase 7 — APK production pointant vers prod (10 min + 15 min de build EAS)

Je m'occupe de cette phase. Mets à jour `eas.json` :

```json
"production": {
  "autoIncrement": true,
  "env": {
    "EXPO_PUBLIC_API_URL": "https://api.mood-iot.fr/api/v1",
    "EXPO_PUBLIC_KEYCLOAK_DISCOVERY": "https://auth.mood-iot.fr/realms/moodiot/.well-known/openid-configuration",
    "EXPO_PUBLIC_KEYCLOAK_CLIENT_ID": "mobile-app"
  },
  "android": {
    "buildType": "apk"
  }
}
```

Build :
```bash
cd frontend/mobile
eas build -p android --profile production
```

15 min plus tard, tu télécharges le APK depuis le lien EAS et tu installes sur ton téléphone.

✅ **Phase 7 OK** → APK prod prête, accessible depuis n'importe quelle connexion (4G, WiFi café, etc.).

---

## Coût mensuel total

| Service | €/mois |
|---|---|
| Hetzner CX22 | 4,51 |
| Vercel Hobby | 0,00 |
| Resend (10 000 emails/mois free) | 0,00 |
| Anthropic Claude Haiku 4.5 (~50 coachings/mois) | ~1,00 |
| Twilio SMS (~20 rappels/mois) | ~0,40 |
| **Total** | **~6 €/mois** |

Pour un staging / démo / pilote → 4 cafés/mois.

---

## Maintenance

### Mettre à jour le code

```bash
ssh -i $env:USERPROFILE\.ssh\hetzner_mood_iot root@<IP>
cd /opt/mood-iot
git pull
sudo systemctl restart mood-iot
```

### Voir les logs

```bash
docker compose -f docker-compose.prod.yml logs -f --tail 100 patient-service
```

### Backup Postgres (à mettre en cron)

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U mood_user mood_iot > backup-$(date +%F).sql
```

### Monitoring santé

```bash
docker compose -f docker-compose.prod.yml ps
curl https://api.mood-iot.fr/api/v1/health | jq
```

---

## Annuler / migrer plus tard

### Annuler Hetzner (anytime)

1. Cloud Console → ton projet → ton serveur
2. **Delete** → confirmation → fin de la facturation IMMÉDIATE
3. Hetzner ne facture que les heures utilisées

### Migrer vers DigitalOcean (quand le GitHub Student Pack arrive)

1. Crée le Droplet DigitalOcean avec le même `cloud-init.sh`
2. Mets à jour les DNS A records OVH vers la nouvelle IP
3. Restaure le dump Postgres
4. Delete le serveur Hetzner

Aucun rebuild d'APK nécessaire — les URLs `api.mood-iot.fr` + `auth.mood-iot.fr` ne changent pas.

---

## Si ça plante

| Symptôme | Action |
|---|---|
| SSH refused | Vérifier IP correcte + SSH key chargée. `ssh -v` pour debug verbose |
| `caddy` n'obtient pas TLS | DNS pas propagé ou port 80/443 bloqué. `dig api.mood-iot.fr` + `curl -v http://api.mood-iot.fr` |
| `keycloak` boucle | KC_HOSTNAME ne matche pas le domaine. Re-éditer `.env.prod` + `docker compose restart keycloak` |
| `gateway` 502 | Service backend KO. `docker compose logs <service>` |
| Out of memory | 4 GB c'est la limite — désactive `teleconsult-service` + `doctor-service` si inutiles dans `docker-compose.prod.yml` |

---

*Version du document : 1.0 — 2026-06-08*
