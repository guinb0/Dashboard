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
    """Gera relatório completo e amplo em formato Word com nome do projeto"""
    try:
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_ALIGN_VERTICAL
        from docx.oxml.shared import OxmlElement, qn
        from io import BytesIO
        
        # Criar documento
        doc = Document()
        
        # Obter nome do projeto do session_state
        nome_projeto = st.session_state.get('nome_projeto', 'Projeto Não Identificado')
        
        # Título principal com nome do projeto
        title = doc.add_heading(f'RELATÓRIO EXECUTIVO DE AVALIAÇÃO DE RISCOS', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtítulo com nome do projeto
        subtitle = doc.add_heading(f'Projeto: {nome_projeto}', level=1)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Metodologia
        metodologia = doc.add_heading('Metodologia TCU - Análise Comparativa de Modalidades de Contratação', level=2)
        metodologia.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
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
        info_para.add_run("Projeto: ").bold = True
        info_para.add_run(f"{nome_projeto}")
        info_para.add_run("\nData da Análise: ").bold = True
        info_para.add_run(f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        info_para.add_run("\nMetodologia: ").bold = True
        info_para.add_run("Roteiro de Auditoria de Gestão de Riscos - TCU")
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
        Este relatório apresenta análise quantitativa de {total_riscos} riscos identificados para o projeto "{nome_projeto}", 
        utilizando a metodologia do Tribunal de Contas da União (TCU). A análise inclui avaliação detalhada 
        de {len(st.session_state.modalidades)} modalidades de contratação, considerando aspectos de impacto e 
        probabilidade de cada risco.

        PRINCIPAIS RESULTADOS:
        • Total de riscos analisados: {total_riscos}
        • Riscos de nível alto: {riscos_altos} ({riscos_altos/total_riscos*100:.1f}%)
        • Riscos de nível médio: {riscos_medios} ({riscos_medios/total_riscos*100:.1f}%)
        • Riscos de nível baixo: {riscos_baixos} ({riscos_baixos/total_riscos*100:.1f}%)
        • Risco inerente total acumulado: {risco_inerente_total:.2f}

        MODALIDADE RECOMENDADA: {melhor_modalidade}
        (Menor risco residual: {risco_acumulado_por_modalidade[melhor_modalidade]:.2f})

        MODALIDADE MENOS RECOMENDADA: {pior_modalidade}
        (Maior risco residual: {risco_acumulado_por_modalidade[pior_modalidade]:.2f})
        """
        
        doc.add_paragraph(resumo)
        
        # 2. METODOLOGIA
        doc.add_heading('2. METODOLOGIA', level=1)
        
        metodologia_texto = """
        A análise de riscos foi conduzida seguindo as diretrizes do Roteiro de Auditoria de Gestão de Riscos 
        do Tribunal de Contas da União (TCU), que estabelece uma abordagem sistemática para identificação, 
        avaliação e tratamento de riscos em projetos públicos.

        2.1 ESCALAS DE AVALIAÇÃO

        IMPACTO (Consequências da materialização do risco):
        • Muito baixo (1): Degradação de operações causando impactos mínimos nos objetivos
        • Baixo (2): Degradação de operações causando impactos pequenos nos objetivos  
        • Médio (5): Interrupção de operações causando impactos significativos mas recuperáveis
        • Alto (8): Interrupção de operações causando impactos de reversão muito difícil
        • Muito alto (10): Paralisação de operações causando impactos irreversíveis/catastróficos

        PROBABILIDADE (Chance de ocorrência do evento de risco):
        • Muito baixa (1): Evento improvável de ocorrer. Não há elementos que indiquem essa possibilidade
        • Baixa (2): Evento raro de ocorrer. Poucos elementos indicam essa possibilidade
        • Média (5): Evento possível de ocorrer. Elementos indicam moderadamente essa possibilidade
        • Alta (8): Evento provável de ocorrer. Elementos indicam consistentemente essa possibilidade
        • Muito alta (10): Evento praticamente certo de ocorrer. Elementos indicam claramente essa possibilidade

        2.2 CÁLCULO DO RISCO

        O valor do risco é calculado pela multiplicação: RISCO = IMPACTO × PROBABILIDADE

        Classificação final:
        • Risco Baixo: ≤ 10
        • Risco Médio: 11-25  
        • Risco Alto: > 25

        2.3 ANÁLISE COMPARATIVA DE MODALIDADES

        Para cada modalidade de contratação, foi aplicado um fator de mitigação específico baseado nas 
        características inerentes da modalidade em relação a cada tipo de risco. O risco residual é 
        calculado como: RISCO RESIDUAL = RISCO INERENTE × FATOR DE MITIGAÇÃO
        """
        
        doc.add_paragraph(metodologia_texto)
        
        # 3. ANÁLISE DETALHADA DOS RISCOS
        doc.add_heading('3. ANÁLISE DETALHADA DOS RISCOS', level=1)
        
        for i, risco in enumerate(st.session_state.riscos, 1):
            doc.add_heading(f'3.{i} {risco["nome"]}', level=2)
            
            # Informações básicas do risco
            info_risco = doc.add_paragraph()
            info_risco.add_run("Classificação: ").bold = True
            info_risco.add_run(f"{risco['classificacao']} ")
            
            # Adicionar cor baseada na classificação
            if risco['classificacao'] == 'Alto':
                info_risco.add_run("🔴")
            elif risco['classificacao'] == 'Médio':
                info_risco.add_run("🟡")
            else:
                info_risco.add_run("🟢")
            
            info_risco.add_run(f"\nImpacto: ").bold = True
            info_risco.add_run(f"{risco['impacto']} ({ESCALAS_IMPACTO[risco['impacto']]['valor']})")
            info_risco.add_run(f"\nProbabilidade: ").bold = True
            info_risco.add_run(f"{risco['probabilidade']} ({ESCALAS_PROBABILIDADE[risco['probabilidade']]['valor']})")
            info_risco.add_run(f"\nRisco Inerente: ").bold = True
            info_risco.add_run(f"{risco['risco_inerente']:.2f}")
            
            # Descrição do impacto e probabilidade
            doc.add_paragraph(f"Descrição do Impacto: {ESCALAS_IMPACTO[risco['impacto']]['descricao']}")
            doc.add_paragraph(f"Descrição da Probabilidade: {ESCALAS_PROBABILIDADE[risco['probabilidade']]['descricao']}")
            
            # Aspectos considerados na avaliação
            if risco['nome'] in ASPECTOS_RISCOS:
                doc.add_heading(f'Aspectos Considerados na Avaliação', level=3)
                
                doc.add_heading(f'Aspectos de Impacto:', level=4)
                for aspecto in ASPECTOS_RISCOS[risco['nome']]['impacto']:
                    doc.add_paragraph(f"• {aspecto}", style='List Bullet')
                
                doc.add_heading(f'Aspectos de Probabilidade:', level=4)
                for aspecto in ASPECTOS_RISCOS[risco['nome']]['probabilidade']:
                    doc.add_paragraph(f"• {aspecto}", style='List Bullet')
            
            # Análise por modalidade
            doc.add_heading(f'Análise por Modalidade de Contratação', level=3)
            
            # Criar tabela para as modalidades
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            
            # Cabeçalho da tabela
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Modalidade'
            hdr_cells[1].text = 'Fator de Mitigação'
            hdr_cells[2].text = 'Risco Residual'
            
            # Dados das modalidades
            for modalidade in st.session_state.modalidades:
                if modalidade in risco['modalidades']:
                    row_cells = table.add_row().cells
                    fator_mitigacao = risco['modalidades'][modalidade]
                    risco_residual = risco['risco_inerente'] * fator_mitigacao
                    
                    row_cells[0].text = modalidade
                    row_cells[1].text = f"{fator_mitigacao:.2f}"
                    row_cells[2].text = f"{risco_residual:.2f}"
        
        # 4. COMPARAÇÃO ENTRE MODALIDADES
        doc.add_heading('4. COMPARAÇÃO ENTRE MODALIDADES', level=1)
        
        # Criar tabela comparativa
        table_comp = doc.add_table(rows=1, cols=len(st.session_state.modalidades) + 1)
        table_comp.style = 'Table Grid'
        
        # Cabeçalho
        hdr_cells = table_comp.rows[0].cells
        hdr_cells[0].text = 'Risco'
        for i, modalidade in enumerate(st.session_state.modalidades, 1):
            hdr_cells[i].text = modalidade
        
        # Dados dos riscos por modalidade
        for risco in st.session_state.riscos:
            row_cells = table_comp.add_row().cells
            row_cells[0].text = risco['nome']
            
            for i, modalidade in enumerate(st.session_state.modalidades, 1):
                if modalidade in risco['modalidades']:
                    fator_mitigacao = risco['modalidades'][modalidade]
                    risco_residual = risco['risco_inerente'] * fator_mitigacao
                    row_cells[i].text = f"{risco_residual:.2f}"
                else:
                    row_cells[i].text = "N/A"
        
        # Linha de totais
        row_cells = table_comp.add_row().cells
        row_cells[0].text = "TOTAL ACUMULADO"
        for i, modalidade in enumerate(st.session_state.modalidades, 1):
            total = risco_acumulado_por_modalidade[modalidade]
            row_cells[i].text = f"{total:.2f}"
        
        # 5. RECOMENDAÇÕES
        doc.add_heading('5. RECOMENDAÇÕES', level=1)
        
        recomendacoes = f"""
        Com base na análise quantitativa realizada para o projeto "{nome_projeto}", apresentam-se as seguintes recomendações:

        5.1 MODALIDADE RECOMENDADA

        A modalidade "{melhor_modalidade}" apresentou o menor risco residual acumulado ({risco_acumulado_por_modalidade[melhor_modalidade]:.2f}), 
        sendo portanto a opção mais adequada do ponto de vista da gestão de riscos.

        5.2 RISCOS PRIORITÁRIOS PARA MONITORAMENTO

        Os seguintes riscos requerem atenção especial independentemente da modalidade escolhida:
        """
        
        # Identificar os 3 maiores riscos
        riscos_ordenados = sorted(st.session_state.riscos, key=lambda x: x['risco_inerente'], reverse=True)
        for i, risco in enumerate(riscos_ordenados[:3], 1):
            recomendacoes += f"\n{i}. {risco['nome']} (Risco inerente: {risco['risco_inerente']:.2f})"
        
        recomendacoes += f"""

        5.3 MEDIDAS DE MITIGAÇÃO GERAIS

        • Estabelecer estrutura robusta de monitoramento e controle
        • Implementar mecanismos contratuais adequados de garantia e sanção
        • Realizar acompanhamento periódico da execução do projeto
        • Manter documentação atualizada de todos os procedimentos
        • Estabelecer canais de comunicação eficientes entre as partes envolvidas

        5.4 REVISÃO PERIÓDICA

        Recomenda-se revisão trimestral desta análise de riscos, considerando:
        • Mudanças no cenário econômico e regulatório
        • Evolução das condições específicas do projeto
        • Surgimento de novos riscos não identificados inicialmente
        • Efetividade das medidas de mitigação implementadas
        """
        
        doc.add_paragraph(recomendacoes)
        
        # 6. CONCLUSÃO
        doc.add_heading('6. CONCLUSÃO', level=1)
        
        diferenca_percentual = ((risco_acumulado_por_modalidade[pior_modalidade] - risco_acumulado_por_modalidade[melhor_modalidade]) / risco_acumulado_por_modalidade[melhor_modalidade]) * 100
        
        conclusao = f"""
        A análise quantitativa de riscos realizada para o projeto "{nome_projeto}" demonstra que a escolha da modalidade 
        de contratação tem impacto significativo no perfil de risco do empreendimento.

        A modalidade "{melhor_modalidade}" apresenta vantagem de {diferenca_percentual:.1f}% em relação à modalidade 
        "{pior_modalidade}" no que se refere ao risco residual acumulado.

        Esta análise fornece base técnica sólida para a tomada de decisão, devendo ser complementada por considerações 
        de viabilidade econômica, aspectos jurídicos e alinhamento com os objetivos estratégicos da organização.

        A implementação de um sistema de monitoramento contínuo dos riscos identificados é fundamental para o sucesso 
        do projeto, independentemente da modalidade escolhida.
        """
        
        doc.add_paragraph(conclusao)
        
        # Salvar documento em BytesIO
        doc_io = BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        
        return doc_io
        
    except ImportError:
        st.error("Biblioteca python-docx não encontrada. Instale com: pip install python-docx")
        return None
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")
        return None

# Inicializar banco de dados
init_db()

# Inicializar session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'riscos' not in st.session_state:
    st.session_state.riscos = []
if 'modalidades' not in st.session_state:
    st.session_state.modalidades = MODALIDADES_PADRAO.copy()
if 'identificacao_relatorio' not in st.session_state:
    st.session_state.identificacao_relatorio = None
if 'nome_projeto' not in st.session_state:
    st.session_state.nome_projeto = ""

# Tela de login
if not st.session_state.authenticated:
    st.title("🔐 Sistema de Avaliação de Riscos - SPU")
    st.markdown("### Login do Sistema")
    
    with st.form("login_form"):
        username = st.selectbox("Usuário", ["SPU 1", "SPU 2", "SPU 3"])
        password = st.text_input("Senha", type="password")
        submit_button = st.form_submit_button("Entrar")
        
        if submit_button:
            if verificar_login(username, password):
                st.session_state.authenticated = True
                st.session_state.user = username
                registrar_acao(username, "Login realizado")
                st.rerun()
            else:
                st.error("Credenciais inválidas!")

else:
    # Interface principal
    st.title("⚠️ Dashboard de Avaliação de Riscos")
    st.markdown(f"**Usuário logado:** {st.session_state.user}")
    
    # Sidebar para logout e informações do projeto
    with st.sidebar:
        st.markdown("### Informações do Projeto")
        
        # Campo para nome do projeto
        nome_projeto = st.text_input(
            "Nome do Projeto *", 
            value=st.session_state.nome_projeto,
            help="Digite o nome do projeto que aparecerá no relatório"
        )
        
        if nome_projeto != st.session_state.nome_projeto:
            st.session_state.nome_projeto = nome_projeto
        
        st.markdown("---")
        
        if st.button("🚪 Logout"):
            registrar_acao(st.session_state.user, "Logout realizado")
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Informações do Sistema")
        st.markdown("**Versão:** 2.0")
        st.markdown("**Metodologia:** TCU")
        st.markdown(f"**Riscos cadastrados:** {len(st.session_state.riscos)}")
        st.markdown(f"**Modalidades:** {len(st.session_state.modalidades)}")
    
    # Tabs principais
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "➕ Cadastrar Risco", "⚙️ Modalidades", "📋 Relatórios", "📜 Logs"])
    
    with tab1:
        st.header("Dashboard de Riscos")
        
        if not st.session_state.nome_projeto:
            st.warning("⚠️ Por favor, defina o nome do projeto na barra lateral antes de continuar.")
        
        if len(st.session_state.riscos) == 0:
            st.info("Nenhum risco cadastrado ainda. Use a aba 'Cadastrar Risco' para começar.")
        else:
            # Métricas principais
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
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de pizza - Distribuição por classificação
                classificacoes = [r['classificacao'] for r in st.session_state.riscos]
                df_class = pd.DataFrame({'Classificação': classificacoes})
                fig_pie = px.pie(df_class, names='Classificação', 
                               title="Distribuição dos Riscos por Classificação",
                               color_discrete_map={'Alto': '#dc3545', 'Médio': '#ffc107', 'Baixo': '#28a745'})
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Gráfico de barras - Riscos por valor
                nomes_riscos = [r['nome'] for r in st.session_state.riscos]
                valores_riscos = [r['risco_inerente'] for r in st.session_state.riscos]
                cores_riscos = [classificar_risco(v)[1] for v in valores_riscos]
                
                fig_bar = go.Figure(data=[go.Bar(x=nomes_riscos, y=valores_riscos, 
                                               marker_color=cores_riscos)])
                fig_bar.update_layout(title="Valor dos Riscos Inerentes",
                                    xaxis_title="Riscos",
                                    yaxis_title="Valor do Risco")
                fig_bar.update_xaxis(tickangle=45)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Análise comparativa por modalidades
            if len(st.session_state.modalidades) > 0:
                st.subheader("Análise Comparativa por Modalidades")
                
                # Calcular risco acumulado por modalidade
                risco_acumulado_por_modalidade = {}
                for modalidade in st.session_state.modalidades:
                    risco_residual_total = 0
                    for risco in st.session_state.riscos:
                        if modalidade in risco['modalidades']:
                            fator_mitigacao = risco['modalidades'][modalidade]
                            risco_residual = risco['risco_inerente'] * fator_mitigacao
                            risco_residual_total += risco_residual
                    risco_acumulado_por_modalidade[modalidade] = risco_residual_total
                
                # Gráfico de barras comparativo
                modalidades_nomes = list(risco_acumulado_por_modalidade.keys())
                modalidades_valores = list(risco_acumulado_por_modalidade.values())
                
                fig_comp = go.Figure(data=[go.Bar(x=modalidades_nomes, y=modalidades_valores,
                                                marker_color='lightblue')])
                fig_comp.update_layout(title="Risco Residual Acumulado por Modalidade",
                                     xaxis_title="Modalidades",
                                     yaxis_title="Risco Residual Acumulado")
                fig_comp.update_xaxis(tickangle=45)
                st.plotly_chart(fig_comp, use_container_width=True)
                
                # Ranking das modalidades
                modalidades_ordenadas = sorted(risco_acumulado_por_modalidade.items(), 
                                             key=lambda x: x[1])
                
                st.subheader("Ranking das Modalidades (Menor Risco = Melhor)")
                for i, (modalidade, valor) in enumerate(modalidades_ordenadas, 1):
                    if i == 1:
                        st.success(f"🥇 {i}º lugar: {modalidade} (Risco: {valor:.2f})")
                    elif i == 2:
                        st.info(f"🥈 {i}º lugar: {modalidade} (Risco: {valor:.2f})")
                    elif i == 3:
                        st.warning(f"🥉 {i}º lugar: {modalidade} (Risco: {valor:.2f})")
                    else:
                        st.text(f"{i}º lugar: {modalidade} (Risco: {valor:.2f})")
            
            # Tabela detalhada dos riscos
            st.subheader("Detalhamento dos Riscos")
            
            df_riscos = pd.DataFrame([
                {
                    'Nome': r['nome'],
                    'Impacto': r['impacto'],
                    'Probabilidade': r['probabilidade'],
                    'Risco Inerente': r['risco_inerente'],
                    'Classificação': r['classificacao']
                }
                for r in st.session_state.riscos
            ])
            
            st.dataframe(df_riscos, use_container_width=True)
    
    with tab2:
        st.header("Cadastrar Novo Risco")
        
        if not st.session_state.nome_projeto:
            st.warning("⚠️ Por favor, defina o nome do projeto na barra lateral antes de cadastrar riscos.")
        else:
            with st.form("cadastro_risco"):
                nome_risco = st.text_input("Nome do Risco")
                
                col1, col2 = st.columns(2)
                with col1:
                    impacto = st.selectbox("Impacto", list(ESCALAS_IMPACTO.keys()))
                    st.caption(ESCALAS_IMPACTO[impacto]['descricao'])
                
                with col2:
                    probabilidade = st.selectbox("Probabilidade", list(ESCALAS_PROBABILIDADE.keys()))
                    st.caption(ESCALAS_PROBABILIDADE[probabilidade]['descricao'])
                
                # Mostrar aspectos a considerar se o risco estiver na base
                if nome_risco in ASPECTOS_RISCOS:
                    st.subheader("Aspectos a Considerar na Avaliação")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Aspectos de Impacto:**")
                        for aspecto in ASPECTOS_RISCOS[nome_risco]['impacto']:
                            st.markdown(f"• {aspecto}")
                    
                    with col2:
                        st.markdown("**Aspectos de Probabilidade:**")
                        for aspecto in ASPECTOS_RISCOS[nome_risco]['probabilidade']:
                            st.markdown(f"• {aspecto}")
                
                st.subheader("Fatores de Mitigação por Modalidade")
                st.caption("Valores entre 0.1 (alta mitigação) e 1.0 (sem mitigação)")
                
                fatores_mitigacao = {}
                for modalidade in st.session_state.modalidades:
                    fator = st.slider(f"{modalidade}", 0.1, 1.0, 0.5, 0.1)
                    fatores_mitigacao[modalidade] = fator
                
                submit_risco = st.form_submit_button("Cadastrar Risco")
                
                if submit_risco:
                    if nome_risco:
                        valor_impacto = ESCALAS_IMPACTO[impacto]['valor']
                        valor_probabilidade = ESCALAS_PROBABILIDADE[probabilidade]['valor']
                        risco_inerente = valor_impacto * valor_probabilidade
                        classificacao, cor = classificar_risco(risco_inerente)
                        
                        novo_risco = {
                            'nome': nome_risco,
                            'impacto': impacto,
                            'probabilidade': probabilidade,
                            'risco_inerente': risco_inerente,
                            'classificacao': classificacao,
                            'modalidades': fatores_mitigacao.copy()
                        }
                        
                        st.session_state.riscos.append(novo_risco)
                        
                        registrar_acao(st.session_state.user, "Risco cadastrado", {
                            'nome_risco': nome_risco,
                            'classificacao': classificacao,
                            'risco_inerente': risco_inerente
                        })
                        
                        st.success(f"Risco '{nome_risco}' cadastrado com sucesso!")
                        st.success(f"Classificação: {classificacao} (Valor: {risco_inerente:.2f})")
                        st.rerun()
                    else:
                        st.error("Por favor, preencha o nome do risco.")
    
    with tab3:
        st.header("Gerenciar Modalidades de Contratação")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Modalidades Atuais")
            for i, modalidade in enumerate(st.session_state.modalidades):
                col_nome, col_acao = st.columns([3, 1])
                with col_nome:
                    st.text(f"{i+1}. {modalidade}")
                with col_acao:
                    if st.button(f"Remover", key=f"remove_{i}"):
                        st.session_state.modalidades.remove(modalidade)
                        registrar_acao(st.session_state.user, "Modalidade removida", {'modalidade': modalidade})
                        st.rerun()
        
        with col2:
            st.subheader("Adicionar Nova Modalidade")
            with st.form("nova_modalidade"):
                nova_modalidade = st.text_input("Nome da Modalidade")
                submit_modalidade = st.form_submit_button("Adicionar")
                
                if submit_modalidade:
                    if nova_modalidade and nova_modalidade not in st.session_state.modalidades:
                        st.session_state.modalidades.append(nova_modalidade)
                        registrar_acao(st.session_state.user, "Modalidade adicionada", {'modalidade': nova_modalidade})
                        st.success(f"Modalidade '{nova_modalidade}' adicionada!")
                        st.rerun()
                    elif nova_modalidade in st.session_state.modalidades:
                        st.error("Modalidade já existe!")
                    else:
                        st.error("Por favor, digite o nome da modalidade.")
        
        if st.button("Restaurar Modalidades Padrão"):
            st.session_state.modalidades = MODALIDADES_PADRAO.copy()
            registrar_acao(st.session_state.user, "Modalidades restauradas para padrão")
            st.success("Modalidades restauradas para o padrão!")
            st.rerun()
    
    with tab4:
        st.header("Relatórios")
        
        if not st.session_state.nome_projeto:
            st.error("⚠️ É obrigatório definir o nome do projeto antes de gerar relatórios!")
        elif len(st.session_state.riscos) == 0:
            st.warning("Nenhum risco cadastrado. Cadastre pelo menos um risco para gerar relatórios.")
        else:
            st.success(f"✅ Projeto: **{st.session_state.nome_projeto}**")
            
            # Seção de identificação do responsável
            st.subheader("Identificação do Responsável pela Análise")
            
            with st.form("identificacao_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    nome_responsavel = st.text_input("Nome Completo", 
                                                   value=st.session_state.identificacao_relatorio['nome'] if st.session_state.identificacao_relatorio else st.session_state.user)
                    divisao = st.text_input("Divisão/Setor", 
                                          value=st.session_state.identificacao_relatorio['divisao'] if st.session_state.identificacao_relatorio else "")
                
                with col2:
                    orgao = st.text_input("Órgão", 
                                        value=st.session_state.identificacao_relatorio['orgao'] if st.session_state.identificacao_relatorio else "SPU")
                    email = st.text_input("E-mail", 
                                        value=st.session_state.identificacao_relatorio['email'] if st.session_state.identificacao_relatorio else "")
                
                if st.form_submit_button("Salvar Identificação"):
                    st.session_state.identificacao_relatorio = {
                        'nome': nome_responsavel,
                        'divisao': divisao,
                        'orgao': orgao,
                        'email': email
                    }
                    st.success("Identificação salva com sucesso!")
            
            st.markdown("---")
            
            # Botões de relatório
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Gerar Relatório Word", type="primary"):
                    with st.spinner("Gerando relatório..."):
                        doc_io = gerar_relatorio_word()
                        if doc_io:
                            registrar_acao(st.session_state.user, "Relatório Word gerado", {
                                'projeto': st.session_state.nome_projeto,
                                'total_riscos': len(st.session_state.riscos)
                            })
                            
                            st.success("Relatório gerado com sucesso!")
                            
                            # Botão de download
                            st.download_button(
                                label="📥 Baixar Relatório Word",
                                data=doc_io.getvalue(),
                                file_name=f"Relatorio_Riscos_{st.session_state.nome_projeto.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
            
            with col2:
                if st.button("📊 Gerar Relatório CSV"):
                    # Criar DataFrame para CSV
                    dados_csv = []
                    for risco in st.session_state.riscos:
                        linha_base = {
                            'Projeto': st.session_state.nome_projeto,
                            'Risco': risco['nome'],
                            'Impacto': risco['impacto'],
                            'Probabilidade': risco['probabilidade'],
                            'Risco_Inerente': risco['risco_inerente'],
                            'Classificacao': risco['classificacao']
                        }
                        
                        # Adicionar dados por modalidade
                        for modalidade in st.session_state.modalidades:
                            if modalidade in risco['modalidades']:
                                linha = linha_base.copy()
                                linha['Modalidade'] = modalidade
                                linha['Fator_Mitigacao'] = risco['modalidades'][modalidade]
                                linha['Risco_Residual'] = risco['risco_inerente'] * risco['modalidades'][modalidade]
                                dados_csv.append(linha)
                    
                    df_csv = pd.DataFrame(dados_csv)
                    csv_data = df_csv.to_csv(index=False)
                    
                    registrar_acao(st.session_state.user, "Relatório CSV gerado", {
                        'projeto': st.session_state.nome_projeto,
                        'total_riscos': len(st.session_state.riscos)
                    })
                    
                    st.download_button(
                        label="📥 Baixar Relatório CSV",
                        data=csv_data,
                        file_name=f"Relatorio_Riscos_{st.session_state.nome_projeto.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
            
            # Preview do relatório
            st.subheader("Preview do Relatório")
            
            total_riscos = len(st.session_state.riscos)
            riscos_altos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Alto')
            riscos_medios = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Médio')
            riscos_baixos = sum(1 for r in st.session_state.riscos if r['classificacao'] == 'Baixo')
            
            st.markdown(f"""
            **Projeto:** {st.session_state.nome_projeto}
            
            **Resumo da Análise:**
            - Total de riscos analisados: {total_riscos}
            - Riscos de nível alto: {riscos_altos} ({riscos_altos/total_riscos*100:.1f}%)
            - Riscos de nível médio: {riscos_medios} ({riscos_medios/total_riscos*100:.1f}%)
            - Riscos de nível baixo: {riscos_baixos} ({riscos_baixos/total_riscos*100:.1f}%)
            
            **Modalidades analisadas:** {len(st.session_state.modalidades)}
            """)
    
    with tab5:
        st.header("Logs do Sistema")
        
        logs = obter_logs()
        
        if logs:
            df_logs = pd.DataFrame(logs, columns=['Timestamp', 'Usuário', 'Ação', 'Detalhes'])
            
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                usuario_filtro = st.selectbox("Filtrar por usuário", 
                                            ["Todos"] + list(set([log[1] for log in logs])))
            with col2:
                acao_filtro = st.selectbox("Filtrar por ação", 
                                         ["Todas"] + list(set([log[2] for log in logs])))
            
            # Aplicar filtros
            df_filtrado = df_logs.copy()
            if usuario_filtro != "Todos":
                df_filtrado = df_filtrado[df_filtrado['Usuário'] == usuario_filtro]
            if acao_filtro != "Todas":
                df_filtrado = df_filtrado[df_filtrado['Ação'] == acao_filtro]
            
            st.dataframe(df_filtrado, use_container_width=True)
            
            # Estatísticas dos logs
            st.subheader("Estatísticas")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de Ações", len(logs))
            with col2:
                st.metric("Usuários Ativos", len(set([log[1] for log in logs])))
            with col3:
                st.metric("Tipos de Ação", len(set([log[2] for log in logs])))
        else:
            st.info("Nenhum log encontrado.")

