# app/agentes/agente_roteador.py
"""
Módulo responsável por interpretar a intenção do usuário.

Versão 2.0: Totalmente expandido para cobrir uma vasta gama de consultas de negócio,
incluindo detalhes de clientes, produtos e pedidos. A estrutura de intenções foi
ampliada para transformar o bot em uma ferramenta de análise de dados conversacional
completa, mantendo a capacidade de solicitar esclarecimentos quando necessário.
"""

import logging
from typing import Literal, Optional, Dict, Any

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models.ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Tipos de intenção expandidos para cobrir novas funcionalidades de negócio
TipoIntencao = Literal[
    # Intenções Originais
    "buscar_produtos_classificados",
    "listar_registros_vendas",
    "obter_itens_pedido",
    
    # Novas Intenções - Clientes
    "consultar_limite_credito",
    "verificar_status_cliente",
    "buscar_dados_contato_cliente",
    "buscar_endereco_cliente",
    "listar_clientes_por_cidade",
    "listar_clientes_recentes",

    # Novas Intenções - Produtos
    "buscar_detalhes_produto", # Intenção original melhorada
    "listar_produtos_por_marca",
    "listar_produtos_descontinuados",

    # Novas Intenções - Pedidos
    "verificar_posicao_pedido",
    "consultar_valor_pedido",
    "consultar_data_entrega_pedido",
    "listar_pedidos_por_posicao",

    # Intenções de Controle
    "necessita_esclarecimento",
    "desconhecido",
]

class IntencaoConsulta(BaseModel):
    """
    Representa a intenção e as entidades extraídas da pergunta do usuário.
    """
    intencao: TipoIntencao = Field(description="A intenção principal extraída da consulta.")
    entidades: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dicionário flexível para armazenar todas as entidades extraídas."
    )
    mensagem_esclarecimento: Optional[str] = Field(
        default=None,
        description="Mensagem para o usuário se a intenção for 'necessita_esclarecimento'."
    )

# Parser JSON que utiliza o modelo Pydantic.
parser_json = JsonOutputParser(pydantic_object=IntencaoConsulta)

# Template do prompt massivamente expandido com novas regras e exemplos.
template_prompt = """
Você é um especialista em análise de linguagem natural para um sistema de vendas da Comercial Esperança. Sua função é interpretar a pergunta do usuário e extrair a intenção e as entidades relevantes em um formato JSON. Responda APENAS com o JSON.

{instrucoes_formato}

--- REGRAS DE EXTRAÇÃO ---
1.  **Intenções de Cliente**:
    - `consultar_limite_credito`: Para perguntas sobre o limite de crédito. Requer `nome_cliente` ou `codigo_cliente`.
    - `verificar_status_cliente`: Para saber se um cliente está ativo ou bloqueado. Requer `nome_cliente` ou `codigo_cliente`.
    - `buscar_dados_contato_cliente`: Para telefone ou email. Requer `nome_cliente` ou `codigo_cliente`.
    - `buscar_endereco_cliente`: Para endereço de entrega. Requer `nome_cliente` ou `codigo_cliente`.
    - `listar_clientes_por_cidade`: Para listar clientes de uma cidade específica. Requer `cidade`.
    - `listar_clientes_recentes`: Para clientes cadastrados recentemente. Requer `periodo_tempo`.

2.  **Intenções de Produto**:
    - `buscar_produtos_classificados`: Para rankings (mais vendidos, etc.). Requer `criterio_classificacao`.
    - `buscar_detalhes_produto`: Para informações gerais de um produto (peso, marca, fornecedor). Requer `nome_produto` ou `codigo_produto`.
    - `listar_produtos_por_marca`: Para listar produtos de uma marca. Requer `marca`.
    - `listar_produtos_descontinuados`: Para produtos com data de exclusão.

3.  **Intenções de Pedido**:
    - `listar_registros_vendas`: Para listar todos os pedidos de um cliente. Requer `nome_cliente` ou `codigo_cliente`.
    - `obter_itens_pedido`: Para ver os itens de um pedido. Requer `id_pedido`.
    - `verificar_posicao_pedido`: Para saber o status (Liberado, Bloqueado, etc.) de um pedido. Requer `id_pedido`.
    - `consultar_valor_pedido`: Para o valor total de um pedido. Requer `id_pedido`.
    - `consultar_data_entrega_pedido`: Para a data de entrega prevista. Requer `id_pedido`.
    - `listar_pedidos_por_posicao`: Para listar pedidos com um status específico. Requer `posicao`.

4.  **Regras Gerais**:
    - **necessita_esclarecimento**: Se a intenção for clara, mas faltar uma entidade OBRIGATÓRIA, use esta intenção e formule uma pergunta em `mensagem_esclarecimento`.
    - **desconhecido**: Se não entender o pedido.
    - **Padrões**: `limite` padrão é 10. `periodo_tempo` padrão é 'sempre'.

--- EXEMPLOS ---
- Texto: "qual o limite de crédito do cliente 123?"
  JSON: {{"intencao": "consultar_limite_credito", "entidades": {{"codigo_cliente": 123}}}}

- Texto: "o cliente Comercial Esperança está ativo?"
  JSON: {{"intencao": "verificar_status_cliente", "entidades": {{"nome_cliente": "Comercial Esperança"}}}}

- Texto: "qual o endereço de entrega do cliente 456"
  JSON: {{"intencao": "buscar_endereco_cliente", "entidades": {{"codigo_cliente": 456}}}}

- Texto: "me liste os clientes de Bauru"
  JSON: {{"intencao": "listar_clientes_por_cidade", "entidades": {{"cidade": "Bauru"}}}}

- Texto: "qual o peso do produto ARROZ TIPO 1?"
  JSON: {{"intencao": "buscar_detalhes_produto", "entidades": {{"nome_produto": "ARROZ TIPO 1"}}}}

- Texto: "qual a posição do pedido 98765?"
  JSON: {{"intencao": "verificar_posicao_pedido", "entidades": {{"id_pedido": 98765}}}}

- Texto: "me mostre os pedidos bloqueados"
  JSON: {{"intencao": "listar_pedidos_por_posicao", "entidades": {{"posicao": "B"}}}}

- Texto: "quero ver os pedidos"
  JSON: {{"intencao": "necessita_esclarecimento", "entidades": {{}}, "mensagem_esclarecimento": "De qual cliente você gostaria de ver os pedidos? Por favor, informe o nome ou código."}}
---

Analise o texto do usuário:
"{entrada_usuario}"
"""

prompt = ChatPromptTemplate.from_template(
    template=template_prompt,
    partial_variables={"instrucoes_formato": parser_json.get_format_instructions()}
)

async def obter_intencao(llm: ChatOllama, entrada_usuario: str) -> IntencaoConsulta:
    """
    Processa a entrada do usuário para extrair a intenção e as entidades.
    """
    logger.info("Iniciando roteamento de intenção do usuário.")
    cadeia_processamento = prompt | llm | parser_json
    
    try:
        logger.debug(f"Enviando para o LLM para extração: '{entrada_usuario}'")
        resultado_dict = await cadeia_processamento.ainvoke({"entrada_usuario": entrada_usuario})
        logger.info(f"Dicionário extraído com sucesso: {resultado_dict}")
        return IntencaoConsulta(**(resultado_dict or {}))
    except Exception as e:
        logger.error(f"Erro ao extrair intenção com o parser JSON: {e}", exc_info=True)
        return IntencaoConsulta(intencao="desconhecido")
