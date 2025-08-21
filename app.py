import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime

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
st.header("Bem-vindo ao Dashboard de Avaliação de Riscos")

# Exibe HTML com cards e seção objetivo
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()

    components.html(
        html_code,
        height=800,
        scrolling=True
    )
except FileNotFoundError:
    st.error("Arquivo index.html não encontrado!")

# Botão de logout
if st.button("Sair", key="logout_btn"):
    st.session_state.logado = False
    st.experimental_rerun()

