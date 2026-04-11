import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# ─── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mood-IoT | Dashboard Médecin",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS PERSONNALISÉ ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Couleurs principales */
    :root {
        --primary: #0288d1;
        --primary-dark: #01579b;
        --primary-light: #b3e5fc;
        --success: #2ecc71;
        --warning: #f39c12;
        --danger: #e74c3c;
        --bg: #f0f7ff;
    }

    .stApp { background-color: #f0f7ff; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #01579b 0%, #0288d1 100%);
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] .stRadio label { color: white !important; }

    /* Cartes patientes */
    .card {
        background: white;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
        box-shadow: 0 2px 8px rgba(2,136,209,0.10);
        border-left: 5px solid #0288d1;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .card-red { border-left-color: #e74c3c; }
    .card-yellow { border-left-color: #f39c12; }
    .card-green { border-left-color: #2ecc71; }

    .card-name { font-size: 1.1rem; font-weight: 700; color: #01579b; }
    .card-score { font-size: 1.3rem; font-weight: 800; }
    .score-red { color: #e74c3c; }
    .score-yellow { color: #f39c12; }
    .score-green { color: #2ecc71; }
    .card-msg { font-size: 0.85rem; color: #555; margin-top: 4px; }

    /* Metric boxes */
    .metric-box {
        background: white;
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 2px 6px rgba(2,136,209,0.08);
        text-align: center;
    }
    .metric-title { font-size: 0.8rem; color: #888; text-transform: uppercase; }
    .metric-value { font-size: 1.6rem; font-weight: 800; color: #0288d1; }

    /* Notification badge */
    .notif {
        background: #e74c3c;
        color: white;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    /* Message bubbles */
    .bubble-medecin {
        background: #0288d1;
        color: white;
        border-radius: 16px 16px 4px 16px;
        padding: 10px 15px;
        margin: 6px 0;
        max-width: 70%;
        margin-left: auto;
        font-size: 0.9rem;
    }
    .bubble-patiente {
        background: white;
        color: #333;
        border-radius: 16px 16px 16px 4px;
        padding: 10px 15px;
        margin: 6px 0;
        max-width: 70%;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        font-size: 0.9rem;
    }
    .bubble-time { font-size: 0.7rem; color: #aaa; margin: 2px 4px; }

    /* Titre dashboard */
    .dashboard-title {
        font-size: 2rem;
        font-weight: 800;
        color: #01579b;
        margin-bottom: 0;
    }
    .dashboard-subtitle {
        color: #0288d1;
        font-size: 0.95rem;
        margin-bottom: 20px;
    }

    /* Bouton notification */
    .stButton > button {
        background: #0288d1;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: #01579b;
        color: white;
    }

    /* Section titre */
    .section-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #01579b;
        border-bottom: 2px solid #b3e5fc;
        padding-bottom: 6px;
        margin: 20px 0 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# ─── CHARGEMENT DONNÉES ────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    donnees = pd.read_csv("simulateur/donnees.csv")
    if os.path.exists("backend/scores.csv"):
        scores = pd.read_csv("backend/scores.csv")
    else:
        import numpy as np
        rows = []
        for p in donnees["patiente"].unique():
            for jour in range(8, 22):
                score = min(100, int((jour - 7) * 6 + np.random.randint(0, 10)))
                if score < 40:
                    niveau, msg = 1, "Continuez comme ça, votre routine est stable."
                elif score < 70:
                    niveau, msg = 2, "Votre sommeil semble perturbé. Essayez une courte marche aujourd'hui."
                else:
                    niveau, msg = 3, "Votre médecin a été informé et va vous contacter rapidement."
                rows.append({"patiente": p, "jour": jour, "score": score, "niveau": niveau, "message_coaching": msg})
        scores = pd.DataFrame(rows)
    return donnees, scores



placeholder = st.empty()
donnees, scores = load_data()

# ─── ÉTAT SESSION ──────────────────────────────────────────────────────────────
if "notifications" not in st.session_state:
    st.session_state.notifications = []
if "messages" not in st.session_state:
    st.session_state.messages = {
        "Sophie": [{"role": "patiente", "texte": "Bonjour docteur, je ne dors plus bien.", "heure": "09:12"}],
        "Marie":  [{"role": "patiente", "texte": "Je me sens très fatiguée ces derniers jours.", "heure": "10:45"}],
        "Léa":    [{"role": "patiente", "texte": "J'ai du mal à sortir de chez moi.", "heure": "11:30"}],
        "Anna":   [],
    }
if "commentaires" not in st.session_state:
    st.session_state.commentaires = {p: "" for p in donnees["patiente"].unique()}

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 10px 0 20px 0;'>
        <div style='font-size:2.5rem;'>🏥</div>
        <div style='font-size:1.2rem; font-weight:800; color:white;'>Mood-IoT</div>
        <div style='font-size:0.75rem; color:#b3e5fc;'>Dashboard Médecin</div>
    </div>
    """, unsafe_allow_html=True)

    # Nombre de notifications
    nb_notif = len([n for n in st.session_state.notifications if not n.get("lue")])
    notif_badge = f" 🔴 {nb_notif}" if nb_notif > 0 else ""

    page = st.radio("Navigation", [
        "🏠 Vue générale",
        "👤 Fiche patiente",
        f"🔔 Notifications{notif_badge}",
        "💬 Messagerie",
    ])

    st.markdown("---")
    st.markdown("<div style='font-size:0.8rem; color:#b3e5fc;'>Dr. Martin — Connecté</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.75rem; color:#b3e5fc;'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def get_couleur(niveau):
    return {1: ("#2ecc71", "green", "🟢"), 2: ("#f39c12", "yellow", "🟡"), 3: ("#e74c3c", "red", "🔴")}[niveau]

derniers_scores = scores.sort_values("jour").groupby("patiente").last().reset_index()
derniers_scores = derniers_scores.sort_values("niveau", ascending=False)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — VUE GÉNÉRALE
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Vue générale":
    st.markdown("<div class='dashboard-title'>🏥 Mood-IoT — Dashboard Médecin</div>", unsafe_allow_html=True)
    st.markdown("<div class='dashboard-subtitle'>Suivi en temps réel des patientes dépressives</div>", unsafe_allow_html=True)

    # KPIs
    nb_rouge = len(derniers_scores[derniers_scores["niveau"] == 3])
    nb_jaune = len(derniers_scores[derniers_scores["niveau"] == 2])
    nb_vert  = len(derniers_scores[derniers_scores["niveau"] == 1])
    score_moy = int(derniers_scores["score"].mean())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='metric-box'><div class='metric-title'>🔴 Alertes critiques</div><div class='metric-value' style='color:#e74c3c'>{nb_rouge}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-box'><div class='metric-title'>🟡 À surveiller</div><div class='metric-value' style='color:#f39c12'>{nb_jaune}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='metric-box'><div class='metric-title'>🟢 Stables</div><div class='metric-value' style='color:#2ecc71'>{nb_vert}</div></div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='metric-box'><div class='metric-title'>📊 Score moyen</div><div class='metric-value'>{score_moy}/100</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>État des patientes aujourd'hui</div>", unsafe_allow_html=True)

    for _, row in derniers_scores.iterrows():
        couleur, cls, emoji = get_couleur(row["niveau"])
        st.markdown(f"""
        <div class='card card-{cls}'>
            <div>
                <div class='card-name'>{emoji} {row['patiente']}</div>
                <div class='card-msg'>{row['message_coaching']}</div>
            </div>
            <div class='card-score score-{cls}'>{row['score']}/100</div>
        </div>
        """, unsafe_allow_html=True)

        if row["niveau"] == 3:
            col_a, col_b = st.columns([6, 1])
            with col_b:
                if st.button(f"🔔 Alerter", key=f"alert_{row['patiente']}"):
                    st.session_state.notifications.append({
                        "patiente": row["patiente"],
                        "score": row["score"],
                        "heure": datetime.now().strftime("%H:%M"),
                        "lue": False,
                        "message": f"Score critique de {row['score']}/100 détecté pour {row['patiente']}"
                    })
                    st.success(f"✅ Notification envoyée pour {row['patiente']} !")

    st.markdown("<div class='section-title'>Évolution des scores sur 21 jours</div>", unsafe_allow_html=True)
    fig = px.line(scores, x="jour", y="score", color="patiente",
                  color_discrete_sequence=["#0288d1", "#f39c12", "#e74c3c", "#2ecc71"],
                  line_shape="spline")
    fig.add_hline(y=40, line_dash="dash", line_color="#f39c12", annotation_text="Seuil niveau 2")
    fig.add_hline(y=70, line_dash="dash", line_color="#e74c3c", annotation_text="Seuil niveau 3")
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="#f8fbff",
                      font=dict(color="#01579b"), legend_title="Patiente")
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — FICHE PATIENTE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👤 Fiche patiente":
    st.markdown("<div class='dashboard-title'>👤 Fiche détaillée — Patiente</div>", unsafe_allow_html=True)

    patiente = st.selectbox("Choisir une patiente", donnees["patiente"].unique())
    score_row = scores[scores["patiente"] == patiente].sort_values("jour").iloc[-1]
    couleur, cls, emoji = get_couleur(int(score_row["niveau"]))

    st.markdown(f"<h2 style='color:{couleur}'>{emoji} Score du jour : {score_row['score']}/100</h2>", unsafe_allow_html=True)

    data_p = donnees[donnees["patiente"] == patiente]
    baseline = data_p[data_p["jour"] <= 7]

    # Métriques comparées à la baseline
    m1, m2, m3, m4 = st.columns(4)
    metrics = [
        ("👟 Pas", "pas", int(baseline["pas"].mean()), int(data_p.iloc[-1]["pas"])),
        ("😴 Sommeil", "sommeil_heures", round(baseline["sommeil_heures"].mean(), 1), round(data_p.iloc[-1]["sommeil_heures"], 1)),
        ("❤️ BPM", "battements_coeur", int(baseline["battements_coeur"].mean()), int(data_p.iloc[-1]["battements_coeur"])),
        ("📱 Écran", "temps_ecran_heures", round(baseline["temps_ecran_heures"].mean(), 1), round(data_p.iloc[-1]["temps_ecran_heures"], 1)),
    ]
    for col, (label, _, base_val, curr_val) in zip([m1, m2, m3, m4], metrics):
        delta = curr_val - base_val
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        with col:
            st.markdown(f"""
            <div class='metric-box'>
                <div class='metric-title'>{label}</div>
                <div class='metric-value'>{curr_val}</div>
                <div style='font-size:0.8rem; color:{"#e74c3c" if delta < 0 else "#f39c12"}'>{delta_str} vs baseline</div>
            </div>
            """, unsafe_allow_html=True)

    # Graphiques
    st.markdown("<div class='section-title'>Évolution sur 21 jours</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    graphiques = [
        (col1, "pas", "👟 Pas par jour", "#0288d1"),
        (col2, "sommeil_heures", "😴 Sommeil (heures)", "#9c27b0"),
        (col3, "battements_coeur", "❤️ Battements de cœur", "#e74c3c"),
    ]
    for col, metric, titre, couleur_g in graphiques:
        with col:
            fig = px.line(data_p, x="jour", y=metric, title=titre,
                          color_discrete_sequence=[couleur_g], line_shape="spline")
            fig.add_vline(x=7, line_dash="dash", line_color="red", annotation_text="Fin baseline")
            fig.update_layout(paper_bgcolor="white", plot_bgcolor="#f8fbff",
                              font=dict(color="#01579b"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Commentaires médecin
    st.markdown("<div class='section-title'>📝 Analyse du médecin</div>", unsafe_allow_html=True)
    commentaire = st.text_area(
        f"Vos observations pour {patiente}",
        value=st.session_state.commentaires[patiente],
        placeholder="Ex : Augmentation notable de la fréquence cardiaque depuis J12. Prévoir appel téléphonique...",
        height=100
    )
    col_save, col_info = st.columns([1, 4])
    with col_save:
        if st.button("💾 Enregistrer"):
            st.session_state.commentaires[patiente] = commentaire
            st.success("Analyse enregistrée !")
    with col_info:
        if st.session_state.commentaires[patiente]:
            st.info(f"💬 Dernière analyse : {st.session_state.commentaires[patiente][:80]}...")

    st.markdown(f"<div style='background:white;border-radius:10px;padding:14px;margin-top:10px;border-left:4px solid {couleur};'>"
                f"<b>Message coaching IA :</b> {score_row['message_coaching']}</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════
elif "Notifications" in page:
    st.markdown("<div class='dashboard-title'>🔔 Notifications</div>", unsafe_allow_html=True)

    # Auto-générer notifications pour les niveaux 3
    for _, row in derniers_scores[derniers_scores["niveau"] == 3].iterrows():
        existe = any(n["patiente"] == row["patiente"] for n in st.session_state.notifications)
        if not existe:
            st.session_state.notifications.append({
                "patiente": row["patiente"],
                "score": row["score"],
                "heure": "Automatique",
                "lue": False,
                "message": f"Alerte critique : score de {row['score']}/100 pour {row['patiente']}"
            })

    if not st.session_state.notifications:
        st.success("✅ Aucune notification pour le moment.")
    else:
        if st.button("✅ Tout marquer comme lu"):
            for n in st.session_state.notifications:
                n["lue"] = True

        for i, notif in enumerate(st.session_state.notifications):
            bg = "white" if notif["lue"] else "#fff3cd"
            st.markdown(f"""
            <div style='background:{bg};border-radius:10px;padding:14px 18px;
                        margin:8px 0;box-shadow:0 2px 6px rgba(0,0,0,0.08);
                        border-left:4px solid {"#aaa" if notif["lue"] else "#e74c3c"}'>
                <b>🔴 {notif["patiente"]}</b> — Score : {notif["score"]}/100
                <span style='float:right;font-size:0.8rem;color:#888'>{notif["heure"]}</span>
                <br><span style='font-size:0.85rem;color:#555'>{notif["message"]}</span>
                {"<br><span style='font-size:0.75rem;color:#aaa'>✓ Lu</span>" if notif["lue"] else ""}
            </div>
            """, unsafe_allow_html=True)

            if not notif["lue"]:
                if st.button(f"Marquer comme lu", key=f"lu_{i}"):
                    st.session_state.notifications[i]["lue"] = True
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — MESSAGERIE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💬 Messagerie":
    st.markdown("<div class='dashboard-title'>💬 Messagerie</div>", unsafe_allow_html=True)

    patiente = st.selectbox("Conversation avec", donnees["patiente"].unique())
    score_row = derniers_scores[derniers_scores["patiente"] == patiente].iloc[0]
    couleur, cls, emoji = get_couleur(int(score_row["niveau"]))

    st.markdown(f"<div style='margin-bottom:12px'>{emoji} <b>{patiente}</b> — Score : <b style='color:{couleur}'>{score_row['score']}/100</b></div>", unsafe_allow_html=True)

    # Affichage messages
    st.markdown("<div style='background:white;border-radius:12px;padding:16px;min-height:200px;max-height:350px;overflow-y:auto;box-shadow:0 2px 8px rgba(2,136,209,0.08)'>", unsafe_allow_html=True)
    if not st.session_state.messages[patiente]:
        st.markdown("<div style='color:#aaa;text-align:center;padding:40px'>Aucun message pour l'instant</div>", unsafe_allow_html=True)
    for msg in st.session_state.messages[patiente]:
        if msg["role"] == "medecin":
            st.markdown(f"<div style='text-align:right'><div class='bubble-medecin'>{msg['texte']}</div><div class='bubble-time'>{msg['heure']}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div><div class='bubble-patiente'>{msg['texte']}</div><div class='bubble-time'>{msg['heure']}</div></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Envoi message
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    col_msg, col_btn = st.columns([5, 1])
    with col_msg:
        nouveau = st.text_input("Votre message", placeholder="Écrire un message...", label_visibility="collapsed")
    with col_btn:
        if st.button("📤 Envoyer"):
            if nouveau.strip():
                st.session_state.messages[patiente].append({
                    "role": "medecin",
                    "texte": nouveau,
                    "heure": datetime.now().strftime("%H:%M")
                })
                st.rerun()

    # Messages rapides
    st.markdown("<div style='margin-top:8px;font-size:0.8rem;color:#888'>Messages rapides :</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    messages_rapides = [
        ("📞 Appel prévu", "Je vous appelle dans la journée pour faire le point."),
        ("💊 Rappel médicament", "Pensez à prendre votre traitement ce soir."),
        ("🌟 Encouragement", "Vous faites du bon travail, continuez ainsi !"),
    ]
    for col, (label, texte) in zip([c1, c2, c3], messages_rapides):
        with col:
            if st.button(label, key=f"rapide_{label}"):
                st.session_state.messages[patiente].append({
                    "role": "medecin",
                    "texte": texte,
                    "heure": datetime.now().strftime("%H:%M")
                })
                st.rerun()
