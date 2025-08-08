# app/core/cliente_waha.py
"""
Cliente para integração com WAHA (WhatsApp HTTP API) - Versão Completa.

Este módulo gerencia toda a comunicação com o WhatsApp através do WAHA,
incluindo envio de mensagens, gerenciamento de sessões, processamento de mídia
e transcrição de áudio.

Versão 4.0: Implementação completa com todos os métodos necessários.
"""

import asyncio
import hashlib
import logging
import os
import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class ConfiguracaoWaha:
    """
    Classe de configuração para o cliente WAHA.

    Attributes:
        base_url: URL base do serviço WAHA.
        api_key: Chave de API para autenticação.
        session_name: Nome da sessão WhatsApp.
        timeout: Timeout para requests HTTP.
        max_retries: Número máximo de tentativas.
        temp_dir: Diretório para arquivos temporários.
    """

    base_url: str
    api_key: str
    session_name: str
    timeout: int = 30
    max_retries: int = 3
    temp_dir: Path = Path("temp")


class ClienteWaha:
    """
    Cliente completo para comunicação com a API WAHA.

    Esta classe encapsula todas as operações relacionadas ao WhatsApp,
    funcionando como uma ponte entre nosso bot e o serviço WAHA.

    Principais funcionalidades:
    - Gerenciamento de sessões WhatsApp
    - Envio de mensagens de texto e mídia
    - Download e processamento de áudio
    - Transcrição de mensagens de voz
    - Indicadores de digitação
    - Cache inteligente de status

    Attributes:
        config: Configurações do cliente WAHA.
        headers: Headers HTTP para requests.
        session_cache: Cache do status da sessão.
        temp_dir: Diretório para arquivos temporários.
    """

    def __init__(self):
        """
        Inicializa o cliente WAHA com configurações otimizadas.

        Examples:
            >>> cliente = ClienteWaha()
            >>> print(cliente.config.base_url)
            "http://localhost:3000"
        """
        self._carregar_configuracoes()
        self._configurar_headers()
        self._inicializar_cache()

        # Criar diretório temporário se não existir
        self.temp_dir = self.config.temp_dir
        self.temp_dir.mkdir(exist_ok=True, parents=True)

        logger.info(
            f"Cliente WAHA inicializado. Base URL: {self.config.base_url}, "
            f"Autenticação: {'✅' if self.config.api_key else '❌'}, "
            f"Sessão: {self.config.session_name}"
        )

    def _carregar_configuracoes(self):
        """
        Carrega configurações do ambiente com validação.

        Carrega e valida todas as configurações necessárias,
        incluindo tratamento especial para diferentes formatos de API key.
        """
        base_url = os.getenv("WAHA_BASE_URL", "http://localhost:3000")
        session_name = os.getenv("WHATSAPP_SESSION_NAME", "default")

        # Tratamento inteligente da API key
        api_key_raw = os.getenv("WAHA_API_KEY", "")
        api_key = self._processar_api_key(api_key_raw)

        self.config = ConfiguracaoWaha(
            base_url=base_url.rstrip("/"),  # Remove trailing slash
            api_key=api_key,
            session_name=session_name,
            timeout=int(os.getenv("WAHA_TIMEOUT", "30")),
            max_retries=int(os.getenv("WAHA_MAX_RETRIES", "3")),
            temp_dir=Path(os.getenv("TEMP_DIR", "temp"))
        )

        # Validar configurações
        self._validar_configuracoes()

    def _processar_api_key(self, api_key_raw: str) -> str:
        """
        Processa a API key para diferentes formatos aceitos pelo WAHA.

        Args:
            api_key_raw: API key bruta do arquivo .env.

        Returns:
            str: API key processada ou vazia se inválida.

        Examples:
            >>> cliente = ClienteWaha()
            >>> key = cliente._processar_api_key("minha_chave_secreta")
            >>> print(key.startswith("sha512:"))
            True
        """
        if not api_key_raw or api_key_raw in [
            "",
            "sua_api_key_aqui",
            "your_api_key_here",
        ]:
            return ""

        # Se já está no formato correto, usar como está
        if api_key_raw.startswith(("sha512:", "sha256:", "md5:")):
            return api_key_raw

        # Se não está no formato correto, assumir que é uma chave raw e converter para SHA512
        if len(api_key_raw) >= 8:  # API key mínima
            sha512_hash = hashlib.sha512(api_key_raw.encode()).hexdigest()
            return f"sha512:{sha512_hash}"

        logger.warning(
            f"API key muito curta ou inválida: {len(api_key_raw)} caracteres"
        )
        return ""

    def _validar_configuracoes(self):
        """
        Valida as configurações carregadas.

        Raises:
            ValueError: Se configurações obrigatórias estiverem inválidas.
        """
        if not self.config.base_url:
            raise ValueError("WAHA_BASE_URL é obrigatório")

        if not self.config.session_name:
            raise ValueError("WHATSAPP_SESSION_NAME é obrigatório")

        if self.config.timeout <= 0:
            raise ValueError("Timeout deve ser maior que 0")

    def _configurar_headers(self):
        """
        Configura headers HTTP baseado na presença da API key.
        """
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Bot-WhatsApp-Cliente/4.0",
        }

        # Adicionar autenticação apenas se API key estiver configurada
        if self.config.api_key:
            # WAHA espera o header X-Api-Key
            self.headers["X-Api-Key"] = self.config.api_key
            logger.debug("Headers configurados COM autenticação")
        else:
            logger.warning("Headers configurados SEM autenticação")

    def _inicializar_cache(self):
        """
        Inicializa cache da sessão.
        """
        self.session_cache = {
            "status": None,
            "last_check": None,
            "cache_duration": 10,  # Cache por 10 segundos
        }

    def _cache_valido(self) -> bool:
        """
        Verifica se o cache da sessão ainda é válido.

        Returns:
            bool: True se o cache ainda é válido.
        """
        if not self.session_cache["last_check"]:
            return False

        tempo_decorrido = datetime.now().timestamp() - self.session_cache["last_check"]
        return tempo_decorrido < self.session_cache["cache_duration"]

    async def _fazer_request_com_retry(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """
        Faz request HTTP com retry automático.

        Args:
            method: Método HTTP (GET, POST, etc).
            url: URL do request.
            **kwargs: Argumentos adicionais para requisições HTTP.

        Returns:
            httpx.Response: Resposta do request.

        Raises:
            httpx.HTTPError: Se todas as tentativas falharem.

        Examples:
            >>> cliente = ClienteWaha()
            >>> response = await cliente._fazer_request_com_retry("GET", "http://localhost:3000/api/sessions")
            >>> print(response.status_code)
            200
        """
        kwargs.setdefault("timeout", self.config.timeout)
        kwargs.setdefault("headers", self.headers)

        ultima_excecao = None

        for tentativa in range(1, self.config.max_retries + 1):
            try:
                logger.debug(
                    f"Request {method} {url} - Tentativa {tentativa}/{self.config.max_retries}"
                )

                async with httpx.AsyncClient() as client:
                    if method.upper() == "GET":
                        response = await client.get(url, **kwargs)
                    elif method.upper() == "POST":
                        response = await client.post(url, **kwargs)
                    elif method.upper() == "DELETE":
                        response = await client.delete(url, **kwargs)
                    else:
                        raise ValueError(f"Método HTTP não suportado: {method}")

                # Log da resposta
                logger.debug(
                    f"Response: {response.status_code} - {response.reason_phrase}"
                )

                return response

            except httpx.HTTPError as e:
                ultima_excecao = e
                logger.warning(f"Tentativa {tentativa} falhou: {e}")

                if tentativa < self.config.max_retries:
                    await asyncio.sleep(2**tentativa)  # Backoff exponencial

        # Se chegou aqui, todas as tentativas falharam
        raise ultima_excecao

    async def verificar_sessao(self, usar_cache: bool = True) -> Dict[str, Any]:
        """
        Verifica o status da sessão do WhatsApp com cache inteligente.

        Args:
            usar_cache: Se deve usar o cache para otimizar verificações frequentes.

        Returns:
            Dict contendo informações sobre o status da sessão.

        Examples:
            >>> cliente = ClienteWaha()
            >>> status = await cliente.verificar_sessao()
            >>> print(status["conectado"])
            True ou False
        """
        # Usar cache se válido e solicitado
        if usar_cache and self._cache_valido():
            logger.debug("Usando cache para status da sessão")
            return self.session_cache["status"]

        try:
            url = f"{self.config.base_url}/api/sessions/{self.config.session_name}"
            response = await self._fazer_request_com_retry("GET", url)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "UNKNOWN")

                resultado = {
                    "conectado": status == "WORKING",
                    "status": status,
                    "qr_code": (
                        data.get("qr", {}).get("value")
                        if status == "SCAN_QR_CODE"
                        else None
                    ),
                    "detalhes": data,
                    "timestamp": datetime.now().isoformat(),
                }

            elif response.status_code == 404:
                resultado = {
                    "conectado": False,
                    "status": "NOT_FOUND",
                    "mensagem": "Sessão não encontrada",
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                resultado = {
                    "conectado": False,
                    "status": "ERROR",
                    "mensagem": f"Erro HTTP {response.status_code}: {response.text}",
                    "timestamp": datetime.now().isoformat(),
                }

            # Atualizar cache
            self.session_cache["status"] = resultado
            self.session_cache["last_check"] = datetime.now().timestamp()

            return resultado

        except httpx.HTTPError as e:
            logger.error(f"Erro ao verificar sessão: {e}")
            resultado = {
                "conectado": False,
                "status": "CONNECTION_ERROR",
                "mensagem": str(e),
                "timestamp": datetime.now().isoformat(),
            }

            # Cache erro por menos tempo
            self.session_cache["status"] = resultado
            self.session_cache["last_check"] = datetime.now().timestamp()
            self.session_cache["cache_duration"] = 5  # Cache erro por apenas 5 segundos

            return resultado

    async def iniciar_sessao(self, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Inicia ou reinicia uma sessão do WhatsApp com configurações otimizadas.

        Args:
            webhook_url: URL para receber webhooks. Se None, usa configuração automática.

        Returns:
            Dict com informações sobre o resultado da operação.

        Examples:
            >>> cliente = ClienteWaha()
            >>> resultado = await cliente.iniciar_sessao("https://abc.ngrok.app/webhook/whatsapp")
            >>> print(resultado["sucesso"])
            True
        """
        try:
            # Resolver webhook URL automaticamente se não fornecida
            if not webhook_url:
                webhook_url = await self._resolver_webhook_url()

            logger.info(
                f"Iniciando sessão '{self.config.session_name}' com webhook: {webhook_url}"
            )

            # Parar sessão existente primeiro
            await self.parar_sessao()
            await asyncio.sleep(3)  # Aguardar um pouco mais para garantir limpeza

            # Configuração robusta da sessão
            url = f"{self.config.base_url}/api/sessions"
            payload = self._construir_payload_sessao(webhook_url)

            response = await self._fazer_request_com_retry("POST", url, json=payload)

            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Sessão iniciada com sucesso: {data}")

                # Limpar cache para forçar verificação na próxima consulta
                self.session_cache["status"] = None

                return {
                    "sucesso": True,
                    "status": data.get("status", "STARTING"),
                    "qr_code": data.get("qr", {}).get("value"),
                    "mensagem": "Sessão criada. Escaneie o QR code se necessário.",
                    "webhook_configurado": webhook_url,
                }
            else:
                logger.error(
                    f"Erro ao iniciar sessão: {response.status_code} - {response.text}"
                )
                return {
                    "sucesso": False,
                    "erro": f"HTTP {response.status_code}",
                    "detalhes": response.text,
                    "webhook_tentado": webhook_url,
                }

        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}", exc_info=True)
            return {"sucesso": False, "erro": str(e), "webhook_tentado": webhook_url}

    async def _resolver_webhook_url(self) -> str:
        """
        Resolve automaticamente a URL do webhook.

        Returns:
            str: URL do webhook resolvida.
        """
        # Tentar obter do .env primeiro
        ngrok_url = os.getenv("NGROK_URL")
        if ngrok_url and ngrok_url != "":
            return f"{ngrok_url.rstrip('/')}/webhook/whatsapp"

        # Tentar obter do ngrok local
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:4040/api/tunnels", timeout=5
                )
            if response.status_code == 200:
                tunnels = response.json().get("tunnels", [])
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        url = tunnel.get("public_url")
                        logger.info(f"URL do ngrok detectada automaticamente: {url}")
                        return f"{url}/webhook/whatsapp"
        except Exception:
            pass

        # Fallback para localhost
        port = os.getenv("PORT", "8000")
        return f"http://localhost:{port}/webhook/whatsapp"

    def _construir_payload_sessao(self, webhook_url: str) -> Dict[str, Any]:
        """
        Constrói payload otimizado para criação de sessão.

        Args:
            webhook_url: URL do webhook.

        Returns:
            Dict: Payload da sessão.
        """
        payload = {
            "name": self.config.session_name,
            "start": True,
            "config": {
                "metadata": {
                    "user.id": "123",
                    "user.email": "email@example.com",
                },
                "proxy": None,
                "debug": False,
                "noweb": {"store": {"enabled": True, "fullSync": False}},
                "webhooks": [
                    {
                        "url": webhook_url,
                        "events": ["message", "session.status"],
                        "hmac": None,
                        "retries": None,
                        "customHeaders": None,
                    }
                ],
            },
        }

        return payload

    async def parar_sessao(self) -> bool:
        """
        Para e remove uma sessão do WhatsApp com limpeza completa.

        Returns:
            bool: True se a sessão foi parada com sucesso.
        """
        try:
            url = f"{self.config.base_url}/api/sessions/{self.config.session_name}"
            response = await self._fazer_request_com_retry("DELETE", url)

            if response.status_code in [200, 204, 404]:
                logger.info(f"Sessão '{self.config.session_name}' parada/removida")
                # Limpar cache
                self.session_cache["status"] = None
                return True
            else:
                logger.warning(
                    f"Resposta inesperada ao parar sessão: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Erro ao parar sessão: {e}")
            return False

    async def enviar_mensagem(
        self, chat_id: str, texto: str, mencoes: Optional[List[str]] = None
    ) -> bool:
        """
        Envia mensagem de texto com suporte a menções e formatação.

        Args:
            chat_id: ID do chat (número@c.us para contatos, id@g.us para grupos).
            texto: Texto da mensagem a ser enviada.
            mencoes: Lista de IDs para mencionar (opcional).

        Returns:
            bool: True se a mensagem foi enviada com sucesso.

        Examples:
            >>> cliente = ClienteWaha()
            >>> sucesso = await cliente.enviar_mensagem("5511999999999@c.us", "Olá!")
            >>> print(sucesso)
            True
        """
        try:
            # Garantir formato correto do chat_id
            chat_id_formatado = self._formatar_chat_id(chat_id)

            url = f"{self.config.base_url}/api/sendText"
            payload = {
                "session": self.config.session_name,
                "chatId": chat_id_formatado,
                "text": texto,
            }

            # Adicionar menções se especificadas
            if mencoes:
                payload["mentions"] = mencoes

            logger.debug(f"Enviando mensagem para {chat_id_formatado}: {texto[:50]}...")
            response = await self._fazer_request_com_retry("POST", url, json=payload)

            if response.status_code in [200, 201]:
                logger.info(f"Mensagem enviada com sucesso para {chat_id_formatado}")
                return True
            else:
                logger.error(
                    f"Falha ao enviar mensagem: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}", exc_info=True)
            return False

    async def enviar_typing(self, chat_id: str, duracao: int = 3) -> bool:
        """
        Envia indicador de "digitando..." para o chat.

        Args:
            chat_id: ID do chat.
            duracao: Duração em segundos do indicador (máximo 10).

        Returns:
            bool: True se o indicador foi enviado com sucesso.

        Examples:
            >>> cliente = ClienteWaha()
            >>> await cliente.enviar_typing("5511999999999@c.us", 5)
            True
        """
        try:
            chat_id_formatado = self._formatar_chat_id(chat_id)
            duracao = min(duracao, 10)  # Limitar a 10 segundos

            url = f"{self.config.base_url}/api/startTyping"
            payload = {
                "session": self.config.session_name,
                "chatId": chat_id_formatado,
                "duration": duracao * 1000  # Converter para milissegundos
            }

            response = await self._fazer_request_com_retry("POST", url, json=payload)

            if response.status_code in [200, 201, 204]:
                logger.debug(f"Indicador de digitação enviado para {chat_id_formatado}")
                return True
            else:
                logger.warning(f"Falha ao enviar typing: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Erro ao enviar typing: {e}")
            return False

    async def baixar_audio(self, message_data: Dict[str, Any]) -> Optional[str]:
        """
        Baixa arquivo de áudio do WhatsApp.

        Args:
            message_data: Dados da mensagem contendo informações do áudio.

        Returns:
            Optional[str]: Caminho do arquivo baixado ou None se falhar.

        Examples:
            >>> cliente = ClienteWaha()
            >>> message_data = {"id": "msg123", "mimetype": "audio/ogg"}
            >>> filepath = await cliente.baixar_audio(message_data)
            >>> print(filepath)
            "temp/audio_msg123.ogg"
        """
        try:
            message_id = message_data.get("id")
            if not message_id:
                logger.error("ID da mensagem não encontrado")
                return None

            # Determinar extensão do arquivo
            mimetype = message_data.get("mimetype", "audio/ogg")
            extensao = mimetype.split("/")[-1].split(";")[0]
            if extensao not in ["ogg", "mp3", "wav", "m4a"]:
                extensao = "ogg"

            # Criar nome do arquivo
            filename = f"audio_{message_id}.{extensao}"
            filepath = self.temp_dir / filename

            # Baixar mídia via WAHA
            url = f"{self.config.base_url}/api/downloadMedia"
            payload = {
                "session": self.config.session_name,
                "messageId": message_id
            }

            response = await self._fazer_request_com_retry("POST", url, json=payload)

            if response.status_code == 200:
                media_data = response.json()
                
                # Decodificar base64 e salvar arquivo
                if "data" in media_data:
                    audio_bytes = base64.b64decode(media_data["data"])
                    
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(audio_bytes)
                    
                    logger.info(f"Áudio baixado: {filepath}")
                    return str(filepath)
                else:
                    logger.error("Dados de mídia não encontrados na resposta")
                    return None
            else:
                logger.error(f"Erro ao baixar áudio: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Erro ao baixar áudio: {e}", exc_info=True)
            return None

    async def transcrever_audio(self, filepath: str) -> Optional[str]:
        """
        Transcreve arquivo de áudio usando serviço externo.

        Args:
            filepath: Caminho do arquivo de áudio.

        Returns:
            Optional[str]: Transcrição do áudio ou None se falhar.

        Examples:
            >>> cliente = ClienteWaha()
            >>> transcricao = await cliente.transcrever_audio("temp/audio.ogg")
            >>> print(transcricao)
            "Olá, gostaria de saber sobre produtos"
        """
        try:
            # Verificar se arquivo existe
            if not Path(filepath).exists():
                logger.error(f"Arquivo não encontrado: {filepath}")
                return None

            # Aqui você pode integrar com serviços de transcrição como:
            # - OpenAI Whisper API
            # - Google Speech-to-Text
            # - Azure Speech Services
            # - Whisper local (se instalado)

            # Por enquanto, retornar placeholder
            logger.warning("Transcrição de áudio não implementada - retornando texto padrão")
            return "[Mensagem de áudio recebida - transcrição não disponível no momento]"

            # Exemplo de integração com Whisper local (comentado):
            """
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(filepath, language="pt")
            return result["text"]
            """

        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {e}", exc_info=True)
            return None

    async def limpar_arquivo_temp(self, filepath: str) -> bool:
        """
        Remove arquivo temporário.

        Args:
            filepath: Caminho do arquivo a ser removido.

        Returns:
            bool: True se o arquivo foi removido com sucesso.

        Examples:
            >>> cliente = ClienteWaha()
            >>> await cliente.limpar_arquivo_temp("temp/audio.ogg")
            True
        """
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                logger.debug(f"Arquivo temporário removido: {filepath}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao remover arquivo temporário: {e}")
            return False

    def _formatar_chat_id(self, chat_id: str) -> str:
        """
        Formata chat_id para o padrão esperado pelo WAHA.

        Args:
            chat_id: ID do chat bruto.

        Returns:
            str: Chat ID formatado.

        Examples:
            >>> cliente = ClienteWaha()
            >>> formatted = cliente._formatar_chat_id("5511999999999")
            >>> print(formatted)
            "5511999999999@c.us"
        """
        if chat_id.endswith("@c.us") or chat_id.endswith("@g.us"):
            return chat_id

        # Se é só número, assumir que é contato pessoal
        if chat_id.replace("+", "").replace("-", "").isdigit():
            return f"{chat_id.replace('+', '').replace('-', '')}@c.us"

        # Se não conseguiu determinar, retornar como está
        logger.warning(f"Formato de chat_id não reconhecido: {chat_id}")
        return chat_id

    async def obter_sessoes_ativas(self) -> List[Dict[str, Any]]:
        """
        Obtém lista de todas as sessões ativas no WAHA.

        Returns:
            Lista de dicionários com informações das sessões.

        Examples:
            >>> cliente = ClienteWaha()
            >>> sessoes = await cliente.obter_sessoes_ativas()
            >>> print(len(sessoes))
            1
        """
        try:
            url = f"{self.config.base_url}/api/sessions"
            response = await self._fazer_request_com_retry("GET", url)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Erro ao obter sessões: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Erro ao obter sessões: {e}")
            return []

    async def listar_contatos(self, limite: int = 50) -> List[Dict[str, Any]]:
        """
        Lista contatos da sessão ativa.

        Args:
            limite: Número máximo de contatos a retornar.

        Returns:
            Lista de dicionários com informações dos contatos.
        """
        try:
            url = f"{self.config.base_url}/api/contacts"
            params = {"session": self.config.session_name, "limit": limite}

            response = await self._fazer_request_com_retry("GET", url, params=params)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Erro ao listar contatos: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Erro ao listar contatos: {e}")
            return []

    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Obtém estatísticas do cliente WAHA.

        Returns:
            Dict com estatísticas de uso e configuração.

        Examples:
            >>> cliente = ClienteWaha()
            >>> stats = cliente.obter_estatisticas()
            >>> print(stats["autenticado"])
            True ou False
        """
        return {
            "base_url": self.config.base_url,
            "session_name": self.config.session_name,
            "autenticado": bool(self.config.api_key),
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "cache_valido": self._cache_valido(),
            "temp_dir": str(self.temp_dir),
            "headers_count": len(self.headers),
        }


# Instância global otimizada do cliente
cliente_waha = ClienteWaha()