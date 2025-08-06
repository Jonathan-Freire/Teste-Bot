# app/main.py
"""
Ponto de entrada principal da API.

Este módulo configura e executa a aplicação FastAPI, gerenciando o ciclo de vida
de recursos essenciais, como a instância do modelo de linguagem (LLM), e
define os endpoints da API.
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from helpers_compartilhados.helpers import configurar_logging
from langchain_community.chat_models.ollama import ChatOllama
from app.core.orquestrador import gerenciar_consulta_usuario
from app.core.processador_whatsapp import processador_whatsapp
from app.core.cliente_waha import cliente_waha

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
    """
    logger.info("Iniciando a API e configurando recursos...")
    base_url = os.getenv("OLLAMA_BASE_URL")
    model = os.getenv("LLM_MODEL")
    
    if not base_url or not model:
        logger.critical("Variáveis de ambiente OLLAMA_BASE_URL ou LLM_MODEL não definidas.")
        raise RuntimeError("As configurações do LLM não foram encontradas no ambiente.")

    logger.info(f"Conectando ao LLM: {model} em {base_url}")
    # Armazena a instância do LLM no estado da aplicação (app.state)
    app.state.llm = ChatOllama(base_url=base_url, model=model)
    logger.info("Instância do LLM criada e pronta para uso.")
    
    yield  # A API fica operacional neste ponto
    
    logger.info("Encerrando a API e limpando recursos...")
    # Limpa os recursos, se necessário
    app.state.llm = None


# --- Injeção de Dependência ---
def obter_llm(request: Request) -> ChatOllama:
    """
    Função de injeção de dependência para fornecer a instância do LLM.

    O FastAPI injetará o resultado desta função nos endpoints que a declararem
    como uma dependência. Isso evita o uso de globais e facilita os testes.

    Args:
        request: O objeto de requisição do FastAPI.

    Returns:
        A instância de ChatOllama armazenada no estado da aplicação.

    Raises:
        HTTPException: Se a instância do LLM não estiver disponível.
    """
    if not hasattr(request.app.state, 'llm') or request.app.state.llm is None:
        logger.error("Tentativa de acesso ao LLM antes da sua inicialização.")
        raise HTTPException(status_code=503, detail="Serviço indisponível: LLM não inicializado.")
    return request.app.state.llm


# --- Definição da API ---
app = FastAPI(
    title="Bot com Arquitetura de Agente",
    version="4.0.0",
    description="""
API que utiliza uma arquitetura de Agente com Ferramentas para consultar um banco de dados de forma conversacional.

**Principais Funcionalidades:**
* **Roteamento de Intenção:** Identifica a intenção do usuário.
* **Construção de Query Segura:** Gera consultas SQL parametrizadas.
* **Sumarização:** Transforma dados brutos em respostas amigáveis.
    """,
    lifespan=lifespan
)


# --- Modelos de Dados (Data Models) ---
class MensagemUsuario(BaseModel):
    id_usuario: str = Field(..., description="Identificador único do usuário.", example="user-123")
    texto: str = Field(..., description="O texto da mensagem enviada pelo usuário.", example="quais os 5 produtos mais vendidos?")


class RespostaBot(BaseModel):
    id_usuario: str = Field(..., description="Identificador único do usuário, espelhado da requisição.")
    resposta: str = Field(..., description="A resposta gerada pelo bot.")


# --- Endpoints da API ---
@app.get("/", summary="Verifica o Status da API", tags=["Status"])
def ler_raiz():
    """Endpoint raiz para verificar a operacionalidade da API."""
    return {"status": "API operacional. Use o endpoint /chat para interagir."}


@app.post("/chat", response_model=RespostaBot, summary="Interage com o Bot", tags=["Chat"])
async def endpoint_chat(
    mensagem: MensagemUsuario,
    llm: Annotated[ChatOllama, Depends(obter_llm)]
):
    """
    Recebe uma mensagem do usuário, processa através do orquestrador e retorna a resposta.
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
    llm: Annotated[ChatOllama, Depends(obter_llm)]
):
    """
    Recebe webhooks do WAHA para processar mensagens do WhatsApp.
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
    """
    try:
        sessao_ativa = await cliente_waha.verificar_sessao()
        return {
            "whatsapp_conectado": sessao_ativa,
            "session_name": cliente_waha.session_name,
            "status": "conectado" if sessao_ativa else "desconectado"
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
    """
    try:
        sucesso = await cliente_waha.iniciar_sessao()
        if sucesso:
            return {"status": "success", "mensagem": "Sessão iniciada com sucesso"}
        else:
            return {"status": "error", "mensagem": "Falha ao iniciar sessão"}
    except Exception as e:
        logger.error(f"Erro ao iniciar sessão do WhatsApp: {e}")
        raise HTTPException(status_code=500, detail="Erro ao iniciar sessão")

