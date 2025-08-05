# app/db/consultas.py
"""
Módulo de acesso a dados para interação com o banco de dados Oracle.

Versão 2.1: A função `executar_consulta_selecao` foi refatorada para retornar
um dicionário padronizado com as chaves 'dados' e 'erro', melhorando o
tratamento de erros no orquestrador. A função `encontrar_clientes_por_nome_ou_codigo`
também foi ajustada para usar este novo padrão de retorno.
"""

import logging
import asyncio
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# (Assumindo que os helpers e dependências externas estão configurados corretamente)
from helpers_compartilhados.helpers import adicionar_modulo
adicionar_modulo('conexaodb')
from DB_Oracle_Encrypted import testarConexao, conexao
from esperanca_excecao_robos import ExcecaoRobo

# Configura o logger para este módulo
logger = logging.getLogger(__name__)


@contextmanager
def _gerenciar_conexao_bd(nome_bd: str = 'prod'):
    """
    Gerenciador de contexto para conexões com o banco de dados Oracle.

    Garante que a conexão e o cursor sejam abertos e fechados corretamente,
    mesmo em caso de erros.
    """
    if not testarConexao(nome_bd):
        raise ConnectionError("Não foi possível estabelecer conexão com o banco de dados.")

    con = None
    cursor = None
    try:
        con = conexao(nome_bd)
        cursor = con.cursor()
        logger.debug(f"Conexão com o banco '{nome_bd}' estabelecida com sucesso.")
        yield cursor
        con.commit()
    except Exception as e:
        logger.error(f"Erro durante a transação com o banco de dados: {e}", exc_info=True)
        if con:
            con.rollback()
        raise ExcecaoRobo(f"Erro na operação de banco de dados: {e}", type(e).__name__) from e
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()
        logger.debug("Conexão com o banco de dados fechada.")


# --- FUNÇÃO CORRIGIDA ---
async def executar_consulta_selecao(sql: str, params: Optional[Dict[str, Any]] = None, db: str = 'prod') -> Dict[str, Any]:
    """
    Executa uma query SELECT de forma assíncrona e segura, retornando um dicionário.

    Args:
        sql: A string da query SQL a ser executada, com placeholders.
        params: Um dicionário com os parâmetros para a query (bind variables).
        db: O nome do banco de dados a ser consultado.

    Returns:
        Um dicionário com as chaves 'dados' (uma lista de dicionários) e 'erro' (uma string ou None).
    """
    logger.info("Iniciando execução de query SELECT no banco de dados.")

    def _executar_sincronamente() -> Dict[str, Any]:
        """Função interna síncrona para ser executada em uma thread separada."""
        with _gerenciar_conexao_bd(db) as cursor:
            logger.debug(f"Executando SQL: {sql} com parâmetros: {params}")
            cursor.execute(sql, params or {})
            
            # Se a query não retornar colunas (ex: um UPDATE sem RETURNING), retorna lista vazia.
            if not cursor.description:
                return {"dados": [], "erro": None}

            # Constrói a lista de dicionários a partir do resultado
            nomes_colunas = [desc[0].lower() for desc in cursor.description]
            linhas = cursor.fetchall()
            logger.info(f"{len(linhas)} registros retornados do banco.")
            
            dados = [dict(zip(nomes_colunas, linha)) for linha in linhas]
            return {"dados": dados, "erro": None}

    try:
        # Executa a função de I/O de banco de dados (que é síncrona) em uma thread
        # separada para não bloquear o event loop do asyncio.
        return await asyncio.to_thread(_executar_sincronamente)
    except Exception as e:
        logger.error(f"Erro ao executar a consulta: {e}", exc_info=True)
        # Em caso de qualquer exceção, retorna o erro no formato padronizado.
        return {"dados": None, "erro": str(e)}

# --- FUNÇÃO CORRIGIDA E COMPLETADA ---
async def encontrar_clientes_por_nome_ou_codigo(nome: Optional[str] = None, codigo: Optional[int] = None) -> Dict[str, Any]:
    """
    Busca clientes por parte do nome/fantasia ou por código exato.

    Args:
        nome: Parte do nome ou nome fantasia do cliente.
        codigo: Código exato do cliente.

    Returns:
        Um dicionário no formato {'dados': [...], 'erro': None} ou {'dados': None, 'erro': '...'}.
    """
    if not nome and not codigo:
        raise ValueError("Nome ou código do cliente deve ser fornecido.")

    clausulas_where = []
    params = {}

    if codigo:
        clausulas_where.append("CODCLI = :codigo_cliente")
        params["codigo_cliente"] = codigo
    elif nome:
        clausulas_where.append("(LOWER(CLIENTE) LIKE LOWER(:nome_cliente) OR LOWER(FANTASIA) LIKE LOWER(:nome_cliente))")
        params["nome_cliente"] = f"%{nome}%"

    declaracao_where = " AND ".join(clausulas_where)
    
    sql = f"""
        SELECT CODCLI, CLIENTE, FANTASIA
        FROM PCCLIENT
        WHERE {declaracao_where}
        FETCH FIRST 10 ROWS ONLY
    """
    
    # Chama a função principal de execução e retorna seu resultado padronizado
    return await executar_consulta_selecao(sql=sql, params=params)
