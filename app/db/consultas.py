"""
Módulo de acesso a dados para interação com o banco de dados Oracle.

Este módulo encapsula toda a lógica para executar consultas SQL, garantindo
práticas seguras (como o uso de prepared statements para prevenir SQL Injection)
e um gerenciamento de conexão eficiente.
"""

import logging
import asyncio
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Importações de módulos customizados do projeto
# [Nota]: A dependência de 'adicionar_modulo' sugere uma configuração de path
# que poderia ser substituída por uma estrutura de pacotes Python padrão.
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

    Args:
        nome_bd: O nome do banco de dados para conectar ('prod', 'dev', etc.).

    Yields:
        O objeto cursor pronto para execução de queries.

    Raises:
        ConnectionError: Se não for possível estabelecer conexão com o BD.
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
        # Re-levanta a exceção para ser tratada pela camada de serviço
        raise ExcecaoRobo(f"Erro na operação de banco de dados: {e}", type(e).__name__) from e
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()
        logger.debug("Conexão com o banco de dados fechada.")


async def executar_consulta_selecao(sql: str, params: Optional[Dict[str, Any]] = None, db: str = 'prod') -> List[Dict[str, Any]]:
    """
    Executa uma query SELECT de forma assíncrona e segura.

    Args:
        sql: A string da query SQL a ser executada, com placeholders.
        params: Um dicionário com os parâmetros para a query (bind variables).
        db: O nome do banco de dados a ser consultado.

    Returns:
        Uma lista de dicionários, onde cada dicionário representa uma linha do resultado.

    Raises:
        ExcecaoRobo: Em caso de erro na execução da query.
    """
    logger.info("Iniciando execução de query SELECT no banco de dados.")

    def _executar_sincronamente() -> List[Dict[str, Any]]:
        with _gerenciar_conexao_bd(db) as cursor:
            logger.debug(f"Executando SQL: {sql} com parâmetros: {params}")
            cursor.execute(sql, params or {})
            
            if not cursor.description:
                return []

            nomes_colunas = [desc[0].lower() for desc in cursor.description]
            linhas = cursor.fetchall()
            logger.info(f"{len(linhas)} registros retornados do banco.")
            
            return [dict(zip(nomes_colunas, linha)) for linha in linhas]

    try:
        # Executa a função de I/O síncrona em uma thread separada
        return await asyncio.to_thread(_executar_sincronamente)
    except (ExcecaoRobo, ConnectionError) as e:
        # Propaga a exceção para ser tratada no orquestrador
        raise e


async def encontrar_clientes_por_nome_ou_codigo(nome: Optional[str] = None, codigo: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Busca clientes por parte do nome/fantasia ou por código exato usando prepared statements.

    Args:
        nome: Parte do nome ou nome fantasia do cliente.
        codigo: Código exato do cliente.

    Returns:
        Uma lista de dicionários com os dados dos clientes encontrados.

    Raises:
        ValueError: Se nem nome nem código forem fornecidos.
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