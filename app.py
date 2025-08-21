import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import numpy as np

# ---------- CONFIGURAÇÃO DA PÁGINA ----------
st.set_page_config(
    page_title="Dashboard de Avaliação de Riscos",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- LOGIN ----------
if "logado" not in st.session_state:
    st.session_state.logado = False

USUARIOS = {"CGU": "eiju@1015@cgu", "fabio": "1234"}

def autenticar(usuario, senha):
    return USUARIOS.get(usuario) == senha

if not st.session_state.logado:
    st.title("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", key="login_btn"):
        if autenticar(usuario, senha):
            st.session_state.logado = True
            st.success("Login bem-sucedido! ✅")
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()  # Interrompe execução até o login

# ---------- APP PRINCIPAL ----------
# Lê o arquivo HTML (cards + seção objetivo)
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()

    # Exibe HTML em iframe maior
    components.html(
        html_code,
        height=1500,  # altura aumentada
        scrolling=True
    )
except FileNotFoundError:
    st.error("Arquivo index.html não encontrado!")

# ---------- BOTÃO DE LOGOUT ----------
if st.button("Sair", key="logout_btn"):
    st.session_state.logado = False
    st.experimental_rerun()

# ---------- DASHBOARD SIMPLES ----------
st.subheader("Dashboard")
st.write("Aqui você pode colocar gráficos e métricas usando Plotly, pandas, etc.")

# Exemplo rápido de gráfico Plotly
df = pd.DataFrame({
    "Data": pd.date_range(start="2025-01-01", periods=10, freq="D"),
    "Risco": np.random.randint(1, 10, 10)
})

fig = px.line(df, x="Data", y="Risco", title="Evolução de Riscos")
st.plotly_chart(fig, use_container_width=True)


