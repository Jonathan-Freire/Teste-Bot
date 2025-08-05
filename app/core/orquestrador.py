# app/orquestrador.py
"""
Módulo orquestrador principal.

Este módulo atua como o ponto de entrada para o processamento de consultas do usuário.
Ele coordena a interação entre os diferentes agentes e ferramentas para:
1. Extrair a intenção do usuário (`agente_roteador`).
2. Construir a consulta SQL apropriada com base na intenção (`ferramentas_sql`).
3. Executar a consulta no banco de dados (`consultas_bd`).
4. Gerar um resumo em linguagem natural dos resultados (`agente_sumarizador`).
"""

import logging
from typing import Any, Dict, Awaitable, Callable

from langchain_community.chat_models.ollama import ChatOllama

from app.agentes.agente_roteador import obter_intencao, IntencaoConsulta
from app.agentes.agente_sumarizador import sumarizar_resultados
from app.ferramentas import ferramentas_sql
from app.db.consultas import executar_consulta_selecao, encontrar_clientes_por_nome_ou_codigo

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Assinatura de tipo para as funções de manipulação de intenção
TipoManipuladorIntencao = Callable[[IntencaoConsulta], Awaitable[str]]


async def _manipular_produtos_classificados(dados_intencao: IntencaoConsulta) -> str:
    """Constrói a query para buscar produtos classificados."""
    logger.info("Intenção 'buscar_produtos_classificados' detectada.")
    if not dados_intencao.criterio_classificacao:
        raise ValueError("Critério de classificação não especificado (ex: mais vendidos).")
    
    filtros = {"marca": dados_intencao.marca, "nome_produto": dados_intencao.nome_produto}
    return ferramentas_sql.construir_query_produtos_classificados(
        filtros=filtros,
        criterio_classificacao=dados_intencao.criterio_classificacao,
        periodo_tempo=dados_intencao.periodo_tempo or "sempre",
        limite=dados_intencao.limite or 10
    )

async def _manipular_registros_vendas(dados_intencao: IntencaoConsulta) -> str:
    """Constrói a query para listar registros de vendas de um cliente."""
    logger.info("Intenção 'listar_registros_vendas' detectada.")
    codigo_cliente = dados_intencao.codigo_cliente
    nome_cliente = dados_intencao.nome_cliente

    if not codigo_cliente and nome_cliente:
        resultados_cliente = await encontrar_clientes_por_nome_ou_codigo(nome=nome_cliente)
        if resultados_cliente["erro"] or not resultados_cliente["dados"]:
            raise ValueError(f"Nenhum cliente encontrado com o nome '{nome_cliente}'.")
        if len(resultados_cliente["dados"]) > 1:
            opcoes = "\n".join([f"- Código: {c['codcli']}, Nome: {c['cliente']}" for c in resultados_cliente["dados"]])
            raise ValueError(f"Encontrei mais de um cliente. Especifique qual deles você deseja:\n{opcoes}")
        codigo_cliente = resultados_cliente["dados"][0]['codcli']

    if not codigo_cliente:
        raise ValueError("Para listar os pedidos, por favor, informe o nome ou o código do cliente.")
        
    filtros = {"codigo_cliente": codigo_cliente, "periodo_tempo": dados_intencao.periodo_tempo or "sempre"}
    return ferramentas_sql.construir_query_registros_vendas(filtros=filtros)

async def _manipular_detalhes_produto(dados_intencao: IntencaoConsulta) -> str:
    """Constrói a query para buscar detalhes de um produto específico."""
    logger.info("Intenção 'buscar_detalhes_produto' detectada.")
    if not dados_intencao.nome_produto:
        raise ValueError("Por favor, especifique o nome do produto que você está procurando.")
    filtros = {"nome_produto": dados_intencao.nome_produto}
    return ferramentas_sql.construir_query_detalhes_produto(filtros=filtros)

async def _manipular_itens_pedido(dados_intencao: IntencaoConsulta) -> str:
    """Constrói a query para obter os itens de um pedido."""
    logger.info("Intenção 'obter_itens_pedido' detectada.")
    if not dados_intencao.id_pedido:
        raise ValueError("Por favor, informe o número do pedido para que eu possa listar os itens.")
    return ferramentas_sql.construir_query_itens_pedido(id_pedido=dados_intencao.id_pedido)


# Mapeia as strings de intenção para suas respectivas funções de manipulação
MAPEAMENTO_INTENCOES: Dict[str, TipoManipuladorIntencao] = {
    "buscar_produtos_classificados": _manipular_produtos_classificados,
    "listar_registros_vendas": _manipular_registros_vendas,
    "buscar_detalhes_produto": _manipular_detalhes_produto,
    "obter_itens_pedido": _manipular_itens_pedido,
}


async def gerenciar_consulta_usuario(llm: ChatOllama, texto_usuario: str) -> str:
    """
    Orquestra o fluxo completo de processamento da consulta do usuário.

    Args:
        llm: A instância do modelo de linguagem a ser usada.
        texto_usuario: A pergunta original do usuário.

    Returns:
        A resposta final formatada para o usuário.
    """
    logger.info(f"--- INÍCIO DA ORQUESTRAÇÃO PARA: '{texto_usuario}' ---")
    try:
        # 1. Roteamento da intenção
        dados_intencao = await obter_intencao(llm, texto_usuario)
        intencao = dados_intencao.intencao

        # 2. Despacho para o manipulador correto
        manipulador = MAPEAMENTO_INTENCOES.get(intencao)
        if not manipulador:
            logger.warning(f"Intenção desconhecida ou não suportada: '{intencao}'")
            return "Desculpe, não entendi sua solicitação. Você pode pedir para ver os produtos mais vendidos, listar os pedidos de um cliente ou ver os itens de um pedido específico."

        # 3. Construção da Query SQL
        query_sql = await manipulador(dados_intencao)
        if not query_sql:
            raise RuntimeError("A ferramenta de construção de query não retornou uma string SQL.")

        # 4. Execução da Query
        resultado_bd = await executar_consulta_selecao(sql=query_sql, db='prod')
        if resultado_bd["erro"]:
            raise ConnectionError(f"Erro ao executar a query no banco de dados: {resultado_bd['erro']}")

        # 5. Sumarização e Resposta Final
        resposta_final = await sumarizar_resultados(llm, texto_usuario, resultado_bd["dados"])
        
        logger.info("--- FIM DA ORQUESTRAÇÃO ---")
        return resposta_final

    except (ValueError, RuntimeError, ConnectionError) as e:
        logger.error(f"Erro de negócio ou de execução durante a orquestração: {e}", exc_info=True)
        return str(e)  # Retorna a mensagem de erro de negócio diretamente para o usuário
    except Exception as e:
        logger.error(f"Erro inesperado na orquestração: {e}", exc_info=True)
        return "Desculpe, ocorreu um erro inesperado ao processar sua solicitação. Tente novamente mais tarde."
