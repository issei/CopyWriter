@echo off
setlocal enabledelayedexpansion

REM Verificar se o venv existe
if not exist "venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    python -m venv venv
)

REM Ativar o ambiente virtual
call venv\Scripts\activate.bat

REM Instalar/atualizar dependências
echo Verificando dependências...
pip install -q -r requirements.txt

REM Verificar se o .env existe
if not exist ".env" (
    echo.
    echo ⚠️  AVISO: Arquivo .env não encontrado!
    echo.
    echo Por favor, crie um arquivo .env na raiz do projeto com:
    echo GOOGLE_API_KEY=sua_chave_aqui
    echo.
    pause
    exit /b 1
)

REM Iniciar a aplicação
echo.
echo 🚀 Iniciando CopyWriter AI...
echo.
streamlit run app.py
