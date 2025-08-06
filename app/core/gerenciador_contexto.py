
import asyncio
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class MensagemContexto:
    usuario_id: str
    texto: str
    timestamp: float
    tipo: str = "text"  # text, audio, image

@dataclass 
class SessaoConversa:
    usuario_id: str
    mensagens: List[MensagemContexto] = field(default_factory=list)
    ultimo_acesso: float = field(default_factory=time.time)
    ativa: bool = True

class GerenciadorContexto:
    def __init__(self, timeout_minutos: int = 30, max_mensagens: int = 10):
        self.sessoes: Dict[str, SessaoConversa] = {}
        self.timeout_segundos = timeout_minutos * 60
        self.max_mensagens = max_mensagens
        self._task_limpeza = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Inicia task de limpeza automática"""
        if self._task_limpeza is None:
            self._task_limpeza = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Loop de limpeza de sessões inativas"""
        while True:
            try:
                await asyncio.sleep(300)  # Verifica a cada 5 minutos
                await self._limpar_sessoes_inativas()
            except Exception as e:
                logger.error(f"Erro na limpeza de sessões: {e}")
    
    async def _limpar_sessoes_inativas(self):
        """Remove sessões que ultrapassaram o timeout"""
        agora = time.time()
        sessoes_para_remover = []
        
        for usuario_id, sessao in self.sessoes.items():
            if agora - sessao.ultimo_acesso > self.timeout_segundos:
                sessoes_para_remover.append(usuario_id)
                logger.info(f"Encerrando sessão inativa para usuário: {usuario_id}")
        
        for usuario_id in sessoes_para_remover:
            del self.sessoes[usuario_id]
    
    async def adicionar_mensagem(self, usuario_id: str, texto: str, tipo: str = "text"):
        """Adiciona mensagem ao contexto do usuário"""
        agora = time.time()
        
        # Criar ou atualizar sessão
        if usuario_id not in self.sessoes:
            self.sessoes[usuario_id] = SessaoConversa(usuario_id=usuario_id)
            logger.info(f"Nova sessão iniciada para usuário: {usuario_id}")
        
        sessao = self.sessoes[usuario_id]
        sessao.ultimo_acesso = agora
        sessao.ativa = True
        
        # Adicionar mensagem
        mensagem = MensagemContexto(
            usuario_id=usuario_id,
            texto=texto,
            timestamp=agora,
            tipo=tipo
        )
        
        sessao.mensagens.append(mensagem)
        
        # Manter apenas as últimas N mensagens
        if len(sessao.mensagens) > self.max_mensagens:
            sessao.mensagens = sessao.mensagens[-self.max_mensagens:]
        
        logger.debug(f"Mensagem adicionada para {usuario_id}. Total: {len(sessao.mensagens)}")
    
    async def obter_contexto(self, usuario_id: str) -> str:
        """Retorna o contexto das mensagens anteriores do usuário"""
        if usuario_id not in self.sessoes:
            return ""
        
        sessao = self.sessoes[usuario_id]
        if not sessao.mensagens:
            return ""
        
        # Formatar contexto das mensagens anteriores (exceto a última)
        contexto_mensagens = []
        for msg in sessao.mensagens[:-1]:  # Não incluir a mensagem atual
            tempo_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
            contexto_mensagens.append(f"[{tempo_str}] {msg.texto}")
        
        if contexto_mensagens:
            return f"Contexto da conversa anterior:\n" + "\n".join(contexto_mensagens[-5:]) + "\n\n"
        
        return ""
    
    async def encerrar_sessao(self, usuario_id: str):
        """Encerra manualmente uma sessão"""
        if usuario_id in self.sessoes:
            del self.sessoes[usuario_id]
            logger.info(f"Sessão encerrada manualmente para usuário: {usuario_id}")

# Instância global do gerenciador
gerenciador_contexto = GerenciadorContexto(timeout_minutos=30, max_mensagens=10)
