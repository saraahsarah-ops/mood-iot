import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Mood-IoT — Dashboard Médecin", layout="wide")

# Chargement des données
@st.cache_data
def load_data():
    donnees = pd.read_csv("simulateur/donnees.csv")
    
    if os.path.exists("backend/scores.csv"):
        scores = pd.read_csv("backend/scores.csv")
    else:
        # Données fictives si scores.csv n'existe pas encore
        import numpy as np
        rows = []
        patientes = donnees["patiente"].unique()
        for p in patientes:
            for jour in range(8, 22):
                score = min(100, int((jour - 7) * 6 + np.random.randint(0, 10)))
                if score < 40:
                    niveau = 1
                    msg = "Continuez comme ça, votre routine est stable."
                elif score < 70:
                    niveau = 2
                    msg = "Votre sommeil semble perturbé. Essayez une courte marche aujourd'hui."
                else:
                    niveau = 3
                    msg = "Votre médecin a été informé et va vous contacter rapidement."
                rows.append({"patiente": p, "jour": jour, "score": score, "niveau": niveau, "message_coaching": msg})
        scores = pd.DataFrame(rows)
    return donnees, scores

donnees, scores = load_data()

# Navigation
page = st.sidebar.radio("Navigation", ["Vue générale", "Fiche patiente"])

if page == "Vue générale":
    st.title("Mood-IoT — Dashboard Médecin")
    
    # Dernier score de chaque patiente
    derniers_scores = scores.sort_values("jour").groupby("patiente").last().reset_index()
    
    def couleur_niveau(niveau):
        if niveau == 1:
            return "🟢"
        elif niveau == 2:
            return "🟡"
        else:
            return "🔴"
    
    derniers_scores["alerte"] = derniers_scores["niveau"].apply(couleur_niveau)
    derniers_scores = derniers_scores.sort_values("niveau", ascending=False)
    
    st.subheader("État des patientes aujourd'hui")
    for _, row in derniers_scores.iterrows():
        st.markdown(f"**{row['alerte']} {row['patiente']}** — Score : {row['score']}/100 — {row['message_coaching']}")
    
    st.subheader("Évolution des scores sur 21 jours")
    fig = px.line(scores, x="jour", y="score", color="patiente",
                  color_discrete_sequence=["#2ecc71", "#f39c12", "#e74c3c", "#3498db"])
    fig.add_hline(y=40, line_dash="dash", line_color="#f39c12", annotation_text="Seuil niveau 2")
    fig.add_hline(y=70, line_dash="dash", line_color="#e74c3c", annotation_text="Seuil niveau 3")
    st.plotly_chart(fig, use_container_width=True)

elif page == "Fiche patiente":
    st.title("Fiche détaillée — Patiente")
    
    patiente = st.selectbox("Choisir une patiente", donnees["patiente"].unique())
    
    score_du_jour = scores[scores["patiente"] == patiente].sort_values("jour").iloc[-1]
    niveau = score_du_jour["niveau"]
    
    if niveau == 1:
        couleur = "#2ecc71"
        emoji = "🟢"
    elif niveau == 2:
        couleur = "#f39c12"
        emoji = "🟡"
    else:
        couleur = "#e74c3c"
        emoji = "🔴"
    
    st.markdown(f"<h2 style='color:{couleur}'>{emoji} Score du jour : {score_du_jour['score']}/100</h2>", unsafe_allow_html=True)
    
    data_patiente = donnees[donnees["patiente"] == patiente]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fig1 = px.line(data_patiente, x="jour", y="pas", title="Pas par jour")
        fig1.add_vline(x=7, line_dash="dash", line_color="red", annotation_text="Fin baseline")
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        fig2 = px.line(data_patiente, x="jour", y="sommeil_heures", title="Sommeil (heures)")
        fig2.add_vline(x=7, line_dash="dash", line_color="red", annotation_text="Fin baseline")
        st.plotly_chart(fig2, use_container_width=True)
    
    with col3:
        fig3 = px.line(data_patiente, x="jour", y="battements_coeur", title="Battements de cœur")
        fig3.add_vline(x=7, line_dash="dash", line_color="red", annotation_text="Fin baseline")
        st.plotly_chart(fig3, use_container_width=True)
    
    st.info(f"💬 {score_du_jour['message_coaching']}")