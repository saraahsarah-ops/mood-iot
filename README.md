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
Le dashboard se lance seul (pas besoin du backend en local : il pointe vers
l'API déjà déployée). Le client Keycloak `dashboard-medecin` autorise déjà
`http://localhost:3000`.

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
