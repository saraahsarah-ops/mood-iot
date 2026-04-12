#!/usr/bin/env bash
# ============================================================================
# Mood-IoT : Script de Smoke Test automatise
# Teste tous les microservices et endpoints principaux
# Usage: bash scripts/smoke_test.sh
# ============================================================================

set -euo pipefail

# --- Configuration ---
AUTH_URL="http://localhost:8011"
PATIENT_URL="http://localhost:8012"
SCORING_URL="http://localhost:8013"
NOTIF_URL="http://localhost:8014"
TELECONSULT_URL="http://localhost:8015"
GATEWAY_URL="http://localhost:8010"

PASS=0
FAIL=0
WARN=0

# --- Helpers ---
green()  { printf "\033[32m%s\033[0m\n" "$1"; }
red()    { printf "\033[31m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
bold()   { printf "\033[1m%s\033[0m\n" "$1"; }

check() {
    local name="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -q "$expected"; then
        green "  PASS  $name"
        PASS=$((PASS + 1))
    else
        red "  FAIL  $name (expected: $expected)"
        echo "        Got: $(echo "$actual" | head -c 200)"
        FAIL=$((FAIL + 1))
    fi
}

check_status() {
    local name="$1" expected_code="$2" url="$3"
    shift 3
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "$@" "$url" 2>/dev/null || echo "000")
    if [ "$code" = "$expected_code" ]; then
        green "  PASS  $name (HTTP $code)"
        PASS=$((PASS + 1))
    else
        red "  FAIL  $name (expected HTTP $expected_code, got $code)"
        FAIL=$((FAIL + 1))
    fi
}

# ============================================================================
bold "======================================================"
bold "  MOOD-IOT SMOKE TEST"
bold "  $(date -Iseconds)"
bold "======================================================"

# --- 1. Health Checks ---
bold ""
bold "--- 1. HEALTH CHECKS ---"

R=$(curl -s "$GATEWAY_URL/api/v1/health" 2>/dev/null || echo "FAIL")
check "Gateway health" '"status":"healthy"' "$R"

for svc in auth patient scoring notification teleconsult; do
    check "Gateway -> $svc health" "\"$svc\":\"healthy\"" "$R"
done

check_status "Auth direct health" "200" "$AUTH_URL/auth/health"
check_status "Patient direct health" "200" "$PATIENT_URL/health"
check_status "Scoring direct health" "200" "$SCORING_URL/scoring/health"
check_status "Notification direct health" "200" "$NOTIF_URL/health"
check_status "Teleconsult direct health" "200" "$TELECONSULT_URL/teleconsult/health"

# --- 2. Auth Service ---
bold ""
bold "--- 2. AUTH SERVICE ---"

# Login psychiatre
LOGIN_DR=$(curl -s -X POST "$AUTH_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"dr.martin@mood-iot.fr","password":"MoodIoT2026!"}' 2>/dev/null)
check "Login psychiatre" '"token_type":"bearer"' "$LOGIN_DR"
check "Login returns user.role" '"role":"psychiatre"' "$LOGIN_DR"

DR_TOKEN=$(echo "$LOGIN_DR" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -z "$DR_TOKEN" ]; then
    red "  FATAL: Cannot extract access_token. Stopping auth tests."
    FAIL=$((FAIL + 10))
else
    # Login patient
    LOGIN_PAT=$(curl -s -X POST "$AUTH_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"sophie.dupont@email.fr","password":"MoodIoT2026!"}' 2>/dev/null)
    check "Login patient Sophie" '"role":"patient"' "$LOGIN_PAT"
    check "Patient first_name from DB" '"first_name":"Sophie"' "$LOGIN_PAT"
    PAT_TOKEN=$(echo "$LOGIN_PAT" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

    # Wrong password
    check_status "Login wrong password -> 401" "401" "$AUTH_URL/auth/login" \
        -X POST -H "Content-Type: application/json" \
        -d '{"email":"dr.martin@mood-iot.fr","password":"wrongpass"}'

    # GET /auth/me
    ME=$(curl -s "$AUTH_URL/auth/me" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
    check "GET /auth/me psychiatre" '"role":"psychiatre"' "$ME"

    ME_PAT=$(curl -s "$AUTH_URL/auth/me" -H "Authorization: Bearer $PAT_TOKEN" 2>/dev/null)
    check "GET /auth/me patient" '"first_name":"Sophie"' "$ME_PAT"

    # Refresh token
    REFRESH=$(echo "$LOGIN_DR" | python -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null)
    REFRESHED=$(curl -s -X POST "$AUTH_URL/auth/refresh" \
        -H "Content-Type: application/json" \
        -d "{\"refresh_token\":\"$REFRESH\"}" 2>/dev/null)
    check "Refresh token" '"token_type":"bearer"' "$REFRESHED"

    # Register new user
    RAND=$RANDOM
    REG=$(curl -s -X POST "$AUTH_URL/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"test${RAND}@test.fr\",\"password\":\"TestPass123!\",\"role\":\"patient\",\"first_name\":\"Test\",\"last_name\":\"User\"}" 2>/dev/null)
    check "Register new user" '"email":"test' "$REG"

    # Register duplicate
    check_status "Register duplicate -> 409" "409" "$AUTH_URL/auth/register" \
        -X POST -H "Content-Type: application/json" \
        -d "{\"email\":\"test${RAND}@test.fr\",\"password\":\"TestPass123!\",\"role\":\"patient\",\"first_name\":\"Test\",\"last_name\":\"User\"}"

    # MFA setup
    MFA=$(curl -s -X POST "$AUTH_URL/auth/mfa/setup" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
    check "MFA setup returns secret" '"secret":' "$MFA"
    check "MFA setup returns QR URL" 'otpauth://' "$MFA"

    # Logout
    LOGOUT=$(curl -s -X DELETE "$AUTH_URL/auth/logout" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
    check "Logout" '"message"' "$LOGOUT"

    # No token -> 401/403
    check_status "No token -> 401/403" "403" "$AUTH_URL/auth/me"
fi

# --- 3. Patient Service (PostgreSQL) ---
bold ""
bold "--- 3. PATIENT SERVICE (PostgreSQL) ---"

DR_TOKEN=$(curl -s -X POST "$AUTH_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"dr.martin@mood-iot.fr","password":"MoodIoT2026!"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

# List patients from seed data (PostgreSQL)
LIST_PAT=$(curl -s "$PATIENT_URL/patients" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
check "List patients from PostgreSQL" '"total":4' "$LIST_PAT"
check "Seed patient Sophie Dupont" '"first_name":"Sophie"' "$LIST_PAT"

# Get seed patient by ID
SOPHIE_ID="c0000000-0000-0000-0000-000000000001"
GET_PAT=$(curl -s "$PATIENT_URL/patients/$SOPHIE_ID" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
check "Get seed patient by ID" '"last_name":"Dupont"' "$GET_PAT"

# Submit PHQ-9 mood entry (persisted in PostgreSQL)
MOOD=$(curl -s -X POST "$PATIENT_URL/patients/$SOPHIE_ID/mood" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DR_TOKEN" \
    -d '{"phq9_scores":[1,2,1,0,2,1,0,1,0],"notes":"Test mood","sleep_hours":7,"activity_minutes":45}' 2>/dev/null)
check "Submit PHQ-9 mood entry" '"severity":"mild"' "$MOOD"
check "PHQ-9 total = 8" '"phq9_total":8' "$MOOD"

# Health data sync (PostgreSQL UPSERT)
SYNC=$(curl -s -X POST "$PATIENT_URL/patients/$SOPHIE_ID/health-data" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DR_TOKEN" \
    -d '{"date":"2026-04-12","heart_rate_avg":72,"sleep_duration_min":450,"step_count":8500,"source_platform":"android_health_connect"}' 2>/dev/null)
check "Health data sync (PostgreSQL)" '"source_platform":"android_health_connect"' "$SYNC"

# Batch health data
BATCH=$(curl -s -X POST "$PATIENT_URL/patients/$SOPHIE_ID/health-data/batch" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DR_TOKEN" \
    -d '[{"date":"2026-04-10","heart_rate_avg":70,"step_count":6000,"source_platform":"android_health_connect"},{"date":"2026-04-11","heart_rate_avg":75,"step_count":9000,"source_platform":"android_health_connect"}]' 2>/dev/null)
check "Batch health data sync" '"synced_count":2' "$BATCH"

# Invalid platform
check_status "Invalid platform -> 422" "422" "$PATIENT_URL/patients/$SOPHIE_ID/health-data" \
    -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $DR_TOKEN" \
    -d '{"date":"2026-04-12","source_platform":"invalid_platform"}'

# Consents from seed data
CONSENT=$(curl -s "$PATIENT_URL/patients/$SOPHIE_ID/consents" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
check "Get consents from PostgreSQL" '"data_collection":true' "$CONSENT"

# --- 4. Teleconsult Service (PostgreSQL) ---
bold ""
bold "--- 4. TELECONSULT SERVICE (PostgreSQL) ---"

# Create session
SESS=$(curl -s -X POST "$TELECONSULT_URL/teleconsult/sessions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DR_TOKEN" \
    -d '{"patient_id":"c0000000-0000-0000-0000-000000000001","psychiatre_id":"a0000000-0000-0000-0000-000000000001","scheduled_at":"2026-04-15T10:00:00Z","duration_minutes":30}' 2>/dev/null)
check "Create teleconsult session" '"status":"scheduled"' "$SESS"
check "Jitsi room generated" '"jitsi_room_name":"mood-iot-' "$SESS"

SESS_ID=$(echo "$SESS" | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)

# List sessions
LIST_SESS=$(curl -s "$TELECONSULT_URL/teleconsult/sessions" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
check "List teleconsult sessions" '"total":' "$LIST_SESS"

# --- 5. Scoring Service ---
bold ""
bold "--- 5. SCORING SERVICE ---"

HIST=$(curl -s "$SCORING_URL/scoring/history/b0000000-0000-0000-0000-000000000001" -H "Authorization: Bearer $DR_TOKEN" 2>/dev/null)
check "Scoring history endpoint" '"patient_id"' "$HIST"

# --- 6. Gateway Proxy ---
bold ""
bold "--- 6. GATEWAY PROXY ---"

GW_LOGIN=$(curl -s -X POST "$GATEWAY_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"dr.martin@mood-iot.fr","password":"MoodIoT2026!"}' 2>/dev/null)
check "Gateway -> Auth login proxy" '"token_type":"bearer"' "$GW_LOGIN"

GW_TOKEN=$(echo "$GW_LOGIN" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

GW_ME=$(curl -s "$GATEWAY_URL/api/v1/auth/me" -H "Authorization: Bearer $GW_TOKEN" 2>/dev/null)
check "Gateway -> Auth /me proxy" '"role":"psychiatre"' "$GW_ME"

GW_HEALTH=$(curl -s "$GATEWAY_URL/api/v1/scoring/health" 2>/dev/null)
check "Gateway -> Scoring health proxy" '"healthy"' "$GW_HEALTH"

# ============================================================================
bold ""
bold "======================================================"
bold "  RESULTS"
bold "======================================================"
green "  PASSED: $PASS"
if [ $FAIL -gt 0 ]; then
    red "  FAILED: $FAIL"
else
    green "  FAILED: $FAIL"
fi
bold "  TOTAL:  $((PASS + FAIL))"
bold "======================================================"

exit $FAIL
