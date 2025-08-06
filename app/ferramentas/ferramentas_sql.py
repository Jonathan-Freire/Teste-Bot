# app/ferramentas/ferramentas_sql.py
"""
Módulo de ferramentas para construção de queries SQL seguras.

Versão 3.3: Implementada validação rigorosa de períodos de tempo para evitar
consultas sem filtro que podem sobrecarregar a base de dados. O sistema agora
rejeita períodos inválidos ou "sempre" para consultas sensíveis.
"""

import logging
from datetime import date, datetime, time
from typing import Any, Dict, List, Tuple

from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

ResultadoQuery = Tuple[str, Dict[str, Any]]

# --- Funções Auxiliares ---

def _construir_clausula_data_otimizada(periodo_tempo: str, coluna_data: str) -> Tuple[str, Dict[str, Any]]:
    """
    Constrói uma cláusula WHERE de data otimizada usando ranges.
    VERSÃO RIGOROSA: Agora rejeita períodos inválidos ou "sempre" para evitar sobrecarga na base.
    """
    if not periodo_tempo or periodo_tempo.lower().strip() == "sempre":
        raise ValueError("Período de tempo é obrigatório e não pode ser 'sempre'. Use: hoje, este_mes, ultimo_mes, etc.")
    
    hoje = date.today()
    params = {}
    
    periodo_normalizado = str(periodo_tempo).lower().replace(" ", "_").strip()

    if periodo_normalizado == 'hoje':
        data_inicio = datetime.combine(hoje, time.min)
        data_fim = datetime.combine(hoje + relativedelta(days=1), time.min)
        clausula = f"{coluna_data} >= :data_inicio AND {coluna_data} < :data_fim"
        params['data_inicio'] = data_inicio
        params['data_fim'] = data_fim
        
    elif periodo_normalizado in ['este_mes', 'mes_atual']:
        data_inicio = datetime.combine(hoje.replace(day=1), time.min)
        data_fim = datetime.combine(data_inicio.date() + relativedelta(months=1), time.min)
        clausula = f"{coluna_data} >= :data_inicio AND {coluna_data} < :data_fim"
        params['data_inicio'] = data_inicio
        params['data_fim'] = data_fim

    elif periodo_normalizado in ['ultimo_mes', 'mes_passado']:
        data_fim = datetime.combine(hoje.replace(day=1), time.min)
        data_inicio = datetime.combine((data_fim.date() - relativedelta(months=1)), time.min)
        clausula = f"{coluna_data} >= :data_inicio AND {coluna_data} < :data_fim"
        params['data_inicio'] = data_inicio
        params['data_fim'] = data_fim

    elif periodo_normalizado in ['esta_semana', 'semana_atual']:
        # Segunda-feira da semana atual
        dias_desde_segunda = hoje.weekday()
        inicio_semana = hoje - relativedelta(days=dias_desde_segunda)
        data_inicio = datetime.combine(inicio_semana, time.min)
        data_fim = datetime.combine(inicio_semana + relativedelta(days=7), time.min)
        clausula = f"{coluna_data} >= :data_inicio AND {coluna_data} < :data_fim"
        params['data_inicio'] = data_inicio
        params['data_fim'] = data_fim

    elif periodo_normalizado in ['semana_passada', 'ultima_semana']:
        # Segunda-feira da semana passada
        dias_desde_segunda = hoje.weekday()
        inicio_semana_atual = hoje - relativedelta(days=dias_desde_segunda)
        inicio_semana_passada = inicio_semana_atual - relativedelta(days=7)
        data_inicio = datetime.combine(inicio_semana_passada, time.min)
        data_fim = datetime.combine(inicio_semana_atual, time.min)
        clausula = f"{coluna_data} >= :data_inicio AND {coluna_data} < :data_fim"
        params['data_inicio'] = data_inicio
        params['data_fim'] = data_fim

    elif periodo_normalizado in ['ontem']:
        ontem = hoje - relativedelta(days=1)
        data_inicio = datetime.combine(ontem, time.min)
        data_fim = datetime.combine(ontem + relativedelta(days=1), time.min)
        clausula = f"{coluna_data} >= :data_inicio AND {coluna_data} < :data_fim"
        params['data_inicio'] = data_inicio
        params['data_fim'] = data_fim
        
    else:
        periodos_validos = [
            'hoje', 'ontem', 'este_mes', 'mes_atual', 'ultimo_mes', 'mes_passado',
            'esta_semana', 'semana_atual', 'ultima_semana', 'semana_passada'
        ]
        raise ValueError(f"Período '{periodo_tempo}' não é válido. Use um dos seguintes: {', '.join(periodos_validos)}")
        
    logger.debug(f"Período '{periodo_tempo}' convertido para range: {data_inicio} até {data_fim}")
    return clausula, params

def _construir_filtro_texto_flexivel(termo: str, campos: List[str], nome_param: str) -> Tuple[str, Dict[str, Any]]:
    """
    Constrói uma cláusula WHERE para busca de texto flexível.
    AVISO: O uso de LOWER() e LIKE '%palavra%' pode ser lento em tabelas grandes,
    pois geralmente impede o uso de índices padrão.
    """
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

def construir_query_produtos_classificados(criterio_classificacao: str, periodo_tempo: str, limite: int) -> ResultadoQuery:
    """
    Constrói uma query otimizada para classificar produtos com base em critérios de vendas.
    VERSÃO RIGOROSA: Agora exige período válido obrigatório.
    """
    logger.info(f"Construindo query de ranking de produtos com critério: {criterio_classificacao}")
    
    if not periodo_tempo or periodo_tempo.strip().lower() == "sempre":
        raise ValueError("Período de tempo é obrigatório para esta consulta. Use: hoje, este_mes, ultimo_mes, etc.")
    
    mapa_sinonimos = {
        "mais_vendidos": "mais_vendidos", "maior_valor_vendas": "mais_vendidos",
        "top_vendas": "mais_vendidos", "menos_vendidos": "menos_vendidos",
    }
    criterio_normalizado = mapa_sinonimos.get(str(criterio_classificacao).lower().replace(" ", "_"))

    mapa_ordenacao = {"mais_vendidos": "TOTAL_VENDIDO DESC", "menos_vendidos": "TOTAL_VENDIDO ASC"}
    clausula_ordenacao = mapa_ordenacao.get(criterio_normalizado)
    if not clausula_ordenacao:
        raise ValueError(f"Critério de classificação inválido para vendas: {criterio_classificacao}")

    params = {"limite": limite}
    
    # Validação rigorosa: período sempre obrigatório
    clausula_data, params_data = _construir_clausula_data_otimizada(periodo_tempo, 'C.DATA')
    params.update(params_data)

    # Otimizada: Uso de hint INDEX_COMBINE, filtro DTEXCLUSAO movido para dentro da subquery
    sql = f"""
        SELECT /*+ FIRST_ROWS({limite}) INDEX_COMBINE(P) */ 
               P.CODPROD, P.DESCRICAO, P.PVENDA, VENDAS.TOTAL_VENDIDO
        FROM PCPRODUT P
        INNER JOIN (
            SELECT /*+ INDEX(I IDX_PCPEDI_CODPROD) INDEX(C IDX_PCPEDC_DATA) */
                   I.CODPROD, COUNT(*) AS TOTAL_VENDIDO
            FROM PCPEDI I
            INNER JOIN PCPEDC C ON I.NUMPED = C.NUMPED
            WHERE {clausula_data}
            GROUP BY I.CODPROD
        ) VENDAS ON P.CODPROD = VENDAS.CODPROD
        WHERE P.DTEXCLUSAO IS NULL
        ORDER BY {clausula_ordenacao}
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

# --- Construtores de Query: CLIENTES ---

def construir_query_clientes_classificados(criterio_classificacao: str, periodo_tempo: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query de ranking de clientes por: {criterio_classificacao}")

    if not periodo_tempo or periodo_tempo.strip().lower() == "sempre":
        raise ValueError("Período de tempo é obrigatório para esta consulta. Use: hoje, este_mes, ultimo_mes, etc.")

    if criterio_classificacao != 'maior_valor_compras':
        raise ValueError(f"Critério de classificação de cliente inválido: {criterio_classificacao}")

    params = {"limite": limite}
    
    # Validação rigorosa: período sempre obrigatório
    clausula_data, params_data = _construir_clausula_data_otimizada(periodo_tempo, 'DATA')
    params.update(params_data)

    # Otimizada: Hint para usar índice na data e evitar sort desnecessário
    sql = f"""
        SELECT /*+ FIRST_ROWS({limite}) INDEX(C) */
               C.CODCLI, C.CLIENTE, C.FANTASIA, GASTOS.VALOR_TOTAL_GASTO
        FROM PCCLIENT C
        INNER JOIN (
            SELECT /*+ INDEX(PCPEDC IDX_PCPEDC_DATA) */
                   CODCLI, SUM(VLTOTAL) AS VALOR_TOTAL_GASTO
            FROM PCPEDC
            WHERE {clausula_data}
            GROUP BY CODCLI
        ) GASTOS ON C.CODCLI = GASTOS.CODCLI
        ORDER BY GASTOS.VALOR_TOTAL_GASTO DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_detalhes_produto(nome_produto: str) -> ResultadoQuery:
    logger.info(f"Construindo query de detalhes para o produto: {nome_produto}")
    clausula_produto, params = _construir_filtro_texto_flexivel(nome_produto, ["P.DESCRICAO"], "produto")
    
    # Otimizada: Filtro DTEXCLUSAO primeiro para reduzir dataset, hint para uso de índice
    sql = f"""
        SELECT /*+ FIRST_ROWS(5) INDEX(P IDX_PCPRODUT_DESCRICAO) */
               P.CODPROD, P.DESCRICAO, P.MARCA, P.PESOLIQ, P.PVENDA, F.FORNECEDOR
        FROM PCPRODUT P
        LEFT JOIN PCFORNEC F ON P.CODFORNEC = F.CODFORNEC
        WHERE P.DTEXCLUSAO IS NULL 
          AND {clausula_produto}
        FETCH FIRST 5 ROWS ONLY
    """
    return sql, params

def construir_query_produtos_por_marca(marca: str, limite: int) -> ResultadoQuery:
    logger.info(f"Construindo query para produtos da marca: {marca}")
    clausula_marca, params = _construir_filtro_texto_flexivel(marca, ["P.MARCA"], "marca")
    params["limite"] = limite
    
    # Otimizada: Filtro DTEXCLUSAO primeiro, hint para índice na marca
    sql = f"""
        SELECT /*+ FIRST_ROWS(:limite) INDEX(P IDX_PCPRODUT_MARCA) */
               CODPROD, DESCRICAO, PVENDA 
        FROM PCPRODUT P
        WHERE P.DTEXCLUSAO IS NULL 
          AND {clausula_marca}
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_produtos_descontinuados(limite: int) -> ResultadoQuery:
    logger.info("Construindo query para produtos descontinuados")
    
    # Otimizada: Hint para usar índice na DTEXCLUSAO
    sql = """
        SELECT /*+ FIRST_ROWS(:limite) INDEX(PCPRODUT IDX_PCPRODUT_DTEXCLUSAO) */
               CODPROD, DESCRICAO, DTEXCLUSAO 
        FROM PCPRODUT
        WHERE DTEXCLUSAO IS NOT NULL
        ORDER BY DTEXCLUSAO DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, {"limite": limite}

# --- Construtores de Query: CLIENTES (Consultas Simples) ---

def construir_query_limite_credito(codigo_cliente: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCCLIENT PK_PCCLIENT) */
               CODCLI, CLIENTE, LIMCRED 
        FROM PCCLIENT 
        WHERE CODCLI = :codigo_cliente
    """
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_status_cliente(codigo_cliente: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCCLIENT PK_PCCLIENT) */
               CODCLI, CLIENTE, BLOQUEIO, MOTIVOBLOQ, DTBLOQ 
        FROM PCCLIENT 
        WHERE CODCLI = :codigo_cliente
    """
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_contato_cliente(codigo_cliente: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCCLIENT PK_PCCLIENT) */
               CODCLI, CLIENTE, TELENT, EMAIL 
        FROM PCCLIENT 
        WHERE CODCLI = :codigo_cliente
    """
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_endereco_cliente(codigo_cliente: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCCLIENT PK_PCCLIENT) */
               CODCLI, CLIENTE, ENDERENT, NUMEROENT, BAIRROENT, MUNICENT, ESTENT, CEPENT 
        FROM PCCLIENT 
        WHERE CODCLI = :codigo_cliente
    """
    return sql, {"codigo_cliente": codigo_cliente}

def construir_query_clientes_por_cidade(cidade: str, limite: int) -> ResultadoQuery:
    clausula_cidade, params = _construir_filtro_texto_flexivel(cidade, ["MUNICENT"], "cidade")
    params["limite"] = limite
    
    # Otimizada: Filtro DTEXCLUSAO primeiro, hint para índice na cidade
    sql = f"""
        SELECT /*+ FIRST_ROWS(:limite) INDEX(PCCLIENT IDX_PCCLIENT_MUNICENT) */
               CODCLI, CLIENTE, FANTASIA, MUNICENT 
        FROM PCCLIENT
        WHERE DTEXCLUSAO IS NULL 
          AND {clausula_cidade}
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_clientes_recentes(periodo_tempo: str, limite: int) -> ResultadoQuery:
    if not periodo_tempo or periodo_tempo.strip().lower() == "sempre":
        raise ValueError("Período de tempo específico é obrigatório para esta consulta.")
        
    clausula_data, params = _construir_clausula_data_otimizada(periodo_tempo, 'DTCADASTRO')
    params["limite"] = limite
    
    # Otimizada: Hint para usar índice na data de cadastro, filtro DTEXCLUSAO otimizado
    sql = f"""
        SELECT /*+ FIRST_ROWS(:limite) INDEX(PCCLIENT IDX_PCCLIENT_DTCADASTRO) */
               CODCLI, CLIENTE, DTCADASTRO 
        FROM PCCLIENT
        WHERE DTEXCLUSAO IS NULL 
          AND {clausula_data}
        ORDER BY DTCADASTRO DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

# --- Construtores de Query: PEDIDOS ---

def construir_query_registros_vendas(codigo_cliente: int, periodo_tempo: str, limite: int) -> ResultadoQuery:
    if not periodo_tempo or periodo_tempo.strip().lower() == "sempre":
        raise ValueError("Período de tempo é obrigatório para esta consulta. Use: hoje, este_mes, ultimo_mes, etc.")
    
    params = {"codigo_cliente": codigo_cliente, "limite": limite}
    clausula_data, params_data = _construir_clausula_data_otimizada(periodo_tempo, 'PC.DATA')
    params.update(params_data)
    
    # Otimizada: Hint para usar índices compostos, JOIN otimizado
    sql = f"""
        SELECT /*+ FIRST_ROWS(:limite) INDEX(PC IDX_PCPEDC_CODCLI_DATA) INDEX(C PK_PCCLIENT) */
               C.CODCLI, C.CLIENTE, PC.NUMPED, PC.VLTOTAL, PC.POSICAO, PC.DATA
        FROM PCPEDC PC 
        INNER JOIN PCCLIENT C ON C.CODCLI = PC.CODCLI
        WHERE PC.CODCLI = :codigo_cliente AND {clausula_data}
        ORDER BY PC.DATA DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, params

def construir_query_itens_pedido(id_pedido: int) -> ResultadoQuery:
    # Otimizada: Hint para usar índice no NUMPED, join otimizado
    sql = """
        SELECT /*+ INDEX(PI IDX_PCPEDI_NUMPED) INDEX(P PK_PCPRODUT) */
               PI.CODPROD, P.DESCRICAO, PI.QT, PI.PVENDA, (PI.QT * PI.PVENDA) AS VLTOTAL_ITEM
        FROM PCPEDI PI 
        INNER JOIN PCPRODUT P ON PI.CODPROD = P.CODPROD
        WHERE PI.NUMPED = :id_pedido
        ORDER BY P.DESCRICAO
    """
    return sql, {"id_pedido": id_pedido}

def construir_query_posicao_pedido(id_pedido: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCPEDC PK_PCPEDC) */
               NUMPED, POSICAO, DATA 
        FROM PCPEDC 
        WHERE NUMPED = :id_pedido
    """
    return sql, {"id_pedido": id_pedido}

def construir_query_valor_pedido(id_pedido: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCPEDC PK_PCPEDC) */
               NUMPED, VLTOTAL, DATA 
        FROM PCPEDC 
        WHERE NUMPED = :id_pedido
    """
    return sql, {"id_pedido": id_pedido}

def construir_query_data_entrega_pedido(id_pedido: int) -> ResultadoQuery:
    # Otimizada: Hint para busca por chave primária
    sql = """
        SELECT /*+ INDEX(PCPEDC PK_PCPEDC) */
               NUMPED, DTENTREGA, DATA 
        FROM PCPEDC 
        WHERE NUMPED = :id_pedido
    """
    return sql, {"id_pedido": id_pedido}

def construir_query_pedidos_por_posicao(posicao: str, limite: int) -> ResultadoQuery:
    mapa_posicao = {'liberado': 'L', 'bloqueado': 'B', 'pendente': 'P', 'faturado': 'F'}
    posicao_cod = mapa_posicao.get(posicao.lower(), posicao.upper())
    
    # Otimizada: Hint para usar índice na posição e data
    sql = """
        SELECT /*+ FIRST_ROWS(:limite) INDEX(PCPEDC IDX_PCPEDC_POSICAO_DATA) */
               NUMPED, CODCLI, VLTOTAL, DATA 
        FROM PCPEDC
        WHERE POSICAO = :posicao
        ORDER BY DATA DESC
        FETCH FIRST :limite ROWS ONLY
    """
    return sql, {"posicao": posicao_cod, "limite": limite}