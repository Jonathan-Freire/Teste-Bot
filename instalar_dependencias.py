#!/usr/bin/env python3
"""
Script de Instalação de Dependências - Bot WhatsApp

Este script automatiza a instalação de todas as dependências necessárias
para o sistema funcionar, incluindo as atualizações para langchain-ollama.

Execute: python instalar_dependencias.py
"""

import subprocess
import sys
import os
from pathlib import Path

def print_colorido(texto: str, cor: str = ""):
    """Imprime texto colorido."""
    cores = {
        "verde": "\033[92m",
        "amarelo": "\033[93m", 
        "vermelho": "\033[91m",
        "azul": "\033[94m",
        "reset": "\033[0m"
    }
    cor_code = cores.get(cor, "")
    print(f"{cor_code}{texto}{cores['reset']}")

def verificar_python():
    """Verifica se a versão do Python é adequada."""
    print_colorido("🐍 Verificando versão do Python...", "azul")
    
    versao = sys.version_info
    if versao >= (3, 10):
        print_colorido(f"✅ Python {versao.major}.{versao.minor}.{versao.micro} - OK", "verde")
        return True
    else:
        print_colorido(f"❌ Python {versao.major}.{versao.minor}.{versao.micro} - Muito antigo", "vermelho")
        print_colorido("   Necessário Python 3.10+", "amarelo")
        return False

def instalar_pip_packages():
    """Instala pacotes Python necessários."""
    print_colorido("\n📦 Instalando dependências Python...", "azul")
    
    # Dependências essenciais com versões específicas
    packages = [
        # Core do sistema
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0", 
        "pydantic==2.5.0",
        
        # LangChain atualizado
        "langchain-core==0.1.0",
        "langchain-ollama==0.3.6",  # NOVA DEPENDÊNCIA
        
        # HTTP clients
        "httpx==0.25.2",
        "requests==2.31.0",
        "aiohttp==3.9.1",
        
        # Utilitários
        "python-dotenv==1.0.0",
        "python-dateutil==2.8.2",
        "aiofiles==23.2.0",
        "python-multipart==0.0.6",
        
        # Logging e monitoramento
        "structlog==23.2.0",
        "psutil==5.9.6",
        
        # WhatsApp e QR Code
        "qrcode[pil]==7.4.2",
        "Pillow==10.1.0",
        
        # Resiliência e Docker
        "tenacity==8.2.3",
        "docker==7.0.0",
        
        # Desenvolvimento (opcional)
        "pytest==7.4.3",
        "pytest-asyncio==0.21.1",
    ]
    
    sucessos = 0
    total = len(packages)
    
    for package in packages:
        try:
            print(f"   Instalando {package}...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", package, "--quiet"
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print_colorido(f"   ✅ {package}", "verde")
                sucessos += 1
            else:
                print_colorido(f"   ❌ {package}: {result.stderr}", "vermelho")
                
        except subprocess.TimeoutExpired:
            print_colorido(f"   ⏱️  {package}: Timeout", "amarelo")
        except Exception as e:
            print_colorido(f"   ❌ {package}: {e}", "vermelho")
    
    print_colorido(f"\n📊 Instalação concluída: {sucessos}/{total} pacotes", "azul")
    return sucessos == total

def verificar_instalacao():
    """Verifica se as principais dependências estão funcionando."""
    print_colorido("\n🧪 Verificando instalação...", "azul")
    
    testes = [
        ("FastAPI", "import fastapi"),
        ("LangChain Ollama", "import langchain_ollama"),  # TESTE ATUALIZADO
        ("Pydantic", "import pydantic"),
        ("Requests", "import requests"),
        ("Docker SDK", "import docker"),
        ("QRCode", "import qrcode"),
    ]
    
    sucessos = 0
    for nome, codigo in testes:
        try:
            exec(codigo)
            print_colorido(f"   ✅ {nome}", "verde")
            sucessos += 1
        except ImportError as e:
            print_colorido(f"   ❌ {nome}: {e}", "vermelho")
        except Exception as e:
            print_colorido(f"   ⚠️  {nome}: {e}", "amarelo")
    
    print_colorido(f"   Total: {sucessos}/{len(testes)} funcionando", "azul")
    return sucessos == len(testes)

def criar_estrutura_diretorios():
    """Cria estrutura de diretórios necessária."""
    print_colorido("\n📁 Criando estrutura de diretórios...", "azul")
    
    diretorios = [
        "logs",
        "temp",
        "app/agentes", 
        "app/core",
        "app/db",
        "app/ferramentas",
        "helpers_compartilhados"
    ]
    
    for diretorio in diretorios:
        try:
            Path(diretorio).mkdir(parents=True, exist_ok=True)
            
            # Criar __init__.py para pacotes Python
            if diretorio.startswith("app/") or diretorio == "helpers_compartilhados":
                init_file = Path(diretorio) / "__init__.py"
                if not init_file.exists():
                    init_file.touch()
                    
            print_colorido(f"   ✅ {diretorio}", "verde")
        except Exception as e:
            print_colorido(f"   ❌ {diretorio}: {e}", "vermelho")

def verificar_ferramentas_externas():
    """Verifica ferramentas externas necessárias."""
    print_colorido("\n🔧 Verificando ferramentas externas...", "azul")
    
    ferramentas = [
        ("Docker", ["docker", "--version"]),
        ("Ngrok", ["ngrok", "version"]),
    ]
    
    for nome, comando in ferramentas:
        try:
            result = subprocess.run(comando, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                versao = result.stdout.split('\n')[0]
                print_colorido(f"   ✅ {nome}: {versao}", "verde")
            else:
                print_colorido(f"   ❌ {nome}: Não funciona", "vermelho")
        except FileNotFoundError:
            print_colorido(f"   ❌ {nome}: Não instalado", "vermelho")
            if nome == "Docker":
                print_colorido("      Baixe em: https://docker.com/get-started", "azul")
            elif nome == "Ngrok":
                print_colorido("      Baixe em: https://ngrok.com/download", "azul")
        except subprocess.TimeoutExpired:
            print_colorido(f"   ⏱️  {nome}: Timeout", "amarelo")

def criar_env_exemplo():
    """Cria arquivo .env de exemplo se não existir."""
    env_path = Path(".env")
    
    if env_path.exists():
        print_colorido("\n⚙️  Arquivo .env já existe", "azul")
        return
    
    print_colorido("\n⚙️  Criando arquivo .env de exemplo...", "azul")
    
    env_content = """# Configurações do Bot WhatsApp
# Gerado automaticamente - ajuste conforme necessário

# === IA (Ollama) ===
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1

# === WhatsApp (WAHA) ===
WAHA_BASE_URL=http://localhost:3000
WAHA_API_KEY=sha512:example_key_here
WHATSAPP_SESSION_NAME=default

# === Bot Configuration ===
BOT_TIMEOUT_MINUTES=30
MAX_CONTEXT_MESSAGES=10

# === API ===
PORT=8000
HOST=0.0.0.0
DEBUG_MODE=True

# === Logs ===
LOG_LEVEL=INFO
LOG_DIR=logs

# === Webhook (será preenchido automaticamente) ===
NGROK_URL=
"""
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print_colorido("   ✅ Arquivo .env criado", "verde")
        print_colorido("   ⚠️  Configure suas chaves antes de usar", "amarelo")
    except Exception as e:
        print_colorido(f"   ❌ Erro ao criar .env: {e}", "vermelho")

def main():
    """Função principal de instalação."""
    print_colorido("=" * 60, "azul")
    print_colorido("🛠️  INSTALADOR DE DEPENDÊNCIAS - BOT WHATSAPP", "azul")
    print_colorido("   Sistema Unificado com correções langchain-ollama", "azul") 
    print_colorido("=" * 60, "azul")
    
    etapas_ok = 0
    total_etapas = 6
    
    # 1. Verificar Python
    if verificar_python():
        etapas_ok += 1
    
    # 2. Criar diretórios
    criar_estrutura_diretorios()
    etapas_ok += 1
    
    # 3. Instalar pacotes Python
    if instalar_pip_packages():
        etapas_ok += 1
    
    # 4. Verificar instalação
    if verificar_instalacao():
        etapas_ok += 1
    
    # 5. Verificar ferramentas externas
    verificar_ferramentas_externas()
    etapas_ok += 1
    
    # 6. Criar .env
    criar_env_exemplo()
    etapas_ok += 1
    
    # Relatório final
    print_colorido("\n" + "=" * 60, "azul")
    print_colorido("📊 RELATÓRIO DE INSTALAÇÃO", "azul")
    print_colorido("=" * 60, "azul")
    
    porcentagem = (etapas_ok / total_etapas) * 100
    print_colorido(f"✅ Progresso: {porcentagem:.0f}% ({etapas_ok}/{total_etapas} etapas)", "verde")
    
    if etapas_ok == total_etapas:
        print_colorido("\n🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!", "verde")
        print_colorido("🚀 Próximos passos:", "azul")
        print("   1. Configure o arquivo .env")
        print("   2. Inicie o Ollama: ollama serve")
        print("   3. Execute: python gerenciador_sistema.py")
    else:
        print_colorido("\n⚠️  INSTALAÇÃO PARCIALMENTE CONCLUÍDA", "amarelo")
        print_colorido("   Algumas dependências podem estar faltando", "amarelo")
        print_colorido("   Verifique os erros acima e tente novamente", "amarelo")
    
    print_colorido("\n📋 COMANDOS ÚTEIS:", "azul")
    print("   python gerenciador_sistema.py          # Menu interativo")
    print("   python gerenciador_sistema.py --iniciar # Inicialização automática") 
    print("   python gerenciador_sistema.py --testar  # Executar testes")

if __name__ == "__main__":
    main()