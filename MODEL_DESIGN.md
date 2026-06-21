# MODEL_DESIGN.md — Conception du modèle de scoring Mood-IoT

> Document de conception du système de scoring de risque dépressif.
> Public : équipe Fil Rouge Mood-IoT + jury de soutenance.
> Objectif : expliquer **honnêtement** ce que le système fait, sur quelles
> bases, et quelles sont ses limites.

---

## 1. Cas d'usage et problème réel

**Objectif du projet** : *détection précoce des rechutes dépressives* à partir
de données de capteurs (sommeil, activité, fréquence cardiaque, etc.).

### Une distinction essentielle : NIVEAU vs RECHUTE

Une **rechute** n'est pas un niveau absolu de dépression — c'est un
**changement dans le temps** : un patient qui allait bien et dont l'état se
dégrade par rapport à *son propre* état habituel.

C'est une distinction cruciale car elle conditionne :
- ce qu'on peut apprendre des données disponibles,
- comment on doit construire les features,
- ce qu'on peut honnêtement affirmer en soutenance.

### Le constat (transparence)

**Aucun dataset clinique librement accessible ne contient de rechutes
longitudinales étiquetées.** Les datasets disponibles mesurent un *niveau* de
dépression à un instant donné :

| Dataset | Étiquette | Nature |
|---|---|---|
| Depresjon (utilisé) | MADRS (2 mesures/patient) | **Niveau**, quasi constant par patient |
| GLOBEM | PHQ-4 / BDI-II | **Niveau** |
| RADAR-MDD | PHQ-8 toutes les 2 semaines | **Longitudinal** (capte les transitions) — accès restreint via consortium |

→ Conséquence : un modèle entraîné sur Depresjon/GLOBEM apprend à distinguer
*déprimé vs sain* (un niveau), **pas** à détecter une rechute (un changement).
Ignorer ce point serait malhonnête.

---

## 2. Architecture retenue : 2 couches complémentaires

Plutôt que de prétendre « prédire des rechutes avec une IA validée » (ce que
les données ne permettent pas), nous combinons **deux signaux complémentaires** :

```
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 1 — Détection de déviation (Z-score)                      │
│  « Ce patient s'écarte-t-il de SON état normal ? »               │
│  → Indicateur conceptuel de la RECHUTE.                           │
│  → Chaque patient est son propre témoin (baseline individuel).   │
│  → Ne dépend d'aucun dataset externe.                            │
├─────────────────────────────────────────────────────────────────┤
│  COUCHE 2 — Pondération clinique (modèle XGBoost / Depresjon)    │
│  « Quelles combinaisons de signaux sont associées à la           │
│    dépression, selon des données cliniques réelles ? »           │
│  → Apporte le poids appris sur étiquettes MADRS validées.        │
└─────────────────────────────────────────────────────────────────┘
```

Les deux couches partagent la même représentation : des **Z-scores**.

---

## 3. Couche 1 — Le Z-score (cœur de la détection de rechute)

### Définition
Pour chaque métrique (sommeil, activité, rythme circadien) et chaque patient :

```
z = (valeur du jour − moyenne habituelle du patient) / écart-type habituel
```

Le baseline (moyenne, écart-type) est calculé sur l'historique propre du patient.

### Pourquoi c'est le bon outil pour une rechute
- **Normalisation individuelle** : un sportif à 12 000 pas et un sédentaire à
  3 000 pas ont chacun leur « normal ». Le Z-score détecte l'écart relatif, pas
  la valeur absolue. C'est exactement ce qui distingue une dégradation.
- **Indépendance du dataset / dispositif** : un z = −2 en sommeil signifie « 2
  écarts-types sous son habitude », que la donnée vienne de l'Actiwatch
  (Depresjon) ou de Health Connect (l'app). → le modèle **transfère** mieux.
- **Pas besoin d'étiquettes externes massives** : le baseline se construit avec
  les premières semaines d'usage de chaque patient.

### Limite assumée
Nécessite une période d'établissement du baseline (premières semaines) avant de
pouvoir détecter des déviations fiables.

---

## 4. Couche 2 — Le modèle XGBoost (pondération clinique)

### Données
**Depresjon** (Simula Research Lab, Norvège — européen) : actigraphie réelle de
55 patients (~14 jours), étiquetée par scores **MADRS** cotés par un clinicien.

### Méthodologie (corrigée — cf. AUDIT_FINDINGS.md §2)
La version initiale comportait 3 défauts méthodologiques, tous corrigés :

| Défaut v1 | Correction v2 |
|---|---|
| Mapping inventé (actigraphie → fréquence cardiaque/GPS fictifs) | 6 features **honnêtes** dérivées uniquement de l'actigraphie réelle |
| Bruit gaussien ajouté aux labels | Labels MADRS interpolés **sans bruit** |
| Data leakage : `trend_14d` dérivé du label | Tendances calculées sur l'**activité**, jamais sur le label |
| KFold aléatoire (fuite inter-jours d'un patient) | **GroupKFold par patient** |
| Métriques sur le train set | **Test holdout** indépendant (patients jamais vus) |

### Features (6, toutes réelles)
`z_step_count`, `z_sleep_duration`, `z_sleep_quality`, `trend_7d`, `trend_14d`,
`is_weekend`.

### Métriques honnêtes (test holdout, 11 patients jamais vus)
- **R² = 0.43** · RMSE = 16.3 · MAE = 13.3
- **Accuracy 4 niveaux = 78.6 %**
- Discrimination réelle : déprimés (prédiction ~32) vs contrôles (~7.6), écart 24.6 pts.
- Feature la plus importante : `z_sleep_quality` (rythme circadien, 27 %) —
  cohérent avec la littérature clinique sur la dépression.

### Interprétation honnête du R² = 0.43
L'actigraphie capture **une partie** du signal dépressif (sommeil, activité,
rythme), pas la totalité (la dépression est multifactorielle). Un R² de 0.3–0.5
est l'ordre de grandeur attendu dans la littérature wearable + santé mentale.
Le R² = 0.84 de la v1 était **illusoire** (data leakage).

---

## 5. Ce que le système affirme (et n'affirme pas)

✅ **On peut affirmer** :
- On détecte des **déviations du baseline individuel** (Z-score) — indicateur de
  possible rechute.
- On les pondère avec un modèle entraîné sur des **données cliniques réelles**
  (Depresjon, MADRS), validé **sans data leakage** (R² = 0.43 en test holdout).
- Le score est **explicable** (SHAP + Z-scores visibles).

❌ **On ne prétend PAS** :
- « Prédire des rechutes réelles avec une IA validée » — aucun dataset
  accessible ne contient de rechutes longitudinales étiquetées pour le valider.
- Remplacer un diagnostic clinique (l'outil est un **dépistage/alerte**, pas un
  diagnostic — cf. disclaimer RGPD dans l'app).

---

## 6. Garde-fous cliniques et éthiques

- **Seuil de sécurité** : si le risque ≥ 80, pas de coaching IA automatique →
  escalade au médecin (`RISK_HARD_CEILING`).
- **Pas de diagnostic** : le coaching IA (Claude) interdit explicitement tout
  vocabulaire diagnostique ; disclaimer systématique.
- **Le médecin garde la décision** : l'outil alerte, le psychiatre décide.

---

## 7. Travail futur

1. **RADAR-MDD** (consortium EU : KCL, Amsterdam, Barcelone) — le seul dataset
   **longitudinal** (PHQ-8 / 2 semaines) qui permettrait de valider réellement
   la détection de *rechutes*. Accès via consortium (en cours d'évaluation).
2. **GLOBEM** (PhysioNet) — plus de signaux (FC, GPS, téléphone) pour enrichir
   la Couche 2. Demande d'accès en cours.
3. **Validation prospective** : suivre de vrais patients avec leur baseline réel
   et confirmer que les déviations Z-score précèdent les dégradations cliniques.

---

## 8. Synthèse pour la soutenance

> *« Notre système détecte les déviations du comportement de chaque patient par
> rapport à son propre baseline (Z-score) — l'indicateur clinique d'une possible
> rechute. Ces déviations sont pondérées par un modèle XGBoost entraîné sur des
> données cliniques réelles (Depresjon, étiquettes MADRS), validé sans data
> leakage avec un R² de 0.43 en test holdout sur des patients jamais vus. Nous
> assumons une limite : aucun dataset librement accessible ne contient de
> rechutes longitudinales étiquetées, donc la validation de la prédiction de
> rechutes réelles est un travail futur (RADAR-MDD). L'outil est un dispositif
> de dépistage et d'alerte, pas un diagnostic. »*

C'est défendable, rigoureux, et honnête.

---

*Version 1.0 — 2026-06-21 · Équipe Mood-IoT, Master ADE, Telecom Paris.*
