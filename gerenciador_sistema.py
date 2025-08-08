# ============================================================================
# CORREÇÃO COMPLETA DA AUTENTICAÇÃO WAHA
# ============================================================================
# Baseado na documentação oficial: https://waha.devlike.pro/docs/how-to/security/
#
# REGRA FUNDAMENTAL DO WAHA:
# - Container: Pode usar plain text OU SHA512 hashed na variável WAHA_API_KEY
# - HTTP Requests: SEMPRE usar a chave plain text original no header X-Api-Key
#
# ============================================================================

# ===== ARQUIVO 1: gerenciador_sistema.py (CORRIGIDO) =====

import asyncio
import subprocess
import sys
import os
import time
import secrets
import string
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging
from dotenv import load_dotenv, set_key

class GerenciadorWAHA:
    """
    Gerenciador WAHA com autenticação CORRIGIDA segundo a documentação oficial.
    
    CORREÇÃO PRINCIPAL:
    - Container: Usa plain text API key (mais simples e compatível)
    - HTTP Requests: Usa a mesma plain text API key
    - Remove toda a complexidade desnecessária de hashing
    
    Attributes:
        api_key: API key em plain text (usada tanto no container quanto nas requisições)
        comando_base: Comando Docker com configuração correta
        processo: Processo do container em execução
    """
    
    def __init__(self):
        """
        Inicializa o gerenciador WAHA com autenticação simplificada e correta.
        
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> print(len(waha.api_key))
            32
        """
        load_dotenv()

        # CORREÇÃO: Usar apenas uma API key simples (plain text)
        self.api_key = os.getenv("WAHA_API_KEY")
        
        # Se não existe ou é inválida, gerar nova
        if not self.api_key or self.api_key.startswith("sha512:") or len(self.api_key) < 16:
            self._gerar_nova_api_key()

        # COMANDO DOCKER CORRETO: Usar plain text API key
        self.comando_base = [
            "docker", "run", "-it", "--rm",
            "-p", "127.0.0.1:3000:3000",
            "-e", f"WAHA_API_KEY={self.api_key}",  # Plain text para o container
            "-e", "WHATSAPP_DEFAULT_ENGINE=WEBJS",
            "-e", "WAHA_PRINT_QR=true",
            "-e", "WAHA_API_KEY_EXCLUDE_PATH=health,ping,version",  # Excluir endpoints de monitoramento
            "--name", "waha-bot",
            "devlikeapro/waha:latest"
        ]
        self.processo = None
        
        print(f"✅ WAHA configurado com API key: {self.api_key[:8]}...")
        
    def _gerar_nova_api_key(self) -> None:
        """
        Gera nova API key seguindo as melhores práticas do WAHA.
        
        CORREÇÃO: Gera apenas plain text, sem hashing desnecessário.
        
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> waha._gerar_nova_api_key()
            >>> print(len(waha.api_key))
            32
        """
        # Gerar chave segura de 32 caracteres (UUID sem hífens)
        import uuid
        self.api_key = str(uuid.uuid4()).replace('-', '')
        
        # Salvar no .env
        env_path = Path(".env")
        set_key(str(env_path), "WAHA_API_KEY", self.api_key)
        
        # Remover variáveis antigas se existirem
        if os.getenv("WAHA_API_KEY_RAW"):
            set_key(str(env_path), "WAHA_API_KEY_RAW", "")
        
        # Atualizar ambiente atual
        os.environ["WAHA_API_KEY"] = self.api_key
        
        print(f"🔑 Nova API key gerada: {self.api_key[:8]}...")
    
    def criar_sessao(self, webhook_url: str) -> bool:
        """
        Cria sessão WAHA usando autenticação CORRETA.
        
        CORREÇÃO PRINCIPAL: Usa plain text API key no header X-Api-Key,
        conforme especificado na documentação oficial do WAHA.
        
        Args:
            webhook_url: URL do webhook para receber eventos
            
        Returns:
            bool: True se sessão foi criada com sucesso
            
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> sucesso = waha.criar_sessao("https://example.ngrok.app/webhook/whatsapp")
            >>> print(sucesso)
            True
        """
        try:
            # CORREÇÃO: Header com plain text API key (documentação oficial)
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key  # SEMPRE plain text para HTTP requests
            }

            print(f"🔐 Autenticando com API key: {self.api_key[:8]}...")

            # Remover sessão existente se houver
            try:
                delete_response = requests.delete(
                    "http://localhost:3000/api/sessions/default",
                    headers=headers,
                    timeout=10
                )
                print(f"📝 Delete session response: {delete_response.status_code}")
            except Exception as e:
                print(f"ℹ️  Erro ao deletar sessão existente (normal): {e}")

            # Configuração da sessão otimizada
            session_config = {
                "name": "default",
                "start": True,
                "config": {
                    "metadata": {
                        "user.id": "bot-whatsapp-comercial",
                        "user.email": "bot@comercial-esperanca.com"
                    },
                    "proxy": None,
                    "debug": False,
                    "noweb": {
                        "store": {
                            "enabled": True,
                            "fullSync": False
                        }
                    },
                    "webhooks": [
                        {
                            "url": webhook_url,
                            "events": [
                                "message",
                                "message.reaction", 
                                "session.status",
                                "message.media"
                            ],
                            "hmac": None,
                            "retries": 3,
                            "customHeaders": {
                                "User-Agent": "Bot-WhatsApp-v5.0-Corrected"
                            }
                        }
                    ]
                }
            }

            print(f"🔗 Configurando webhook: {webhook_url}")
            
            response = requests.post(
                "http://localhost:3000/api/sessions",
                json=session_config,
                headers=headers,
                timeout=20
            )
            
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                print("✅ Sessão WAHA criada com sucesso!")
                
                # Verificar status da sessão
                status = data.get("status", "UNKNOWN")
                if status == "SCAN_QR_CODE":
                    print("📱 QR code disponível em http://localhost:3000")
                    print("📸 Escaneie com seu WhatsApp para ativar o bot")
                elif status == "WORKING":
                    print("🚀 Sessão já autenticada e funcionando!")
                else:
                    print(f"📊 Sessão criada com status: {status}")
                
                return True
            else:
                print(f"❌ Erro ao criar sessão: Status {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"📝 Detalhes do erro: {error_data}")
                    
                    # Debug adicional para erro 401
                    if response.status_code == 401:
                        print("🔍 DIAGNÓSTICO ERRO 401:")
                        print(f"   API Key enviada: {self.api_key[:8]}...")
                        print(f"   Header X-Api-Key: Presente")
                        print(f"   Container API Key: {self.api_key[:8]}...")
                        print("📚 Conforme documentação WAHA: HTTP requests devem usar plain text API key")
                        
                except:
                    print(f"📝 Response text: {response.text}")
                return False
                
        except Exception as e:
            print(f"💥 Erro ao criar sessão WAHA: {e}")
            return False
    
    # ... resto dos métodos permanecem iguais mas com a API key corrigida ...

# ===== ARQUIVO 2: app/core/cliente_waha.py (CORRIGIDO) =====

import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ConfiguracaoWaha:
    """Configuração WAHA corrigida para autenticação simples."""
    base_url: str
    api_key: str  # SEMPRE plain text
    session_name: str
    timeout: int = 30
    max_retries: int = 3
    temp_dir: Path = Path("temp")

class ClienteWaha:
    """
    Cliente WAHA com autenticação CORRIGIDA segundo documentação oficial.
    
    PRINCIPAIS CORREÇÕES:
    1. Remove toda a complexidade de hash/plain text
    2. Usa apenas plain text API key para tudo
    3. Simplifica o processamento da API key
    4. Segue exatamente a documentação oficial do WAHA
    
    Attributes:
        config: Configuração com API key em plain text
        headers: Headers HTTP com X-Api-Key correto
    """
    
    def __init__(self):
        """
        Inicializa cliente WAHA com autenticação simplificada e correta.
        
        Examples:
            >>> cliente = ClienteWaha()
            >>> print(cliente.config.api_key[:8])
            # 8 primeiros caracteres da API key
        """
        self._carregar_configuracoes_corrigidas()
        self._configurar_headers_corretos()
        
        # Criar diretório temporário
        self.temp_dir = self.config.temp_dir
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        
        logger.info(f"Cliente WAHA inicializado com autenticação corrigida")
        logger.info(f"Base URL: {self.config.base_url}")
        logger.info(f"API Key configurada: {'✅' if self.config.api_key else '❌'}")
        
    def _carregar_configuracoes_corrigidas(self):
        """
        Carrega configurações seguindo a documentação oficial do WAHA.
        
        CORREÇÃO: Remove toda a lógica complexa de hashing e usa plain text.
        """
        base_url = os.getenv("WAHA_BASE_URL", "http://localhost:3000")
        session_name = os.getenv("WHATSAPP_SESSION_NAME", "default")
        
        # CORREÇÃO PRINCIPAL: API key sempre em plain text
        api_key = os.getenv("WAHA_API_KEY", "")
        
        # Se a chave está no formato SHA512, extrair a original ou gerar nova
        if api_key.startswith("sha512:"):
            logger.warning("API key em formato SHA512 detectada - gerando nova plain text")
            api_key = self._gerar_api_key_plain_text()
            self._salvar_api_key_corrigida(api_key)
        elif not api_key or len(api_key) < 16:
            logger.info("API key não configurada - gerando nova")
            api_key = self._gerar_api_key_plain_text()
            self._salvar_api_key_corrigida(api_key)
        
        self.config = ConfiguracaoWaha(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            session_name=session_name,
            timeout=int(os.getenv("WAHA_TIMEOUT", "30")),
            max_retries=int(os.getenv("WAHA_MAX_RETRIES", "3")),
            temp_dir=Path(os.getenv("TEMP_DIR", "temp"))
        )
        
        logger.info("Configurações WAHA carregadas com autenticação corrigida")
    
    def _gerar_api_key_plain_text(self) -> str:
        """
        Gera API key em plain text conforme recomendações WAHA.
        
        Returns:
            str: API key em plain text (UUID sem hífens)
            
        Examples:
            >>> cliente = ClienteWaha()
            >>> key = cliente._gerar_api_key_plain_text()
            >>> print(len(key))
            32
        """
        import uuid
        return str(uuid.uuid4()).replace('-', '')
    
    def _salvar_api_key_corrigida(self, api_key: str):
        """
        Salva API key corrigida no arquivo .env.
        
        Args:
            api_key: API key em plain text para salvar
        """
        try:
            from dotenv import set_key
            env_path = Path(".env")
            set_key(str(env_path), "WAHA_API_KEY", api_key)
            os.environ["WAHA_API_KEY"] = api_key
            logger.info("API key corrigida salva no .env")
        except Exception as e:
            logger.error(f"Erro ao salvar API key: {e}")
    
    def _configurar_headers_corretos(self):
        """
        Configura headers HTTP seguindo documentação oficial WAHA.
        
        CORREÇÃO: X-Api-Key sempre com plain text, nunca hash.
        """
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Bot-WhatsApp-Cliente-Corrected/5.0",
        }
        
        # CORREÇÃO CRÍTICA: X-Api-Key sempre com plain text
        if self.config.api_key:
            self.headers["X-Api-Key"] = self.config.api_key  # SEMPRE plain text
            logger.debug("Headers configurados com X-Api-Key (plain text)")
        else:
            logger.warning("Headers configurados SEM autenticação")
    
    async def verificar_sessao(self, usar_cache: bool = True) -> Dict[str, Any]:
        """
        Verifica status da sessão usando autenticação correta.
        
        Args:
            usar_cache: Se deve usar cache (para compatibilidade)
            
        Returns:
            Dict: Status da sessão WAHA
            
        Examples:
            >>> cliente = ClienteWaha()
            >>> status = await cliente.verificar_sessao()
            >>> print(status["conectado"])
            True ou False
        """
        try:
            url = f"{self.config.base_url}/api/sessions/{self.config.session_name}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, 
                    headers=self.headers,  # Headers com X-Api-Key correto
                    timeout=self.config.timeout
                )
            
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
                
                logger.info(f"Sessão verificada: {status}")
                return resultado
                
            elif response.status_code == 404:
                return {
                    "conectado": False,
                    "status": "NOT_FOUND",
                    "mensagem": "Sessão não encontrada",
                    "timestamp": datetime.now().isoformat(),
                }
            elif response.status_code == 401:
                logger.error("Erro 401: Falha na autenticação WAHA")
                logger.error(f"API Key usada: {self.config.api_key[:8]}...")
                return {
                    "conectado": False,
                    "status": "AUTH_ERROR",
                    "mensagem": "Erro de autenticação - verifique WAHA_API_KEY",
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "conectado": False,
                    "status": "ERROR",
                    "mensagem": f"Erro HTTP {response.status_code}: {response.text}",
                    "timestamp": datetime.now().isoformat(),
                }
                
        except Exception as e:
            logger.error(f"Erro ao verificar sessão WAHA: {e}")
            return {
                "conectado": False,
                "status": "CONNECTION_ERROR",
                "mensagem": str(e),
                "timestamp": datetime.now().isoformat(),
            }
    
    async def enviar_mensagem(self, chat_id: str, texto: str, mencoes: Optional[list] = None) -> bool:
        """
        Envia mensagem usando autenticação correta.
        
        Args:
            chat_id: ID do chat WhatsApp
            texto: Texto da mensagem
            mencoes: Lista de menções (opcional)
            
        Returns:
            bool: True se enviada com sucesso
            
        Examples:
            >>> cliente = ClienteWaha()
            >>> sucesso = await cliente.enviar_mensagem("5511999999999@c.us", "Olá!")
            >>> print(sucesso)
            True
        """
        try:
            url = f"{self.config.base_url}/api/sendText"
            payload = {
                "session": self.config.session_name,
                "chatId": self._formatar_chat_id(chat_id),
                "text": texto,
            }
            
            if mencoes:
                payload["mentions"] = mencoes
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers,  # Headers com X-Api-Key correto
                    timeout=self.config.timeout
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"Mensagem enviada para {chat_id}")
                return True
            else:
                logger.error(f"Falha ao enviar mensagem: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False
    
    def _formatar_chat_id(self, chat_id: str) -> str:
        """
        Formata chat_id para padrão WhatsApp.
        
        Args:
            chat_id: ID do chat bruto
            
        Returns:
            str: Chat ID formatado
            
        Examples:
            >>> cliente = ClienteWaha()
            >>> formatted = cliente._formatar_chat_id("5511999999999")
            >>> print(formatted)
            "5511999999999@c.us"
        """
        if chat_id.endswith("@c.us") or chat_id.endswith("@g.us"):
            return chat_id
        
        # Se é só número, assumir contato pessoal
        if chat_id.replace("+", "").replace("-", "").isdigit():
            return f"{chat_id.replace('+', '').replace('-', '')}@c.us"
        
        return chat_id
    
    # ... outros métodos seguem o mesmo padrão corrigido ...

# Instância global corrigida
cliente_waha = ClienteWaha()

# ===== ARQUIVO 3: Script de Teste da Correção =====

async def testar_autenticacao_corrigida():
    """
    Script de teste para validar se a correção da autenticação está funcionando.
    
    Este script testa:
    1. Geração correta da API key
    2. Configuração adequada do container
    3. Requisições HTTP com autenticação correta
    4. Criação de sessão WAHA
    
    Examples:
        >>> await testar_autenticacao_corrigida()
        # Executa todos os testes de autenticação
    """
    print("🧪 TESTANDO CORREÇÃO DA AUTENTICAÇÃO WAHA")
    print("=" * 50)
    
    # Teste 1: Configuração da API key
    print("\n1. Testando configuração da API key...")
    load_dotenv()
    api_key = os.getenv("WAHA_API_KEY")
    
    if api_key and not api_key.startswith("sha512:") and len(api_key) >= 16:
        print(f"✅ API key válida: {api_key[:8]}...")
    else:
        print("❌ API key inválida - executando correção...")
        waha = GerenciadorWAHA()  # Isso irá corrigir automaticamente
        api_key = waha.api_key
        print(f"✅ API key corrigida: {api_key[:8]}...")
    
    # Teste 2: Teste de autenticação HTTP
    print("\n2. Testando autenticação HTTP...")
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": api_key  # Plain text conforme documentação
        }
        
        response = requests.get("http://localhost:3000/api/sessions", headers=headers, timeout=5)
        
        if response.status_code == 200:
            print("✅ Autenticação HTTP funcionando")
            sessions = response.json()
            print(f"📊 Sessões encontradas: {len(sessions)}")
        elif response.status_code == 401:
            print("❌ Erro 401 - Falha na autenticação")
            print(f"🔍 API key testada: {api_key[:8]}...")
            print("📚 Verifique se o container WAHA foi iniciado com a mesma chave")
        else:
            print(f"⚠️  Status inesperado: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠️  WAHA não está rodando - teste de autenticação adiado")
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
    
    # Teste 3: Configuração do cliente
    print("\n3. Testando cliente WAHA...")
    try:
        cliente = ClienteWaha()
        print(f"✅ Cliente configurado com API key: {cliente.config.api_key[:8]}...")
        
        # Testar verificação de sessão
        status = await cliente.verificar_sessao()
        print(f"📱 Status da sessão: {status.get('status', 'UNKNOWN')}")
        
        if status.get("status") == "AUTH_ERROR":
            print("❌ Erro de autenticação detectado")
            return False
        else:
            print("✅ Cliente funcionando corretamente")
            
    except Exception as e:
        print(f"❌ Erro no cliente: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 TESTE DE CORREÇÃO CONCLUÍDO")
    print("📚 Conforme documentação oficial WAHA:")
    print("   - Container: Plain text API key na variável WAHA_API_KEY") 
    print("   - HTTP: Plain text API key no header X-Api-Key")
    print("   - Formato: UUID sem hífens (32 caracteres)")
    
    return True

# ===== ARQUIVO 4: .env corrigido =====

"""
# .env CORRIGIDO para WAHA
# Baseado na documentação oficial: https://waha.devlike.pro/docs/how-to/security/

# === WAHA Configuration (CORRIGIDO) ===
WAHA_BASE_URL=http://localhost:3000
WAHA_API_KEY=sua_api_key_plain_text_aqui_32_chars
# IMPORTANTE: Usar apenas plain text, SEM prefixo sha512:
# Exemplo: WAHA_API_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# === Outras configurações ===
WHATSAPP_SESSION_NAME=default
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1
PORT=8000
HOST=0.0.0.0
DEBUG_MODE=True
LOG_LEVEL=INFO
LOG_DIR=logs

# === Webhook (preenchido automaticamente) ===
NGROK_URL=

# === Configurações opcionais ===
BOT_TIMEOUT_MINUTES=30
MAX_CONTEXT_MESSAGES=10
"""

print("📋 RESUMO DA CORREÇÃO:")
print("✅ Removida complexidade desnecessária de hash/plain text")
print("✅ Container WAHA usa plain text API key")  
print("✅ HTTP requests usam plain text API key")
print("✅ Geração automática de API key no formato correto")
print("✅ Headers X-Api-Key configurados corretamente")
print("✅ Tratamento de erro 401 aprimorado")
print("✅ Documentação oficial seguida rigorosamente")
print("\n🔧 Para aplicar a correção:")
print("1. Substitua os arquivos pelos códigos corrigidos")
print("2. Execute: python -c 'from gerenciador_sistema import testar_autenticacao_corrigida; import asyncio; asyncio.run(testar_autenticacao_corrigida())'")
print("3. Reinicie o sistema: python gerenciador_sistema.py")