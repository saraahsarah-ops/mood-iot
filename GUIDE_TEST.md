# Mood-IoT — Guide de tests et validation

## Prerequis

- Docker Desktop installe et lance
- Git Bash ou terminal compatible
- Ports libres : 4566, 5433, 6380, 8010-8015

---

## 1. Lancement de l'infrastructure

```bash
cd mood-iot

# Construire et lancer tous les services
docker compose up --build -d

# Verifier que tous les containers sont "healthy" / "running"
docker compose ps
```

**Resultat attendu :** 9 containers (postgres, redis, api-gateway, auth-service, patient-service, ml-scoring, notification-service, teleconsult-service, localstack) tous en etat "Up".

```bash
# Verifier les logs pour erreurs de demarrage
docker compose logs --tail=20 auth-service
docker compose logs --tail=20 patient-service
docker compose logs --tail=20 ml-scoring
docker compose logs --tail=20 api-gateway
```

---

## 2. Verification de la base de donnees

```bash
# Se connecter a PostgreSQL
docker exec -it mood-iot-postgres psql -U mood_user -d mood_iot

# Dans psql :
\dt                          -- Lister les 17 tables
SELECT count(*) FROM users;  -- Doit retourner 5 (1 medecin + 4 patientes)
SELECT email, role FROM users;
SELECT first_name, last_name, diagnosis FROM patients;
SELECT * FROM model_versions;
\q
```

**Resultat attendu :**
- 17 tables creees (zones 1-4)
- 5 users (dr.martin + 4 patientes)
- 4 patients avec diagnostics
- 1 model_version active (v1.0.0)

---

## 3. Tests des Health Checks

```bash
# Gateway
curl http://localhost:8010/api/v1/health

# Services individuels
curl http://localhost:8011/auth/health
curl http://localhost:8012/patients/health
curl http://localhost:8013/scoring/health
curl http://localhost:8014/notifications/health
curl http://localhost:8015/teleconsult/health
```

**Resultat attendu :** Chaque endpoint retourne `{"status": "healthy", "service": "..."}`.

---

## 4. Tests du Service Auth (port 8001)

### 4.1 Login avec le medecin seed

```bash
# Login du Dr. Martin (mot de passe : MoodIoT2026!)
curl -X POST http://localhost:8011/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dr.martin@mood-iot.fr", "password": "MoodIoT2026!"}'
```

**Resultat attendu :** JSON avec `access_token`, `refresh_token`, `user.role = "psychiatre"`.

> **IMPORTANT :** Copiez le `access_token` retourne. On l'utilisera comme `$TOKEN_DOC` dans la suite.

### 4.2 Login d'une patiente

```bash
curl -X POST http://localhost:8011/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "sophie.dupont@email.fr", "password": "MoodIoT2026!"}'
```

**Resultat attendu :** `access_token` avec `user.role = "patient"`, `first_name = "Sophie"`.

> Copiez le `access_token` comme `$TOKEN_SOPHIE`.

### 4.3 Enregistrement d'un nouvel utilisateur

```bash
curl -X POST http://localhost:8011/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@mood-iot.fr",
    "password": "TestPass2026!",
    "role": "patient",
    "first_name": "Test",
    "last_name": "User"
  }'
```

**Resultat attendu :** HTTP 201 avec id, email, role.

### 4.4 Acces protege (/auth/me)

```bash
# Avec token valide
curl http://localhost:8011/auth/me \
  -H "Authorization: Bearer $TOKEN_DOC"

# Sans token (doit echouer)
curl http://localhost:8011/auth/me
```

**Resultat attendu :** 200 avec info user / 403 sans token.

### 4.5 Refresh token

```bash
curl -X POST http://localhost:8011/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "COLLER_LE_REFRESH_TOKEN_ICI"}'
```

---

## 5. Tests du Service Patient (port 8002)

### 5.1 Lister les patients (psychiatre uniquement)

```bash
curl http://localhost:8012/patients \
  -H "Authorization: Bearer $TOKEN_DOC"
```

**Resultat attendu :** Liste de 4 patientes (Sophie, Marie, Lea, Anna).

> **Note :** Ce service utilise encore un stockage in-memory. Les patients du seed SQL ne sont PAS dans le store in-memory. Pour tester, il faut d'abord creer un patient via POST.

### 5.2 Creer un patient

```bash
curl -X POST http://localhost:8012/patients \
  -H "Authorization: Bearer $TOKEN_DOC" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Claire",
    "last_name": "Petit",
    "date_of_birth": "1993-05-12",
    "gender": "female"
  }'
```

### 5.3 Soumettre une entree d'humeur (PHQ-9)

```bash
curl -X POST http://localhost:8012/patients/{PATIENT_ID}/mood \
  -H "Authorization: Bearer $TOKEN_DOC" \
  -H "Content-Type: application/json" \
  -d '{
    "phq9_scores": [2, 1, 3, 2, 1, 2, 1, 0, 1],
    "notes": "Sommeil perturbe cette semaine",
    "sleep_hours": 5.5
  }'
```

**Resultat attendu :** `phq9_total = 13`, `severity = "moderate"`.

### 5.4 Sync Health Data (Health Connect)

```bash
curl -X POST http://localhost:8012/patients/{PATIENT_ID}/health-data \
  -H "Authorization: Bearer $TOKEN_SOPHIE" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-04-12",
    "heart_rate_avg": 85.5,
    "heart_rate_variability": 32.0,
    "sleep_duration_min": 320,
    "step_count": 4200,
    "screen_time_min": 180,
    "source_platform": "android_health_connect"
  }'
```

### 5.5 Batch Health Data Sync

```bash
curl -X POST http://localhost:8012/patients/{PATIENT_ID}/health-data/batch \
  -H "Authorization: Bearer $TOKEN_SOPHIE" \
  -H "Content-Type: application/json" \
  -d '[
    {"date": "2026-04-10", "heart_rate_avg": 78, "step_count": 6200, "sleep_duration_min": 420, "source_platform": "android_health_connect"},
    {"date": "2026-04-11", "heart_rate_avg": 82, "step_count": 5100, "sleep_duration_min": 380, "source_platform": "android_health_connect"}
  ]'
```

---

## 6. Tests du Gateway (port 8000)

Le gateway proxifie toutes les requetes vers les microservices.

```bash
# Via gateway au lieu d'acceder au service directement
curl -X POST http://localhost:8010/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dr.martin@mood-iot.fr", "password": "MoodIoT2026!"}'
```

**Resultat attendu :** Meme reponse que l'appel direct au port 8001.

---

## 7. Tests du Service Scoring (port 8003)

### 7.1 Calculer un score

```bash
curl -X POST http://localhost:8013/scoring/compute/{PATIENT_UUID} \
  -H "Authorization: Bearer $TOKEN_DOC"
```

> **Note :** Necessite des `daily_aggregates` en base pour fonctionner. Si aucune donnee n'existe, le pipeline retournera une erreur ou un score par defaut.

### 7.2 Historique des scores

```bash
curl "http://localhost:8013/scoring/history/{PATIENT_UUID}?from_date=2026-04-01&to_date=2026-04-12" \
  -H "Authorization: Bearer $TOKEN_DOC"
```

---

## 8. Tests du Service Notification (port 8004)

### 8.1 Envoyer une notification

```bash
curl -X POST http://localhost:8014/notifications/send \
  -H "Authorization: Bearer $TOKEN_DOC" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PATIENT_UUID",
    "type": "coaching_ia",
    "level": 1,
    "channel": "websocket",
    "title": "Conseil du jour",
    "body": "Essayez une promenade de 15 minutes."
  }'
```

### 8.2 WebSocket temps reel

```bash
# Utiliser wscat (npm install -g wscat)
wscat -c ws://localhost:8004/notifications/ws/USER_UUID
```

---

## 9. Tests du Service Teleconsult (port 8005)

### 9.1 Creer une session

```bash
curl -X POST http://localhost:8015/teleconsult/sessions \
  -H "Authorization: Bearer $TOKEN_DOC" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PATIENT_UUID",
    "psychiatre_id": "a0000000-0000-0000-0000-000000000001",
    "scheduled_at": "2026-04-12T14:00:00Z",
    "duration_minutes": 30,
    "reason": "Suivi hebdomadaire"
  }'
```

### 9.2 Rejoindre une session

```bash
curl -X POST http://localhost:8015/teleconsult/sessions/{SESSION_ID}/join \
  -H "Authorization: Bearer $TOKEN_DOC"
```

**Resultat attendu :** URL Jitsi Meet retournee.

---

## 10. Tests du Frontend Dashboard (Next.js)

```bash
cd frontend/dashboard
npm install
npm run dev
# Ouvrir http://localhost:3000
```

**Verifier :**
- [ ] Sidebar avec 4 onglets de navigation
- [ ] Page d'accueil avec 4 KPI cards
- [ ] Liste des patientes triee par score
- [ ] Graphique d'evolution sur 21 jours
- [ ] Page "Fiche patiente" avec metriques vs baseline
- [ ] Page "Notifications" avec bouton "tout marquer comme lu"
- [ ] Page "Messagerie" avec messages rapides et saisie libre

---

## 11. Verification de l'integrite du projet

```bash
# Aucune trace de MQTT
grep -r "mqtt\|mosquitto\|paho" backend/ --include="*.py" --include="*.yml" --include="*.txt"

# Validation XML des diagrammes
for f in *.drawio; do python -c "import xml.etree.ElementTree; xml.etree.ElementTree.parse('$f')" && echo "$f OK"; done

# Docker compose valide
docker compose config --quiet && echo "docker-compose.yml OK"
```

---

## 12. UUIDs de reference (seed data)

| Entite | UUID | Email |
|--------|------|-------|
| Dr. Martin (psychiatre) | `a0000000-0000-0000-0000-000000000001` | dr.martin@mood-iot.fr |
| Sophie Dupont (patient user) | `b0000000-0000-0000-0000-000000000001` | sophie.dupont@email.fr |
| Marie Laurent (patient user) | `b0000000-0000-0000-0000-000000000002` | marie.laurent@email.fr |
| Lea Moreau (patient user) | `b0000000-0000-0000-0000-000000000003` | lea.moreau@email.fr |
| Anna Bernard (patient user) | `b0000000-0000-0000-0000-000000000004` | anna.bernard@email.fr |
| Sophie (patient profile) | `c0000000-0000-0000-0000-000000000001` | — |
| Marie (patient profile) | `c0000000-0000-0000-0000-000000000002` | — |
| Lea (patient profile) | `c0000000-0000-0000-0000-000000000003` | — |
| Anna (patient profile) | `c0000000-0000-0000-0000-000000000004` | — |

**Mot de passe universel seed :** `MoodIoT2026!`

---

## 13. Problemes connus et limitations

1. **Patient et Teleconsult services** utilisent encore un stockage in-memory pour le CRUD (pas PostgreSQL). Les donnees ne persistent pas entre redemarrages.
2. **Scoring service** necessite des `daily_aggregates` en base pour calculer un score reel.
3. **Notification channels** (Twilio, FCM, SES) ne fonctionnent pas sans cles API reelles. Le coaching IA Claude necessite `ANTHROPIC_API_KEY`.
4. **L'app mobile** (React Native/Expo) necessite un device Android avec Health Connect pour lire les donnees de sante reelles.
5. **Le dashboard** utilise des donnees de demonstration statiques (pas encore connecte a l'API).

---

## Script de test automatise rapide

```bash
#!/bin/bash
# mood-iot-smoke-test.sh
set -e

BASE="http://localhost"
# Puertos remapeados: gateway=8010, auth=8011, patient=8012, scoring=8013, notif=8014, teleconsult=8015
echo "=== Mood-IoT Smoke Test ==="

echo "[1/6] Health checks..."
curl -sf $BASE:8010/api/v1/health | python -m json.tool
curl -sf $BASE:8011/auth/health > /dev/null && echo "  Auth: OK"
curl -sf $BASE:8012/patients/health > /dev/null && echo "  Patient: OK"
curl -sf $BASE:8013/scoring/health > /dev/null && echo "  Scoring: OK"
curl -sf $BASE:8014/notifications/health > /dev/null && echo "  Notification: OK"
curl -sf $BASE:8015/teleconsult/health > /dev/null && echo "  Teleconsult: OK"

echo ""
echo "[2/6] Login psychiatre..."
RESP=$(curl -sf -X POST $BASE:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dr.martin@mood-iot.fr","password":"MoodIoT2026!"}')
TOKEN=$(echo $RESP | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  Token obtenu: ${TOKEN:0:20}..."

echo ""
echo "[3/6] Login patiente Sophie..."
RESP_S=$(curl -sf -X POST $BASE:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sophie.dupont@email.fr","password":"MoodIoT2026!"}')
TOKEN_S=$(echo $RESP_S | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  Token Sophie: ${TOKEN_S:0:20}..."

echo ""
echo "[4/6] /auth/me..."
curl -sf $BASE:8011/auth/me -H "Authorization: Bearer $TOKEN" | python -m json.tool

echo ""
echo "[5/6] Gateway proxy test..."
curl -sf -X POST $BASE:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dr.martin@mood-iot.fr","password":"MoodIoT2026!"}' | python -c "import sys,json; d=json.load(sys.stdin); print(f'  Gateway proxy: OK (role={d[\"user\"][\"role\"]})')"

echo ""
echo "[6/6] Database verification..."
docker exec mood-iot-postgres psql -U mood_user -d mood_iot -c "SELECT count(*) as user_count FROM users;" -t | xargs echo "  Users in DB:"
docker exec mood-iot-postgres psql -U mood_user -d mood_iot -c "SELECT count(*) as patient_count FROM patients;" -t | xargs echo "  Patients in DB:"
docker exec mood-iot-postgres psql -U mood_user -d mood_iot -c "SELECT count(*) as tables FROM information_schema.tables WHERE table_schema='public';" -t | xargs echo "  Tables in DB:"

echo ""
echo "=== Tous les tests passes ==="
```

Sauvegardez ce script dans `mood-iot-smoke-test.sh` et lancez-le avec `bash mood-iot-smoke-test.sh`.
