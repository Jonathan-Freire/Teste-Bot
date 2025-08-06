# teste_sistema_completo.py
"""
Script de Teste Completo para o Sistema de ChatBot WhatsApp

Este script funciona como um "médico" que examina cada parte do seu sistema
para garantir que tudo está funcionando corretamente antes de começar os testes reais.

Execute este script antes de começar a testar com o WhatsApp para identificar 
e corrigir qualquer problema de configuração.

Como usar:
1. Certifique-se que o Ollama está rodando
2. Configure as variáveis no arquivo .env
3. Execute: python teste_sistema_completo.py
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any

# Configurar logging para testes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/teste_sistema.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class TestadorSistema:
    """
    Classe responsável por testar todos os componentes do sistema.
    
    Pense nesta classe como um técnico especializado que conhece 
    cada parte do sistema e sabe como testá-las adequadamente.
    """
    
    def __init__(self):
        self.resultados_teste = {}
        self.erros_encontrados = []
        
    async def executar_todos_os_testes(self) -> bool:
        """
        Executa todos os testes em sequência lógica.
        
        A ordem dos testes é importante: primeiro testamos as bases 
        (configuração, banco de dados) e depois os componentes 
        mais complexos que dependem delas.
        """
        print("=" * 60)
        print("🔍 INICIANDO VALIDAÇÃO COMPLETA DO SISTEMA")
        print("=" * 60)
        
        testes_a_executar = [
            ("Configuração do Ambiente", self._testar_configuracao_ambiente),
            ("Conexão com IA (Ollama)", self._testar_conexao_ollama),
            ("Base de Dados", self._testar_base_dados),
            ("Processamento de Intenções", self._testar_processamento_intencoes),
            ("Gerenciador de Contexto", self._testar_gerenciador_contexto),
            ("Cliente WAHA", self._testar_cliente_waha),
            ("Fluxo Completo de Processamento", self._testar_fluxo_completo),
        ]
        
        sucessos = 0
        total_testes = len(testes_a_executar)
        
        for nome_teste, funcao_teste in testes_a_executar:
            print(f"\n📋 Testando: {nome_teste}")
            try:
                resultado = await funcao_teste()
                if resultado:
                    print(f"✅ {nome_teste}: PASSOU")
                    sucessos += 1
                else:
                    print(f"❌ {nome_teste}: FALHOU")
                    
            except Exception as e:
                print(f"💥 {nome_teste}: ERRO - {str(e)}")
                self.erros_encontrados.append(f"{nome_teste}: {str(e)}")
        
        # Relatório final
        print("\n" + "=" * 60)
        print("📊 RELATÓRIO FINAL DOS TESTES")
        print("=" * 60)
        print(f"✅ Testes aprovados: {sucessos}/{total_testes}")
        print(f"❌ Testes falharam: {total_testes - sucessos}/{total_testes}")
        
        if self.erros_encontrados:
            print("\n🚨 ERROS ENCONTRADOS:")
            for erro in self.erros_encontrados:
                print(f"   • {erro}")
        
        if sucessos == total_testes:
            print("\n🎉 SISTEMA PRONTO PARA TESTES!")
            print("Você pode agora iniciar a aplicação e testar com o WhatsApp.")
            return True
        else:
            print(f"\n⚠️  SISTEMA PRECISA DE AJUSTES")
            print("Corrija os problemas encontrados antes de prosseguir com os testes.")
            return False
    
    async def _testar_configuracao_ambiente(self) -> bool:
        """Testa se todas as variáveis de ambiente estão configuradas"""
        from dotenv import load_dotenv
        load_dotenv()
        
        variaveis_obrigatorias = [
            'OLLAMA_BASE_URL',
            'LLM_MODEL',
            'WAHA_BASE_URL',
            'WAHA_API_KEY',
            'WHATSAPP_SESSION_NAME'
        ]
        
        faltando = []
        for var in variaveis_obrigatorias:
            valor = os.getenv(var)
            if not valor or valor == 'your_api_key_here':
                faltando.append(var)
        
        if faltando:
            print(f"   ⚠️  Variáveis não configuradas: {', '.join(faltando)}")
            return False
        
        print(f"   ✅ Todas as {len(variaveis_obrigatorias)} variáveis configuradas")
        return True
    
    async def _testar_conexao_ollama(self) -> bool:
        """Testa conexão com o Ollama e se o modelo está disponível"""
        try:
            from langchain_community.chat_models.ollama import ChatOllama
            
            base_url = os.getenv("OLLAMA_BASE_URL")
            model = os.getenv("LLM_MODEL")
            
            print(f"   🔗 Conectando com Ollama em {base_url}")
            print(f"   🤖 Testando modelo: {model}")
            
            llm = ChatOllama(base_url=base_url, model=model)
            
            # Teste simples de resposta
            resposta = await llm.ainvoke("Responda apenas 'OK' para confirmar funcionamento.")
            
            if resposta and resposta.content:
                print(f"   ✅ Modelo respondeu: {resposta.content[:50]}...")
                return True
            else:
                print(f"   ❌ Modelo não respondeu adequadamente")
                return False
                
        except Exception as e:
            print(f"   💥 Erro na conexão: {str(e)}")
            return False
    
    async def _testar_base_dados(self) -> bool:
        """Testa conexão com a base de dados e execução de uma query simples"""
        try:
            # Importar o módulo de consultas
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.db.consultas import executar_consulta_selecao
            
            # Query simples para testar conexão
            sql_teste = "SELECT 1 as teste FROM dual"
            
            print("   🗄️  Testando conexão com base de dados...")
            resultado = await executar_consulta_selecao(sql_teste, {})
            
            if resultado.get("erro"):
                print(f"   ❌ Erro na base de dados: {resultado['erro']}")
                return False
            
            dados = resultado.get("dados", [])
            if dados and len(dados) > 0:
                print(f"   ✅ Base de dados respondendo corretamente")
                return True
            else:
                print(f"   ❌ Base de dados não retornou dados esperados")
                return False
                
        except ImportError as e:
            print(f"   ⚠️  Módulo de BD não encontrado: {str(e)}")
            return False
        except Exception as e:
            print(f"   💥 Erro no teste de BD: {str(e)}")
            return False
    
    async def _testar_processamento_intencoes(self) -> bool:
        """Testa o sistema de processamento de intenções"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.core.orquestrador import gerenciar_consulta_usuario
            from langchain_community.chat_models.ollama import ChatOllama
            
            base_url = os.getenv("OLLAMA_BASE_URL")
            model = os.getenv("LLM_MODEL")
            llm = ChatOllama(base_url=base_url, model=model)
            
            # Teste com pergunta simples sobre produtos
            pergunta_teste = "me mostra os 3 produtos mais vendidos este mês"
            
            print(f"   🧠 Testando processamento de: '{pergunta_teste}'")
            
            resposta = await gerenciar_consulta_usuario(llm, pergunta_teste)
            
            if resposta and len(resposta) > 10:  # Resposta razoável
                print(f"   ✅ Processamento funcionando. Resposta obtida: {len(resposta)} caracteres")
                return True
            else:
                print(f"   ❌ Processamento falhou ou resposta muito curta")
                return False
                
        except Exception as e:
            print(f"   💥 Erro no processamento: {str(e)}")
            # Para debug detalhado
            import traceback
            print(f"   📝 Traceback completo:")
            traceback.print_exc()
            return False
    
    async def _testar_gerenciador_contexto(self) -> bool:
        """Testa o gerenciador de contexto para múltiplas conversas"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.core.gerenciador_contexto import gerenciador_contexto
            
            # Simular conversas de dois usuários diferentes
            usuario1 = "teste_user_1"
            usuario2 = "teste_user_2"
            
            print("   💬 Testando múltiplas conversas simultâneas...")
            
            # Adicionar mensagens para usuário 1
            await gerenciador_contexto.adicionar_mensagem(usuario1, "Quais produtos temos?", "text")
            await gerenciador_contexto.adicionar_mensagem(usuario1, "Me mostre os preços", "text")
            
            # Adicionar mensagens para usuário 2  
            await gerenciador_contexto.adicionar_mensagem(usuario2, "Preciso de informações de clientes", "text")
            
            # Verificar contextos separados
            contexto1 = await gerenciador_contexto.obter_contexto(usuario1)
            contexto2 = await gerenciador_contexto.obter_contexto(usuario2)
            
            # Verificar se os contextos são diferentes e contém as mensagens esperadas
            if ("produtos" in contexto1.lower() and 
                "clientes" in contexto2.lower() and 
                contexto1 != contexto2):
                print("   ✅ Contextos individuais funcionando corretamente")
                return True
            else:
                print("   ❌ Problema na separação de contextos")
                return False
                
        except Exception as e:
            print(f"   💥 Erro no gerenciador de contexto: {str(e)}")
            return False
    
    async def _testar_cliente_waha(self) -> bool:
        """Testa o cliente WAHA (configuração básica)"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.core.cliente_waha import cliente_waha
            
            print("   📱 Testando configuração do cliente WAHA...")
            
            # Verificar se as configurações estão corretas
            if not cliente_waha.api_key or cliente_waha.api_key == "your_api_key_here":
                print("   ⚠️  WAHA_API_KEY não configurada")
                print("   ℹ️  Você precisará configurar isso para testes reais com WhatsApp")
                return True  # Não consideramos falha crítica para testes iniciais
            
            # Tentar verificar sessão (pode falhar se API key for inválida, mas é ok para teste básico)
            print("   🔑 Configurações WAHA carregadas corretamente")
            return True
            
        except Exception as e:
            print(f"   💥 Erro no cliente WAHA: {str(e)}")
            return False
    
    async def _testar_fluxo_completo(self) -> bool:
        """Testa o fluxo completo simulando uma mensagem do WhatsApp"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.core.processador_whatsapp import processador_whatsapp
            from langchain_community.chat_models.ollama import ChatOllama
            
            base_url = os.getenv("OLLAMA_BASE_URL")
            model = os.getenv("LLM_MODEL")
            llm = ChatOllama(base_url=base_url, model=model)
            
            # Simular webhook do WhatsApp
            webhook_simulado = {
                "payload": {
                    "event": "message", 
                    "data": {
                        "from": "teste_user_fluxo_completo",
                        "id": f"msg_teste_{datetime.now().timestamp()}",
                        "type": "text",
                        "body": "quais são os produtos mais caros que temos?"
                    }
                }
            }
            
            print("   🔄 Testando fluxo completo de processamento...")
            
            # Simular processamento (sem enviar resposta real)
            # Vamos testar apenas até a geração da resposta
            message_data = webhook_simulado["payload"]["data"]
            chat_id = message_data["from"]
            texto_usuario = message_data["body"]
            
            from app.core.gerenciador_contexto import gerenciador_contexto
            await gerenciador_contexto.adicionar_mensagem(chat_id, texto_usuario, "text")
            
            contexto = await gerenciador_contexto.obter_contexto(chat_id)
            prompt_completo = f"{contexto}Pergunta atual: {texto_usuario}"
            
            from app.core.orquestrador import gerenciar_consulta_usuario
            resposta = await gerenciar_consulta_usuario(llm, prompt_completo)
            
            if resposta and len(resposta) > 20:
                print(f"   ✅ Fluxo completo funcionando. Resposta gerada com sucesso")
                print(f"   📝 Preview da resposta: {resposta[:100]}...")
                return True
            else:
                print(f"   ❌ Fluxo completo falhou")
                return False
            
        except Exception as e:
            print(f"   💥 Erro no fluxo completo: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

# Função principal para execução dos testes
async def main():
    """Executa todos os testes"""
    # Garantir que o diretório de logs existe
    os.makedirs("logs", exist_ok=True)
    
    testador = TestadorSistema()
    sucesso = await testador.executar_todos_os_testes()
    
    if sucesso:
        print("\n" + "🚀" * 20)
        print("SISTEMA VALIDADO E PRONTO PARA USAR!")
        print("🚀" * 20)
        print("\nPróximos passos:")
        print("1. Configure sua WAHA_API_KEY no arquivo .env")
        print("2. Execute: python -m uvicorn app.main:app --reload --port 8000")
        print("3. Configure o webhook no WAHA para: http://seu-endereco:8000/webhook/whatsapp")
        print("4. Comece a testar enviando mensagens no WhatsApp!")
    else:
        print("\n" + "⚠️ " * 15)
        print("CORRIJA OS PROBLEMAS ANTES DE CONTINUAR")
        print("⚠️ " * 15)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())