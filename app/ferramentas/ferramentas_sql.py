# app/ferramentas/ferramentas_sql.py
"""
Módulo de ferramentas para construção de queries SQL seguras.

Versão 2.0: Massivamente expandido para suportar todas as novas intenções de negócio.
Cada função é responsável por gerar uma query SQL parametrizada específica, garantindo
segurança contra SQL Injection e mantendo a lógica de banco de dados centralizada e
organizada.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Tuple, Optional

from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

ResultadoQuery = Tuple[str, Dict[str, Any]]

# --- Funções Auxiliares ---

def _construir_clausula_data(periodo_tempo: str, coluna_data: str) -> Tuple[str, Dict[str, Any]]:
    hoje = date.today()
    params = {}
    
    if periodo_tempo == 'hoje':
        clausula = f"TRUNC({coluna_data}) = :data_filtro"
        params['data_filtro'] = hoje
    elif periodo_tempo == 'este_mes':
        clausula = f"TO_CHAR({coluna_data}, 'YYYY-MM') = :data_filtro"
        params['data_filtro'] = hoje.strftime('%Y-%m')
    elif periodo_tempo == 'ultimo_mes':
        data_ultimo_mes = hoje - relativedelta(months=1)
        clausula = f"TO_CHAR({coluna_data}, 'YYYY-MM') = :data_filtro"
        params['data_filtro'] = data_ultimo_mes.strftime('%Y-%m')
    else:
        return "", {}
        
    return clausula, params

def _construir_filtro_texto_flexivel(termo: str, campos: List[str], nome_param: str) -> Tuple[str, Dict[str, Any]]:
    palavras_chave = str(termo).split()
    if not palavras_chave:
        return "", {}
    params = {}
    clausulas_campo = []
    for i, campo in enumerate(campos):
        clausulas_palavra_chave = []
        for j, palavra in enumerate(palavras_chave):
            key_param = f"{nome_param}_{i}_{j}"
            clausulas_palavra_chave.append(f"LOWER({campo}) LIKE LOWER(:{key_param})")
            params[key_param] = f"%{palavra}%"
        clausulas_campo.append(f"({' AND '.join(clausulas_palavra_chave)})")
    return f"({' OR '.join(clausulas_campo)})", params

# --- Construtores de Query: PRODUTOS ---

def construir_query_produtos_classificados(filtros: Dict, criterio_classificacao: str, periodo_tempo: str, limite: int) -> ResultadoQuery:
    # (Função original mantida e funcional)
    logger.info(f"Construindo query de ranking com critério: {criterio_classificacao}")
    mapa_ordenacao = {
        "mais_vendidos": "TOTAL_VENDIDO DESC", "menos_vendidos": "TOTAL_VENDIDO ASC",
        "mais_caros": "P.PVENDA DESC", "mais_baratos": "P.PVENDA ASC",
    }
    clausula_ordenacao = mapa_ordenacao.get(criterio_classificacao)
    if not clausula_ordenacao:
        raise ValueError(f"Critério de classificação inválido: {criterio_classificacao}")

    clausulas_where = ["P.DTEXCLUSAO IS NULL"]
    params = {"limite": limite}
    clausula_join = "LEFT JOIN PCPEDI PE ON P.CODPROD = PE.CODPROD LEFT JOIN PCPEDC PC ON PE.NUMPED = PC.NUMPED"
    clausula_group_by = "GROUP BY P.CODPROD, P.DESCRICAO, P.PVENDA"
    campos_select = "P.CODPROD, P.DESCRICAO, P.PVENDA, COUNT(PE.CODPROD) AS TOTAL_VENDIDO"
    
    clausula_data, params_data = _construir_clausula_data(periodo_tempo, 'PC.DATA')
    if clausula_data:
        clausulas_where.append(clausula_data)
        params.update(params_data)

    declaracao_where = " AND ".join(filter(None, clausulas_where))
    sql = f"""
        SELECT * FROM (
            SELECT {campos_select} FROM PCPRODUT P {clausula_join}
            WHERE {declaracao_where} {clausula_group_by} ORDER BY {clausula_ordenacao}
        ) WHERE ROWNUM <= :limite
    """
    return sql, params

def construir_query_detalhes_produto(nome_produto: str) -> ResultadoQuery:
    logger.info(f"Construindo query de detalhes para o produto: {nome_produto}")
    clausula_produto, params = _construir_filtro_texto_flexivel(nome_produto, ["P.DESCRICAO"], "produto")
    sql = f"""
        SELECT P.CODPROD, P.DESCRICAO, P.MARCA, P.PESOLIQ, P.PVENDA, F.FORNECEDOR
        FROM PCPRODUT P
        LEFT JOIN PCFORNEC F ON P.CODFORNEC = F.CODFORNEC
        WHERE {clausula_produto} AND P.DTEXCLUSAO IS NULL
        FETCH FIRST 5 ROWS ONLY
    """
    return sql, params

def construir_query_produtos_por_marca(marca: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query para produtos da marca: {marca}")
    clausula_marca, params = _construir_filtro_texto_flexivel(marca, ["P.MARCA"], "marca")
    params["limite"] = limite
    sql = f"""
        SELECT CODPROD, DESCRICAO, PVENDA FROM PCPRODUT P
        WHERE {clausula_marca} AND P.DTEXCLUSAO IS NULL
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_produtos_descontinuados(limite: int) -> ResultadoQuery:
    logger.info("Construindo query para produtos descontinuados")
    sql = """
        SELECT CODPROD, DESCRICAO, DTEXCLUSAO FROM PCPRODUT
        WHERE DTEXCLUSAO IS NOT NULL
        ORDER BY DTEXCLUSAO DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, {"limite": limite}

# --- Construtores de Query: CLIENTES ---

def construir_query_limite_credito(codigo_cliente: int) -> ResultadoQuery:
    logger.info(f"Construindo query para buscar limite de crédito do cliente: {codigo_cliente}")
    sql = "SELECT CODCLI, CLIENTE, LIMCRED FROM PCCLIENT WHERE CODCLI = :codigo_cliente"
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_status_cliente(codigo_cliente: int) -> ResultadoQuery:
    logger.info(f"Construindo query para status do cliente: {codigo_cliente}")
    sql = "SELECT CODCLI, CLIENTE, BLOQUEIO, MOTIVOBLOQ, DTBLOQ FROM PCCLIENT WHERE CODCLI = :codigo_cliente"
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_contato_cliente(codigo_cliente: int) -> ResultadoQuery:
    logger.info(f"Construindo query para contato do cliente: {codigo_cliente}")
    sql = "SELECT CODCLI, CLIENTE, TELENT, EMAIL FROM PCCLIENT WHERE CODCLI = :codigo_cliente"
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_endereco_cliente(codigo_cliente: int) -> ResultadoQuery:
    logger.info(f"Construindo query para endereço do cliente: {codigo_cliente}")
    sql = "SELECT CODCLI, CLIENTE, ENDERENT, NUMEROENT, BAIRROENT, MUNICENT, ESTENT, CEPENT FROM PCCLIENT WHERE CODCLI = :codigo_cliente"
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_clientes_por_cidade(cidade: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query para clientes na cidade: {cidade}")
    clausula_cidade, params = _construir_filtro_texto_flexivel(cidade, ["MUNICENT"], "cidade")
    params["limite"] = limite
    sql = f"""
        SELECT CODCLI, CLIENTE, FANTASIA, MUNICENT FROM PCCLIENT
        WHERE {clausula_cidade} AND DTEXCLUSAO IS NULL
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_clientes_recentes(periodo_tempo: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query para clientes recentes do período: {periodo_tempo}")
    clausula_data, params = _construir_clausula_data(periodo_tempo, 'DTCADASTRO')
    if not clausula_data:
        raise ValueError("Período de tempo inválido para esta consulta.")
    params["limite"] = limite
    sql = f"""
        SELECT CODCLI, CLIENTE, DTCADASTRO FROM PCCLIENT
        WHERE {clausula_data} AND DTEXCLUSAO IS NULL
        ORDER BY DTCADASTRO DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

# --- Construtores de Query: PEDIDOS ---

def construir_query_registros_vendas(codigo_cliente: int, periodo_tempo: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query de listagem de vendas para o cliente: {codigo_cliente}")
    clausulas_where = ["C.CODCLI = :codigo_cliente"]
    params = {"codigo_cliente": codigo_cliente, "limite": limite}
    
    clausula_data, params_data = _construir_clausula_data(periodo_tempo, 'PC.DATA')
    if clausula_data:
        clausulas_where.append(clausula_data)
        params.update(params_data)
        
    declaracao_where = " AND ".join(clausulas_where)
    sql = f"""
        SELECT C.CODCLI, C.CLIENTE, PC.NUMPED, PC.VLTOTAL, PC.POSICAO, PC.DATA
        FROM PCPEDC PC JOIN PCCLIENT C ON C.CODCLI = PC.CODCLI
        WHERE {declaracao_where} ORDER BY PC.DATA DESC FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_itens_pedido(id_pedido: int) -> ResultadoQuery:
    logger.info(f"Construindo query para buscar itens do pedido: {id_pedido}")
    sql = """
        SELECT PI.CODPROD, P.DESCRICAO, PI.QT, PI.PVENDA, (PI.QT * PI.PVENDA) AS VLTOTAL_ITEM
        FROM PCPEDI PI JOIN PCPRODUT P ON PI.CODPROD = P.CODPROD
        WHERE PI.NUMPED = :id_pedido
        ORDER BY P.DESCRICAO
    """
    return sql, {"id_pedido": id_pedido}

def construir_query_posicao_pedido(id_pedido: int) -> ResultadoQuery:
    logger.info(f"Construindo query para posição do pedido: {id_pedido}")
    sql = "SELECT NUMPED, POSICAO, DATA FROM PCPEDC WHERE NUMPED = :id_pedido"
    return sql, {"id_pedido": id_pedido}

def construir_query_valor_pedido(id_pedido: int) -> ResultadoQuery:
    logger.info(f"Construindo query para valor do pedido: {id_pedido}")
    sql = "SELECT NUMPED, VLTOTAL, DATA FROM PCPEDC WHERE NUMPED = :id_pedido"
    return sql, {"id_pedido": id_pedido}

def construir_query_data_entrega_pedido(id_pedido: int) -> ResultadoQuery:
    logger.info(f"Construindo query para data de entrega do pedido: {id_pedido}")
    sql = "SELECT NUMPED, DTENTREGA, DATA FROM PCPEDC WHERE NUMPED = :id_pedido"
    return sql, {"id_pedido": id_pedido}

def construir_query_pedidos_por_posicao(posicao: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query para pedidos na posição: {posicao}")
    mapa_posicao = {'liberado': 'L', 'bloqueado': 'B', 'pendente': 'P', 'faturado': 'F'}
    posicao_cod = mapa_posicao.get(posicao.lower(), posicao.upper())
    
    sql = """
        SELECT NUMPED, CODCLI, VLTOTAL, DATA FROM PCPEDC
        WHERE POSICAO = :posicao
        ORDER BY DATA DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, {"posicao": posicao_cod, "limite": limite}
