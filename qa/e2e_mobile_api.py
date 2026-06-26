"""
Tests E2E des flux côté APP MOBILE (patient), via l'API DÉPLOYÉE.

Teste les endpoints que l'app patient appelle réellement : résolution du
patient, synchronisation des données capteurs (UPSERT), statut de sync,
enregistrement du token push, historique de score, messages.

NB : ne couvre PAS le natif du téléphone (Health Connect, lecture réelle des
capteurs, permission push, safe-area) — ça se confirme sur l'appareil.

Identifiant patient via variable d'environnement :
    MOODIOT_PATIENT_PASS  (mot de passe de marie.dupont@example.test)

Lancement (PowerShell) :
    $env:MOODIOT_PATIENT_PASS = "Marie2026!"
    python qa/e2e_mobile_api.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://auth.mood-iot.fr/realms/moodiot/protocol/openid-connect/token"
API = "https://api.mood-iot.fr/api/v1"
USER = os.environ.get("MOODIOT_PATIENT_USER", "marie.dupont@example.test")
PASS = os.environ.get("MOODIOT_PATIENT_PASS")
TEST_DATE = "2026-05-15"  # hors de la plage du simulateur, facile à nettoyer

results = []


def record(tc, nom, ok, detail):
    results.append({"tc": tc, "nom": nom, "statut": "Réussi" if ok else "Échoué", "detail": detail})
    print(f"  {'OK ' if ok else 'XX '}{tc}  {nom}  ->  {'Réussi' if ok else 'Échoué'}")
    if detail:
        print(f"       {detail}")


def get_token():
    data = urllib.parse.urlencode({
        "client_id": "mobile-app", "grant_type": "password", "scope": "openid",
        "username": USER, "password": PASS,
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(AUTH_URL, data=data), timeout=30) as r:
        return json.loads(r.read())["access_token"]


def api(method, path, token, body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt.strip() else {})
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt


def main():
    if not PASS:
        print("ERREUR : MOODIOT_PATIENT_PASS non définie.")
        sys.exit(1)

    print("\n=== Tests E2E flux app mobile (patient, DÉPLOYÉ) ===")
    print(f"Patient : {USER}\n")
    token = get_token()
    print("[0] Token patient obtenu (OIDC password grant)\n")

    # --- 1. Résolution patient.id (GET /patients/me) --------------------
    print("[1] Résolution du patient")
    st, me = api("GET", "/patients/me", token)
    pid = me.get("id") if isinstance(me, dict) else None
    record("TC-UC10-ME", "GET /patients/me résout patient.id",
           st == 200 and bool(pid), f"-> {st}, patient.id={pid}, nom={me.get('first_name') if isinstance(me, dict) else '?'}")

    # --- 2. Sync données capteurs + UPSERT (UC10-16) --------------------
    print("[2] Envoi des données capteurs (UPSERT)")
    payload = {
        "date": TEST_DATE, "heart_rate_avg": 68.0, "heart_rate_variability": 42.0,
        "sleep_duration_min": 430, "step_count": 7200, "screen_time_min": 310,
        "call_count": 3, "gps_radius_km": 2.4,
        "source_platform": "android_health_connect",
    }
    st1, r1 = api("POST", "/patients/me/health-data", token, payload)
    # 2e envoi même date -> doit UPSERT (pas d'erreur de doublon)
    payload2 = {**payload, "step_count": 9000}
    st2, r2 = api("POST", "/patients/me/health-data", token, payload2)
    record("TC-UC10-16", "Envoi des données capteurs au backend (POST health-data)",
           st1 in (200, 201), f"1er POST -> {st1}")
    record("TC-UC10-16b", "Idempotence/UPSERT (2e POST même date)",
           st2 in (200, 201), f"2e POST même date -> {st2} (doit rester OK, pas de doublon)")

    # --- 3. Statut de synchronisation -----------------------------------
    print("[3] Statut de synchronisation")
    st, status = api("GET", "/patients/me/health-data/status", token)
    record("TC-UC10-STATUS", "Statut de synchronisation des données",
           st == 200, f"-> {st} : {json.dumps(status)[:120] if isinstance(status, dict) else status}")

    # --- 4. Enregistrement token push (UC10-14 côté backend) ------------
    print("[4] Enregistrement du token push")
    st, _ = api("PUT", "/patients/me/device-token", token, {"device_token": "qa-test-fcm-token-DELETEME"})
    record("TC-UC10-14b", "Enregistrement du token push (PUT device-token)",
           st in (200, 204), f"PUT device-token -> {st}")

    # --- 5. Historique de score (ce que l'app affiche) ------------------
    print("[5] Historique de score")
    st, hist = api("GET", f"/scoring/history/{pid}", token) if pid else (0, {})
    n = len(hist.get("scores", [])) if isinstance(hist, dict) else 0
    record("TC-UC10-HIST", "Historique de score accessible par le patient",
           st == 200, f"-> {st}, {n} scores")

    # --- 6. Messages ----------------------------------------------------
    print("[6] Messages du patient")
    st, msgs = api("GET", "/patients/me/messages", token)
    record("TC-UC10-MSG", "Messages du patient accessibles",
           st == 200, f"-> {st}")

    out = "resultats_mobile_api.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"results": results, "test_date": TEST_DATE, "patient_id": pid}, f, ensure_ascii=False, indent=2)
    reussis = sum(1 for r in results if r["statut"] == "Réussi")
    print(f"\n=== Résumé : {reussis}/{len(results)} Réussi ===")
    print(f"(nettoyage : supprimer les données de test du {TEST_DATE} + reset device_token)")
    print(f"JSON : {out}\n")


if __name__ == "__main__":
    main()
