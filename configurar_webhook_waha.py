#!/usr/bin/env python3
"""
Configurador Webhook WAHA - Solução Completa

Este script resolve os problemas identificados:
1. ✅ Atualiza automaticamente o arquivo .env
2. ✅ Configura webhook corretamente no WAHA  
3. ✅ Testa conectividade antes de configurar
4. ✅ Gera API keys seguras
5. ✅ Interface step-by-step

Execute: python configurador_webhook_waha.py
"""

import asyncio
import requests
import json
import os
import hashlib
import secrets
import string
import time
from pathlib import Path
from dotenv import load_dotenv, set_key

class Cores:
    VERDE = '\033[92m'
    AMARELO = '\033[93m'
    VERMELHO = '\033[91m'
    AZUL = '\033[94m'
    MAGENTA = '\033[95m'
    CIANO = '\033[96m'
    RESET = '\033[0m'
    NEGRITO = '\033[1m'

def print_colorido(texto: str, cor: str = Cores.RESET):
    """Imprime texto colorido."""
    print(f"{cor}{texto}{Cores.RESET}")

def print_titulo(titulo: str):
    """Imprime título formatado."""
    print("\n" + "=" * 60)
    print_colorido(f"  {titulo}", Cores.NEGRITO + Cores.AZUL)
    print("=" * 60)

def print_sucesso(mensagem: str):
    print_colorido(f"✅ {mensagem}", Cores.VERDE)

def print_erro(mensagem: str):
    print_colorido(f"❌ {mensagem}", Cores.VERMELHO)

def print_aviso(mensagem: str):
    print_colorido(f"⚠️  {mensagem}", Cores.AMARELO)

def print_info(mensagem: str):
    print_colorido(f"ℹ️  {mensagem}", Cores.AZUL)

class ConfiguradorWebhookWAHA:
    """
    Configurador completo que resolve todos os problemas identificados.
    
    Problemas resolvidos:
    1. Geração e salvamento automático da WAHA_API_KEY
    2. Obtenção e salvamento automático da NGROK_URL
    3. Configuração correta do webhook no WAHA
    4. Testes de conectividade antes da configuração
    5. Interface passo-a-passo para debug
    
    Attributes:
        env_path: Caminho para o arquivo .env
        waha_api_key: API key gerada ou existente
        ngrok_url: URL pública do ngrok
        webhook_url: URL completa do webhook
    """
    
    def __init__(self):
        """
        Inicializa o configurador.
        
        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> print(config.env_path)
            .env
        """
        self.env_path = Path(".env")
        self.waha_api_key_plain = None
        self.waha_api_key_hash = None
        self.ngrok_url = None
        self.webhook_url = None
        self.waha_base_url = os.getenv("WAHA_BASE_URL", "http://localhost:3000")
        
        # Carregar .env se existir
        if self.env_path.exists():
            load_dotenv()
    
    def gerar_api_key_segura(self) -> tuple[str, str]:
        """
        Gera uma API key segura e seu hash SHA512.

        Returns:
            tuple[str, str]: Tupla contendo a chave em texto plano e o hash
            no formato ``sha512:<hash>``.

        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> plain, hashed = config.gerar_api_key_segura()
            >>> plain != hashed and hashed.startswith("sha512:")
            True
        """
        # Gerar string aleatória segura (texto plano)
        random_string = ''.join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(64)
        )

        # Criar hash SHA512
        sha512_hash = hashlib.sha512(random_string.encode()).hexdigest()

        return random_string, f"sha512:{sha512_hash}"
    
    def atualizar_env(self, chave: str, valor: str):
        """
        Atualiza ou adiciona uma chave no arquivo .env.
        
        Args:
            chave: Nome da variável de ambiente
            valor: Valor a ser definido
            
        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> config.atualizar_env("TEST_VAR", "test_value")
        """
        try:
            # Usar python-dotenv para atualizar corretamente
            set_key(str(self.env_path), chave, valor)
            print_info(f"✓ {chave} atualizada no .env")
        except Exception as e:
            print_erro(f"Erro ao atualizar {chave}: {e}")
    
    def obter_ngrok_url(self) -> str:
        """
        Obtém a URL pública atual do ngrok.
        
        Returns:
            str: URL pública do ngrok ou None se não encontrada
            
        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> url = config.obter_ngrok_url()
            >>> print(url.startswith("https://") if url else "None")
        """
        try:
            print_info("Obtendo URL do ngrok...")
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        url = tunnel.get("public_url")
                        print_sucesso(f"URL do ngrok encontrada: {url}")
                        return url
                
                print_erro("Nenhum túnel HTTPS encontrado no ngrok")
                return None
            else:
                print_erro(f"Ngrok API retornou status {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            print_erro("Ngrok não está rodando em localhost:4040")
            print_info("Execute: ngrok http 8000")
            return None
        except Exception as e:
            print_erro(f"Erro ao obter URL do ngrok: {e}")
            return None
    
    def verificar_api_funcionando(self) -> bool:
        """
        Verifica se a API FastAPI está funcionando.
        
        Returns:
            bool: True se a API está respondendo
        """
        try:
            print_info("Verificando se API FastAPI está rodando...")
            response = requests.get("http://localhost:8000/", timeout=5)
            
            if response.status_code == 200:
                print_sucesso("API FastAPI está funcionando")
                return True
            else:
                print_erro(f"API retornou status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            print_erro("API não está rodando em localhost:8000")
            print_info("Execute: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return False
        except Exception as e:
            print_erro(f"Erro ao verificar API: {e}")
            return False
    
    def testar_webhook_conectividade(self, webhook_url: str) -> bool:
        """
        Testa se o webhook está acessível externamente.
        
        Args:
            webhook_url: URL completa do webhook para testar
            
        Returns:
            bool: True se o webhook está acessível
            
        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> ok = config.testar_webhook_conectividade("https://test.ngrok.app/webhook/whatsapp")
            >>> print(type(ok))
            <class 'bool'>
        """
        try:
            print_info("Testando acessibilidade do webhook...")
            
            # Fazer uma requisição POST de teste
            test_payload = {
                "payload": {
                    "event": "test",
                    "data": {
                        "from": "test@c.us",
                        "id": "test_msg_123",
                        "type": "text",
                        "body": "teste de conectividade"
                    }
                }
            }
            
            response = requests.post(
                webhook_url,
                json=test_payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("status") == "received":
                        print_sucesso("Webhook está acessível e respondendo corretamente")
                        return True
                except:
                    pass
                
                print_sucesso("Webhook está acessível")
                return True
            else:
                print_erro(f"Webhook retornou status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print_erro("Timeout ao testar webhook (>10s)")
            return False
        except requests.exceptions.ConnectionError:
            print_erro("Não foi possível conectar com o webhook")
            print_info("Verifique se a URL do ngrok está correta")
            return False
        except Exception as e:
            print_erro(f"Erro ao testar webhook: {e}")
            return False
    
    def verificar_waha_funcionando(self) -> bool:
        """
        Verifica se o WAHA está funcionando.
        
        Returns:
            bool: True se WAHA está acessível
        """
        try:
            print_info("Verificando se WAHA está funcionando...")
            response = requests.get(f"{self.waha_base_url}/api/sessions", timeout=5)
            
            if response.status_code in [200, 401]:  # 401 é OK se tiver autenticação
                print_sucesso("WAHA está funcionando")
                return True
            else:
                print_erro(f"WAHA retornou status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            print_erro(f"WAHA não está rodando em {self.waha_base_url}")
            print_info(
                "Execute: docker run -it --rm -p 3000:3000 devlikeapro/waha"
            )
            return False
        except Exception as e:
            print_erro(f"Erro ao verificar WAHA: {e}")
            return False
    
    def configurar_webhook_no_waha(self, api_key_plain: str, webhook_url: str) -> bool:
        """
        Configura o webhook no WAHA corretamente.

        Args:
            api_key_plain: API key em texto plano
            webhook_url: URL do webhook
            
        Returns:
            bool: True se configurado com sucesso
            
        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> ok = config.configurar_webhook_no_waha("sha512:key", "https://test.ngrok.app/webhook/whatsapp")
            >>> print(type(ok))
            <class 'bool'>
        """
        try:
            print_info("Configurando webhook no WAHA...")
            
            # Primeiro, parar sessão existente se houver
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": api_key_plain,
            }

            session_name = os.getenv("WHATSAPP_SESSION_NAME", "default")

            # Tentar parar sessão existente (ignorar erros)
            try:
                requests.delete(
                    f"{self.waha_base_url}/api/sessions/default",
                    headers=headers,
                    timeout=5
                )
                time.sleep(2)  # Aguardar um pouco
            except:
                pass

            # Criar nova sessão com webhook
            session_config = {
                "name": session_name,
                "start": True,
                "config": {
                    "metadata": {
                        "user.id": "123",
                        "user.email": "bot@exemplo.com"
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
                                "session.status"
                            ],
                            "hmac": None,
                            "retries": None,
                            "customHeaders": None
                        }
                    ]
                }
            }
            
            response = requests.post(
                f"{self.waha_base_url}/api/sessions",
                json=session_config,
                headers=headers,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                print_sucesso("Sessão WAHA criada com webhook configurado")
                
                # Aguardar um pouco e verificar status
                time.sleep(3)
                try:
                    status_response = requests.get(
                        f"{self.waha_base_url}/api/sessions/default",
                        headers=headers,
                        timeout=5
                    )
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get("status", "UNKNOWN")
                        print_info(f"Status da sessão: {status}")
                        
                        if status == "SCAN_QR_CODE":
                            print_sucesso("Sessão pronta! Você precisa escanear o QR code")
                            print_info(
                                f"Acesse {self.waha_base_url} para ver o QR code"
                            )
                        elif status == "WORKING":
                            print_sucesso("Sessão já autenticada e funcionando!")
                            
                except Exception as e:
                    print_aviso(f"Não foi possível verificar status: {e}")
                
                return True
            else:
                print_erro(f"Falha ao criar sessão: {response.status_code}")
                try:
                    error_detail = response.json()
                    print_erro(f"Detalhes: {error_detail}")
                except:
                    print_erro(f"Resposta: {response.text}")
                return False
                
        except Exception as e:
            print_erro(f"Erro ao configurar webhook no WAHA: {e}")
            return False
    
    async def configuracao_completa(self):
        """
        Executa configuração completa passo a passo.
        
        Esta função resolve todos os problemas identificados:
        1. Gera/obtém API key segura
        2. Obtém URL do ngrok
        3. Atualiza .env automaticamente
        4. Testa conectividade
        5. Configura webhook no WAHA
        
        Examples:
            >>> config = ConfiguradorWebhookWAHA()
            >>> await config.configuracao_completa()
        """
        print_titulo("CONFIGURAÇÃO COMPLETA WEBHOOK WAHA")
        print_colorido("Resolvendo todos os problemas identificados...", Cores.CIANO)
        
        # PASSO 1: Verificar serviços básicos
        print_colorido("\n🔍 PASSO 1: Verificando serviços", Cores.NEGRITO)
        
        api_ok = self.verificar_api_funcionando()
        waha_ok = self.verificar_waha_funcionando()
        
        if not api_ok or not waha_ok:
            print_erro("Serviços básicos não estão funcionando")
            print_info("Execute primeiro: python gerenciador_sistema.py --iniciar")
            return
        
        # PASSO 2: Obter/gerar API key
        print_colorido("\n🔑 PASSO 2: Configurando API key", Cores.NEGRITO)
        
        # Verificar se já existe uma API key válida
        existing_hash = os.getenv("WAHA_API_KEY")
        existing_plain = os.getenv("WAHA_API_KEY_PLAIN")

        if existing_hash and existing_plain:
            print_info("API key existente encontrada no .env")
            self.waha_api_key_hash = existing_hash
            self.waha_api_key_plain = existing_plain
        else:
            print_info("Gerando nova API key segura...")
            plain, hashed = self.gerar_api_key_segura()
            self.waha_api_key_plain = plain
            self.waha_api_key_hash = hashed
            self.atualizar_env("WAHA_API_KEY", hashed)
            self.atualizar_env("WAHA_API_KEY_PLAIN", plain)
            os.environ["WAHA_API_KEY"] = hashed
            os.environ["WAHA_API_KEY_PLAIN"] = plain
            load_dotenv()
            if (
                os.getenv("WAHA_API_KEY") == hashed
                and os.getenv("WAHA_API_KEY_PLAIN") == plain
            ):
                print_sucesso("Nova API key gerada e salva no .env")
            else:
                print_erro("Erro ao salvar API key no .env")
            print_aviso(f"Guarde a chave em local seguro: {plain}")
        
        # PASSO 3: Obter URL do ngrok
        print_colorido("\n🌐 PASSO 3: Obtendo URL do ngrok", Cores.NEGRITO)
        
        self.ngrok_url = self.obter_ngrok_url()
        if not self.ngrok_url:
            print_erro("Não foi possível obter URL do ngrok")
            print_info("Verifique se o ngrok está rodando: ngrok http 8000")
            return
        
        # Salvar URL no .env
        self.atualizar_env("NGROK_URL", self.ngrok_url)
        
        # Construir URL do webhook
        self.webhook_url = f"{self.ngrok_url}/webhook/whatsapp"
        print_info(f"URL do webhook: {self.webhook_url}")
        
        # PASSO 4: Testar conectividade
        print_colorido("\n🧪 PASSO 4: Testando conectividade", Cores.NEGRITO)
        
        webhook_ok = self.testar_webhook_conectividade(self.webhook_url)
        if not webhook_ok:
            print_erro("Webhook não está acessível")
            print_info("Possíveis causas:")
            print_info("  - API não está rodando")
            print_info("  - Ngrok não está funcionando")
            print_info("  - Firewall bloqueando conexões")
            return
        
        # PASSO 5: Configurar webhook no WAHA
        print_colorido("\n⚙️  PASSO 5: Configurando webhook no WAHA", Cores.NEGRITO)
        
        config_ok = self.configurar_webhook_no_waha(
            self.waha_api_key_plain, self.webhook_url
        )
        if not config_ok:
            print_erro("Falha ao configurar webhook no WAHA")
            return
        
        # PASSO 6: Resumo final
        print_colorido("\n✅ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!", Cores.NEGRITO + Cores.VERDE)
        print()
        print_colorido("📋 RESUMO DA CONFIGURAÇÃO:", Cores.NEGRITO)
        print(f"   🔑 API Key: {self.waha_api_key_plain[:20]}...")
        print(f"   🌐 Ngrok URL: {self.ngrok_url}")
        print(f"   🔗 Webhook: {self.webhook_url}")
        print(f"   📄 Arquivo .env: Atualizado")
        
        print_colorido("\n🎯 PRÓXIMOS PASSOS:", Cores.NEGRITO)
        print(f"   1. Acesse: {self.waha_base_url}")
        print("   2. Escaneie o QR code com seu WhatsApp")
        print("   3. Teste enviando uma mensagem")
        
        print_colorido("\n💬 MENSAGENS DE TESTE:", Cores.CIANO)
        print("   'olá'")
        print("   'quais os produtos mais vendidos este mês?'")
        print("   'qual o limite de crédito do cliente 123?'")
    
    async def diagnostico_problemas(self):
        """
        Executa diagnóstico completo dos problemas.
        
        Esta função identifica exatamente o que está errado
        e fornece soluções específicas.
        """
        print_titulo("DIAGNÓSTICO DE PROBLEMAS")
        
        print_colorido("🔍 Verificando cada componente...", Cores.CIANO)
        
        problemas_encontrados = []
        solucoes = []
        
        # 1. Verificar .env
        if not self.env_path.exists():
            problemas_encontrados.append("❌ Arquivo .env não existe")
            solucoes.append("Criar arquivo .env com: python instalar_dependencias.py")
        else:
            load_dotenv()
            waha_key = os.getenv("WAHA_API_KEY")
            ngrok_url = os.getenv("NGROK_URL")
            
            if not waha_key or waha_key == "your_api_key_here":
                problemas_encontrados.append("❌ WAHA_API_KEY não configurada no .env")
                solucoes.append("Executar: python configurador_webhook_waha.py")
            
            if not ngrok_url:
                problemas_encontrados.append("❌ NGROK_URL não configurada no .env")
                solucoes.append("Executar configuração automática")
        
        # 2. Verificar serviços
        try:
            requests.get("http://localhost:8000/", timeout=2)
            print_sucesso("API FastAPI funcionando")
        except:
            problemas_encontrados.append("❌ API FastAPI não está rodando")
            solucoes.append("Execute: python -m uvicorn app.main:app --port 8000")

        try:
            requests.get(f"{self.waha_base_url}/api/sessions", timeout=2)
            print_sucesso("WAHA funcionando")
        except:
            problemas_encontrados.append("❌ WAHA não está rodando")
            solucoes.append("Execute: docker run -it --rm -p 3000:3000 devlikeapro/waha")
        
        try:
            response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
            tunnels = response.json().get("tunnels", [])
            if tunnels:
                print_sucesso("Ngrok funcionando")
            else:
                problemas_encontrados.append("❌ Ngrok sem túneis ativos")
                solucoes.append("Execute: ngrok http 8000")
        except:
            problemas_encontrados.append("❌ Ngrok não está rodando")
            solucoes.append("Execute: ngrok http 8000")
        
        # Mostrar diagnóstico
        if problemas_encontrados:
            print_colorido("\n🚨 PROBLEMAS ENCONTRADOS:", Cores.VERMELHO)
            for problema in problemas_encontrados:
                print(f"   {problema}")
            
            print_colorido("\n💡 SOLUÇÕES:", Cores.AMARELO)
            for solucao in solucoes:
                print(f"   • {solucao}")
        else:
            print_sucesso("Nenhum problema detectado!")
    
    def mostrar_menu(self):
        """
        Mostra menu interativo.
        """
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print_colorido("=" * 60, Cores.AZUL)
        print_colorido("🔧 CONFIGURADOR WEBHOOK WAHA", Cores.NEGRITO + Cores.AZUL)
        print_colorido("   Solução para problemas de configuração", Cores.CIANO)
        print_colorido("=" * 60, Cores.AZUL)
        
        print_colorido("\n📋 OPÇÕES:", Cores.NEGRITO)
        print_colorido("  [1] 🚀 Configuração Automática Completa", Cores.VERDE)
        print_colorido("      Resolve todos os problemas automaticamente")
        print()
        print_colorido("  [2] 🔍 Diagnóstico de Problemas", Cores.AMARELO) 
        print_colorido("      Identifica o que está errado")
        print()
        print_colorido("  [3] 🔑 Gerar Nova API Key", Cores.CIANO)
        print_colorido("      Cria nova API key e atualiza .env")
        print()
        print_colorido("  [4] 🌐 Obter URL Ngrok", Cores.MAGENTA)
        print_colorido("      Encontra e salva URL do ngrok")
        print()
        print_colorido("  [5] 🧪 Testar Webhook", Cores.AZUL)
        print_colorido("      Testa se webhook está acessível")
        print()
        print_colorido("  [0] 🚪 Sair", Cores.AMARELO)
        print()
        print_colorido("=" * 60, Cores.AZUL)

async def main():
    """
    Função principal com menu interativo.
    
    Examples:
        >>> await main()
        # Executa menu interativo
    """
    configurador = ConfiguradorWebhookWAHA()
    
    while True:
        configurador.mostrar_menu()
        
        try:
            opcao = input("\n👉 Escolha uma opção: ").strip()
            
            if opcao == "1":
                await configurador.configuracao_completa()
            elif opcao == "2":
                await configurador.diagnostico_problemas()
            elif opcao == "3":
                print_titulo("GERANDO NOVA API KEY")
                plain, hashed = configurador.gerar_api_key_segura()
                configurador.atualizar_env("WAHA_API_KEY", hashed)
                configurador.atualizar_env("WAHA_API_KEY_PLAIN", plain)
                os.environ["WAHA_API_KEY"] = hashed
                os.environ["WAHA_API_KEY_PLAIN"] = plain
                load_dotenv()
                if (
                    os.getenv("WAHA_API_KEY") == hashed
                    and os.getenv("WAHA_API_KEY_PLAIN") == plain
                ):
                    print_sucesso(f"Nova API key gerada: {plain[:20]}...")
                else:
                    print_erro("Erro ao salvar API key no .env")
                print_aviso("Guarde esta chave em local seguro")
            elif opcao == "4":
                print_titulo("OBTENDO URL DO NGROK")
                url = configurador.obter_ngrok_url()
                if url:
                    configurador.atualizar_env("NGROK_URL", url)
            elif opcao == "5":
                print_titulo("TESTANDO WEBHOOK")
                ngrok_url = configurador.obter_ngrok_url()
                if ngrok_url:
                    webhook_url = f"{ngrok_url}/webhook/whatsapp"
                    configurador.testar_webhook_conectividade(webhook_url)
            elif opcao == "0":
                print_colorido("\n👋 Encerrando configurador...", Cores.AMARELO)
                break
            else:
                print_erro("Opção inválida!")
            
            if opcao != "0":
                input("\nPressione ENTER para continuar...")
                
        except KeyboardInterrupt:
            print_colorido("\n\n👋 Encerrando...", Cores.AMARELO)
            break
        except Exception as e:
            print_erro(f"Erro: {e}")
            input("\nPressione ENTER para continuar...")

if __name__ == "__main__":
    asyncio.run(main())