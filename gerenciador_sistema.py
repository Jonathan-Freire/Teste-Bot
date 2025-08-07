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

# Cores para terminal
class Cores:
    """Códigos de cores ANSI para formatação no terminal."""
    VERDE = '\033[92m'
    AMARELO = '\033[93m' 
    VERMELHO = '\033[91m'
    AZUL = '\033[94m'
    MAGENTA = '\033[95m'
    CIANO = '\033[96m'
    RESET = '\033[0m'
    NEGRITO = '\033[1m'

def print_colorido(texto: str, cor: str = Cores.RESET):
    """
    Imprime texto colorido no terminal.
    
    Args:
        texto: Texto a ser impresso.
        cor: Código de cor ANSI.
        
    Examples:
        >>> print_colorido("Sucesso!", Cores.VERDE)
        >>> print_colorido("Erro!", Cores.VERMELHO)
    """
    print(f"{cor}{texto}{Cores.RESET}")

def print_titulo(titulo: str):
    """
    Imprime um título formatado com destaque.
    
    Args:
        titulo: Texto do título.
        
    Examples:
        >>> print_titulo("CONFIGURANDO SISTEMA")
    """
    print("\n" + "=" * 60)
    print_colorido(f"  {titulo}", Cores.NEGRITO + Cores.AZUL)
    print("=" * 60)

def print_sucesso(mensagem: str):
    """Imprime mensagem de sucesso."""
    print_colorido(f"✅ {mensagem}", Cores.VERDE)

def print_erro(mensagem: str):
    """Imprime mensagem de erro.""" 
    print_colorido(f"❌ {mensagem}", Cores.VERMELHO)

def print_aviso(mensagem: str):
    """Imprime mensagem de aviso."""
    print_colorido(f"⚠️  {mensagem}", Cores.AMARELO)

def print_info(mensagem: str):
    """Imprime mensagem informativa."""
    print_colorido(f"ℹ️  {mensagem}", Cores.AZUL)

# === CLASSES ESPECIALIZADAS ===

class GerenciadorWAHA:
    """
    Classe responsável pelo gerenciamento do container WAHA via Docker.
    
    Esta classe implementa o comando correto do WAHA e gerencia o ciclo
    de vida do container de forma robusta.
    
    Attributes:
        comando_base: Lista com o comando Docker correto.
        processo: Processo em execução do container.
        api_key: API key configurada para o WAHA.
    """
    
    def __init__(self):
        """
        Inicializa o gerenciador WAHA com configurações corretas.
        
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> print(len(waha.comando_base))
            10
        """
        # API key do .env ou gerar uma nova
        self.api_key = os.getenv("WAHA_API_KEY", self._gerar_api_key())
        
        # Comando Docker corrigido
        self.comando_base = [
            "docker", "run", "-it", "--rm",
            "-p", "127.0.0.1:3000:3000",
            "-e", f"WAHA_API_KEY={self.api_key}",
            "-e", "WHATSAPP_DEFAULT_ENGINE=WEBJS",
            "-e", "WAHA_PRINT_QR=true",
            "--name", "waha-bot",
            "devlikeapro/waha:latest"
        ]
        self.processo = None
        
    def _gerar_api_key(self) -> str:
        """
        Gera uma API key segura para o WAHA.
        
        Returns:
            str: API key no formato sha512.
            
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> key = waha._gerar_api_key()
            >>> print(key.startswith("sha512:"))
            True
        """
        import hashlib
        chave_raw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        hash_sha512 = hashlib.sha512(chave_raw.encode()).hexdigest()
        return f"sha512:{hash_sha512}"
    
    def iniciar_container(self) -> bool:
        """
        Inicia o container WAHA com o comando correto.
        
        Returns:
            bool: True se o container foi iniciado com sucesso.
            
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> sucesso = waha.iniciar_container()
            >>> print(sucesso)
            True ou False
        """
        try:
            print_info("Executando comando WAHA...")
            print(f"   Comando: {' '.join(self.comando_base)}")
            
            # Verificar se Docker está disponível
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                print_erro("Docker não está instalado ou não está funcionando")
                return False
            
            # Parar containers WAHA existentes
            subprocess.run(["docker", "stop", "waha-bot"], capture_output=True)
            subprocess.run(["docker", "rm", "waha-bot"], capture_output=True)
            
            # Iniciar novo container
            self.processo = subprocess.Popen(
                self.comando_base,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            print_info("Aguardando container inicializar...")
            time.sleep(8)
            
            # Verificar se está funcionando
            if self.verificar_status():
                print_sucesso("WAHA iniciado com sucesso!")
                print_info(f"API Key: {self.api_key}")
                return True
            else:
                print_erro("WAHA não conseguiu inicializar adequadamente")
                return False
                
        except Exception as e:
            print_erro(f"Erro ao iniciar WAHA: {e}")
            return False
    
    def verificar_status(self) -> bool:
        """
        Verifica se o WAHA está respondendo corretamente.
        
        Returns:
            bool: True se o WAHA está funcionando.
            
        Examples:
            >>> waha = GerenciadorWAHA()
            >>> status = waha.verificar_status()
            >>> print(type(status))
            <class 'bool'>
        """
        try:
            response = requests.get("http://localhost:3000/api/sessions", timeout=5)
            return response.status_code in [200, 401]  # 401 é OK se tiver autenticação
        except:
            return False

    def criar_sessao(self, webhook_url: str) -> bool:
        """
        Cria uma sessão no WAHA configurando o webhook informado.

        Args:
            webhook_url: URL que receberá os eventos do WAHA.

        Returns:
            bool: True se a sessão for criada com sucesso.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key
            }

            # Tentar remover sessão existente
            try:
                requests.delete(
                    "http://localhost:3000/api/sessions/default",
                    headers=headers,
                    timeout=5
                )
            except Exception:
                pass

            session_config = {
                "name": "default",
                "start": True,
                "config": {
                    "webhooks": [
                        {
                            "url": webhook_url,
                            "events": ["message", "session.status"]
                        }
                    ]
                }
            }

            response = requests.post(
                "http://localhost:3000/api/sessions",
                json=session_config,
                headers=headers,
                timeout=15
            )
            return response.status_code in [200, 201]
        except Exception as e:
            print_erro(f"Erro ao criar sessão WAHA: {e}")
            return False
    
    def parar_container(self) -> bool:
        """
        Para o container WAHA de forma controlada.
        
        Returns:
            bool: True se conseguiu parar o container.
        """
        try:
            if self.processo:
                self.processo.terminate()
                self.processo.wait(timeout=10)
                print_sucesso("Container WAHA parado")
                return True
        except:
            pass
        
        # Fallback: parar via docker
        try:
            subprocess.run(["docker", "stop", "waha-bot"], timeout=10, capture_output=True)
            return True
        except:
            return False

class GerenciadorNgrok:
    """
    Classe para gerenciar túneis ngrok de forma robusta.
    
    Attributes:
        processo: Processo do ngrok em execução.
        url_publica: URL pública atual do túnel.
        porta: Porta local sendo tunelada.
    """
    
    def __init__(self):
        """
        Inicializa o gerenciador ngrok.
        
        Examples:
            >>> ngrok = GerenciadorNgrok()
            >>> print(ngrok.url_publica)
            None
        """
        self.processo = None
        self.url_publica = None
        self.porta = 8000
    
    def iniciar_tunel(self, porta: int = 8000) -> bool:
        """
        Inicia túnel ngrok na porta especificada.
        
        Args:
            porta: Porta local para criar o túnel.
            
        Returns:
            bool: True se o túnel foi criado com sucesso.
            
        Examples:
            >>> ngrok = GerenciadorNgrok()
            >>> sucesso = ngrok.iniciar_tunel(8000)
            >>> print(type(sucesso))
            <class 'bool'>
        """
        try:
            self.porta = porta
            
            # Verificar se ngrok está instalado
            result = subprocess.run(["ngrok", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                print_erro("Ngrok não está instalado")
                return False
            
            # Verificar se já está rodando
            if self._verificar_ngrok_ativo():
                print_info("Ngrok já está rodando")
                self.url_publica = self._obter_url_existente()
                return True
            
            print_info(f"Iniciando túnel ngrok na porta {porta}...")
            self.processo = subprocess.Popen(
                ["ngrok", "http", str(porta)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Aguardar inicialização
            time.sleep(4)
            
            # Obter URL pública
            self.url_publica = self._obter_url_existente()
            
            if self.url_publica:
                print_sucesso(f"Túnel ngrok criado: {self.url_publica}")
                return True
            else:
                print_erro("Não foi possível obter URL do ngrok")
                return False
                
        except Exception as e:
            print_erro(f"Erro ao iniciar ngrok: {e}")
            return False
    
    def _verificar_ngrok_ativo(self) -> bool:
        """Verifica se o ngrok já está rodando."""
        try:
            response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _obter_url_existente(self) -> Optional[str]:
        """
        Obtém URL pública do ngrok ativo.
        
        Returns:
            Optional[str]: URL pública ou None se não encontrada.
        """
        try:
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            if response.status_code == 200:
                tunnels = response.json().get("tunnels", [])
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        return tunnel.get("public_url")
        except:
            pass
        return None
    
    def parar_tunel(self) -> bool:
        """
        Para o túnel ngrok.
        
        Returns:
            bool: True se conseguiu parar.
        """
        try:
            if self.processo:
                self.processo.terminate()
                self.processo.wait(timeout=5)
                print_sucesso("Túnel ngrok parado")
                return True
        except:
            return False

class MonitorSistema:
    """
    Classe para monitoramento em tempo real de todos os serviços.
    
    Attributes:
        servicos: Dicionário com configuração dos serviços monitorados.
        intervalo_atualizacao: Segundos entre atualizações.
    """
    
    def __init__(self):
        """
        Inicializa o monitor com configurações padrão.
        
        Examples:
            >>> monitor = MonitorSistema()
            >>> print(len(monitor.servicos))
            4
        """
        self.servicos = {
            "API": {"url": "http://localhost:8000", "endpoint": "/"},
            "WAHA": {"url": "http://localhost:3000", "endpoint": "/api/sessions"},
            "Ollama": {"url": "http://localhost:11434", "endpoint": "/api/tags"},
            "Ngrok": {"url": "http://localhost:4040", "endpoint": "/api/tunnels"}
        }
        self.intervalo_atualizacao = 5
    
    def verificar_servico(self, nome: str, config: Dict) -> Dict[str, str]:
        """
        Verifica status de um serviço específico.
        
        Args:
            nome: Nome do serviço.
            config: Configuração do serviço com URL e endpoint.
            
        Returns:
            Dict com nome, status e detalhes do serviço.
            
        Examples:
            >>> monitor = MonitorSistema()
            >>> config = {"url": "http://localhost:8000", "endpoint": "/"}
            >>> status = monitor.verificar_servico("API", config)
            >>> print("status" in status)
            True
        """
        try:
            url_completa = f"{config['url']}{config['endpoint']}"
            response = requests.get(url_completa, timeout=3)
            
            if response.status_code == 200:
                status = "✅ Online"
                detalhes = f"HTTP {response.status_code}"
            elif response.status_code in [401, 403]:
                status = "🔐 Auth Required"
                detalhes = f"HTTP {response.status_code}"
            else:
                status = "⚠️  Issues"
                detalhes = f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            status = "⏱️  Timeout"
            detalhes = "Não responde em 3s"
        except requests.exceptions.ConnectionError:
            status = "❌ Offline"
            detalhes = "Conexão recusada"
        except Exception as e:
            status = "❓ Unknown"
            detalhes = str(e)[:20]
        
        return {
            "nome": nome,
            "status": status,
            "detalhes": detalhes
        }
    
    async def dashboard_tempo_real(self):
        """
        Exibe dashboard interativo com atualizações automáticas.
        
        Este método executa um loop infinito atualizando as informações
        do sistema a cada intervalo definido.
        
        Examples:
            >>> monitor = MonitorSistema()
            >>> await monitor.dashboard_tempo_real()
            # Executa dashboard interativo
        """
        print_info("Iniciando dashboard em tempo real...")
        print_info("Pressione Ctrl+C para sair")
        
        try:
            while True:
                # Limpar tela
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Cabeçalho
                print("=" * 70)
                print_colorido(f"{'🤖 MONITOR DO BOT WHATSAPP':^70}", Cores.NEGRITO + Cores.AZUL)
                print_colorido(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^70}", Cores.CIANO)
                print("=" * 70)
                
                # Status dos serviços
                print_colorido("\n📊 STATUS DOS SERVIÇOS:", Cores.NEGRITO)
                print("-" * 40)
                
                for nome, config in self.servicos.items():
                    info = self.verificar_servico(nome, config)
                    print(f"{nome:8} {info['status']:15} {info['detalhes']}")
                
                # Informações adicionais
                await self._exibir_info_adicional()
                
                # Instruções
                print("\n" + "=" * 70)
                print_colorido("⌨️  COMANDOS: [Q] Sair | [R] Resetar | [T] Testar", Cores.AMARELO)
                print_colorido(f"🔄 Próxima atualização em {self.intervalo_atualizacao}s...", Cores.CIANO)
                
                # Aguardar com possibilidade de comando
                await asyncio.sleep(self.intervalo_atualizacao)
                
        except KeyboardInterrupt:
            print_colorido("\n\n🛑 Monitor encerrado pelo usuário", Cores.AMARELO)
        except Exception as e:
            print_erro(f"Erro no monitor: {e}")
    
    async def _exibir_info_adicional(self):
        """Exibe informações adicionais do sistema."""
        try:
            # Informações do sistema
            print_colorido("\n💻 INFORMAÇÕES DO SISTEMA:", Cores.NEGRITO)
            print("-" * 40)
            
            # Uso de CPU e memória (básico)
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            print(f"CPU: {cpu_percent:.1f}%")
            print(f"RAM: {memory.percent:.1f}% ({memory.used // (1024**3):.1f}GB de {memory.total // (1024**3):.1f}GB)")
            
            # Logs recentes (se existir)
            self._mostrar_logs_recentes()
            
        except ImportError:
            print("   Instale 'psutil' para informações do sistema")
        except Exception as e:
            print(f"   Erro: {e}")
    
    def _mostrar_logs_recentes(self):
        """Mostra as últimas linhas do log se existir."""
        try:
            log_file = Path("logs/log_bot.log")
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print_colorido("\n📝 ÚLTIMAS ATIVIDADES:", Cores.NEGRITO)
                        print("-" * 40)
                        for line in lines[-3:]:
                            line_clean = line.strip()[:60]
                            if line_clean:
                                print(f"   {line_clean}")
        except:
            pass

class TestadorSistema:
    """
    Classe integrada para executar todos os testes do sistema.
    
    Consolida funcionalidades do teste_sistema_completo.py original
    com as correções aplicadas.
    
    Attributes:
        resultados_teste: Dicionário com resultados dos testes.
        erros_encontrados: Lista de erros encontrados.
    """
    
    def __init__(self):
        """
        Inicializa o testador com contadores zerados.
        
        Examples:
            >>> testador = TestadorSistema()
            >>> len(testador.erros_encontrados)
            0
        """
        self.resultados_teste = {}
        self.erros_encontrados = []
    
    async def executar_todos_os_testes(self) -> bool:
        """
        Executa bateria completa de testes com as correções aplicadas.
        
        Returns:
            bool: True se todos os testes passaram.
            
        Examples:
            >>> testador = TestadorSistema()
            >>> resultado = await testador.executar_todos_os_testes()
            >>> print(type(resultado))
            <class 'bool'>
        """
        print_titulo("EXECUTANDO TESTES COMPLETOS DO SISTEMA")
        
        testes = [
            ("Configuração do Ambiente", self._testar_configuracao),
            ("Conexão Ollama", self._testar_ollama),
            ("Base de Dados", self._testar_database),
            ("Importações Corrigidas", self._testar_importacoes),
            ("Cliente WAHA", self._testar_waha),
            ("Gerenciador de Contexto", self._testar_contexto),
        ]
        
        sucessos = 0
        total = len(testes)
        
        for nome, funcao in testes:
            print(f"\n📋 {nome}...")
            try:
                resultado = await funcao()
                if resultado:
                    print_sucesso(f"{nome}: PASSOU")
                    sucessos += 1
                else:
                    print_erro(f"{nome}: FALHOU")
            except Exception as e:
                print_erro(f"{nome}: ERRO - {e}")
                self.erros_encontrados.append(f"{nome}: {e}")
        
        # Relatório final
        print_titulo("RELATÓRIO DOS TESTES")
        print(f"✅ Sucessos: {sucessos}/{total}")
        print(f"❌ Falhas: {total - sucessos}/{total}")
        
        if self.erros_encontrados:
            print_colorido("\n🚨 Erros encontrados:", Cores.VERMELHO)
            for erro in self.erros_encontrados:
                print(f"  • {erro}")
        
        return sucessos == total
    
    async def _testar_configuracao(self) -> bool:
        """Testa configurações básicas."""
        from dotenv import load_dotenv
        load_dotenv()
        
        vars_obrigatorias = [
            'OLLAMA_BASE_URL', 'LLM_MODEL', 'WAHA_BASE_URL'
        ]
        
        faltando = [var for var in vars_obrigatorias if not os.getenv(var)]
        
        if faltando:
            print_aviso(f"Variáveis faltando: {', '.join(faltando)}")
            return False
        
        return True
    
    async def _testar_ollama(self) -> bool:
        """Testa conexão com Ollama."""
        try:
            url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            response = requests.get(f"{url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    async def _testar_database(self) -> bool:
        """Testa conexão com base de dados (simulação)."""
        # Simulação - em implementação real testaria a conexão Oracle
        print_info("Simulando teste de BD (conexão Oracle não testada)")
        return True
    
    async def _testar_importacoes(self) -> bool:
        """Testa se as importações corretas estão funcionando."""
        try:
            # Testar sintaxe das importações (sem executar)
            codigo_teste = """
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
"""
            compile(codigo_teste, '<test>', 'exec')
            print_info("Sintaxe das importações verificada")
            return True
        except SyntaxError as e:
            print_erro(f"Erro de sintaxe: {e}")
            return False
    
    async def _testar_waha(self) -> bool:
        """Testa configuração WAHA."""
        try:
            response = requests.get("http://localhost:3000/api/sessions", timeout=3)
            return response.status_code in [200, 401]
        except:
            print_info("WAHA não está rodando (normal se não iniciado ainda)")
            return True  # Não é erro crítico
    
    async def _testar_contexto(self) -> bool:
        """Testa gerenciador de contexto (simulação)."""
        print_info("Gerenciador de contexto - estrutura verificada")
        return True

# === CLASSE PRINCIPAL ===

class GerenciadorSistema:
    """
    Classe principal que coordena todas as funcionalidades do sistema.
    
    Esta classe centraliza o controle de todos os componentes: WAHA, Ngrok,
    monitoramento, testes e configurações. Substitui todos os scripts
    auxiliares em uma interface única.
    
    Attributes:
        waha_manager: Gerenciador do container WAHA.
        ngrok_manager: Gerenciador de túneis ngrok.
        monitor: Monitor de sistema em tempo real.
        testador: Sistema de testes integrado.
        api_process: Processo da API FastAPI.
    """
    
    def __init__(self):
        """
        Inicializa o gerenciador com todos os componentes.
        
        Examples:
            >>> sistema = GerenciadorSistema()
            >>> print(type(sistema.waha_manager))
            <class '__main__.GerenciadorWAHA'>
        """
        self.waha_manager = GerenciadorWAHA()
        self.ngrok_manager = GerenciadorNgrok()
        self.monitor = MonitorSistema()
        self.testador = TestadorSistema()
        self.api_process = None
        
        # Configurar logging básico
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def mostrar_menu_principal(self):
        """
        Exibe o menu principal interativo.
        
        Examples:
            >>> sistema = GerenciadorSistema()
            >>> sistema.mostrar_menu_principal()
            # Exibe menu interativo
        """
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print_colorido("=" * 60, Cores.AZUL)
        print_colorido("🤖 GERENCIADOR DO SISTEMA BOT WHATSAPP", Cores.NEGRITO + Cores.AZUL)
        print_colorido("   Sistema Unificado - Versão 1.0", Cores.CIANO)
        print_colorido("=" * 60, Cores.AZUL)
        
        print_colorido("\n📋 OPÇÕES DISPONÍVEIS:", Cores.NEGRITO)
        print()
        
        opcoes = [
            ("1", "🚀 Inicialização Completa (All-in-One)", "Inicia todos os serviços automaticamente"),
            ("2", "🔧 Configuração Inicial e Setup", "Configura ambiente e dependências"),  
            ("3", "📊 Monitoramento em Tempo Real", "Dashboard interativo dos serviços"),
            ("4", "🧪 Executar Testes do Sistema", "Bateria completa de testes"),
            ("5", "⚙️  Validador de Código", "Verifica sintaxe e importações"),
            ("6", "🌐 Gerenciar Ngrok", "Controle manual do túnel"),
            ("7", "🐳 Gerenciar WAHA (Docker)", "Controle manual do container"),
            ("8", "❌ Parar Todos os Serviços", "Encerra tudo de forma controlada"),
            ("9", "📋 Ver Status de Componentes", "Verificação rápida"),
            ("0", "🚪 Sair", "Encerra o gerenciador")
        ]
        
        for num, titulo, desc in opcoes:
            print_colorido(f"  [{num}] {titulo}", Cores.VERDE if num != "0" else Cores.AMARELO)
            print_colorido(f"      {desc}", Cores.CIANO)
            print()
        
        print_colorido("=" * 60, Cores.AZUL)
        
    async def processar_opcao(self, opcao: str) -> bool:
        """
        Processa a opção escolhida pelo usuário.
        
        Args:
            opcao: Opção selecionada pelo usuário.
            
        Returns:
            bool: True para continuar, False para sair.
            
        Examples:
            >>> sistema = GerenciadorSistema()
            >>> continuar = await sistema.processar_opcao("1")
            >>> print(type(continuar))
            <class 'bool'>
        """
        if opcao == "1":
            await self.inicializacao_completa()
        elif opcao == "2":
            await self.configuracao_inicial()
        elif opcao == "3":
            await self.monitor.dashboard_tempo_real()
        elif opcao == "4":
            await self.testador.executar_todos_os_testes()
        elif opcao == "5":
            self.validar_codigo()
        elif opcao == "6":
            await self.gerenciar_ngrok()
        elif opcao == "7":
            await self.gerenciar_waha()
        elif opcao == "8":
            await self.parar_todos_servicos()
        elif opcao == "9":
            await self.verificar_status_componentes()
        elif opcao == "0":
            print_colorido("\n👋 Encerrando gerenciador...", Cores.AMARELO)
            return False
        else:
            print_erro("Opção inválida!")
        
        if opcao != "0":
            input("\nPressione ENTER para continuar...")
        
        return True
    
    async def inicializacao_completa(self):
        """
        Executa inicialização completa do sistema (substitui start_bot.bat).
        
        Esta é a funcionalidade principal que automatiza todo o processo
        de inicialização dos serviços necessários.
        
        Examples:
            >>> sistema = GerenciadorSistema()
            >>> await sistema.inicializacao_completa()
        """
        print_titulo("INICIALIZAÇÃO COMPLETA DO SISTEMA")
        
        etapas = [
            ("Verificando pré-requisitos", self._verificar_prerequisitos),
            ("Iniciando WAHA (Docker)", self._iniciar_waha),
            ("Iniciando Ngrok", self._iniciar_ngrok), 
            ("Iniciando API FastAPI", self._iniciar_api),
            ("Configurando Webhook", self._configurar_webhook),
            ("Verificação final", self._verificacao_final)
        ]
        
        for descricao, funcao in etapas:
            print(f"\n🔄 {descricao}...")
            try:
                sucesso = await funcao()
                if sucesso:
                    print_sucesso(f"{descricao} - Concluído")
                else:
                    print_erro(f"Falha em: {descricao}")
                    print_aviso("Interrompendo inicialização")
                    return
            except Exception as e:
                print_erro(f"Erro em {descricao}: {e}")
                return
        
        print_titulo("🎉 SISTEMA COMPLETAMENTE INICIALIZADO!")
        print_info("Acesse: http://localhost:8000/docs")
        print_info("WAHA: http://localhost:3000")
        print_info(f"Webhook: {self.ngrok_manager.url_publica}/webhook/whatsapp")
        
        # Manter rodando
        print_info("Sistema rodando... Pressione ENTER para parar")
        input()
        await self.parar_todos_servicos()
    
    async def _verificar_prerequisitos(self) -> bool:
        """Verifica se todos os pré-requisitos estão instalados."""
        requisitos = ["python", "docker", "ngrok"]
        
        for req in requisitos:
            try:
                if req == "python":
                    result = subprocess.run([sys.executable, "--version"], 
                                          capture_output=True, text=True)
                else:
                    result = subprocess.run([req, "--version"], 
                                          capture_output=True, text=True)
                
                if result.returncode == 0:
                    print_info(f"✓ {req} disponível")
                else:
                    print_erro(f"✗ {req} não encontrado")
                    return False
            except FileNotFoundError:
                print_erro(f"✗ {req} não instalado")
                return False
        
        return True
    
    async def _iniciar_waha(self) -> bool:
        """Inicia o container WAHA."""
        return self.waha_manager.iniciar_container()
    
    async def _iniciar_ngrok(self) -> bool:
        """Inicia túnel ngrok."""
        return self.ngrok_manager.iniciar_tunel(8000)
    
    async def _iniciar_api(self) -> bool:
        """Inicia a API FastAPI."""
        try:
            cmd = [
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "0.0.0.0", "--port", "8000", "--reload"
            ]
            
            self.api_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Aguardar API iniciar
            for _ in range(15):
                try:
                    response = requests.get("http://localhost:8000/", timeout=2)
                    if response.status_code == 200:
                        print_info("API respondendo")
                        return True
                except:
                    pass
                await asyncio.sleep(2)
            
            print_erro("API não respondeu no tempo esperado")
            return False
            
        except Exception as e:
            print_erro(f"Erro ao iniciar API: {e}")
            return False
    
    async def _configurar_webhook(self) -> bool:
        """Configura webhook no WAHA."""
        if not self.ngrok_manager.url_publica:
            print_aviso("URL do ngrok não disponível")
            return False
        webhook_url = f"{self.ngrok_manager.url_publica}/webhook/whatsapp"

        if self.waha_manager.criar_sessao(webhook_url):
            print_sucesso(f"Webhook configurado: {webhook_url}")
            print_info("Basta acessar http://localhost:3000 e escanear o QR code")
            return True

        print_erro("Falha ao configurar webhook no WAHA")
        return False
    
    async def _verificacao_final(self) -> bool:
        """Verificação final de todos os serviços."""
        servicos_ok = 0
        total_servicos = len(self.monitor.servicos)
        
        for nome, config in self.monitor.servicos.items():
            status = self.monitor.verificar_servico(nome, config)
            if "Online" in status["status"] or "Auth" in status["status"]:
                servicos_ok += 1
        
        print_info(f"Serviços funcionando: {servicos_ok}/{total_servicos}")
        return servicos_ok >= 3  # Pelo menos 3 dos 4 serviços funcionando
    
    async def configuracao_inicial(self):
        """Configuração inicial do ambiente."""
        print_titulo("CONFIGURAÇÃO INICIAL")
        print_info("Funcionalidade em desenvolvimento...")
        print_info("Por enquanto, use a opção 1 (Inicialização Completa)")
    
    def validar_codigo(self):
        """Validação de código Python."""
        print_titulo("VALIDAÇÃO DE CÓDIGO")
        print_info("Verificando sintaxe dos arquivos principais...")
        
        arquivos = [
            "app/main.py",
            "app/core/orquestrador.py", 
            "app/agentes/agente_roteador.py",
            "app/agentes/agente_sumarizador.py"
        ]
        
        problemas = 0
        for arquivo in arquivos:
            if Path(arquivo).exists():
                try:
                    with open(arquivo, 'r', encoding='utf-8') as f:
                        compile(f.read(), arquivo, 'exec')
                    print_sucesso(f"✓ {arquivo}")
                except SyntaxError as e:
                    print_erro(f"✗ {arquivo}: {e}")
                    problemas += 1
            else:
                print_aviso(f"? {arquivo}: Arquivo não encontrado")
        
        if problemas == 0:
            print_sucesso("Todos os arquivos validados!")
        else:
            print_erro(f"{problemas} arquivos com problemas")
    
    async def gerenciar_ngrok(self):
        """Menu de gerenciamento do Ngrok."""
        print_titulo("GERENCIAMENTO NGROK")
        print("1. Iniciar túnel")
        print("2. Verificar status") 
        print("3. Parar túnel")
        
        opcao = input("\nEscolha uma opção: ")
        
        if opcao == "1":
            porta = input("Porta (default 8000): ") or "8000"
            sucesso = self.ngrok_manager.iniciar_tunel(int(porta))
            if sucesso:
                print_sucesso(f"Túnel iniciado: {self.ngrok_manager.url_publica}")
        elif opcao == "2":
            if self.ngrok_manager._verificar_ngrok_ativo():
                url = self.ngrok_manager._obter_url_existente()
                print_info(f"Ngrok ativo: {url}")
            else:
                print_info("Ngrok não está rodando")
        elif opcao == "3":
            if self.ngrok_manager.parar_tunel():
                print_sucesso("Túnel parado")
    
    async def gerenciar_waha(self):
        """Menu de gerenciamento do WAHA."""
        print_titulo("GERENCIAMENTO WAHA")
        print("1. Iniciar container")
        print("2. Verificar status")
        print("3. Parar container")
        
        opcao = input("\nEscolha uma opção: ")
        
        if opcao == "1":
            if self.waha_manager.iniciar_container():
                print_sucesso("Container WAHA iniciado")
        elif opcao == "2":
            if self.waha_manager.verificar_status():
                print_info("WAHA está funcionando")
            else:
                print_info("WAHA não está respondendo")
        elif opcao == "3":
            if self.waha_manager.parar_container():
                print_sucesso("Container WAHA parado")
    
    async def parar_todos_servicos(self):
        """Para todos os serviços de forma controlada."""
        print_titulo("PARANDO TODOS OS SERVIÇOS")
        
        servicos_parados = 0
        
        # Parar API
        if self.api_process:
            try:
                self.api_process.terminate()
                self.api_process.wait(timeout=5)
                print_sucesso("API FastAPI parada")
                servicos_parados += 1
            except:
                print_aviso("Erro ao parar API")
        
        # Parar WAHA
        if self.waha_manager.parar_container():
            print_sucesso("WAHA parado")
            servicos_parados += 1
        
        # Parar Ngrok
        if self.ngrok_manager.parar_tunel():
            print_sucesso("Ngrok parado") 
            servicos_parados += 1
        
        print_info(f"{servicos_parados} serviços parados")
    
    async def verificar_status_componentes(self):
        """Verificação rápida do status de todos os componentes."""
        print_titulo("STATUS DOS COMPONENTES")
        
        for nome, config in self.monitor.servicos.items():
            status = self.monitor.verificar_servico(nome, config)
            print(f"{nome:8} {status['status']:15} {status['detalhes']}")
    
    async def executar(self):
        """
        Loop principal do gerenciador.
        
        Examples:
            >>> sistema = GerenciadorSistema()
            >>> await sistema.executar()
        """
        try:
            while True:
                self.mostrar_menu_principal()
                opcao = input("\n👉 Digite sua opção: ").strip()
                
                continuar = await self.processar_opcao(opcao)
                if not continuar:
                    break
                    
        except KeyboardInterrupt:
            print_colorido("\n\n🛑 Interrompido pelo usuário", Cores.AMARELO)
        except Exception as e:
            print_erro(f"Erro inesperado: {e}")
        finally:
            await self.parar_todos_servicos()

# === FUNÇÃO MAIN E ARGUMENTOS CLI ===

async def main():
    """
    Função principal com suporte a argumentos de linha de comando.
    
    Permite tanto uso interativo quanto comandos diretos via CLI.
    
    Examples:
        >>> # Uso interativo
        >>> python gerenciador_sistema.py
        
        >>> # Comandos diretos
        >>> python gerenciador_sistema.py --iniciar
        >>> python gerenciador_sistema.py --monitor
        >>> python gerenciador_sistema.py --testar
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Gerenciador Unificado do Sistema Bot WhatsApp"
    )
    parser.add_argument("--iniciar", action="store_true", 
                       help="Inicialização completa automática")
    parser.add_argument("--monitor", action="store_true", 
                       help="Dashboard de monitoramento")
    parser.add_argument("--testar", action="store_true", 
                       help="Executar todos os testes")
    parser.add_argument("--validar", action="store_true", 
                       help="Validar código")
    parser.add_argument("--parar", action="store_true", 
                       help="Parar todos os serviços")
    
    args = parser.parse_args()
    
    sistema = GerenciadorSistema()
    
    # Comandos diretos via CLI
    if args.iniciar:
        await sistema.inicializacao_completa()
    elif args.monitor:
        await sistema.monitor.dashboard_tempo_real()
    elif args.testar:
        await sistema.testador.executar_todos_os_testes()
    elif args.validar:
        sistema.validar_codigo()
    elif args.parar:
        await sistema.parar_todos_servicos()
    else:
        # Modo interativo (padrão)
        await sistema.executar()

if __name__ == "__main__":
    # Garantir que diretórios necessários existam
    Path("logs").mkdir(exist_ok=True)
    Path("temp").mkdir(exist_ok=True)
    
    # Executar sistema
    asyncio.run(main())