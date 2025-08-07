#!/usr/bin/env python3
"""
Script de Configuração e Teste do Bot WhatsApp

Este script guia você através de todo o processo de configuração
do bot WhatsApp, desde a verificação dos requisitos até o teste final.

Versão 2.1: Corrigidas importações do LangChain para compatibilidade Python 3.10.11

Execute: python setup_whatsapp.py
"""

import asyncio
import subprocess
import sys
import os
import time
import requests
import qrcode
from pathlib import Path
from typing import Optional

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

# Cores para o terminal
class Cores:
    """Classe para definir cores no terminal."""
    VERDE = '\033[92m'
    AMARELO = '\033[93m'
    VERMELHO = '\033[91m'
    AZUL = '\033[94m'
    RESET = '\033[0m'
    NEGRITO = '\033[1m'

def print_colorido(texto: str, cor: str = Cores.RESET):
    """
    Imprime texto colorido no terminal.
    
    Args:
        texto: Texto a ser impresso.
        cor: Código de cor ANSI.
    """
    print(f"{cor}{texto}{Cores.RESET}")

def print_titulo(titulo: str):
    """
    Imprime um título formatado.
    
    Args:
        titulo: Texto do título.
    """
    print("\n" + "=" * 60)
    print_colorido(f"  {titulo}", Cores.NEGRITO + Cores.AZUL)
    print("=" * 60)

def print_sucesso(mensagem: str):
    """
    Imprime mensagem de sucesso.
    
    Args:
        mensagem: Mensagem a ser exibida.
    """
    print_colorido(f"✅ {mensagem}", Cores.VERDE)

def print_erro(mensagem: str):
    """
    Imprime mensagem de erro.
    
    Args:
        mensagem: Mensagem de erro a ser exibida.
    """
    print_colorido(f"❌ {mensagem}", Cores.VERMELHO)

def print_aviso(mensagem: str):
    """
    Imprime mensagem de aviso.
    
    Args:
        mensagem: Mensagem de aviso a ser exibida.
    """
    print_colorido(f"⚠️  {mensagem}", Cores.AMARELO)

def print_info(mensagem: str):
    """
    Imprime mensagem informativa.
    
    Args:
        mensagem: Mensagem informativa a ser exibida.
    """
    print_colorido(f"ℹ️  {mensagem}", Cores.AZUL)

class ConfiguradorWhatsApp:
    """
    Classe principal para configurar o sistema WhatsApp.
    
    Esta classe gerencia todo o processo de configuração do bot,
    desde a verificação de requisitos até o teste final do sistema.
    
    Attributes:
        ngrok_process: Processo do ngrok em execução.
        uvicorn_process: Processo da API FastAPI em execução.
        ngrok_url: URL pública gerada pelo ngrok.
        waha_url: URL local do serviço WAHA.
        api_port: Porta onde a API será executada.
    """
    
    def __init__(self):
        """
        Inicializa o configurador com valores padrão.
        
        Examples:
            >>> configurador = ConfiguradorWhatsApp()
            >>> print(configurador.api_port)
            8000
        """
        self.ngrok_process = None
        self.uvicorn_process = None
        self.ngrok_url = None
        self.waha_url = "http://localhost:3000"
        self.api_port = 8000
        
    async def verificar_requisitos(self) -> bool:
        """
        Verifica se todos os requisitos estão instalados.
        
        Returns:
            bool: True se todos os requisitos estão atendidos.
        """
        print_titulo("VERIFICANDO REQUISITOS")
        
        requisitos_ok = True
        
        # Verificar Python
        print("Verificando Python...")
        if sys.version_info >= (3, 8):
            print_sucesso(f"Python {sys.version.split()[0]} encontrado")
        else:
            print_erro("Python 3.8+ é necessário")
            requisitos_ok = False
        
        # Verificar pip packages
        packages_necessarios = [
            "fastapi", "uvicorn", "langchain_core", "langchain_community", 
            "pydantic", "aiofiles", "requests", "qrcode"
        ]
        
        print("\nVerificando pacotes Python...")
        for package in packages_necessarios:
            try:
                # Correção: usar nome correto para importação
                nome_import = package.replace("-", "_")
                __import__(nome_import)
                print_sucesso(f"{package} instalado")
            except ImportError:
                print_erro(f"{package} não encontrado")
                print_info(f"Instale com: pip install {package}")
                requisitos_ok = False
        
        # Verificar ngrok
        print("\nVerificando ngrok...")
        try:
            result = subprocess.run(["ngrok", "version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print_sucesso(f"ngrok encontrado: {result.stdout.strip()}")
            else:
                raise FileNotFoundError
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print_erro("ngrok não encontrado")
            print_info("Baixe em: https://ngrok.com/download")
            print_info("Ou instale com: brew install ngrok (Mac) / snap install ngrok (Linux)")
            requisitos_ok = False
        
        # Verificar Ollama
        print("\nVerificando Ollama...")
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    print_sucesso(f"Ollama rodando com {len(models)} modelo(s)")
                    for model in models[:3]:  # Mostrar até 3 modelos
                        print_info(f"  - {model['name']}")
                else:
                    print_aviso("Ollama rodando mas sem modelos")
                    print_info("Instale um modelo com: ollama pull llama3.1")
            else:
                raise requests.exceptions.RequestException
        except requests.exceptions.RequestException:
            print_erro("Ollama não está rodando ou não está acessível")
            print_info("Inicie o Ollama com: ollama serve")
            requisitos_ok = False
        
        # Verificar WAHA
        print("\nVerificando WAHA...")
        try:
            response = requests.get(f"{self.waha_url}/api/sessions", timeout=5)
            if response.status_code in [200, 401]:  # 401 se tiver autenticação
                print_sucesso("WAHA está rodando")
            else:
                raise requests.exceptions.RequestException
        except requests.exceptions.RequestException:
            print_erro("WAHA não está rodando em http://localhost:3000")
            print_info("Inicie o WAHA com Docker:")
            print_info("docker run -it -p 3000:3000 devlikeapro/waha")
            requisitos_ok = False
        
        # Verificar arquivo .env
        print("\nVerificando configuração...")
        if Path(".env").exists():
            print_sucesso("Arquivo .env encontrado")
        else:
            print_aviso("Arquivo .env não encontrado - será criado")
            self.criar_env_padrao()
        
        return requisitos_ok
    
    def criar_env_padrao(self):
        """
        Cria arquivo .env com configurações padrão.
        
        Examples:
            >>> configurador = ConfiguradorWhatsApp()
            >>> configurador.criar_env_padrao()
            # Cria arquivo .env com configurações
        """
        env_content = """# Configurações do Bot WhatsApp
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1
WAHA_BASE_URL=http://localhost:3000
WAHA_API_KEY=
WHATSAPP_SESSION_NAME=default
BOT_TIMEOUT_MINUTES=30
MAX_CONTEXT_MESSAGES=10
DEBUG_MODE=True
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO
LOG_DIR=logs
"""
        with open(".env", "w") as f:
            f.write(env_content)
        print_info("Arquivo .env criado com configurações padrão")
    
    async def iniciar_ngrok(self) -> Optional[str]:
        """
        Inicia o ngrok e retorna a URL pública.
        
        Returns:
            Optional[str]: URL pública do ngrok ou None se falhar.
        """
        print_titulo("INICIANDO NGROK")
        
        try:
            # Iniciar ngrok
            print_info(f"Iniciando túnel ngrok na porta {self.api_port}...")
            self.ngrok_process = subprocess.Popen(
                ["ngrok", "http", str(self.api_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Aguardar o ngrok iniciar
            time.sleep(3)
            
            # Obter URL do ngrok via API local
            try:
                response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
                tunnels = response.json()["tunnels"]
                
                for tunnel in tunnels:
                    if tunnel["proto"] == "https":
                        self.ngrok_url = tunnel["public_url"]
                        print_sucesso(f"Ngrok iniciado: {self.ngrok_url}")
                        
                        # Salvar URL no .env
                        self.atualizar_env("NGROK_URL", self.ngrok_url)
                        return self.ngrok_url
                
            except Exception as e:
                print_erro(f"Erro ao obter URL do ngrok: {e}")
                print_info("Verifique o ngrok em: http://localhost:4040")
                
        except Exception as e:
            print_erro(f"Erro ao iniciar ngrok: {e}")
            return None
    
    def atualizar_env(self, chave: str, valor: str):
        """
        Atualiza uma chave no arquivo .env.
        
        Args:
            chave: Nome da variável de ambiente.
            valor: Valor a ser atribuído.
        """
        try:
            # Ler arquivo existente
            lines = []
            if Path(".env").exists():
                with open(".env", "r") as f:
                    lines = f.readlines()
            
            # Atualizar ou adicionar chave
            chave_encontrada = False
            for i, line in enumerate(lines):
                if line.startswith(f"{chave}="):
                    lines[i] = f"{chave}={valor}\n"
                    chave_encontrada = True
                    break
            
            if not chave_encontrada:
                lines.append(f"{chave}={valor}\n")
            
            # Salvar arquivo
            with open(".env", "w") as f:
                f.writelines(lines)
                
        except Exception as e:
            print_erro(f"Erro ao atualizar .env: {e}")
    
    async def configurar_waha(self) -> bool:
        """
        Configura a sessão do WhatsApp no WAHA.
        
        Returns:
            bool: True se configurado com sucesso.
        """
        print_titulo("CONFIGURANDO WHATSAPP")
        
        try:
            # Importar após verificar requisitos
            from app.core.cliente_waha import cliente_waha
            
            # Verificar sessão existente
            print_info("Verificando sessão WhatsApp...")
            status = await cliente_waha.verificar_sessao()
            
            if status["conectado"]:
                print_sucesso("WhatsApp já está conectado!")
                return True
            
            # Iniciar nova sessão
            webhook_url = f"{self.ngrok_url}/webhook/whatsapp" if self.ngrok_url else None
            print_info(f"Iniciando sessão com webhook: {webhook_url}")
            
            resultado = await cliente_waha.iniciar_sessao(webhook_url)
            
            if not resultado["sucesso"]:
                print_erro(f"Erro ao iniciar sessão: {resultado.get('erro')}")
                return False
            
            # Aguardar e obter QR code
            print_info("Aguardando QR code...")
            for i in range(30):  # Tentar por 30 segundos
                await asyncio.sleep(1)
                status = await cliente_waha.verificar_sessao()
                
                if status["conectado"]:
                    print_sucesso("WhatsApp conectado com sucesso!")
                    return True
                
                if status.get("qr_code"):
                    print("\n" + "=" * 60)
                    print_colorido("📱 ESCANEIE O QR CODE COM SEU WHATSAPP", Cores.NEGRITO + Cores.VERDE)
                    print("=" * 60)
                    
                    # Mostrar QR code no terminal
                    qr = qrcode.QRCode(version=1, box_size=2, border=1)
                    qr.add_data(status["qr_code"])
                    qr.make(fit=True)
                    qr.print_ascii(invert=True)
                    
                    # Aguardar conexão
                    print_info("Aguardando autenticação...")
                    for j in range(60):  # Aguardar até 60 segundos
                        await asyncio.sleep(2)
                        status = await cliente_waha.verificar_sessao()
                        if status["conectado"]:
                            print_sucesso("WhatsApp conectado com sucesso!")
                            return True
                    
                    print_erro("Tempo esgotado para autenticação")
                    return False
            
            print_erro("Não foi possível obter QR code")
            return False
            
        except Exception as e:
            print_erro(f"Erro ao configurar WhatsApp: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def iniciar_api(self):
        """
        Inicia a API FastAPI.
        
        Returns:
            bool: True se a API foi iniciada com sucesso.
        """
        print_titulo("INICIANDO API")
        
        try:
            print_info(f"Iniciando servidor na porta {self.api_port}...")
            
            # Comando para iniciar o uvicorn
            cmd = [
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--host", "0.0.0.0",
                "--port", str(self.api_port),
                "--reload"
            ]
            
            self.uvicorn_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Aguardar servidor iniciar
            print_info("Aguardando servidor iniciar...")
            for i in range(30):
                try:
                    response = requests.get(f"http://localhost:{self.api_port}/", timeout=1)
                    if response.status_code == 200:
                        print_sucesso(f"API rodando em http://localhost:{self.api_port}")
                        print_info(f"Documentação em: http://localhost:{self.api_port}/docs")
                        return True
                except requests.exceptions.RequestException:
                    await asyncio.sleep(1)
            
            print_erro("Servidor não iniciou no tempo esperado")
            return False
            
        except Exception as e:
            print_erro(f"Erro ao iniciar API: {e}")
            return False
    
    async def testar_sistema(self):
        """
        Realiza teste completo do sistema.
        
        Returns:
            bool: True se todos os testes passaram.
        """
        print_titulo("TESTANDO SISTEMA COMPLETO")
        
        try:
            # Teste 1: API está respondendo
            print("\n1. Testando API...")
            response = requests.get(f"http://localhost:{self.api_port}/")
            if response.status_code == 200:
                print_sucesso("API respondendo")
            else:
                print_erro("API não está respondendo")
                return False
            
            # Teste 2: Status do WhatsApp
            print("\n2. Verificando WhatsApp...")
            response = requests.get(f"http://localhost:{self.api_port}/whatsapp/status")
            data = response.json()
            if data.get("whatsapp_conectado"):
                print_sucesso("WhatsApp conectado e pronto")
            else:
                print_erro("WhatsApp não está conectado")
                return False
            
            # Teste 3: Teste de chat
            print("\n3. Testando processamento de mensagem...")
            test_message = {
                "id_usuario": "teste_setup",
                "texto": "quais os 5 produtos mais vendidos este mês?"
            }
            
            response = requests.post(
                f"http://localhost:{self.api_port}/chat",
                json=test_message,
                timeout=30
            )
            
            if response.status_code == 200:
                resposta = response.json()
                print_sucesso("Processamento funcionando")
                print_info(f"Resposta: {resposta['resposta'][:100]}...")
            else:
                print_erro(f"Erro no processamento: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            print_erro(f"Erro nos testes: {e}")
            return False
    
    async def executar(self):
        """
        Executa todo o processo de configuração.
        
        Este é o método principal que orquestra todo o processo de configuração
        do bot WhatsApp, desde a verificação de requisitos até os testes finais.
        """
        print_colorido("\n🤖 CONFIGURADOR DO BOT WHATSAPP 🤖", Cores.NEGRITO + Cores.AZUL)
        print("=" * 60)
        
        try:
            # 1. Verificar requisitos
            if not await self.verificar_requisitos():
                print_erro("\n❌ Corrija os problemas acima antes de continuar")
                return
            
            print_sucesso("\n✅ Todos os requisitos verificados!")
            
            # 2. Iniciar ngrok
            input("\nPressione ENTER para iniciar o ngrok...")
            ngrok_url = await self.iniciar_ngrok()
            if not ngrok_url:
                print_erro("Falha ao iniciar ngrok")
                return
            
            # 3. Iniciar API
            input("\nPressione ENTER para iniciar a API...")
            if not await self.iniciar_api():
                print_erro("Falha ao iniciar API")
                return
            
            # 4. Configurar WhatsApp
            input("\nPressione ENTER para configurar o WhatsApp...")
            if not await self.configurar_waha():
                print_erro("Falha ao configurar WhatsApp")
                return
            
            # 5. Testar sistema
            input("\nPressione ENTER para testar o sistema...")
            if await self.testar_sistema():
                print_sucesso("\n🎉 SISTEMA CONFIGURADO E FUNCIONANDO!")
                print("\n" + "=" * 60)
                print_colorido("INSTRUÇÕES PARA TESTAR:", Cores.NEGRITO)
                print("=" * 60)
                print(f"1. Envie uma mensagem para o número do WhatsApp configurado")
                print(f"2. A API está rodando em: http://localhost:{self.api_port}")
                print(f"3. Webhook configurado em: {ngrok_url}/webhook/whatsapp")
                print(f"4. Logs em: logs/log_bot.log")
                print("\nExemplos de perguntas para testar:")
                print("  - 'Quais os produtos mais vendidos este mês?'")
                print("  - 'Qual o limite de crédito do cliente João?'")
                print("  - 'Mostre os pedidos do cliente 123 este mês'")
                print("\n" + "=" * 60)
                print_info("Pressione Ctrl+C para parar o sistema")
                
                # Manter rodando
                while True:
                    await asyncio.sleep(1)
            else:
                print_erro("Testes falharam")
                
        except KeyboardInterrupt:
            print_aviso("\n\nEncerrando sistema...")
        finally:
            # Limpar recursos
            if self.ngrok_process:
                self.ngrok_process.terminate()
                print_info("Ngrok encerrado")
            if self.uvicorn_process:
                self.uvicorn_process.terminate()
                print_info("API encerrada")

async def main():
    """
    Função principal do configurador.
    
    Examples:
        >>> await main()
        # Executa todo o processo de configuração
    """
    configurador = ConfiguradorWhatsApp()
    await configurador.executar()

if __name__ == "__main__":
    asyncio.run(main())