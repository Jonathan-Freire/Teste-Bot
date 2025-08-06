# app/core/orquestrador.py
"""
Módulo orquestrador principal.

Versão 2.4: Removidos defaults de "sempre" para período de tempo em consultas sensíveis.
Agora o sistema é mais rigoroso e sempre exigirá período específico para evitar
sobrecarga na base de dados.
"""

import logging
from typing import Any, Dict, Awaitable, Callable, Tuple

from langchain_community.chat_models.ollama import ChatOllama

from app.agentes.agente_roteador import obter_intencao
from app.agentes.agente_sumarizador import sumarizar_resultados
from app.ferramentas import ferramentas_sql
from app.ferramentas.ferramentas_sql import ResultadoQuery
from app.db.consultas import executar_consulta_selecao, encontrar_clientes_por_nome_ou_codigo

logger = logging.getLogger(__name__)

# A assinatura do manipulador espera um Awaitable, então as funções devem ser async.
TipoManipuladorIntencao = Callable[[Dict[str, Any]], Awaitable[ResultadoQuery]]

# --- Funções Auxiliares do Orquestrador ---

async def _resolver_cliente(entidades: Dict[str, Any]) -> int:
    """Função auxiliar para encontrar o código do cliente a partir do nome ou código."""
    codigo_cliente = entidades.get("codigo_cliente")
    nome_cliente = entidades.get("nome_cliente")

    if codigo_cliente:
        return int(codigo_cliente)

    if nome_cliente:
        resultados_cliente = await encontrar_clientes_por_nome_ou_codigo(nome=nome_cliente)
        if resultados_cliente.get("erro") or not resultados_cliente.get("dados"):
            raise ValueError(f"Nenhum cliente encontrado com o nome '{nome_cliente}'.")
        if len(resultados_cliente["dados"]) > 1:
            opcoes = "\n".join([f"- Código: {c['codcli']}, Nome: {c['cliente']}" for c in resultados_cliente["dados"]])
            raise ValueError(f"Encontrei mais de um cliente. Por favor, especifique qual deles você deseja:\n{opcoes}")
        return resultados_cliente["dados"][0]['codcli']

    raise ValueError("Para esta consulta, por favor, informe o nome ou o código do cliente.")

# --- Manipuladores de Intenção ---

async def _manipular_produtos_classificados(entidades: Dict[str, Any]) -> ResultadoQuery:
    criterio = entidades.get("criterio_classificacao")
    if not criterio:
        raise ValueError("Critério de classificação não especificado (ex: mais vendidos).")
    
    periodo = entidades.get("periodo_tempo")
    if not periodo:
        raise ValueError("Período de tempo é obrigatório para esta consulta.")
    
    return ferramentas_sql.construir_query_produtos_classificados(
        criterio_classificacao=criterio,
        periodo_tempo=periodo,
        limite=entidades.get("limite", 10)
    )

async def _manipular_registros_vendas(entidades: Dict[str, Any]) -> ResultadoQuery:
    codigo_cliente = await _resolver_cliente(entidades)
    periodo = entidades.get("periodo_tempo")
    if not periodo:
        raise ValueError("Período de tempo é obrigatório para esta consulta.")
    
    return ferramentas_sql.construir_query_registros_vendas(
        codigo_cliente=codigo_cliente,
        periodo_tempo=periodo,
        limite=entidades.get("limite", 50)
    )

async def _manipular_detalhes_produto(entidades: Dict[str, Any]) -> ResultadoQuery:
    nome_produto = entidades.get("nome_produto")
    if not nome_produto:
        raise ValueError("Por favor, especifique o nome do produto.")
    return ferramentas_sql.construir_query_detalhes_produto(nome_produto=nome_produto)

async def _manipular_itens_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_itens_pedido(id_pedido=int(id_pedido))

async def _manipular_limite_credito(entidades: Dict[str, Any]) -> ResultadoQuery:
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_limite_credito(codigo_cliente)

async def _manipular_status_cliente(entidades: Dict[str, Any]) -> ResultadoQuery:
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_status_cliente(codigo_cliente)

async def _manipular_contato_cliente(entidades: Dict[str, Any]) -> ResultadoQuery:
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_contato_cliente(codigo_cliente)

async def _manipular_endereco_cliente(entidades: Dict[str, Any]) -> ResultadoQuery:
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_endereco_cliente(codigo_cliente)

async def _manipular_clientes_por_cidade(entidades: Dict[str, Any]) -> ResultadoQuery:
    cidade = entidades.get("cidade")
    if not cidade:
        raise ValueError("Por favor, especifique a cidade.")
    return ferramentas_sql.construir_query_clientes_por_cidade(cidade, entidades.get("limite", 20))

async def _manipular_clientes_recentes(entidades: Dict[str, Any]) -> ResultadoQuery:
    periodo = entidades.get("periodo_tempo")
    if not periodo or periodo == "sempre":
        raise ValueError("Por favor, especifique um período de tempo específico (ex: 'este mês', 'hoje').")
    return ferramentas_sql.construir_query_clientes_recentes(periodo, entidades.get("limite", 20))

async def _manipular_produtos_por_marca(entidades: Dict[str, Any]) -> ResultadoQuery:
    marca = entidades.get("marca")
    if not marca:
        raise ValueError("Por favor, especifique a marca do produto.")
    return ferramentas_sql.construir_query_produtos_por_marca(marca, entidades.get("limite", 20))

async def _manipular_produtos_descontinuados(entidades: Dict[str, Any]) -> ResultadoQuery:
    return ferramentas_sql.construir_query_produtos_descontinuados(entidades.get("limite", 20))

async def _manipular_posicao_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_posicao_pedido(int(id_pedido))

async def _manipular_valor_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_valor_pedido(int(id_pedido))

async def _manipular_data_entrega_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_data_entrega_pedido(int(id_pedido))

async def _manipular_pedidos_por_posicao(entidades: Dict[str, Any]) -> ResultadoQuery:
    posicao = entidades.get("posicao")
    if not posicao:
        raise ValueError("Por favor, especifique a posição dos pedidos (ex: 'bloqueado').")
    return ferramentas_sql.construir_query_pedidos_por_posicao(posicao, entidades.get("limite", 20))

async def _manipular_clientes_classificados(entidades: Dict[str, Any]) -> ResultadoQuery:
    criterio = entidades.get("criterio_classificacao")
    if not criterio:
        raise ValueError("Critério de classificação para clientes não especificado.")
    
    periodo = entidades.get("periodo_tempo")
    if not periodo:
        raise ValueError("Período de tempo é obrigatório para esta consulta.")
    
    return ferramentas_sql.construir_query_clientes_classificados(
        criterio_classificacao=criterio,
        periodo_tempo=periodo,
        limite=entidades.get("limite", 10)
    )

# Mapeamento expandido de intenções para suas respectivas funções de manipulação
MAPEAMENTO_INTENCOES: Dict[str, TipoManipuladorIntencao] = {
    "buscar_produtos_classificados": _manipular_produtos_classificados,
    "listar_registros_vendas": _manipular_registros_vendas,
    "buscar_detalhes_produto": _manipular_detalhes_produto,
    "obter_itens_pedido": _manipular_itens_pedido,
    "consultar_limite_credito": _manipular_limite_credito,
    "verificar_status_cliente": _manipular_status_cliente,
    "buscar_dados_contato_cliente": _manipular_contato_cliente,
    "buscar_endereco_cliente": _manipular_endereco_cliente,
    "listar_clientes_por_cidade": _manipular_clientes_por_cidade,
    "listar_clientes_recentes": _manipular_clientes_recentes,
    "listar_produtos_por_marca": _manipular_produtos_por_marca,
    "listar_produtos_descontinuados": _manipular_produtos_descontinuados,
    "verificar_posicao_pedido": _manipular_posicao_pedido,
    "consultar_valor_pedido": _manipular_valor_pedido,
    "consultar_data_entrega_pedido": _manipular_data_entrega_pedido,
    "listar_pedidos_por_posicao": _manipular_pedidos_por_posicao,
    "buscar_clientes_classificados": _manipular_clientes_classificados,
}

async def gerenciar_consulta_usuario(llm: ChatOllama, texto_usuario: str) -> str:
    logger.info(f"--- INÍCIO DA ORQUESTRAÇÃO PARA: '{texto_usuario}' ---")
    try:
        dados_intencao = await obter_intencao(llm, texto_usuario)
        intencao = dados_intencao.intencao
        entidades = dados_intencao.entidades

        if intencao == "desconhecido":
            return "Desculpe, não entendi sua solicitação. Você pode perguntar sobre clientes, produtos ou pedidos."
        if intencao == "necessita_esclarecimento":
            return dados_intencao.mensagem_esclarecimento

        manipulador = MAPEAMENTO_INTENCOES.get(intencao)
        if not manipulador:
            raise RuntimeError(f"Nenhum manipulador definido para a intenção '{intencao}'.")

        # A chamada ao manipulador agora é sempre 'await' porque todos eles são async.
        query_sql, params = await manipulador(entidades)
        
        resultado_bd = await executar_consulta_selecao(sql=query_sql, params=params, db='prod')
        if resultado_bd["erro"]:
            raise ConnectionError(f"Erro ao consultar o banco de dados: {resultado_bd['erro']}")

        resposta_final = await sumarizar_resultados(llm, texto_usuario, resultado_bd["dados"])
        
        logger.info("--- FIM DA ORQUESTRAÇÃO ---")
        return resposta_final

    except (ValueError, RuntimeError, ConnectionError) as e:
        logger.error(f"Erro de negócio durante a orquestração: {e}", exc_info=False)
        return str(e)
    except Exception as e:
        logger.error(f"Erro inesperado na orquestração: {e}", exc_info=True)
        return "Desculpe, ocorreu um erro inesperado. Tente novamente mais tarde."