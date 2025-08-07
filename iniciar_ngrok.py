#!/usr/bin/env python3
"""
Script para iniciar e verificar o ngrok corretamente no Windows

Este script garante que o ngrok inicie e crie o túnel adequadamente.
"""

import subprocess
import time
import requests
import json
import os
import sys

def limpar_ngrok_existente():
    """Para qualquer processo ngrok existente"""
    print("🔄 Limpando processos ngrok existentes...")
    try:
        # Tentar matar processos ngrok no Windows
        subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], 
                      capture_output=True, shell=True)
        time.sleep(2)
    except:
        pass

def iniciar_ngrok_windows(porta=8000):
    """Inicia o ngrok especificamente para Windows"""
    print(f"🚀 Iniciando ngrok na porta {porta}...")
    
    # Limpar processos antigos
    limpar_ngrok_existente()
    
    # Tentar diferentes formas de iniciar o ngrok
    comandos_possiveis = [
        ["ngrok", "http", str(porta)],
        ["ngrok.exe", "http", str(porta)],
        [r"C:\ngrok\ngrok.exe", "http", str(porta)],
        ["py", "-m", "pyngrok", "http", str(porta)]  # Se tiver pyngrok instalado
    ]
    
    processo = None
    for cmd in comandos_possiveis:
        try:
            print(f"Tentando: {' '.join(cmd)}")
            
            # Usar CREATE_NEW_CONSOLE no Windows para abrir em nova janela
            if sys.platform == "win32":
                processo = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                processo = subprocess.Popen(cmd)
            
            # Aguardar o ngrok inicializar
            print("⏳ Aguardando ngrok inicializar...")
            time.sleep(5)
            
            # Verificar se iniciou
            try:
                response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
                if response.status_code == 200:
                    print("✅ Ngrok iniciado com sucesso!")
                    return processo
            except:
                continue
                
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"Erro: {e}")
            continue
    
    return None

def obter_url_ngrok(tentativas=10):
    """Obtém a URL pública do ngrok"""
    print("🔍 Obtendo URL do ngrok...")
    
    for i in range(tentativas):
        try:
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                
                if not tunnels:
                    print(f"  Tentativa {i+1}/{tentativas}: Nenhum túnel ainda...")
                    time.sleep(2)
                    continue
                
                # Procurar túnel HTTPS
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        url = tunnel.get("public_url")
                        print(f"✅ URL do ngrok obtida: {url}")
                        return url
                
                # Se não encontrou HTTPS, pegar o primeiro
                if tunnels:
                    url = tunnels[0].get("public_url")
                    print(f"✅ URL do ngrok obtida: {url}")
                    return url
                    
        except requests.exceptions.RequestException as e:
            print(f"  Tentativa {i+1}/{tentativas}: Aguardando API do ngrok...")
            time.sleep(2)
        except Exception as e:
            print(f"  Erro: {e}")
            time.sleep(2)
    
    return None

def usar_pyngrok_alternativa(porta=8000):
    """Alternativa usando pyngrok se estiver instalado"""
    try:
        from pyngrok import ngrok as pyngrok
        
        print("📦 Usando pyngrok como alternativa...")
        
        # Configurar e iniciar
        tunnel = pyngrok.connect(porta, "http")
        url = tunnel.public_url
        
        # Converter HTTP para HTTPS se necessário
        if url.startswith("http://"):
            url = url.replace("http://", "https://")
        
        print(f"✅ Túnel criado via pyngrok: {url}")
        return url
        
    except ImportError:
        print("❌ pyngrok não está instalado")
        print("💡 Instale com: pip install pyngrok")
        return None
    except Exception as e:
        print(f"❌ Erro com pyngrok: {e}")
        return None

def salvar_url_no_env(url):
    """Salva a URL do ngrok no arquivo .env"""
    try:
        # Ler arquivo .env existente
        env_path = ".env"
        lines = []
        
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
        
        # Atualizar ou adicionar NGROK_URL
        url_atualizada = False
        for i, line in enumerate(lines):
            if line.startswith("NGROK_URL="):
                lines[i] = f"NGROK_URL={url}\n"
                url_atualizada = True
                break
        
        if not url_atualizada:
            lines.append(f"NGROK_URL={url}\n")
        
        # Salvar arquivo
        with open(env_path, "w") as f:
            f.writelines(lines)
        
        print(f"✅ URL salva no arquivo .env")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao salvar no .env: {e}")
        return False

def main():
    """Função principal"""
    print("=" * 60)
    print("🌐 CONFIGURADOR DO NGROK PARA WINDOWS")
    print("=" * 60)
    
    # Opção 1: Tentar iniciar ngrok normal
    processo = iniciar_ngrok_windows(8000)
    
    if processo:
        # Obter URL
        url = obter_url_ngrok()
        
        if url:
            print("\n" + "=" * 60)
            print("✅ NGROK CONFIGURADO COM SUCESSO!")
            print("=" * 60)
            print(f"📌 URL Pública: {url}")
            print(f"📊 Dashboard: http://localhost:4040")
            print(f"🔗 Webhook URL: {url}/webhook/whatsapp")
            
            # Salvar no .env
            salvar_url_no_env(url)
            
            print("\n📝 Próximos passos:")
            print("1. Copie a URL acima")
            print("2. Inicie a API em outro terminal:")
            print("   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
            print("\n⚠️  Mantenha esta janela aberta!")
            
            # Manter rodando
            try:
                input("\nPressione ENTER para parar o ngrok...")
            except KeyboardInterrupt:
                pass
            finally:
                if processo:
                    processo.terminate()
        else:
            print("❌ Não foi possível obter a URL do ngrok")
            print("\n💡 Tentando alternativa com pyngrok...")
            
            # Opção 2: Tentar pyngrok
            url = usar_pyngrok_alternativa(8000)
            if url:
                salvar_url_no_env(url)
                print("\n⚠️  Mantenha esta janela aberta!")
                try:
                    input("\nPressione ENTER para parar...")
                except KeyboardInterrupt:
                    pass
    else:
        print("\n❌ Não foi possível iniciar o ngrok")
        print("\n💡 Tente as seguintes alternativas:")
        print("\n1. Instalar pyngrok:")
        print("   pip install pyngrok")
        print("   python iniciar_ngrok.py")
        print("\n2. Iniciar manualmente:")
        print("   ngrok http 8000")
        print("\n3. Verificar instalação:")
        print("   - Baixe em: https://ngrok.com/download")
        print("   - Extraia para C:\\ngrok\\")
        print("   - Adicione ao PATH do Windows")

if __name__ == "__main__":
    main()