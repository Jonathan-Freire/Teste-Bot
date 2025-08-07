# app/agentes/agente_sumarizador.py
"""
Módulo responsável por sumarizar resultados de consultas.

Versão 2.1: Corrigidas importações do LangChain e compatibilidade Python 3.10.11
Mantém a persona de um assistente prestativo e a capacidade de sugerir
próximas ações, tornando a interação mais natural e guiada.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.llms.ollama import Ollama

logger = logging.getLogger(__name__)

# Template do prompt aprimorado com mais instruções de formatação.
template_prompt = """
Você é um assistente de vendas da Comercial Esperança, especialista em analisar dados. Sua tarefa é transformar dados brutos de consultas em respostas claras, amigáveis e úteis para o usuário.

**Contexto Fornecido:**
- **Pergunta original do usuário:** "{pergunta}"
- **Dados encontrados no banco de dados (em formato JSON):**
{dados}

**Instruções para a Resposta:**
1.  **Seja Direto e Claro:** Comece respondendo diretamente à pergunta do usuário.
2.  **Formate os Dados de Forma Inteligente:**
    - **Listas (produtos, clientes, pedidos):** Use tabelas em markdown ou listas com marcadores.
    - **Endereços:** Formate em múltiplas linhas (Rua, Bairro, Cidade/Estado, CEP).
    - **Status de Cliente:** Se o campo 'BLOQUEIO' for 'S', diga "Sim, o cliente está bloqueado". Se for 'N', diga "Não, o cliente está ativo".
    - **Valores Monetários:** Formate como moeda (ex: R$ 1.234,56).
3.  **Adote uma Linguagem Humana:** Use uma linguagem natural e prestativa. Em vez de "a query retornou 1 linha", diga "Encontrei as informações que você pediu:".
4.  **Trate a Ausência de Dados:** Se o JSON de dados estiver vazio (`[]` ou `null`), informe ao usuário de forma amigável que não encontrou resultados para aquela consulta específica.
5.  **Não Invente Informações:** Baseie sua resposta estritamente nos dados fornecidos.
6.  **Seja Proativo:** Ao final da resposta, se apropriado, sugira uma próxima ação. 
    - Se listou pedidos, sugira: "Deseja ver os itens de algum desses pedidos? Basta me dizer o número."
    - Se mostrou um cliente, sugira: "Posso verificar o limite de crédito ou os últimos pedidos dele para você."

Formule sua resposta final abaixo:
"""

prompt = ChatPromptTemplate.from_template(template=template_prompt)

async def sumarizar_resultados(
    llm: Ollama, 
    pergunta: str, 
    dados: Optional[List[Dict[str, Any]]]
) -> str:
    """
    Gera um resumo em linguagem natural a partir de dados de uma consulta.
    
    Args:
        llm: Instância do modelo Ollama para processamento de linguagem natural.
        pergunta: A pergunta original do usuário que gerou os dados.
        dados: Lista de dicionários com os dados retornados da consulta.
    
    Returns:
        str: Resposta formatada em linguagem natural para o usuário.
        
    Examples:
        >>> llm = Ollama(base_url="http://localhost:11434", model="llama3.1")
        >>> dados = [{"codprod": 123, "descricao": "Produto X", "pvenda": 10.50}]
        >>> resposta = await sumarizar_resultados(llm, "quais produtos?", dados)
        >>> print(resposta)
        "Encontrei as informações que você pediu:..."
    """
    logger.info("Iniciando a sumarização dos resultados.")
    
    if not dados:
        logger.warning("Não há dados para sumarizar. Retornando mensagem contextual.")
        return "Desculpe, não encontrei nenhum resultado para a sua consulta no banco de dados."

    cadeia_processamento = prompt | llm
    
    try:
        dados_json_str = json.dumps(dados, indent=2, default=str, ensure_ascii=False)
        
        logger.debug(f"Enviando {len(dados)} registros para sumarização.")
        
        resposta = await cadeia_processamento.ainvoke({
            "pergunta": pergunta, 
            "dados": dados_json_str
        })
        
        logger.info("Sumarização gerada com sucesso.")
        # Corrigida para acessar o conteúdo corretamente
        if hasattr(resposta, 'content'):
            return resposta.content.strip()
        else:
            return str(resposta).strip()
        
    except Exception as e:
        logger.error(f"Erro ao sumarizar resultados com o LLM: {e}", exc_info=True)
        return "Tive um problema ao tentar interpretar os dados encontrados. Por favor, tente sua consulta novamente."