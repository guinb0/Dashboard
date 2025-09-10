# Dashboard de Avaliação de Riscos

Este projeto implementa um Dashboard interativo para avaliação e gestão de riscos, com foco na metodologia SAROI (Sistema de Análise de Riscos em Operações Imobiliárias). A ferramenta permite aos usuários cadastrar, editar, analisar e comparar riscos, além de gerar relatórios detalhados e manter um log de atividades.

## Metodologia

A metodologia central utilizada neste dashboard é baseada no **SAROI (Sistema de Análise de Riscos em Operações Imobiliárias)**. Esta abordagem é aplicada para:

- **Avaliação de Impacto e Probabilidade:** Utiliza escalas predefinidas (Muito baixo, Baixo, Médio, Alto, Muito alto) para quantificar o impacto e a probabilidade de cada risco, permitindo o cálculo do Risco Inerente (Impacto x Probabilidade).
- **Classificação de Riscos:** Os riscos são classificados em categorias (Baixo, Médio, Alto) com base no seu valor inerente.
- **Análise de Mitigação por Modalidade:** A ferramenta permite associar fatores de mitigação a diferentes modalidades de contratação (e.g., Permuta por imóvel, Build to Suit, Obra pública convencional). Isso possibilita calcular o Risco Residual para cada risco sob diferentes cenários de mitigação.
- **Comparação de Modalidades:** O dashboard oferece uma análise comparativa das modalidades de contratação, calculando o risco residual acumulado e a eficácia de mitigação para cada uma, auxiliando na identificação da modalidade mais vantajosa.
- **Geração de Relatórios:** Um relatório executivo completo em formato Word é gerado, consolidando a análise de riscos, a comparação de modalidades e as recomendações, seguindo a estrutura e os preceitos do SAROI.
- **Gestão de Usuários e Logs:** O sistema inclui um módulo de autenticação de usuários e um log de ações para rastrear as modificações e interações com a ferramenta, garantindo rastreabilidade e governança.

## Bibliotecas Utilizadas

O projeto faz uso das seguintes bibliotecas Python para construir a aplicação e suas funcionalidades:

- **`streamlit`**: Utilizado para a construção da interface web interativa do dashboard, permitindo a criação de uma aplicação rica e responsiva com pouco código.
- **`pandas`**: Essencial para a manipulação e análise de dados, especialmente para a organização e processamento dos dados de riscos e modalidades em DataFrames.
- **`plotly.express` e `plotly.graph_objects`**: Empregadas para a criação de visualizações de dados interativas e dinâmicas, como gráficos de pizza, dispersão, barras e heatmaps, que facilitam a compreensão dos dados de risco.
- **`numpy`**: Utilizada para operações numéricas eficientes, como cálculos de médias e manipulação de arrays, que são fundamentais para as análises quantitativas de risco.
- **`datetime`**: Usada para lidar com operações de data e hora, como o registro de timestamps nos logs de atividades e a data de edição dos riscos.
- **`sqlite3`**: Fornece a interface para interagir com o banco de dados SQLite, utilizado para armazenar informações de usuários e logs de ações de forma persistente.
- **`hashlib`**: Empregada para a geração de hashes de senhas, garantindo a segurança das credenciais dos usuários.
- **`json`**: Utilizada para serializar e desserializar dados em formato JSON, especialmente para armazenar detalhes complexos nos logs de atividades.
- **`os`**: Uma biblioteca padrão do Python para interações com o sistema operacional, útil para manipulação de caminhos de arquivo e outras operações de sistema.
- **`io.BytesIO`**: Permite a manipulação de dados em memória como se fossem arquivos, sendo crucial para a geração e o download do relatório Word diretamente da aplicação.
- **`python-docx` (via `docx` import)**: Biblioteca poderosa para a criação e modificação de arquivos Microsoft Word (.docx). É utilizada para gerar o relatório executivo detalhado com base nos dados e análises do dashboard.

Essas bibliotecas, em conjunto, fornecem a base para um sistema robusto de avaliação de riscos, combinando uma interface de usuário amigável com capacidades analíticas e de geração de relatórios avançadas.

