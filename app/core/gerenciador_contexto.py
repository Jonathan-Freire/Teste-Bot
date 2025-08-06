# app/core/gerenciador_contexto.py
"""
Gerenciador de Contexto para Conversas Individuais no WhatsApp

Este módulo funciona como a "memória" do chatbot, mantendo o histórico 
de cada conversa separadamente. Imagine que é como ter uma gaveta diferente 
para cada pessoa que está conversando com o bot.

Principais responsabilidades:
1. Manter histórico individual de cada usuário
2. Limpar sessões antigas automaticamente 
3. Fornecer contexto relevante para a IA
4. Gerenciar múltiplas conversas simultâneas
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class MensagemContexto:
    """Representa uma mensagem individual no contexto da conversa"""
    texto: str
    timestamp: float
    tipo: str = "text"  # text, audio, image, etc
    resposta_bot: Optional[str] = None  # resposta que o bot deu para esta mensagem

class SessaoUsuario:
    """
    Representa uma sessão de conversa com um usuário específico.
    
    Pense nesta classe como um "caderno de conversa" para cada pessoa.
    Cada usuário tem seu próprio caderno onde guardamos:
    - As mensagens que ele enviou
    - Quando foram enviadas
    - As respostas que demos
    """
    
    def __init__(self, usuario_id: str, timeout_minutos: int = 30, max_mensagens: int = 10):
        self.usuario_id = usuario_id
        self.mensagens: List[MensagemContexto] = []
        self.ultima_atividade = datetime.now()
        self.timeout_minutos = timeout_minutos
        self.max_mensagens = max_mensagens
        
        # Estatísticas úteis para debug
        self.total_mensagens_recebidas = 0
        self.sessao_iniciada = datetime.now()
    
    def adicionar_mensagem(self, texto: str, tipo: str = "text") -> None:
        """
        Adiciona uma nova mensagem à sessão.
        
        É como escrever uma nova linha no caderno de conversa.
        """
        nova_mensagem = MensagemContexto(
            texto=texto,
            timestamp=datetime.now().timestamp(),
            tipo=tipo
        )
        
        self.mensagens.append(nova_mensagem)
        self.ultima_atividade = datetime.now()
        self.total_mensagens_recebidas += 1
        
        # Manter apenas as últimas N mensagens para não sobrecarregar a memória
        if len(self.mensagens) > self.max_mensagens:
            # Remove mensagens mais antigas, mas mantém pelo menos 3 para contexto básico
            mensagens_para_remover = len(self.mensagens) - max(3, self.max_mensagens)
            self.mensagens = self.mensagens[mensagens_para_remover:]
            
        logger.debug(f"Mensagem adicionada para {self.usuario_id}. Total: {len(self.mensagens)}")
    
    def adicionar_resposta_bot(self, resposta: str) -> None:
        """
        Adiciona a resposta do bot à última mensagem.
        
        Isso nos ajuda a entender o fluxo da conversa quando 
        precisarmos gerar respostas futuras.
        """
        if self.mensagens:
            self.mensagens[-1].resposta_bot = resposta
            logger.debug(f"Resposta do bot adicionada para {self.usuario_id}")
    
    def esta_expirada(self) -> bool:
        """
        Verifica se a sessão está expirada (inativa por muito tempo).
        
        É como verificar se alguém parou de conversar há muito tempo.
        """
        tempo_inativo = datetime.now() - self.ultima_atividade
        return tempo_inativo > timedelta(minutes=self.timeout_minutos)
    
    def obter_contexto_formatado(self) -> str:
        """
        Retorna o contexto formatado para enviar para a IA.
        
        Transforma nosso "caderno de conversa" em um formato 
        que a IA consegue entender e usar para gerar respostas melhores.
        """
        if not self.mensagens:
            return ""
        
        linhas_contexto = []
        
        # Incluir apenas as últimas 5 mensagens para não sobrecarregar a IA
        mensagens_recentes = self.mensagens[-5:]
        
        for msg in mensagens_recentes[:-1]:  # Excluir a mensagem atual (última)
            tempo_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
            
            # Formato: [Hora] Usuário: mensagem
            linhas_contexto.append(f"[{tempo_str}] Usuário: {msg.texto}")
            
            # Se temos a resposta do bot, incluir também
            if msg.resposta_bot:
                linhas_contexto.append(f"[{tempo_str}] Bot: {msg.resposta_bot[:100]}...")  # Truncar respostas longas
        
        if linhas_contexto:
            return f"Histórico da conversa:\n" + "\n".join(linhas_contexto) + "\n\nPergunta atual: "
        
        return ""
    
    def obter_estatisticas(self) -> Dict:
        """Retorna estatísticas da sessão para debug"""
        tempo_ativo = datetime.now() - self.sessao_iniciada
        return {
            "usuario_id": self.usuario_id,
            "total_mensagens": len(self.mensagens),
            "mensagens_recebidas": self.total_mensagens_recebidas,
            "sessao_iniciada": self.sessao_iniciada.strftime("%H:%M:%S"),
            "ultima_atividade": self.ultima_atividade.strftime("%H:%M:%S"),
            "tempo_ativo_minutos": int(tempo_ativo.total_seconds() / 60),
            "expira_em_minutos": max(0, self.timeout_minutos - int((datetime.now() - self.ultima_atividade).total_seconds() / 60))
        }

class GerenciadorContexto:
    """
    Gerenciador principal que coordena todas as sessões de usuários.
    
    Pense neste como o "bibliotecário" que cuida de todos os cadernos 
    de conversa. Ele sabe onde está cada caderno e cuida para que 
    cadernos muito antigos sejam removidos para liberar espaço.
    """
    
    def __init__(self, timeout_minutos: int = 30, max_mensagens: int = 10):
        self.sessoes: Dict[str, SessaoUsuario] = {}
        self.timeout_minutos = timeout_minutos
        self.max_mensagens = max_mensagens
        self._task_limpeza = None
        
        # Estatísticas globais
        self.total_sessoes_criadas = 0
        self.total_sessoes_limpas = 0
        
        # Iniciar task de limpeza automática
        self._iniciar_limpeza_automatica()
        
        logger.info(f"Gerenciador de contexto inicializado. Timeout: {timeout_minutos}min, Max mensagens: {max_mensagens}")
    
    def _iniciar_limpeza_automatica(self):
        """
        Inicia uma tarefa em segundo plano para limpar sessões expiradas.
        
        É como ter um funcionário que passa de tempos em tempos 
        verificando quais cadernos não são mais usados e os remove.
        """
        async def limpeza_periodica():
            while True:
                try:
                    await self._limpar_sessoes_expiradas()
                    # Executar limpeza a cada 5 minutos
                    await asyncio.sleep(300)
                except Exception as e:
                    logger.error(f"Erro na limpeza automática: {e}")
                    await asyncio.sleep(60)  # Retry em 1 minuto se houver erro
        
        self._task_limpeza = asyncio.create_task(limpeza_periodica())
    
    async def adicionar_mensagem(self, usuario_id: str, texto: str, tipo: str = "text") -> None:
        """
        Adiciona uma mensagem para um usuário específico.
        
        Se é a primeira vez que este usuário está conversando, 
        criamos um novo caderno para ele.
        """
        # Criar sessão se não existir
        if usuario_id not in self.sessoes:
            self.sessoes[usuario_id] = SessaoUsuario(
                usuario_id=usuario_id,
                timeout_minutos=self.timeout_minutos,
                max_mensagens=self.max_mensagens
            )
            self.total_sessoes_criadas += 1
            logger.info(f"Nova sessão criada para usuário: {usuario_id}")
        
        # Adicionar mensagem à sessão
        self.sessoes[usuario_id].adicionar_mensagem(texto, tipo)
        
        logger.debug(f"Mensagem adicionada para {usuario_id}: {texto[:50]}...")
    
    async def adicionar_resposta_bot(self, usuario_id: str, resposta: str) -> None:
        """Adiciona a resposta do bot à última mensagem do usuário"""
        if usuario_id in self.sessoes:
            self.sessoes[usuario_id].adicionar_resposta_bot(resposta)
    
    async def obter_contexto(self, usuario_id: str) -> str:
        """
        Obtém o contexto da conversa para um usuário.
        
        Se o usuário não tem histórico, retorna string vazia.
        """
        if usuario_id not in self.sessoes:
            return ""
        
        return self.sessoes[usuario_id].obter_contexto_formatado()
    
    async def _limpar_sessoes_expiradas(self) -> int:
        """
        Remove sessões que não são mais usadas.
        
        Retorna o número de sessões removidas.
        """
        sessoes_removidas = 0
        usuarios_expirados = []
        
        # Identificar sessões expiradas
        for usuario_id, sessao in self.sessoes.items():
            if sessao.esta_expirada():
                usuarios_expirados.append(usuario_id)
        
        # Remover sessões expiradas
        for usuario_id in usuarios_expirados:
            del self.sessoes[usuario_id]
            sessoes_removidas += 1
            self.total_sessoes_limpas += 1
            logger.info(f"Sessão expirada removida: {usuario_id}")
        
        if sessoes_removidas > 0:
            logger.info(f"Limpeza automática: {sessoes_removidas} sessões removidas")
        
        return sessoes_removidas
    
    async def encerrar_sessao(self, usuario_id: str) -> bool:
        """Encerra manualmente uma sessão específica"""
        if usuario_id in self.sessoes:
            del self.sessoes[usuario_id]
            logger.info(f"Sessão encerrada manualmente: {usuario_id}")
            return True
        return False
    
    def obter_estatisticas_globais(self) -> Dict:
        """Retorna estatísticas globais do gerenciador"""
        return {
            "sessoes_ativas": len(self.sessoes),
            "total_sessoes_criadas": self.total_sessoes_criadas,
            "total_sessoes_limpas": self.total_sessoes_limpas,
            "timeout_minutos": self.timeout_minutos,
            "max_mensagens_por_sessao": self.max_mensagens
        }
    
    def obter_estatisticas_sessao(self, usuario_id: str) -> Optional[Dict]:
        """Retorna estatísticas de uma sessão específica"""
        if usuario_id in self.sessoes:
            return self.sessoes[usuario_id].obter_estatisticas()
        return None
    
    def listar_sessoes_ativas(self) -> List[str]:
        """Retorna lista de IDs de usuários com sessões ativas"""
        return list(self.sessoes.keys())
    
    async def encerrar(self):
        """Encerra o gerenciador e para a limpeza automática"""
        if self._task_limpeza and not self._task_limpeza.done():
            self._task_limpeza.cancel()
            logger.info("Task de limpeza automática encerrada")

# Instância global do gerenciador - é aqui que tudo acontece
# Pense nisto como o "balcão de atendimento" principal do sistema
gerenciador_contexto = GerenciadorContexto(timeout_minutos=30, max_mensagens=10)