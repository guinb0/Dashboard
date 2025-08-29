
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
        "descricao": "Evento provável de ocorrer. Elementos indicam consistentemente essa possibilidade"
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
                  password_hash TEXT NOT NULL)
              ''')
    
    # Tabela de logs de ações
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  username TEXT NOT NULL,
                  acao TEXT NOT NULL,
                  detalhes TEXT)
              ''')
    
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
                'unidade': 'Unidade Padrão',
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
        info_para.add_run(f"\nDivisão: {st.session_state.identificacao_relatorio['unidade']}")
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
        
        doc.add_paragraph(f"O sistema identificou um total de {total_riscos} riscos para o projeto '{nome_projeto}'.")
        doc.add_paragraph(f"Dentre estes, {riscos_altos} foram classificados como de risco ALTO, {riscos_medios} como MÉDIO e {riscos_baixos} como BAIXO.")
        doc.add_paragraph(f"O risco inerente total acumulado para o projeto é de {risco_inerente_total:.2f}.")
        doc.add_paragraph(f"A análise das modalidades de contratação revelou que a modalidade '{melhor_modalidade}' apresenta o menor risco residual acumulado, enquanto a modalidade '{pior_modalidade}' apresenta o maior risco residual acumulado.")
        
        doc.add_page_break()
        
        # 2. INTRODUÇÃO
        doc.add_heading('2. INTRODUÇÃO', level=1)
        doc.add_paragraph("Este relatório apresenta os resultados da avaliação de riscos aplicada às diferentes modalidades de contratação para o projeto em questão. O objetivo é fornecer uma visão clara dos riscos inerentes e residuais associados a cada modalidade, subsidiando a tomada de decisão e o planejamento de estratégias de mitigação.")
        doc.add_paragraph("A metodologia utilizada baseia-se no Roteiro de Auditoria de Gestão de Riscos - SAROI, adaptada para a análise comparativa de modalidades de contratação. Foram considerados aspectos de impacto e probabilidade para cada risco identificado, bem como fatores de mitigação específicos para cada modalidade.")
        
        doc.add_page_break()

        # 3. METODOLOGIA
        doc.add_heading('3. METODOLOGIA', level=1)
        doc.add_paragraph("A avaliação de riscos foi realizada em duas etapas principais: identificação e análise. Na etapa de identificação, foram levantados os principais riscos associados a projetos de contratação, com base em experiências anteriores e diretrizes da SPU. Na etapa de análise, cada risco foi avaliado quanto ao seu impacto e probabilidade, utilizando as escalas de avaliação SAROI.")
        doc.add_paragraph("Para cada risco, foram definidos aspectos específicos de impacto e probabilidade, conforme detalhado na seção de Análise de Riscos. A classificação do risco inerente (Impacto x Probabilidade) foi realizada de acordo com a matriz de risco, resultando em classificações de Baixo, Médio e Alto.")
        doc.add_paragraph("Adicionalmente, foi introduzido o conceito de fator de mitigação para cada modalidade de contratação. Este fator representa a capacidade da modalidade em reduzir o risco inerente, resultando no cálculo do risco residual (Risco Inerente x Fator de Mitigação).")
        
        doc.add_page_break()

        # 4. ANÁLISE DE RISCOS
        doc.add_heading('4. ANÁLISE DE RISCOS', level=1)
        doc.add_paragraph("Nesta seção, são detalhados os riscos identificados e suas respectivas avaliações de impacto e probabilidade. Para cada risco, são apresentados os aspectos considerados na avaliação, a nota atribuída e a justificativa para essa nota.")
        
        for i, risco in enumerate(st.session_state.riscos):
            doc.add_heading(f"4.{i+1}. Risco: {risco['nome']}", level=2)
            doc.add_paragraph(f"Descrição: {risco['descricao']}")
            
            # Tabela de Impacto
            doc.add_heading('Impacto', level=3)
            table_impacto = doc.add_table(rows=1, cols=2)
            table_impacto.style = 'Table Grid'
            hdr_cells_impacto = table_impacto.rows[0].cells
            hdr_cells_impacto[0].text = 'Aspecto'
            hdr_cells_impacto[1].text = 'Consideração'
            
            for aspecto in ASPECTOS_RISCOS[risco['nome']]['impacto']:
                row_cells = table_impacto.add_row().cells
                row_cells[0].text = aspecto
                row_cells[1].text = 'Sim' # Placeholder, pois não há dados de consideração no app
            
            doc.add_paragraph(f"Nota de Impacto: {risco['impacto']} ({[k for k, v in ESCALAS_IMPACTO.items() if v['valor'] == risco['impacto']][0]})")
            doc.add_paragraph(f"Justificativa Impacto: {risco.get('justificativa_impacto', 'Não informada')}")

            # Tabela de Probabilidade
            doc.add_heading('Probabilidade', level=3)
            table_probabilidade = doc.add_table(rows=1, cols=2)
            table_probabilidade.style = 'Table Grid'
            hdr_cells_probabilidade = table_probabilidade.rows[0].cells
            hdr_cells_probabilidade[0].text = 'Aspecto'
            hdr_cells_probabilidade[1].text = 'Consideração'
            
            for aspecto in ASPECTOS_RISCOS[risco['nome']]['probabilidade']:
                row_cells = table_probabilidade.add_row().cells
                row_cells[0].text = aspecto
                row_cells[1].text = 'Sim' # Placeholder
            
            doc.add_paragraph(f"Nota de Probabilidade: {risco['probabilidade']} ({[k for k, v in ESCALAS_PROBABILIDADE.items() if v['valor'] == risco['probabilidade']][0]})")
            doc.add_paragraph(f"Justificativa Probabilidade: {risco.get('justificativa_probabilidade', 'Não informada')}")

            doc.add_paragraph(f"Risco Inerente Calculado: {risco['risco_inerente']:.2f} ({risco['classificacao']})")
            doc.add_paragraph()
            
            # Tabela de Fatores de Mitigação por Modalidade
            doc.add_heading('Fatores de Mitigação por Modalidade', level=3)
            table_mitigacao = doc.add_table(rows=1, cols=2)
            table_mitigacao.style = 'Table Grid'
            hdr_cells_mitigacao = table_mitigacao.rows[0].cells
            hdr_cells_mitigacao[0].text = 'Modalidade'
            hdr_cells_mitigacao[1].text = 'Fator de Mitigação'
            
            for modalidade, fator in risco['modalidades'].items():
                row_cells = table_mitigacao.add_row().cells
                row_cells[0].text = modalidade
                row_cells[1].text = f"{fator:.2f}"
            doc.add_paragraph()
            
            doc.add_page_break()

        # 5. AVALIAÇÃO COMPARATIVA DAS MODALIDADES
        doc.add_heading('5. AVALIAÇÃO COMPARATIVA DAS MODALIDADES', level=1)
        doc.add_paragraph("Esta seção apresenta a avaliação comparativa do risco residual para cada modalidade de contratação, considerando os fatores de mitigação aplicados aos riscos inerentes.")
        
        # Tabela de Risco Residual por Modalidade
        doc.add_heading('Risco Residual por Modalidade', level=2)
        table_risco_residual = doc.add_table(rows=1, cols=2)
        table_risco_residual.style = 'Table Grid'
        hdr_cells_residual = table_risco_residual.rows[0].cells
        hdr_cells_residual[0].text = 'Modalidade'
        hdr_cells_residual[1].text = 'Risco Residual Acumulado'
        
        for modalidade, risco_acumulado in risco_acumulado_por_modalidade.items():
            row_cells = table_risco_residual.add_row().cells
            row_cells[0].text = modalidade
            row_cells[1].text = f"{risco_acumulado:.2f}"
        doc.add_paragraph()

        doc.add_paragraph(f"Conforme a análise, a modalidade '{melhor_modalidade}' demonstrou ser a mais vantajosa em termos de risco residual, enquanto '{pior_modalidade}' apresentou o maior risco.")
        doc.add_paragraph("Recomenda-se que a escolha da modalidade leve em consideração não apenas o risco residual, mas também outros fatores estratégicos e operacionais do projeto.")

        doc.add_page_break()

        # 6. RECOMENDAÇÕES
        doc.add_heading('6. RECOMENDAÇÕES', level=1)
        doc.add_paragraph("Com base na análise de riscos, as seguintes recomendações são propostas para otimizar a gestão de riscos no projeto:")
        doc.add_paragraph("\u2022 Priorizar modalidades com menor risco residual, sempre que alinhado aos objetivos do projeto.")
        doc.add_paragraph("\u2022 Desenvolver planos de contingência específicos para os riscos classificados como 'Alto'.")
        doc.add_paragraph("\u2022 Monitorar continuamente os riscos identificados, revisando suas avaliações periodicamente.")
        doc.add_paragraph("\u2022 Implementar as estratégias de mitigação propostas para cada risco e modalidade.")
        doc.add_paragraph("\u2022 Considerar a realização de workshops e treinamentos para a equipe envolvida na gestão de riscos.")
        doc.add_paragraph("\u2022 Documentar todas as decisões e ações relacionadas à gestão de riscos para futuras referências e aprendizado organizacional.")

        doc.add_page_break()

        # 7. CONCLUSÃO
        doc.add_heading('7. CONCLUSÃO', level=1)
        doc.add_paragraph("A gestão proativa de riscos é fundamental para o sucesso de qualquer projeto. Este relatório forneceu uma análise abrangente dos riscos associados às diferentes modalidades de contratação, permitindo uma tomada de decisão mais informada e a implementação de estratégias eficazes para minimizar impactos negativos e maximizar as chances de sucesso do projeto.")
        
        # Salvar o documento em um buffer de bytes
        doc_buffer = BytesIO()
        doc.save(doc_buffer)
        doc_buffer.seek(0)
        
        return doc_buffer

    except ImportError:
        st.error("A biblioteca 'python-docx' não está instalada. Por favor, instale-a para gerar relatórios Word: pip install python-docx")
        return None
    except Exception as e:
        st.error(f"Erro ao gerar relatório Word: {e}")
        return None

# Inicialização do banco de dados
init_db()

# --- Funções de Interface do Streamlit ---
def login_page():
    st.title("Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        if verificar_login(username, password):
            st.session_state.logged_in = True
            st.session_state.user = username
            registrar_acao(username, "Login", {"status": "sucesso"})
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha inválidos")
            registrar_acao(username, "Login", {"status": "falha"})

def logout():
    registrar_acao(st.session_state.user, "Logout")
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.riscos = []
    st.session_state.modalidades = MODALIDADES_PADRAO.copy()
    st.session_state.nome_projeto = "Meu Projeto de Avaliação de Riscos"
    st.session_state.identificacao_relatorio = None # Limpar identificação do relatório
    st.experimental_rerun()

def cadastrar_risco_page():
    st.subheader("Cadastrar Novo Risco")

    with st.form("form_cadastro_risco", clear_on_submit=True):
        nome = st.selectbox("Nome do Risco", list(ASPECTOS_RISCOS.keys()), key="nome_risco_cadastro")
        descricao = st.text_area("Descrição Detalhada do Risco", key="descricao_risco_cadastro")
        
        st.markdown("### Avaliação de Impacto")
        impacto_selecionado = st.radio("Selecione o Impacto", list(ESCALAS_IMPACTO.keys()), key="impacto_cadastro")
        justificativa_impacto = st.text_area("Justificativa para a nota de Impacto (obrigatório)", key="just_impacto_cadastro")
        st.info(f"Descrição do Impacto: {ESCALAS_IMPACTO[impacto_selecionado]['descricao']}")

        st.markdown("### Avaliação de Probabilidade")
        probabilidade_selecionada = st.radio("Selecione a Probabilidade", list(ESCALAS_PROBABILIDADE.keys()), key="probabilidade_cadastro")
        justificativa_probabilidade = st.text_area("Justificativa para a nota de Probabilidade (obrigatório)", key="just_prob_cadastro")
        st.info(f"Descrição da Probabilidade: {ESCALAS_PROBABILIDADE[probabilidade_selecionada]['descricao']}")

        st.markdown("### Fatores de Mitigação por Modalidade")
        fatores_mitigacao = {}
        for modalidade in st.session_state.modalidades:
            fator = st.slider(f"Fator de Mitigação para {modalidade}", 0.0, 1.0, 1.0, 0.05, key=f"fator_{modalidade}_cadastro")
            fatores_mitigacao[modalidade] = fator

        submitted = st.form_submit_button("Cadastrar Risco")
        if submitted:
            if not justificativa_impacto.strip():
                st.error("A justificativa para a nota de Impacto é obrigatória.")
            elif not justificativa_probabilidade.strip():
                st.error("A justificativa para a nota de Probabilidade é obrigatória.")
            else:
                impacto_valor = ESCALAS_IMPACTO[impacto_selecionado]['valor']
                probabilidade_valor = ESCALAS_PROBABILIDADE[probabilidade_selecionada]['valor']
                risco_inerente = impacto_valor * probabilidade_valor
                classificacao, cor = classificar_risco(risco_inerente)

                novo_risco = {
                    "id": len(st.session_state.riscos) + 1,
                    "nome": nome,
                    "descricao": descricao,
                    "impacto": impacto_valor,
                    "justificativa_impacto": justificativa_impacto,
                    "probabilidade": probabilidade_valor,
                    "justificativa_probabilidade": justificativa_probabilidade,
                    "risco_inerente": risco_inerente,
                    "classificacao": classificacao,
                    "cor": cor,
                    "modalidades": fatores_mitigacao
                }
                st.session_state.riscos.append(novo_risco)
                registrar_acao(st.session_state.user, "Cadastro de Risco", {"risco": nome, "id": novo_risco["id"]})
                st.success(f"Risco '{nome}' cadastrado com sucesso!")
                st.experimental_rerun()

def editar_risco_page():
    st.subheader("Editar Risco Existente")

    if not st.session_state.riscos:
        st.info("Nenhum risco cadastrado para editar.")
        return

    riscos_nomes = {risco['nome']: risco for risco in st.session_state.riscos}
    risco_selecionado_nome = st.selectbox("Selecione o Risco para Editar", list(riscos_nomes.keys()), key="select_risco_editar")

    if risco_selecionado_nome:
        risco_para_editar = riscos_nomes[risco_selecionado_nome]
        risco_index = st.session_state.riscos.index(risco_para_editar)

        with st.form(f"form_editar_risco_{risco_para_editar['id']}"):
            st.text_input("Nome do Risco", risco_para_editar['nome'], disabled=True)
            descricao_editada = st.text_area("Descrição Detalhada do Risco", risco_para_editar['descricao'], key=f"descricao_editada_{risco_para_editar['id']}")

            st.markdown("### Avaliação de Impacto")
            # Encontrar a chave do impacto atual
            impacto_atual_key = [k for k, v in ESCALAS_IMPACTO.items() if v['valor'] == risco_para_editar['impacto']][0]
            impacto_selecionado_editado = st.radio("Selecione o Impacto", list(ESCALAS_IMPACTO.keys()), index=list(ESCALAS_IMPACTO.keys()).index(impacto_atual_key), key=f"impacto_editado_{risco_para_editar['id']}")
            
            # Garantir que a justificativa exista, senão preencher com '.'
            justificativa_impacto_editada_default = risco_para_editar.get('justificativa_impacto', '.')
            justificativa_impacto_editada = st.text_area("Justificativa para a nota de Impacto (obrigatório)", value=justificativa_impacto_editada_default, key=f"just_impacto_editada_{risco_para_editar['id']}")
            st.info(f"Descrição do Impacto: {ESCALAS_IMPACTO[impacto_selecionado_editado]['descricao']}")

            st.markdown("### Avaliação de Probabilidade")
            # Encontrar a chave da probabilidade atual
            probabilidade_atual_key = [k for k, v in ESCALAS_PROBABILIDADE.items() if v['valor'] == risco_para_editar['probabilidade']][0]
            probabilidade_selecionada_editada = st.radio("Selecione a Probabilidade", list(ESCALAS_PROBABILIDADE.keys()), index=list(ESCALAS_PROBABILIDADE.keys()).index(probabilidade_atual_key), key=f"probabilidade_editada_{risco_para_editar['id']}")
            
            # Garantir que a justificativa exista, senão preencher com '.'
            justificativa_probabilidade_editada_default = risco_para_editar.get('justificativa_probabilidade', '.')
            justificativa_probabilidade_editada = st.text_area("Justificativa para a nota de Probabilidade (obrigatório)", value=justificativa_probabilidade_editada_default, key=f"just_prob_editada_{risco_para_editar['id']}")
            st.info(f"Descrição da Probabilidade: {ESCALAS_PROBABILIDADE[probabilidade_selecionada_editada]['descricao']}")

            st.markdown("### Fatores de Mitigação por Modalidade")
            fatores_mitigacao_editados = {}
            for modalidade in st.session_state.modalidades:
                fator_atual = risco_para_editar['modalidades'].get(modalidade, 1.0) # Pega o fator atual ou 1.0 se não existir
                fator = st.slider(f"Fator de Mitigação para {modalidade}", 0.0, 1.0, fator_atual, 0.05, key=f"fator_editado_{modalidade}_{risco_para_editar['id']}")
                fatores_mitigacao_editados[modalidade] = fator

            col1, col2 = st.columns(2)
            with col1:
                salvar_edicao = st.form_submit_button("Salvar Edição")
            with col2:
                excluir_risco = st.form_submit_button("Excluir Risco")

            if salvar_edicao:
                if not justificativa_impacto_editada.strip():
                    st.error("A justificativa para a nota de Impacto é obrigatória.")
                elif not justificativa_probabilidade_editada.strip():
                    st.error("A justificativa para a nota de Probabilidade é obrigatória.")
                else:
                    impacto_valor_editado = ESCALAS_IMPACTO[impacto_selecionado_editado]['valor']
                    probabilidade_valor_editada = ESCALAS_PROBABILIDADE[probabilidade_selecionada_editada]['valor']
                    risco_inerente_editado = impacto_valor_editado * probabilidade_valor_editada
                    classificacao_editada, cor_editada = classificar_risco(risco_inerente_editado)

                    st.session_state.riscos[risco_index] = {
                        "id": risco_para_editar['id'],
                        "nome": risco_para_editar['nome'],
                        "descricao": descricao_editada,
                        "impacto": impacto_valor_editado,
                        "justificativa_impacto": justificativa_impacto_editada,
                        "probabilidade": probabilidade_valor_editada,
                        "justificativa_probabilidade": justificativa_probabilidade_editada,
                        "risco_inerente": risco_inerente_editado,
                        "classificacao": classificacao_editada,
                        "cor": cor_editada,
                        "modalidades": fatores_mitigacao_editados
                    }
                    registrar_acao(st.session_state.user, "Edição de Risco", {"risco": risco_para_editar['nome'], "id": risco_para_editar['id']})
                    st.success(f"Risco '{risco_para_editar['nome']}' atualizado com sucesso!")
                    st.experimental_rerun()

            if excluir_risco:
                st.session_state.riscos.pop(risco_index)
                registrar_acao(st.session_state.user, "Exclusão de Risco", {"risco": risco_para_editar['nome'], "id": risco_para_editar['id']})
                st.success(f"Risco '{risco_para_editar['nome']}' excluído com sucesso!")
                st.experimental_rerun()

def reavaliacao_modalidades_page():
    st.subheader("Reavaliação das Modalidades")

    if not st.session_state.modalidades:
        st.info("Nenhuma modalidade cadastrada.")
        return

    st.write("Ajuste os fatores de mitigação para cada modalidade. Estes fatores serão aplicados a TODOS os riscos cadastrados.")

    novas_modalidades_fatores = {}
    for modalidade in st.session_state.modalidades:
        novo_fator = st.slider(f"Fator de Mitigação para {modalidade}", 0.0, 1.0, 1.0, 0.05, key=f"reavalia_fator_{modalidade}")
        novas_modalidades_fatores[modalidade] = novo_fator
    
    if st.button("Aplicar Novos Fatores de Mitigação"):
        for risco in st.session_state.riscos:
            for modalidade, novo_fator in novas_modalidades_fatores.items():
                risco['modalidades'][modalidade] = novo_fator
        registrar_acao(st.session_state.user, "Reavaliação de Modalidades", {"fatores_aplicados": novas_modalidades_fatores})
        st.success("Fatores de mitigação aplicados a todos os riscos com sucesso!")
        st.experimental_rerun()

def avaliacao_modalidades_page():
    st.subheader("Avaliação das Modalidades")

    if not st.session_state.riscos:
        st.info("Nenhum risco cadastrado para avaliação. Por favor, cadastre riscos primeiro.")
        return

    if not st.session_state.modalidades:
        st.info("Nenhuma modalidade cadastrada para avaliação. Por favor, cadastre modalidades primeiro.")
        return

    st.write("### Risco Residual por Modalidade")

    risco_acumulado_por_modalidade = {}
    for modalidade in st.session_state.modalidades:
        risco_residual_total = 0
        for risco in st.session_state.riscos:
            if modalidade in risco['modalidades']:
                fator_mitigacao = risco['modalidades'][modalidade]
                risco_residual = risco['risco_inerente'] * fator_mitigacao
                risco_residual_total += risco_residual
        risco_acumulado_por_modalidade[modalidade] = risco_residual_total

    df_risco_modalidade = pd.DataFrame(
        list(risco_acumulado_por_modalidade.items()),
        columns=['Modalidade', 'Risco Residual Acumulado']
    ).sort_values(by='Risco Residual Acumulado', ascending=True)

    st.dataframe(df_risco_modalidade, use_container_width=True)

    fig_modalidades = px.bar(
        df_risco_modalidade,
        x='Modalidade',
        y='Risco Residual Acumulado',
        title='Risco Residual Acumulado por Modalidade',
        labels={'Risco Residual Acumulado': 'Risco Residual Acumulado'},
        color='Risco Residual Acumulado',
        color_continuous_scale=px.colors.sequential.Plasma
    )
    st.plotly_chart(fig_modalidades, use_container_width=True)

    st.write("### Detalhamento do Risco Residual por Risco e Modalidade")

    # Preparar dados para o heatmap
    data_heatmap = []
    for risco in st.session_state.riscos:
        row = {'Risco': risco['nome']}
        for modalidade in st.session_state.modalidades:
            fator_mitigacao = risco['modalidades'].get(modalidade, 1.0) # Pega o fator ou 1.0 se não existir
            risco_residual = risco['risco_inerente'] * fator_mitigacao
            row[modalidade] = risco_residual
        data_heatmap.append(row)

    df_heatmap = pd.DataFrame(data_heatmap).set_index('Risco')

    if not df_heatmap.empty:
        fig_heatmap = px.imshow(df_heatmap,
                                 text_auto=True,
                                 aspect="auto",
                                 color_continuous_scale="RdYlGn_r",
                                 title="Risco Residual por Risco e Modalidade")
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("Não há dados suficientes para gerar o heatmap de risco residual.")

def gerenciar_modalidades_page():
    st.subheader("Gerenciar Modalidades de Mitigação")

    st.write("### Modalidades Atuais")
    if st.session_state.modalidades:
        for i, modalidade in enumerate(st.session_state.modalidades):
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                st.write(f"- {modalidade}")
            with col2:
                if st.button("Remover", key=f"remove_modalidade_{modalidade}"):
                    st.session_state.modalidades.remove(modalidade)
                    # Remover a modalidade dos riscos existentes
                    for risco in st.session_state.riscos:
                        if modalidade in risco['modalidades']:
                            del risco['modalidades'][modalidade]
                    registrar_acao(st.session_state.user, "Remoção de Modalidade", {"modalidade": modalidade})
                    st.success(f"Modalidade '{modalidade}' removida.")
                    st.experimental_rerun()
    else:
        st.info("Nenhuma modalidade cadastrada.")

    st.write("### Adicionar Nova Modalidade")
    nova_modalidade = st.text_input("Nome da Nova Modalidade")
    if st.button("Adicionar Modalidade"):
        if nova_modalidade and nova_modalidade not in st.session_state.modalidades:
            st.session_state.modalidades.append(nova_modalidade)
            # Adicionar a nova modalidade aos riscos existentes com fator 1.0
            for risco in st.session_state.riscos:
                risco['modalidades'][nova_modalidade] = 1.0
            registrar_acao(st.session_state.user, "Adição de Modalidade", {"modalidade": nova_modalidade})
            st.success(f"Modalidade '{nova_modalidade}' adicionada.")
            st.experimental_rerun()
        elif nova_modalidade in st.session_state.modalidades:
            st.warning(f"A modalidade '{nova_modalidade}' já existe.")
        else:
            st.warning("Por favor, digite um nome para a nova modalidade.")

def dashboard_page():
    st.subheader("Dashboard de Avaliação de Riscos")

    st.write(f"### Projeto: {st.session_state.nome_projeto}")

    # Campo para editar o nome do projeto
    novo_nome_projeto = st.text_input("Editar Nome do Projeto", st.session_state.nome_projeto)
    if novo_nome_projeto != st.session_state.nome_projeto:
        st.session_state.nome_projeto = novo_nome_projeto
        registrar_acao(st.session_state.user, "Edição de Nome de Projeto", {"novo_nome": novo_nome_projeto})
        st.success("Nome do projeto atualizado!")
        st.experimental_rerun()

    if not st.session_state.riscos:
        st.info("Nenhum risco cadastrado. Por favor, cadastre riscos na aba 'Cadastrar Risco'.")
        return

    df_riscos = pd.DataFrame(st.session_state.riscos)

    # Gráfico de Matriz de Risco (Impacto vs Probabilidade)
    st.write("### Matriz de Risco Inerente")
    fig_matriz = px.scatter(
        df_riscos,
        x='probabilidade',
        y='impacto',
        size='risco_inerente',
        color='classificacao',
        color_discrete_map={'Baixo': '#28a745', 'Médio': '#ffc107', 'Alto': '#dc3545'},
        hover_name='nome',
        hover_data={'descricao': True, 'risco_inerente': ':.2f', 'impacto': True, 'probabilidade': True},
        title='Matriz de Risco Inerente (Impacto vs Probabilidade)',
        labels={'impacto': 'Impacto', 'probabilidade': 'Probabilidade'},
        range_x=[0, 10], range_y=[0, 10]
    )
    fig_matriz.update_traces(marker=dict(sizemode='diameter', sizeref=2.*max(df_riscos['risco_inerente'])/(60.**2), sizemin=4))
    fig_matriz.update_layout(
        xaxis = dict(
            tickmode = 'array',
            tickvals = [v['valor'] for v in ESCALAS_PROBABILIDADE.values()],
            ticktext = list(ESCALAS_PROBABILIDADE.keys())
        ),
        yaxis = dict(
            tickmode = 'array',
            tickvals = [v['valor'] for v in ESCALAS_IMPACTO.values()],
            ticktext = list(ESCALAS_IMPACTO.keys())
        )
    )
    st.plotly_chart(fig_matriz, use_container_width=True)

    # Gráfico de Barras de Classificação de Risco
    st.write("### Classificação dos Riscos Inerentes")
    contagem_classificacao = df_riscos['classificacao'].value_counts().reindex(['Baixo', 'Médio', 'Alto'])
    fig_classificacao = px.bar(
        x=contagem_classificacao.index,
        y=contagem_classificacao.values,
        color=contagem_classificacao.index,
        color_discrete_map={'Baixo': '#28a745', 'Médio': '#ffc107', 'Alto': '#dc3545'},
        labels={'x': 'Classificação', 'y': 'Número de Riscos'},
        title='Número de Riscos por Classificação Inerente'
    )
    st.plotly_chart(fig_classificacao, use_container_width=True)

    # Tabela de Riscos Cadastrados
    st.write("### Detalhamento dos Riscos Cadastrados")
    df_display = df_riscos[['nome', 'descricao', 'impacto', 'justificativa_impacto', 'probabilidade', 'justificativa_probabilidade', 'risco_inerente', 'classificacao']]
    st.dataframe(df_display, use_container_width=True)

    # Gráfico de Risco Inerente por Risco
    st.write("### Risco Inerente por Risco")
    fig_risco_inerente = px.bar(
        df_riscos.sort_values(by='risco_inerente', ascending=False),
        x='nome',
        y='risco_inerente',
        color='classificacao',
        color_discrete_map={'Baixo': '#28a745', 'Médio': '#ffc107', 'Alto': '#dc3545'},
        labels={'nome': 'Risco', 'risco_inerente': 'Risco Inerente'},
        title='Risco Inerente por Risco'
    )
    st.plotly_chart(fig_risco_inerente, use_container_width=True)

    # Gráfico de Risco Residual por Modalidade (se houver modalidades e riscos)
    if st.session_state.modalidades and st.session_state.riscos:
        st.write("### Risco Residual Acumulado por Modalidade")
        risco_acumulado_por_modalidade = {}
        for modalidade in st.session_state.modalidades:
            risco_residual_total = 0
            for risco in st.session_state.riscos:
                if modalidade in risco['modalidades']:
                    fator_mitigacao = risco['modalidades'][modalidade]
                    risco_residual = risco['risco_inerente'] * fator_mitigacao
                    risco_residual_total += risco_residual
            risco_acumulado_por_modalidade[modalidade] = risco_residual_total

        df_risco_modalidade = pd.DataFrame(
            list(risco_acumulado_por_modalidade.items()),
            columns=['Modalidade', 'Risco Residual Acumulado']
        ).sort_values(by='Risco Residual Acumulado', ascending=True)

        fig_modalidades = px.bar(
            df_risco_modalidade,
            x='Modalidade',
            y='Risco Residual Acumulado',
            title='Risco Residual Acumulado por Modalidade',
            labels={'Risco Residual Acumulado': 'Risco Residual Acumulado'},
            color='Risco Residual Acumulado',
            color_continuous_scale=px.colors.sequential.Plasma
        )
        st.plotly_chart(fig_modalidades, use_container_width=True)

def logs_page():
    st.subheader("Logs de Atividade")
    logs = obter_logs()
    if logs:
        df_logs = pd.DataFrame(logs, columns=['Timestamp', 'Usuário', 'Ação', 'Detalhes'])
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.info("Nenhuma atividade registrada ainda.")

def identificacao_relatorio_page():
    st.subheader("Identificação do Responsável pelo Relatório")

    # Inicializa com valores padrão ou os já existentes
    if 'identificacao_relatorio' not in st.session_state or st.session_state.identificacao_relatorio is None:
        st.session_state.identificacao_relatorio = {
            'nome': st.session_state.user,
            'unidade': 'Unidade Padrão',
            'orgao': 'SPU',
            'email': 'usuario@spu.gov.br'
        }

    with st.form("form_identificacao_relatorio"):
        nome = st.text_input("Nome Completo", value=st.session_state.identificacao_relatorio['nome'], key="id_nome")
        unidade = st.text_input("Unidade/Divisão", value=st.session_state.identificacao_relatorio['unidade'], key="id_unidade")
        orgao = st.text_input("Órgão", value=st.session_state.identificacao_relatorio['orgao'], key="id_orgao")
        email = st.text_input("E-mail", value=st.session_state.identificacao_relatorio['email'], key="id_email")

        submitted = st.form_submit_button("Salvar Identificação")
        if submitted:
            st.session_state.identificacao_relatorio = {
                'nome': nome,
                'unidade': unidade,
                'orgao': orgao,
                'email': email
            }
            registrar_acao(st.session_state.user, "Atualização Identificação Relatório", {"nome": nome})
            st.success("Identificação salva com sucesso!")
            st.experimental_rerun()

# --- Lógica Principal do Aplicativo ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.riscos = []
    st.session_state.modalidades = MODALIDADES_PADRAO.copy()
    st.session_state.nome_projeto = "Meu Projeto de Avaliação de Riscos"
    st.session_state.identificacao_relatorio = None

# Backfill para riscos existentes: garantir que 'justificativa_impacto' e 'justificativa_probabilidade' existam
# Isso é importante para riscos que foram cadastrados antes da implementação desses campos
if 'riscos' in st.session_state and st.session_state.riscos:
    for risco in st.session_state.riscos:
        if 'justificativa_impacto' not in risco:
            risco['justificativa_impacto'] = '.'
        if 'justificativa_probabilidade' not in risco:
            risco['justificativa_probabilidade'] = '.'

if not st.session_state.logged_in:
    login_page()
else:
    st.sidebar.title(f"Bem-vindo, {st.session_state.user}!")
    st.sidebar.markdown(f"**Projeto Atual:** {st.session_state.nome_projeto}")

    menu = [
        "Dashboard", 
        "Cadastrar Risco", 
        "Editar Risco", 
        "Reavaliação das Modalidades", 
        "Avaliação das Modalidades", 
        "Gerenciar Modalidades",
        "Identificação do Relatório",
        "Logs de Atividade",
        "Gerar Relatório Word"
    ]
    choice = st.sidebar.radio("Menu", menu)

    if choice == "Dashboard":
        dashboard_page()
    elif choice == "Cadastrar Risco":
        cadastrar_risco_page()
    elif choice == "Editar Risco":
        editar_risco_page()
    elif choice == "Reavaliação das Modalidades":
        reavaliacao_modalidades_page()
    elif choice == "Avaliação das Modalidades":
        avaliacao_modalidades_page()
    elif choice == "Gerenciar Modalidades":
        gerenciar_modalidades_page()
    elif choice == "Identificação do Relatório":
        identificacao_relatorio_page()
    elif choice == "Logs de Atividade":
        logs_page()
    elif choice == "Gerar Relatório Word":
        st.subheader("Gerar Relatório Word")
        st.write("Clique no botão abaixo para gerar o relatório completo em formato Word.")
        
        if st.button("Gerar Relatório"):
            with st.spinner("Gerando relatório Word... Isso pode levar alguns segundos."):
                word_buffer = gerar_relatorio_word()
                if word_buffer:
                    st.download_button(
                        label="Download Relatório Word",
                        data=word_buffer,
                        file_name=f"Relatorio_Avaliacao_Riscos_{st.session_state.nome_projeto.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    registrar_acao(st.session_state.user, "Geração de Relatório Word", {"projeto": st.session_state.nome_projeto})
                    st.success("Relatório gerado com sucesso!")
                else:
                    st.error("Falha ao gerar o relatório Word.")

    st.sidebar.markdown("--- ")
    st.sidebar.button("Sair", on_click=logout)




