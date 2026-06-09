# Guide pas-à-pas — Déployer Mood-IoT sur Oracle Cloud Always Free

> Objectif : un environnement staging **gratuit pour toujours** sur Oracle
> Cloud, avec `api.mood-iot.fr` (backend) + `auth.mood-iot.fr` (Keycloak) +
> `dashboard.mood-iot.fr` (Vercel) accessibles depuis n'importe où.
>
> **⚠️ Pas de PHI réel ici** — uniquement pour démo, tests, et validation
> end-to-end. Pour des patients FR réels → OVH HDS (cf. `DEPLOY.md`).

---

## Vue d'ensemble

| Composant | Hébergement | Coût |
|---|---|---|
| Backend (7 microservices + Postgres + Redis + Keycloak) | Oracle Cloud VM ARM Ampere A1 | **0 €/mois** |
| Dashboard Next.js | Vercel Hobby | **0 €/mois** |
| Domaine | mood-iot.fr (déjà payé) | — |
| **Total** | | **0 €/mois** |

Temps total estimé : **~1h** (création compte + provision VM + déploiement).

---

## Phase 1 — Compte Oracle Cloud (10-15 min)

### 1.1 S'inscrire

1. Rendez-vous sur <https://www.oracle.com/cloud/free/>
2. Cliquez sur **"Start for free"**
3. Renseignez :
   - **Email professionnel** (créez `ops@mood-iot.fr` si pas déjà fait via Resend / Google Workspace, ou utilisez votre email perso)
   - **Country/Territory** : France
   - **Home Region** : **Germany Central (Frankfurt) — eu-frankfurt-1**
     - ⚠️ **IRREVERSIBLE** — la région ne peut PAS être changée après création. Choisissez bien Frankfurt (plus proche FR + Always Free dispo).

### 1.2 Vérification

- Téléphone : code SMS
- **Carte de crédit** : Oracle prendra une autorisation de **1 €** qui sera remboursée. La carte sert **uniquement à la vérification** : Oracle s'engage à ne pas convertir le tier Always Free en facturé sans confirmation explicite. Pas de chiffre tabou.

### 1.3 Validation

Une fois inscrit, vous arrivez sur **OCI Console** (`cloud.oracle.com`).
Vérifiez en haut à droite que vous êtes dans la **région Frankfurt**.

✅ **Phase 1 OK** → me dites "Oracle prête" et on enchaîne sur la Phase 2.

---

## Phase 2 — Provisionner la VM ARM Ampere (10 min)

### 2.1 Créer une Compute Instance

1. Menu hamburger (☰) en haut à gauche → **Compute → Instances**
2. Bouton **"Create instance"**
3. Renseignez :
   - **Name** : `mood-iot-prod`
   - **Compartment** : laissez le compartment racine
   - **Placement** : laissez le défaut (AD-1)

### 2.2 Image et shape

- **Image** : cliquez sur **"Change image"** → onglet **"Canonical Ubuntu"** → sélectionnez **"Ubuntu 22.04 (Aarch64)"** (ARM)
- **Shape** : cliquez sur **"Change shape"** → onglet **"Ampere"** → sélectionnez **"VM.Standard.A1.Flex"**
  - **OCPUs** : **4**
  - **Memory (GB)** : **24**
  - Vérifiez que **"Always Free-eligible"** est marqué ✅

### 2.3 Networking

- **Primary VNIC** :
  - **VCN** : Create new VCN (acceptez le défaut `vcn-<date>`)
  - **Subnet** : Create new public subnet
  - ✅ **Assign a public IPv4 address** : coché

### 2.4 SSH keys

- **Generate a key pair for me** → cliquez **"Save Private Key"** → enregistrez `ssh-key-mood-iot.key` quelque part SÛR (vous en aurez besoin pour SSH)
  - ⚠️ **Cette clé ne sera plus jamais téléchargeable**. Si perdue : vous devez recréer la VM.

### 2.5 Boot volume

- **Specify a custom boot volume size** : **100** GB (limite Always Free totale = 200 GB, on en garde la moitié au cas où)

### 2.6 Cloud-init (auto-bootstrap)

Tout en bas, **"Show advanced options" → onglet "Management"** :

- **Cloud-init script** : collez le contenu de `infrastructure/oracle/cloud-init.sh` (depuis ce repo)
  - ⚠️ Avant de coller, **éditez la ligne `REPO_URL=`** avec l'URL HTTPS de votre repo GitHub :
    ```bash
    REPO_URL="https://github.com/VOTRE-USERNAME/mood-iot.git"
    ```

### 2.7 Create

- Cliquez **"Create"** en bas
- La VM se provisionne en ~2 min
- Quand status = **"Running"** : notez la **Public IPv4 Address** affichée à droite (vous l'utiliserez pour le DNS et le SSH)

✅ **Phase 2 OK** → me dites "VM en route" + me passez l'IP publique.

---

## Phase 3 — Ouvrir les ports dans le Security List (5 min)

Oracle ferme tous les ports par défaut. Ouvrez 80 + 443.

1. Toujours dans **Compute → Instances**, cliquez sur votre VM `mood-iot-prod`
2. Sous **"Primary VNIC"** → cliquez sur le nom du **Subnet** (lien bleu)
3. Section **"Security Lists"** → cliquez sur **"Default Security List for vcn-…"**
4. **"Add Ingress Rules"** (2 fois) :

**Règle 1 — HTTPS** :
- Source CIDR : `0.0.0.0/0`
- IP Protocol : `TCP`
- Destination Port Range : `443`
- Description : `HTTPS public`

**Règle 2 — HTTP (pour ACME Let's Encrypt)** :
- Source CIDR : `0.0.0.0/0`
- IP Protocol : `TCP`
- Destination Port Range : `80`
- Description : `HTTP (Let's Encrypt ACME)`

Le port 22 (SSH) est déjà ouvert par défaut.

✅ **Phase 3 OK** → ports ouverts côté Oracle. UFW dans la VM les ouvrira aussi (déjà fait par `cloud-init.sh`).

---

## Phase 4 — DNS — pointer mood-iot.fr vers la VM (10 min)

Votre domaine `mood-iot.fr` est chez OVH (ou Cloudflare ?). Créez 3 enregistrements **A** vers l'IP publique Oracle :

| Nom | Type | Valeur | TTL |
|---|---|---|---|
| `api` | A | `<IP_PUBLIQUE_ORACLE>` | 300 |
| `auth` | A | `<IP_PUBLIQUE_ORACLE>` | 300 |
| `dashboard` | CNAME | `cname.vercel-dns.com` | 300 |

> Le `dashboard` pointe vers Vercel — on le configure en Phase 6.

### Si DNS chez OVH

1. <https://www.ovh.com/manager/> → **Web Cloud → Domaines → mood-iot.fr**
2. Onglet **"Zone DNS"** → **"Ajouter une entrée"**

### Si DNS chez Cloudflare

1. <https://dash.cloudflare.com/> → mood-iot.fr → **DNS**
2. **"Add record"** → type A, name = api, IPv4 = IP Oracle, proxy status = **DNS only** (le proxy orange interférerait avec Let's Encrypt en mode HTTP-01)

✅ **Phase 4 OK** → DNS propage en 5-15 min. Testez avec :
```bash
dig +short api.mood-iot.fr
```
Doit retourner votre IP Oracle.

---

## Phase 5 — Première connexion + édition `.env.prod` (15 min)

### 5.1 SSH vers la VM

Sur votre PC (Windows PowerShell ou WSL/Mac/Linux) :

```bash
# Permissions correctes sur la clé (sinon SSH refuse)
chmod 600 ssh-key-mood-iot.key

# Connexion
ssh -i ssh-key-mood-iot.key ubuntu@<IP_PUBLIQUE_ORACLE>
```

Si Windows PowerShell : utilisez **OpenSSH** intégré (préinstallé sur Win10/11) :
```powershell
icacls ssh-key-mood-iot.key /inheritance:r /grant:r "$($env:USERNAME):(R)"
ssh -i ssh-key-mood-iot.key ubuntu@<IP_PUBLIQUE_ORACLE>
```

### 5.2 Vérifier que cloud-init a tourné

```bash
# Vous devez voir Docker installé
docker --version
docker compose version

# Le repo doit être cloné
ls /opt/mood-iot
```

Si cloud-init a planté : `sudo cat /var/log/cloud-init-output.log` pour voir où.

### 5.3 Éditer `.env.prod`

```bash
sudo nano /opt/mood-iot/.env.prod
```

Champs OBLIGATOIRES à remplacer (parmi les `change-me-*`) :

```bash
# Postgres : générez avec : openssl rand -base64 32
POSTGRES_PASSWORD=<32 chars random>
DATABASE_URL=postgresql://mood_user:<même password>@postgres:5432/mood_iot

# JWT inter-services : openssl rand -hex 32
JWT_SECRET_KEY=<32 chars random hex>

# Keycloak
KEYCLOAK_HOSTNAME=auth.mood-iot.fr
KEYCLOAK_ISSUER=https://auth.mood-iot.fr/realms/moodiot
KEYCLOAK_JWKS_URI=http://keycloak:8080/realms/moodiot/protocol/openid-connect/certs
KEYCLOAK_TOKEN_ENDPOINT=http://keycloak:8080/realms/moodiot/protocol/openid-connect/token
KC_BOOTSTRAP_ADMIN_PASSWORD=<mot de passe admin Keycloak fort>

# Chiffrement Fernet
# Générez avec : python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=<clé Fernet>

# Resend (déjà configuré pour mood-iot.fr)
RESEND_API_KEY=<votre clé re_xxx>

# Anthropic Claude Haiku
ANTHROPIC_API_KEY=<votre clé sk-ant-xxx>

# Environnement
ENVIRONMENT=production
LOG_LEVEL=INFO
STRUCTLOG_JSON=true
```

Sauvegardez avec `Ctrl+O`, `Enter`, `Ctrl+X`.

### 5.4 Démarrer la stack

```bash
sudo systemctl start mood-iot
```

Suivez les logs en temps réel :

```bash
cd /opt/mood-iot
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f
```

Au bout de 1-2 min vous devriez voir :
- ✅ Postgres `database system is ready`
- ✅ Redis `Ready to accept connections`
- ✅ Keycloak `Listening on http://0.0.0.0:8080`
- ✅ Caddy `serving initial configuration` + `obtained certificate` (Let's Encrypt)
- ✅ Gateway/Auth/Patient/etc. `Application startup complete`

### 5.5 Smoke test

Depuis votre PC :

```bash
curl https://api.mood-iot.fr/api/v1/health
# → {"status":"healthy",...}

curl https://auth.mood-iot.fr/realms/master/
# → HTML de la page de login Keycloak admin
```

✅ **Phase 5 OK** → backend prod accessible mondialement.

---

## Phase 6 — Dashboard sur Vercel (10 min)

### 6.1 Setup Vercel

1. <https://vercel.com/signup> → connectez-vous avec GitHub
2. **"Add New Project"** → sélectionnez `mood-iot` repo → **"Import"**
3. **Configure** :
   - **Root Directory** : `frontend/dashboard`
   - **Framework Preset** : Next.js (auto-détecté)
   - **Build Command** : laissez le défaut (`next build`)
   - **Output Directory** : laissez le défaut

### 6.2 Variables d'environnement Vercel

Dans la section **"Environment Variables"** du wizard d'import :

| Name | Value |
|---|---|
| `NEXTAUTH_URL` | `https://dashboard.mood-iot.fr` |
| `NEXTAUTH_SECRET` | `<openssl rand -base64 32>` |
| `KEYCLOAK_CLIENT_ID` | `dashboard-medecin` |
| `KEYCLOAK_CLIENT_SECRET` | `<récupérer dans la console Keycloak admin>` |
| `KEYCLOAK_ISSUER` | `https://auth.mood-iot.fr/realms/moodiot` |
| `NEXT_PUBLIC_API_URL` | `https://api.mood-iot.fr/api/v1` |

### 6.3 Deploy + domaine custom

1. **"Deploy"** → 1er deploy ~3 min
2. Une fois live (URL temporaire `mood-iot-XXX.vercel.app`) :
3. **Settings → Domains → Add** → `dashboard.mood-iot.fr`
   - Vercel vous donne un `CNAME` cible — confirmez que celui ajouté en Phase 4 est correct
4. Attendez que Vercel verifie + provisionne le TLS (auto, ~2 min)

✅ **Phase 6 OK** → dashboard accessible sur <https://dashboard.mood-iot.fr>

---

## Phase 7 — APK mobile pointant vers prod (10 min)

Dans `frontend/mobile/eas.json`, mettez à jour le profil `production` :

```json
"production": {
  "autoIncrement": true,
  "env": {
    "EXPO_PUBLIC_API_URL": "https://api.mood-iot.fr/api/v1",
    "EXPO_PUBLIC_KEYCLOAK_DISCOVERY": "https://auth.mood-iot.fr/realms/moodiot/.well-known/openid-configuration",
    "EXPO_PUBLIC_KEYCLOAK_CLIENT_ID": "mobile-app"
  },
  "android": {
    "buildType": "app-bundle"
  }
}
```

Build :

```bash
cd frontend/mobile
eas build -p android --profile production
```

Sortie : un `.aab` à uploader sur Play Console (Internal Testing), ou changez `buildType` à `apk` pour distribuer hors-store.

✅ **Phase 7 OK** → APK production prête.

---

## Maintenance

### Update du code

```bash
ssh -i ssh-key-mood-iot.key ubuntu@<IP>
cd /opt/mood-iot
git pull
sudo systemctl restart mood-iot
```

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f --tail 100 patient-service
```

### Backup Postgres (à mettre en cron weekly)

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U mood_user mood_iot > backup-$(date +%F).sql
```

### Monitoring santé

```bash
# Status tous services
docker compose -f docker-compose.prod.yml ps

# Healthcheck endpoint
curl https://api.mood-iot.fr/api/v1/health | jq
```

---

## Limites de l'environnement Always Free

| Ressource | Limite Always Free |
|---|---|
| OCPU ARM | 4 (total cumulé toutes VMs) |
| Mémoire ARM | 24 GB (total cumulé) |
| Boot volume + Block | 200 GB total |
| Bande passante sortante | 10 TB/mois (plus que suffisant) |
| Object Storage | 20 GB |

Pour 50-100 patients de démo : largement suffisant.

---

## Si quelque chose plante

| Symptôme | Diagnostic | Action |
|---|---|---|
| SSH refused | Security List bloque 22 ou IP changed | Vérifier OCI Console → Networking → Security List |
| `caddy` ne provisionne pas TLS | DNS pas propagé ou port 80 fermé | `dig api.mood-iot.fr` + `curl -v http://api.mood-iot.fr` |
| `keycloak` boucle | KC_HOSTNAME ne match pas le domaine d'accès | Re-vérifier `.env.prod` puis `docker compose restart keycloak` |
| `gateway` retourne 502 | Service backend KO | `docker compose logs <service>` |
| Out of memory | Trop de services en même temps | Désactiver `teleconsult-service` + `doctor-service` si inutiles |

---

*Version du document : 1.0 — 2026-06-08*
