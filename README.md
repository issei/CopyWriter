# CopyWriter AI

Geração de Copy para Lançamentos com LangGraph.

## Hipóteses Assumidas e Exceções (Especificação Visual)

Conforme a `SPEC-IMPLEMENTACAO.md`, as seguintes hipóteses e restrições foram adotadas durante o desenvolvimento do renderizador determinístico do carrossel:

- **D5 (Nenhuma variável de ambiente nova lida internamente):** O projeto utiliza `Gemini` e toda a configuração flui via Factory, lendo a chave a partir de `config.py`. Não foram introduzidas chaves como `OPENAI_API_KEY` ou `TEXT_MODEL_PROVIDER` diretamente nos workers do carrossel.
- **D6 (Bold Sintético Proibido):** A identidade solicitou *DM Serif Display Bold 700*. Como a família DM Serif Display só possui pesos Regular e Italic, o renderizador utiliza **DM Serif Display Regular**. A utilização de negrito sintético (traço artificial da engine gráfica) foi estritamente proibida por destruir a modulação da fonte serifada, sendo esta uma exceção consciente à regra de pesos da identidade.
- **D10 (CLI Pública Adiada):** A versão CLI originalmente pensada na V1 foi adiada em favor de uma integração direta ao pipeline visual utilizando Streamlit para orquestração. O código ainda suporta modos `--dry-run` para facilitar a validação via pytest, mas o CLI público oficial não é parte da interface padrão do projeto.

---
Para rodar a aplicação:
```bash
start.bat
```
