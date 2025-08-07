import logging
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from helpers_compartilhados.helpers import configurar_logging
# CORREÇÃO: Importação atualizada para langchain-ollama
from langchain_ollama import OllamaLLM
from app.core.orquestrador import gerenciar_consulta_usuario
from app.core.processador_whatsapp import processador_whatsapp
from app.core.cliente_waha import cliente_waha
from app.core.gerenciador_contexto import gerenciador_contexto

# --- Configuração Inicial ---
load_dotenv()
configurar_logging('log_bot')
logger = logging.getLogger(__name__)


# --- Gerenciamento do Ciclo de Vida (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    Este gerenciador de contexto é executado durante a inicialização e o
    encerramento da API. Ele é responsável por criar e armazenar a instância
    do LLM no estado da aplicação, garantindo que o modelo seja carregado
    apenas uma vez.
    
    Args:
        app: Instância da aplicação FastAPI.
        
    Yields:
        None: Permite que a aplicação execute normalmente entre setup e teardown.
        
    Examples:
        >>> # Usado automaticamente pelo FastAPI
        >>> app = FastAPI(lifespan=lifespan)
    """
    logger.info("Iniciando a API e configurando recursos...")
    base_url = os.getenv("OLLAMA_BASE_URL")
    model = os.getenv("LLM_MODEL")
    
    if not base_url or not model:
        logger.critical("Variáveis de ambiente OLLAMA_BASE_URL ou LLM_MODEL não definidas.")
        raise RuntimeError("As configurações do LLM não foram encontradas no ambiente.")

    logger.info(f"Conectando ao LLM: {model} em {base_url}")
    # CORREÇÃO: Usando OllamaLLM com timeout adequado
    app.state.llm = OllamaLLM(
        model=model,
        base_url=base_url,
        temperature=0.1,
        client_kwargs={"timeout": 120.0},
        keep_alive="30m",
        validate_model_on_init=True
    )
    logger.info("Instância do LLM criada e pronta para uso.")

    await gerenciador_contexto.iniciar()

    yield  # A API fica operacional neste ponto
    
    logger.info("Encerrando a API e limpando recursos...")
    # Limpa os recursos, se necessário
    app.state.llm = None


# --- Injeção de Dependência ---
def obter_llm(request: Request) -> OllamaLLM:
    """
    Função de injeção de dependência para fornecer a instância do LLM.

    O FastAPI injetará o resultado desta função nos endpoints que a declararem
    como uma dependência. Isso evita o uso de globais e facilita os testes.

    Args:
        request: O objeto de requisição do FastAPI.

    Returns:
        OllamaLLM: A instância de OllamaLLM armazenada no estado da aplicação.

    Raises:
        HTTPException: Se a instância do LLM não estiver disponível.
        
    Examples:
        >>> # Em um endpoint
        >>> async def meu_endpoint(llm: OllamaLLM = Depends(obter_llm)):
        >>>     resposta = await llm.ainvoke("Olá!")
    """
    if not hasattr(request.app.state, 'llm') or request.app.state.llm is None:
        logger.error("Tentativa de acesso ao LLM antes da sua inicialização.")
        raise HTTPException(status_code=503, detail="Serviço indisponível: LLM não inicializado.")
    return request.app.state.llm


# --- Definição da API ---
app = FastAPI(
    title="Bot com Arquitetura de Agente",
    version="4.2.0",
    description="""
API que utiliza uma arquitetura de Agente com Ferramentas para consultar um banco de dados de forma conversacional.

**Principais Funcionalidades:**
* **Roteamento de Intenção:** Identifica a intenção do usuário.
* **Construção de Query Segura:** Gera consultas SQL parametrizadas.
* **Sumarização:** Transforma dados brutos em respostas amigáveis.
* **WhatsApp Integration:** Processa mensagens via webhook WAHA.

**Versão 4.2.0 - Melhorias:**
* ✅ Migração para langchain-ollama
* ✅ Timeout configurável para LLM
* ✅ Validação de modelo na inicialização
* ✅ Gerenciamento otimizado de recursos
    """,
    lifespan=lifespan
)


# --- Modelos de Dados (Data Models) ---
class MensagemUsuario(BaseModel):
    """
    Modelo para requisições de chat do usuário.
    
    Attributes:
        id_usuario: Identificador único do usuário que está enviando a mensagem.
        texto: Conteúdo da mensagem/pergunta do usuário.
    """
    id_usuario: str = Field(..., description="Identificador único do usuário.", example="user-123")
    texto: str = Field(..., description="O texto da mensagem enviada pelo usuário.", example="quais os 5 produtos mais vendidos este mês?")


class RespostaBot(BaseModel):
    """
    Modelo para respostas do bot.
    
    Attributes:
        id_usuario: Identificador do usuário (espelhado da requisição).
        resposta: Texto da resposta gerada pelo sistema.
    """
    id_usuario: str = Field(..., description="Identificador único do usuário, espelhado da requisição.")
    resposta: str = Field(..., description="A resposta gerada pelo bot.")


# --- Endpoints da API ---
@app.get("/", summary="Verifica o Status da API", tags=["Status"])
def ler_raiz():
    """
    Endpoint raiz para verificar a operacionalidade da API.
    
    Returns:
        dict: Dicionário com informações sobre o status da API.
        
    Examples:
        >>> # GET /
        >>> {"status": "API operacional", "versao": "4.2.0"}
    """
    return {
        "status": "API operacional. Use o endpoint /chat para interagir.",
        "versao": "4.2.0",
        "llm_engine": "langchain-ollama"
    }


@app.post("/chat", response_model=RespostaBot, summary="Interage com o Bot", tags=["Chat"])
async def endpoint_chat(
    mensagem: MensagemUsuario,
    llm: Annotated[OllamaLLM, Depends(obter_llm)]
):
    """
    Recebe uma mensagem do usuário, processa através do orquestrador e retorna a resposta.
    
    Args:
        mensagem: Objeto contendo o ID do usuário e o texto da mensagem.
        llm: Instância do modelo OllamaLLM (injetada automaticamente).
        
    Returns:
        RespostaBot: Objeto contendo o ID do usuário e a resposta gerada.
        
    Raises:
        HTTPException: Em caso de erro interno do servidor.
        
    Examples:
        >>> # POST /chat
        >>> {
        >>>   "id_usuario": "user123",
        >>>   "texto": "quais os produtos mais vendidos?"
        >>> }
        >>> # Response:
        >>> {
        >>>   "id_usuario": "user123",
        >>>   "resposta": "Aqui estão os produtos mais vendidos..."
        >>> }
    """
    try:
        texto_resposta = await gerenciar_consulta_usuario(llm, mensagem.texto)
        return RespostaBot(id_usuario=mensagem.id_usuario, resposta=texto_resposta)
        
    except Exception as e:
        logger.error(f"Erro crítico no endpoint /chat para o usuário '{mensagem.id_usuario}': {e}", exc_info=True)
        # Em um ambiente de produção, o detalhe do erro não deveria ser exposto.
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno no servidor ao processar sua solicitação.")


@app.post("/webhook/whatsapp", summary="Webhook do WhatsApp", tags=["WhatsApp"])
async def webhook_whatsapp(
    request: Request,
    llm: Annotated[OllamaLLM, Depends(obter_llm)]
):
    """
    Recebe webhooks do WAHA para processar mensagens do WhatsApp.
    
    Args:
        request: Objeto de requisição contendo os dados do webhook.
        llm: Instância do modelo OllamaLLM (injetada automaticamente).
        
    Returns:
        dict: Confirmação de recebimento do webhook.
        
    Raises:
        HTTPException: Em caso de erro no processamento do webhook.
        
    Examples:
        >>> # POST /webhook/whatsapp
        >>> {
        >>>   "payload": {
        >>>     "event": "message",
        >>>     "data": {
        >>>       "from": "5511999999999@c.us",
        >>>       "body": "Olá, como posso ajudar?"
        >>>     }
        >>>   }
        >>> }
    """
    try:
        webhook_data = await request.json()
        logger.info(f"Webhook recebido: {webhook_data}")
        
        # Processar mensagem em background para resposta rápida
        asyncio.create_task(
            processador_whatsapp.processar_mensagem(llm, webhook_data)
        )
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Erro no webhook do WhatsApp: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao processar webhook")


@app.get("/whatsapp/status", summary="Status do WhatsApp", tags=["WhatsApp"])
async def status_whatsapp():
    """
    Verifica o status da conexão com WhatsApp.
    
    Returns:
        dict: Informações sobre o status da conexão WhatsApp.
        
    Examples:
        >>> # GET /whatsapp/status
        >>> {
        >>>   "whatsapp_conectado": True,
        >>>   "session_name": "default",
        >>>   "status": "WORKING"
        >>> }
    """
    try:
        status_info = await cliente_waha.verificar_sessao()
        return {
            "whatsapp_conectado": status_info.get("conectado", False),
            "session_name": cliente_waha.config.session_name,
            "status": status_info.get("status", "unknown"),
            "qr_code": status_info.get("qr_code")
        }
    except Exception as e:
        logger.error(f"Erro ao verificar status do WhatsApp: {e}")
        return {
            "whatsapp_conectado": False,
            "status": "erro",
            "mensagem": str(e)
        }


@app.post("/whatsapp/iniciar", summary="Iniciar Sessão WhatsApp", tags=["WhatsApp"])
async def iniciar_whatsapp():
    """
    Inicia uma nova sessão do WhatsApp.
    
    Returns:
        dict: Resultado da tentativa de iniciar a sessão.
        
    Examples:
        >>> # POST /whatsapp/iniciar
        >>> {
        >>>   "status": "success",
        >>>   "mensagem": "Sessão iniciada com sucesso"
        >>> }
    """
    try:
        resultado = await cliente_waha.iniciar_sessao()
        if resultado.get("sucesso"):
            return {
                "status": "success", 
                "mensagem": "Sessão iniciada com sucesso",
                "qr_code": resultado.get("qr_code")
            }
        else:
            return {
                "status": "error", 
                "mensagem": f"Falha ao iniciar sessão: {resultado.get('erro')}"
            }
    except Exception as e:
        logger.error(f"Erro ao iniciar sessão do WhatsApp: {e}")
        raise HTTPException(status_code=500, detail="Erro ao iniciar sessão")
