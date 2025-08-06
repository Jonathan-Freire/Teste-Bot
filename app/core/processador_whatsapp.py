
import logging
from typing import Dict, Any
from app.core.orquestrador import gerenciar_consulta_usuario
from app.core.gerenciador_contexto import gerenciador_contexto
from app.core.cliente_waha import cliente_waha
from langchain_community.chat_models.ollama import ChatOllama

logger = logging.getLogger(__name__)

class ProcessadorWhatsApp:
    def __init__(self):
        self.mensagens_processando = set()
    
    async def processar_mensagem(self, llm: ChatOllama, webhook_data: Dict[str, Any]) -> bool:
        """Processa mensagem recebida do WhatsApp via webhook"""
        try:
            # Extrair dados da mensagem
            if "payload" not in webhook_data:
                logger.warning("Webhook sem payload")
                return False
            
            payload = webhook_data["payload"]
            
            # Verificar se é uma mensagem
            if payload.get("event") != "message":
                return False
            
            message_data = payload.get("data", {})
            
            # Extrair informações básicas
            chat_id = message_data.get("from")
            message_id = message_data.get("id")
            message_type = message_data.get("type", "text")
            
            if not chat_id or not message_id:
                logger.warning("Dados incompletos na mensagem")
                return False
            
            # Evitar processamento duplicado
            if message_id in self.mensagens_processando:
                logger.info(f"Mensagem {message_id} já está sendo processada")
                return False
            
            self.mensagens_processando.add(message_id)
            
            try:
                # Processar baseado no tipo de mensagem
                texto_usuario = await self._extrair_texto_mensagem(message_data)
                
                if not texto_usuario:
                    logger.warning(f"Não foi possível extrair texto da mensagem tipo {message_type}")
                    return False
                
                # Adicionar ao contexto
                await gerenciador_contexto.adicionar_mensagem(
                    usuario_id=chat_id,
                    texto=texto_usuario,
                    tipo=message_type
                )
                
                # Obter contexto da conversa
                contexto = await gerenciador_contexto.obter_contexto(chat_id)
                
                # Construir prompt com contexto
                prompt_completo = f"{contexto}Pergunta atual: {texto_usuario}"
                
                # Processar com a IA
                logger.info(f"Processando mensagem de {chat_id}: {texto_usuario[:50]}...")
                resposta = await gerenciar_consulta_usuario(llm, prompt_completo)
                
                # Enviar resposta
                sucesso = await cliente_waha.enviar_mensagem(chat_id, resposta)
                
                if sucesso:
                    logger.info(f"Resposta enviada com sucesso para {chat_id}")
                else:
                    logger.error(f"Falha ao enviar resposta para {chat_id}")
                
                return sucesso
                
            finally:
                # Remover da lista de processamento
                self.mensagens_processando.discard(message_id)
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do WhatsApp: {e}", exc_info=True)
            return False
    
    async def _extrair_texto_mensagem(self, message_data: Dict[str, Any]) -> str:
        """Extrai texto de diferentes tipos de mensagem"""
        message_type = message_data.get("type", "text")
        
        if message_type == "text":
            return message_data.get("body", "")
        
        elif message_type == "ptt" or message_type == "audio":
            # Mensagem de voz
            logger.info("Processando mensagem de voz")
            
            # Baixar áudio
            filepath = await cliente_waha.baixar_audio(message_data)
            if not filepath:
                return "[Erro ao baixar áudio]"
            
            try:
                # Transcrever áudio
                transcricao = await cliente_waha.transcrever_audio(filepath)
                return transcricao or "[Erro na transcrição do áudio]"
            
            finally:
                # Limpar arquivo temporário
                await cliente_waha.limpar_arquivo_temp(filepath)
        
        elif message_type == "image":
            # Mensagem com imagem
            caption = message_data.get("caption", "")
            return f"[Imagem recebida] {caption}" if caption else "[Imagem recebida]"
        
        else:
            return f"[Mensagem do tipo {message_type} recebida]"

# Instância global do processador
processador_whatsapp = ProcessadorWhatsApp()
