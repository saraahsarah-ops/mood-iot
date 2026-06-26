# 🚀 Guía del equipo — Mood-IoT (paso a paso, desde cero)

> Guía de onboarding para alguien que trabaja en el proyecto **por primera vez**.
> Si solo quieres tocar el **dashboard médico**, salta directo a la
> [Opción A](#-opción-a-recomendada--dashboard-local--backend-desplegado).
>
> _El código y la interfaz están en francés; esta guía está en español para el equipo._

---

## 1. ¿Qué es Mood-IoT?

Sistema de **detección temprana de recaídas depresivas**. Tiene 3 piezas:

| Pieza | Tecnología | Quién la usa |
|---|---|---|
| **App móvil (paciente)** | Expo / React Native | El paciente registra su humor y los sensores |
| **Dashboard (médico)** | Next.js 14 + NextAuth v5 | El psiquiatra ve pacientes, scores, alertas, teleconsultas |
| **Backend** | FastAPI (microservicios) + PostgreSQL + Redis + Keycloak | API + autenticación + scoring + notificaciones |

**El backend ya está desplegado** en un servidor (Hetzner Cloud), así que **NO necesitas levantarlo** para trabajar en el dashboard o la móvil:

- API: `https://api.mood-iot.fr`  (doc Swagger: `https://api.mood-iot.fr/docs`)
- Auth (Keycloak): `https://auth.mood-iot.fr`
- Dashboard en producción: `https://dashboard.mood-iot.fr`

---

## 2. Requisitos previos (instalar una vez)

| Herramienta | Versión | Para qué |
|---|---|---|
| **Git** | cualquiera reciente | clonar el repo |
| **Node.js** | **18+** (recomendado 20 LTS) | dashboard y app móvil |
| **npm** | viene con Node | dependencias |
| **Python** | **3.11+** | simulador de datos y scripts de QA |
| **Docker Desktop** | reciente | _solo_ si vas a usar la Opción B (backend local) |
| **App Expo Go** | en tu teléfono | _solo_ para probar la app móvil |

Verifica que tengas lo básico:
```bash
git --version
node --version    # debe decir v18 o superior
npm --version
python --version  # 3.11+
```

---

## 3. Clonar el repositorio

El proyecto vive en **dos repos** (se mantienen iguales): `origin` (Cinthya) y
`team` (equipo). Clona el del equipo:

```bash
git clone https://github.com/saraahsarah-ops/mood-iot.git
cd mood-iot
git checkout audit/modernization     # <-- rama de trabajo (NO es main)
git pull
```

> ⚠️ **Siempre trabajamos en la rama `audit/modernization`**, no en `main`.

### Estructura del proyecto
```
mood-iot/
├── backend/              # microservicios FastAPI (gateway, auth, patient, scoring,
│   │                     #   notification, teleconsult, doctor) + modelos + scripts
│   ├── src/
│   └── scripts/          # migraciones SQL puntuales
├── frontend/
│   ├── dashboard/        # dashboard médico (Next.js)  <- aquí trabaja Hawa
│   └── mobile/           # app paciente (Expo)          <- aquí trabaja Cinthya
├── qa/                   # scripts de pruebas E2E (Playwright + API)
├── docker-compose.yml        # stack LOCAL (Opción B)
├── docker-compose.prod.yml   # stack del servidor (no tocar para dev)
└── GUIA_EQUIPO.md        # esta guía
```

---

## 4. ✅ Opción A (recomendada) — Dashboard local + backend desplegado

**La más simple.** No levantas backend ni base de datos: tu dashboard en
`localhost:3000` habla con la API y el Keycloak **ya desplegados**. Ves los
**datos reales** (que están al día) y el login funciona de punta a punta.

```bash
cd frontend/dashboard
cp .env.example .env.local      # luego edita .env.local (ver abajo)
npm install
npm run dev                     # abre http://localhost:3000
```

### Qué rellenar en `.env.local`
Casi todo viene listo en `.env.example` (apunta al backend desplegado). Solo
debes rellenar **2 valores**:

```ini
# 1) Secreto que firma tu sesión local. Genera uno con:
#    openssl rand -base64 32      (en Windows: usa Git Bash, o https://generate-secret.vercel.app/32)
AUTH_SECRET=pega-aqui-un-valor-aleatorio-de-32-bytes

# 2) Secreto del cliente Keycloak `dashboard-medecin`. NO está en el repo (es sensible).
#    Pídeselo a Cinthya/al equipo por un canal privado.
AUTH_KEYCLOAK_SECRET=pide-este-valor-al-equipo
```

Los demás valores del `.env.example` ya están correctos para la Opción A:
- `NEXT_PUBLIC_API_URL=https://api.mood-iot.fr/api/v1`
- `AUTH_URL=http://localhost:3000`
- `AUTH_TRUST_HOST=true`
- `AUTH_KEYCLOAK_ID=dashboard-medecin`
- `AUTH_KEYCLOAK_ISSUER=https://auth.mood-iot.fr/realms/moodiot`

### Probar
1. Abre `http://localhost:3000`.
2. Clic en **"Se connecter"**.
3. Inicia sesión con un usuario de prueba (ver [sección 7](#7-credenciales-de-prueba)):
   `dr.martin@example.test` / `Martin2026!`.

### Editar
- Edita archivos en `frontend/dashboard/src/...`.
- `npm run dev` **recarga en caliente** automáticamente al guardar.

---

## 5. 📱 App móvil (paciente) — Expo

```bash
cd frontend/mobile
cp .env.example .env.local      # ya apunta al backend desplegado, no hace falta tocar
npm install
npx expo start                  # muestra un código QR
```

- Abre **Expo Go** en tu teléfono y **escanea el QR**.
- El cliente Keycloak `mobile-app` es **público (PKCE)** → no hay secretos que poner.
- Login de prueba (paciente): `marie.dupont@example.test` / `Marie2026!`.

> 💡 **Nota importante:** Expo Go carga el JavaScript desde tu PC (necesita estar
> en la misma red WiFi, o usar `npx expo start --tunnel`). Para una app que corra
> **sola en el teléfono sin PC** se genera un **APK** con EAS
> (`eas build -p android --profile preview`). Funciones nativas como
> **Health Connect** y **push** solo se prueban bien en el APK, no en Expo Go.

---

## 6. 🐳 Opción B — Todo local con Docker (avanzado)

Solo si necesitas el **backend corriendo en tu máquina** (p. ej. para modificar
un microservicio).

```bash
# Desde la raíz del repo:
docker compose up -d            # levanta postgres, redis, keycloak y los 7 microservicios
docker compose ps               # verifica que todos estén "healthy"
```

Puertos locales (host):

| Servicio | Puerto local |
|---|---|
| API Gateway | `8010` |
| Keycloak | `8080` |
| PostgreSQL | `5433` |
| Redis | `6380` |
| auth / patient / scoring / notification / teleconsult / doctor | `8011`–`8016` |

Luego apunta el dashboard al backend local: en `frontend/dashboard/.env.local`
**comenta** la línea desplegada y usa:
```ini
NEXT_PUBLIC_API_URL=http://localhost:8010/api/v1
AUTH_KEYCLOAK_ISSUER=http://localhost:8080/realms/moodiot
```

> ⚠️ **Sobre la base de datos local:**
> - Si es la **primera vez** (`docker compose up`), la BD se crea con el esquema
>   correcto pero **vacía**. Para tener pacientes de prueba, corre el simulador:
>   `python qa/simulate_patients.py` (ver el script para opciones).
> - Si ya tenías un volumen **viejo de antes** y algo falla con columnas/tablas
>   nuevas, **recrea la BD desde cero**:
>   ```bash
>   docker compose down -v       # ⚠️ borra los datos locales
>   docker compose up -d
>   ```

---

## 7. Credenciales de prueba

| Rol | Email | Contraseña |
|---|---|---|
| Médico (psiquiatra) | `dr.martin@example.test` | `Martin2026!` |
| Paciente | `marie.dupont@example.test` | `Marie2026!` |

---

## 8. Correr las pruebas de QA (opcional)

En `qa/` hay scripts de pruebas E2E contra el sistema **desplegado**:

```bash
# Pruebas del dashboard (navegador, Playwright):
pip install playwright && playwright install chromium
# PowerShell:
$env:MOODIOT_PASS = "Martin2026!"; python qa/e2e_dashboard.py
# Git Bash:
MOODIOT_PASS='Martin2026!' python qa/e2e_dashboard.py

# Pruebas de los flujos médico (API):
MOODIOT_PASS='Martin2026!' python qa/e2e_backend.py
```

La contraseña se pasa por variable de entorno (no se escribe en el código).
La matriz de casos y las evidencias viven en Google Drive (carpeta *QA Evidencias*),
no en el repo.

---

## 9. Flujo de Git (importante)

- Trabajamos en la rama **`audit/modernization`**.
- Hay **dos remotos** y deben quedar **iguales** (homologados):

```bash
git remote -v
# origin -> CinthyaCBGON/mood-iot
# team   -> saraahsarah-ops/mood-iot

# Antes de empezar a trabajar, trae lo último:
git pull team audit/modernization

# Al terminar un cambio:
git add .
git commit -m "tipo: descripción breve"      # tipos: feat, fix, refactor, docs, test, chore
git push origin audit/modernization
git push team   audit/modernization           # <-- ¡no olvides empujar a AMBOS!
```

> Si te sale conflicto al hacer pull, avisa al equipo antes de forzar nada.

---

## 10. Errores comunes y solución

| Síntoma | Causa probable | Solución |
|---|---|---|
| Login redirige a `0.0.0.0:3000` | falta `AUTH_URL` / `AUTH_TRUST_HOST` en `.env.local` | añádelas (ver sección 4) |
| `InvalidEndpoints: ... missing issuer` | falta `AUTH_KEYCLOAK_ISSUER` | añádela |
| Login da error de cliente/secreto | `AUTH_KEYCLOAK_SECRET` vacío o incorrecto | pide el secreto al equipo |
| `npm run dev` no arranca | dependencias desactualizadas | `npm install` de nuevo |
| (Opción B) error de columnas/tablas en el backend | BD local vieja sin las migraciones | `docker compose down -v && docker compose up -d` (recrea la BD) |
| La app móvil no conecta al backend local | usaste `localhost` en vez de la IP LAN | usa la IP de tu PC (`ipconfig`) — ver `frontend/mobile/.env.example` |

> Si el error no está aquí: **copia el mensaje de error completo** y compártelo
> con el equipo. No vuelvas a una versión anterior sin avisar — la actual incluye
> correcciones importantes (entre ellas un arreglo del login del dashboard).

---

## 11. Documentación de la API

- **Swagger UI** (interactivo): `https://api.mood-iot.fr/docs`
- **OpenAPI JSON**: `https://api.mood-iot.fr/openapi.json`
- En local (Opción B) cada microservicio expone su propia doc en `/docs`.
