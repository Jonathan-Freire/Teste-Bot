# app/agentes/agente_roteador.py
"""
Módulo responsável por interpretar a intenção do usuário.

Este agente utiliza um modelo de linguagem (LLM) para analisar a entrada de texto
do usuário e extrair uma intenção estruturada, juntamente com as entidades 
relevantes (como nome de produto, ID de pedido, etc.). O resultado é retornado
em um objeto Pydantic para uso em outras partes do sistema.
"""

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models.ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Define os tipos de intenção possíveis para melhorar a checagem estática
TipoIntencao = Literal[
    "buscar_produtos_classificados",
    "buscar_detalhes_produto",
    "listar_registros_vendas",
    "obter_itens_pedido",
    "desconhecido",
]

class IntencaoConsulta(BaseModel):
    """
    Representa a intenção e as entidades extraídas da pergunta do usuário.

    Atributos:
        intencao: A ação principal que o usuário deseja realizar.
        marca: A marca do produto mencionada.
        nome_produto: O nome específico de um produto.
        nome_cliente: O nome ou parte do nome de um cliente.
        codigo_cliente: O código numérico de um cliente.
        id_pedido: O número de um pedido de venda.
        criterio_classificacao: Critério de ordenação como 'mais_vendidos'.
        limite: O número de resultados a serem retornados (ex: 'top 5' -> 5).
        periodo_tempo: Período de tempo como 'hoje', 'este_mes'.
    """
    intencao: TipoIntencao = Field(
        description="A intenção principal extraída da consulta. Opções: ['buscar_produtos_classificados', 'buscar_detalhes_produto', 'listar_registros_vendas', 'obter_itens_pedido', 'desconhecido']"
    )
    marca: Optional[str] = Field(default=None, description="A marca do produto mencionada na consulta.")
    nome_produto: Optional[str] = Field(default=None, description="O nome específico de um produto.")
    nome_cliente: Optional[str] = Field(default=None, description="O nome ou parte do nome de um cliente.")
    codigo_cliente: Optional[int] = Field(default=None, description="O código numérico de um cliente.")
    id_pedido: Optional[int] = Field(default=None, description="O número de um pedido de venda.")
    criterio_classificacao: Optional[str] = Field(default=None, description="Critério de ordenação como 'mais vendidos' ou 'mais caros'. Mapear para: ['mais_vendidos', 'mais_caros', etc.]")
    limite: Optional[int] = Field(default=None, description="O número de resultados a serem retornados (ex: 'top 5' -> 5).")
    periodo_tempo: Optional[str] = Field(default=None, description="Período de tempo como 'hoje', 'este mês'. Mapear para: ['hoje', 'este_mes', etc.]")


# Cria um parser JSON que utiliza o modelo Pydantic para validar a saída.
parser_json = JsonOutputParser(pydantic_object=IntencaoConsulta)

# Template do prompt para o LLM, com instruções claras e exemplos.
template_prompt = """
Você é um robô de extração de dados altamente preciso e eficiente. Sua única função é analisar o texto do usuário e retornar um objeto JSON bem formatado, sem nenhuma explicação ou texto adicional. Sua resposta deve ser APENAS o objeto JSON.

{instrucoes_formato}

Analise o texto do usuário abaixo e gere o objeto JSON correspondente, seguindo estritamente as regras e os exemplos fornecidos.

--- REGRAS DE EXTRAÇÃO CRÍTICAS ---
1.  **buscar_produtos_classificados**: Use para perguntas sobre performance de produtos. Ex: "top 5 mais vendidos".
2.  **listar_registros_vendas**: Use para listar pedidos de um cliente. Ex: "pedidos do cliente 1234".
3.  **obter_itens_pedido**: Use quando o usuário pedir os itens, produtos ou detalhes de um pedido específico. Ex: "o que tem no pedido 5678?".
4.  **buscar_detalhes_produto**: Use para buscar informações de um produto específico. Ex: "qual o preço do produto Y?".
5.  Se um número estiver próximo a "pedido", "nota", "venda", extraia como `id_pedido`.
6.  Se um número estiver próximo a "cliente", "código", extraia como `codigo_cliente`.
7.  Se um período de tempo não for mencionado, o padrão para `periodo_tempo` é "sempre".
8.  Se um limite numérico não for mencionado, o padrão para `limite` é 10.

--- EXEMPLOS ---
Texto do usuário: "quais os 5 produtos mais vendidos este mês?"
JSON: {{"intencao": "buscar_produtos_classificados", "criterio_classificacao": "mais_vendidos", "limite": 5, "periodo_tempo": "este_mes"}}

Texto do usuário: "me mostra os itens do pedido 98765"
JSON: {{"intencao": "obter_itens_pedido", "id_pedido": 98765}}

Texto do usuário: "quais os pedidos do cliente Comercial Esperança?"
JSON: {{"intencao": "listar_registros_vendas", "nome_cliente": "Comercial Esperança"}}

Texto do usuário: "cliente 456"
JSON: {{"intencao": "listar_registros_vendas", "codigo_cliente": 456}}

Texto do usuário: "qual o preço do produto 'ARROZ TIPO 1'?"
JSON: {{"intencao": "buscar_detalhes_produto", "nome_produto": "ARROZ TIPO 1"}}
---

Texto do usuário a ser analisado:
"{entrada_usuario}"
"""

# Cria o prompt a partir do template, inserindo as instruções de formato do parser.
prompt = ChatPromptTemplate.from_template(
    template=template_prompt,
    partial_variables={"instrucoes_formato": parser_json.get_format_instructions()}
)

async def obter_intencao(llm: ChatOllama, entrada_usuario: str) -> IntencaoConsulta:
    """
    Processa a entrada do usuário para extrair a intenção e as entidades.

    Args:
        llm: A instância do modelo de linguagem (ChatOllama) a ser usada.
        entrada_usuario: O texto da pergunta feita pelo usuário.

    Returns:
        Um objeto IntencaoConsulta contendo os dados estruturados extraídos.
        Caso ocorra um erro ou a intenção não seja identificada, retorna um
        objeto com a intenção 'desconhecido'.
    """
    logger.info("Iniciando roteamento de intenção do usuário.")
    
    # Constrói a cadeia de processamento: prompt -> llm -> parser
    cadeia_processamento = prompt | llm | parser_json
    
    try:
        logger.debug(f"Enviando para o LLM para extração: '{entrada_usuario}'")
        resultado_dict = await cadeia_processamento.ainvoke({"entrada_usuario": entrada_usuario})
        logger.info(f"Dicionário extraído com sucesso: {resultado_dict}")
        
        # Valida e cria o objeto Pydantic a partir do dicionário retornado
        return IntencaoConsulta(**(resultado_dict or {}))
        
    except Exception as e:
        logger.error(f"Erro ao extrair intenção com o parser JSON: {e}", exc_info=True)
        # Retorna um objeto padrão em caso de falha na extração ou validação
        return IntencaoConsulta(intencao="desconhecido")
