import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

from esperanca_excecao_robos import ExcecaoRobo

logger = logging.getLogger(__name__)


def adicionar_modulo(nome_pasta_modulo: str):
    """
    Adiciona os modulos dos robôs, que ficam armazenados na pasta `C:\Robos\modulos`

    Args:
        nome_pasta_modulo (str): Nome da pasta onde os arquivos do modulo se encontram.
        
    Raises:
        ExcecaoRobo: Se nenhum diretório válido for encontrado para os módulos.
    """
    try:
        logger.debug(f"Tentando adicionar o módulo '{nome_pasta_modulo}' ao sys.path.")
        caminhos_possiveis = [
            Path("C:/Robos/modulos"),
            Path("P:/Informatica/Projetos/Projetos-Ajustados/02-Python/modulos")
        ]

        # Encontra o primeiro caminho base que existe.
        diretorio_base = next((caminho for caminho in caminhos_possiveis if caminho.is_dir()), None)

        if diretorio_base is None:
            raise ExcecaoRobo("Nenhum diretório base válido (C:/Robos/modulos ou P:/Informatica/Projetos/Projetos-Ajustados/02-Python/modulos) foi encontrado.", "DirectoryNotFound")

        caminho_modulo = diretorio_base / nome_pasta_modulo
        if not caminho_modulo.is_dir():
             raise ExcecaoRobo(f"A pasta do módulo '{caminho_modulo}' não existe.", "DirectoryNotFound")

        caminho_str = str(caminho_modulo.resolve())

        if caminho_str not in sys.path:
            sys.path.insert(1, caminho_str)
            logger.info(f"Módulo '{nome_pasta_modulo}' adicionado ao sys.path: {caminho_str}")
        else:
            logger.debug(f"Módulo '{nome_pasta_modulo}' já estava no sys.path.")
            
    except ExcecaoRobo:
        raise
    except Exception as e:
        raise ExcecaoRobo(
            f"Erro inesperado ao adicionar módulo {nome_pasta_modulo}: {e}",
            type(e).__name__
        ) from e
        
def configurar_logging(nome_arquivo_log: str, diretorio_log: Path = Path("logs")):
    """
    Configura o logging para a aplicação e limpa logs antigos.

    Cria um diretório de logs, exclui arquivos com mais de 3 meses, e
    configura dois handlers:
    1. FileHandler: Salva os logs em um arquivo com nome dinâmico.
    2. StreamHandler: Exibe os logs no console.

    Args:
        nome_arquivo_log (str): O nome do arquivo de log (sem a extensão).
        diretorio_log (Path, optional): O diretório onde os logs serão salvos. 
                                        Padrão é 'logs'.
    """
    # 1. Limpa os logs antigos antes de qualquer outra coisa
    _limpar_logs_antigos(diretorio_log)

    # 2. Cria o diretório de logs se ele não existir
    diretorio_log.mkdir(parents=True, exist_ok=True)
    
    # Define o caminho completo para o arquivo de log
    caminho_arquivo_log = diretorio_log / f"{nome_arquivo_log}.log"

    # Define o formato das mensagens de log com data e hora em pt-br
    formato_log = "%(asctime)s - %(levelname)s - %(name)s - [%(funcName)s] - %(message)s"
    formatador = logging.Formatter(formato_log, datefmt="%d-%m-%Y %H:%M:%S")

    # Pega o logger raiz. Todos os outros loggers criados com
    # logging.getLogger(__name__) herdarão esta configuração.
    logger_raiz = logging.getLogger()
    logger_raiz.setLevel(logging.DEBUG) # Define o nível mínimo de log a ser capturado

    # Limpa quaisquer handlers existentes para evitar logs duplicados
    if logger_raiz.hasHandlers():
        logger_raiz.handlers.clear()

    # --- Handler para salvar em arquivo ---
    file_handler = logging.FileHandler(caminho_arquivo_log, encoding='utf-8')
    file_handler.setFormatter(formatador)
    logger_raiz.addHandler(file_handler)

    # --- Handler para exibir no console ---
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatador)
    logger_raiz.addHandler(stream_handler)

    logging.info(f"Logging configurado. Os logs serão salvos em: {caminho_arquivo_log}")
    
def _limpar_logs_antigos(diretorio_log: Path, meses: int = 3):
    """
    Verifica o diretório de logs e exclui arquivos mais antigos que o limite.

    Args:
        diretorio_log (Path): O diretório onde os logs estão salvos.
        meses (int): A idade máxima em meses que um arquivo de log pode ter.
    """
    if not diretorio_log.exists():
        return # Se o diretório não existe, não há nada a fazer.

    # Aproximação de 3 meses = 90 dias
    limite_dias = meses * 30
    agora = datetime.now()
    limite_tempo = agora - timedelta(days=limite_dias)

    logging.info(f"Verificando e limpando logs com mais de {meses} meses em '{diretorio_log}'...")

    for arquivo_log in diretorio_log.glob("*.log"):
        try:
            # Pega a data de modificação do arquivo
            data_modificacao = datetime.fromtimestamp(arquivo_log.stat().st_mtime)
            
            if data_modificacao < limite_tempo:
                logging.warning(f"Excluindo arquivo de log antigo: {arquivo_log.name} (modificado em {data_modificacao.strftime('%d-%m-%Y')})")
                arquivo_log.unlink() # Exclui o arquivo
        except OSError as e:
            logging.error(f"Não foi possível excluir o arquivo de log '{arquivo_log.name}': {e}")
        except Exception as e:
            logging.error(f"Ocorreu um erro inesperado ao processar o arquivo '{arquivo_log.name}': {e}")    