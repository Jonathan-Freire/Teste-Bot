
import os
import logging
import requests
import base64
from typing import Optional, Dict, Any
import asyncio
import aiofiles
from io import BytesIO

logger = logging.getLogger(__name__)

class ClienteWaha:
    def __init__(self):
        self.base_url = os.getenv("WAHA_BASE_URL", "https://waha.devlike.pro")
        self.api_key = os.getenv("WAHA_API_KEY")
        self.session_name = os.getenv("WHATSAPP_SESSION_NAME", "default")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else None
        }
        
    async def verificar_sessao(self) -> bool:
        """Verifica se a sessão do WhatsApp está ativa"""
        try:
            url = f"{self.base_url}/api/sessions/{self.session_name}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "WORKING"
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar sessão: {e}")
            return False
    
    async def iniciar_sessao(self) -> bool:
        """Inicia uma nova sessão do WhatsApp"""
        try:
            url = f"{self.base_url}/api/sessions/"
            payload = {
                "name": self.session_name,
                "config": {
                    "webhooks": [
                        {
                            "url": f"https://{os.getenv('REPL_SLUG', 'your-repl')}.{os.getenv('REPL_OWNER', 'your-username')}.repl.co/webhook/whatsapp",
                            "events": ["message"]
                        }
                    ]
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code in [200, 201]
            
        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}")
            return False
    
    async def enviar_mensagem(self, chat_id: str, texto: str) -> bool:
        """Envia mensagem de texto"""
        try:
            url = f"{self.base_url}/api/sendText"
            payload = {
                "session": self.session_name,
                "chatId": chat_id,
                "text": texto
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False
    
    async def baixar_audio(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Baixa áudio e retorna o caminho do arquivo"""
        try:
            if "media" not in message_data or not message_data["media"].get("url"):
                return None
                
            media_url = message_data["media"]["url"]
            
            # Baixar o arquivo
            response = requests.get(media_url, headers=self.headers)
            if response.status_code != 200:
                return None
            
            # Salvar temporariamente
            timestamp = str(int(asyncio.get_event_loop().time()))
            filename = f"temp_audio_{timestamp}.ogg"
            filepath = f"temp/{filename}"
            
            # Criar diretório temp se não existir
            os.makedirs("temp", exist_ok=True)
            
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(response.content)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Erro ao baixar áudio: {e}")
            return None
    
    async def transcrever_audio(self, filepath: str) -> Optional[str]:
        """Transcreve áudio usando whisper (implementação básica)"""
        try:
            # Aqui você pode integrar com Whisper ou outro serviço de transcrição
            # Por enquanto, retornamos uma mensagem indicativa
            return "[Áudio recebido - transcrição não implementada ainda]"
            
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {e}")
            return None
    
    async def limpar_arquivo_temp(self, filepath: str):
        """Remove arquivo temporário"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"Erro ao limpar arquivo temp: {e}")

# Instância global do cliente
cliente_waha = ClienteWaha()
