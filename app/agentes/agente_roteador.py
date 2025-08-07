
import logging
from typing import Literal, Optional, Dict, Any

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
# CORREÇÃO: Importação atualizada para langchain-ollama
from langchain_ollama import OllamaLLM
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
    "buscar_clientes_classificados",

    # Novas Intenções - Produtos
    "buscar_detalhes_produto", 
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

# Definir quais intenções OBRIGATORIAMENTE precisam de período de tempo
INTENCOES_QUE_PRECISAM_PERIODO = {
    "buscar_produtos_classificados",
    "buscar_clientes_classificados", 
    "listar_registros_vendas"
}

class IntencaoConsulta(BaseModel):
    """
    Representa a intenção e as entidades extraídas da pergunta do usuário.
    
    Attributes:
        intencao: A intenção principal identificada na consulta do usuário.
        entidades: Dicionário com as entidades extraídas (nomes, códigos, períodos, etc).
        mensagem_esclarecimento: Mensagem a ser exibida quando necessário esclarecimento.
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

# Template do prompt expandido com regras rígidas sobre períodos de tempo.
template_prompt = """
Você é um especialista em análise de linguagem natural para um sistema de vendas da Comercial Esperança. Sua função é interpretar a pergunta do usuário e extrair a intenção e as entidades relevantes em um formato JSON. Responda APENAS com o JSON.

{instrucoes_formato}

--- REGRAS CRÍTICAS SOBRE PERÍODO DE TEMPO ---
**ATENÇÃO**: Para evitar sobrecarga no banco de dados, certas consultas OBRIGATORIAMENTE precisam de um período específico:

**CONSULTAS QUE EXIGEM PERÍODO OBRIGATÓRIO:**
- `buscar_produtos_classificados` (rankings de produtos)
- `buscar_clientes_classificados` (rankings de clientes)  
- `listar_registros_vendas` (histórico de vendas)

**PERÍODOS VÁLIDOS:**
- 'hoje', 'este_mes', 'ultimo_mes', 'esta_semana', 'mes_passado'
- Se o usuário não especificar período para essas consultas, use OBRIGATORIAMENTE `necessita_esclarecimento`

**REGRA DE OURO**: NUNCA extraia `periodo_tempo` como 'sempre' ou deixe vazio para as intenções listadas acima.

--- REGRAS DE EXTRAÇÃO ---
1.  **Intenções de Cliente**:
    - `consultar_limite_credito`: Para perguntas sobre o limite de crédito. Requer `nome_cliente` ou `codigo_cliente`.
    - `verificar_status_cliente`: Para saber se um cliente está ativo ou bloqueado. Requer `nome_cliente` ou `codigo_cliente`.
    - `buscar_dados_contato_cliente`: Para telefone ou email. Requer `nome_cliente` ou `codigo_cliente`.
    - `buscar_endereco_cliente`: Para endereço de entrega. Requer `nome_cliente` ou `codigo_cliente`.
    - `listar_clientes_por_cidade`: Para listar clientes de uma cidade específica. Requer `cidade`.
    - `listar_clientes_recentes`: Para clientes cadastrados recentemente. Requer `periodo_tempo`.
    - `buscar_clientes_classificados`: **REQUER PERÍODO OBRIGATÓRIO**. Para rankings de clientes. Requer `criterio_classificacao` (só aceita 'maior_valor_compras') E `periodo_tempo` válido.

2.  **Intenções de Produto**:
    - `buscar_produtos_classificados`: **REQUER PERÍODO OBRIGATÓRIO**. Para rankings de produtos. Requer `criterio_classificacao` ('mais_vendidos' ou 'menos_vendidos') E `periodo_tempo` válido.
    - `buscar_detalhes_produto`: Para informações gerais de um produto. Requer `nome_produto` ou `codigo_produto`.
    - `listar_produtos_por_marca`: Para listar produtos de uma marca. Requer `marca`.
    - `listar_produtos_descontinuados`: Para produtos com data de exclusão.

3.  **Intenções de Pedido**:
    - `listar_registros_vendas`: **REQUER PERÍODO OBRIGATÓRIO**. Para listar pedidos de um cliente. Requer `nome_cliente` ou `codigo_cliente` E `periodo_tempo` válido.
    - `obter_itens_pedido`: Para ver os itens de um pedido. Requer `id_pedido`.
    - `verificar_posicao_pedido`: Para saber o status de um pedido. Requer `id_pedido`.
    - `consultar_valor_pedido`: Para o valor total de um pedido. Requer `id_pedido`.
    - `consultar_data_entrega_pedido`: Para a data de entrega prevista. Requer `id_pedido`.
    - `listar_pedidos_por_posicao`: Para listar pedidos com um status específico. Requer `posicao`.

4.  **Regras Gerais**:
    - **necessita_esclarecimento**: Use quando a intenção for clara, mas faltar uma entidade OBRIGATÓRIA (incluindo período quando necessário).
    - **desconhecido**: Se não entender o pedido.
    - **Padrões**: `limite` padrão é 10.

--- EXEMPLOS COM VALIDAÇÃO DE PERÍODO ---
- Texto: "quais os 5 produtos mais vendidos?"
  JSON: {{"intencao": "necessita_esclarecimento", "entidades": {{}}, "mensagem_esclarecimento": "Para consultar os produtos mais vendidos, preciso saber o período. Você quer ver os dados de hoje, este mês, último mês ou outro período específico?"}}

- Texto: "quais os produtos mais vendidos este mês?"
  JSON: {{"intencao": "buscar_produtos_classificados", "entidades": {{"criterio_classificacao": "mais_vendidos", "periodo_tempo": "este_mes", "limite": 10}}}}

- Texto: "top 5 clientes que mais gastaram"
  JSON: {{"intencao": "necessita_esclarecimento", "entidades": {{}}, "mensagem_esclarecimento": "Para consultar os clientes que mais gastaram, preciso saber o período. Você quer ver os dados de hoje, este mês, último mês ou outro período específico?"}}

- Texto: "clientes que mais compraram no último mês"
  JSON: {{"intencao": "buscar_clientes_classificados", "entidades": {{"criterio_classificacao": "maior_valor_compras", "periodo_tempo": "ultimo_mes", "limite": 10}}}}

- Texto: "pedidos do cliente João"
  JSON: {{"intencao": "necessita_esclarecimento", "entidades": {{}}, "mensagem_esclarecimento": "Para consultar os pedidos do cliente João, preciso saber o período. Você quer ver os pedidos de hoje, este mês, último mês ou outro período específico?"}}

- Texto: "pedidos do cliente João este mês"
  JSON: {{"intencao": "listar_registros_vendas", "entidades": {{"nome_cliente": "João", "periodo_tempo": "este_mes"}}}}

- Texto: "qual o limite de crédito do cliente 123?"
  JSON: {{"intencao": "consultar_limite_credito", "entidades": {{"codigo_cliente": 123}}}}

- Texto: "qual a posição do pedido 98765?"
  JSON: {{"intencao": "verificar_posicao_pedido", "entidades": {{"id_pedido": 98765}}}}
---

Analise o texto do usuário:
"{entrada_usuario}"
"""

prompt = ChatPromptTemplate.from_template(
    template=template_prompt,
    partial_variables={"instrucoes_formato": parser_json.get_format_instructions()}
)

async def obter_intencao(llm: OllamaLLM, entrada_usuario: str) -> IntencaoConsulta:
    """
    Processa a entrada do usuário para extrair a intenção e as entidades.
    
    Args:
        llm: Instância do modelo OllamaLLM para processamento de linguagem natural.
        entrada_usuario: Texto da pergunta ou comando do usuário.
    
    Returns:
        IntencaoConsulta: Objeto contendo a intenção identificada e entidades extraídas.
        
    Examples:
        >>> llm = OllamaLLM(model="llama3.1", base_url="http://localhost:11434")
        >>> resultado = await obter_intencao(llm, "quais os produtos mais vendidos este mês?")
        >>> print(resultado.intencao)
        "buscar_produtos_classificados"
        >>> print(resultado.entidades)
        {'criterio_classificacao': 'mais_vendidos', 'periodo_tempo': 'este_mes', 'limite': 10}
    """
    logger.info("Iniciando roteamento de intenção do usuário.")
    cadeia_processamento = prompt | llm | parser_json
    
    try:
        logger.debug(f"Enviando para o LLM para extração: '{entrada_usuario}'")
        resultado_dict = await cadeia_processamento.ainvoke({"entrada_usuario": entrada_usuario})
        logger.info(f"Dicionário extraído com sucesso: {resultado_dict}")
        
        intencao_obj = IntencaoConsulta(**(resultado_dict or {}))
        
        # Validação adicional: verificar se intenções que precisam de período têm período válido
        if intencao_obj.intencao in INTENCOES_QUE_PRECISAM_PERIODO:
            periodo = intencao_obj.entidades.get("periodo_tempo")
            
            # Se não há período ou é "sempre", forçar esclarecimento
            if not periodo or periodo == "sempre":
                logger.warning(f"Período obrigatório não fornecido para intenção: {intencao_obj.intencao}")
                
                mensagens_esclarecimento = {
                    "buscar_produtos_classificados": "Para consultar os produtos mais vendidos, preciso saber o período. Você quer ver os dados de hoje, este mês, último mês ou outro período específico?",
                    "buscar_clientes_classificados": "Para consultar os clientes que mais gastaram, preciso saber o período. Você quer ver os dados de hoje, este mês, último mês ou outro período específico?",
                    "listar_registros_vendas": "Para consultar o histórico de vendas, preciso saber o período. Você quer ver os dados de hoje, este mês, último mês ou outro período específico?"
                }
                
                return IntencaoConsulta(
                    intencao="necessita_esclarecimento",
                    entidades={},
                    mensagem_esclarecimento=mensagens_esclarecimento.get(
                        intencao_obj.intencao, 
                        "Para esta consulta, preciso saber o período de tempo. Você pode especificar: hoje, este mês, último mês ou outro período?"
                    )
                )
        
        return intencao_obj
        
    except Exception as e:
        logger.error(f"Erro ao extrair intenção com o parser JSON: {e}", exc_info=True)
        return IntencaoConsulta(intencao="desconhecido")