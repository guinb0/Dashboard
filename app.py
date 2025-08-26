import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import sqlite3
import hashlib
import json
import os

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Avaliação de Riscos",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Escalas de avaliação baseadas na metodologia TCU
ESCALAS_IMPACTO = {
    "Muito baixo": {
        "valor": 1,
        "descricao": "Degradação de operações causando impactos mínimos nos objetivos"
    },
    "Baixo": {
        "valor": 2,
        "descricao": "Degradação de operações causando impactos pequenos nos objetivos"
    },
    "Médio": {
        "valor": 5,
        "descricao": "Interrupção de operações causando impactos significativos mas recuperáveis"
    },
    "Alto": {
        "valor": 8,
        "descricao": "Interrupção de operações causando impactos de reversão muito difícil"
    },
    "Muito alto": {
        "valor": 10,
        "descricao": "Paralisação de operações causando impactos irreversíveis/catastróficos"
    }
}

ESCALAS_PROBABILIDADE = {
    "Muito baixa": {
        "valor": 1,
        "descricao": "Evento improvável de ocorrer. Não há elementos que indiquem essa possibilidade"
    },
    "Baixa": {
        "valor": 2,
        "descricao": "Evento raro de ocorrer. Poucos elementos indicam essa possibilidade"
    },
    "Média": {
        "valor": 5,
        "descricao": "Evento possível de ocorrer. Elementos indicam moderadamente essa possibilidade"
    },
    "Alta": {
        "valor": 8,
        "descricao": "Evento provável de ocorrer. Elementos indicam consistently essa possibilidade"
    },
    "Muito alta": {
        "valor": 10,
        "descricao": "Evento praticamente certo de ocorrer. Elementos indicam claramente essa possibilidade"
    }
}

# Modalidades de mitigação padrão (baseadas na planilha fornecida)
MODALIDADES_PADRAO = [
    "Permuta por imóvel já construído",
    "Permuta por edificação a construir (terreno terceiros)",
    "Permuta por obra (terreno da União)",
    "Build to Suit (terreno da União)",
    "Contratação com dação em pagamento",
    "Obra pública convencional"
]

# Aspectos a serem considerados para cada risco (extraídos da planilha) - AMPLIADO
ASPECTOS_RISCOS = {
    'Descumprimento do Prazo de entrega': {
        'impacto': [
            "Condições de segurança/conservação do imóvel utilizado pelo órgão",
            "Custo de locação do imóvel utilizado pelo órgão", 
            "Taxa de ocupação do imóvel utilizado pelo órgão",
            "Impacto na continuidade dos serviços públicos",
            "Custos adicionais com prorrogações contratuais"
        ],
        'probabilidade': [
            "Estrutura de monitoramento e mecanismos contratuais de sanção previstos",
            "Complexidade técnica do empreendimento e riscos externos (licenças, clima, logística)",
            "Grau de maturidade dos projetos disponibilizados",
            "Características do local de implantação",
            "Histórico de cumprimento de prazos da empresa contratada",
            "Capacidade técnica e financeira do contratado"
        ]
    },
    'Indisponibilidade de imóveis públicos p/ implantação ou dação em permuta': {
        'impacto': [
            "Quantidade de imóveis disponíveis e nível de desembraço desses imóveis",
            "Impacto na viabilidade econômica da operação",
            "Necessidade de recursos orçamentários adicionais",
            "Comprometimento da estratégia de otimização do patrimônio público"
        ],
        'probabilidade': [
            "Quantidade de imóveis disponíveis e nível de desembraço desses imóveis",
            "Processos judiciais em andamento sobre os imóveis",
            "Situação registral e documental dos imóveis",
            "Interesse de outros órgãos públicos nos mesmo imóveis",
            "Complexidade dos procedimentos de desafetação"
        ]
    },
    'Condições de mercado desfavoráveis': {
        'impacto': [
            "Condições de segurança/conservação do imóvel utilizado pelo órgão",
            "Custo de locação do imóvel utilizado pelo órgão",
            "Taxa de ocupação do imóvel utilizado pelo órgão",
            "Redução da competitividade no processo licitatório",
            "Aumento dos custos da operação"
        ],
        'probabilidade': [
            "Valor do investimento necessário (valor imóveis x torna x construção)",
            "Atratividade dos lotes ofertados (valor; possibilidades de utilização; tendências do mercado)",
            "Grau de especialização exigida do investidor",
            "Grau de aquecimento do mercado x taxa de juros x rentabilidade esperada",
            "Manifestações de interesse ou consultas públicas realizadas",
            "Histórico de certames semelhantes e nível de participação",
            "Cenário econômico nacional e setorial"
        ]
    },
    'Abandono da obra pela empresa': {
        'impacto': [
            "Condições de segurança/conservação do imóvel utilizado pelo órgão",
            "Custo de locação do imóvel utilizado pelo órgão",
            "Taxa de ocupação do imóvel utilizado pelo órgão",
            "Custos de nova licitação e retomada da obra",
            "Atraso significativo na entrega do empreendimento"
        ],
        'probabilidade': [
            "Requisitos técnicos e financeiros a serem previstos no processo de seleção",
            "Garantias contratuais e outras salvaguardas a serem previstas",
            "Garantias contratuais e outras salvaguardas previstas na modelagem",
            "Percentual do novo prédio a ser ocupado pela Administração",
            "Situação financeira e histórico da empresa contratada",
            "Robustez dos mecanismos de acompanhamento da execução"
        ]
    },
    'Baixa rentabilização do estoque de imóveis': {
        'impacto': [
            "Valor dos imóveis dados em permuta na operação frente ao valor do imóvel adquirido",
            "Amplitude do potencial de valorização dos imóveis dados em permuta",
            "Grau de contribuição da operação para a redução de imóveis ociosos",
            "Prejuízo patrimonial para a União",
            "Redução da eficiência da gestão patrimonial"
        ],
        'probabilidade': [
            "Grau de contribuição da operação para a redução de imóveis ociosos",
            "Adequação do uso proposto às características do imóvel",
            "Potencial de economia de despesas (Eficiência do plano de gestão do ativo)",
            "Eficiência do plano de gestão do ativo pós-permuta",
            "Demanda do mercado e probabilidade de valorização dos imóveis",
            "Localização e características dos imóveis ofertados",
            "Estratégia de alienação ou exploração econômica"
        ]
    },
    'Dotação orçamentária insuficiente': {
        'impacto': [
            "Condições de segurança/conservação do imóvel utilizado pelo órgão",
            "Custo de locação do imóvel utilizado pelo órgão",
            "Taxa de ocupação do imóvel utilizado pelo órgão",
            "Percentual do valor da operação que será custeada com recursos orçamentários",
            "Inviabilização completa do projeto",
            "Necessidade de renegociação contratual"
        ],
        'probabilidade': [
            "Peso da previsão de despesa em relação à dotação orçamentária de investimento",
            "Informações constantes da LOA e PPA",
            "Histórico de contingenciamento do órgão",
            "Peso político dos órgãos beneficiários",
            "Cenário fiscal e orçamentário da União",
            "Priorização do projeto no planejamento governamental"
        ]
    },
    'Questionamento jurídico': {
        'impacto': [
            "Paralisação completa ou parcial do projeto",
            "Custos adicionais com defesa jurídica",
            "Perda de credibilidade institucional",
            "Necessidade de reformulação da modelagem",
            "Impacto na continuidade dos serviços públicos"
        ],
        'probabilidade': [
            "Complexidade e inovação da modelagem jurídica adotada",
            "Precedentes jurisprudenciais sobre modalidades similares",
            "Robustez da fundamentação legal da contratação",
            "Histórico de questionamentos em projetos similares",
            "Atuação de órgãos de controle externo",
            "Transparência e aderência aos princípios da administração pública",
            "Qualidade da documentação jurídica do processo"
        ]
    },
    'Baixa qualidade dos serviços entregues': {
        'impacto': [
            "Custos adicionais com reparos e adequações",
            "Insatisfação dos usuários finais",
            "Redução da vida útil do empreendimento",
            "Necessidade de nova contratação para correções",
            "Comprometimento da imagem institucional",
            "Impacto na funcionalidade operacional"
        ],
        'probabilidade': [
            "Rigor dos critérios de qualificação técnica",
            "Estrutura de fiscalização e acompanhamento técnico",
            "Especificações técnicas e padrões de qualidade definidos",
            "Histórico de qualidade dos serviços da empresa contratada",
            "Mecanismos contratuais de garantia de qualidade",
            "Complexidade técnica dos serviços demandados",
            "Adequação entre o preço contratado e o padrão de qualidade esperado"
        ]
    }
}

# Funções para gerenciamento do banco de dados
def init_db():
    """Inicializa o banco de dados SQLite"""
    conn = sqlite3.connect('riscos.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL)''')
    
    # Tabela de logs de ações
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  username TEXT NOT NULL,
                  acao TEXT NOT NULL,
                  detalhes TEXT)''')
    
    # Inserir usuários padrão se não existirem
    usuarios_padrao = [
        ("SPU 1", hashlib.sha256("1234".encode()).hexdigest()),
        ("SPU 2", hashlib.sha256("1234".encode()).hexdigest()),
        ("SPU 3", hashlib.sha256("1234".encode()).hexdigest())
    ]
    
    for usuario, senha_hash in usuarios_padrao:
        try:
            c.execute("INSERT INTO usuarios (username, password_hash) VALUES (?, ?)", 
                     (usuario, senha_hash))
        except sqlite3.IntegrityError:
            pass  # Usuário já existe
    
    conn.commit()
    conn.close()

def verificar_login(username, password):
    """Verifica se as credenciais são válidas"""
    conn = sqlite3.connect('riscos.db')
    c = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM usuarios WHERE username = ? AND password_hash = ?", 
             (username, password_hash))
    
    resultado = c.fetchone()
    conn.close()
    
    return resultado is not None

def registrar_acao(username, acao, detalhes=None):
    """Registra uma ação no log"""
    conn = sqlite3.connect('riscos.db')
    c = conn.cursor()
    
    c.execute("INSERT INTO logs (username, acao, detalhes) VALUES (?, ?, ?)",
             (username, acao, json.dumps(detalhes) if detalhes else None))
    
    conn.commit()
    conn.close()

def obter_logs():
    """Obtém todos os logs do sistema"""
    conn = sqlite3.connect('riscos.db')
    c = conn.cursor()
    
    c.execute("SELECT timestamp, username, acao, detalhes FROM logs ORDER BY timestamp DESC")
    logs = c.fetchall()
    conn.close()
    
    return logs

def classificar_risco(valor_risco):
    """Classifica o risco baseado no valor calculado"""
    if valor_risco <= 10:
        return "Baixo", "#28a745"
    elif valor_risco <= 25:
        return "Médio", "#ffc107"
    else:
        return "Alto", "#dc3545"

def gerar_relatorio_word():
    """Gera relatório completo e amplo em formato Word"""
    try:
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_ALIGN_VERTICAL
        from docx.oxml.shared import OxmlElement, qn
        from io import BytesIO
        
        # Criar documento
        doc = Document()
        
        # Título principal
        title = doc.add_heading('RELATÓRIO EXECUTIVO DE AVALIAÇÃO DE RISCOS', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtítulo
        subtitle = doc.add_heading('Metodologia TCU - Análise Comparativa de Modalidades de Contratação', level=1)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Informações do relatório
        info_para = doc.add_paragraph()
        info_para.add_run("Data da Análise: ").bold = True
        info_para.add_run(f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        info_para.add_run("\nMetodologia: ").bold = True
        info_para.add_run("Roteiro de Auditoria de Gestão de Riscos - TCU")
        info_para.add_run("\nVersão do Sistema: ").bold = True
        info_para.add_run("2.0 - Análise Ampliada")
        
        doc.add_paragraph()
        
        # 1. RESUMO EXECUTIVO
        doc.add_heading('1. RESUMO EXECUTIVO', level=1)
        
        total_riscos = len(st.session_state.riscos)
        riscos_altos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Alto')
        riscos_medios = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Médio')
        riscos_baixos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Baixo')
        risco_inerente_total = sum(r['risco_inerente'] for r in st.session_state.riscos)
        
        # Calcular melhor e pior modalidade
        risco_acumulado_por_modalidade = {}
        for modalidade in st.session_state.modalidades:
            risco_residual_total = 0
            for risco in st.session_state.riscos:
                if modalidade in risco['modalidades']:
                    fator_mitigacao = risco['modalidades'][modalidade]
                    risco_residual = risco['risco_inerente'] * fator_mitigacao
                    risco_residual_total += risco_residual
            risco_acumulado_por_modalidade[modalidade] = risco_residual_total
        
        melhor_modalidade = min(risco_acumulado_por_modalidade.keys(), 
                               key=lambda x: risco_acumulado_por_modalidade[x])
        pior_modalidade = max(risco_acumulado_por_modalidade.keys(), 
                             key=lambda x: risco_acumulado_por_modalidade[x])
        
        resumo = f"""
        Este relatório apresenta análise quantitativa de {total_riscos} riscos identificados para o projeto, 
        utilizando a metodologia do Tribunal de Contas da União (TCU). A análise incluye avaliação detalhada 
        de impacto e probabilidade, cálculo de riscos inerentes e residuais, e comparação sistemática entre 
        {len(st.session_state.modalidades)} modalidades de contratação.
        
        MÉTRICAS PRINCIPAIS DO PROJETO:
        • Total de Riscos Analisados: {total_riscos}
        • Distribuição por Classificação:
          - Riscos ALTOS: {riscos_altos} ({riscos_altos/total_riscos*100:.1f}%)
          - Riscos MÉDIOS: {riscos_medios} ({riscos_medios/total_riscos*100:.1f}%)
          - Riscos BAIXOS: {riscos_baixos} ({riscos_baixos/total_riscos*100:.1f}%)
        • Risco Inerente Total: {risco_inerente_total:.1f} pontos
        
        RESULTADO DA ANÁLISE COMPARATIVA:
        • MODALIDADE RECOMENDADA: {melhor_modalidade}
          - Risco Residual: {risco_acumulado_por_modalidade[melhor_modalidade]:.1f} pontos
        • MODALIDADE DE MAIOR RISCO: {pior_modalidade}
          - Risco Residual: {risco_acumulado_por_modalidade[pior_modalidade]:.1f} pontos
        • DIFERENÇA DE RISCO: {risco_acumulado_por_modalidade[pior_modalidade] - risco_acumulado_por_modalidade[melhor_modalidade]:.1f} pontos
        """
        doc.add_paragraph(resumo)
        
        # Salvar em buffer
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer
        
    except ImportError:
        st.error("📋 Para gerar relatórios Word, instale a biblioteca python-docx: pip install python-docx")
        return None
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")
        return None

def calcular_risco_inerente(impacto, probabilidade):
    """Calcula o risco inerente (Impacto x Probabilidade)"""
    return impacto * probabilidade

def inicializar_dados():
    """Inicializa os dados padrão se não existirem"""
    if 'riscos' not in st.session_state:
        st.session_state.riscos = [
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Descumprimento do Prazo de entrega',
                'descricao': 'Histórico de atrasos em obras públicas é elevado, especialmente em projetos complexos.',
                'impacto_nivel': 'Alto',
                'impacto_valor': 8,
                'probabilidade_nivel': 'Alta',
                'probabilidade_valor': 8,
                'risco_inerente': 64,
                'classificacao': 'Alto',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.1,
                    'Permuta por edificação a construir (terreno terceiros)': 0.8,
                    'Permuta por obra (terreno da União)': 0.8,
                    'Build to Suit (terreno da União)': 0.8,
                    'Contratação com dação em pagamento': 0.8,
                    'Obra pública convencional': 0.8
                }
            },
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Indisponibilidade de imóveis públicos p/ implantação ou dação em permuta',
                'descricao': 'Dificuldades na disponibilização de imóveis públicos adequados para permuta ou implantação.',
                'impacto_nivel': 'Muito alto',
                'impacto_valor': 10,
                'probabilidade_nivel': 'Média',
                'probabilidade_valor': 5,
                'risco_inerente': 50,
                'classificacao': 'Alto',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.8,
                    'Permuta por edificação a construir (terreno terceiros)': 0.9,
                    'Permuta por obra (terreno da União)': 0.9,
                    'Build to Suit (terreno da União)': 0.9,
                    'Contratação com dação em pagamento': 0.2,
                    'Obra pública convencional': 0.1
                }
            },
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Abandono da obra pela empresa',
                'descricao': 'O histórico de abandono de obras públicas indica que tais eventos ocorrem, mas são raros.',
                'impacto_nivel': 'Médio',
                'impacto_valor': 5,
                'probabilidade_nivel': 'Baixa',
                'probabilidade_valor': 2,
                'risco_inerente': 10,
                'classificacao': 'Médio',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.1,
                    'Permuta por edificação a construir (terreno terceiros)': 0.6,
                    'Permuta por obra (terreno da União)': 0.2,
                    'Build to Suit (terreno da União)': 0.2,
                    'Contratação com dação em pagamento': 0.4,
                    'Obra pública convencional': 0.4
                }
            },
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Baixa rentabilização do estoque de imóveis',
                'descricao': 'O histórico de operações com soluções individuais, mas que pouco colaboram com o incremento do uso racional dos imóveis da União é elevado.',
                'impacto_nivel': 'Alto',
                'impacto_valor': 8,
                'probabilidade_nivel': 'Alta',
                'probabilidade_valor': 8,
                'risco_inerente': 64,
                'classificacao': 'Alto',
                'modalidades': {
                    'Permuta por imóvel já construído': 1.0,
                    'Permuta por edificação a construir (terreno terceiros)': 1.0,
                    'Permuta por obra (terreno da União)': 0.2,
                    'Build to Suit (terreno da União)': 0.6,
                    'Contratação com dação em pagamento': 0.4,
                    'Obra pública convencional': 0.8
                }
            },
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Dotação orçamentária insuficiente',
                'descricao': 'Impacto total, somente superável no caso de a SPU disponibilizar diversos imóveis de alto interesse pelo mercado.',
                'impacto_nivel': 'Muito alto',
                'impacto_valor': 10,
                'probabilidade_nivel': 'Muito alta',
                'probabilidade_valor': 10,
                'risco_inerente': 100,
                'classificacao': 'Alto',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.0,
                    'Permuta por edificação a construir (terreno terceiros)': 0.1,
                    'Permuta por obra (terreno da União)': 0.1,
                    'Build to Suit (terreno da União)': 0.4,
                    'Contratação com dação em pagamento': 0.4,
                    'Obra pública convencional': 1.0
                }
            },
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Questionamento jurídico',
                'descricao': 'Possibilidade de questionamentos jurídicos quanto à legalidade da modalidade de contratação escolhida, especialmente em modalidades inovadoras ou complexas.',
                'impacto_nivel': 'Médio',
                'impacto_valor': 5,
                'probabilidade_nivel': 'Média',
                'probabilidade_valor': 5,
                'risco_inerente': 25,
                'classificacao': 'Médio',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.2,
                    'Permuta por edificação a construir (terreno terceiros)': 0.4,
                    'Permuta por obra (terreno da União)': 0.4,
                    'Build to Suit (terreno da União)': 0.4,
                    'Contratação com dação em pagamento': 0.6,
                    'Obra pública convencional': 0.1
                }
            },
            {
                'objetivo_chave': 'Entrega da obra no prazo, com qualidade e preço compatível aos praticados no mercado e promovendo o melhor uso racional do conjunto de imóveis da União',
                'risco_chave': 'Baixa qualidade dos serviços entregues',
                'descricao': 'Risco de que os serviços ou obras entregues não atendam aos padrões de qualidade exigidos, comprometendo a funcionalidade e durabilidade do empreendimento.',
                'impacto_nivel': 'Médio',
                'impacto_valor': 5,
                'probabilidade_nivel': 'Baixa',
                'probabilidade_valor': 2,
                'risco_inerente': 10,
                'classificacao': 'Médio',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.8,
                    'Permuta por edificação a construir (terreno terceiros)': 0.8,
                    'Permuta por obra (terreno da União)': 0.4,
                    'Build to Suit (terreno da União)': 0.4,
                    'Contratação com dação em pagamento': 0.2,
                    'Obra pública convencional': 0.2
                }
            }
        ]
    if 'modalidades' not in st.session_state:
        st.session_state.modalidades = MODALIDADES_PADRAO.copy()

def cadastro_riscos():
    st.header("📝 Cadastro de Riscos")
    
    if st.session_state.riscos:
        st.info(f"💡 **{len(st.session_state.riscos)} riscos** da planilha já estão carregados. Use o formulário abaixo para adicionar novos riscos.")
        st.info("💡 **Dica:** Para personalizar riscos existentes conforme seu caso concreto, use a aba '✏️ Editar Riscos'")
    
    with st.form("cadastro_risco"):
        col1, col2 = st.columns(2)
        
        with col1:
            objetivo_chave = st.text_area(
                "Objetivo-Chave:",
                placeholder="Ex: Entrega da obra no prazo, com qualidade e preço compatível..."
            )
            
            risco_chave = st.text_input(
                "Risco-Chave:",
                placeholder="Ex: Descumprimento do Prazo de entrega"
            )
            
            descricao_risco = st.text_area(
                "Descrição/Justificativa do Risco:",
                placeholder="Descreva os aspectos que levam a este risco..."
            )
            
            contexto_especifico = st.text_area(
                "Características do Caso Concreto:",
                placeholder="Ex: Localização, tipo de obra, prazo, complexidade...",
                help="Aspectos específicos do seu projeto que influenciam este risco"
            )
        
        with col2:
            # Avaliação de Impacto
            st.subheader("🎯 Avaliação de Impacto")
            impacto_nivel = st.selectbox(
                "Nível de Impacto:",
                list(ESCALAS_IMPACTO.keys()),
                help="Selecione o nível de impacto baseado na escala TCU"
            )
            st.info(f"**{impacto_nivel}** (Valor: {ESCALAS_IMPACTO[impacto_nivel]['valor']})")
            st.caption(ESCALAS_IMPACTO[impacto_nivel]['descricao'])
            
            # Avaliação de Probabilidade
            st.subheader("📊 Avaliação de Probabilidade")
            probabilidade_nivel = st.selectbox(
                "Nível de Probabilidade:",
                list(ESCALAS_PROBABILIDADE.keys()),
                help="Selecione o nível de probabilidade baseado na escala TCU"
            )
            st.info(f"**{probabilidade_nivel}** (Valor: {ESCALAS_PROBABILIDADE[probabilidade_nivel]['valor']})")
            st.caption(ESCALAS_PROBABILIDADE[probabilidade_nivel]['descricao'])
        
        # Cálculo automático do risco inerente
        impacto_valor = ESCALAS_IMPACTO[impacto_nivel]['valor']
        probabilidade_valor = ESCALAS_PROBABILIDADE[probabilidade_nivel]['valor']
        risco_inerente = calcular_risco_inerente(impacto_valor, probabilidade_valor)
        classificacao, cor = classificar_risco(risco_inerente)
        
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Impacto", impacto_valor)
        with col2:
            st.metric("Probabilidade", probabilidade_valor)
        with col3:
            st.metric("Risco Inerente", f"{risco_inerente} - {classificacao}")
        
        # Avaliação por modalidade
        st.subheader("🔄 Avaliação por Modalidades")
        st.info("Para cada modalidade, defina os fatores de mitigação (0.0 = elimina totalmente o risco, 1.0 = não mitiga)")
        
        modalidades_avaliacao = {}
        cols = st.columns(min(3, len(st.session_state.modalidades)))
        
        for i, modalidade in enumerate(st.session_state.modalidades):
            with cols[i % len(cols)]:
                fator = st.slider(
                    f"{modalidade}:",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    step=0.1,
                    key=f"modalidade_{i}"
                )
                modalidades_avaliacao[modalidade] = fator
                
                # Calcular risco residual
                risco_residual = risco_inerente * fator
                class_residual, _ = classificar_risco(risco_residual)
                st.caption(f"Risco Residual: {risco_residual:.1f} ({class_residual})")
        
        submitted = st.form_submit_button("💾 Salvar Risco", type="primary")
        
        if submitted and objetivo_chave and risco_chave:
            novo_risco = {
                'objetivo_chave': objetivo_chave,
                'risco_chave': risco_chave,
                'descricao': descricao_risco,
                'contexto_especifico': contexto_especifico,
                'impacto_nivel': impacto_nivel,
                'impacto_valor': impacto_valor,
                'probabilidade_nivel': probabilidade_nivel,
                'probabilidade_valor': probabilidade_valor,
                'risco_inerente': risco_inerente,
                'classificacao': classificacao,
                'modalidades': modalidades_avaliacao.copy(),
                'personalizado': True,  # Marcar como personalizado
                'criado_por': st.session_state.user,
                'data_criacao': datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            
            st.session_state.riscos.append(novo_risco)
            
            # Registrar a ação no log
            registrar_acao(
                st.session_state.user, 
                "Criou risco", 
                {"risco": risco_chave, "detalhes": novo_risco}
            )
            
            st.success(f"✅ Risco '{risco_chave}' salvo com sucesso!")
            st.rerun()

def editar_riscos():
    st.header("✏️ Editar Riscos Existentes")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado para editar. Vá para a aba 'Cadastro de Riscos' para adicionar riscos.")
        return
    
    st.info("💡 **Personalize a avaliação** dos riscos conforme as características específicas do seu caso concreto.")
    
    # Seleção do risco para editar
    col1, col2 = st.columns([2, 1])
    
    with col1:
        opcoes_riscos = [f"{i+1}. {risco['risco_chave']}" for i, risco in enumerate(st.session_state.riscos)]
        risco_selecionado_str = st.selectbox(
            "Selecione o risco para editar:",
            opcoes_riscos,
            help="Escolha o risco que deseja personalizar"
        )
    
    with col2:
        if st.button("🔄 Recarregar página"):
            st.rerun()
    
    if not risco_selecionado_str:
        return
    
    # Extrair índice do risco selecionado
    indice_risco = int(risco_selecionado_str.split('.')[0]) - 1
    risco_atual = st.session_state.riscos[indice_risco]
    
    # Mostrar informações atuais do risco
    with st.expander("📋 Informações atuais do risco", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Impacto Atual", f"{risco_atual['impacto_valor']} ({risco_atual['impacto_nivel']})")
        with col2:
            st.metric("Probabilidade Atual", f"{risco_atual['probabilidade_valor']} ({risco_atual['probabilidade_nivel']})")
        with col3:
            st.metric("Risco Inerente Atual", f"{risco_atual['risco_inerente']} ({risco_atual['classificacao']})")
    
    # Formulário de edição
    with st.form(f"editar_risco_{indice_risco}"):
        st.subheader(f"🎯 Editando: {risco_atual['risco_chave']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Edição da descrição/justificativa
            nova_descricao = st.text_area(
                "Justificativa para o caso concreto:",
                value=risco_atual['descricao'],
                help="Descreva as características específicas do seu caso que justificam a avaliação"
            )
            
            # Avaliação de Impacto
            st.subheader("🎯 Reavaliação de Impacto")
            st.caption("Considere as características específicas do seu projeto:")
            
            # Mostrar aspectos a serem considerados para IMPACTO
            risco_nome = risco_atual['risco_chave']
            if risco_nome in ASPECTOS_RISCOS:
                with st.expander("💡 Aspectos a serem considerados para IMPACTO", expanded=True):
                    st.write("**Considere os seguintes aspectos ao avaliar o impacto:**")
                    for i, aspecto in enumerate(ASPECTOS_RISCOS[risco_nome]['impacto'], 1):
                        st.write(f"• {aspecto}")
                    st.info("💡 **Dica:** Analise como cada aspecto se aplica ao seu caso específico antes de definir o nível de impacto.")
            
            # Encontrar o índice atual do impacto
            niveis_impacto = list(ESCALAS_IMPACTO.keys())
            indice_impacto_atual = niveis_impacto.index(risco_atual['impacto_nivel'])
            
            novo_impacto_nivel = st.selectbox(
                "Novo Nível de Impacto:",
                niveis_impacto,
                index=indice_impacto_atual,
                help="Baseado nas características do seu caso concreto"
            )
            
            # Mostrar a escala para referência
            with st.expander("📖 Consultar Escala de Impacto"):
                for nivel, dados in ESCALAS_IMPACTO.items():
                    emoji = "👉" if nivel == novo_impacto_nivel else "•"
                    st.write(f"{emoji} **{nivel}** (Valor: {dados['valor']}): {dados['descricao']}")
        
        with col2:
            # Contexto específico
            st.subheader("🗗️ Características do Caso Concreto")
            contexto_especifico = st.text_area(
                "Fatores específicos que influenciam este risco:",
                value=risco_atual.get('contexto_especifico', ''),
                placeholder="Ex: Localização, tipo de obra, prazo, complexidade, recursos disponíveis...",
                help="Descreva os aspectos únicos do seu projeto"
            )
            
            # Avaliação de Probabilidade
            st.subheader("📊 Reavaliação de Probabilidade")
            st.caption("Considere a realidade do seu contexto:")
            
            # Mostrar aspectos a serem considerados para PROBABILIDADE
            if risco_nome in ASPECTOS_RISCOS:
                with st.expander("💡 Aspectos a serem considerados para PROBABILIDADE", expanded=True):
                    st.write("**Considere os seguintes aspectos ao avaliar a probabilidade:**")
                    for i, aspecto in enumerate(ASPECTOS_RISCOS[risco_nome]['probabilidade'], 1):
                        st.write(f"• {aspecto}")
                    st.info("💡 **Dica:** Analise como cada aspecto se aplica ao seu contexto antes de definir o nível de probabilidade.")
            
            # Encontrar o índice atual da probabilidade
            niveis_probabilidade = list(ESCALAS_PROBABILIDADE.keys())
            indice_probabilidade_atual = niveis_probabilidade.index(risco_atual['probabilidade_nivel'])
            
            nova_probabilidade_nivel = st.selectbox(
                "Novo Nível de Probabilidade:",
                niveis_probabilidade,
                index=indice_probabilidade_atual,
                help="Baseado na realidade do seu contexto"
            )
            
            # Mostrar a escala para referência
            with st.expander("📖 Consultar Escala de Probabilidade"):
                for nivel, dados in ESCALAS_PROBABILIDADE.items():
                    emoji = "👉" if nivel == nova_probabilidade_nivel else "•"
                    st.write(f"{emoji} **{nivel}** (Valor: {dados['valor']}): {dados['descricao']}")
        
        # Calcular novos valores
        novo_impacto_valor = ESCALAS_IMPACTO[novo_impacto_nivel]['valor']
        nova_probabilidade_valor = ESCALAS_PROBABILIDADE[nova_probabilidade_nivel]['valor']
        novo_risco_inerente = calcular_risco_inerente(novo_impacto_valor, nova_probabilidade_valor)
        nova_classificacao, _ = classificar_risco(novo_risco_inerente)
        
        # Mostrar comparação
        st.divider()
        st.subheader("📊 Comparação: Antes vs Depois")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Impacto", 
                f"{novo_impacto_valor} ({novo_impacto_nivel})",
                delta=f"{novo_impacto_valor - risco_atual['impacto_valor']}"
            )
        with col2:
            st.metric(
                "Probabilidade", 
                f"{nova_probabilidade_valor} ({nova_probabilidade_nivel})",
                delta=f"{nova_probabilidade_valor - risco_atual['probabilidade_valor']}"
            )
        with col3:
            st.metric(
                "Risco Inerente", 
                f"{novo_risco_inerente} ({nova_classificacao})",
                delta=f"{novo_risco_inerente - risco_atual['risco_inerente']}"
            )
        
        # Reavaliação das modalidades
        st.subheader("🔄 Reavaliação das Modalidades")
        st.info("Ajuste os fatores de mitigação considerando as características específicas do seu caso")
        
        novas_modalidades = {}
        cols = st.columns(min(3, len(st.session_state.modalidades)))
        
        for i, modalidade in enumerate(st.session_state.modalidades):
            with cols[i % len(cols)]:
                valor_atual = risco_atual['modalidades'].get(modalidade, 0.5)
                novo_fator = st.slider(
                    f"{modalidade}:",
                    min_value=0.0,
                    max_value=1.0,
                    value=valor_atual,
                    step=0.1,
                    key=f"nova_modalidade_{i}_{indice_risco}"
                )
                novas_modalidades[modalidade] = novo_fator
                
                # Mostrar comparação do risco residual
                risco_residual_antigo = risco_atual['risco_inerente'] * valor_atual
                risco_residual_novo = novo_risco_inerente * novo_fator
                delta_residual = risco_residual_novo - risco_residual_antigo
                
                st.caption(f"Risco Residual: {risco_residual_novo:.1f}")
                if delta_residual != 0:
                    st.caption(f"Δ: {delta_residual:+.1f}")
        
        # Botões de ação
        col1, col2 = st.columns(2)
        with col1:
            salvar = st.form_submit_button("💾 Salvar Alterações", type="primary")
        with col2:
            duplicar = st.form_submit_button("📋 Criar Novo Risco (Duplicar)")
        
        if salvar:
            # Atualizar o risco existente
            st.session_state.riscos[indice_risco].update({
                'descricao': nova_descricao,
                'contexto_especifico': contexto_especifico,
                'impacto_nivel': novo_impacto_nivel,
                'impacto_valor': novo_impacto_valor,
                'probabilidade_nivel': nova_probabilidade_nivel,
                'probabilidade_valor': nova_probabilidade_valor,
                'risco_inerente': novo_risco_inerente,
                'classificacao': nova_classificacao,
                'modalidades': novas_modalidades.copy(),
                'editado': True,
                'editado_por': st.session_state.user,
                'data_edicao': datetime.now().strftime("%d/%m/%Y %H:%M")
            })
            
            # Registrar a ação
            registrar_acao(
                st.session_state.user,
                "Editou risco",
                {"risco": risco_atual['risco_chave'], "alteracoes": {
                    'impacto_anterior': risco_atual['impacto_valor'],
                    'impacto_novo': novo_impacto_valor,
                    'probabilidade_anterior': risco_atual['probabilidade_valor'],
                    'probabilidade_nova': nova_probabilidade_valor,
                    'risco_inerente_anterior': risco_atual['risco_inerente'],
                    'risco_inerente_novo': novo_risco_inerente
                }}
            )
            
            st.success(f"✅ Risco '{risco_atual['risco_chave']}' atualizado com sucesso!")
            st.balloons()
            st.rerun()
        
        if duplicar:
            # Criar um novo risco com os valores editados
            novo_risco = {
                'objetivo_chave': risco_atual['objetivo_chave'],
                'risco_chave': f"{risco_atual['risco_chave']} (Personalizado)",
                'descricao': nova_descricao,
                'contexto_especifico': contexto_especifico,
                'impacto_nivel': novo_impacto_nivel,
                'impacto_valor': novo_impacto_valor,
                'probabilidade_nivel': nova_probabilidade_nivel,
                'probabilidade_valor': nova_probabilidade_valor,
                'risco_inerente': novo_risco_inerente,
                'classificacao': nova_classificacao,
                'modalidades': novas_modalidades.copy(),
                'personalizado': True,
                'criado_por': st.session_state.user,
                'data_criacao': datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            
            st.session_state.riscos.append(novo_risco)
            
            # Registrar a ação
            registrar_acao(
                st.session_state.user,
                "Duplicou risco",
                {"risco_original": risco_atual['risco_chave'], "novo_risco": novo_risco}
            )
            
            st.success(f"✅ Novo risco '{novo_risco['risco_chave']}' criado com base nas suas personalizações!")
            st.rerun()

def analise_riscos():
    st.header("📊 Análise de Riscos")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado. Vá para a aba 'Cadastro de Riscos' para adicionar riscos.")
        return
    
    # Mostrar informações sobre personalização
    riscos_personalizados = sum(1 for r in st.session_state.riscos if r.get('personalizado', False))
    riscos_editados = sum(1 for r in st.session_state.riscos if r.get('editado', False))
    
    if riscos_personalizados > 0 or riscos_editados > 0:
        col1, col2 = st.columns(2)
        with col1:
            if riscos_editados > 0:
                st.info(f"✏️ **{riscos_editados} riscos** foram personalizados para seu caso concreto")
        with col2:
            if riscos_personalizados > 0:
                st.info(f"➕ **{riscos_personalizados} riscos** foram adicionados por você")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_classificacao = st.multiselect(
            "Filtrar por Classificação:",
            ["Baixo", "Médio", "Alto"],
            default=["Baixo", "Médio", "Alto"]
        )
    
    with col2:
        filtro_busca = st.text_input(
            "Buscar risco:",
            placeholder="Digite palavras-chave..."
        )
    
    with col3:
        filtro_tipo = st.selectbox(
            "Filtrar por Tipo:",
            ["Todos", "Originais da planilha", "Personalizados", "Adicionados"]
        )
    
    # Aplicar filtros
    riscos_filtrados = []
    for risco in st.session_state.riscos:
        # Filtro por classificação
        if risco['classificacao'] not in filtro_classificacao:
            continue
        
        # Filtro por busca
        if filtro_busca and filtro_busca.lower() not in risco['risco_chave'].lower():
            continue
        
        # Filtro por tipo
        if filtro_tipo == "Originais da planilha" and (risco.get('personalizado', False) or risco.get('editado', False)):
            continue
        elif filtro_tipo == "Personalizados" and not risco.get('editado', False):
            continue
        elif filtro_tipo == "Adicionados" and not risco.get('personalizado', False):
            continue
        
        riscos_filtrados.append(risco)
    
    if not riscos_filtrados:
        st.warning("Nenhum risco encontrado com os filtros aplicados.")
        return
    
    # Visualizações
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de distribuição por classificação
        classificacoes = [r['classificacao'] for r in riscos_filtrados]
        df_class = pd.DataFrame({'Classificação': classificacoes})
        contagem_class = df_class['Classificação'].value_counts()
        
        fig_pizza = px.pie(
            values=contagem_class.values,
            names=contagem_class.index,
            title="Distribuição de Riscos por Classificação",
            color_discrete_map={"Baixo": "#28a745", "Médio": "#ffc107", "Alto": "#dc3545"}
        )
        st.plotly_chart(fig_pizza, use_container_width=True)
    
    with col2:
        # Gráfico de dispersão Impacto x Probabilidade
        df_scatter = pd.DataFrame(riscos_filtrados)
        
        # Adicionar indicador de personalização
        df_scatter['Tipo'] = df_scatter.apply(
            lambda row: 'Personalizado' if row.get('editado', False)
            else ('Adicionado' if row.get('personalizado', False) else 'Original'), 
            axis=1
        )
        
        fig_scatter = px.scatter(
            df_scatter,
            x='probabilidade_valor',
            y='impacto_valor',
            size='risco_inerente',
            color='Tipo',
            hover_data=['risco_chave', 'classificacao'],
            title="Matriz de Riscos (Impacto x Probabilidade)",
            labels={'probabilidade_valor': 'Probabilidade', 'impacto_valor': 'Impacto'},
            color_discrete_map={
                "Original": "#6c757d", 
                "Personalizado": "#007bff", 
                "Adicionado": "#28a745"
            }
        )
        fig_scatter.update_layout(xaxis_range=[0, 11], yaxis_range=[0, 11])
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Tabela detalhada
    st.subheader("📋 Detalhamento dos Riscos")
    
    # Preparar dados para a tabela
    dados_tabela = []
    for risco in riscos_filtrados:
        # Indicador de tipo
        if risco.get('editado', False):
            tipo_icon = "✏️"
            tipo = "Personalizado"
        elif risco.get('personalizado', False):
            tipo_icon = "➕"
            tipo = "Adicionado"
        else:
            tipo_icon = "📋"
            tipo = "Original"
        
        dados_tabela.append({
            'Tipo': f"{tipo_icon} {tipo}",
            'Risco': risco['risco_chave'],
            'Impacto': risco['impacto_valor'],
            'Probabilidade': risco['probabilidade_valor'],
            'Risco Inerente': risco['risco_inerente'],
            'Classificação': risco['classificacao']
        })
    
    df_display = pd.DataFrame(dados_tabela)
    
    # Exibir tabela
    try:
        st.dataframe(df_display, use_container_width=True)
    except:
        st.dataframe(df_display, use_container_width=True)
    
    # Legenda
    st.caption("**Legenda:** 📋 Original da planilha | ✏️ Personalizado para caso concreto | ➕ Adicionado manualmente")
    
    # Detalhes expandidos para riscos personalizados
    riscos_editados_detalhes = [r for r in riscos_filtrados if r.get('editado', False)]
    if riscos_editados_detalhes:
        with st.expander(f"🔍 Detalhes dos {len(riscos_editados_detalhes)} riscos personalizados"):
            for risco in riscos_editados_detalhes:
                st.write(f"**{risco['risco_chave']}**")
                if 'contexto_especifico' in risco and risco['contexto_especifico']:
                    st.write(f"*Contexto específico:* {risco['contexto_especifico']}")
                if 'data_edicao' in risco:
                    st.write(f"*Última edição:* {risco['data_edicao']}")
                if 'descricao' in risco and risco['descricao']:
                    st.write(f"*Descrição:* {risco['descricao']}")
                st.write("---")
    
    # Nova seção: Visão rápida do risco residual acumulado
    st.subheader("⚡ Visão Rápida - Risco Residual por Modalidade")
    st.caption("Baseado nos riscos filtrados atualmente")
    
    # Calcular risco residual para os riscos filtrados
    if len(riscos_filtrados) > 1:  # Só mostrar se há mais de um risco
        risco_residual_rapido = {}
        
        for modalidade in st.session_state.modalidades:
            risco_total = 0
            count = 0
            
            for risco in riscos_filtrados:
                if modalidade in risco['modalidades']:
                    risco_residual = risco['risco_inerente'] * risco['modalidades'][modalidade]
                    risco_total += risco_residual
                    count += 1
            
            if count > 0:
                risco_residual_rapido[modalidade] = risco_total
        
        if risco_residual_rapido:
            # Mostrar as 3 melhores e 3 piores modalidades
            modalidades_ordenadas = sorted(risco_residual_rapido.items(), key=lambda x: x[1])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.success("**🏆 Melhores Modalidades (Menor Risco Residual):**")
                for i, (modalidade, risco) in enumerate(modalidades_ordenadas[:3], 1):
                    classificacao, _ = classificar_risco(risco)
                    st.write(f"{i}. **{modalidade}**: {risco:.1f} ({classificacao})")
            
            with col2:
                st.error("**⚠️ Modalidades de Maior Risco Residual:**")
                for i, (modalidade, risco) in enumerate(reversed(modalidades_ordenadas[-3:]), 1):
                    classificacao, _ = classificar_risco(risco)
                    st.write(f"{i}. **{modalidade}**: {risco:.1f} ({classificacao})")
            
            st.info(f"💡 **Dica:** Para análise completa do risco acumulado, acesse a aba '🔄 Comparação de Modalidades'")
    else:
        st.info("💡 Selecione múltiplos riscos para ver a análise de risco residual acumulado.")

def comparacao_modalidades():
    st.header("🔄 Comparação de Modalidades")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado para comparação.")
        return
    
    # Selecionar riscos para comparação
    riscos_opcoes = [f"{i+1}. {r['risco_chave']}" for i, r in enumerate(st.session_state.riscos)]
    riscos_selecionados = st.multiselect(
        "Selecione os riscos para comparação:",
        riscos_opcoes,
        default=riscos_opcoes
    )
    
    if not riscos_selecionados:
        st.warning("Selecione pelo menos um risco para comparação.")
        return
    
    # Extrair índices dos riscos selecionados
    indices_selecionados = [int(r.split('.')[0]) - 1 for r in riscos_selecionados]
    riscos_comparacao = [st.session_state.riscos[i] for i in indices_selecionados]
    
    # Calcular risco residual ACUMULADO por modalidade
    st.subheader("📊 Risco Residual Acumulado por Modalidade")
    st.info("💡 **Risco Residual Acumulado** = Soma de todos os riscos residuais para cada modalidade. Representa o risco total ao escolher uma estratégia.")
    
    risco_acumulado_por_modalidade = {}
    risco_inerente_total = sum(risco['risco_inerente'] for risco in riscos_comparacao)
    
    # Calcular dados detalhados e acumulados
    dados_comparacao = []
    
    for modalidade in st.session_state.modalidades:
        risco_residual_total = 0
        riscos_modalidade = []
        
        for risco in riscos_comparacao:
            if modalidade in risco['modalidades']:
                fator_mitigacao = risco['modalidades'][modalidade]
                risco_residual = risco['risco_inerente'] * fator_mitigacao
                risco_residual_total += risco_residual
                classificacao_residual, _ = classificar_risco(risco_residual)
                
                dados_comparacao.append({
                    'Modalidade': modalidade,
                    'Risco': risco['risco_chave'],
                    'Risco_Inerente': risco['risco_inerente'],
                    'Fator_Mitigacao': fator_mitigacao,
                    'Risco_Residual': risco_residual,
                    'Classificacao_Residual': classificacao_residual,
                    'Reducao_Percentual': (1 - fator_mitigacao) * 100
                })
                
                riscos_modalidade.append({
                    'risco': risco['risco_chave'],
                    'inerente': risco['risco_inerente'],
                    'fator': fator_mitigacao,
                    'residual': risco_residual
                })
        
        # Armazenar dados acumulados
        risco_acumulado_por_modalidade[modalidade] = {
            'risco_residual_total': risco_residual_total,
            'risco_inerente_total': sum(r['inerente'] for r in riscos_modalidade),
            'eficacia_percentual': ((sum(r['inerente'] for r in riscos_modalidade) - risco_residual_total) / sum(r['inerente'] for r in riscos_modalidade) * 100) if riscos_modalidade else 0,
            'classificacao_total': classificar_risco(risco_residual_total)[0],
            'detalhes': riscos_modalidade
        }
    
    # Visualização do Risco Acumulado
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de barras: Risco residual ACUMULADO por modalidade
        modalidades_nomes = list(risco_acumulado_por_modalidade.keys())
        riscos_acumulados = [dados['risco_residual_total'] for dados in risco_acumulado_por_modalidade.values()]
        eficacias = [dados['eficacia_percentual'] for dados in risco_acumulado_por_modalidade.values()]
        
        df_acumulado = pd.DataFrame({
            'Modalidade': modalidades_nomes,
            'Risco_Residual_Total': riscos_acumulados,
            'Eficacia_Percentual': eficacias
        })
        
        fig_acumulado = px.bar(
            df_acumulado,
            x='Modalidade',
            y='Risco_Residual_Total',
            color='Eficacia_Percentual',
            title="Risco Residual ACUMULADO por Modalidade",
            labels={'Risco_Residual_Total': 'Risco Residual Total'},
            color_continuous_scale='RdYlGn'
        )
        fig_acumulado.update_xaxes(tickangle=45)
        st.plotly_chart(fig_acumulado, use_container_width=True)
    
    with col2:
        # Gráfico de eficácia comparativa
        fig_eficacia = px.bar(
            df_acumulado.sort_values('Eficacia_Percentual', ascending=True),
            x='Eficacia_Percentual',
            y='Modalidade',
            orientation='h',
            title="Eficácia de Mitigação por Modalidade",
            labels={'Eficacia_Percentual': 'Eficácia (%)'},
            color='Eficacia_Percentual',
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig_eficacia, use_container_width=True)
    
    # Ranking de modalidades baseado no risco acumulado
    st.subheader("🏆 Ranking de Modalidades (Baseado no Risco Acumulado)")
    
    # Preparar dados para ranking
    ranking_data = []
    for modalidade, dados in risco_acumulado_por_modalidade.items():
        ranking_data.append({
            'Modalidade': modalidade,
            'Risco_Residual_Total': dados['risco_residual_total'],
            'Risco_Inerente_Total': dados['risco_inerente_total'],
            'Eficacia_Percentual': dados['eficacia_percentual'],
            'Classificacao_Total': dados['classificacao_total'],
            'Score': dados['eficacia_percentual'] - (dados['risco_residual_total'] / 10)  # Score considerando eficácia e risco residual
        })
    
    df_ranking = pd.DataFrame(ranking_data)
    df_ranking = df_ranking.sort_values('Score', ascending=False)
    df_ranking.index = range(1, len(df_ranking) + 1)
    df_ranking.index.name = 'Posição'
    
    # Colorir o ranking
    def colorir_ranking(row):
        styles = [''] * len(row)
        if 'Classificacao_Total' in row.index:
            pos = row.index.get_loc('Classificacao_Total')
            if row['Classificacao_Total'] == 'Alto':
                styles[pos] = 'background-color: #f8d7da'
            elif row['Classificacao_Total'] == 'Médio':
                styles[pos] = 'background-color: #fff3cd'
            elif row['Classificacao_Total'] == 'Baixo':
                styles[pos] = 'background-color: #d4edda'
        return styles
    
    try:
        st.dataframe(
            df_ranking.style.apply(colorir_ranking, axis=1),
            use_container_width=True
        )
    except:
        st.dataframe(df_ranking, use_container_width=True)
    
    # Insights automáticos
    st.subheader("💡 Insights Automáticos")
    
    if risco_acumulado_por_modalidade:
        melhor_modalidade = min(risco_acumulado_por_modalidade.keys(), 
                               key=lambda x: risco_acumulado_por_modalidade[x]['risco_residual_total'])
        pior_modalidade = max(risco_acumulado_por_modalidade.keys(), 
                             key=lambda x: risco_acumulado_por_modalidade[x]['risco_residual_total'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success(f"""
            **🏆 Melhor Modalidade: {melhor_modalidade}**
            - Risco Residual Total: {risco_acumulado_por_modalidade[melhor_modalidade]['risco_residual_total']:.1f}
            - Eficácia: {risco_acumulado_por_modalidade[melhor_modalidade]['eficacia_percentual']:.1f}%
            - Classificação: {risco_acumulado_por_modalidade[melhor_modalidade]['classificacao_total']}
            """)
        
        with col2:
            st.error(f"""
            **⚠️ Modalidade de Maior Risco: {pior_modalidade}**
            - Risco Residual Total: {risco_acumulado_por_modalidade[pior_modalidade]['risco_residual_total']:.1f}
            - Eficácia: {risco_acumulado_por_modalidade[pior_modalidade]['eficacia_percentual']:.1f}%
            - Classificação: {risco_acumulado_por_modalidade[pior_modalidade]['classificacao_total']}
            """)
        
        # Diferença entre melhor e pior
        diferenca = (risco_acumulado_por_modalidade[pior_modalidade]['risco_residual_total'] - 
                    risco_acumulado_por_modalidade[melhor_modalidade]['risco_residual_total'])
        
        st.info(f"""
        **📊 Análise Comparativa:**
        - Diferença de risco entre melhor e pior modalidade: **{diferenca:.1f} pontos**
        - Escolher a melhor modalidade reduz o risco total em **{diferenca/risco_inerente_total*100:.1f}%**
        - Total de riscos analisados: **{len(riscos_comparacao)}**
        - Risco inerente total (sem mitigação): **{risco_inerente_total:.1f}**
        """)

def dashboard_geral():
    st.header("📈 Dashboard Geral")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado.")
        return
    
    # Métricas gerais
    total_riscos = len(st.session_state.riscos)
    riscos_altos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Alto')
    riscos_medios = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Médio')
    riscos_baixos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Baixo')
    
    risco_medio_inerente = np.mean([r['risco_inerente'] for r in st.session_state.riscos])
    risco_inerente_total = sum(r['risco_inerente'] for r in st.session_state.riscos)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Riscos", total_riscos)
    with col2:
        st.metric("Riscos Altos", riscos_altos, delta=f"{(riscos_altos/total_riscos)*100:.1f}%")
    with col3:
        st.metric("Riscos Médios", riscos_medios, delta=f"{(riscos_medios/total_riscos)*100:.1f}%")
    with col4:
        st.metric("Risco Inerente Total", f"{risco_inerente_total:.1f}")
    
    st.divider()
    
    # Nova seção: Análise de Risco Residual por Modalidade
    st.subheader("🛡️ Análise de Risco Residual Acumulado por Modalidade")
    st.info("💡 **Risco Residual Acumulado** = Soma de todos os riscos residuais para cada modalidade considerando TODOS os riscos.")
    
    # Calcular risco residual acumulado para todas as modalidades
    risco_residual_por_modalidade = {}
    
    for modalidade in st.session_state.modalidades:
        risco_residual_total = 0
        count_riscos = 0
        
        for risco in st.session_state.riscos:
            if modalidade in risco['modalidades']:
                fator_mitigacao = risco['modalidades'][modalidade]
                risco_residual = risco['risco_inerente'] * fator_mitigacao
                risco_residual_total += risco_residual
                count_riscos += 1
        
        if count_riscos > 0:
            eficacia_total = ((sum(r['risco_inerente'] for r in st.session_state.riscos if modalidade in r['modalidades']) - risco_residual_total) / 
                            sum(r['risco_inerente'] for r in st.session_state.riscos if modalidade in r['modalidades']) * 100)
            
            risco_residual_por_modalidade[modalidade] = {
                'risco_residual_total': risco_residual_total,
                'eficacia_percentual': eficacia_total,
                'classificacao': classificar_risco(risco_residual_total)[0],
                'count_riscos': count_riscos
            }
    
    # Visualizar riscos residuais acumulados
    col1, col2 = st.columns(2)
    
    with col1:
        # Métricas de risco residual
        if risco_residual_por_modalidade:
            melhor_modalidade = min(risco_residual_por_modalidade.keys(), 
                                   key=lambda x: risco_residual_por_modalidade[x]['risco_residual_total'])
            pior_modalidade = max(risco_residual_por_modalidade.keys(), 
                                 key=lambda x: risco_residual_por_modalidade[x]['risco_residual_total'])
            
            st.success(f"""
            **🏆 Melhor Modalidade (Menor Risco Residual):**
            **{melhor_modalidade}**
            - Risco Residual Total: {risco_residual_por_modalidade[melhor_modalidade]['risco_residual_total']:.1f}
            - Eficácia: {risco_residual_por_modalidade[melhor_modalidade]['eficacia_percentual']:.1f}%
            """)
            
            st.error(f"""
            **⚠️ Modalidade de Maior Risco Residual:**
            **{pior_modalidade}**
            - Risco Residual Total: {risco_residual_por_modalidade[pior_modalidade]['risco_residual_total']:.1f}
            - Eficácia: {risco_residual_por_modalidade[pior_modalidade]['eficacia_percentual']:.1f}%
            """)
            
            diferenca_risco = (risco_residual_por_modalidade[pior_modalidade]['risco_residual_total'] - 
                              risco_residual_por_modalidade[melhor_modalidade]['risco_residual_total'])
            st.info(f"**Diferença de Risco:** {diferenca_risco:.1f} pontos ({diferenca_risco/risco_inerente_total*100:.1f}% do risco total)")
    
    with col2:
        # Gráfico de barras dos riscos residuais acumulados
        if risco_residual_por_modalidade:
            modalidades_nomes = list(risco_residual_por_modalidade.keys())
            riscos_residuais = [dados['risco_residual_total'] for dados in risco_residual_por_modalidade.values()]
            eficacias = [dados['eficacia_percentual'] for dados in risco_residual_por_modalidade.values()]
            
            df_residual = pd.DataFrame({
                'Modalidade': modalidades_nomes,
                'Risco_Residual_Total': riscos_residuais,
                'Eficacia': eficacias
            })
            
            fig_residual = px.bar(
                df_residual.sort_values('Risco_Residual_Total'),
                x='Risco_Residual_Total',
                y='Modalidade',
                orientation='h',
                title="Risco Residual Total por Modalidade",
                color='Eficacia',
                color_continuous_scale='RdYlGn',
                labels={'Risco_Residual_Total': 'Risco Residual Total'}
            )
            st.plotly_chart(fig_residual, use_container_width=True)
    
    # Tabela resumo de todas as modalidades
    if risco_residual_por_modalidade:
        st.subheader("📊 Resumo Executivo - Todas as Modalidades")
        
        dados_resumo = []
        for modalidade, dados in risco_residual_por_modalidade.items():
            dados_resumo.append({
                'Modalidade': modalidade,
                'Risco_Residual_Total': dados['risco_residual_total'],
                'Eficacia_Percentual': dados['eficacia_percentual'],
                'Classificacao_Total': dados['classificacao'],
                'Riscos_Aplicaveis': dados['count_riscos']
            })
        
        df_resumo = pd.DataFrame(dados_resumo)
        df_resumo = df_resumo.sort_values('Risco_Residual_Total')
        df_resumo.index = range(1, len(df_resumo) + 1)
        df_resumo.index.name = 'Ranking'
        
        # Aplicar cores baseado na classificação
        def colorir_classificacao_resumo(row):
            styles = [''] * len(row)
            if 'Classificacao_Total' in row.index:
                pos = row.index.get_loc('Classificacao_Total')
                if row['Classificacao_Total'] == 'Alto':
                    styles[pos] = 'background-color: #f8d7da'
                elif row['Classificacao_Total'] == 'Médio':
                    styles[pos] = 'background-color: #fff3cd'
                elif row['Classificacao_Total'] == 'Baixo':
                    styles[pos] = 'background-color: #d4edda'
            return styles
        
        try:
            st.dataframe(
                df_resumo.style.apply(colorir_classificacao_resumo, axis=1),
                use_container_width=True
            )
        except:
            st.dataframe(df_resumo, use_container_width=True)

def visualizar_logs():
    st.header("📋 Log de Ações do Sistema")
    
    logs = obter_logs()
    
    if not logs:
        st.info("Nenhuma ação registrada ainda.")
        return
    
    # Criar dataframe para exibição
    df_logs = pd.DataFrame(logs, columns=['Data/Hora', 'Usuário', 'Ação', 'Detalhes'])
    
    # Formatar a coluna de detalhes
    def formatar_detalhes(detalhes):
        if detalhes:
            try:
                detalhes_obj = json.loads(detalhes)
                return str(detalhes_obj)
            except:
                return detalhes
        return "N/A"
    
    df_logs['Detalhes'] = df_logs['Detalhes'].apply(formatar_detalhes)
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        usuarios = df_logs['Usuário'].unique()
        usuario_filtro = st.multiselect(
            "Filtrar por usuário:",
            options=usuarios,
            default=usuarios
        )
    
    with col2:
        acoes = df_logs['Ação'].unique()
        acao_filtro = st.multiselect(
            "Filtrar por ação:",
            options=acoes,
            default=acoes
        )
    
    # Aplicar filtros
    df_filtrado = df_logs[
        (df_logs['Usuário'].isin(usuario_filtro)) & 
        (df_logs['Ação'].isin(acao_filtro))
    ]
    
    # Exibir tabela
    st.dataframe(df_filtrado, use_container_width=True)
    
    # Estatísticas
    st.subheader("📊 Estatísticas de Atividade")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Ações", len(df_filtrado))
    
    with col2:
        acoes_por_usuario = df_filtrado['Usuário'].value_counts()
        st.metric("Ações por Usuário", f"{len(acoes_por_usuario)} usuários")
    
    with col3:
        st.metric("Período Registrado", 
                 f"{df_filtrado['Data/Hora'].min().split()[0]} a {df_filtrado['Data/Hora'].max().split()[0]}")
    
    # Gráfico de atividades por usuário
    fig = px.bar(acoes_por_usuario, 
                 x=acoes_por_usuario.index, 
                 y=acoes_por_usuario.values,
                 title="Ações por Usuário",
                 labels={'x': 'Usuário', 'y': 'Número de Ações'})
    st.plotly_chart(fig, use_container_width=True)

def main():
    # Inicializar banco de dados
    init_db()
    
    # Verificar se o usuário está logado
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    # Se não está logado, mostrar tela de login
    if not st.session_state.user:
        st.title("🔐 Login - Sistema de Gestão de Riscos")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                # MUDANÇA: Usar text_input em vez de selectbox para permitir digitação livre
                username = st.text_input("Usuário", placeholder="Digite seu usuário")
                password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
                
                submitted = st.form_submit_button("Entrar")
                
                if submitted:
                    if verificar_login(username, password):
                        st.session_state.user = username
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos")
        
        st.stop()
    
    # Se está logado, mostrar a aplicação normal
    st.title("🛡️ Dashboard de Avaliação de Riscos")
    st.markdown(f"*Usuário: {st.session_state.user}*")
    st.markdown("*Metodologia baseada no Roteiro de Auditoria de Gestão de Riscos do TCU*")
    
    inicializar_dados()
    
    # Mostrar informações sobre os dados pré-carregados
    if st.session_state.riscos:
        st.success(f"✅ **{len(st.session_state.riscos)} riscos** da planilha foram carregados automaticamente!")
        with st.expander("📋 Visualizar riscos carregados"):
            for i, risco in enumerate(st.session_state.riscos, 1):
                st.write(f"**{i}. {risco['risco_chave']}**")
                st.write(f"   - Risco Inerente: {risco['risco_inerente']} ({risco['classificacao']})")
                st.write(f"   - Impacto: {risco['impacto_valor']} | Probabilidade: {risco['probabilidade_valor']}")
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.info("💡 **Dados Pré-carregados**\n\nOs riscos da sua planilha já estão carregados! Você pode adicionar novos, editar existentes ou modificar modalidades.")
        
        # Mostrar estatísticas dos riscos
        if st.session_state.riscos:
            st.subheader("📊 Estatísticas Atuais")
            total = len(st.session_state.riscos)
            altos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Alto')
            medios = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Médio')
            baixos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Baixo')
            editados = sum(1 for r in st.session_state.riscos if r.get('editado', False))
            adicionados = sum(1 for r in st.session_state.riscos if r.get('personalizado', False))
            
            st.write(f"**Total:** {total} riscos")
            st.write(f"🔴 **Altos:** {altos} ({altos/total*100:.0f}%)")
            st.write(f"🟡 **Médios:** {medios} ({medios/total*100:.0f}%)")
            st.write(f"🟢 **Baixos:** {baixos} ({baixos/total*100:.0f}%)")
            
            if editados > 0:
                st.write(f"✏️ **Personalizados:** {editados}")
            if adicionados > 0:
                st.write(f"➕ **Adicionados:** {adicionados}")
        
        st.divider()
        
        # Gerenciar modalidades
        st.subheader("Modalidades de Mitigação")
        nova_modalidade = st.text_input("Adicionar nova modalidade:")
        if st.button("➕ Adicionar") and nova_modalidade:
            if nova_modalidade not in st.session_state.modalidades:
                st.session_state.modalidades.append(nova_modalidade)
                # Adicionar a nova modalidade a todos os riscos existentes
                for risco in st.session_state.riscos:
                    if 'modalidades' not in risco:
                        risco['modalidades'] = {}
                    risco['modalidades'][nova_modalidade] = 0.5  # Valor padrão
                st.success(f"Modalidade '{nova_modalidade}' adicionada!")
                st.rerun()
            else:
                st.warning("Modalidade já existe!")
        
        # Remover modalidade
        if st.session_state.modalidades:
            modalidade_remover = st.selectbox(
                "Remover modalidade:",
                ["Selecione..."] + st.session_state.modalidades
            )
            if st.button("🗑️ Remover") and modalidade_remover != "Selecione...":
                st.session_state.modalidades.remove(modalidade_remover)
                # Remover a modalidade de todos os riscos
                for risco in st.session_state.riscos:
                    if 'modalidades' in risco and modalidade_remover in risco['modalidades']:
                        del risco['modalidades'][modalidade_remover]
                st.success(f"Modalidade '{modalidade_remover}' removida!")
                st.rerun()
        
        st.divider()
        
        # Exportar/Importar dados
        st.subheader("📄 Gerenciar Dados")
        
        # Botão para gerar relatório Word
        if st.button("📄 Gerar Relatório Word", help="Gera relatório completo em formato .docx"):
            with st.spinner("Gerando relatório..."):
                buffer = gerar_relatorio_word()
                if buffer:
                    st.download_button(
                        label="📥 Baixar Relatório Word",
                        data=buffer,
                        file_name=f"relatorio_riscos_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    st.success("✅ Relatório gerado com sucesso!")
        
        if st.button("💾 Exportar dados (JSON)"):
            import json
            dados_export = {
                'riscos': st.session_state.riscos,
                'modalidades': st.session_state.modalidades
            }
            json_string = json.dumps(dados_export, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Baixar arquivo JSON",
                data=json_string,
                file_name="avaliacao_riscos.json",
                mime="application/json"
            )
        
        # Resetar dados
        if st.button("🔄 Recarregar dados originais"):
            st.session_state.riscos = []
            st.session_state.modalidades = []
            inicializar_dados()
            st.success("Dados originais recarregados!")
            st.rerun()
        
        if st.button("🔥 Limpar todos os dados"):
            if st.checkbox("⚠️ Confirmo que quero limpar todos os dados"):
                st.session_state.riscos = []
                st.session_state.modalidades = MODALIDADES_PADRAO.copy()
                st.success("Dados limpos!")
                st.rerun()
            else:
                st.warning("Marque a confirmação para limpar os dados")
        
        st.divider()
        st.write(f"Usuário: **{st.session_state.user}**")
        if st.button("🚪 Sair"):
            st.session_state.user = None
            st.rerun()
    
    # Abas principais - CORREÇÃO: Adicionada a aba de logs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📝 Cadastro de Riscos", 
        "✏️ Editar Riscos",
        "📊 Análise de Riscos", 
        "🔄 Comparação de Modalidades",
        "📈 Dashboard Geral",
        "📋 Log de Ações"
    ])
    
    with tab1:
        cadastro_riscos()
    
    with tab2:
        editar_riscos()
    
    with tab3:
        analise_riscos()
    
    with tab4:
        comparacao_modalidades()
    
    with tab5:
        dashboard_geral()
    
    # CORREÇÃO: Adicionada a chamada da função visualizar_logs
    with tab6:
        visualizar_logs()

if __name__ == "__main__":
    main()
