"""
Tests E2E backend (système DÉPLOYÉ — https://api.mood-iot.fr) des flux médecin.

Couvre : modification du profil médecin, création/suppression de patient,
cycle de téléconsultation (créer/lien Jitsi/notes/terminer), envoi de message
au patient.

Identifiants via variables d'environnement (jamais en dur) :
    MOODIOT_USER  (def. dr.martin@example.test)
    MOODIOT_PASS  (OBLIGATOIRE)

Lancement (PowerShell) :
    $env:MOODIOT_PASS = "Martin2026!"
    python qa/e2e_backend.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://auth.mood-iot.fr/realms/moodiot/protocol/openid-connect/token"
API = "https://api.mood-iot.fr/api/v1"
USER = os.environ.get("MOODIOT_USER", "dr.martin@example.test")
PASS = os.environ.get("MOODIOT_PASS")

results = []
created = {}  # ids créés (pour le nettoyage)


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
    """Retourne (status, json|texte)."""
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt


def main():
    if not PASS:
        print("ERREUR : MOODIOT_PASS non définie.")
        sys.exit(1)

    print("\n=== Tests E2E backend Mood-IoT (DÉPLOYÉ) ===")
    print(f"Médecin : {USER}\n")

    token = get_token()
    print("[0] Token psychiatre obtenu (OIDC password grant)\n")

    # user_id du médecin (psychiatre_id pour les sessions)
    st, me = api("GET", "/auth/me", token)
    psy_id = me.get("id") or me.get("user_id") if isinstance(me, dict) else None
    print(f"[me] user_id médecin = {psy_id}\n")

    # --- 1. Modifier le profil médecin (PUT /doctor/me) -----------------
    print("[1] Modifier les données du médecin")
    st, cur = api("GET", "/doctor/me", token)
    orig_spec = cur.get("speciality") if isinstance(cur, dict) else None
    st2, upd = api("PUT", "/doctor/me", token, {"speciality": "QA-Test-Speciality"})
    st3, ver = api("GET", "/doctor/me", token)
    new_spec = ver.get("speciality") if isinstance(ver, dict) else None
    ok = st2 == 200 and new_spec == "QA-Test-Speciality"
    record("TC-UC9-MODMED", "Modification du profil médecin (PUT /doctor/me)", ok,
           f"GET={st}, PUT={st2}, speciality '{orig_spec}' -> '{new_spec}'")
    # revert
    if orig_spec is not None:
        api("PUT", "/doctor/me", token, {"speciality": orig_spec})
        print(f"       (speciality remise à '{orig_spec}')")

    # --- 2. Créer un patient (POST /patients) + supprimer ---------------
    print("[2] Créer un nouveau patient")
    body = {"first_name": "QATest", "last_name": "Patient", "gender": "female",
            "date_of_birth": "1990-01-01", "email": "qatest.patient@sim.test"}
    if psy_id:
        body["psychiatre_id"] = psy_id
    st, res = api("POST", "/patients", token, body)
    new_id = res.get("id") if isinstance(res, dict) else None
    created["patient"] = new_id
    record("TC-UC4-CREATE", "Création d'un nouveau patient (POST /patients)",
           st in (200, 201) and bool(new_id), f"POST /patients -> {st}, id={new_id}")
    if new_id:
        dst, _ = api("DELETE", f"/patients/{new_id}", token)
        print(f"       (patient test supprimé -> {dst})")

    # --- 3. Téléconsultation : créer -> lien Jitsi -> notes -> terminer --
    print("[3] Cycle téléconsultation")
    sess_body = {"patient_id": "d3f58dcd-eeef-45ff-84c9-5bb59e902f01",  # Hugo
                 "psychiatre_id": psy_id, "scheduled_at": "2026-07-01T15:00:00",
                 "duration_minutes": 30, "reason": "QA test cycle"}
    st, s = api("POST", "/teleconsult/sessions", token, sess_body)
    sid = s.get("id") if isinstance(s, dict) else None
    jitsi = s.get("jitsi_url") if isinstance(s, dict) else None
    created["session"] = sid
    record("TC-UC5-03", "Téléconsultation : créer une session + lien Jitsi (join)",
           st in (200, 201) and bool(jitsi), f"POST -> {st}, jitsi_url={jitsi}")

    if sid:
        st, n = api("POST", f"/teleconsult/sessions/{sid}/notes", token,
                    {"content": "Note clinique de test QA", "note_type": "observation"})
        record("TC-UC5-04", "Téléconsultation : ajouter une note clinique",
               st in (200, 201), f"POST notes -> {st}")
        st, e = api("PUT", f"/teleconsult/sessions/{sid}/end", token)
        new_status = e.get("status") if isinstance(e, dict) else None
        record("TC-UC5-05", "Téléconsultation : terminer la session",
               st == 200, f"PUT /end -> {st}, status={new_status}")

    # --- 4. Envoyer un message au patient -------------------------------
    print("[4] Envoyer un message au patient")
    st, m = api("POST", "/teleconsult/messages/d3f58dcd-eeef-45ff-84c9-5bb59e902f01",
                token, {"content": "Message de test QA au patient."})
    record("TC-UC9-15", "Messagerie : envoyer un message au patient",
           st in (200, 201), f"POST message -> {st}")

    out = "resultats_backend.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"results": results, "created": created}, f, ensure_ascii=False, indent=2)
    reussis = sum(1 for r in results if r["statut"] == "Réussi")
    print(f"\n=== Résumé : {reussis}/{len(results)} Réussi ===")
    print(f"IDs créés (à nettoyer) : {created}")
    print(f"JSON : {out}\n")


if __name__ == "__main__":
    main()
