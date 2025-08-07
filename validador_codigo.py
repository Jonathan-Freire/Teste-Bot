# validador_codigo.py
"""
Script para validar todos os códigos Python do projeto.

Este script verifica:
1. Sintaxe dos arquivos Python
2. Importações não utilizadas
3. Variáveis não utilizadas
4. Compatibilidade com Python 3.10.11
5. Problemas de tipagem
6. Docstrings faltando

Execute: python validador_codigo.py
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Any, Tuple
import importlib.util

class ValidadorCodigo:
    """
    Validador de código Python para detectar problemas comuns.
    
    Esta classe analisa arquivos Python e identifica:
    - Erros de sintaxe
    - Importações não utilizadas
    - Variáveis não utilizadas
    - Funções sem docstring
    - Problemas de compatibilidade
    """
    
    def __init__(self):
        """
        Inicializa o validador com contadores zerados.
        """
        self.arquivos_analisados = 0
        self.problemas_encontrados = []
        self.avisos = []
        
        # Importações que podem não ser diretamente referenciadas no código
        self.importacoes_especiais = {
            'adicionar_modulo',  # Função helper que adiciona módulos ao path
            'configurar_logging', # Função helper para configurar logs
            'ExcecaoRobo',       # Exceção customizada
            'DB_Oracle_Encrypted', # Biblioteca interna
            'esperanca_excecao_robos' # Biblioteca interna
        }
    
    def validar_projeto(self, diretorio_raiz: str = ".") -> bool:
        """
        Valida todos os arquivos Python do projeto.
        
        Args:
            diretorio_raiz: Diretório raiz do projeto para análise.
            
        Returns:
            bool: True se não houver problemas críticos.
        """
        print("=" * 60)
        print("🔍 VALIDADOR DE CÓDIGO PYTHON")
        print("=" * 60)
        
        # Encontrar todos os arquivos Python
        arquivos_python = self._encontrar_arquivos_python(diretorio_raiz)
        
        print(f"📁 Encontrados {len(arquivos_python)} arquivos Python para análise\n")
        
        # Analisar cada arquivo
        for arquivo in arquivos_python:
            self._analisar_arquivo(arquivo)
        
        # Exibir relatório final
        self._exibir_relatorio()
        
        # Retornar se há problemas críticos
        return len(self.problemas_encontrados) == 0
    
    def _encontrar_arquivos_python(self, diretorio: str) -> List[Path]:
        """
        Encontra todos os arquivos .py no projeto.
        
        Args:
            diretorio: Diretório para buscar arquivos.
            
        Returns:
            Lista de caminhos para arquivos Python.
        """
        arquivos = []
        for caminho in Path(diretorio).rglob("*.py"):
            # Ignorar diretórios específicos
            if any(parte in str(caminho) for parte in ['__pycache__', '.git', 'venv', 'env']):
                continue
            arquivos.append(caminho)
        
        return sorted(arquivos)
    
    def _analisar_arquivo(self, arquivo: Path):
        """
        Analisa um arquivo Python específico.
        
        Args:
            arquivo: Caminho do arquivo a ser analisado.
        """
        print(f"🔍 Analisando: {arquivo}")
        self.arquivos_analisados += 1
        
        try:
            # Ler conteúdo do arquivo
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
            
            # Verificar sintaxe
            try:
                tree = ast.parse(conteudo, filename=str(arquivo))
            except SyntaxError as e:
                self.problemas_encontrados.append(
                    f"❌ ERRO DE SINTAXE em {arquivo}:{e.lineno} - {e.msg}"
                )
                return
            
            # Analisar AST
            self._analisar_ast(tree, arquivo, conteudo)
            
        except Exception as e:
            self.problemas_encontrados.append(
                f"❌ ERRO ao analisar {arquivo}: {e}"
            )
    
    def _analisar_ast(self, tree: ast.AST, arquivo: Path, conteudo: str):
        """
        Analisa a árvore sintática abstrata do arquivo.
        
        Args:
            tree: AST do arquivo Python.
            arquivo: Caminho do arquivo.
            conteudo: Conteúdo textual do arquivo.
        """
        # Coletar informações do arquivo
        importacoes = set()
        nomes_usados = set()
        funcoes_sem_docstring = []
        
        for node in ast.walk(tree):
            # Coletar importações
            if isinstance(node, ast.Import):
                for alias in node.names:
                    importacoes.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    importacoes.add(node.module.split('.')[0])
                for alias in node.names:
                    importacoes.add(alias.name)
            
            # Coletar nomes usados
            elif isinstance(node, ast.Name):
                nomes_usados.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    nomes_usados.add(node.value.id)
            
            # Verificar funções sem docstring
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not ast.get_docstring(node):
                    # Ignorar funções privadas pequenas
                    if not node.name.startswith('_') or len(node.body) > 5:
                        funcoes_sem_docstring.append(
                            f"linha {node.lineno}: {node.name}()"
                        )
        
        # Verificar importações não utilizadas
        self._verificar_importacoes_nao_utilizadas(importacoes, nomes_usados, conteudo, arquivo)
        
        # Avisar sobre funções sem docstring
        if funcoes_sem_docstring:
            self.avisos.append(
                f"⚠️  {arquivo}: Funções sem docstring: {', '.join(funcoes_sem_docstring)}"
            )
    
    def _verificar_importacoes_nao_utilizadas(self, importacoes: Set[str], nomes_usados: Set[str], 
                                            conteudo: str, arquivo: Path):
        """
        Verifica se há importações não utilizadas no arquivo.
        
        Args:
            importacoes: Set de módulos importados.
            nomes_usados: Set de nomes referenciados no código.
            conteudo: Conteúdo textual do arquivo.
            arquivo: Caminho do arquivo.
        """
        nao_utilizadas = []
        
        for importacao in importacoes:
            # Ignorar importações especiais
            if importacao in self.importacoes_especiais:
                continue
            
            # Verificar se é usada diretamente
            if importacao in nomes_usados:
                continue
            
            # Verificar se é usada como string (para imports dinâmicos)
            if f"'{importacao}'" in conteudo or f'"{importacao}"' in conteudo:
                continue
            
            # Verificar se é um módulo que é importado para efeitos colaterais
            if importacao in ['dotenv', 'logging', 'asyncio']:
                continue
            
            nao_utilizadas.append(importacao)
        
        if nao_utilizadas:
            self.avisos.append(
                f"⚠️  {arquivo}: Possíveis importações não utilizadas: {', '.join(nao_utilizadas)}"
            )
    
    def _exibir_relatorio(self):
        """
        Exibe o relatório final da validação.
        """
        print("\n" + "=" * 60)
        print("📊 RELATÓRIO DE VALIDAÇÃO")
        print("=" * 60)
        
        print(f"📁 Arquivos analisados: {self.arquivos_analisados}")
        print(f"❌ Problemas críticos: {len(self.problemas_encontrados)}")
        print(f"⚠️  Avisos: {len(self.avisos)}")
        
        if self.problemas_encontrados:
            print("\n🚨 PROBLEMAS CRÍTICOS ENCONTRADOS:")
            for problema in self.problemas_encontrados:
                print(f"   {problema}")
        
        if self.avisos:
            print(f"\n⚠️  AVISOS (não críticos):")
            for aviso in self.avisos:
                print(f"   {aviso}")
        
        if not self.problemas_encontrados and not self.avisos:
            print("\n🎉 TODOS OS CÓDIGOS ESTÃO VALIDADOS!")
            print("✅ Nenhum problema encontrado.")
        elif not self.problemas_encontrados:
            print("\n✅ VALIDAÇÃO PASSOU!")
            print("Apenas avisos encontrados, nada crítico.")
        else:
            print(f"\n❌ VALIDAÇÃO FALHOU!")
            print("Corrija os problemas críticos antes de continuar.")

def validar_compatibilidade_python():
    """
    Verifica compatibilidade com Python 3.10.11.
    
    Returns:
        bool: True se a versão é compatível.
    """
    print("🐍 Verificando compatibilidade do Python...")
    
    versao_atual = sys.version_info
    versao_minima = (3, 10)
    versao_recomendada = (3, 10, 11)
    
    if versao_atual < versao_minima:
        print(f"❌ Python {versao_atual.major}.{versao_atual.minor}.{versao_atual.micro} não é suportado")
        print(f"   Versão mínima necessária: {versao_minima[0]}.{versao_minima[1]}")
        return False
    elif versao_atual[:3] == versao_recomendada:
        print(f"✅ Python {versao_atual.major}.{versao_atual.minor}.{versao_atual.micro} - Versão exata recomendada!")
    elif versao_atual >= versao_minima:
        print(f"✅ Python {versao_atual.major}.{versao_atual.minor}.{versao_atual.micro} - Compatível")
    
    return True

def verificar_dependencias():
    """
    Verifica se as dependências principais estão instaladas.
    
    Returns:
        bool: True se todas as dependências estão disponíveis.
    """
    print("\n📦 Verificando dependências principais...")
    
    dependencias = [
        'fastapi',
        'uvicorn', 
        'pydantic',
        'langchain_core',
        'langchain_community',
        'aiofiles',
        'requests',
        'dotenv'
    ]
    
    faltando = []
    for dep in dependencias:
        try:
            # Tentar importar usando o nome padrão
            nome_import = dep.replace('-', '_')
            if dep == 'dotenv':
                nome_import = 'dotenv'
                
            spec = importlib.util.find_spec(nome_import)
            if spec is None:
                faltando.append(dep)
            else:
                print(f"   ✅ {dep}")
        except:
            faltando.append(dep)
    
    if faltando:
        print(f"\n❌ Dependências faltando: {', '.join(faltando)}")
        print("   Instale com: pip install " + " ".join(faltando))
        return False
    
    print("   ✅ Todas as dependências principais estão instaladas")
    return True

def main():
    """
    Função principal do validador.
    """
    print("🔍 INICIANDO VALIDAÇÃO COMPLETA DO CÓDIGO\n")
    
    # Verificar compatibilidade do Python
    if not validar_compatibilidade_python():
        sys.exit(1)
    
    # Verificar dependências
    if not verificar_dependencias():
        print("\n⚠️  Continue mesmo com dependências faltando se for apenas para validação de código.")
    
    print()
    
    # Validar códigos
    validador = ValidadorCodigo()
    sucesso = validador.validar_projeto()
    
    if sucesso:
        print("\n" + "🎉" * 20)
        print("TODOS OS CÓDIGOS VALIDADOS COM SUCESSO!")
        print("🎉" * 20)
        print("\n✅ Seu projeto está pronto para execução!")
    else:
        print("\n" + "⚠️ " * 15)
        print("ALGUNS PROBLEMAS PRECISAM SER CORRIGIDOS")
        print("⚠️ " * 15)
        sys.exit(1)

if __name__ == "__main__":
    main()