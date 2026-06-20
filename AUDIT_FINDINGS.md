# AUDIT_FINDINGS.md — Auditoría technique rigoureuse Mood-IoT

> Date : 2026-06-20 · Méthode : revue de code avec preuves (`fichier:ligne`).
> Périmètre : backend (`backend/src/`), pipeline ML (`backend/src/scoring/`),
> intégration Claude (`backend/src/notification/`).
> **Aucune supposition** — chaque constat est vérifié dans le code.

---

## Verdict global

L'application est un **excellent prototype/démo déployé**, **PAS un produit
prêt pour des patients réels**. Trois axes de risque majeurs :

1. **Sécurité** : IDOR critiques + PHI non chiffré → non conforme RGPD/HDS.
2. **ML** : le modèle XGBoost est entraîné mais **jamais utilisé** pour prédire.
3. **Coûts IA** : aucun rate limiting sur Claude → facture sans plafond.

Aucun de ces points ne casse la démo. Mais les présenter comme « système d'IA
clinique validé » ne tiendrait pas face à un revue technique.

---

## 1. Sécurité (CRITIQUE)

### 1.1 IDOR — accès aux données d'autres patients
Endpoints recevant `{patient_id}` sans vérifier l'appartenance au user authentifié :

| Endpoint | Fichier:ligne | Impact |
|---|---|---|
| `GET /scoring/latest/{patient_id}` | `scoring/main.py:378` | Lire le score de risque d'un autre patient |
| `GET /scoring/history/{patient_id}` | `scoring/main.py:412` | Historique de risque d'autrui |
| `GET /scoring/explain/{score_id}` | `scoring/main.py:464` | SHAP de n'importe quel score |
| `POST /scoring/compute/{patient_id}` | `scoring/main.py:215` | Forcer un calcul pour autrui |
| `GET /patients/{patient_id}/baseline` | `patient/main.py:536` | Baseline (GPS, FC) d'autrui |
| `GET /patients/{patient_id}/metrics` | `patient/main.py:1191` | Métriques santé d'autrui |

**Le patron de correction existe déjà** et est correct dans les endpoints
`/me/*` (`patient/main.py:953` `_resolve_my_patient_id`) et `list_patients`
(filtre par `PatientPsychiatrist`). Il suffit de l'appliquer partout.

### 1.2 Endpoint interne sans auth, exposé à internet
`POST /scoring/internal/compute/{patient_id}` (`scoring/main.py:322`) déclare
`x_internal_service: str = ""` comme **query param** (jamais validé) et le
gateway le route sans filtrer (`gateway/main.py:196-202`). N'importe qui peut
déclencher recalculs + alertes pour n'importe quel patient.

### 1.3 PHI non chiffré au repos
Données de santé mentale en clair (`models.py`) :
- `MoodEntry.notes`, `phq9_score`, `mood_rating` (`:467-488`)
- `Patient.diagnosis` (`:350`)
- `DailyAggregate` (FC, sommeil, GPS, appels), `RiskScore`

Seuls RPPS + licence médecin sont chiffrés (Fernet, `shared/encryption.py`).
**Bug** : `auth/main.py:250-251` stocke le RPPS **en clair** dans une colonne
`_encrypted` alors que `doctor/main.py:223` le chiffre → décryptage renvoie
`[CHIFFREMENT INVALIDE]`.

### 1.4 Autres
- **Aucun rate limiting** dans tout le backend (`slowapi|limiter` → 0 résultat).
- **CORS** `allow_origins=["*"]` + `allow_credentials=True` partout
  (`gateway/main.py:28`, etc.).
- **Defaults dangereux** sans validation au boot : `JWT_SECRET_KEY=
  "change-me-in-production"` (`config.py:37`), `DATABASE_URL` avec password par
  défaut (`config.py:19`), `JITSI_JWT_SECRET="change-me"` (`config.py:68`).
- **Pas de headers de sécurité** (HSTS/CSP/X-Frame) au niveau app (Caddy en
  ajoute certains côté proxy en prod).
- **Fuite d'infos** : `gateway/main.py:119,124` renvoie `target_url` interne et
  `str(e)` au client.
- `ENVIRONMENT`/`LOG_LEVEL` défaut = development/DEBUG → Swagger + SQL logs.

### Points positifs (vérifiés)
- Vérification token Keycloak correcte : RS256, `exp`, `iss`, `aud`
  (`shared/keycloak.py:54-119`).
- **Aucune injection SQL** (ORM paramétré partout).
- **Aucun secret hardcodé** dans le code.
- Endpoints RGPD (export/anonymisation) implémentés.

---

## 2. Machine Learning (CRITIQUE — modèle fantôme)

### 2.1 Le modèle XGBoost n'est jamais utilisé pour prédire
- Modèle réel entraîné : `backend/models/xgboost_risk_model.json` (363 KB,
  200 arbres, 11 features). Vérifié non-trivial.
- **MAIS** `_predict_score` (`pipeline.py:535-647`) ne contient **aucun**
  `self._model.predict()`. Le score sort d'une **heuristique hardcodée**
  (sigmoïde sur Z-scores pondérés + pénalités).
- `self._model` ne sert qu'à SHAP (`pipeline.py:682-688`).
- Le système rapporte `model_version="xgboost-..."` (`pipeline.py:301`) →
  **trompeur** : laisse croire au psychiatre qu'une alerte vient d'un ML validé.

### 2.2 Défauts d'entraînement
- **Data leakage** : `trend_14d` (feature #1, importance 0.232) dérivée du label
  (`train_model.py:404-432`) → R²=0.84 illusoire.
- **Labels semi-synthétiques** : bruit gaussien `np.random.normal(0,3)` ajouté
  (`train_model.py:384`).
- **Proxies injustifiés** : actigraphie poignet mappée vers FC/HRV/GPS/appels que
  le dataset ne mesure pas (`train_model.py:213-249`).
- **Non reproductible** : dataset Depresjon absent du repo ; `backend/scores.csv`
  est un fixture démo sans rapport.
- **Hyperparamètres** fixes à la main, aucun tuning (`train_model.py:475-485`).
- **CV avec fuite** inter-patients (KFold aléatoire au lieu de GroupKFold,
  `train_model.py:490`).
- **Métriques sur le train set** (`train_model.py:512-517`) → surapprentissage.

---

## 3. Intégration Claude / Anthropic (coûts + sécurité clinique)

### 3.1 Trois intégrations distinctes, sans couche commune
| Fichier:ligne | Modèle | max_tokens | Usage |
|---|---|---|---|
| `ai_coach.py:58` | `claude-haiku-4-5` | 200 | Coaching |
| `channels.py:92` | `claude-sonnet-4` (~5x cher) | 300 | Coaching escalade |
| `main.py:520` | `claude-sonnet-4` | 1000 | Synthèse clinique |

### 3.2 Risques vérifiés
- **Aucun rate limiting / plafond** sur les appels (grep `rate.?limit` → 0).
  Coût = prix unitaire × invocations illimitées.
- **Bypass du garde-fou clinique** : `RISK_HARD_CEILING=80` ne s'applique que
  `if risk_score is not None` (`ai_coach.py:130`). `risk_score` étant optionnel
  (`ai_coach.py:112`, `main.py:577`), un appel sans lui génère du coaching pour
  un patient en risque critique.
- **Aucun timeout** configuré → défaut SDK 600s ; `main.py:520` bloque le worker
  jusqu'à 10 min.
- **Aucun cache** (ni prompt caching Anthropic ni cache de réponses).
- **Modèle hardcodé** (non configurable par env).

### Points positifs
- Fallback robuste si l'API échoue (`ai_coach.py:99-105`).
- 1 seul appel Claude par patient (pas de re-appel par canal).
- Disclaimer RGPD/santé déterministe et toujours présent
  (`templates/fr/ai_coaching.py:20`).
- System prompt anti-diagnostic bien construit (`ai_coach.py:61-76`).

---

## 4. Infrastructure (constats serveur)

- **1 seul serveur** Hetzner CX23 (2 vCPU, 3,7 GB RAM, 38 GB disque).
  Tout y vit : 11 conteneurs, Postgres, Redis. Usage actuel : 1,6 GB RAM, 12 GB disque.
- **Bases de données** = volumes Docker locaux (`postgres_data` 13 MB,
  `redis_data`). **Aucun backup automatique configuré** → perte totale si le
  volume est corrompu/supprimé.
- **Pas de CI/CD actif** : déploiement manuel (git pull + rebuild en SSH).
- **TLS BD désactivé** en mode cloud (`database.py:27-28`,
  `check_hostname=False`, `CERT_NONE`).

---

## Plan de remédiation priorisé

### P0 — avant tout patient réel
- [ ] Corriger les IDOR (§1.1) — appliquer le patron `/me/*` partout.
- [ ] Sécuriser/supprimer l'endpoint interne exposé (§1.2).
- [ ] Chiffrer le PHI au repos (§1.3) — Fernet sur mood/PHQ-9/diagnosis.
- [ ] Rate limiting global (slowapi) + plafond Claude par patient/jour (§3.2).
- [ ] Corriger le bypass `risk_score=None` du garde-fou (§3.2).

### P1 — avant production
- [ ] Validation des secrets au boot (rejeter les defaults `change-me`).
- [ ] CORS restrictif (origines explicites).
- [ ] Timeout sur les appels Claude.
- [ ] Backups automatiques Postgres (cron + Object Storage).
- [ ] Connecter le modèle XGBoost OU rapporter `model_version` honnête (§2.1).

### P2 — qualité / honnêteté technique
- [ ] Réentraîner sans data leakage (GroupKFold, sans bruit synthétique,
      données reproductibles).
- [ ] Headers de sécurité, masquage des erreurs internes du gateway.
- [ ] Prompt caching Anthropic pour la synthèse clinique.

---

*Cet audit reflète l'état du code au commit de la branche `audit/modernization`
au 2026-06-20. Les preuves `fichier:ligne` permettent de tout re-vérifier.*
