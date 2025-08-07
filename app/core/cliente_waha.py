# app/core/cliente_waha.py
"""
Cliente para integração com WAHA (WhatsApp HTTP API).

Este módulo gerencia toda a comunicação com o WhatsApp através do WAHA,
incluindo envio de mensagens, gerenciamento de sessões e processamento de mídia.

Versão 2.0: Adaptado para uso local com Docker e ngrok.
"""

import os
import logging
import requests
import asyncio
import aiofiles
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ClienteWaha:
    """
    Cliente para comunicação com a API WAHA.
    
    Esta classe encapsula todas as operações relacionadas ao WhatsApp,
    funcionando como uma ponte entre nosso bot e o serviço WAHA.
    """
    
    def __init__(self):
        """
        Inicializa o cliente WAHA com configurações do ambiente.
        
        As configurações são carregadas do arquivo .env para facilitar
        a mudança entre ambientes (desenvolvimento/produção).
        """
        self.base_url = os.getenv("WAHA_BASE_URL", "http://localhost:3000")
        self.api_key = os.getenv("WAHA_API_KEY", "")
        self.session_name = os.getenv("WHATSAPP_SESSION_NAME", "default")
        
        # Configurar headers - se não há API key, não incluir Authorization
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Criar diretório temporário se não existir
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        logger.info(f"Cliente WAHA inicializado. Base URL: {self.base_url}, Sessão: {self.session_name}")
    
    async def verificar_sessao(self) -> Dict[str, Any]:
        """
        Verifica o status da sessão do WhatsApp.
        
        Returns:
            Dict contendo informações sobre o status da sessão.
            
        Examples:
            >>> status = await cliente_waha.verificar_sessao()
            >>> print(status)
            {"conectado": True, "status": "WORKING", "qr_code": None}
        """
        try:
            url = f"{self.base_url}/api/sessions/{self.session_name}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "UNKNOWN")
                
                return {
                    "conectado": status == "WORKING",
                    "status": status,
                    "qr_code": data.get("qr", {}).get("value") if status == "SCAN_QR_CODE" else None,
                    "detalhes": data
                }
            elif response.status_code == 404:
                return {
                    "conectado": False,
                    "status": "NOT_FOUND",
                    "mensagem": "Sessão não encontrada"
                }
            else:
                return {
                    "conectado": False,
                    "status": "ERROR",
                    "mensagem": f"Erro HTTP {response.status_code}"
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao verificar sessão: {e}")
            return {
                "conectado": False,
                "status": "CONNECTION_ERROR",
                "mensagem": str(e)
            }
    
    async def iniciar_sessao(self, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Inicia ou reinicia uma sessão do WhatsApp.
        
        Args:
            webhook_url: URL para receber webhooks. Se None, usa a configuração do ambiente.
            
        Returns:
            Dict com informações sobre o resultado da operação.
            
        Examples:
            >>> resultado = await cliente_waha.iniciar_sessao("https://abc.ngrok.app/webhook/whatsapp")
            >>> print(resultado["sucesso"])
            True
        """
        try:
            # Se não foi fornecida URL, tentar pegar do ambiente ou usar localhost
            if not webhook_url:
                webhook_url = os.getenv("NGROK_URL")
                if webhook_url:
                    webhook_url = f"{webhook_url}/webhook/whatsapp"
                else:
                    webhook_url = f"http://localhost:{os.getenv('PORT', '8000')}/webhook/whatsapp"
            
            logger.info(f"Iniciando sessão '{self.session_name}' com webhook: {webhook_url}")
            
            # Primeiro, tentar deletar sessão existente
            await self.parar_sessao()
            
            # Aguardar um pouco para garantir que a sessão foi removida
            await asyncio.sleep(2)
            
            # Criar nova sessão
            url = f"{self.base_url}/api/sessions"
            payload = {
                "name": self.session_name,
                "config": {
                    "webhooks": [
                        {
                            "url": webhook_url,
                            "events": ["message", "session.status"],
                            "hmac": None,
                            "retries": {
                                "delaySeconds": 2,
                                "attempts": 3
                            }
                        }
                    ]
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Sessão iniciada com sucesso: {data}")
                
                # Retornar informações úteis
                return {
                    "sucesso": True,
                    "status": data.get("status", "STARTING"),
                    "qr_code": data.get("qr", {}).get("value"),
                    "mensagem": "Sessão criada. Escaneie o QR code se necessário."
                }
            else:
                logger.error(f"Erro ao iniciar sessão: {response.status_code} - {response.text}")
                return {
                    "sucesso": False,
                    "erro": f"HTTP {response.status_code}",
                    "detalhes": response.text
                }
                
        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}", exc_info=True)
            return {
                "sucesso": False,
                "erro": str(e)
            }
    
    async def parar_sessao(self) -> bool:
        """
        Para e remove uma sessão do WhatsApp.
        
        Returns:
            bool: True se a sessão foi parada com sucesso.
        """
        try:
            url = f"{self.base_url}/api/sessions/{self.session_name}"
            response = requests.delete(url, headers=self.headers, timeout=10)
            
            if response.status_code in [200, 204, 404]:
                logger.info(f"Sessão '{self.session_name}' parada/removida")
                return True
            else:
                logger.warning(f"Resposta inesperada ao parar sessão: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao parar sessão: {e}")
            return False
    
    async def enviar_mensagem(self, chat_id: str, texto: str) -> bool:
        """
        Envia mensagem de texto para um contato ou grupo.
        
        Args:
            chat_id: ID do chat (número@c.us para contatos, id@g.us para grupos).
            texto: Texto da mensagem a ser enviada.
            
        Returns:
            bool: True se a mensagem foi enviada com sucesso.
            
        Examples:
            >>> sucesso = await cliente_waha.enviar_mensagem("5511999999999@c.us", "Olá!")
            >>> print(sucesso)
            True
        """
        try:
            # Garantir formato correto do chat_id
            if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"):
                # Se é só número, assumir que é contato
                if chat_id.replace("+", "").isdigit():
                    chat_id = f"{chat_id}@c.us"
            
            url = f"{self.base_url}/api/sendText"
            payload = {
                "session": self.session_name,
                "chatId": chat_id,
                "text": texto
            }
            
            logger.debug(f"Enviando mensagem para {chat_id}: {texto[:50]}...")
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 201:
                logger.info(f"Mensagem enviada com sucesso para {chat_id}")
                return True
            else:
                logger.error(f"Falha ao enviar mensagem: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}", exc_info=True)
            return False
    
    async def baixar_audio(self, message_data: Dict[str, Any]) -> Optional[str]:
        """
        Baixa arquivo de áudio recebido e salva temporariamente.
        
        Args:
            message_data: Dados da mensagem contendo informações do áudio.
            
        Returns:
            str: Caminho do arquivo baixado ou None se falhar.
        """
        try:
            # WAHA geralmente fornece o ID do media
            media_id = message_data.get("media", {}).get("id")
            if not media_id:
                logger.warning("Mensagem não contém ID de mídia")
                return None
            
            # Endpoint para baixar mídia
            url = f"{self.base_url}/api/messages/media/{media_id}"
            params = {"session": self.session_name}
            
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Erro ao baixar áudio: HTTP {response.status_code}")
                return None
            
            # Salvar arquivo temporário
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{timestamp}.ogg"
            filepath = self.temp_dir / filename
            
            # Salvar conteúdo do áudio
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(response.content)
            
            logger.info(f"Áudio salvo em: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Erro ao baixar áudio: {e}", exc_info=True)
            return None
    
    async def transcrever_audio(self, filepath: str) -> Optional[str]:
        """
        Transcreve áudio usando serviço de transcrição.
        
        Args:
            filepath: Caminho do arquivo de áudio.
            
        Returns:
            str: Texto transcrito ou None se falhar.
            
        Note:
            Esta é uma implementação básica. Para produção, integre com
            serviços como Whisper API, Google Speech-to-Text, etc.
        """
        try:
            # TODO: Implementar transcrição real
            # Opções:
            # 1. OpenAI Whisper API
            # 2. Google Cloud Speech-to-Text
            # 3. Whisper local (requer instalação)
            # 4. Azure Speech Services
            
            logger.warning("Transcrição de áudio ainda não implementada")
            return "[Áudio recebido - transcrição não configurada]"
            
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {e}")
            return None
    
    async def limpar_arquivo_temp(self, filepath: str):
        """
        Remove arquivo temporário do sistema.
        
        Args:
            filepath: Caminho do arquivo a ser removido.
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Arquivo temporário removido: {filepath}")
        except Exception as e:
            logger.error(f"Erro ao limpar arquivo temporário: {e}")
    
    async def obter_qr_code(self) -> Optional[str]:
        """
        Obtém o QR code para autenticação do WhatsApp.
        
        Returns:
            str: String do QR code ou None se não disponível.
        """
        try:
            status = await self.verificar_sessao()
            return status.get("qr_code")
        except Exception as e:
            logger.error(f"Erro ao obter QR code: {e}")
            return None
    
    async def enviar_typing(self, chat_id: str, duracao: int = 3):
        """
        Envia indicador de "digitando..." para o chat.
        
        Args:
            chat_id: ID do chat.
            duracao: Duração em segundos do indicador.
        """
        try:
            url = f"{self.base_url}/api/startTyping"
            payload = {
                "session": self.session_name,
                "chatId": chat_id,
                "duration": duracao * 1000  # API espera milissegundos
            }
            
            requests.post(url, json=payload, headers=self.headers, timeout=5)
            logger.debug(f"Indicador de digitação enviado para {chat_id}")
            
        except Exception as e:
            logger.debug(f"Erro ao enviar typing (não crítico): {e}")

# Instância global do cliente
cliente_waha = ClienteWaha()