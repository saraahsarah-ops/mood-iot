import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Mood-IoT — App Patient",
    page_icon="💙",
    layout="centered",
)

# CSS global : fond blanc, cartes arrondies
st.markdown("""
<style>
    .main { background-color: #ffffff; }
    .card {
        background: #f8f9fe;
        border-radius: 16px;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    }
    .card-green  { border-left: 5px solid #2ecc71; }
    .card-yellow { border-left: 5px solid #f1c40f; }
    .card-red    { border-left: 5px solid #e74c3c; }
    .score-big {
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        margin: 8px 0;
    }
    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-label { color: #555; font-size: 0.95rem; }
    .metric-value { font-weight: 700; font-size: 1.1rem; }
    .metric-delta { font-size: 0.85rem; color: #888; }
    .alert-box {
        background: #fdecea;
        border: 1.5px solid #e74c3c;
        border-radius: 12px;
        padding: 14px 18px;
        color: #c0392b;
        font-weight: 600;
        text-align: center;
        margin-top: 12px;
    }
    .coaching-box {
        border-radius: 12px;
        padding: 14px 18px;
        margin-top: 16px;
        font-size: 1rem;
    }
    .stSelectbox > div { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent

@st.cache_data
def load_data():
    donnees = pd.read_csv(BASE_DIR / "simulateur" / "donnees.csv")
    scores  = pd.read_csv(BASE_DIR / "backend"    / "scores.csv")
    donnees["date"] = pd.to_datetime(donnees["date"])
    scores["date"]  = pd.to_datetime(scores["date"])
    return donnees, scores

donnees, scores = load_data()

# Baseline par patiente (jours 1-7)
baseline = (
    donnees[donnees["jour"] <= 7]
    .groupby("patiente")[["pas", "sommeil_heures", "battements_coeur", "temps_ecran_heures"]]
    .mean()
)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
page = st.sidebar.radio(
    "Navigation",
    ["📊 Mon suivi aujourd'hui", "📈 Mon historique"],
    label_visibility="collapsed",
)

PATIENTES = ["Sophie", "Marie", "Léa", "Anna"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def score_ui(niveau):
    if niveau == 1:
        return "🟢", "#2ecc71", "Niveau 1 — Tout va bien", "card-green"
    elif niveau == 2:
        return "🟡", "#f39c12", "Niveau 2 — Quelques signaux", "card-yellow"
    else:
        return "🔴", "#e74c3c", "Niveau 3 — Attention requise", "card-red"


def fleche_delta(val, ref, plus_haut_est_mauvais=True):
    """Retourne emoji flèche + texte delta."""
    diff = val - ref
    pct  = (diff / ref * 100) if ref != 0 else 0
    if abs(pct) < 2:
        arrow = "➡️"
    elif diff > 0:
        arrow = "📈" if not plus_haut_est_mauvais else "📈"
    else:
        arrow = "📉"
    return arrow, f"{pct:+.0f}%"


def metric_card(label, value_str, arrow, delta_str, card_class="card"):
    st.markdown(f"""
    <div class="card {card_class}">
        <div class="metric-row">
            <span class="metric-label">{label}</span>
            <span>
                <span class="metric-value">{value_str}</span>&nbsp;
                <span>{arrow}</span>&nbsp;
                <span class="metric-delta">{delta_str} vs normale</span>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE 1 — Mon suivi aujourd'hui
# ---------------------------------------------------------------------------
if page == "📊 Mon suivi aujourd'hui":

    patiente = st.selectbox("Choisir une patiente", PATIENTES, key="p1")
    st.markdown(f"## Bonjour {patiente} 👋")

    # Dernier jour disponible
    data_p   = donnees[donnees["patiente"] == patiente].sort_values("jour")
    scores_p = scores[scores["patiente"] == patiente].sort_values("jour")
    last_row  = data_p.iloc[-1]
    last_score = scores_p.iloc[-1]

    niveau = int(last_score["niveau"])
    emoji, color, label_score, card_class = score_ui(niveau)

    # --- Score du jour ---
    st.markdown(f"""
    <div class="card {card_class}" style="text-align:center; padding: 24px;">
        <div style="color:{color}; font-size:3rem; font-weight:800;">{emoji} {label_score}</div>
        <div style="color:#888; font-size:0.85rem; margin-top:4px;">
            Jour {int(last_row['jour'])} — {last_row['date'].strftime('%d %B %Y')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Métriques du jour ---
    st.markdown("### 📋 Mes métriques du jour")
    ref = baseline.loc[patiente]

    pas_val   = int(last_row["pas"])
    somm_val  = float(last_row["sommeil_heures"])
    bpm_val   = int(last_row["battements_coeur"])
    ecran_val = float(last_row["temps_ecran_heures"])

    arrow, delta = fleche_delta(pas_val,   ref["pas"],                  plus_haut_est_mauvais=False)
    metric_card("🚶 Pas", f"{pas_val:,}", arrow, delta)

    arrow, delta = fleche_delta(somm_val,  ref["sommeil_heures"],        plus_haut_est_mauvais=False)
    metric_card("😴 Sommeil", f"{somm_val:.1f} h", arrow, delta)

    arrow, delta = fleche_delta(bpm_val,   ref["battements_coeur"],      plus_haut_est_mauvais=True)
    metric_card("❤️ Battements cœur", f"{bpm_val} bpm", arrow, delta)

    arrow, delta = fleche_delta(ecran_val, ref["temps_ecran_heures"],    plus_haut_est_mauvais=True)
    metric_card("📱 Temps écran", f"{ecran_val:.1f} h", arrow, delta)

    # --- Message de coaching ---
    coaching_colors = {
        1: ("background:#eafaf1; border:1.5px solid #2ecc71;", "#1a7a47"),
        2: ("background:#fef9e7; border:1.5px solid #f1c40f;", "#7d6608"),
        3: ("background:#fdecea; border:1.5px solid #e74c3c;", "#922b21"),
    }
    box_style, text_color = coaching_colors[niveau]
    message = str(last_score["message_coaching"])

    st.markdown(f"""
    <div class="coaching-box" style="{box_style} color:{text_color};">
        💬 <strong>Message du jour</strong><br>{message}
    </div>
    """, unsafe_allow_html=True)

    # --- Alerte niveau 3 ---
    if niveau == 3:
        st.markdown("""
        <div class="alert-box">
            🚨 Votre médecin a été informé et va vous contacter.
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE 2 — Mon historique
# ---------------------------------------------------------------------------
elif page == "📈 Mon historique":

    patiente = st.selectbox("Choisir une patiente", PATIENTES, key="p2")
    st.markdown("## 📈 Mon évolution")

    data_p   = donnees[donnees["patiente"] == patiente].sort_values("jour")
    scores_p = scores[scores["patiente"] == patiente].sort_values("jour")

    jours      = data_p["jour"].tolist()
    dates_str  = data_p["date"].dt.strftime("%d/%m").tolist()

    niveau_colors = {1: "#2ecc71", 2: "#f1c40f", 3: "#e74c3c"}

    def ligne_ref(fig):
        fig.add_vline(
            x=7, line_dash="dash", line_color="#aaa", line_width=1.5,
            annotation_text="Fin de la période de référence",
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color="#888",
        )
        return fig

    # --- Graphique score ---
    st.markdown("#### 🎯 Score de risque")
    colors_pts = [niveau_colors[int(n)] for n in scores_p["niveau"]]

    fig_score = go.Figure()
    fig_score.add_trace(go.Scatter(
        x=jours, y=scores_p["niveau"],
        mode="lines+markers",
        line=dict(color="#aac4f7", width=2),
        marker=dict(color=colors_pts, size=10, line=dict(width=1, color="#fff")),
        hovertemplate="Jour %{x} — Niveau %{y}<extra></extra>",
    ))
    fig_score.update_layout(
        yaxis=dict(tickvals=[1, 2, 3], ticktext=["🟢 Niveau 1", "🟡 Niveau 2", "🔴 Niveau 3"],
                   range=[0.5, 3.5]),
        xaxis=dict(title="Jour", tickvals=jours[::2], ticktext=dates_str[::2]),
        plot_bgcolor="#f8f9fe", paper_bgcolor="#ffffff",
        margin=dict(t=20, b=40, l=20, r=20), height=240,
    )
    ligne_ref(fig_score)
    st.plotly_chart(fig_score, use_container_width=True)

    # --- Graphique pas ---
    st.markdown("#### 🚶 Pas par jour")
    fig_pas = go.Figure()
    fig_pas.add_trace(go.Scatter(
        x=jours, y=data_p["pas"],
        mode="lines+markers",
        line=dict(color="#5dade2", width=2),
        marker=dict(color="#5dade2", size=6),
        fill="tozeroy", fillcolor="rgba(93,173,226,0.12)",
        hovertemplate="Jour %{x} — %{y:,} pas<extra></extra>",
    ))
    fig_pas.update_layout(
        xaxis=dict(title="Jour", tickvals=jours[::2], ticktext=dates_str[::2]),
        yaxis=dict(title="Pas"),
        plot_bgcolor="#f8f9fe", paper_bgcolor="#ffffff",
        margin=dict(t=20, b=40, l=20, r=20), height=240,
    )
    ligne_ref(fig_pas)
    st.plotly_chart(fig_pas, use_container_width=True)

    # --- Graphique sommeil ---
    st.markdown("#### 😴 Sommeil (heures)")
    fig_somm = go.Figure()
    fig_somm.add_trace(go.Scatter(
        x=jours, y=data_p["sommeil_heures"],
        mode="lines+markers",
        line=dict(color="#a29bfe", width=2),
        marker=dict(color="#a29bfe", size=6),
        fill="tozeroy", fillcolor="rgba(162,155,254,0.12)",
        hovertemplate="Jour %{x} — %{y:.1f} h<extra></extra>",
    ))
    fig_somm.update_layout(
        xaxis=dict(title="Jour", tickvals=jours[::2], ticktext=dates_str[::2]),
        yaxis=dict(title="Heures"),
        plot_bgcolor="#f8f9fe", paper_bgcolor="#ffffff",
        margin=dict(t=20, b=40, l=20, r=20), height=240,
    )
    ligne_ref(fig_somm)
    st.plotly_chart(fig_somm, use_container_width=True)
