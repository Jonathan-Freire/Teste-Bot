# app/ferramentas/ferramentas_sql.py
"""
Módulo de ferramentas para construção de queries SQL seguras.

Este módulo fornece funções para gerar dinamicamente as strings SQL e os
dicionários de parâmetros correspondentes para diversas consultas, utilizando
prepared statements para garantir a segurança contra ataques de SQL Injection.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Tuple

from dateutil.relativedelta import relativedelta

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Tipo para representar o resultado de uma função de construção de query
ResultadoQuery = Tuple[str, Dict[str, Any]]


def _construir_clausula_data(periodo_tempo: str, coluna_data: str = 'PC.DATA') -> Tuple[str, Dict[str, Any]]:
    """
    Constrói uma cláusula de filtro de data segura e seus parâmetros.

    Args:
        periodo_tempo: String que define o período ('hoje', 'este_mes', etc.).
        coluna_data: O nome da coluna de data a ser filtrada.

    Returns:
        Uma tupla contendo a string da cláusula SQL e um dicionário de parâmetros.
    """
    hoje = date.today()
    params = {}
    
    if periodo_tempo == 'hoje':
        clausula = f"TRUNC({coluna_data}) = :data_filtro"
        params['data_filtro'] = hoje
    elif periodo_tempo == 'este_mes':
        clausula = f"TO_CHAR({coluna_data}, 'YYYY-MM') = :data_filtro"
        params['data_filtro'] = hoje.strftime('%Y-%m')
    elif periodo_tempo == 'este_ano':
        clausula = f"TO_CHAR({coluna_data}, 'YYYY') = :data_filtro"
        params['data_filtro'] = hoje.strftime('%Y')
    elif periodo_tempo == 'ultimo_mes':
        data_ultimo_mes = hoje - relativedelta(months=1)
        clausula = f"TO_CHAR({coluna_data}, 'YYYY-MM') = :data_filtro"
        params['data_filtro'] = data_ultimo_mes.strftime('%Y-%m')
    else:
        # Se não houver filtro de tempo, retorna uma cláusula vazia
        return "", {}
        
    return clausula, params


def _construir_filtro_texto_flexivel(termo: str, campos: List[str], nome_param: str) -> Tuple[str, Dict[str, Any]]:
    """
    Constrói um filtro de texto flexível para múltiplos campos e palavras-chave.

    Args:
        termo: O termo de busca.
        campos: Lista de colunas onde a busca será realizada.
        nome_param: O nome base para os parâmetros da query.

    Returns:
        Uma tupla contendo a string da cláusula SQL e um dicionário de parâmetros.
    """
    palavras_chave = str(termo).split()
    if not palavras_chave:
        return "", {}

    params = {}
    clausulas_campo = []
    for i, campo in enumerate(campos):
        clausulas_palavra_chave = []
        for j, palavra in enumerate(palavras_chave):
            # Cria um nome de parâmetro único para cada palavra-chave e campo
            key_param = f"{nome_param}_{i}_{j}"
            clausulas_palavra_chave.append(f"LOWER({campo}) LIKE LOWER(:{key_param})")
            params[key_param] = f"%{palavra}%"
        clausulas_campo.append(f"({' AND '.join(clausulas_palavra_chave)})")
    
    return f"({' OR '.join(clausulas_campo)})", params


def construir_query_produtos_classificados(filtros: Dict, criterio_classificacao: str, periodo_tempo: str, limite: int = 10) -> ResultadoQuery:
    """Constrói a query para buscar produtos classificados."""
    logger.info(f"Construindo query de ranking com filtros: {filtros}, critério: {criterio_classificacao}, período: {periodo_tempo}")

    mapa_ordenacao = {
        "mais_vendidos": "TOTAL_VENDIDO DESC", "menos_vendidos": "TOTAL_VENDIDO ASC",
        "mais_caros": "P.PVENDA DESC", "mais_baratos": "P.PVENDA ASC",
        "mais_pesados": "P.PESOLIQ DESC", "mais_leves": "P.PESOLIQ ASC"
    }
    clausula_ordenacao = mapa_ordenacao.get(criterio_classificacao)
    if not clausula_ordenacao:
        raise ValueError(f"Critério de classificação inválido: {criterio_classificacao}")

    clausulas_where = ["P.DTEXCLUSAO IS NULL"]
    params = {"limite": limite}
    clausula_join, clausula_group_by, campos_select = "", "", "P.CODPROD, P.DESCRICAO, P.PVENDA, P.PESOLIQ"

    if "TOTAL_VENDIDO" in clausula_ordenacao:
        clausula_join = "JOIN PCPEDI PE ON P.CODPROD = PE.CODPROD JOIN PCPEDC PC ON PE.NUMPED = PC.NUMPED"
        clausula_group_by = "GROUP BY P.CODPROD, P.DESCRICAO, P.PVENDA, P.PESOLIQ"
        campos_select += ", SUM(PE.QT) AS TOTAL_VENDIDO"
        clausula_data, params_data = _construir_clausula_data(periodo_tempo, 'PC.DATA')
        if clausula_data:
            clausulas_where.append(clausula_data)
            params.update(params_data)

    if filtros.get("marca"):
        clausula_marca, params_marca = _construir_filtro_texto_flexivel(filtros["marca"], ["P.DESCRICAO"], "marca")
        clausulas_where.append(clausula_marca)
        params.update(params_marca)
    if filtros.get("nome_produto"):
        clausula_produto, params_produto = _construir_filtro_texto_flexivel(filtros["nome_produto"], ["P.DESCRICAO"], "produto")
        clausulas_where.append(clausula_produto)
        params.update(params_produto)

    declaracao_where = " AND ".join(filter(None, clausulas_where))
    sql = f"""
        SELECT * FROM (
            SELECT {campos_select} FROM PCPRODUT P {clausula_join}
            WHERE {declaracao_where} {clausula_group_by} ORDER BY {clausula_ordenacao}
        ) WHERE ROWNUM <= :limite
    """
    return sql, params


def construir_query_registros_vendas(filtros: Dict, limite: int = 50) -> ResultadoQuery:
    """Constrói a query para listar registros de vendas."""
    logger.info(f"Construindo query de listagem de vendas com filtros: {filtros}")
    clausulas_where = []
    params = {"limite": limite}

    if filtros.get("codigo_cliente"):
        clausulas_where.append("C.CODCLI = :codigo_cliente")
        params["codigo_cliente"] = filtros['codigo_cliente']
    
    clausula_data, params_data = _construir_clausula_data(filtros.get("periodo_tempo", "sempre"), 'PC.DATA')
    if clausula_data:
        clausulas_where.append(clausula_data)
        params.update(params_data)
        
    declaracao_where = " AND ".join(clausulas_where) if clausulas_where else "1=1"
    sql = f"""
        SELECT C.CODCLI, C.CLIENTE, PC.NUMPED, PC.VLTOTAL, PC.POSICAO, PC.DATA
        FROM PCPEDC PC JOIN PCCLIENT C ON C.CODCLI = PC.CODCLI
        WHERE {declaracao_where} ORDER BY PC.DATA DESC FETCH FIRST :limite ROWS ONLY
    """
    return sql, params


def construir_query_detalhes_produto(filtros: Dict) -> ResultadoQuery:
    """Constrói a query para buscar detalhes de um produto."""
    logger.info(f"Construindo query de detalhes de produto com filtros: {filtros}")
    clausulas_where = ["P.DTEXCLUSAO IS NULL"]
    params = {}

    if filtros.get("nome_produto"):
        clausula_produto, params_produto = _construir_filtro_texto_flexivel(filtros["nome_produto"], ["P.DESCRICAO"], "produto")
        clausulas_where.append(clausula_produto)
        params.update(params_produto)
    
    declaracao_where = " AND ".join(filter(None, clausulas_where))
    sql = f"""
        SELECT CODPROD, DESCRICAO, PVENDA, PESOLIQ, UNIDADE FROM PCPRODUT P
        WHERE {declaracao_where} FETCH FIRST 5 ROWS ONLY
    """
    return sql, params


def construir_query_itens_pedido(id_pedido: int) -> ResultadoQuery:
    """Constrói a query para buscar os itens de um pedido específico."""
    logger.info(f"Construindo query para buscar itens do pedido: {id_pedido}")
    sql = """
        SELECT PI.CODPROD, P.DESCRICAO, PI.QT, PI.PVENDA, (PI.QT * PI.PVENDA) AS VLTOTAL_ITEM
        FROM PCPEDI PI JOIN PCPRODUT P ON PI.CODPROD = P.CODPROD
        WHERE PI.NUMPED = :id_pedido AND P.DTEXCLUSAO IS NULL
        ORDER BY P.DESCRICAO
    """
    params = {"id_pedido": id_pedido}
    return sql, params
