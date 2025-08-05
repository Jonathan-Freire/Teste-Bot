# app/agentes/agente_sumarizador.py
"""
Módulo responsável por sumarizar resultados de consultas.

Este agente recebe dados brutos (geralmente de um banco de dados) e a pergunta
original do usuário. Ele utiliza um modelo de linguagem (LLM) para transformar
esses dados em uma resposta em linguagem natural, formatada de maneira clara
e amigável para o usuário final.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models.ollama import ChatOllama

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Template do prompt com uma persona definida e instruções detalhadas
template_prompt = """
Você é um assistente de vendas da Comercial Esperança, especialista em analisar dados. Sua tarefa é transformar dados brutos de consultas em respostas claras, amigáveis e úteis para o usuário.

**Contexto Fornecido:**
- **Pergunta original do usuário:** "{pergunta}"
- **Dados encontrados no banco de dados (em formato JSON):**
{dados}

**Instruções para a Resposta:**
1.  **Seja Direto e Claro:** Comece respondendo diretamente à pergunta do usuário.
2.  **Formate Listas de Forma Legível:** Se os dados forem uma lista (produtos, pedidos, etc.), use uma tabela simples em markdown ou uma lista com marcadores (bullet points) para facilitar a leitura.
3.  **Adote uma Linguagem Humana:** Use uma linguagem natural e prestativa. Em vez de "a query retornou 5 linhas", diga algo como "Encontrei 5 produtos que correspondem à sua busca:".
4.  **Trate a Ausência de Dados:** Se o JSON de dados estiver vazio (`[]` ou `null`), informe ao usuário de forma amigável que não encontrou resultados. Exemplo: "Não encontrei nenhum pedido para o cliente informado nesse período."
5.  **Não Invente Informações:** Baseie sua resposta estritamente nos dados fornecidos. Não adicione informações que não estão presentes no JSON.
6.  **Mantenha a Simplicidade:** Evite jargões técnicos. O objetivo é ser útil para um vendedor, não para um analista de dados.

Formule sua resposta final abaixo:
"""

# Cria o prompt a partir do template
prompt = ChatPromptTemplate.from_template(template=template_prompt)

async def sumarizar_resultados(
    llm: ChatOllama, 
    pergunta: str, 
    dados: Optional[List[Dict[str, Any]]]
) -> str:
    """
    Gera um resumo em linguagem natural a partir de dados de uma consulta.

    Args:
        llm: A instância do modelo de linguagem (ChatOllama) a ser usada.
        pergunta: A pergunta original feita pelo usuário.
        dados: Uma lista de dicionários contendo os dados retornados pela
               consulta ao banco de dados. Pode ser None ou vazia se nada
               for encontrado.

    Returns:
        Uma string contendo a resposta sumarizada e formatada para o usuário.
        Retorna uma mensagem de erro amigável se a sumarização falhar.
    """
    logger.info("Iniciando a sumarização dos resultados.")
    
    # Tratamento para quando a consulta não retorna dados
    if not dados:
        logger.warning("Não há dados para sumarizar. Retornando mensagem contextual.")
        if "pedido" in pergunta.lower():
            return "Não encontrei nenhum pedido que corresponda à sua busca. Por favor, verifique o número ou o cliente e tente novamente."
        if "produto" in pergunta.lower():
            return "Não encontrei nenhum produto com os critérios informados."
        return "Desculpe, não foram encontrados resultados para a sua consulta no banco de dados."

    # Constrói a cadeia de processamento: prompt -> llm
    cadeia_processamento = prompt | llm
    
    try:
        # Converte a lista de dados para uma string JSON formatada
        # Usa `default=str` para lidar com tipos não serializáveis (como datas)
        # `ensure_ascii=False` para garantir a correta exibição de caracteres em português
        dados_json_str = json.dumps(dados, indent=2, default=str, ensure_ascii=False)
        
        logger.debug(f"Enviando {len(dados)} registros para sumarização.")
        
        # Invoca a cadeia com a pergunta e os dados
        resposta = await cadeia_processamento.ainvoke({
            "pergunta": pergunta, 
            "dados": dados_json_str
        })
        
        logger.info("Sumarização gerada com sucesso.")
        return resposta.content.strip()
        
    except Exception as e:
        logger.error(f"Erro ao sumarizar resultados com o LLM: {e}", exc_info=True)
        return "Tive um problema ao tentar interpretar os dados encontrados. Por favor, tente sua consulta novamente."

