import logging
from typing import Dict, Any

# CORREÇÃO: Importação atualizada para langchain-ollama
from langchain_ollama import OllamaLLM
from app.core.orquestrador import gerenciar_consulta_usuario
from app.core.gerenciador_contexto import gerenciador_contexto
from app.core.cliente_waha import cliente_waha

logger = logging.getLogger(__name__)

class ProcessadorWhatsApp:
    """
    Classe responsável por processar mensagens recebidas do WhatsApp.
    
    Esta classe atua como uma ponte entre o webhook do WhatsApp (via WAHA)
    e o sistema de processamento de consultas do bot, garantindo que:
    
    1. Mensagens sejam processadas apenas uma vez (evita duplicatas)
    2. Contexto da conversa seja mantido por usuário
    3. Diferentes tipos de mídia sejam tratados adequadamente
    4. Respostas sejam enviadas de volta pelo WhatsApp
    
    Attributes:
        mensagens_processando: Set com IDs de mensagens sendo processadas para evitar duplicatas.
    """
    
    def __init__(self):
        """
        Inicializa o processador com controle de mensagens duplicadas.
        
        Examples:
            >>> processador = ProcessadorWhatsApp()
            >>> len(processador.mensagens_processando)
            0
        """
        self.mensagens_processando = set()
    
    async def processar_mensagem(self, llm: OllamaLLM, webhook_data: Dict[str, Any]) -> bool:
        """
        Processa mensagem recebida do WhatsApp via webhook.
        
        Args:
            llm: Instância do modelo OllamaLLM para processamento de linguagem natural.
            webhook_data: Dados recebidos do webhook do WAHA contendo a mensagem.
            
        Returns:
            bool: True se a mensagem foi processada e respondida com sucesso.
            
        Examples:
            >>> llm = OllamaLLM(model="llama3.1", base_url="http://localhost:11434")
            >>> webhook_data = {
            ...     "payload": {
            ...         "event": "message",
            ...         "data": {
            ...             "from": "5511999999999@c.us",
            ...             "id": "msg123",
            ...             "type": "text",
            ...             "body": "Olá, quais produtos temos?"
            ...         }
            ...     }
            ... }
            >>> resultado = await processador.processar_mensagem(llm, webhook_data)
            >>> print(resultado)
            True
        """
        try:
            # Extrair dados da mensagem
            if "payload" not in webhook_data:
                logger.warning("Webhook sem payload")
                return False
            
            payload = webhook_data["payload"]
            
            # Verificar se é uma mensagem
            if payload.get("event") != "message":
                logger.debug(f"Evento ignorado: {payload.get('event')}")
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
                
                # Enviar indicador de "digitando..."
                await cliente_waha.enviar_typing(chat_id, 3)
                
                # Adicionar ao contexto
                await gerenciador_contexto.adicionar_mensagem(
                    usuario_id=chat_id,
                    texto=texto_usuario,
                    tipo=message_type
                )
                
                # Obter contexto da conversa
                contexto = await gerenciador_contexto.obter_contexto(chat_id)
                
                # Construir prompt com contexto
                prompt_completo = f"{contexto}{texto_usuario}" if contexto else texto_usuario
                
                # Processar com a IA
                logger.info(f"Processando mensagem de {chat_id}: {texto_usuario[:50]}...")
                resposta = await gerenciar_consulta_usuario(llm, prompt_completo)
                
                # Adicionar resposta ao contexto
                await gerenciador_contexto.adicionar_resposta_bot(chat_id, resposta)
                
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
        """
        Extrai texto de diferentes tipos de mensagem do WhatsApp.
        
        Args:
            message_data: Dados da mensagem recebida do webhook.
            
        Returns:
            str: Texto extraído ou descrição da mensagem para tipos não textuais.
            
        Examples:
            >>> message_data = {"type": "text", "body": "Olá!"}
            >>> texto = await processador._extrair_texto_mensagem(message_data)
            >>> print(texto)
            "Olá!"
            
            >>> message_data = {"type": "image", "caption": "Veja esta foto"}
            >>> texto = await processador._extrair_texto_mensagem(message_data)
            >>> print(texto)
            "[Imagem recebida] Veja esta foto"
        """
        message_type = message_data.get("type", "text")
        
        if message_type == "text":
            return message_data.get("body", "")
        
        elif message_type in ["ptt", "audio"]:
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
        
        elif message_type == "video":
            # Mensagem com vídeo
            caption = message_data.get("caption", "")
            return f"[Vídeo recebido] {caption}" if caption else "[Vídeo recebido]"
        
        elif message_type == "document":
            # Mensagem com documento
            filename = message_data.get("filename", "documento")
            return f"[Documento recebido: {filename}]"
        
        elif message_type == "location":
            # Mensagem com localização
            return "[Localização recebida]"
        
        elif message_type == "contact":
            # Mensagem com contato
            return "[Contato recebido]"
        
        else:
            return f"[Mensagem do tipo {message_type} recebida]"

# Instância global do processador
processador_whatsapp = ProcessadorWhatsApp()