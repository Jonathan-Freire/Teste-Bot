import logging
from typing import Any, Dict, Awaitable, Callable

# CORREÇÃO: Importação atualizada para langchain-ollama
from langchain_ollama import OllamaLLM

from app.agentes.agente_roteador import obter_intencao
from app.agentes.agente_sumarizador import sumarizar_resultados
from app.ferramentas import ferramentas_sql
from app.ferramentas.ferramentas_sql import ResultadoQuery
from app.db.consultas import executar_consulta_selecao, encontrar_clientes_por_nome_ou_codigo

logger = logging.getLogger(__name__)

TipoManipuladorIntencao = Callable[[Dict[str, Any]], Awaitable[ResultadoQuery]]

# --- Funções Auxiliares ---

async def _resolver_cliente(entidades: Dict[str, Any]) -> int:
    """
    Resolve o código do cliente a partir do nome ou código fornecido.
    
    Args:
        entidades: Dicionário contendo as entidades extraídas da pergunta do usuário.
        
    Returns:
        int: Código do cliente encontrado no banco de dados.
        
    Raises:
        ValueError: Se nenhum cliente for encontrado ou houver ambiguidade na busca.
        
    Examples:
        >>> entidades = {"nome_cliente": "João Silva"}
        >>> codigo = await _resolver_cliente(entidades)
        >>> print(codigo)  # 12345
        
        >>> entidades = {"codigo_cliente": 123}
        >>> codigo = await _resolver_cliente(entidades)
        >>> print(codigo)  # 123
    """
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
    """
    Constrói query para buscar produtos classificados por critério de vendas.
    
    Args:
        entidades: Dicionário com criterio_classificacao, periodo_tempo e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
        
    Examples:
        >>> entidades = {
        ...     "criterio_classificacao": "mais_vendidos", 
        ...     "periodo_tempo": "este_mes", 
        ...     "limite": 5
        ... }
        >>> sql, params = await _manipular_produtos_classificados(entidades)
        >>> print(type(sql))
        <class 'str'>
    """
    criterio = entidades.get("criterio_classificacao")
    if not criterio:
        raise ValueError("Critério de classificação não especificado (ex: mais vendidos).")
    
    periodo = entidades.get("periodo_tempo")
    if not periodo:
        periodo = "este_mes"
        logger.warning(f"Período não especificado, usando padrão: {periodo}")
    
    return ferramentas_sql.construir_query_produtos_classificados(
        criterio_classificacao=criterio,
        periodo_tempo=periodo,
        limite=entidades.get("limite", 10)
    )

async def _manipular_registros_vendas(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para listar registros de vendas de um cliente.
    
    Args:
        entidades: Dicionário com nome_cliente/codigo_cliente, periodo_tempo e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
        
    Examples:
        >>> entidades = {"nome_cliente": "João", "periodo_tempo": "este_mes"}
        >>> sql, params = await _manipular_registros_vendas(entidades)
        >>> print("cliente" in str(sql).lower())
        True
    """
    codigo_cliente = await _resolver_cliente(entidades)
    periodo = entidades.get("periodo_tempo", "este_mes")
    
    return ferramentas_sql.construir_query_registros_vendas(
        codigo_cliente=codigo_cliente,
        periodo_tempo=periodo,
        limite=entidades.get("limite", 50)
    )

async def _manipular_detalhes_produto(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para buscar detalhes de um produto.
    
    Args:
        entidades: Dicionário com nome_produto.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
        
    Examples:
        >>> entidades = {"nome_produto": "Parafuso"}
        >>> sql, params = await _manipular_detalhes_produto(entidades)
        >>> print("produto" in str(sql).lower())
        True
    """
    nome_produto = entidades.get("nome_produto")
    if not nome_produto:
        raise ValueError("Por favor, especifique o nome do produto.")
    return ferramentas_sql.construir_query_detalhes_produto(nome_produto=nome_produto)

async def _manipular_itens_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para obter itens de um pedido.
    
    Args:
        entidades: Dicionário com id_pedido.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
        
    Examples:
        >>> entidades = {"id_pedido": 12345}
        >>> sql, params = await _manipular_itens_pedido(entidades)
        >>> print(params["id_pedido"])
        12345
    """
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_itens_pedido(id_pedido=int(id_pedido))

async def _manipular_limite_credito(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para consultar limite de crédito de um cliente.
    
    Args:
        entidades: Dicionário com nome_cliente ou codigo_cliente.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
        
    Examples:
        >>> entidades = {"codigo_cliente": 123}
        >>> sql, params = await _manipular_limite_credito(entidades)
        >>> print(params["codigo_cliente"])
        123
    """
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_limite_credito(codigo_cliente)

async def _manipular_status_cliente(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para verificar status de bloqueio de um cliente.
    
    Args:
        entidades: Dicionário com nome_cliente ou codigo_cliente.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_status_cliente(codigo_cliente)

async def _manipular_contato_cliente(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para buscar dados de contato de um cliente.
    
    Args:
        entidades: Dicionário com nome_cliente ou codigo_cliente.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_contato_cliente(codigo_cliente)

async def _manipular_endereco_cliente(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para buscar endereço de um cliente.
    
    Args:
        entidades: Dicionário com nome_cliente ou codigo_cliente.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    codigo_cliente = await _resolver_cliente(entidades)
    return ferramentas_sql.construir_query_endereco_cliente(codigo_cliente)

async def _manipular_clientes_por_cidade(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para listar clientes de uma cidade.
    
    Args:
        entidades: Dicionário com cidade e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    cidade = entidades.get("cidade")
    if not cidade:
        raise ValueError("Por favor, especifique a cidade.")
    return ferramentas_sql.construir_query_clientes_por_cidade(cidade, entidades.get("limite", 20))

async def _manipular_clientes_recentes(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para listar clientes cadastrados recentemente.
    
    Args:
        entidades: Dicionário com periodo_tempo e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    periodo = entidades.get("periodo_tempo")
    if not periodo or periodo == "sempre":
        raise ValueError("Por favor, especifique um período de tempo específico (ex: 'este mês', 'hoje').")
    return ferramentas_sql.construir_query_clientes_recentes(periodo, entidades.get("limite", 20))

async def _manipular_produtos_por_marca(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para listar produtos de uma marca.
    
    Args:
        entidades: Dicionário com marca e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    marca = entidades.get("marca")
    if not marca:
        raise ValueError("Por favor, especifique a marca do produto.")
    return ferramentas_sql.construir_query_produtos_por_marca(marca, entidades.get("limite", 20))

async def _manipular_produtos_descontinuados(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para listar produtos descontinuados.
    
    Args:
        entidades: Dicionário com limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    return ferramentas_sql.construir_query_produtos_descontinuados(entidades.get("limite", 20))

async def _manipular_posicao_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para verificar posição/status de um pedido.
    
    Args:
        entidades: Dicionário com id_pedido.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_posicao_pedido(int(id_pedido))

async def _manipular_valor_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para consultar valor total de um pedido.
    
    Args:
        entidades: Dicionário com id_pedido.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_valor_pedido(int(id_pedido))

async def _manipular_data_entrega_pedido(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para consultar data de entrega de um pedido.
    
    Args:
        entidades: Dicionário com id_pedido.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    id_pedido = entidades.get("id_pedido")
    if not id_pedido:
        raise ValueError("Por favor, informe o número do pedido.")
    return ferramentas_sql.construir_query_data_entrega_pedido(int(id_pedido))

async def _manipular_pedidos_por_posicao(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para listar pedidos com uma determinada posição/status.
    
    Args:
        entidades: Dicionário com posicao e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    posicao = entidades.get("posicao")
    if not posicao:
        raise ValueError("Por favor, especifique a posição dos pedidos (ex: 'bloqueado').")
    return ferramentas_sql.construir_query_pedidos_por_posicao(posicao, entidades.get("limite", 20))

async def _manipular_clientes_classificados(entidades: Dict[str, Any]) -> ResultadoQuery:
    """
    Constrói query para buscar clientes classificados por critério de compras.
    
    Args:
        entidades: Dicionário com criterio_classificacao, periodo_tempo e limite.
        
    Returns:
        ResultadoQuery: Tupla com SQL e parâmetros para execução.
    """
    criterio = entidades.get("criterio_classificacao")
    if not criterio:
        raise ValueError("Critério de classificação para clientes não especificado.")
    
    periodo = entidades.get("periodo_tempo")
    if not periodo:
        periodo = "este_mes"
        logger.warning(f"Período não especificado para clientes classificados, usando: {periodo}")
    
    return ferramentas_sql.construir_query_clientes_classificados(
        criterio_classificacao=criterio,
        periodo_tempo=periodo,
        limite=entidades.get("limite", 10)
    )

# Mapeamento de intenções para suas funções manipuladoras
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

async def gerenciar_consulta_usuario(llm: OllamaLLM, texto_usuario: str) -> str:
    """
    Orquestra o processamento completo de uma consulta do usuário.
    
    Esta função coordena todo o fluxo: identificação de intenção,
    construção de query, execução no banco e sumarização dos resultados.
    
    Args:
        llm: Instância do modelo OllamaLLM para processamento de linguagem natural.
        texto_usuario: Pergunta ou comando do usuário em linguagem natural.
        
    Returns:
        str: Resposta formatada em linguagem natural para o usuário.
        
    Examples:
        >>> llm = OllamaLLM(model="llama3.1", base_url="http://localhost:11434")
        >>> resposta = await gerenciar_consulta_usuario(llm, "quais os 5 produtos mais vendidos este mês?")
        >>> print(type(resposta))
        <class 'str'>
        >>> print(len(resposta) > 0)
        True
    """
    logger.info(f"--- INÍCIO DA ORQUESTRAÇÃO PARA: '{texto_usuario}' ---")
    try:
        # Fase 1: Identificar intenção e extrair entidades
        dados_intencao = await obter_intencao(llm, texto_usuario)
        intencao = dados_intencao.intencao
        entidades = dados_intencao.entidades
        
        logger.info(f"Intenção identificada: {intencao}")
        logger.debug(f"Entidades extraídas: {entidades}")

        # Tratamento de casos especiais
        if intencao == "desconhecido":
            return ("Desculpe, não entendi sua solicitação. Você pode perguntar sobre:\n"
                   "• Produtos mais vendidos\n"
                   "• Informações de clientes\n"
                   "• Status de pedidos\n"
                   "• Limites de crédito")
            
        if intencao == "necessita_esclarecimento":
            return dados_intencao.mensagem_esclarecimento or "Por favor, forneça mais detalhes para sua consulta."

        # Fase 2: Obter manipulador apropriado
        manipulador = MAPEAMENTO_INTENCOES.get(intencao)
        if not manipulador:
            logger.error(f"Nenhum manipulador definido para a intenção '{intencao}'.")
            return f"Desculpe, ainda não consigo processar este tipo de consulta: {intencao}"

        # Fase 3: Construir query SQL
        logger.info(f"Executando manipulador para intenção: {intencao}")
        try:
            query_sql, params = await manipulador(entidades)
        except ValueError as ve:
            logger.warning(f"Erro de validação ao construir query: {ve}")
            return f"❌ {str(ve)}"
        
        logger.debug(f"Query SQL gerada: {query_sql}")
        logger.debug(f"Parâmetros: {params}")

        # Fase 4: Executar consulta no banco
        resultado = await executar_consulta_selecao(query_sql, params)
        
        if resultado.get("erro"):
            logger.error(f"Erro na execução da consulta: {resultado['erro']}")
            return "Desculpe, ocorreu um erro ao consultar a base de dados. Por favor, tente novamente."

        dados = resultado.get("dados", [])
        
        if not dados:
            logger.info("Nenhum resultado encontrado para a consulta.")
            return ("Não encontrei nenhum resultado para sua consulta. "
                   "Verifique se os dados estão corretos ou tente com outros parâmetros.")

        logger.info(f"Consulta executada com sucesso. {len(dados)} registros encontrados.")

        # Fase 5: Sumarizar resultados
        resposta_final = await sumarizar_resultados(
            llm=llm,
            pergunta=texto_usuario,
            dados=dados
        )

        logger.info("Orquestração concluída com sucesso.")
        return resposta_final

    except Exception as e:
        logger.error(f"Erro inesperado na orquestração: {e}", exc_info=True)
        return ("Desculpe, ocorreu um erro interno ao processar sua solicitação. "
                "Nossa equipe foi notificada e estamos trabalhando para resolver.")