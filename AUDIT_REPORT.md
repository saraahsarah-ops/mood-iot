# Reporte de Auditoría Arquitectónica - Mood-IoT

## 1. Inventario y Mapa del Repositorio

**Análisis completado.** La arquitectura de Mood-IoT sigue un patrón de microservicios con una estructura en monorepo parcial, segmentada en las siguientes áreas:

*   **Backend (Microservicios en Python):**
    *   **Lenguaje y Framework:** Python 3.x con FastAPI.
    *   **Servicios Identificados:** API Gateway (`:8010`), Auth (`:8011`), Patient (`:8012`), ML-Scoring (`:8013`), Notification (`:8014`), Teleconsult (`:8015`).
    *   **Dependencias principales:** `pydantic`, `sqlalchemy`, `asyncpg`, `redis`, `xgboost`, `scikit-learn`, `anthropic`, `twilio`.
*   **Frontend (Dashboard):**
    *   **Lenguaje y Framework:** TypeScript, React 18, Next.js 14.
    *   **Dependencias principales:** `recharts`, `zustand`, `framer-motion`, `tailwindcss`.
*   **Mobile-Hub (SanteConnect):**
    *   **Framework:** React Native (CLI).
*   **App Patient (Simulador/Dashboard alternativo):**
    *   **Framework:** Streamlit (Python) (`app.py`).
*   **Infraestructura Local (IaC) & CI/CD:**
    *   **Actual:** Basado íntegramente en `docker-compose.yml` (Postgres, Redis, 6 microservicios, LocalStack).
    *   **CI/CD:** No se detectan pipelines de integración continua (Github Actions o GitLab CI) configurados en el repositorio actualmente. Hay rastros de `render.yaml`, sugiriendo un despliegue planificado en PaaS.

---

## 2. Búsqueda de valores hardcodeados y configuración insegura

**Análisis completado.** Se ejecutó un escaneo recursivo en el código fuente ignorando dependencias.
*   **Archivos de QA:** Se encontraron contraseñas en texto plano (`MoodIoT2026!`) en `qa/record_demo.py` y `qa/test_dashboard.py`.
*   **Configuración Base:** `docker-compose.yml` define *fallbacks* con contraseñas por defecto (`mood_secret_2026`, `change-me-in-production`).
*   **Frontend/Mobile:** Los tokens y contraseñas detectados en el frontend (`src/lib/auth.ts`, `stores/authStore.ts`) son firmas de métodos y variables de estado, no secretos hardcodeados (falsos positivos descartados).

**Parches generados:** Las instrucciones de mitigación se han guardado en `proposals/hardcoded_fixes.md` para evitar inyectar código destructivo sin aprobación.

---

## 3. Evaluación de Despliegue: AWS vs GCP vs Estado Actual

Dado que el sistema está en fase de MVP (volumen bajo) y se busca un costo de **0 pesos (Free Tier ideal)** para procesamiento y almacenamiento de datos regulados (GDPR / HDS en Europa):

| Plataforma | Arquitectura Propuesta | Costo Estimado (MVP) | Pros | Contras |
| :--- | :--- | :--- | :--- | :--- |
| **A: Estado Actual (Local / VM Básica)** | Mantener `docker-compose` en 1 VM gratuita (AWS EC2 t2.micro o GCP e2-micro). | **$0/mes** | 100% control, cero migraciones de código (ya funciona). | Riesgo si la VM falla, no es escalable si el MVP crece súbitamente. RAM muy limitada para cargar XGBoost (1GB RAM). |
| **B: Google Cloud (Recomendado PaaS)** | Firebase Auth (Login Google), Cloud Run (para FastAPI), Firestore/Cloud SQL free tier, Firebase Hosting. | **$0/mes** | Escala a cero, excelente free tier para Cloud Run (2M peticiones). Autenticación segura y rápida con Google Sign-In. | Migrar de Postgres a Firestore es destructivo. Cloud SQL de Postgres NO es gratis perpetuamente. |
| **C: AWS (Serverless)** | Cognito, AWS Lambda + API Gateway, RDS (t3.micro), S3 (Modelos), Amplify (Next.js). | **$0/mes** (primeros 12 meses) | RDS incluye 12 meses gratis. Ecosistema robusto para salud. | Las lambdas con XGBoost sufren *cold starts* muy pesados. Complejidad alta de refactorización (`Mangum` para FastAPI). |

### **Recomendación Técnica y Económica**

Se recomienda **Mantener el stack relacional (PostgreSQL) usando Cloud Run (GCP) u otra solución de contenedores PaaS con free tier** para evitar reescribir la lógica de datos. 

Sin embargo, dado el objetivo de coste 0 y el límite de las instancias *free tier* convencionales (1 GB RAM), correr Postgres + Redis + 5 servicios FastAPI + Next.js en una sola capa es insostenible en Cloud (se requeriría al menos 4GB de RAM). 
**Plan de Migración Sugerido (Zero Cost):**
1. Unificar temporalmente los microservicios FastAPI en un **monolito modular** solo para el MVP. Esto reduce el *overhead* de 6 workers uvicorn a 1.
2. Desplegar este servicio backend unificado en **Render.com (Web Service Free)** o **GCP Cloud Run**.
3. Alojar la BD en una capa gratuita (e.g. Supabase Free Tier o Neon Serverless Postgres).
4. El Frontend Next.js puede ser alojado gratuitamente en **Vercel** o **Firebase Hosting**.

---

*(Las siguientes secciones se actualizarán conforme avance la auditoría)*

## 4. Auditoría de roles y permisos (RBAC/ABAC)

**Análisis completado.** Se detectaron fallos críticos de validación de propiedad de recursos (IDOR - Insecure Direct Object Reference) en el servicio `patient`.
1. **[CRÍTICA] Escalada Horizontal (Psiquiatras):** El endpoint `PUT /patients/{patient_id}` verifica que el rol sea psiquiatra, pero no valida la tabla de asignación (`PatientPsychiatrist`). Esto permite a cualquier doctor sobrescribir datos de pacientes ajenos.
2. **[CRÍTICA] IDOR en Módulos Sensibles:** Los endpoints `POST /mood`, `POST /health-data` y `PUT /consents` solo exigen estar autenticado (`get_current_user`), pero carecen por completo de verificación de autoría. Un paciente podría inyectar datos de sensores espurios o revocar consentimientos médicos de otro paciente cambiando el UUID en la ruta.

**Parches generados:** Se creó `proposals/rbac_fixes.md` con las correcciones requeridas (checks de autorización a nivel de servicio para FastAPI).
## 5. Pipeline de scoring del paciente

**Análisis completado.** El pipeline actual reside en `backend/src/scoring/pipeline.py`.
- **Comportamiento:**
  1. Carga un modelo `XGBoost` pre-entrenado desde el disco. Si falla o falta la librería, utiliza un **Modelo Heurístico** (Fallback) basado en pesos estáticos.
  2. Calcula Z-scores diarios (Ej. varianza del sueño, ritmo cardíaco) relativos a una Baseline histórica del paciente de al menos 3 días de data.
  3. Aplica penalizaciones absolutas (ej. sueño < 4 hrs = +25 pts de riesgo).
  4. Genera explicaciones (SHAP o aproximación heurística si XGBoost no está) y alertas si el score supera el umbral (40/60/80).
- **Pruebas de Regresión:** Creadas en `backend/tests/test_scoring_regression.py` para bloquear el comportamiento matemático actual del modelo heurístico antes de cualquier refactor.
- **Datasets Propuestos para Simulación:** 
  - [MIMIC-IV (PhysioNet)](https://physionet.org/content/mimiciv/): Ideal para datos vitales, requiere certificación DUA y CITI (No usar para prototipo abierto).
  - **Synthea (Synthetic Patient Population Simulator):** Generador de datos médicos sintéticos sin riesgo HIPAA/GDPR. Excelente para simular el PHQ-9 y datos wearables de pacientes virtuales.
- **Mejoras Propuestas:**
  1. **Tolerancia a Fallos de IoT:** Los Z-scores actuales fallan matemáticamente o emiten falsos positivos si el sensor de ritmo cardíaco arroja "0" por un mal contacto en la muñeca. Se requiere un paso de *Outlier Rejection* antes del pipeline.
  2. **Feature Leakage:** El modelo heurístico da peso al conteo de pasos y al tiempo de pantalla, variables altamente colineales. Reducir la dimensionalidad mejorará la interpretabilidad de SHAP.
## 7. Versiones y vulnerabilidades (CVEs)

**Análisis completado.** Se revisaron los manifiestos de dependencias (`backend/requirements.txt` y `frontend/dashboard/package.json`).

### Frontend (Next.js)
Las dependencias están actualizadas a sus versiones recientes (Next.js 14.2, React 18.3, Zustand 5). No se detectan librerías obsoletas ni dependencias con CVEs críticos públicos en las versiones mayores declaradas.

### Backend (Python / FastAPI)
Se detectaron dos paquetes con riesgo técnico y de seguridad:
1. **`python-jose` (CVE-2024-33663):** Esta librería está abandonada desde 2021 y posee vulnerabilidades conocidas de *Algorithm Confusion*.
   - **Parche sugerido:** Migrar a `PyJWT` para la validación y firma de tokens JWT.
2. **`passlib`:** Librería abandonada y con fallos de compatibilidad en versiones modernas de Python (depende de módulos de encriptación antiguos). 
   - **Parche sugerido:** Eliminar completamente de `requirements.txt`. El servicio `auth/main.py` ya fue refactorizado para usar `bcrypt` nativo, por lo que `passlib` es código muerto (dead-dependency).

**Parches generados:** Las instrucciones de actualización segura y el reemplazo de la librería JWT se documentarán en un PR de modernización una vez aprobado este reporte.

---
**Fin del Reporte de Auditoría Arquitectónica.**
