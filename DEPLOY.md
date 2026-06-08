# Déploiement — Mood-IoT sur OVH Public Cloud HDS

> **Statut juridique** : Mood-IoT manipule des données de santé à caractère
> personnel (DSCP) au sens de la **loi française** + **RGPD article 9**.
> Hébergement OBLIGATOIRE chez un opérateur certifié HDS (Hébergeur de
> Données de Santé). Liste officielle :
> <https://esante.gouv.fr/labels-certifications/hds/liste-des-hebergeurs-certifies>
>
> **OVH** est certifié HDS depuis 2018. Ce document décrit le déploiement
> sur OVH Public Cloud HDS exclusivement.

---

## 1. Pré-requis OVH

### 1.1 Commandes OVH (compte entreprise)

| Service | Référence OVH | Quantité minimum (100 patients) |
|---|---|---|
| Projet Public Cloud HDS | "Public Cloud Project" + option HDS activée | 1 |
| Kubernetes managé HDS | "OVHcloud Managed Kubernetes" sur instances HDS | 1 cluster, 3 worker nodes `b2-15` |
| Postgres managé HDS | "Postgres Essential" avec option HDS | 1 instance 4 vCPU / 15 GB RAM |
| Redis managé | "Redis Essential" | 1 instance 1 GB |
| Object Storage HDS | "Object Storage S3" en région HDS (GRA, RBX, SBG) | 1 bucket par environnement |
| Container Registry | "OVH Managed Private Registry" | 1 |
| Load Balancer + IP failover | "Public Cloud Load Balancer" | 1 |
| Domaine DNS | `mood-iot.fr` + `auth.moodiot.fr` + `api.moodiot.fr` | délégation OVH ou Cloudflare |

**Coût estimatif mensuel (100 patients actifs)** :
- Compute K8s : ~120 €
- Postgres managé HDS : ~150 €
- Redis : ~25 €
- Object Storage (10 GB audio + ML) : ~5 €
- Load Balancer + IP : ~25 €
- Registry : ~10 €
- Bande passante : ~10 €
- **Total ~345 €/mois HT** (hors Anthropic/OpenAI/Resend/Twilio)

### 1.2 Documents légaux

- **DPA (Data Processing Agreement)** OVH HDS : à signer dans l'espace
  client OVH avant tout déploiement de PHI.
- **Convention de service HDS** OVH : génère automatiquement les annexes
  RGPD/HDS et un PRA (Plan de Reprise d'Activité).
- **Registre des traitements RGPD** : voir `docs/rgpd/registre.md`
  (à créer en Phase 3).
- **Étude d'impact relative à la protection des données (AIPD)** : à
  réaliser avant la mise en production (CNIL recommande pour tout
  système de santé connecté).

### 1.3 Tiers nécessaires hors-OVH

| Service | Usage | DPA signable | Souveraineté FR |
|---|---|---|---|
| Anthropic Claude Haiku 4.5 | Coaching IA + analyse humeur voix | Oui (commercial agreement) | EU data residency (Frankfurt) |
| OpenAI Whisper API | Transcription voix → texte | Oui (zero-retention add-on) | EU data residency disponible |
| Resend | Emails transactionnels + SMTP Keycloak | Oui (RGPD inclus) | EU servers |
| Twilio | SMS rappels RDV | Oui | Servers UE (à confirmer) — migrer vers OVH SMS en cible |
| Expo / EAS Build | Builds mobiles + push notifs | Standard | US (build seul, pas de PHI) |

---

## 2. Préparation du cluster

### 2.1 Création du cluster

```bash
ovhai k8s cluster create mood-iot-prod \
  --version 1.31 \
  --region GRA9 \
  --private-network vrack-mood-iot \
  --node-pool name=workers,flavor=b2-15,desired-nodes=3,min-nodes=2,max-nodes=6
```

Récupère le `kubeconfig` :

```bash
ovhcloud-cli kubernetes cluster kubeconfig --cluster-id <id> --output kubeconfig.yaml
export KUBECONFIG=$PWD/kubeconfig.yaml
kubectl get nodes
```

### 2.2 Installation cert-manager + ingress

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager --namespace cert-manager \
  --create-namespace --version v1.15.3 --set installCRDs=true

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx \
  --create-namespace --set controller.replicaCount=2
```

Configure le `ClusterIssuer` Let's Encrypt :

```yaml
# k8s/cert-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    email: ops@mood-iot.fr
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

```bash
kubectl apply -f k8s/cert-issuer.yaml
```

### 2.3 Secrets management

OVH ne fournit pas de Secret Manager natif. Choix :

- **Option A — Sealed Secrets** (recommandé pour démarrer) :
  ```bash
  helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system
  ```
  Les secrets chiffrés peuvent être committés en clair dans git.

- **Option B — HashiCorp Vault** : plus robuste, audit log natif HDS-friendly.

Tous les secrets DOIVENT être chiffrés au repos (étape obligatoire HDS).

---

## 3. Déploiement de Keycloak

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami

helm install keycloak bitnami/keycloak \
  --namespace auth --create-namespace \
  --values k8s/keycloak/values.prod.yaml
```

`k8s/keycloak/values.prod.yaml` (extrait) :

```yaml
production: true
proxy: edge          # derrière l'ingress-nginx
auth:
  adminUser: admin
  existingSecret: keycloak-admin
ingress:
  enabled: true
  hostname: auth.moodiot.fr
  ingressClassName: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  tls: true
postgresql:
  enabled: false
externalDatabase:
  host: <ovh-managed-postgres-host>
  database: keycloak
  user: keycloak
  existingSecret: keycloak-db
extraEnvVars:
  - name: KC_SPI_THEME_STATIC_MAX_AGE
    value: "3600"
```

**Import du realm `moodiot`** (idempotent) :

```bash
kubectl exec -n auth keycloak-0 -- /opt/bitnami/keycloak/bin/kc.sh \
  import --file /tmp/realm-moodiot.json --override true
```

Fichier source : `infrastructure/keycloak/realms/moodiot.json` (à versionner).

---

## 4. Déploiement de l'application

### 4.1 Construction et push des images

```bash
export REGISTRY=registry.gra.cloud.ovh.net/mood-iot
docker login $REGISTRY

for service in gateway auth patient scoring notification doctor teleconsult; do
  docker build \
    --build-arg SERVICE_NAME=$service \
    -t $REGISTRY/$service:$(git rev-parse --short HEAD) \
    -t $REGISTRY/$service:latest \
    -f backend/infrastructure/docker/Dockerfile backend/
  docker push $REGISTRY/$service:$(git rev-parse --short HEAD)
  docker push $REGISTRY/$service:latest
done
```

> En réalité, la pipeline CI fait ce travail — voir `.github/workflows/ci.yml`.

### 4.2 Helm chart Mood-IoT

```bash
helm install mood-iot ./infrastructure/helm/mood-iot \
  --namespace mood-iot --create-namespace \
  --values infrastructure/helm/mood-iot/values.prod.yaml
```

Le chart déploie :

- 7 microservices (1 Deployment + 1 Service par microservice)
- 1 Ingress `api.moodiot.fr` → gateway-service
- HPA (autoscaling) sur scoring + notification
- NetworkPolicy : seul le gateway accepte du trafic extérieur
- PodDisruptionBudget min 1
- ServiceAccount + RoleBinding (least-privilege)

### 4.3 Migrations base de données

```bash
kubectl run psql-migrator --rm -it \
  --image=$REGISTRY/patient:latest \
  --restart=Never -- \
  python -m alembic upgrade head
```

**Ordre des migrations Postgres** (déjà numéroté dans `backend/migrations/`) :
1. `00-extensions.sql` — pgcrypto, uuid-ossp
2. `01-init-schema.sql` — tables principales
3. `02-rls.sql` — Row-Level Security
4. `03-audit.sql` — audit_log + triggers
5. `04-fixtures-dev.sql` — **NE PAS exécuter en prod**
6. `05-keycloak-migration.sql`
7. `06-humeur-messages-prefs.sql`
8. `07-humeur-emoji-voix.sql`

---

## 5. Observabilité & sécurité opérationnelle

### 5.1 Logs centralisés

Tous les services écrivent en **JSON sur stdout** via `structlog`. Le
collecteur K8s (Fluent Bit) achemine vers **OVH Logs Data Platform** :

```bash
helm install fluent-bit fluent/fluent-bit \
  --namespace logging --create-namespace \
  --values k8s/fluent-bit/values.yaml
```

Conservation logs : **6 ans** (obligation HDS pour audit_log).

### 5.2 Métriques

Prometheus Operator + Grafana :

```bash
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```

Dashboards versionnés dans `infrastructure/grafana/dashboards/`.

### 5.3 Backups

- **Postgres** : snapshot OVH managed *quotidien*, rétention 30 jours,
  + dump logique hebdomadaire vers Object Storage HDS chiffré.
- **Object Storage** : versioning activé + Object Lock 90 jours.
- **Keycloak** : `kc.sh export` quotidien vers Object Storage HDS.

### 5.4 PRA (Plan de Reprise d'Activité)

- RTO cible : 4 h
- RPO cible : 1 h
- Région de bascule : OVH RBX (si prod GRA)
- Test PRA semestriel — runbook : `docs/ops/runbook-pra.md`

### 5.5 Conservation des données

| Donnée | Durée | Référence légale |
|---|---|---|
| `audit_log` | 6 ans | Code de la santé publique L.1111-7 |
| `health_data` (capteurs) | Pendant la prise en charge + 20 ans | L.1112-7 |
| `humeur_entries` | Pendant la prise en charge + 20 ans | L.1112-7 |
| `messages` (med→patient) | Pendant la prise en charge + 20 ans | L.1112-7 |
| Comptes inactifs | Anonymisation après 3 ans d'inactivité | CNIL (recommandation santé) |

---

## 6. Mise à jour / rollback

```bash
# Déploiement standard (CI/CD GitHub Actions le fait sur push main)
helm upgrade mood-iot ./infrastructure/helm/mood-iot \
  --namespace mood-iot \
  --values infrastructure/helm/mood-iot/values.prod.yaml \
  --set image.tag=$(git rev-parse --short HEAD)

# Rollback rapide vers la version précédente
helm rollback mood-iot 0 -n mood-iot
```

---

## 7. Environnement low-cost de staging (NON-PROD, sans PHI réel)

Pour les tests d'intégration & démos sans engager de coût HDS :

| Service | Provider | Coût |
|---|---|---|
| Compute | GCP Cloud Run (jamais de PHI réel) | gratuit jusqu'à 2M req/mois |
| Postgres | Neon free tier | gratuit (1 projet, 3 GB) |
| Redis | Upstash free tier | gratuit (10k req/jour) |
| Object Storage | Cloudflare R2 (free egress) | gratuit jusqu'à 10 GB |
| Keycloak | image officielle sur Cloud Run | gratuit (sleep si inactif) |

**Règle absolue** : ces environnements N'HÉBERGENT JAMAIS de PHI réel. Seules
des fixtures synthétiques (`backend/migrations/04-fixtures-dev.sql`) y vivent.

---

## 8. Checklist Go-Live

- [ ] DPA OVH HDS signé
- [ ] DPA Anthropic, OpenAI, Resend, Twilio signés
- [ ] AIPD réalisée et validée par le DPO
- [ ] Registre des traitements RGPD à jour
- [ ] Cluster K8s + Postgres + Redis HDS provisionnés
- [ ] cert-manager + ingress + Let's Encrypt OK
- [ ] Domaines `auth.moodiot.fr` + `api.moodiot.fr` + `mood-iot.fr` pointés
- [ ] Realm Keycloak `moodiot` importé + identity providers Google/Apple OK
- [ ] Tous les secrets en Sealed Secrets ou Vault
- [ ] Migrations Postgres appliquées (sans `04-fixtures-dev.sql`)
- [ ] Logs centralisés + alertes Prometheus/Grafana
- [ ] Backups automatiques OK + 1 restore test validé
- [ ] Runbook PRA répété au moins 1 fois
- [ ] Pen-test externe réalisé (au moins OWASP Top 10)
- [ ] Audit code IDOR/SQLi/XSS clean (cf. `AUDIT.md` § sécurité)
- [ ] Stores app mobile (Apple App Store + Google Play) en review
- [ ] Information patients : politique de confidentialité publiée
- [ ] Procédure d'exercice des droits RGPD documentée (access/rectification/effacement)

---

*Version du document : 1.0 — 2026-06-08*
