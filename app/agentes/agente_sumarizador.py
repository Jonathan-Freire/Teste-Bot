# app/agentes/agente_sumarizador.py
"""
Agente Sumarizador - Transforma dados brutos em linguagem natural.

Este módulo é responsável por converter os resultados de consultas SQL
em respostas amigáveis e compreensíveis para o usuário final.

Versão 2.0: Tratamento robusto de respostas do OllamaLLM.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM

logger = logging.getLogger(__name__)

# Template do prompt aprimorado com mais instruções de formatação
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
    - **Datas:** Formate como DD/MM/AAAA.
    - **Posição de Pedidos:** L=Liberado, B=Bloqueado, P=Pendente, F=Faturado
3.  **Adote uma Linguagem Humana:** Use uma linguagem natural e prestativa. Em vez de "a query retornou 1 linha", diga "Encontrei as informações que você pediu:".
4.  **Trate a Ausência de Dados:** Se o JSON de dados estiver vazio (`[]` ou `null`), informe ao usuário de forma amigável que não encontrou resultados para aquela consulta específica.
5.  **Não Invente Informações:** Baseie sua resposta estritamente nos dados fornecidos.
6.  **Seja Proativo:** Ao final da resposta, se apropriado, sugira uma próxima ação. 
    - Se listou pedidos, sugira: "Deseja ver os itens de algum desses pedidos? Basta me dizer o número."
    - Se mostrou um cliente, sugira: "Posso verificar o limite de crédito ou os últimos pedidos dele para você."
    - Se mostrou produtos, sugira: "Gostaria de ver mais detalhes sobre algum produto específico?"

**Formatação Especial:**
- Para valores monetários, use o formato brasileiro: R$ 1.234,56
- Para percentuais, use: 15,5%
- Para quantidades grandes, use separador de milhares: 1.234 unidades

Formule sua resposta final abaixo:
"""

prompt = ChatPromptTemplate.from_template(template=template_prompt)


async def sumarizar_resultados(
    llm: OllamaLLM, 
    pergunta: str, 
    dados: Optional[List[Dict[str, Any]]]
) -> str:
    """
    Gera um resumo em linguagem natural a partir de dados de uma consulta.
    
    Transforma resultados brutos de consultas SQL em respostas amigáveis
    e bem formatadas para o usuário final, incluindo formatação de valores
    monetários, datas e sugestões de próximas ações.
    
    Args:
        llm: Instância do modelo OllamaLLM para processamento de linguagem natural.
        pergunta: A pergunta original do usuário que gerou os dados.
        dados: Lista de dicionários com os dados retornados da consulta.
    
    Returns:
        str: Resposta formatada em linguagem natural para o usuário.
        
    Examples:
        >>> llm = OllamaLLM(model="llama3.1", base_url="http://localhost:11434")
        >>> dados = [{"codprod": 123, "descricao": "Produto X", "pvenda": 10.50}]
        >>> resposta = await sumarizar_resultados(llm, "quais produtos?", dados)
        >>> print(resposta)
        "Encontrei as informações que você pediu:..."
        
        >>> # Exemplo com dados vazios
        >>> resposta = await sumarizar_resultados(llm, "produtos inexistentes", [])
        >>> print(resposta)
        "Desculpe, não encontrei nenhum resultado para a sua consulta no banco de dados."
        
        >>> # Exemplo com múltiplos registros
        >>> dados = [
        ...     {"codprod": 1, "descricao": "Produto A", "pvenda": 100.00},
        ...     {"codprod": 2, "descricao": "Produto B", "pvenda": 200.00}
        ... ]
        >>> resposta = await sumarizar_resultados(llm, "produtos mais caros", dados)
        >>> # Resposta conterá formatação em lista ou tabela
    """
    logger.info("Iniciando a sumarização dos resultados.")
    
    # Validação de entrada
    if not dados:
        logger.warning("Não há dados para sumarizar. Retornando mensagem contextual.")
        return (
            "Desculpe, não encontrei nenhum resultado para a sua consulta no banco de dados. "
            "Isso pode acontecer se:\n"
            "• Os critérios de busca estão muito específicos\n"
            "• O período selecionado não tem movimentação\n"
            "• O item pesquisado não existe no cadastro\n\n"
            "Tente ajustar os parâmetros da sua busca ou me pergunte de outra forma."
        )
    
    # Pré-processar dados para melhor formatação
    dados_processados = _preprocessar_dados(dados)
    
    cadeia_processamento = prompt | llm
    
    try:
        # Serializar dados com formatação adequada
        dados_json_str = json.dumps(
            dados_processados, 
            indent=2, 
            default=str, 
            ensure_ascii=False
        )
        
        logger.debug(f"Enviando {len(dados)} registros para sumarização.")
        
        # Invocar o LLM
        resposta_raw = await cadeia_processamento.ainvoke({
            "pergunta": pergunta, 
            "dados": dados_json_str
        })
        
        logger.info("Sumarização gerada com sucesso.")
        
        # Extrair texto da resposta (tratamento robusto)
        resultado = _extrair_texto_resposta(resposta_raw)
        
        # Validar resposta
        if not resultado or len(resultado.strip()) < 10:
            logger.warning("Resposta da IA muito curta ou vazia, usando fallback.")
            return _gerar_resposta_fallback(pergunta, dados)
        
        # Pós-processar resposta (adicionar formatações extras se necessário)
        resultado_final = _pos_processar_resposta(resultado, dados)
        
        return resultado_final
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao serializar dados JSON: {e}", exc_info=True)
        return _gerar_resposta_fallback(pergunta, dados)
        
    except Exception as e:
        logger.error(f"Erro ao sumarizar resultados com o LLM: {e}", exc_info=True)
        return _gerar_resposta_fallback(pergunta, dados)


def _extrair_texto_resposta(resposta_raw: Any) -> str:
    """
    Extrai texto de diferentes tipos de resposta do OllamaLLM.
    
    Trata diferentes formatos de resposta que o OllamaLLM pode retornar,
    garantindo compatibilidade com diferentes versões da biblioteca.
    
    Args:
        resposta_raw: Resposta bruta do OllamaLLM.
        
    Returns:
        str: Texto extraído da resposta.
        
    Examples:
        >>> # Se resposta é string direta
        >>> texto = _extrair_texto_resposta("Resposta direta")
        >>> print(texto)
        "Resposta direta"
        
        >>> # Se resposta tem atributo content
        >>> from types import SimpleNamespace
        >>> resp = SimpleNamespace(content="Resposta com content")
        >>> texto = _extrair_texto_resposta(resp)
        >>> print(texto)
        "Resposta com content"
    """
    # Tentar diferentes formas de extrair o texto
    if isinstance(resposta_raw, str):
        return resposta_raw.strip()
    
    # Tentar acessar atributo content
    if hasattr(resposta_raw, 'content'):
        return str(resposta_raw.content).strip()
    
    # Tentar acessar atributo text
    if hasattr(resposta_raw, 'text'):
        return str(resposta_raw.text).strip()
    
    # Tentar converter para string diretamente
    return str(resposta_raw).strip()


def _preprocessar_dados(dados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pré-processa dados para melhor apresentação.
    
    Formata valores monetários, datas e outros campos especiais
    antes de enviar para o LLM.
    
    Args:
        dados: Lista de dicionários com dados brutos.
        
    Returns:
        Lista de dicionários com dados formatados.
        
    Examples:
        >>> dados = [{"pvenda": 100.50, "data": "2024-01-15"}]
        >>> processados = _preprocessar_dados(dados)
        >>> print(processados[0]["pvenda"])
        100.5
    """
    dados_processados = []
    
    for registro in dados:
        registro_processado = {}
        
        for chave, valor in registro.items():
            # Processar valores específicos
            if chave.lower() in ['pvenda', 'vltotal', 'limcred', 'valor_total_gasto']:
                # Valores monetários - manter como número
                registro_processado[chave] = valor
            elif chave.lower() in ['data', 'dtcadastro', 'dtentrega', 'dtexclusao', 'dtbloq']:
                # Datas - manter formato original (o LLM formatará)
                registro_processado[chave] = valor
            elif chave.lower() == 'posicao':
                # Mapear códigos de posição
                mapa_posicao = {
                    'L': 'Liberado',
                    'B': 'Bloqueado', 
                    'P': 'Pendente',
                    'F': 'Faturado'
                }
                registro_processado[chave] = mapa_posicao.get(valor, valor)
            elif chave.lower() == 'bloqueio':
                # Mapear status de bloqueio
                registro_processado[chave] = 'Bloqueado' if valor == 'S' else 'Ativo'
            else:
                registro_processado[chave] = valor
        
        dados_processados.append(registro_processado)
    
    return dados_processados


def _gerar_resposta_fallback(pergunta: str, dados: List[Dict[str, Any]]) -> str:
    """
    Gera uma resposta básica quando o LLM falha.
    
    Cria uma resposta estruturada básica para garantir que o usuário
    sempre receba alguma informação útil, mesmo em caso de falha.
    
    Args:
        pergunta: Pergunta original do usuário.
        dados: Dados da consulta.
        
    Returns:
        str: Resposta fallback formatada.
        
    Examples:
        >>> dados = [{"codprod": 1, "descricao": "Produto"}]
        >>> resposta = _gerar_resposta_fallback("produtos?", dados)
        >>> print("Encontrei" in resposta)
        True
    """
    try:
        num_registros = len(dados)
        
        if num_registros == 1:
            # Um único registro - mostrar detalhes
            registro = dados[0]
            linhas = ["Encontrei 1 resultado para sua consulta:\n"]
            
            for chave, valor in registro.items():
                chave_formatada = chave.replace('_', ' ').title()
                linhas.append(f"• **{chave_formatada}**: {valor}")
            
            return "\n".join(linhas)
        else:
            # Múltiplos registros - mostrar resumo
            resposta = f"Encontrei {num_registros} resultados para sua consulta.\n\n"
            
            # Mostrar primeiros 5 registros
            for i, registro in enumerate(dados[:5], 1):
                resposta += f"**Resultado {i}:**\n"
                
                # Mostrar apenas campos principais
                campos_principais = []
                for chave, valor in registro.items():
                    if chave.lower() in ['codprod', 'descricao', 'cliente', 'codcli', 'numped', 'pvenda', 'vltotal']:
                        campos_principais.append(f"{chave}: {valor}")
                
                if campos_principais:
                    resposta += " | ".join(campos_principais[:3]) + "\n\n"
            
            if num_registros > 5:
                resposta += f"... e mais {num_registros - 5} resultados.\n"
            
            return resposta
            
    except Exception as e:
        logger.error(f"Erro ao gerar resposta fallback: {e}")
        return (
            "Encontrei dados para sua consulta, mas houve um problema ao formatá-los. "
            "Por favor, tente fazer sua pergunta de forma mais específica."
        )


def _pos_processar_resposta(resposta: str, dados: List[Dict[str, Any]]) -> str:
    """
    Pós-processa a resposta do LLM para adicionar formatações extras.
    
    Adiciona elementos visuais e sugestões contextuais baseadas
    no tipo de dados retornados.
    
    Args:
        resposta: Resposta gerada pelo LLM.
        dados: Dados originais da consulta.
        
    Returns:
        str: Resposta pós-processada.
        
    Examples:
        >>> resposta = "Lista de produtos"
        >>> dados = [{"codprod": 1}]
        >>> final = _pos_processar_resposta(resposta, dados)
        >>> print(len(final) > len(resposta))
        True
    """
    # Adicionar estatísticas se relevante
    if len(dados) > 10:
        resposta += f"\n\n📊 **Resumo:** Total de {len(dados)} registros encontrados."
    
    # Adicionar sugestões baseadas no conteúdo
    if any('codprod' in d for d in dados):
        if not any(sugestao in resposta.lower() for sugestao in ['posso', 'gostaria', 'deseja']):
            resposta += "\n\n💡 **Próximos passos:** Posso mostrar mais detalhes sobre algum produto específico ou ajudar com outra consulta."
    
    elif any('codcli' in d for d in dados):
        if not any(sugestao in resposta.lower() for sugestao in ['posso', 'gostaria', 'deseja']):
            resposta += "\n\n💡 **Próximos passos:** Posso verificar pedidos, limite de crédito ou outras informações desses clientes."
    
    elif any('numped' in d for d in dados):
        if not any(sugestao in resposta.lower() for sugestao in ['posso', 'gostaria', 'deseja']):
            resposta += "\n\n💡 **Próximos passos:** Posso mostrar os itens de algum pedido ou verificar outros períodos."
    
    return resposta