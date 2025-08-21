import streamlit as st
import streamlit.components.v1 as components

# ---------- LOGIN ----------
if "logado" not in st.session_state:
    st.session_state.logado = False

USUARIOS = {"CGU": "eiju@1015@cgu", "fabio": "1234"}

def autenticar(usuario, senha):
    return USUARIOS.get(usuario) == senha

if not st.session_state.logado:
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if autenticar(usuario, senha):
            st.session_state.logado = True
            st.success("Login bem-sucedido! ✅")
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()

# ---------- RENDERIZAR INDEX.HTML ----------
with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Ajuste a altura conforme o tamanho da página
components.html(html, height=1200, scrolling=True)

fig = px.line(df, x="Data", y="Risco", title="Evolução de Riscos")
st.plotly_chart(fig, use_container_width=True)


