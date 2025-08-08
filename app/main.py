# app/main.py
"""
API Principal do Bot WhatsApp com Arquitetura de Agentes.

Este módulo implementa a API FastAPI que serve como interface principal
do sistema, gerenciando requisições HTTP, webhooks do WhatsApp e
coordenando todas as operações do bot.

Versão 5.0: Gerenciamento robusto de tasks assíncronas e melhor tratamento de erros.
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Set, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis de ambiente antes de importações locais

from helpers_compartilhados.helpers import configurar_logging
from langchain_ollama import OllamaLLM
from app.core.orquestrador import gerenciar_consulta_usuario
from app.core.processador_whatsapp import processador_whatsapp
from app.core.cliente_waha import cliente_waha
from app.core.gerenciador_contexto import gerenciador_contexto

# --- Configuração Inicial ---
configurar_logging('log_bot')
logger = logging.getLogger(__name__)


# --- Gerenciamento de Tasks ---
class GerenciadorTasks:
    """
    Gerenciador centralizado de tasks assíncronas.
    
    Mantém controle de todas as tasks em execução para garantir
    que sejam finalizadas adequadamente no shutdown da aplicação.
    
    Attributes:
        tasks: Conjunto de tasks em execução.
        max_tasks: Número máximo de tasks simultâneas permitidas.
        _lock: Lock para operações thread-safe.
    """
    
    def __init__(self, max_tasks: int = 100):
        """
        Inicializa o gerenciador de tasks.
        
        Args:
            max_tasks: Número máximo de tasks simultâneas.
            
        Examples:
            >>> gerenciador = GerenciadorTasks(max_tasks=50)
            >>> print(gerenciador.max_tasks)
            50
        """
        self.tasks: Set[asyncio.Task] = set()
        self.max_tasks = max_tasks
        self._lock = asyncio.Lock()
        
    async def adicionar_task(self, coro) -> asyncio.Task:
        """
        Adiciona e rastreia uma nova task.
        
        Args:
            coro: Corrotina a ser executada.
            
        Returns:
            asyncio.Task: Task criada.
            
        Raises:
            RuntimeError: Se o limite de tasks for atingido.
            
        Examples:
            >>> async def minha_funcao():
            ...     await asyncio.sleep(1)
            >>> task = await gerenciador.adicionar_task(minha_funcao())
        """
        async with self._lock:
            # Limpar tasks finalizadas
            self.limpar_finalizadas()
            
            # Verificar limite
            if len(self.tasks) >= self.max_tasks:
                logger.warning(f"Limite de tasks atingido: {len(self.tasks)}/{self.max_tasks}")
                raise RuntimeError("Limite de tasks simultâneas atingido")
            
            # Criar e rastrear task
            task = asyncio.create_task(coro)
            self.tasks.add(task)
            
            # Adicionar callback para remover task quando finalizar
            task.add_done_callback(self._remover_task)
            
            logger.debug(f"Task adicionada. Total em execução: {len(self.tasks)}")
            return task
    
    def _remover_task(self, task: asyncio.Task):
        """
        Remove task do conjunto quando finalizada.
        
        Args:
            task: Task finalizada.
        """
        self.tasks.discard(task)
        
        # Log de erros se a task falhou
        if task.done() and not task.cancelled():
            try:
                exception = task.exception()
                if exception:
                    logger.error(f"Task falhou com exceção: {exception}")
            except Exception:
                pass
    
    def limpar_finalizadas(self):
        """
        Remove tasks finalizadas do conjunto.
        
        Examples:
            >>> gerenciador.limpar_finalizadas()
        """
        finalizadas = {task for task in self.tasks if task.done()}
        self.tasks -= finalizadas
        
        if finalizadas:
            logger.debug(f"Removidas {len(finalizadas)} tasks finalizadas")
    
    async def aguardar_todas(self, timeout: float = 30):
        """
        Aguarda todas as tasks finalizarem.
        
        Args:
            timeout: Tempo máximo de espera em segundos.
            
        Examples:
            >>> await gerenciador.aguardar_todas(timeout=60)
        """
        if not self.tasks:
            return
        
        logger.info(f"Aguardando {len(self.tasks)} tasks finalizarem...")
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True),
                timeout=timeout
            )
            logger.info("Todas as tasks finalizaram")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout aguardando tasks. {len(self.tasks)} ainda em execução")
            # Cancelar tasks restantes
            for task in self.tasks:
                if not task.done():
                    task.cancel()
    
    def obter_estatisticas(self) -> dict:
        """
        Retorna estatísticas das tasks.
        
        Returns:
            dict: Estatísticas do gerenciador.
            
        Examples:
            >>> stats = gerenciador.obter_estatisticas()
            >>> print(stats["em_execucao"])
            5
        """
        self.limpar_finalizadas()
        return {
            "em_execucao": len(self.tasks),
            "max_permitido": self.max_tasks,
            "porcentagem_uso": (len(self.tasks) / self.max_tasks) * 100 if self.max_tasks > 0 else 0
        }


# Instância global do gerenciador de tasks
gerenciador_tasks = GerenciadorTasks(max_tasks=100)


# --- Gerenciamento do Ciclo de Vida (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    Este gerenciador de contexto é executado durante a inicialização e o
    encerramento da API. Ele é responsável por criar e armazenar a instância
    do LLM no estado da aplicação, garantindo que o modelo seja carregado
    apenas uma vez e que todas as tasks sejam finalizadas no shutdown.
    
    Args:
        app: Instância da aplicação FastAPI.
        
    Yields:
        None: Permite que a aplicação execute normalmente entre setup e teardown.
        
    Examples:
        >>> # Usado automaticamente pelo FastAPI
        >>> app = FastAPI(lifespan=lifespan)
    """
    logger.info("Iniciando a API e configurando recursos...")
    
    # Configurar LLM
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("LLM_MODEL", "llama3.1")
    
    if not model:
        logger.critical("Variável de ambiente LLM_MODEL não definida.")
        raise RuntimeError("A configuração do modelo LLM não foi encontrada no ambiente.")

    logger.info(f"Conectando ao LLM: {model} em {base_url}")
    
    try:
        app.state.llm = OllamaLLM(
            model=model,
            base_url=base_url,
            temperature=0.1,
            client_kwargs={"timeout": 120.0},
            keep_alive="30m",
            validate_model_on_init=True
        )
        logger.info("Instância do LLM criada e pronta para uso.")
    except Exception as e:
        logger.critical(f"Falha ao inicializar LLM: {e}")
        raise RuntimeError(f"Não foi possível inicializar o LLM: {e}")

    # Iniciar gerenciador de contexto
    await gerenciador_contexto.iniciar()
    
    # Armazenar gerenciador de tasks no estado da app
    app.state.gerenciador_tasks = gerenciador_tasks

    yield  # A API fica operacional neste ponto
    
    logger.info("Encerrando a API e limpando recursos...")
    
    # Aguardar tasks pendentes
    await gerenciador_tasks.aguardar_todas(timeout=30)
    
    # Encerrar gerenciador de contexto
    await gerenciador_contexto.encerrar()

    # Encerrar cliente WAHA
    await cliente_waha.close()

    # Limpar recursos
    app.state.llm = None
    logger.info("Recursos liberados com sucesso")


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


def obter_gerenciador_tasks(request: Request) -> GerenciadorTasks:
    """
    Função de injeção de dependência para fornecer o gerenciador de tasks.
    
    Args:
        request: O objeto de requisição do FastAPI.
        
    Returns:
        GerenciadorTasks: Instância do gerenciador de tasks.
        
    Examples:
        >>> # Em um endpoint
        >>> async def meu_endpoint(tasks: GerenciadorTasks = Depends(obter_gerenciador_tasks)):
        >>>     await tasks.adicionar_task(minha_corrotina())
    """
    if not hasattr(request.app.state, 'gerenciador_tasks'):
        return gerenciador_tasks  # Usar instância global como fallback
    return request.app.state.gerenciador_tasks


# --- Definição da API ---
app = FastAPI(
    title="Bot WhatsApp com Arquitetura de Agente",
    version="5.0.0",
    description="""
API que utiliza uma arquitetura de Agente com Ferramentas para consultar um banco de dados de forma conversacional.

**Principais Funcionalidades:**
* **Roteamento de Intenção:** Identifica a intenção do usuário.
* **Construção de Query Segura:** Gera consultas SQL parametrizadas.
* **Sumarização:** Transforma dados brutos em respostas amigáveis.
* **WhatsApp Integration:** Processa mensagens via webhook WAHA.
* **Gerenciamento de Tasks:** Controle robusto de operações assíncronas.

**Versão 5.0.0 - Melhorias:**
* ✅ Gerenciamento robusto de tasks assíncronas
* ✅ Tratamento aprimorado de erros
* ✅ Métricas e estatísticas de performance
* ✅ Shutdown gracioso com finalização de tasks
* ✅ CORS configurado para integração frontend
    """,
    lifespan=lifespan
)

# --- Configuração CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


class StatusWhatsApp(BaseModel):
    """
    Modelo para status da conexão WhatsApp.
    
    Attributes:
        whatsapp_conectado: Se o WhatsApp está conectado.
        session_name: Nome da sessão ativa.
        status: Status atual da sessão.
        qr_code: QR code para autenticação (se disponível).
        sessoes_ativas: Número de sessões de chat ativas.
        timestamp: Timestamp da verificação.
    """
    whatsapp_conectado: bool
    session_name: str
    status: str
    qr_code: Optional[str] = None
    sessoes_ativas: int = 0
    timestamp: Optional[str] = None


# --- Tratamento Global de Erros ---
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    """
    Tratamento global de exceções não capturadas.
    
    Args:
        request: Requisição que causou a exceção.
        exc: Exceção capturada.
        
    Returns:
        JSONResponse: Resposta de erro formatada.
    """
    logger.error(f"Erro não tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno do servidor",
            "type": type(exc).__name__,
            "timestamp": datetime.now().isoformat()
        }
    )


# --- Endpoints da API ---
@app.get("/", summary="Verifica o Status da API", tags=["Status"])
async def ler_raiz():
    """
    Endpoint raiz para verificar a operacionalidade da API.
    
    Returns:
        dict: Dicionário com informações sobre o status da API.
        
    Examples:
        >>> # GET /
        >>> {"status": "API operacional", "versao": "5.0.0"}
    """
    stats = gerenciador_tasks.obter_estatisticas()
    return {
        "status": "API operacional. Use o endpoint /chat para interagir.",
        "versao": "5.0.0",
        "llm_engine": "langchain-ollama",
        "tasks_em_execucao": stats["em_execucao"],
        "capacidade_tasks": f"{stats['porcentagem_uso']:.1f}%",
        "documentacao": "/docs",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", summary="Health Check", tags=["Status"])
async def health_check():
    """
    Endpoint de health check para monitoramento.
    
    Verifica o status de todos os componentes críticos do sistema
    e retorna um relatório de saúde consolidado.
    
    Returns:
        dict: Status de saúde dos componentes.
        
    Examples:
        >>> # GET /health
        >>> {"status": "healthy", "components": {...}}
    """
    try:
        # Verificar componentes
        llm_ok = hasattr(app.state, 'llm') and app.state.llm is not None
        
        # Verificar WhatsApp
        try:
            waha_status = await cliente_waha.verificar_sessao(usar_cache=True)
            waha_ok = waha_status.get("conectado", False)
        except Exception as e:
            logger.error(f"Erro ao verificar WAHA: {e}")
            waha_ok = False
        
        # Obter estatísticas
        contexto_stats = gerenciador_contexto.obter_estatisticas_globais()
        tasks_stats = gerenciador_tasks.obter_estatisticas()
        
        # Determinar status geral
        if llm_ok and waha_ok:
            status_geral = "healthy"
        elif llm_ok:
            status_geral = "degraded"
        else:
            status_geral = "unhealthy"
        
        return {
            "status": status_geral,
            "timestamp": datetime.now().isoformat(),
            "components": {
                "llm": {
                    "status": "ok" if llm_ok else "unavailable",
                    "model": os.getenv("LLM_MODEL", "unknown")
                },
                "whatsapp": {
                    "status": "ok" if waha_ok else "disconnected",
                    "session": cliente_waha.config.session_name
                },
                "database": {
                    "status": "ok",  # Assumindo que DB está ok se a API está rodando
                    "type": "oracle"
                },
                "context_manager": {
                    "status": "ok",
                    "sessoes_ativas": contexto_stats["sessoes_ativas"],
                    "total_criadas": contexto_stats["total_sessoes_criadas"]
                },
                "task_manager": {
                    "status": "ok",
                    "tasks_em_execucao": tasks_stats["em_execucao"],
                    "capacidade": f"{tasks_stats['porcentagem_uso']:.1f}%"
                }
            }
        }
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/chat", response_model=RespostaBot, summary="Interage com o Bot", tags=["Chat"])
async def endpoint_chat(
    mensagem: MensagemUsuario,
    llm: Annotated[OllamaLLM, Depends(obter_llm)]
):
    """
    Recebe uma mensagem do usuário, processa através do orquestrador e retorna a resposta.
    
    Este é o endpoint principal para interação com o bot. Ele mantém contexto
    de conversa por usuário e processa consultas usando IA.
    
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
        logger.info(f"Processando mensagem de {mensagem.id_usuario}: {mensagem.texto[:50]}...")
        
        # Adicionar mensagem ao contexto
        await gerenciador_contexto.adicionar_mensagem(
            usuario_id=mensagem.id_usuario,
            texto=mensagem.texto,
            tipo="text"
        )
        
        # Obter contexto da conversa
        contexto = await gerenciador_contexto.obter_contexto(mensagem.id_usuario)
        
        # Construir prompt com contexto
        prompt_completo = f"{contexto}{mensagem.texto}" if contexto else mensagem.texto
        
        # Processar consulta
        texto_resposta = await gerenciar_consulta_usuario(llm, prompt_completo)
        
        # Adicionar resposta ao contexto
        await gerenciador_contexto.adicionar_resposta_bot(
            usuario_id=mensagem.id_usuario,
            resposta=texto_resposta
        )
        
        logger.info(f"Resposta gerada para {mensagem.id_usuario}")
        
        return RespostaBot(
            id_usuario=mensagem.id_usuario, 
            resposta=texto_resposta
        )
        
    except Exception as e:
        logger.error(f"Erro crítico no endpoint /chat para o usuário '{mensagem.id_usuario}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Ocorreu um erro interno no servidor ao processar sua solicitação."
        )


@app.post("/webhook/whatsapp", summary="Webhook do WhatsApp", tags=["WhatsApp"])
async def webhook_whatsapp(
    request: Request,
    llm: Annotated[OllamaLLM, Depends(obter_llm)],
    tasks: Annotated[GerenciadorTasks, Depends(obter_gerenciador_tasks)]
):
    """
    Recebe webhooks do WAHA para processar mensagens do WhatsApp.
    
    Este endpoint é chamado pelo WAHA sempre que uma nova mensagem é recebida
    no WhatsApp. A mensagem é processada de forma assíncrona.
    
    Args:
        request: Objeto de requisição contendo os dados do webhook.
        llm: Instância do modelo OllamaLLM (injetada automaticamente).
        tasks: Gerenciador de tasks (injetado automaticamente).
        
    Returns:
        dict: Confirmação de recebimento do webhook.
        
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
        
        # Log básico do evento
        evento = webhook_data.get('payload', {}).get('event', 'unknown')
        logger.info(f"Webhook recebido: {evento}")
        
        # Verificar se é um evento de mensagem
        if evento == 'message':
            # Processar mensagem em background com rastreamento
            try:
                task = await tasks.adicionar_task(
                    processador_whatsapp.processar_mensagem(llm, webhook_data)
                )
                logger.debug(f"Task de processamento criada")
            except RuntimeError as e:
                logger.error(f"Não foi possível criar task: {e}")
                # Responder sucesso mesmo assim para não perder mensagens
                # O WhatsApp tentará reenviar se retornarmos erro
        elif evento == 'session.status':
            # Evento de status da sessão
            logger.info(f"Status da sessão atualizado: {webhook_data.get('payload', {}).get('data', {})}")
        else:
            logger.debug(f"Evento não processado: {evento}")
        
        return {
            "status": "received", 
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro no webhook do WhatsApp: {e}", exc_info=True)
        # Retornar sucesso para evitar retry infinito do WAHA
        return {
            "status": "received", 
            "error": "processing_failed",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/whatsapp/status", response_model=StatusWhatsApp, summary="Status do WhatsApp", tags=["WhatsApp"])
async def status_whatsapp():
    """
    Verifica o status da conexão com WhatsApp.
    
    Retorna informações detalhadas sobre a sessão do WhatsApp,
    incluindo se está conectado, QR code para autenticação (se necessário)
    e estatísticas de uso.
    
    Returns:
        StatusWhatsApp: Informações sobre o status da conexão WhatsApp.
        
    Examples:
        >>> # GET /whatsapp/status
        >>> {
        >>>   "whatsapp_conectado": True,
        >>>   "session_name": "default",
        >>>   "status": "WORKING",
        >>>   "sessoes_ativas": 5
        >>> }
    """
    try:
        status_info = await cliente_waha.verificar_sessao()
        contexto_stats = gerenciador_contexto.obter_estatisticas_globais()
        
        return StatusWhatsApp(
            whatsapp_conectado=status_info.get("conectado", False),
            session_name=cliente_waha.config.session_name,
            status=status_info.get("status", "unknown"),
            qr_code=status_info.get("qr_code"),
            sessoes_ativas=contexto_stats["sessoes_ativas"],
            timestamp=status_info.get("timestamp")
        )
    except Exception as e:
        logger.error(f"Erro ao verificar status do WhatsApp: {e}")
        return StatusWhatsApp(
            whatsapp_conectado=False,
            session_name=cliente_waha.config.session_name,
            status="erro",
            qr_code=None,
            sessoes_ativas=0,
            timestamp=datetime.now().isoformat()
        )


@app.post("/whatsapp/iniciar", summary="Iniciar Sessão WhatsApp", tags=["WhatsApp"])
async def iniciar_whatsapp(webhook_url: Optional[str] = None):
    """
    Inicia uma nova sessão do WhatsApp.
    
    Cria uma nova sessão no WAHA e configura o webhook para receber mensagens.
    Se um QR code for necessário, ele será retornado na resposta.
    
    Args:
        webhook_url: URL customizada para webhook (opcional).
    
    Returns:
        dict: Resultado da tentativa de iniciar a sessão.
        
    Examples:
        >>> # POST /whatsapp/iniciar
        >>> {
        >>>   "status": "success",
        >>>   "mensagem": "Sessão iniciada com sucesso",
        >>>   "qr_code": "data:image/png;base64,..."
        >>> }
    """
    try:
        resultado = await cliente_waha.iniciar_sessao(webhook_url)
        
        if resultado.get("sucesso"):
            return {
                "status": "success", 
                "mensagem": "Sessão iniciada com sucesso. Escaneie o QR code se necessário.",
                "qr_code": resultado.get("qr_code"),
                "webhook": resultado.get("webhook_configurado"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error", 
                "mensagem": f"Falha ao iniciar sessão: {resultado.get('erro')}",
                "detalhes": resultado.get("detalhes"),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Erro ao iniciar sessão do WhatsApp: {e}")
        raise HTTPException(status_code=500, detail="Erro ao iniciar sessão")


@app.post("/whatsapp/parar", summary="Parar Sessão WhatsApp", tags=["WhatsApp"])
async def parar_whatsapp():
    """
    Para a sessão ativa do WhatsApp.
    
    Encerra a sessão atual do WhatsApp no WAHA. Útil para forçar
    uma nova autenticação ou resolver problemas de conexão.
    
    Returns:
        dict: Resultado da tentativa de parar a sessão.
        
    Examples:
        >>> # POST /whatsapp/parar
        >>> {
        >>>   "status": "success",
        >>>   "mensagem": "Sessão encerrada com sucesso"
        >>> }
    """
    try:
        sucesso = await cliente_waha.parar_sessao()
        
        if sucesso:
            return {
                "status": "success",
                "mensagem": "Sessão encerrada com sucesso",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "mensagem": "Falha ao encerrar sessão",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Erro ao parar sessão do WhatsApp: {e}")
        raise HTTPException(status_code=500, detail="Erro ao parar sessão")


@app.get("/stats", summary="Estatísticas do Sistema", tags=["Status"])
async def obter_estatisticas():
    """
    Retorna estatísticas detalhadas do sistema.
    
    Fornece métricas sobre todos os componentes do sistema,
    incluindo uso de memória, tasks em execução, sessões ativas, etc.
    
    Returns:
        dict: Estatísticas de todos os componentes.
        
    Examples:
        >>> # GET /stats
        >>> {
        >>>   "contexto": {
        >>>     "sessoes_ativas": 5,
        >>>     "total_sessoes_criadas": 100
        >>>   },
        >>>   "tasks": {
        >>>     "em_execucao": 3,
        >>>     "max_permitido": 100
        >>>   }
        >>> }
    """
    try:
        # Obter estatísticas de cada componente
        contexto_stats = gerenciador_contexto.obter_estatisticas_globais()
        tasks_stats = gerenciador_tasks.obter_estatisticas()
        waha_stats = cliente_waha.obter_estatisticas()
        
        # Adicionar informações do sistema
        import psutil
        processo = psutil.Process()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "sistema": {
                "cpu_percent": processo.cpu_percent(),
                "memoria_mb": processo.memory_info().rss / 1024 / 1024,
                "threads": processo.num_threads()
            },
            "contexto": contexto_stats,
            "tasks": tasks_stats,
            "waha": waha_stats
        }
    except ImportError:
        # Se psutil não estiver instalado, retornar sem métricas do sistema
        return {
            "timestamp": datetime.now().isoformat(),
            "contexto": gerenciador_contexto.obter_estatisticas_globais(),
            "tasks": gerenciador_tasks.obter_estatisticas(),
            "waha": cliente_waha.obter_estatisticas()
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        raise HTTPException(status_code=500, detail="Erro ao obter estatísticas")


@app.delete("/contexto/{usuario_id}", summary="Limpar Contexto de Usuário", tags=["Chat"])
async def limpar_contexto_usuario(usuario_id: str):
    """
    Limpa o contexto/histórico de conversa de um usuário específico.
    
    Útil para reiniciar uma conversa ou resolver problemas de contexto.
    
    Args:
        usuario_id: ID do usuário para limpar o contexto.
        
    Returns:
        dict: Confirmação da limpeza.
        
    Examples:
        >>> # DELETE /contexto/user123
        >>> {
        >>>   "status": "success",
        >>>   "mensagem": "Contexto limpo com sucesso"
        >>> }
    """
    try:
        sucesso = await gerenciador_contexto.encerrar_sessao(usuario_id)
        
        if sucesso:
            return {
                "status": "success",
                "mensagem": f"Contexto do usuário {usuario_id} limpo com sucesso",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "not_found",
                "mensagem": f"Nenhuma sessão ativa encontrada para o usuário {usuario_id}",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Erro ao limpar contexto: {e}")
        raise HTTPException(status_code=500, detail="Erro ao limpar contexto")


@app.get("/contexto/{usuario_id}", summary="Obter Contexto de Usuário", tags=["Chat"])
async def obter_contexto_usuario(usuario_id: str):
    """
    Obtém o contexto/histórico atual de conversa de um usuário.
    
    Retorna as últimas mensagens trocadas com o usuário e
    estatísticas da sessão.
    
    Args:
        usuario_id: ID do usuário para obter o contexto.
        
    Returns:
        dict: Contexto e estatísticas da sessão.
        
    Examples:
        >>> # GET /contexto/user123
        >>> {
        >>>   "usuario_id": "user123",
        >>>   "contexto": "Histórico da conversa...",
        >>>   "estatisticas": {...}
        >>> }
    """
    try:
        contexto = await gerenciador_contexto.obter_contexto(usuario_id)
        stats = gerenciador_contexto.obter_estatisticas_sessao(usuario_id)
        
        if stats:
            return {
                "usuario_id": usuario_id,
                "contexto": contexto if contexto else "Sem histórico",
                "estatisticas": stats,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "usuario_id": usuario_id,
                "contexto": "Sem histórico",
                "estatisticas": None,
                "mensagem": "Nenhuma sessão ativa para este usuário",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Erro ao obter contexto: {e}")
        raise HTTPException(status_code=500, detail="Erro ao obter contexto")


# --- Endpoints de Documentação Customizada ---
@app.get("/info", summary="Informações da API", tags=["Status"])
async def informacoes_api():
    """
    Retorna informações detalhadas sobre a API e suas capacidades.
    
    Returns:
        dict: Informações sobre a API.
        
    Examples:
        >>> # GET /info
        >>> {
        >>>   "nome": "Bot WhatsApp API",
        >>>   "versao": "5.0.0",
        >>>   "capacidades": [...]
        >>> }
    """
    return {
        "nome": "Bot WhatsApp com Arquitetura de Agentes",
        "versao": "5.0.0",
        "descricao": "Sistema de chatbot inteligente para WhatsApp com consultas a banco de dados Oracle",
        "capacidades": [
            "Processamento de linguagem natural com LLM",
            "Consultas SQL dinâmicas e seguras",
            "Integração com WhatsApp via WAHA",
            "Gerenciamento de contexto por usuário",
            "Processamento assíncrono de mensagens",
            "Suporte a mensagens de texto e áudio",
            "Métricas e monitoramento em tempo real"
        ],
        "tecnologias": {
            "framework": "FastAPI",
            "llm": "Ollama/Llama3.1",
            "database": "Oracle",
            "whatsapp": "WAHA",
            "linguagem": "Python 3.10+"
        },
        "endpoints_principais": {
            "chat": "/chat - Interação com o bot",
            "webhook": "/webhook/whatsapp - Recebimento de mensagens",
            "status": "/whatsapp/status - Status da conexão",
            "health": "/health - Verificação de saúde",
            "stats": "/stats - Estatísticas do sistema"
        },
        "documentacao": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "timestamp": datetime.now().isoformat()
    }