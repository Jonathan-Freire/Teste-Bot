#!/usr/bin/env python3
"""
Monitor do Sistema Bot WhatsApp

Este script monitora continuamente o status de todos os componentes
e exibe informações úteis para debug e acompanhamento.

Versão 2.1: Corrigidas importações e compatibilidade Python 3.10.11

Execute: python monitor.py
"""

import asyncio
import requests
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

class MonitorSistema:
    """
    Classe para monitorar continuamente o sistema bot WhatsApp.
    
    Esta classe verifica o status de todos os componentes do sistema:
    - API FastAPI
    - Serviço WAHA
    - Ollama
    - Ngrok
    - WhatsApp
    - Gerenciador de contexto
    - Logs do sistema
    
    Attributes:
        api_url: URL da API FastAPI local.
        waha_url: URL do serviço WAHA local.
        ollama_url: URL do serviço Ollama local.
        ngrok_url: URL da API do ngrok local.
    """
    
    def __init__(self):
        """
        Inicializa o monitor com URLs padrão dos serviços.
        
        Examples:
            >>> monitor = MonitorSistema()
            >>> print(monitor.api_url)
            "http://localhost:8000"
        """
        self.api_url = "http://localhost:8000"
        self.waha_url = "http://localhost:3000"
        self.ollama_url = "http://localhost:11434"
        self.ngrok_url = "http://localhost:4040"
        
    def limpar_tela(self):
        """
        Limpa a tela do terminal.
        """
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def verificar_servico(self, nome: str, url: str, endpoint: str = "") -> Dict[str, str]:
        """
        Verifica status de um serviço HTTP.
        
        Args:
            nome: Nome amigável do serviço.
            url: URL base do serviço.
            endpoint: Endpoint específico para testar (opcional).
            
        Returns:
            Dicionário com nome, status e detalhes do serviço.
            
        Examples:
            >>> monitor = MonitorSistema()
            >>> status = monitor.verificar_servico("API", "http://localhost:8000", "/")
            >>> print(status["status"])
            "✅ Online" ou "❌ Offline"
        """
        try:
            response = requests.get(f"{url}{endpoint}", timeout=2)
            return {
                "nome": nome,
                "status": "✅ Online",
                "detalhes": f"HTTP {response.status_code}"
            }
        except requests.exceptions.RequestException:
            return {
                "nome": nome,
                "status": "❌ Offline",
                "detalhes": "Não responde"
            }
    
    async def obter_status_whatsapp(self) -> Dict[str, Any]:
        """
        Obtém status detalhado do WhatsApp via API.
        
        Returns:
            Dicionário com informações sobre a conexão WhatsApp.
        """
        try:
            response = requests.get(f"{self.api_url}/whatsapp/status", timeout=2)
            data = response.json()
            return {
                "conectado": data.get("whatsapp_conectado", False),
                "sessao": data.get("session_name", "default"),
                "status": data.get("status", "desconhecido")
            }
        except requests.exceptions.RequestException:
            return {
                "conectado": False,
                "sessao": "N/A",
                "status": "erro"
            }
    
    async def obter_estatisticas_contexto(self) -> Dict[str, Any]:
        """
        Obtém estatísticas do gerenciador de contexto.
        
        Returns:
            Dicionário com estatísticas das sessões de conversa.
        """
        try:
            from app.core.gerenciador_contexto import gerenciador_contexto
            stats = gerenciador_contexto.obter_estatisticas_globais()
            sessoes_ativas = gerenciador_contexto.listar_sessoes_ativas()
            return {
                "sessoes_ativas": stats.get("sessoes_ativas", 0),
                "total_criadas": stats.get("total_sessoes_criadas", 0),
                "usuarios": sessoes_ativas[:5] if sessoes_ativas else []
            }
        except (ImportError, AttributeError):
            return {
                "sessoes_ativas": 0,
                "total_criadas": 0,
                "usuarios": []
            }
    
    def obter_ultimas_linhas_log(self, n: int = 5) -> List[str]:
        """
        Obtém as últimas n linhas do log.
        
        Args:
            n: Número de linhas a serem retornadas.
            
        Returns:
            Lista com as últimas linhas do log.
        """
        try:
            log_file = Path("logs/log_bot.log")
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    return lines[-n:] if lines else ["Log vazio"]
            return ["Arquivo de log não encontrado"]
        except Exception as e:
            return [f"Erro ao ler log: {e}"]
    
    def obter_info_ngrok(self) -> Dict[str, Any]:
        """
        Obtém informações do túnel ngrok.
        
        Returns:
            Dicionário com informações sobre o túnel ngrok.
        """
        try:
            response = requests.get(f"{self.ngrok_url}/api/tunnels", timeout=2)
            tunnels = response.json().get("tunnels", [])
            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    return {
                        "url": tunnel.get("public_url", "N/A"),
                        "status": "✅ Ativo",
                        "conexoes": tunnel.get("metrics", {}).get("conns", {}).get("count", 0)
                    }
            return {"url": "N/A", "status": "❌ Sem túnel", "conexoes": 0}
        except requests.exceptions.RequestException:
            return {"url": "N/A", "status": "❌ Offline", "conexoes": 0}
    
    async def exibir_dashboard(self):
        """
        Exibe o dashboard de monitoramento em tempo real.
        
        Este método executa um loop infinito que atualiza as informações
        do sistema a cada 5 segundos, permitindo comandos do usuário.
        """
        while True:
            try:
                self.limpar_tela()
                
                # Cabeçalho
                print("=" * 80)
                print(f"{'MONITOR DO BOT WHATSAPP':^80}")
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^80}")
                print("=" * 80)
                
                # Status dos Serviços
                print("\n📊 STATUS DOS SERVIÇOS:")
                print("-" * 40)
                
                servicos = [
                    self.verificar_servico("API FastAPI", self.api_url, "/"),
                    self.verificar_servico("WAHA", self.waha_url, "/api/sessions"),
                    self.verificar_servico("Ollama", self.ollama_url, "/api/tags"),
                    self.verificar_servico("Ngrok", self.ngrok_url, "/api/tunnels"),
                ]
                
                for servico in servicos:
                    print(f"{servico['nome']:15} {servico['status']:12} {servico['detalhes']}")
                
                # Status do WhatsApp
                print("\n📱 WHATSAPP:")
                print("-" * 40)
                wa_status = await self.obter_status_whatsapp()
                status_icon = "✅" if wa_status["conectado"] else "❌"
                print(f"Conectado: {status_icon} {wa_status['status']}")
                print(f"Sessão: {wa_status['sessao']}")
                
                # Informações do Ngrok
                print("\n🌐 TÚNEL NGROK:")
                print("-" * 40)
                ngrok_info = self.obter_info_ngrok()
                print(f"Status: {ngrok_info['status']}")
                print(f"URL: {ngrok_info['url']}")
                print(f"Conexões: {ngrok_info['conexoes']}")
                
                # Estatísticas de Contexto
                print("\n💬 SESSÕES DE CONVERSA:")
                print("-" * 40)
                ctx_stats = await self.obter_estatisticas_contexto()
                print(f"Sessões ativas: {ctx_stats['sessoes_ativas']}")
                print(f"Total criadas: {ctx_stats['total_criadas']}")
                if ctx_stats['usuarios']:
                    usuarios_str = ', '.join(ctx_stats['usuarios'][:3])
                    if len(ctx_stats['usuarios']) > 3:
                        usuarios_str += f" (+{len(ctx_stats['usuarios']) - 3} mais)"
                    print(f"Usuários ativos: {usuarios_str}")
                
                # Últimas linhas do log
                print("\n📝 ÚLTIMAS ATIVIDADES DO LOG:")
                print("-" * 40)
                log_lines = self.obter_ultimas_linhas_log(5)
                for line in log_lines:
                    # Truncar linhas muito longas
                    line_limpa = line.strip()
                    if len(line_limpa) > 76:
                        line_limpa = line_limpa[:73] + "..."
                    print(f"  {line_limpa}")
                
                # Instruções
                print("\n" + "=" * 80)
                print("Comandos: [Q] Sair | [L] Limpar Log | [R] Reiniciar WhatsApp | [T] Testar")
                print("Atualizando a cada 5 segundos...")
                
                # Aguardar input com timeout
                try:
                    comando = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, input, ""),
                        timeout=5
                    )
                    
                    if comando.lower() == 'q':
                        print("\nEncerrando monitor...")
                        break
                    elif comando.lower() == 'l':
                        await self.limpar_logs()
                    elif comando.lower() == 'r':
                        await self.reiniciar_whatsapp()
                    elif comando.lower() == 't':
                        await self.testar_sistema()
                        
                except asyncio.TimeoutError:
                    continue
                    
            except KeyboardInterrupt:
                print("\n\nMonitor encerrado.")
                break
            except Exception as e:
                print(f"\nErro no monitor: {e}")
                await asyncio.sleep(5)
    
    async def limpar_logs(self):
        """
        Limpa o arquivo de log criando um backup.
        """
        try:
            log_file = Path("logs/log_bot.log")
            if log_file.exists():
                # Fazer backup antes de limpar
                backup_name = f"logs/log_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                log_file.rename(backup_name)
                # Criar novo arquivo vazio
                log_file.touch()
                print(f"\n✅ Log limpo. Backup salvo em: {backup_name}")
            else:
                print("\n❌ Arquivo de log não encontrado")
        except Exception as e:
            print(f"\n❌ Erro ao limpar log: {e}")
        
        await asyncio.sleep(2)
    
    async def reiniciar_whatsapp(self):
        """
        Reinicia a sessão do WhatsApp.
        """
        try:
            print("\n🔄 Reiniciando WhatsApp...")
            from app.core.cliente_waha import cliente_waha
            
            # Parar sessão atual
            await cliente_waha.parar_sessao()
            await asyncio.sleep(2)
            
            # Iniciar nova sessão
            ngrok_info = self.obter_info_ngrok()
            webhook_url = f"{ngrok_info['url']}/webhook/whatsapp" if ngrok_info['url'] != 'N/A' else None
            
            resultado = await cliente_waha.iniciar_sessao(webhook_url)
            
            if resultado["sucesso"]:
                print("✅ WhatsApp reiniciado com sucesso")
                if resultado.get("qr_code"):
                    print("📱 Escaneie o QR code no WAHA")
            else:
                print(f"❌ Erro ao reiniciar: {resultado.get('erro')}")
                
        except Exception as e:
            print(f"\n❌ Erro ao reiniciar WhatsApp: {e}")
        
        await asyncio.sleep(3)
    
    async def testar_sistema(self):
        """
        Executa teste rápido do sistema.
        """
        try:
            print("\n🧪 Testando sistema...")
            
            # Teste 1: API
            response = requests.get(f"{self.api_url}/", timeout=5)
            print(f"  API: {'✅' if response.status_code == 200 else '❌'}")
            
            # Teste 2: Chat
            test_msg = {
                "id_usuario": "monitor_test",
                "texto": "teste rápido"
            }
            response = requests.post(f"{self.api_url}/chat", json=test_msg, timeout=10)
            print(f"  Chat: {'✅' if response.status_code == 200 else '❌'}")
            
            # Teste 3: WhatsApp
            response = requests.get(f"{self.api_url}/whatsapp/status", timeout=5)
            data = response.json()
            print(f"  WhatsApp: {'✅' if data.get('whatsapp_conectado') else '❌'}")
            
            print("\n✅ Teste concluído")
            
        except Exception as e:
            print(f"\n❌ Erro no teste: {e}")
        
        await asyncio.sleep(3)

async def main():
    """
    Função principal do monitor.
    
    Cria uma instância do monitor e inicia o dashboard interativo.
    
    Examples:
        >>> await main()
        # Inicia o monitor interativo
    """
    monitor = MonitorSistema()
    await monitor.exibir_dashboard()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitor encerrado.")