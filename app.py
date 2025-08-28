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

# Escalas de avaliação baseadas na metodologia SAROI
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

def calcular_risco_inerente(impacto, probabilidade):
    """Calcula o risco inerente"""
    return impacto * probabilidade

def inicializar_dados():
    """Inicializa os dados padrão se não existirem"""
    if 'riscos' not in st.session_state:
        st.session_state.riscos = [
            {
                'risco_chave': 'Descumprimento do Prazo de entrega',
                'descricao': 'Risco de atraso na entrega da obra, comprometendo o cronograma estabelecido.',
                'impacto_nivel': 'Alto',
                'impacto_valor': 8,
                'probabilidade_nivel': 'Média',
                'probabilidade_valor': 5,
                'risco_inerente': 40,
                'classificacao': 'Alto',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.0,
                    'Permuta por edificação a construir (terreno terceiros)': 0.8,
                    'Permuta por obra (terreno da União)': 0.6,
                    'Build to Suit (terreno da União)': 0.6,
                    'Contratação com dação em pagamento': 0.6,
                    'Obra pública convencional': 0.8
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Imóvel já está pronto, eliminando riscos de construção',
                    'Permuta por edificação a construir (terreno terceiros)': 'Risco alto devido à dependência de terceiros',
                    'Permuta por obra (terreno da União)': 'Controle moderado sobre o cronograma',
                    'Build to Suit (terreno da União)': 'Controle moderado com especificações definidas',
                    'Contratação com dação em pagamento': 'Controle moderado sobre execução',
                    'Obra pública convencional': 'Risco alto devido à complexidade dos processos públicos'
                }
            },
            {
                'risco_chave': 'Indisponibilidade de imóveis públicos p/ implantação ou dação em permuta',
                'descricao': 'Risco de não haver imóveis públicos adequados disponíveis para a operação.',
                'impacto_nivel': 'Muito alto',
                'impacto_valor': 10,
                'probabilidade_nivel': 'Baixa',
                'probabilidade_valor': 2,
                'risco_inerente': 20,
                'classificacao': 'Médio',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.8,
                    'Permuta por edificação a construir (terreno terceiros)': 0.0,
                    'Permuta por obra (terreno da União)': 0.6,
                    'Build to Suit (terreno da União)': 0.6,
                    'Contratação com dação em pagamento': 0.8,
                    'Obra pública convencional': 0.0
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Depende da disponibilidade de imóveis adequados',
                    'Permuta por edificação a construir (terreno terceiros)': 'Não depende de imóveis públicos',
                    'Permuta por obra (terreno da União)': 'Requer terreno da União disponível',
                    'Build to Suit (terreno da União)': 'Requer terreno da União disponível',
                    'Contratação com dação em pagamento': 'Depende da disponibilidade de imóveis para dação',
                    'Obra pública convencional': 'Não depende de permuta de imóveis'
                }
            },
            {
                'risco_chave': 'Condições de mercado desfavoráveis',
                'descricao': 'Risco de condições econômicas adversas que impactem a viabilidade da operação.',
                'impacto_nivel': 'Alto',
                'impacto_valor': 8,
                'probabilidade_nivel': 'Média',
                'probabilidade_valor': 5,
                'risco_inerente': 40,
                'classificacao': 'Alto',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.4,
                    'Permuta por edificação a construir (terreno terceiros)': 0.8,
                    'Permuta por obra (terreno da União)': 0.6,
                    'Build to Suit (terreno da União)': 0.6,
                    'Contratação com dação em pagamento': 0.4,
                    'Obra pública convencional': 0.2
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Menor exposição a variações de mercado',
                    'Permuta por edificação a construir (terreno terceiros)': 'Alta exposição a condições de mercado',
                    'Permuta por obra (terreno da União)': 'Exposição moderada a variações',
                    'Build to Suit (terreno da União)': 'Exposição moderada com contratos específicos',
                    'Contratação com dação em pagamento': 'Menor dependência de condições de mercado',
                    'Obra pública convencional': 'Menor exposição devido ao financiamento público'
                }
            },
            {
                'risco_chave': 'Abandono da obra pela empresa',
                'descricao': 'Risco de a empresa contratada abandonar a obra antes da conclusão.',
                'impacto_nivel': 'Muito alto',
                'impacto_valor': 10,
                'probabilidade_nivel': 'Baixa',
                'probabilidade_valor': 2,
                'risco_inerente': 20,
                'classificacao': 'Médio',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.0,
                    'Permuta por edificação a construir (terreno terceiros)': 0.6,
                    'Permuta por obra (terreno da União)': 0.4,
                    'Build to Suit (terreno da União)': 0.4,
                    'Contratação com dação em pagamento': 0.4,
                    'Obra pública convencional': 0.2
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Obra já concluída, risco inexistente',
                    'Permuta por edificação a construir (terreno terceiros)': 'Risco moderado com garantias contratuais',
                    'Permuta por obra (terreno da União)': 'Controle maior sobre a execução',
                    'Build to Suit (terreno da União)': 'Contratos específicos reduzem o risco',
                    'Contratação com dação em pagamento': 'Garantias contratuais adequadas',
                    'Obra pública convencional': 'Rigorosos processos de qualificação e garantias'
                }
            },
            {
                'risco_chave': 'Baixa rentabilização do estoque de imóveis',
                'descricao': 'Risco de os imóveis utilizados na operação não gerarem o retorno esperado.',
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
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Risco total de baixa rentabilização',
                    'Permuta por edificação a construir (terreno terceiros)': 'Risco total de baixa rentabilização',
                    'Permuta por obra (terreno da União)': 'Otimização significativa do patrimônio',
                    'Build to Suit (terreno da União)': 'Otimização moderada do patrimônio',
                    'Contratação com dação em pagamento': 'Boa otimização do patrimônio público',
                    'Obra pública convencional': 'Rentabilização limitada dos imóveis'
                }
            },
            {
                'risco_chave': 'Dotação orçamentária insuficiente',
                'descricao': 'Risco de não haver recursos orçamentários suficientes para a operação.',
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
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Não requer recursos orçamentários',
                    'Permuta por edificação a construir (terreno terceiros)': 'Recursos mínimos necessários',
                    'Permuta por obra (terreno da União)': 'Recursos mínimos necessários',
                    'Build to Suit (terreno da União)': 'Requer recursos moderados',
                    'Contratação com dação em pagamento': 'Requer recursos moderados',
                    'Obra pública convencional': 'Totalmente dependente de recursos orçamentários'
                }
            },
            {
                'risco_chave': 'Questionamento jurídico',
                'descricao': 'Risco de questionamentos jurídicos quanto à legalidade da modalidade escolhida.',
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
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Modalidade bem estabelecida juridicamente',
                    'Permuta por edificação a construir (terreno terceiros)': 'Modalidade com precedentes, mas complexa',
                    'Permuta por obra (terreno da União)': 'Modalidade com precedentes, mas complexa',
                    'Build to Suit (terreno da União)': 'Modalidade inovadora com riscos jurídicos',
                    'Contratação com dação em pagamento': 'Modalidade complexa com riscos jurídicos',
                    'Obra pública convencional': 'Modalidade tradicional e bem estabelecida'
                }
            },
            {
                'risco_chave': 'Baixa qualidade dos serviços entregues',
                'descricao': 'Risco de os serviços não atenderem aos padrões de qualidade exigidos.',
                'impacto_nivel': 'Médio',
                'impacto_valor': 5,
                'probabilidade_nivel': 'Baixa',
                'probabilidade_valor': 2,
                'risco_inerente': 10,
                'classificacao': 'Baixo',
                'modalidades': {
                    'Permuta por imóvel já construído': 0.8,
                    'Permuta por edificação a construir (terreno terceiros)': 0.8,
                    'Permuta por obra (terreno da União)': 0.4,
                    'Build to Suit (terreno da União)': 0.4,
                    'Contratação com dação em pagamento': 0.2,
                    'Obra pública convencional': 0.2
                },
                'justificativas_mitigacao': {
                    'Permuta por imóvel já construído': 'Qualidade já estabelecida, mas sem controle',
                    'Permuta por edificação a construir (terreno terceiros)': 'Controle limitado sobre a qualidade',
                    'Permuta por obra (terreno da União)': 'Controle moderado sobre especificações',
                    'Build to Suit (terreno da União)': 'Especificações detalhadas reduzem o risco',
                    'Contratação com dação em pagamento': 'Controle rigoroso sobre qualidade',
                    'Obra pública convencional': 'Fiscalização rigorosa e padrões estabelecidos'
                }
            }
        ]
    if 'modalidades' not in st.session_state:
        st.session_state.modalidades = MODALIDADES_PADRAO.copy()

def gerar_relatorio_word():
    """Gera relatório completo e amplo em formato Word"""
    try:
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_ALIGN_VERTICAL
        from docx.oxml.shared import OxmlElement, qn
        from io import BytesIO
        
        # Obter nome do projeto da session_state
        nome_projeto = st.session_state.get('nome_projeto', 'Projeto')
        
        # Criar documento
        doc = Document()
        
        # Título principal com nome do projeto
        title = doc.add_heading(f'RELATÓRIO EXECUTIVO DE AVALIAÇÃO DE RISCOS - {nome_projeto}', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtítulo
        subtitle = doc.add_heading("Metodologia - Análise Comparativa de Modalidades de Contratação", level=1)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # NOVO: Nome do Projeto como título dentro do documento
        doc.add_heading(f"Projeto: {nome_projeto}", level=2)
        doc.add_paragraph()
        
        # NOVA SEÇÃO: Informações do responsável pelo relatório
        # Solicitar identificação do usuário se não estiver definida
        if 'identificacao_relatorio' not in st.session_state or st.session_state.identificacao_relatorio is None:
            st.session_state.identificacao_relatorio = {
                'nome': st.session_state.user,
                'divisao': 'Divisão Padrão',
                'orgao': 'SPU',
                'email': 'usuario@spu.gov.br'
            }
        

        # Informações do relatório com identificação
        info_para = doc.add_paragraph()
        info_para.add_run("Data da Análise: ").bold = True
        info_para.add_run(f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        info_para.add_run("\nMetodologia: ").bold = True
        info_para.add_run("Roteiro de Auditoria de Gestão de Riscos - SAROI")
        info_para.add_run("\nVersão do Sistema: ").bold = True
        info_para.add_run("2.0 - Análise Ampliada")
        
        # Adicionar informações do responsável
        info_para.add_run("\n\nRESPONSÁVEL PELA ANÁLISE:").bold = True
        info_para.add_run(f"\nNome: {st.session_state.identificacao_relatorio['nome']}")
        info_para.add_run(f"\nDivisão: {st.session_state.identificacao_relatorio['divisao']}")
        if st.session_state.identificacao_relatorio['orgao']:
            info_para.add_run(f"\nÓrgão: {st.session_state.identificacao_relatorio['orgao']}")
        if st.session_state.identificacao_relatorio['email']:
            info_para.add_run(f"\nE-mail: {st.session_state.identificacao_relatorio['email']}")
        
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
        utilizando a metodologia do Tribunal de Contas da União (TCU). A análise inclui avaliação detalhada 
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
        return buffer.getvalue()
        
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")
        return None

def cadastro_riscos():
    st.header("📝 Cadastro de Riscos")
    
    if st.session_state.riscos:
        st.info(f"💡 **{len(st.session_state.riscos)} riscos** da planilha já estão carregados. Use o formulário abaixo para adicionar novos riscos.")
        st.info("💡 **Dica:** Para personalizar riscos existentes conforme seu caso concreto, use a aba '✏️ Editar Riscos'")
    
    with st.form("cadastro_risco"):
        col1, col2 = st.columns(2)
        
        with col1:
            risco_chave = st.text_input(
                "Risco-Chave:",
                placeholder="Ex: Descumprimento do Prazo de entrega"
            )
            
            descricao_risco = st.text_area(
                "Descrição/Justificativa do Risco:",
                placeholder="Descreva os aspectos que levam a este risco..."
            )
            
            contexto_especifico = st.text_area(
                "Justificativa de mudança de Probabilidade:",
                placeholder="Ex: Localização, tipo de obra, prazo, complexidade...",
                help="Aspectos específicos do seu projeto que influenciam este risco"
            )
        
        with col2:
            # Avaliação de Impacto
            st.subheader("🎯 Avaliação de Impacto")
            impacto_nivel = st.selectbox(
                "Nível de Impacto:",
                list(ESCALAS_IMPACTO.keys()),
                help="Selecione o nível de impacto baseado na escala SAROI"
            )
            st.info(f"**{impacto_nivel}** (Valor: {ESCALAS_IMPACTO[impacto_nivel]['valor']})")
            st.caption(ESCALAS_IMPACTO[impacto_nivel]['descricao'])
            
            # Avaliação de Probabilidade
            st.subheader("📊 Avaliação de Probabilidade")
            probabilidade_nivel = st.selectbox(
                "Nível de Probabilidade:",
                list(ESCALAS_PROBABILIDADE.keys()),
                help="Selecione o nível de probabilidade baseado na escala SAROI"
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
        justificativas_mitigacao = {}
        
        for i, modalidade in enumerate(st.session_state.modalidades):
            st.write(f"**{modalidade}:**")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                fator = st.slider(
                    f"Fator de mitigação:",
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
            
            with col2:
                justificativa = st.text_area(
                    f"Justificativa para {modalidade}:",
                    placeholder="Explique por que este fator de mitigação foi escolhido...",
                    key=f"justificativa_{i}",
                    height=100
                )
                justificativas_mitigacao[modalidade] = justificativa
        
        submitted = st.form_submit_button("💾 Salvar Risco", type="primary")
        
        if submitted and risco_chave:
            # Verificar se todas as justificativas foram preenchidas
            justificativas_vazias = [modalidade for modalidade, justificativa in justificativas_mitigacao.items() if not justificativa.strip()]
            
            if justificativas_vazias:
                st.error(f"Por favor, preencha as justificativas para as seguintes modalidades: {', '.join(justificativas_vazias)}")
            else:
                novo_risco = {
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
                    'justificativas_mitigacao': justificativas_mitigacao.copy(),
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
            st.subheader("🗗️ Justificativa de mudança de Probabilidade")
            contexto_especifico = st.text_area(
                "Fatores específicos que influenciam a probabilidade deste risco:",
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
                delta=f"{novo_impacto_valor - risco_atual['impacto_valor']:+d}"
            )
        
        with col2:
            st.metric(
                "Probabilidade", 
                f"{nova_probabilidade_valor} ({nova_probabilidade_nivel})",
                delta=f"{nova_probabilidade_valor - risco_atual['probabilidade_valor']:+d}"
            )
        
        with col3:
            st.metric(
                "Risco Inerente", 
                f"{novo_risco_inerente} ({nova_classificacao})",
                delta=f"{novo_risco_inerente - risco_atual['risco_inerente']:+d}"
            )
        
        # Reavaliação das modalidades
        st.subheader("🔄 Reavaliação das Modalidades")
        st.info("Ajuste os fatores de mitigação conforme seu caso específico:")
        
        novas_modalidades = {}
        novas_justificativas = {}
        
        for modalidade in st.session_state.modalidades:
            if modalidade in risco_atual['modalidades']:
                st.write(f"**{modalidade}:**")
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    valor_atual = risco_atual['modalidades'][modalidade]
                    novo_fator = st.slider(
                        f"Fator de mitigação:",
                        min_value=0.0,
                        max_value=1.0,
                        value=valor_atual,
                        step=0.1,
                        key=f"edit_modalidade_{modalidade}_{indice_risco}"
                    )
                    novas_modalidades[modalidade] = novo_fator
                    
                    # Calcular risco residual
                    risco_residual = novo_risco_inerente * novo_fator
                    class_residual, _ = classificar_risco(risco_residual)
                    st.caption(f"Risco Residual: {risco_residual:.1f} ({class_residual})")
                
                with col2:
                    justificativa_atual = risco_atual.get('justificativas_mitigacao', {}).get(modalidade, '')
                    nova_justificativa = st.text_area(
                        f"Justificativa para {modalidade}:",
                        value=justificativa_atual,
                        placeholder="Explique por que este fator de mitigação foi escolhido...",
                        key=f"edit_justificativa_{modalidade}_{indice_risco}",
                        height=100
                    )
                    novas_justificativas[modalidade] = nova_justificativa
        
        # Botão de salvar
        submitted = st.form_submit_button("💾 Salvar Alterações", type="primary")
        
        if submitted:
            # Verificar se todas as justificativas foram preenchidas
            justificativas_vazias = [modalidade for modalidade, justificativa in novas_justificativas.items() if not justificativa.strip()]
            
            if justificativas_vazias:
                st.error(f"Por favor, preencha as justificativas para as seguintes modalidades: {', '.join(justificativas_vazias)}")
            else:
                # Atualizar o risco
                st.session_state.riscos[indice_risco].update({
                    'descricao': nova_descricao,
                    'contexto_especifico': contexto_especifico,
                    'impacto_nivel': novo_impacto_nivel,
                    'impacto_valor': novo_impacto_valor,
                    'probabilidade_nivel': nova_probabilidade_nivel,
                    'probabilidade_valor': nova_probabilidade_valor,
                    'risco_inerente': novo_risco_inerente,
                    'classificacao': nova_classificacao,
                    'modalidades': novas_modalidades,
                    'justificativas_mitigacao': novas_justificativas,
                    'editado': True,
                    'editado_por': st.session_state.user,
                    'data_edicao': datetime.now().strftime("%d/%m/%Y %H:%M")
                })
                
                # Registrar a ação no log
                registrar_acao(
                    st.session_state.user, 
                    "Editou risco", 
                    {"risco": risco_atual['risco_chave'], "alteracoes": "Personalização conforme caso concreto"}
                )
                
                st.success(f"✅ Risco '{risco_atual['risco_chave']}' atualizado com sucesso!")
                st.rerun()

def analise_riscos():
    st.header("📊 Análise Detalhada de Riscos")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado para análise.")
        return
    
    # Métricas gerais
    col1, col2, col3, col4 = st.columns(4)
    
    total_riscos = len(st.session_state.riscos)
    riscos_altos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Alto')
    riscos_medios = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Médio')
    riscos_baixos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Baixo')
    
    with col1:
        st.metric("Total de Riscos", total_riscos)
    with col2:
        st.metric("Riscos Altos", riscos_altos, delta=f"{riscos_altos/total_riscos*100:.1f}%")
    with col3:
        st.metric("Riscos Médios", riscos_medios, delta=f"{riscos_medios/total_riscos*100:.1f}%")
    with col4:
        st.metric("Riscos Baixos", riscos_baixos, delta=f"{riscos_baixos/total_riscos*100:.1f}%")
    
    # Gráficos de análise
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribuição por classificação
        classificacoes = [r['classificacao'] for r in st.session_state.riscos]
        df_class = pd.DataFrame({'Classificação': classificacoes})
        fig_class = px.pie(df_class, names='Classificação', 
                          title="Distribuição dos Riscos por Classificação",
                          color_discrete_map={'Alto': '#dc3545', 'Médio': '#ffc107', 'Baixo': '#28a745'})
        st.plotly_chart(fig_class, use_container_width=True)
    
    with col2:
        # Riscos por valor inerente
        df_riscos = pd.DataFrame(st.session_state.riscos)
        fig_bar = px.bar(df_riscos, x='risco_chave', y='risco_inerente',
                        title="Valor do Risco Inerente por Tipo",
                        color='classificacao',
                        color_discrete_map={'Alto': '#dc3545', 'Médio': '#ffc107', 'Baixo': '#28a745'})
        fig_bar.update_xaxis(tickangle=45)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Tabela detalhada
    st.subheader("📋 Detalhamento dos Riscos")
    
    # Preparar dados para a tabela
    dados_tabela = []
    for risco in st.session_state.riscos:
        dados_tabela.append({
            'Risco': risco['risco_chave'],
            'Impacto': f"{risco['impacto_valor']} ({risco['impacto_nivel']})",
            'Probabilidade': f"{risco['probabilidade_valor']} ({risco['probabilidade_nivel']})",
            'Risco Inerente': risco['risco_inerente'],
            'Classificação': risco['classificacao'],
            'Personalizado': '✅' if risco.get('editado', False) or risco.get('personalizado', False) else '❌'
        })
    
    df_tabela = pd.DataFrame(dados_tabela)
    st.dataframe(df_tabela, use_container_width=True)

def comparacao_modalidades():
    st.header("🔄 Comparação de Modalidades de Contratação")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado para comparação.")
        return
    
    # Calcular risco residual por modalidade
    risco_residual_por_modalidade = {}
    
    for modalidade in st.session_state.modalidades:
        risco_residual_total = 0
        risco_inerente_aplicavel = 0
        
        for risco in st.session_state.riscos:
            if modalidade in risco['modalidades']:
                fator_mitigacao = risco['modalidades'][modalidade]
                risco_residual = risco['risco_inerente'] * fator_mitigacao
                risco_residual_total += risco_residual
                risco_inerente_aplicavel += risco['risco_inerente']
        
        eficacia = ((risco_inerente_aplicavel - risco_residual_total) / risco_inerente_aplicavel * 100) if risco_inerente_aplicavel > 0 else 0
        
        risco_residual_por_modalidade[modalidade] = {
            'risco_residual_total': risco_residual_total,
            'risco_inerente_aplicavel': risco_inerente_aplicavel,
            'eficacia_percentual': eficacia
        }
    
    # Ordenar modalidades por risco residual (menor = melhor)
    modalidades_ordenadas = sorted(risco_residual_por_modalidade.items(), 
                                 key=lambda x: x[1]['risco_residual_total'])
    
    # Métricas principais
    st.subheader("🏆 Ranking das Modalidades")
    
    for i, (modalidade, dados) in enumerate(modalidades_ordenadas, 1):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(f"{i}º Lugar", modalidade)
        with col2:
            st.metric("Risco Residual", f"{dados['risco_residual_total']:.1f}")
        with col3:
            st.metric("Eficácia", f"{dados['eficacia_percentual']:.1f}%")
        with col4:
            if i == 1:
                st.success("🥇 RECOMENDADA")
            elif i == len(modalidades_ordenadas):
                st.error("🚫 NÃO RECOMENDADA")
            else:
                st.info(f"#{i}")
    
    # Gráfico comparativo
    st.subheader("📊 Comparação Visual")
    
    df_comp = pd.DataFrame([
        {
            'Modalidade': modalidade,
            'Risco Residual': dados['risco_residual_total'],
            'Eficácia (%)': dados['eficacia_percentual']
        }
        for modalidade, dados in modalidades_ordenadas
    ])
    
    fig = px.bar(df_comp, x='Modalidade', y='Risco Residual',
                title="Risco Residual por Modalidade (Menor = Melhor)",
                color='Eficácia (%)',
                color_continuous_scale='RdYlGn')
    fig.update_xaxis(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

def dashboard_geral():
    st.header("📈 Dashboard Geral")
    
    if not st.session_state.riscos:
        st.warning("⚠️ Nenhum risco cadastrado para exibir no dashboard.")
        return
    
    # Métricas principais
    total_riscos = len(st.session_state.riscos)
    risco_inerente_total = sum(r['risco_inerente'] for r in st.session_state.riscos)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Riscos", total_riscos)
    with col2:
        st.metric("Risco Inerente Total", f"{risco_inerente_total:.1f}")
    with col3:
        risco_medio = risco_inerente_total / total_riscos if total_riscos > 0 else 0
        st.metric("Risco Médio", f"{risco_medio:.1f}")
    
    # Top 5 riscos mais críticos
    st.subheader("🔥 Top 5 Riscos Mais Críticos")
    riscos_ordenados = sorted(st.session_state.riscos, key=lambda x: x['risco_inerente'], reverse=True)[:5]
    
    for i, risco in enumerate(riscos_ordenados, 1):
        classificacao, cor = classificar_risco(risco['risco_inerente'])
        st.write(f"{i}. **{risco['risco_chave']}**")
        st.progress(min(risco['risco_inerente']/100, 1.0))
        st.caption(f"Risco Inerente: {risco['risco_inerente']} ({classificacao})")
        st.write("")

def visualizar_logs():
    st.header("📋 Log de Ações do Sistema")
    
    # Obter logs do banco de dados
    logs = obter_logs()
    
    if not logs:
        st.info("📝 Nenhuma ação registrada ainda.")
        return
    
    # Converter para DataFrame
    df_logs = pd.DataFrame(logs, columns=['Data/Hora', 'Usuário', 'Ação', 'Detalhes'])
    
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
                
                # NOVO: Campo para nome do projeto
                nome_projeto = st.text_input("Nome do Projeto", placeholder="Digite o nome do projeto trabalhado")
                
                submitted = st.form_submit_button("Entrar")
                
                if submitted:
                    if not nome_projeto.strip():
                        st.error("Por favor, digite o nome do projeto")
                    elif verificar_login(username, password):
                        st.session_state.user = username
                        st.session_state.nome_projeto = nome_projeto.strip()
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos")
        
        st.stop()
    
    # Se está logado, mostrar a aplicação normal
    nome_projeto_titulo = st.session_state.get('nome_projeto', 'Projeto')
    st.title(f"🛡️ Dashboard de Avaliação de Riscos - {nome_projeto_titulo}")
    st.markdown(f"*Usuário: {st.session_state.user}*")
    st.markdown("*Metodologia baseada no Roteiro de Auditoria de Gestão de Riscos *")
    
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
                    if 'justificativas_mitigacao' not in risco:
                        risco['justificativas_mitigacao'] = {}
                    risco['justificativas_mitigacao'][nova_modalidade] = "Justificativa padrão - necessário personalizar"
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
                    if 'justificativas_mitigacao' in risco and modalidade_remover in risco['justificativas_mitigacao']:
                        del risco['justificativas_mitigacao'][modalidade_remover]
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
                    nome_projeto_arquivo = st.session_state.get('nome_projeto', 'Projeto').replace(' ', '_')
                    st.download_button(
                        label="📥 Baixar Relatório Word",
                        data=buffer,
                        file_name=f"relatorio_riscos_{nome_projeto_arquivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_report_sidebar"
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
    
    # MUDANÇA: Abas principais com 'Editar Riscos' como primeira aba
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "✏️ Editar Riscos",
        "📝 Cadastro de Riscos", 
        "📊 Análise de Riscos", 
        "🔄 Comparação de Modalidades",
        "📈 Dashboard Geral",
        "📋 Log de Ações"
    ])
    
    with tab1:
        editar_riscos()
    
    with tab2:
        cadastro_riscos()
    
    with tab3:
        analise_riscos()
    
    with tab4:
        comparacao_modalidades()
    
    with tab5:
        dashboard_geral()
    
    with tab6:
        visualizar_logs()

if __name__ == "__main__":
    main()

