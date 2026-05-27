# Propuestas de Corrección: Auditoría RBAC y Autorización (IDOR)

Durante la auditoría del servicio de pacientes (`patient/main.py`), se identificaron varias vulnerabilidades críticas de Insecure Direct Object Reference (IDOR) y falta de control de acceso a nivel de recurso.

### Hallazgo 1: IDOR en `update_patient` (PUT `/patients/{patient_id}`)
**Riesgo:** Crítica.
**Problema:** El endpoint exige que el rol sea "psychiatre" o "admin", pero no valida si el "psychiatre" está asignado al paciente que intenta modificar. Cualquier psiquiatra autenticado puede sobrescribir datos de pacientes de otros colegas.

**Parche sugerido (`patient/main.py`):**
```python
# ANTES
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None: ...

# DESPUÉS
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None: ...
    
    # NUEVA VALIDACION
    if current_user["role"] == "psychiatre":
        check = await db.execute(
            select(PatientPsychiatrist).where(
                and_(
                    PatientPsychiatrist.patient_id == patient_id,
                    PatientPsychiatrist.psychiatrist_id == current_user["user_id"],
                )
            )
        )
        if check.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Vous n'etes pas assigne a ce patient")
```

### Hallazgo 2: IDOR masivo en Endpoints Clínicos y de IoT
**Archivos afectados:** `patient/main.py`
**Endpoints:**
- `POST /patients/{patient_id}/mood`
- `GET /patients/{patient_id}/consents`
- `PUT /patients/{patient_id}/consents`
- `POST /patients/{patient_id}/health-data`

**Riesgo:** Crítica.
**Problema:** Estos endpoints utilizan `get_current_user` pero no validan que el `user_id` del token JWT coincida con el `user_id` del `patient_id` objetivo en la BD. Un paciente malicioso puede inyectar datos de salud falsos (Health Connect) o scores PHQ-9 alterados al expediente de otro paciente simplemente iterando UUIDs en la URL.

**Parche sugerido (Aplicable a los 4 endpoints):**
Se debe recuperar el `patient` de la BD y validar la autoría:
```python
# Insertar justo después de recuperar el paciente de la BD:
    if current_user["role"] == "patient" and str(patient.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Acces refuse - Vous ne pouvez modifier que vos propres donnees")
```
