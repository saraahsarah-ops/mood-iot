import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

st.set_page_config(
    page_title="Mood-IoT | Dr. Claire Rousseau",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

st.markdown("""
<style>
    html, body, p, h1, h2, h3, h4, h5, h6, li, a,
    button, input, textarea, select,
    .stApp .main, .stApp .block-container,
    [data-testid="stSidebar"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] *,
    [data-testid="stRadio"] label,
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stButton"] button,
    .stMarkdown, .stMarkdown *,
    .element-container, .element-container * {
        font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .material-icons, .material-icons-outlined,
    .material-symbols-outlined, .material-symbols-rounded,
    [class^="material-"], [class*=" material-"] {
        font-family: 'Material Icons', 'Material Symbols Outlined' !important;
    }

    [data-testid="InputInstructions"] { display: none !important; }
    [data-testid="stToolbar"]         { opacity: 0 !important; pointer-events: none !important; }
    #MainMenu                         { display: none !important; }
    footer                            { display: none !important; }

    /* ── FOND ── */
    .stApp { background-color: #F0F4F8 !important; }
    .main .block-container { padding: 2rem 2.5rem 3rem 2.5rem; max-width: 1300px; }

    /* ── SIDEBAR BLEU DOCTOLIB ── */
    [data-testid="stSidebar"] { background-color: #0D1B3E !important; }
    [data-testid="stSidebar"] > div:first-child { background-color: #0D1B3E !important; }
    [data-testid="stSidebar"] * { color: #7F91B2 !important; }
    [data-testid="stSidebar"] hr { border-color: #1E2F52 !important; }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] .stRadio > label,
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label:first-child { display: none !important; }
    [data-testid="stSidebar"] [role="radio"] > div:first-child,
    [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child { display: none !important; }
    [data-testid="stSidebar"] .stRadio > div { display: flex; flex-direction: column; gap: 2px; }
    [data-testid="stSidebar"] [data-baseweb="radio"] { background: transparent !important; padding: 0 !important; }
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        color: #8899BB !important; font-size: 0.875rem !important; font-weight: 600 !important;
        padding: 10px 16px !important; border-radius: 8px !important; cursor: pointer !important;
        display: block !important; width: 100% !important; box-sizing: border-box !important;
        transition: all 0.15s !important; border-left: 3px solid transparent !important; margin: 0 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
        background: rgba(0,188,212,0.1) !important; color: #00BCD4 !important;
        border-left-color: rgba(0,188,212,0.4) !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) label {
        background: rgba(0,188,212,0.12) !important; color: #00BCD4 !important;
        border-left-color: #00BCD4 !important; font-weight: 700 !important;
    }

    /* ── PAGE HEADER ── */
    .page-header {
        background: #ffffff; border-radius: 14px; padding: 20px 24px;
        margin-bottom: 1.5rem; border: 1px solid #E2E8F0;
        box-shadow: 0 2px 8px rgba(13,27,62,0.07);
    }
    .page-title { font-size: 1.25rem; font-weight: 800; color: #0D1B3E; margin: 0 0 3px 0; letter-spacing: -0.02em; }
    .page-subtitle { font-size: 0.82rem; color: #64748B; font-weight: 500; margin: 0; }

    /* ── KPI CARDS ── */
    .kpi-card {
        background: #ffffff; border-radius: 16px; padding: 20px;
        border: 1px solid #E2E8F0; box-shadow: 0 2px 10px rgba(13,27,62,0.07);
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(13,27,62,0.12); }
    .kpi-icon-circle {
        width: 52px; height: 52px; border-radius: 14px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.4rem; flex-shrink: 0; margin-bottom: 14px;
    }
    .kpi-icon-red    { background: #FEE2E2; }
    .kpi-icon-orange { background: #FEF3C7; }
    .kpi-icon-green  { background: #D1FAE5; }
    .kpi-icon-blue   { background: #DBEAFE; }
    .kpi-label { font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 4px; }
    .kpi-value { font-size: 2rem; font-weight: 900; line-height: 1; letter-spacing: -0.03em; color: #0D1B3E; }
    .kpi-sub   { font-size: 0.72rem; color: #94A3B8; margin-top: 7px; }
    .kpi-critical .kpi-value { color: #DC2626; }
    .kpi-watch   .kpi-value  { color: #D97706; }
    .kpi-stable  .kpi-value  { color: #059669; }
    .kpi-avg     .kpi-value  { color: #1565C0; }

    /* ── CARTES PATIENTES ── */
    .patient-card {
        background: #ffffff; border-radius: 10px; padding: 14px 18px;
        border: 1px solid #E5E7EB; border-left-width: 4px;
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: box-shadow 0.15s, transform 0.1s;
    }
    .patient-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.08); transform: translateY(-1px); }
    .pc-red    { border-left-color: #EF4444 !important; }
    .pc-orange { border-left-color: #F59E0B !important; }
    .pc-green  { border-left-color: #10B981 !important; }
    .patient-left { display: flex; align-items: center; gap: 14px; }
    .patient-avatar {
        width: 42px; height: 42px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.88rem; font-weight: 800; color: white; flex-shrink: 0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }
    .av-red    { background: linear-gradient(135deg, #EF4444, #DC2626); }
    .av-orange { background: linear-gradient(135deg, #F59E0B, #D97706); }
    .av-green  { background: linear-gradient(135deg, #10B981, #059669); }
    .patient-name { font-size: 0.92rem; font-weight: 700; color: #0D1B3E; margin-bottom: 2px; }
    .patient-note { font-size: 0.78rem; color: #64748B; }
    .score-badge { font-size: 0.88rem; font-weight: 800; padding: 5px 14px; border-radius: 20px; min-width: 74px; text-align: center; }
    .badge-red    { background: #FEE2E2; color: #991B1B; }
    .badge-orange { background: #FEF3C7; color: #92400E; }
    .badge-green  { background: #D1FAE5; color: #065F46; }

    /* ── SECTION TITLE ── */
    .section-title {
        font-size: 0.72rem; font-weight: 800; color: #1565C0;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 1.75rem 0 0.85rem 0; padding-bottom: 8px;
        border-bottom: 2px solid #DBEAFE;
    }

    /* ── MÉTRIQUES avec TOOLTIP ── */
    .metric-box {
        background: #ffffff; border-radius: 12px; padding: 18px;
        border: 1px solid #E5E7EB; text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        position: relative; cursor: default;
        transition: box-shadow 0.15s;
    }
    .metric-box:hover { box-shadow: 0 4px 14px rgba(21,101,192,0.12); }
    .metric-label { font-size: 0.68rem; font-weight: 800; color: #6B7280; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
    .metric-val   { font-size: 1.6rem; font-weight: 900; color: #1565C0; }
    .metric-delta { font-size: 0.76rem; margin-top: 3px; font-weight: 600; }
    .delta-neg    { color: #EF4444; }
    .delta-warn   { color: #F59E0B; }
    .metric-tooltip {
        display: none; position: absolute; bottom: calc(100% + 10px);
        left: 50%; transform: translateX(-50%);
        background: #0D1B3E; color: #E2E8F0;
        padding: 10px 14px; border-radius: 10px;
        font-size: 0.76rem; line-height: 1.5; white-space: nowrap;
        z-index: 9999; box-shadow: 0 6px 20px rgba(13,27,62,0.3);
        pointer-events: none; min-width: 220px; text-align: left; font-weight: 500;
    }
    .metric-tooltip::after {
        content: ''; position: absolute; top: 100%; left: 50%;
        transform: translateX(-50%); border: 6px solid transparent;
        border-top-color: #0D1B3E;
    }
    .metric-box:hover .metric-tooltip { display: block; }

    /* ── NOTIFICATIONS ── */
    .notif-card {
        background: #ffffff; border-radius: 12px; padding: 16px 18px 16px 20px;
        border: 1px solid #E8ECF0; margin-bottom: 10px;
        display: flex; align-items: flex-start; gap: 14px;
        box-shadow: 0 2px 8px rgba(13,27,62,0.06);
        transition: transform 0.12s, box-shadow 0.12s;
    }
    .notif-card:hover { transform: translateY(-1px); box-shadow: 0 5px 16px rgba(13,27,62,0.1); }
    .notif-unread { border-left: 4px solid #EF4444; }
    .notif-read   { border-left: 4px solid #E8ECF0; opacity: 0.5; }
    .notif-dot-on  { width: 11px; height: 11px; border-radius: 50%; background: #EF4444; flex-shrink: 0; margin-top: 3px; box-shadow: 0 0 0 3px rgba(239,68,68,0.18); }
    .notif-dot-off { width: 11px; height: 11px; border-radius: 50%; background: #CBD5E1; flex-shrink: 0; margin-top: 3px; }
    .notif-body { flex: 1; }
    .notif-patient { font-weight: 800; font-size: 0.9rem; color: #0D1B3E; }
    .notif-msg     { font-size: 0.82rem; color: #4A5568; margin-top: 4px; line-height: 1.45; }
    .notif-time    { font-size: 0.7rem; color: #94A3B8; margin-top: 6px; }

    /* ── MESSAGERIE ── */
    .chat-legend { display: flex; gap: 18px; margin-bottom: 10px; font-size: 0.72rem; color: #6B7280; font-weight: 600; }
    .legend-dot  { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 5px; }
    .chat-box {
        background: #F8FAFC; border-radius: 12px; border: 1px solid #E5E7EB;
        padding: 16px; min-height: 300px; max-height: 440px;
        overflow-y: auto; margin-bottom: 12px;
    }
    .chat-empty { text-align: center; color: #9CA3AF; font-size: 0.85rem; padding: 70px 0; }
    .chat-day-sep {
        text-align: center; margin: 14px 0 10px 0;
        font-size: 0.68rem; font-weight: 700; color: #9CA3AF;
        text-transform: uppercase; letter-spacing: 0.07em;
        display: flex; align-items: center; gap: 10px;
    }
    .chat-day-sep::before, .chat-day-sep::after { content: ''; flex: 1; height: 1px; background: #E5E7EB; }
    .msg-doctor  { display: flex; justify-content: flex-end;  margin: 6px 0; }
    .msg-patient { display: flex; justify-content: flex-start; margin: 6px 0; }
    .msg-ia      { display: flex; justify-content: flex-start; margin: 6px 0; }
    .bbl-doc {
        background: linear-gradient(135deg, #0D1B3E, #1565C0); color: #ffffff;
        border-radius: 14px 14px 3px 14px; padding: 10px 15px; max-width: 66%;
        font-size: 0.87rem; line-height: 1.5; font-weight: 500;
        box-shadow: 0 3px 12px rgba(13,27,62,0.25);
    }
    .bbl-pat {
        background: #ffffff; color: #111827; border: 1px solid #E5E7EB;
        border-radius: 14px 14px 14px 3px; padding: 10px 15px; max-width: 66%;
        font-size: 0.87rem; line-height: 1.5;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .bbl-ia-wrapper { max-width: 72%; }
    .bbl-ia-label {
        font-size: 0.64rem; font-weight: 800; color: #1565C0;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin-bottom: 4px; margin-left: 2px;
        display: flex; align-items: center; gap: 5px;
    }
    .bbl-ia {
        background: #EFF6FF; color: #1E40AF; border: 1px solid #BFDBFE;
        border-radius: 14px 14px 14px 3px; padding: 10px 15px;
        font-size: 0.87rem; line-height: 1.5; font-style: italic; font-weight: 500;
    }
    .bbl-time { font-size: 0.66rem; color: #9CA3AF; margin: 3px 5px 0 5px; display: block; font-weight: 600; }
    .time-r { text-align: right; }

    /* ── COACHING ── */
    .coaching-box {
        background: #EFF6FF; border-radius: 10px; padding: 14px 17px;
        border: 1px solid #BFDBFE; margin-top: 14px; border-left: 4px solid #1565C0;
    }
    .coaching-tag  { font-size: 0.68rem; font-weight: 800; color: #1565C0; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 5px; }
    .coaching-text { font-size: 0.87rem; color: #1E40AF; line-height: 1.55; font-weight: 500; }

    /* ── BOUTONS BLEU DOCTOLIB ── */
    .stButton > button {
        border-radius: 9px !important; font-size: 0.855rem !important;
        font-weight: 700 !important; border: none !important;
        background: linear-gradient(135deg, #1565C0, #0D47A1) !important;
        color: white !important; padding: 9px 22px !important;
        transition: all 0.15s !important; letter-spacing: 0.01em !important;
        box-shadow: 0 3px 10px rgba(21,101,192,0.35) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #0D47A1, #0A3880) !important;
        box-shadow: 0 5px 16px rgba(21,101,192,0.45) !important;
        transform: translateY(-1px);
    }
    .stButton > button:active { transform: translateY(0) !important; }

    /* ── INPUTS ── */
    [data-baseweb="select"] { border-radius: 9px !important; }
    .stTextArea textarea, .stTextInput input {
        border-radius: 9px !important; border: 1.5px solid #E2E8F0 !important;
        font-size: 0.875rem !important; background: #ffffff !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #1565C0 !important;
        box-shadow: 0 0 0 3px rgba(21,101,192,0.15) !important;
    }

    /* ── LOGIN ── */
    .login-outer { display: flex; justify-content: center; align-items: flex-start; padding-top: 6vh; }
    .login-box { background: #ffffff; border-radius: 24px; width: 380px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); overflow: hidden; }
    .login-top { background: linear-gradient(160deg, #060F24, #0D1B3E); padding: 36px 36px 28px 36px; text-align: center; }
    .login-portrait { width: 80px; height: 80px; border-radius: 50%; margin: 0 auto 16px auto; border: 3px solid rgba(0,188,212,0.5); overflow: hidden; display: flex; }
    .login-brand { font-size: 1.5rem; font-weight: 900; color: #ffffff; letter-spacing: -0.03em; }
    .login-brand span { color: #00BCD4; }
    .login-tagline { font-size: 0.78rem; color: #7F91B2; margin-top: 4px; font-weight: 500; }
    .login-pill {
        display: inline-block; background: rgba(0,188,212,0.15); color: #00BCD4;
        font-size: 0.65rem; font-weight: 800; padding: 4px 16px; border-radius: 20px;
        margin-top: 14px; text-transform: uppercase; letter-spacing: 0.1em;
        border: 1px solid rgba(0,188,212,0.35);
    }
    .login-bottom { padding: 28px 32px 32px 32px; }
    .login-footer { text-align: center; font-size: 0.7rem; color: #94A3B8; margin-top: 18px; display: flex; align-items: center; justify-content: center; gap: 6px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

DOCTOR_SVG = """
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg-dr" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0D1B3E"/><stop offset="100%" stop-color="#1565C0"/>
    </linearGradient>
    <clipPath id="clip-dr"><circle cx="32" cy="32" r="32"/></clipPath>
  </defs>
  <circle cx="32" cy="32" r="32" fill="url(#bg-dr)"/>
  <g clip-path="url(#clip-dr)">
    <path d="M6 68 Q6 48 32 48 Q58 48 58 68Z" fill="#F8FAFC"/>
    <rect x="28" y="38" width="8" height="12" rx="3" fill="#F5CBA7"/>
    <ellipse cx="32" cy="29" rx="11" ry="12" fill="#F5CBA7"/>
    <path d="M21 24 Q22 13 32 12 Q42 13 43 24 Q41 15 32 15 Q23 15 21 24Z" fill="#3D2B1F"/>
    <ellipse cx="21.5" cy="29" rx="2" ry="2.5" fill="#F5CBA7"/>
    <ellipse cx="42.5" cy="29" rx="2" ry="2.5" fill="#F5CBA7"/>
    <path d="M24 48 L29 41 L32 47 L35 41 L40 48" fill="#F8FAFC"/>
    <path d="M27 50 Q32 54 37 50" stroke="#00BCD4" stroke-width="2" fill="none" stroke-linecap="round"/>
    <rect x="36.5" y="43" width="5" height="1.5" rx="0.75" fill="#00BCD4"/>
    <rect x="38.5" y="41" width="1.5" height="5" rx="0.75" fill="#00BCD4"/>
  </g>
</svg>"""

DOCTOR_SVG_SM = """
<svg width="44" height="44" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg-sm" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0D1B3E"/><stop offset="100%" stop-color="#1565C0"/>
    </linearGradient>
    <clipPath id="clip-sm"><circle cx="32" cy="32" r="32"/></clipPath>
  </defs>
  <circle cx="32" cy="32" r="32" fill="url(#bg-sm)"/>
  <g clip-path="url(#clip-sm)">
    <path d="M6 68 Q6 48 32 48 Q58 48 58 68Z" fill="#F8FAFC"/>
    <rect x="28" y="38" width="8" height="12" rx="3" fill="#F5CBA7"/>
    <ellipse cx="32" cy="29" rx="11" ry="12" fill="#F5CBA7"/>
    <path d="M21 24 Q22 13 32 12 Q42 13 43 24 Q41 15 32 15 Q23 15 21 24Z" fill="#3D2B1F"/>
    <ellipse cx="21.5" cy="29" rx="2" ry="2.5" fill="#F5CBA7"/>
    <ellipse cx="42.5" cy="29" rx="2" ry="2.5" fill="#F5CBA7"/>
    <path d="M24 48 L29 41 L32 47 L35 41 L40 48" fill="#F8FAFC"/>
    <path d="M27 50 Q32 54 37 50" stroke="#00BCD4" stroke-width="2" fill="none" stroke-linecap="round"/>
  </g>
</svg>"""

LOGO_SVG = """
<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="lg-logo" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00BCD4"/><stop offset="100%" stop-color="#1565C0"/>
    </linearGradient>
  </defs>
  <rect width="32" height="32" rx="9" fill="url(#lg-logo)"/>
  <path d="M6 18 C6 18 8 10 10 14 C12 18 12 12 14 12 C16 12 16 20 18 16 C20 12 22 18 22 18"
        stroke="white" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="22" cy="10" r="3" fill="white" opacity="0.5"/>
  <circle cx="22" cy="10" r="1.5" fill="white"/>
</svg>"""

# ── LOGIN ──
if not st.session_state.logged_in:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        .stApp { background: linear-gradient(160deg, #060F24 0%, #0D1B3E 55%, #0A3040 100%) !important; }
    </style>
    """, unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown(f"""
        <div class='login-outer'><div class='login-box'>
          <div class='login-top'>
            <div class='login-portrait'>{DOCTOR_SVG}</div>
            <div class='login-brand'>Mood<span>-IoT</span></div>
            <div class='login-tagline'>Plateforme de suivi psychiatrique connecté</div>
            <div class='login-pill'>Espace médecin sécurisé</div>
          </div>
          <div class='login-bottom'></div>
        </div></div>
        """, unsafe_allow_html=True)
        email    = st.text_input("Email professionnel", placeholder="dr.rousseau@mood-iot.fr")
        password = st.text_input("Mot de passe", type="password", placeholder="••••••••")
        if st.button("Se connecter", use_container_width=True):
            if email.strip() == "dr.rousseau@mood-iot.fr" and password == "medecin123":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Identifiants incorrects. Essayez : dr.rousseau@mood-iot.fr / medecin123")
        st.markdown("""
        <div class='login-footer'>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
              <rect x="5" y="11" width="14" height="11" rx="2" stroke="#94A3B8" stroke-width="2"/>
              <path d="M8 11V7a4 4 0 018 0v4" stroke="#94A3B8" stroke-width="2" stroke-linecap="round"/>
            </svg>
            Connexion chiffrée &middot; Données de santé protégées
        </div>""", unsafe_allow_html=True)
    st.stop()

# ── DONNÉES ──
@st.cache_data
def load_data():
    donnees = pd.read_csv("../simulateur/donnees.csv")
    if os.path.exists("../backend/scores.csv"):
        scores = pd.read_csv("../backend/scores.csv")
    else:
        import numpy as np
        rows = []
        for p in donnees["patiente"].unique():
            for jour in range(8, 22):
                score = min(100, int((jour - 7) * 6 + np.random.randint(0, 10)))
                niveau = 1 if score < 40 else (2 if score < 70 else 3)
                msg = (
                    "Continuez comme ça, votre routine est stable." if niveau == 1
                    else "Votre sommeil semble perturbé. Essayez une courte marche." if niveau == 2
                    else "Votre médecin a été informé et va vous contacter rapidement."
                )
                rows.append({"patiente": p, "jour": jour, "score": score, "niveau": niveau, "message_coaching": msg})
        scores = pd.DataFrame(rows)
    return donnees, scores

donnees, scores = load_data()

# ── SESSION ──
if "notifications" not in st.session_state:
    st.session_state.notifications = []

if "messages" not in st.session_state:
    # Messages IA exemples enrichis par patiente
    messages_ia_exemples = {
        "Sophie": [
            {"role": "ia", "texte": "Bonjour Sophie ! Votre rythme de sommeil s'est amélioré cette semaine. Continuez à maintenir des horaires réguliers.", "heure": "Jour 3", "jour": 3},
            {"role": "ia", "texte": "Votre activité physique a légèrement baissé. Essayez une marche de 20 minutes aujourd'hui pour stimuler votre humeur.", "heure": "Jour 8", "jour": 8},
            {"role": "ia", "texte": "Excellent ! Vous avez franchi les 8 000 pas aujourd'hui. Cette régularité est bénéfique pour votre équilibre émotionnel.", "heure": "Jour 14", "jour": 14},
        ],
        "Marie": [
            {"role": "ia", "texte": "Bonjour Marie. Nous avons détecté une perturbation de votre sommeil les 2 dernières nuits. Avez-vous des préoccupations particulières ?", "heure": "Jour 5", "jour": 5},
            {"role": "ia", "texte": "Votre fréquence cardiaque au repos a augmenté. Pensez à pratiquer quelques exercices de respiration avant de dormir.", "heure": "Jour 10", "jour": 10},
            {"role": "ia", "texte": "Votre médecin a été alerté de l'évolution de vos scores. Elle va vous contacter dans les prochaines heures.", "heure": "Jour 18", "jour": 18},
        ],
        "Léa": [
            {"role": "ia", "texte": "Bonjour Léa ! Votre activité est en hausse cette semaine. C'est un très bon signe pour votre rétablissement.", "heure": "Jour 4", "jour": 4},
            {"role": "ia", "texte": "Nous remarquons que vous sortez moins ces derniers jours. Même une petite promenade peut faire une grande différence.", "heure": "Jour 9", "jour": 9},
        ],
        "Anna": [
            {"role": "ia", "texte": "Bonjour Anna. Vos indicateurs sont stables cette semaine. Le Dr. Rousseau est satisfaite de votre progression.", "heure": "Jour 6", "jour": 6},
            {"role": "ia", "texte": "Votre score a franchi le seuil d'alerte. Votre médecin a été prévenue et va vous appeler rapidement.", "heure": "Jour 19", "jour": 19},
        ],
    }
    messages_initiaux = {
        "Sophie": [{"role": "patiente", "texte": "Bonjour docteur, je ne dors plus bien.", "heure": "J1", "jour": 1}],
        "Marie":  [{"role": "patiente", "texte": "Je me sens très fatiguée ces derniers jours.", "heure": "J1", "jour": 1}],
        "Léa":    [{"role": "patiente", "texte": "J'ai du mal à sortir de chez moi.", "heure": "J1", "jour": 1}],
        "Anna":   [{"role": "patiente", "texte": "Bonjour, comment ça se passe pour mon suivi ?", "heure": "J1", "jour": 1}],
    }
    st.session_state.messages = {}
    for p_nom in donnees["patiente"].unique():
        msgs = list(messages_initiaux.get(p_nom, []))
        msgs += messages_ia_exemples.get(p_nom, [])
        scores_p = scores[scores["patiente"] == p_nom].sort_values("jour")
        for _, row in scores_p.iterrows():
            jour = int(row["jour"])
            already = any(m["role"] == "ia" and m.get("jour") == jour for m in msgs)
            if not already:
                msgs.append({"role": "ia", "texte": row["message_coaching"], "heure": f"Jour {jour}", "jour": jour})
        msgs.sort(key=lambda m: m.get("jour", 0))
        st.session_state.messages[p_nom] = msgs

if "commentaires" not in st.session_state:
    st.session_state.commentaires = {p: "" for p in donnees["patiente"].unique()}

# ── HELPERS ──
def niveau_meta(niveau):
    return {
        1: {"color": "#059669", "cls": "green",  "av": "av-green",  "badge": "badge-green",  "pc": "pc-green",  "label": "Stable"},
        2: {"color": "#D97706", "cls": "orange", "av": "av-orange", "badge": "badge-orange", "pc": "pc-orange", "label": "À surveiller"},
        3: {"color": "#DC2626", "cls": "red",    "av": "av-red",    "badge": "badge-red",    "pc": "pc-red",    "label": "Critique"},
    }[niveau]

def initiales(nom):
    parts = nom.strip().split()
    return ("".join(p[0] for p in parts[:2])).upper()

derniers_scores = scores.sort_values("jour").groupby("patiente").last().reset_index()
derniers_scores = derniers_scores.sort_values("niveau", ascending=False)

# ── SIDEBAR ──
with st.sidebar:
    st.markdown(f"""
    <div style='padding:24px 16px 16px 16px;'>
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:6px;'>
            {LOGO_SVG}
            <div style='font-size:1.15rem;font-weight:900;color:#E2E8F0;letter-spacing:-0.02em;'>Mood-IoT</div>
        </div>
        <div style='font-size:0.68rem;color:#3A5080;margin-top:2px;font-weight:700;
                    padding-left:42px;text-transform:uppercase;letter-spacing:0.08em;'>
            Suivi psychiatrique
        </div>
    </div>
    <hr style='border:none;border-top:1px solid #1E2F52;margin:0 16px 14px 16px;'>
    <div style='padding:0 14px;font-size:0.6rem;font-weight:800;color:#3A5080;
                text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px;'>Navigation</div>
    """, unsafe_allow_html=True)

    nb_notif = len([n for n in st.session_state.notifications if not n.get("lue")])
    notif_label = f"Notifications  ·  {nb_notif}" if nb_notif > 0 else "Notifications"
    page = st.radio("Navigation", ["Vue générale", "Fiche patiente", notif_label, "Messagerie"], label_visibility="collapsed")

    st.markdown("<hr style='border:none;border-top:1px solid #1E2F52;margin:14px 16px;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='padding:0 16px 20px 16px;'>
        <div style='display:flex;align-items:center;gap:12px;'>
            <div style='width:48px;height:48px;border-radius:50%;overflow:hidden;flex-shrink:0;
                        border:2px solid rgba(0,188,212,0.45);box-shadow:0 0 0 3px rgba(0,188,212,0.12);'>
                {DOCTOR_SVG_SM}
            </div>
            <div>
                <div style='font-size:0.87rem;font-weight:800;color:#E2E8F0;line-height:1.2;'>Dr. Claire Rousseau</div>
                <div style='font-size:0.7rem;color:#00BCD4;font-weight:700;margin-top:2px;'>Psychiatre</div>
                <div style='display:flex;align-items:center;gap:5px;margin-top:4px;'>
                    <div style='width:7px;height:7px;border-radius:50%;background:#10B981;box-shadow:0 0 0 2px rgba(16,185,129,0.2);'></div>
                    <div style='font-size:0.65rem;color:#3A5080;font-weight:600;'>Connectée · {datetime.now().strftime('%H:%M')}</div>
                </div>
            </div>
        </div>
    </div>
    <div style='padding:0 14px 8px 14px;'>
        <div style='font-size:0.6rem;font-weight:800;color:#3A5080;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px;'>Session</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Se déconnecter", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# ══ PAGE 1 — VUE GÉNÉRALE ══
if page == "Vue générale":
    st.markdown(f"""
    <div class='page-header' style='display:flex;align-items:center;justify-content:space-between;'>
        <div>
            <div class='page-title'>Bonjour, Dr. Claire Rousseau 👋</div>
            <div class='page-subtitle'>État de votre cohorte psychiatrique — Mood-IoT</div>
        </div>
        <div style='display:flex;align-items:center;gap:8px;font-size:0.8rem;font-weight:700;
                    color:#1565C0;background:#EFF6FF;padding:9px 16px;border-radius:10px;border:1px solid #BFDBFE;'>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="18" rx="2" stroke="#1565C0" stroke-width="2"/>
              <path d="M16 2v4M8 2v4M3 10h18" stroke="#1565C0" stroke-width="2" stroke-linecap="round"/>
            </svg>
            {datetime.now().strftime('%d %B %Y')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    nb_rouge  = len(derniers_scores[derniers_scores["niveau"] == 3])
    nb_jaune  = len(derniers_scores[derniers_scores["niveau"] == 2])
    nb_vert   = len(derniers_scores[derniers_scores["niveau"] == 1])
    score_moy = int(derniers_scores["score"].mean())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='kpi-card kpi-critical'>
            <div class='kpi-icon-circle kpi-icon-red'>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 21h20L12 2z" stroke="#EF4444" stroke-width="2" stroke-linejoin="round"/><path d="M12 9v5" stroke="#EF4444" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="17.5" r="0.75" fill="#EF4444" stroke="#EF4444" stroke-width="1"/></svg>
            </div>
            <div class='kpi-value'>{nb_rouge}</div><div class='kpi-label'>Alertes critiques</div>
            <div class='kpi-sub'>Nécessitent une action immédiate</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='kpi-card kpi-watch'>
            <div class='kpi-icon-circle kpi-icon-orange'>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="#F59E0B" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="#F59E0B" stroke-width="2"/></svg>
            </div>
            <div class='kpi-value'>{nb_jaune}</div><div class='kpi-label'>À surveiller</div>
            <div class='kpi-sub'>Suivi renforcé conseillé</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='kpi-card kpi-stable'>
            <div class='kpi-icon-circle kpi-icon-green'>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#10B981" stroke-width="2"/><path d="M8 12l3 3 5-6" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <div class='kpi-value'>{nb_vert}</div><div class='kpi-label'>Stables</div>
            <div class='kpi-sub'>Évolution favorable</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class='kpi-card kpi-avg'>
            <div class='kpi-icon-circle kpi-icon-blue'>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 17l5-5 4 4 7-8" stroke="#1565C0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 17H3" stroke="#1565C0" stroke-width="1.5" stroke-linecap="round"/></svg>
            </div>
            <div class='kpi-value'>{score_moy}</div><div class='kpi-label'>Score moyen</div>
            <div class='kpi-sub'>Sur 100 — cohorte entière</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>État des patientes aujourd'hui</div>", unsafe_allow_html=True)

    for _, row in derniers_scores.iterrows():
        meta = niveau_meta(row["niveau"])
        ini  = initiales(row["patiente"])
        if row["niveau"] == 3:
            col_card, col_btn = st.columns([8, 2])
        else:
            col_card, col_btn = st.columns([10, 1])
        with col_card:
            st.markdown(f"""
            <div class='patient-card {meta["pc"]}'>
                <div class='patient-left'>
                    <div class='patient-avatar {meta["av"]}'>{ini}</div>
                    <div>
                        <div class='patient-name'>{row['patiente']}</div>
                        <div class='patient-note'>{row['message_coaching']}</div>
                    </div>
                </div>
                <div class='score-badge {meta["badge"]}'>{row['score']}/100</div>
            </div>""", unsafe_allow_html=True)
        with col_btn:
            if row["niveau"] == 3:
                st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
                if st.button("Envoyer alerte", key=f"alert_{row['patiente']}"):
                    st.session_state.notifications.append({
                        "patiente": row["patiente"], "score": row["score"],
                        "heure": datetime.now().strftime("%H:%M"), "lue": False,
                        "message": f"Score critique de {row['score']}/100 détecté pour {row['patiente']}"
                    })
                    st.success(f"✓ Alerte envoyée pour {row['patiente']}.")
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Évolution des scores — 21 jours</div>", unsafe_allow_html=True)

    # Palette Doctolib pour les 4 courbes
    palette = ["#1565C0", "#00BCD4", "#F59E0B", "#EF4444"]
    patientes_list = sorted(scores["patiente"].unique().tolist())
    color_map = {p: palette[i % len(palette)] for i, p in enumerate(patientes_list)}

    fig = go.Figure()
    for patiente_nom in patientes_list:
        df_p = scores[scores["patiente"] == patiente_nom].sort_values("jour")
        couleur = color_map[patiente_nom]
        fig.add_trace(go.Scatter(
            x=df_p["jour"], y=df_p["score"],
            mode="lines", name=patiente_nom,
            line=dict(color=couleur, width=2.5, shape="spline"),
            customdata=df_p[["patiente", "niveau", "message_coaching"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b> — Jour %{x}<br>"
                "Score : <b>%{y}/100</b><br>"
                "<i>%{customdata[2]}</i><extra></extra>"
            )
        ))
    fig.add_hline(y=40, line_dash="dot", line_color="#F59E0B", line_width=1.5,
                  annotation_text="Seuil surveillance", annotation_font_color="#F59E0B", annotation_font_size=11)
    fig.add_hline(y=70, line_dash="dot", line_color="#EF4444", line_width=1.5,
                  annotation_text="Seuil critique", annotation_font_color="#EF4444", annotation_font_size=11)
    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#F8FAFC",
        font=dict(family="Nunito, sans-serif", color="#0D1B3E", size=12),
        legend=dict(title_text="Patiente", bgcolor="rgba(255,255,255,0.8)", bordercolor="#E2E8F0", borderwidth=1),
        xaxis=dict(showgrid=False, title="Jour"),
        yaxis=dict(gridcolor="#E2E8F0", title="Score / 100", range=[0, 105]),
        margin=dict(t=20, b=20, l=10, r=10), height=360,
        hoverlabel=dict(bgcolor="#0D1B3E", font_color="#E2E8F0", font_size=12, font_family="Nunito, sans-serif"),
    )
    st.plotly_chart(fig, use_container_width=True)

# ══ PAGE 2 — FICHE PATIENTE ══
elif page == "Fiche patiente":
    st.markdown("""
    <div class='page-header'>
        <div class='page-title'>Fiche patiente</div>
        <div class='page-subtitle'>Données biométriques et évolution clinique — Mood-IoT</div>
    </div>""", unsafe_allow_html=True)

    patiente  = st.selectbox("Sélectionner une patiente", donnees["patiente"].unique())
    score_row = scores[scores["patiente"] == patiente].sort_values("jour").iloc[-1]
    meta      = niveau_meta(int(score_row["niveau"]))
    ini       = initiales(patiente)

    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:14px;margin:1rem 0 1.5rem 0;
                background:#ffffff;border-radius:14px;padding:16px 22px;
                border:1px solid #E5E7EB;box-shadow:0 2px 10px rgba(13,27,62,0.07);'>
        <div class='patient-avatar {meta["av"]}' style='width:48px;height:48px;font-size:1rem;'>{ini}</div>
        <div style='flex:1;'>
            <div style='font-size:1.08rem;font-weight:800;color:#0D1B3E;'>{patiente}</div>
            <div style='font-size:0.8rem;color:#6B7280;font-weight:500;'>Patiente suivie en psychiatrie</div>
        </div>
        <div class='score-badge {meta["badge"]}' style='font-size:1rem;padding:8px 18px;'>
            {score_row['score']}/100 — {meta["label"]}
        </div>
    </div>""", unsafe_allow_html=True)

    data_p   = donnees[donnees["patiente"] == patiente]
    baseline = data_p[data_p["jour"] <= 7]

    metrics = [
        ("Pas / jour",      "pas",               int(round(baseline["pas"].mean())),              int(data_p.iloc[-1]["pas"])),
        ("Sommeil (h)",     "sommeil_heures",     round(baseline["sommeil_heures"].mean(), 2),      round(float(data_p.iloc[-1]["sommeil_heures"]), 2)),
        ("Fréq. cardiaque", "battements_coeur",   int(round(baseline["battements_coeur"].mean())),  int(data_p.iloc[-1]["battements_coeur"])),
        ("Temps écran (h)", "temps_ecran_heures", round(baseline["temps_ecran_heures"].mean(), 2),  round(float(data_p.iloc[-1]["temps_ecran_heures"]), 2)),
    ]

    tooltips_interpretation = {
        "Pas / jour": {
            "positif": "✅ Activité physique stable ou en hausse. La marche régulière réduit les symptômes dépressifs.",
            "neutre":  "⚠️ Légère baisse d'activité. Encourager une marche quotidienne de 20 min minimum.",
            "negatif": "🔴 Activité physique fortement réduite. Signe possible de repli ou de dépression. À surveiller.",
            "seuil_pos": 0, "seuil_neg": -1000
        },
        "Sommeil (h)": {
            "positif": "✅ Durée de sommeil stable. Un sommeil régulier de 7-9h favorise la stabilité de l'humeur.",
            "neutre":  "⚠️ Légère réduction du sommeil. Vérifier les facteurs environnementaux ou anxiogènes.",
            "negatif": "🔴 Sommeil significativement perturbé. Risque accru de rechute dépressive. Intervention recommandée.",
            "seuil_pos": 0, "seuil_neg": -1.5
        },
        "Fréq. cardiaque": {
            "positif": "✅ FC au repos normale (60-100 bpm). Pas de signe de stress physiologique apparent.",
            "neutre":  "⚠️ Légère augmentation de la FC. Peut indiquer un stress ou une anxiété sous-jacente.",
            "negatif": "🔴 FC élevée. Possible état d'anxiété chronique ou effet secondaire médicamenteux à évaluer.",
            "seuil_pos": 5, "seuil_neg": -5
        },
        "Temps écran (h)": {
            "positif": "✅ Temps d'écran maîtrisé. Bonne hygiène numérique favorable à la qualité du sommeil.",
            "neutre":  "⚠️ Légère augmentation. Surveiller l'impact sur le sommeil et l'isolement social.",
            "negatif": "🔴 Temps d'écran très élevé. Associé à l'isolement et à la dégradation du sommeil.",
            "seuil_pos": 0.5, "seuil_neg": 2
        },
    }

    def get_tooltip(label, delta):
        t = tooltips_interpretation.get(label, {})
        if label in ["Pas / jour", "Sommeil (h)"]:
            if delta >= t["seuil_pos"]: return t["positif"]
            elif delta >= t["seuil_neg"]: return t["neutre"]
            else: return t["negatif"]
        else:  # FC et écran : hausse = mauvais
            if delta <= t["seuil_pos"]: return t["positif"]
            elif delta <= t["seuil_neg"]: return t["neutre"]
            else: return t["negatif"]

    m1, m2, m3, m4 = st.columns(4)
    for col, (label, _, base_val, curr_val) in zip([m1, m2, m3, m4], metrics):
        delta     = round(curr_val - base_val, 2)
        is_float  = isinstance(curr_val, float)
        val_str   = f"{curr_val:.2f}" if is_float else str(curr_val)
        delta_str = (f"+{delta:.2f}" if is_float else f"+{int(delta)}") if delta > 0 else (f"{delta:.2f}" if is_float else str(int(delta)))
        dcls      = "delta-neg" if delta < 0 else "delta-warn"
        tooltip   = get_tooltip(label, delta)
        with col:
            st.markdown(f"""
            <div class='metric-box'>
                <div class='metric-tooltip'>{tooltip}</div>
                <div class='metric-label'>{label}</div>
                <div class='metric-val'>{val_str}</div>
                <div class='metric-delta {dcls}'>{delta_str} vs baseline</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Évolution sur 21 jours</div>", unsafe_allow_html=True)

    graphiques_info = {
        "pas": {
            "titre": "Pas par jour", "couleur": "#1565C0", "unite": "pas",
            "ref_val": 8000, "ref_label": "Objectif : 8 000 pas/j",
            "tooltip": "Nombre de pas quotidiens. En dessous de 5 000 pas/j, le risque de symptômes dépressifs augmente significativement."
        },
        "sommeil_heures": {
            "titre": "Sommeil (heures)", "couleur": "#00BCD4", "unite": "h",
            "ref_val": 8, "ref_label": "Recommandé : 7–9 h/nuit",
            "tooltip": "Durée de sommeil nocturne. Un sommeil inférieur à 6h est un facteur de risque de rechute dépressive."
        },
        "battements_coeur": {
            "titre": "Fréquence cardiaque", "couleur": "#EF4444", "unite": "bpm",
            "ref_val": 80, "ref_label": "Normal : 60–100 bpm",
            "tooltip": "FC au repos. Une FC élevée de façon chronique peut signaler un état anxieux ou un effet indésirable médicamenteux."
        },
    }

    col1, col2, col3 = st.columns(3)
    for col, (metric, info) in zip([col1, col2, col3], graphiques_info.items()):
        with col:
            st.markdown(f"""
            <div style='background:#EFF6FF;border-radius:8px;padding:8px 12px;margin-bottom:8px;
                        border-left:3px solid {info["couleur"]};font-size:0.75rem;color:#1E40AF;font-weight:500;'>
                💡 {info["tooltip"]}
            </div>""", unsafe_allow_html=True)

            fig = px.line(data_p, x="jour", y=metric, title=info["titre"],
                          color_discrete_sequence=[info["couleur"]], line_shape="spline")
            fig.add_hline(y=info["ref_val"], line_dash="dot", line_color="#94A3B8",
                          annotation_text=info["ref_label"], annotation_font_color="#94A3B8", annotation_font_size=10)
            fig.add_vline(x=7, line_dash="dot", line_color="#CBD5E1",
                          annotation_text="Baseline", annotation_font_color="#CBD5E1", annotation_font_size=10)
            fig.update_traces(
                line_width=2.5,
                hovertemplate=f"<b>Jour %{{x}}</b><br>{info['titre']} : %{{y:.1f}} {info['unite']}<br><i style='color:#94A3B8'>{info['ref_label']}</i><extra></extra>",
            )
            fig.update_layout(
                paper_bgcolor="#ffffff", plot_bgcolor="#F8FAFC",
                font=dict(family="Nunito, sans-serif", color="#0D1B3E", size=11),
                showlegend=False,
                xaxis=dict(showgrid=False, title="Jour", title_font_size=10),
                yaxis=dict(gridcolor="#E2E8F0", title=info["unite"], title_font_size=10),
                margin=dict(t=36, b=16, l=10, r=10),
                title_font_size=13, title_font_color="#0D1B3E", height=240,
                hoverlabel=dict(bgcolor="#0D1B3E", font_color="#E2E8F0", font_size=12),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-title'>Analyse clinique</div>", unsafe_allow_html=True)
    commentaire = st.text_area(
        f"Observations pour {patiente}",
        value=st.session_state.commentaires[patiente],
        placeholder="Ex : Augmentation de la FC depuis J12. Troubles du sommeil persistants. Prévoir consultation...",
        height=100
    )
    col_save, col_info = st.columns([1, 4])
    with col_save:
        if st.button("Enregistrer"):
            st.session_state.commentaires[patiente] = commentaire
            st.success("✓ Analyse enregistrée.")
    with col_info:
        if st.session_state.commentaires[patiente]:
            st.info(f"Dernière note : {st.session_state.commentaires[patiente][:90]}…")

    st.markdown(f"""
    <div class='coaching-box'>
        <div class='coaching-tag'>🤖 Message de suivi automatique — Mood-IoT IA</div>
        <div class='coaching-text'>{score_row['message_coaching']}</div>
    </div>""", unsafe_allow_html=True)

# ══ PAGE 3 — NOTIFICATIONS ══
elif "Notifications" in page:
    st.markdown("""
    <div class='page-header'>
        <div class='page-title'>Notifications</div>
        <div class='page-subtitle'>Alertes cliniques et événements patientes — Mood-IoT</div>
    </div>""", unsafe_allow_html=True)

    for _, row in derniers_scores[derniers_scores["niveau"] == 3].iterrows():
        existe = any(n["patiente"] == row["patiente"] for n in st.session_state.notifications)
        if not existe:
            st.session_state.notifications.append({
                "patiente": row["patiente"], "score": row["score"],
                "heure": "Automatique", "lue": False,
                "message": f"Alerte critique : score de {row['score']}/100 pour {row['patiente']}"
            })

    nb_non_lues = len([n for n in st.session_state.notifications if not n.get("lue")])
    if not st.session_state.notifications:
        st.markdown("""<div style='background:#fff;border-radius:12px;padding:40px;border:1px solid #E5E7EB;
                    text-align:center;color:#64748B;font-size:0.875rem;font-weight:500;'>
            ✓ Aucune notification pour le moment.</div>""", unsafe_allow_html=True)
    else:
        col_h, col_btn = st.columns([5, 1])
        with col_h:
            st.markdown(f"<div style='font-size:0.85rem;color:#64748B;padding:6px 0;font-weight:600;'>{nb_non_lues} non lue{'s' if nb_non_lues > 1 else ''} sur {len(st.session_state.notifications)}</div>", unsafe_allow_html=True)
        with col_btn:
            if st.button("Tout lire"):
                for n in st.session_state.notifications: n["lue"] = True
                st.rerun()
        for i, notif in enumerate(st.session_state.notifications):
            lue = notif.get("lue", False)
            col_n, col_b = st.columns([8, 1])
            with col_n:
                st.markdown(f"""
                <div class='notif-card {"notif-read" if lue else "notif-unread"}'>
                    <div class='{"notif-dot-off" if lue else "notif-dot-on"}'></div>
                    <div class='notif-body'>
                        <div class='notif-patient'>{notif["patiente"]}
                            <span style='font-weight:600;color:#64748B;'> — Score : {notif["score"]}/100</span>
                        </div>
                        <div class='notif-msg'>{notif["message"]}</div>
                        <div class='notif-time'>{notif["heure"]}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            with col_b:
                if not lue:
                    st.markdown("<div style='margin-top:10px'>", unsafe_allow_html=True)
                    if st.button("Lu", key=f"lu_{i}"):
                        st.session_state.notifications[i]["lue"] = True
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

# ══ PAGE 4 — MESSAGERIE ══
elif page == "Messagerie":
    st.markdown("""
    <div class='page-header'>
        <div class='page-title'>Messagerie</div>
        <div class='page-subtitle'>Communication sécurisée médecin – patiente — Mood-IoT</div>
    </div>""", unsafe_allow_html=True)

    patiente  = st.selectbox("Conversation avec", donnees["patiente"].unique())
    score_row = derniers_scores[derniers_scores["patiente"] == patiente].iloc[0]
    meta      = niveau_meta(int(score_row["niveau"]))
    ini       = initiales(patiente)

    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:12px;margin-bottom:14px;
                background:#ffffff;border-radius:10px;padding:14px 18px;
                border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);'>
        <div class='patient-avatar {meta["av"]}' style='width:36px;height:36px;font-size:0.82rem;'>{ini}</div>
        <div style='flex:1;'>
            <div style='font-size:0.92rem;font-weight:800;color:#0D1B3E;'>{patiente}</div>
            <div style='font-size:0.75rem;color:#6B7280;font-weight:500;'>Psychiatrie — Suivi actif</div>
        </div>
        <div class='score-badge {meta["badge"]}'>{score_row['score']}/100</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class='chat-legend'>
        <span><span class='legend-dot' style='background:#0D1B3E;'></span>Médecin</span>
        <span><span class='legend-dot' style='background:#E5E7EB;border:1px solid #D1D5DB;'></span>Patiente</span>
        <span><span class='legend-dot' style='background:#1565C0;'></span>Assistant IA — Mood-IoT</span>
    </div>""", unsafe_allow_html=True)

    msgs_html = ""
    if not st.session_state.messages.get(patiente):
        msgs_html = "<div class='chat-empty'>Aucun message dans cette conversation.</div>"
    else:
        current_jour = None
        for msg in st.session_state.messages[patiente]:
            jour = msg.get("jour")
            if jour is not None and jour != current_jour:
                current_jour = jour
                msgs_html += f"<div class='chat-day-sep'>Jour {jour}</div>"
            if msg["role"] == "medecin":
                msgs_html += f"""<div class='msg-doctor'><div>
                    <div class='bbl-doc'>{msg['texte']}</div>
                    <span class='bbl-time time-r'>{msg['heure']}</span>
                </div></div>"""
            elif msg["role"] == "ia":
                msgs_html += f"""<div class='msg-ia'><div class='bbl-ia-wrapper'>
                    <div class='bbl-ia-label'>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" style="display:inline;vertical-align:middle;">
                        <rect x="3" y="8" width="18" height="13" rx="2" stroke="#1565C0" stroke-width="2"/>
                        <path d="M9 3h6M12 3v5" stroke="#1565C0" stroke-width="2" stroke-linecap="round"/>
                        <circle cx="9" cy="14" r="1.5" fill="#1565C0"/><circle cx="15" cy="14" r="1.5" fill="#1565C0"/>
                      </svg>
                      Assistant IA · Mood-IoT
                    </div>
                    <div class='bbl-ia'>{msg['texte']}</div>
                    <span class='bbl-time'>{msg['heure']}</span>
                </div></div>"""
            else:
                msgs_html += f"""<div class='msg-patient'><div>
                    <div class='bbl-pat'>{msg['texte']}</div>
                    <span class='bbl-time'>{msg['heure']}</span>
                </div></div>"""

    st.markdown(f"<div class='chat-box'>{msgs_html}</div>", unsafe_allow_html=True)

    col_msg, col_btn = st.columns([5, 1])
    with col_msg:
        nouveau = st.text_input("Message", placeholder="Écrire un message…", label_visibility="collapsed")
    with col_btn:
        if st.button("Envoyer"):
            if nouveau.strip():
                st.session_state.messages[patiente].append({
                    "role": "medecin", "texte": nouveau, "heure": datetime.now().strftime("%H:%M")
                })
                st.rerun()

    st.markdown("""<div style='font-size:0.72rem;font-weight:800;color:#1565C0;
                text-transform:uppercase;letter-spacing:0.08em;margin:12px 0 6px 0;'>
        Réponses rapides</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, (label, texte) in zip([c1, c2, c3], [
        ("Appel prévu",       "Je vous appelle dans la journée pour faire le point."),
        ("Rappel traitement", "Pensez à prendre votre traitement ce soir."),
        ("Encouragement",     "Vous faites du bon travail, continuez ainsi."),
    ]):
        with col:
            if st.button(label, key=f"rapide_{label}"):
                st.session_state.messages[patiente].append({
                    "role": "medecin", "texte": texte, "heure": datetime.now().strftime("%H:%M")
                })
                st.rerun()
                