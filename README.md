# Mood-IoT
Système de détection précoce des rechutes dépressives.

## Équipe
- Salma : Simulateur de données
- Arleth : Scoring et alertes
- Hawa : Dashboard médecin
- Cynthia : App patient

## Lancer le simulateur
cd simulateur
python simulateur.py

## Lancer le dashboard médecin (dev local)
Deux modes possibles :

- **Mode A (recommandé) — dashboard local + backend déployé.** Le plus simple :
  pas besoin de lancer le backend. Le dashboard sur `http://localhost:3000`
  tape l'API et le Keycloak déjà déployés. Fonctionne de bout en bout
  (login + données) : le client Keycloak `dashboard-medecin` autorise
  `localhost:3000`, et le CORS du backend déployé autorise aussi
  `http://localhost:3000`. C'est la config du `.env.example`.
- **Mode B — tout en local.** Lancer le backend via `docker compose up -d`
  (à la racine), puis pointer le dashboard vers le local : dans `.env.local`,
  `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` et
  `AUTH_KEYCLOAK_ISSUER=http://localhost:8080/realms/moodiot`.

Étapes (mode A) :

```bash
cd frontend/dashboard
cp .env.example .env.local       # puis remplir les valeurs (voir commentaires)
#   - AUTH_SECRET : openssl rand -base64 32
#   - AUTH_KEYCLOAK_SECRET : à demander à l'équipe (secret du client Keycloak)
npm install
npm run dev                      # http://localhost:3000
```

Erreurs fréquentes si `.env.local` est incomplet :
- `InvalidEndpoints: Provider "keycloak" is missing ... issuer` → `AUTH_KEYCLOAK_ISSUER` manquant.
- redirections vers `0.0.0.0:3000` → `AUTH_URL` et `AUTH_TRUST_HOST` manquants.

Connexion de test : `dr.martin@example.test` / `Martin2026!`.

## Documentation de l'API (Swagger)
Le backend FastAPI expose une doc interactive auto-générée :
- Swagger UI : https://api.mood-iot.fr/docs
- OpenAPI JSON : https://api.mood-iot.fr/openapi.json

En local, chaque microservice expose aussi sa propre doc sur `/docs`.
