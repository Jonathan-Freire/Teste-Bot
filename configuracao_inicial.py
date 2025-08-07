#!/usr/bin/env python3
"""
Script de Configuração Inicial do Bot WhatsApp

Este script configura automaticamente todo o ambiente necessário
para o bot WhatsApp funcionar, incluindo:
- Verificação de dependências
- Configuração do arquivo .env
- Teste de conectividade com serviços
- Criação de estrutura de diretórios
- Configuração inicial do WAHA

Versão 3.0: Configuração automática completa

Execute: python configuracao_inicial.py
"""

import asyncio
import os
import sys
import subprocess
import requests
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import secrets
import string

class ConfiguradorInicial:
    """
    Classe responsável pela configuração inicial completa do sistema.
    
    Esta classe verifica e configura todos os componentes necessários
    para o bot WhatsApp funcionar adequadamente.
    
    Attributes:
        requisitos: Lista de requisitos do sistema.
        servicos: Dicionário com configurações dos serviços.
        env_vars: Dicionário com variáveis de ambiente.
    """
    
    def __init__(self):
        """
        Inicializa o configurador com valores padrão.
        
        Examples:
            >>> configurador = ConfiguradorInicial()
            >>> print(len(configurador.requisitos))
            6
        """
        self.requisitos = [
            "python", "pip", "docker", "ngrok", "curl", "git"
        ]
        
        self.servicos = {
            "ollama": {"url": "http://localhost:11434", "endpoint": "/api/tags"},
            "waha": {"url": "http://localhost:3000", "endpoint": "/"},
            "ngrok": {"url": "http://localhost:4040", "endpoint": "/api/tunnels"}
        }
        
        self.env_vars = {}
        
    def print_colorido(self, texto: str, cor: str = ""):
        """
        Imprime texto colorido no terminal.
        
        Args:
            texto: Texto a ser impresso.
            cor: Código de cor ANSI (opcional).
            
        Examples:
            >>> configurador = ConfiguradorInicial()
            >>> configurador.print_colorido("Sucesso!", "\033[92m")
        """
        cores = {
            "verde": "\033[92m",
            "amarelo": "\033[93m", 
            "vermelho": "\033[91m",
            "azul": "\033[94m",
            "reset": "\033[0m"
        }
        
        cor_code = cores.get(cor, "")
        print(f"{cor_code}{texto}{cores['reset']}")
    
    def verificar_requisito(self, comando: str) -> Tuple[bool, str]:
        """
        Verifica se um requisito está instalado.
        
        Args:
            comando: Comando a ser testado.
            
        Returns:
            Tupla com (sucesso, mensagem_detalhada).
            
        Examples:
            >>> configurador = ConfiguradorInicial()
            >>> sucesso, msg = configurador.verificar_requisito("python")
            >>> print(sucesso)
            True
        """
        try:
            # Comandos especiais para verificação
            comandos_teste = {
                "python": ["python", "--version"],
                "pip": ["pip", "--version"],
                "docker": ["docker", "--version"],
                "ngrok": ["ngrok", "version"],
                "curl": ["curl", "--version"],
                "git": ["git", "--version"]
            }
            
            cmd = comandos_teste.get(comando, [comando, "--version"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Extrair versão da saída
                versao = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
                return True, f"✅ {comando}: {versao}"
            else:
                return False, f"❌ {comando}: Não encontrado"
                
        except subprocess.TimeoutExpired:
            return False, f"❌ {comando}: Timeout"
        except FileNotFoundError:
            return False, f"❌ {comando}: Comando não encontrado"
        except Exception as e:
            return False, f"❌ {comando}: Erro - {str(e)}"
    
    def verificar_servico(self, nome: str, url: str, endpoint: str) -> Tuple[bool, str]:
        """
        Verifica se um serviço está rodando.
        
        Args:
            nome: Nome do serviço.
            url: URL base do serviço.
            endpoint: Endpoint para teste.
            
        Returns:
            Tupla com (sucesso, mensagem_detalhada).
        """
        try:
            response = requests.get(f"{url}{endpoint}", timeout=5)
            if response.status_code < 500:
                return True, f"✅ {nome}: Rodando (HTTP {response.status_code})"
            else:
                return False, f"❌ {nome}: Erro HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"❌ {nome}: Não acessível ({str(e)[:50]}...)"
    
    def gerar_api_key_segura(self, tamanho: int = 32) -> str:
        """
        Gera uma API key segura.
        
        Args:
            tamanho: Tamanho da chave a ser gerada.
            
        Returns:
            String com a API key gerada.
            
        Examples:
            >>> configurador = ConfiguradorInicial()
            >>> key = configurador.gerar_api_key_segura()
            >>> len(key)
            32
        """
        alfabeto = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alfabeto) for _ in range(tamanho))
    
    def criar_estrutura_diretorios(self) -> bool:
        """
        Cria a estrutura de diretórios necessária.
        
        Returns:
            bool: True se criou com sucesso.
        """
        diretorios = [
            "logs",
            "temp", 
            "app/agentes",
            "app/core",
            "app/db",
            "app/ferramentas",
            "helpers_compartilhados"
        ]
        
        try:
            for diretorio in diretorios:
                Path(diretorio).mkdir(parents=True, exist_ok=True)
                
                # Criar __init__.py se for um pacote Python
                if diretorio.startswith("app/") or diretorio == "helpers_compartilhados":
                    init_file = Path(diretorio) / "__init__.py"
                    if not init_file.exists():
                        init_file.touch()
            
            self.print_colorido("✅ Estrutura de diretórios criada", "verde")
            return True
            
        except Exception as e:
            self.print_colorido(f"❌ Erro ao criar diretórios: {e}", "vermelho")
            return False
    
    def configurar_env(self) -> bool:
        """
        Configura o arquivo .env com valores adequados.
        
        Returns:
            bool: True se configurou com sucesso.
        """
        try:
            # Valores padrão inteligentes
            env_config = {
                "# Configurações da IA (Ollama)": "",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "LLM_MODEL": "llama3.1",
                "",
                "# Configurações do WhatsApp via WAHA": "",
                "WAHA_BASE_URL": "http://localhost:3000",
                "WAHA_API_KEY": self.gerar_api_key_segura(),
                "WHATSAPP_SESSION_NAME": "default",
                "",
                "# Configurações do Webhook (será preenchido automaticamente)": "",
                "NGROK_URL": "",
                "",
                "# Configurações do Bot": "",
                "BOT_TIMEOUT_MINUTES": "30",
                "MAX_CONTEXT_MESSAGES": "10",
                "",
                "# Configurações de Desenvolvimento": "",
                "DEBUG_MODE": "True",
                "PORT": "8000",
                "HOST": "0.0.0.0",
                "",
                "# Logs": "",
                "LOG_LEVEL": "INFO",
                "LOG_DIR": "logs"
            }
            
            # Se já existe .env, fazer backup
            env_path = Path(".env")
            if env_path.exists():
                backup_path = Path(f".env.backup.{self._timestamp()}")
                env_path.rename(backup_path)
                self.print_colorido(f"📁 Backup do .env salvo: {backup_path}", "amarelo")
            
            # Escrever novo .env
            with open(".env", "w", encoding="utf-8") as f:
                for key, value in env_config.items():
                    if key.startswith("#") or key == "":
                        f.write(f"{key}\n")
                    else:
                        f.write(f"{key}={value}\n")
            
            self.print_colorido("✅ Arquivo .env configurado", "verde")
            
            # Salvar API key para usar no WAHA
            self.env_vars["WAHA_API_KEY"] = env_config["WAHA_API_KEY"]
            
            return True
            
        except Exception as e:
            self.print_colorido(f"❌ Erro ao configurar .env: {e}", "vermelho")
            return False
    
    def _timestamp(self) -> str:
        """
        Retorna timestamp atual formatado.
        
        Returns:
            String com timestamp no formato YYYYMMDD_HHMMSS.
        """
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def instalar_dependencias(self) -> bool:
        """
        Instala as dependências Python do projeto.
        
        Returns:
            bool: True se instalou com sucesso.
        """
        try:
            self.print_colorido("📦 Instalando dependências Python...", "azul")
            
            # Verificar se requirements.txt existe
            req_file = Path("requirements.txt")
            if not req_file.exists():
                self.print_colorido("❌ Arquivo requirements.txt não encontrado", "vermelho")
                return False
            
            # Instalar dependências
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.print_colorido("✅ Dependências instaladas com sucesso", "verde")
                return True
            else:
                self.print_colorido(f"❌ Erro na instalação: {result.stderr}", "vermelho")
                return False
                
        except subprocess.TimeoutExpired:
            self.print_colorido("❌ Timeout na instalação das dependências", "vermelho")
            return False
        except Exception as e:
            self.print_colorido(f"❌ Erro inesperado: {e}", "vermelho")
            return False
    
    def verificar_ollama_models(self) -> bool:
        """
        Verifica se há modelos instalados no Ollama.
        
        Returns:
            bool: True se há pelo menos um modelo disponível.
        """
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                if models:
                    self.print_colorido(f"✅ Ollama: {len(models)} modelo(s) disponível(is)", "verde")
                    for model in models[:3]:  # Mostrar até 3 modelos
                        self.print_colorido(f"   - {model['name']}", "azul")
                    return True
                else:
                    self.print_colorido("⚠️  Ollama está rodando mas sem modelos", "amarelo")
                    self.print_colorido("   Instale um modelo com: ollama pull llama3.1", "azul")
                    return False
            else:
                return False
                
        except Exception:
            return False
    
    def configurar_waha_docker(self) -> bool:
        """
        Configura e inicia o WAHA via Docker com a API key gerada.
        
        Returns:
            bool: True se configurou com sucesso.
        """
        try:
            self.print_colorido("🐳 Configurando WAHA com Docker...", "azul")
            
            api_key = self.env_vars.get("WAHA_API_KEY", "")
            if not api_key:
                self.print_colorido("❌ API key não encontrada", "vermelho")
                return False
            
            # Parar containers existentes
            subprocess.run(["docker", "stop", "waha-bot"], capture_output=True)
            subprocess.run(["docker", "rm", "waha-bot"], capture_output=True)
            
            # Comando Docker com configurações de segurança
            cmd = [
                "docker", "run", "-d", "--name", "waha-bot",
                "-p", "3000:3000",
                "-e", "WHATSAPP_DEFAULT_ENGINE=WEBJS",
                "-e", f"WAHA_SECURITY=sha512:{api_key}",
                "-e", "WAHA_PRINT_QR=true",
                "devlikeapro/waha:latest"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.print_colorido("✅ WAHA configurado e iniciado", "verde")
                self.print_colorido(f"🔑 API Key: {api_key}", "amarelo")
                return True
            else:
                self.print_colorido(f"❌ Erro ao iniciar WAHA: {result.stderr}", "vermelho")
                return False
                
        except subprocess.TimeoutExpired:
            self.print_colorido("❌ Timeout ao iniciar WAHA", "vermelho")
            return False
        except Exception as e:
            self.print_colorido(f"❌ Erro ao configurar WAHA: {e}", "vermelho")
            return False
    
    def criar_script_startup(self) -> bool:
        """
        Cria script de inicialização personalizado.
        
        Returns:
            bool: True se criou com sucesso.
        """
        try:
            script_content = f'''#!/usr/bin/env python3
"""
Script de inicialização rápida gerado automaticamente.
API Key WAHA: {self.env_vars.get("WAHA_API_KEY", "N/A")}
"""

import subprocess
import sys
import time

def main():
    print("🚀 Iniciando Bot WhatsApp...")
    
    # Iniciar API
    print("📡 Iniciando API...")
    api_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "app.main:app", 
        "--host", "0.0.0.0", "--port", "8000", "--reload"
    ])
    
    print("✅ Sistema iniciado!")
    print("📊 API: http://localhost:8000/docs")
    print("📱 WAHA: http://localhost:3000")
    print("🔧 Monitor: python monitor.py")
    
    try:
        api_process.wait()
    except KeyboardInterrupt:
        print("🛑 Encerrando...")
        api_process.terminate()

if __name__ == "__main__":
    main()
'''
            
            with open("iniciar_rapido.py", "w", encoding="utf-8") as f:
                f.write(script_content)
            
            self.print_colorido("✅ Script de inicialização criado: iniciar_rapido.py", "verde")
            return True
            
        except Exception as e:
            self.print_colorido(f"❌ Erro ao criar script: {e}", "vermelho")
            return False
    
    async def executar_configuracao(self) -> bool:
        """
        Executa todo o processo de configuração inicial.
        
        Returns:
            bool: True se configurou com sucesso.
            
        Examples:
            >>> configurador = ConfiguradorInicial()
            >>> sucesso = await configurador.executar_configuracao()
            >>> print(sucesso)
            True
        """
        self.print_colorido("=" * 60, "azul")
        self.print_colorido("🔧 CONFIGURAÇÃO INICIAL DO BOT WHATSAPP", "azul")
        self.print_colorido("=" * 60, "azul")
        
        etapas_sucesso = 0
        total_etapas = 8
        
        # 1. Verificar requisitos
        self.print_colorido("\n📋 [1/8] Verificando requisitos...", "azul")
        for req in self.requisitos:
            sucesso, msg = self.verificar_requisito(req)
            print(f"  {msg}")
            if sucesso:
                etapas_sucesso += 0.125  # Cada requisito vale 1/8 da etapa
        
        # 2. Criar estrutura
        self.print_colorido("\n📁 [2/8] Criando estrutura de diretórios...", "azul")
        if self.criar_estrutura_diretorios():
            etapas_sucesso += 1
        
        # 3. Instalar dependências
        self.print_colorido("\n📦 [3/8] Instalando dependências...", "azul")
        if self.instalar_dependencias():
            etapas_sucesso += 1
        
        # 4. Configurar .env
        self.print_colorido("\n⚙️  [4/8] Configurando arquivo .env...", "azul")
        if self.configurar_env():
            etapas_sucesso += 1
        
        # 5. Verificar Ollama
        self.print_colorido("\n🤖 [5/8] Verificando Ollama...", "azul")
        if self.verificar_ollama_models():
            etapas_sucesso += 1
        else:
            self.print_colorido("⚠️  Continue mesmo sem modelos - você pode instalar depois", "amarelo")
        
        # 6. Configurar WAHA
        self.print_colorido("\n🐳 [6/8] Configurando WAHA...", "azul")
        if self.configurar_waha_docker():
            etapas_sucesso += 1
        else:
            self.print_colorido("⚠️  WAHA pode ser configurado manualmente depois", "amarelo")
        
        # 7. Verificar serviços
        self.print_colorido("\n🔍 [7/8] Verificando serviços...", "azul")
        for nome, config in self.servicos.items():
            sucesso, msg = self.verificar_servico(nome, config["url"], config["endpoint"])
            print(f"  {msg}")
            if sucesso:
                etapas_sucesso += 0.33
        
        # 8. Criar scripts
        self.print_colorido("\n📝 [8/8] Criando scripts auxiliares...", "azul")
        if self.criar_script_startup():
            etapas_sucesso += 1
        
        # Relatório final
        porcentagem = (etapas_sucesso / total_etapas) * 100
        self.print_colorido(f"\n📊 Configuração concluída: {porcentagem:.1f}%", "azul")
        
        if porcentagem >= 80:
            self.print_colorido("🎉 CONFIGURAÇÃO BEM-SUCEDIDA!", "verde")
            self.print_colorido("\n📋 PRÓXIMOS PASSOS:", "azul")
            print("1. Execute: iniciar_bot_completo.bat")
            print("2. Ou execute: python iniciar_rapido.py")
            print("3. Configure WhatsApp no WAHA: http://localhost:3000")
            print("4. Use a API Key gerada:", self.env_vars.get("WAHA_API_KEY", "N/A"))
            return True
        else:
            self.print_colorido("⚠️  CONFIGURAÇÃO PARCIAL", "amarelo")
            self.print_colorido("Alguns componentes precisam ser configurados manualmente", "amarelo")
            return False

async def main():
    """
    Função principal da configuração inicial.
    
    Examples:
        >>> await main()
        # Executa toda a configuração inicial
    """
    configurador = ConfiguradorInicial()
    sucesso = await configurador.executar_configuracao()
    
    if sucesso:
        print("\n✨ Configuração inicial concluída com sucesso!")
        print("Execute 'iniciar_bot_completo.bat' para iniciar o sistema completo")
    else:
        print("\n⚠️  Configuração concluída com algumas pendências")
        print("Verifique as mensagens acima e configure manualmente se necessário")

if __name__ == "__main__":
    asyncio.run(main())