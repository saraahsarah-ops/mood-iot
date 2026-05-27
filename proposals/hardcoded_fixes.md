# Propuestas de Corrección: Valores Hardcodeados

Se han detectado múltiples instancias de contraseñas y credenciales incrustadas directamente en el código o con valores por defecto inseguros. Para cumplir con el requerimiento de seguridad, se proponen los siguientes cambios sin romper la funcionalidad (usando variables de entorno con `python-dotenv` y validación).

### Hallazgo 1: Contraseñas en scripts de QA y Testing

**Archivos afectados:**
- `qa/record_demo.py` (Línea 16: `PASSWORD = "MoodIoT2026!"`)
- `qa/test_dashboard.py` (Línea 28: `PASSWORD = "MoodIoT2026!"`)

**Riesgo:** Alta. Las credenciales de prueba suelen filtrarse a producción o ser utilizadas en ataques de fuerza bruta si el seed de la DB no se limpia.

**Parche sugerido (Python):**

```python
# ANTES
PASSWORD = "MoodIoT2026!"

# DESPUÉS
import os
from dotenv import load_dotenv

load_dotenv()
PASSWORD = os.getenv("TEST_USER_PASSWORD")
if not PASSWORD:
    raise ValueError("Falta la variable de entorno TEST_USER_PASSWORD")
```

### Hallazgo 2: Valores por defecto en `docker-compose.yml`

**Archivos afectados:**
- `docker-compose.yml` (Múltiples líneas)

**Riesgo:** Media. Aunque usan la sintaxis de fallback (`${VAR:-default}`), los valores como `mood_secret_2026` y `change-me-in-production` están versionados en Git. Un despliegue accidental sin `.env` usaría claves conocidas públicamente.

**Parche sugerido (`docker-compose.yml`):**

```yaml
# ANTES
JWT_SECRET_KEY=${JWT_SECRET_KEY:-change-me-in-production}
DATABASE_URL=${DATABASE_URL:-postgresql://mood_user:mood_secret_2026@postgres:5432/mood_iot}

# DESPUÉS (Forzar el fallo si no existe la variable)
JWT_SECRET_KEY=${JWT_SECRET_KEY:?Error: JWT_SECRET_KEY no está definida}
DATABASE_URL=${DATABASE_URL:?Error: DATABASE_URL no está definida}
```

*Nota: Esto requerirá que exista un archivo `.env` válido localmente o variables inyectadas por el CI/CD.*
