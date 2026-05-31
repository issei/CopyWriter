# AGENT.md — CopyWriter AI

Guia de referência para o agente de IA que trabalha neste repositório.

---

## O que é este projeto

Aplicação Streamlit que usa um grafo LangGraph para gerar copy de lançamento de infoprodutos em múltiplos canais (Email, Instagram Stories, YouTube VSL, Meta Ads). O fluxo usa RAG local (ChromaDB) para enriquecer contexto e um ciclo de revisão com crítico de marketing.

**Stack:** Python 3.14 · Streamlit 1.58 · LangGraph 1.2 · LangChain 1.3 · langchain-google-genai 4.2 · ChromaDB 1.5 · google-genai 2.7

---

## Estrutura de arquivos

```
D:\projetos\CopyWriter\
├── app.py           # Toda a aplicação (backend + frontend em um único arquivo)
├── requirements.txt # Dependências pip
├── venv/            # Ambiente virtual (não commitar)
└── chroma_db/       # Criado em runtime — apagado e recriado a cada execução
```

---

## Como rodar

```powershell
cd D:\projetos\CopyWriter
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

Acesse `http://localhost:8501`.

---

## Arquitetura do grafo LangGraph

```
START ──┬──► analise_dores_promessas ──┐
        ├──► analise_objecoes_quebras ──┼──► consolidador ──► adaptacao_canais ──► critico_revisor
        └──► analise_headlines_angulos ─┘                              │
                                                        ┌──────────────┘
                                               "REFINAR" (até 2x) ──► adaptacao_canais
                                               "APROVADO" ──► END
```

### Nós e responsabilidades

| Nó | Função | Saída no estado |
|----|--------|----------------|
| `analise_dores_promessas` | Extrai dores e promessas transformacionais | `dores_promessas` |
| `analise_objecoes_quebras` | Mapeia objeções e cria quebras persuasivas | `objecoes_quebras` |
| `analise_headlines_angulos` | Gera headlines magnéticas e ângulos criativos | `headlines_angulos` |
| `consolidador` | Merge das 3 análises em JSON enriquecido | `contexto_enriquecido` |
| `adaptacao_canais` | Gera copy para email, stories, ads e VSL | `copy_por_canal` |
| `critico_revisor` | Aprova (`APROVADO`) ou solicita ajuste (`REFINAR:`) | `revisao_critico` |

Os 3 primeiros nós rodam em paralelo — todos têm `set_entry_point`, convergindo no `consolidador`.

### `AgentState` (TypedDict)

```python
briefing: Dict                # Briefing completo do formulário
contexto_rag: str             # Chunks recuperados do ChromaDB
dores_promessas: Optional[Dict]
objecoes_quebras: Optional[Dict]
headlines_angulos: Optional[Dict]
contexto_enriquecido: Optional[str]  # JSON consolidado das 3 análises
copy_por_canal: Optional[Dict]       # Outputs finais: email, stories, ads, vsl
revisao_critico: Optional[str]       # "APROVADO" ou "REFINAR: ..."
tentativas_refinamento: int          # Máx: MAX_REFINEMENT_ATTEMPTS = 2
```

---

## RAG (Retrieval-Augmented Generation)

- **Embedding model:** `models/gemini-embedding-001` via `GoogleGenerativeAIEmbeddings`
  - Atenção: `langchain-google-genai` 4.x usa o SDK `google-genai` que roteia para v1beta. Apenas modelos Gemini Embedding funcionam nesse endpoint. `text-embedding-004` e `embedding-001` retornam 404.
- **Vector store:** `langchain_chroma.Chroma` (não `langchain_community` — deprecado)
- **Chunk:** 1000 chars, overlap 150
- **Limpeza:** `chroma_db/` é deletada com `shutil.rmtree` antes de cada execução para evitar contaminação entre briefings.
- **Query:** usa `problema_principal` do briefing para recuperar os chunks mais relevantes.

---

## Parsing de JSON do LLM (`force_json`)

O Gemini 2.5-flash nem sempre envolve a resposta em blocos markdown. A função `force_json` (linha 132) tenta 4 estratégias em cascata:

1. Bloco ` ```json ... ``` `
2. Qualquer bloco ` ``` ... ``` `
3. Primeiro `{...}` encontrado no texto livre
4. Texto completo limpo

Fallback devolve `{"error": "...", "raw_content": "..."}` que é detectado e exibido no frontend.

---

## Variáveis e constantes importantes

| Variável | Localização | Valor atual |
|----------|-------------|-------------|
| `GOOGLE_API_KEY` | linha 17 | hardcoded (trocar pela chave real) |
| `GEMINI_MODEL` | linha 21 | `"gemini-2.5-flash"` |
| `TEMPERATURE` | linha 22 | `0.7` |
| `MAX_REFINEMENT_ATTEMPTS` | linha 23 | `2` |

---

## Problemas conhecidos e soluções aplicadas

| Problema | Causa | Solução |
|----------|-------|---------|
| `ModuleNotFoundError: langchain.text_splitter` | Movido para pacote separado | `from langchain_text_splitters import RecursiveCharacterTextSplitter` |
| `DeprecationWarning: Chroma` | `langchain_community.vectorstores.Chroma` deprecado | `pip install langchain-chroma` + `from langchain_chroma import Chroma` |
| `404 NOT_FOUND: models/embedding-001` | Modelo não existe no endpoint v1beta | Usar `models/gemini-embedding-001` |
| `404 NOT_FOUND: models/text-embedding-004` | Mesmo problema de endpoint | Usar `models/gemini-embedding-001` |
| `"Falha ao decodificar JSON"` | LLM retorna JSON sem fences markdown | `force_json` com 4 estratégias de extração em cascata |
| `json.loads(contexto)` crashando | `contexto_enriquecido` pode não ser JSON válido | Envolto em `try/except (JSONDecodeError, TypeError)` |

---

## Limitações atuais

- **API key hardcoded** em `app.py:17`. Mover para `.env` + `python-dotenv` antes de qualquer commit público.
- **Todo o código em um único arquivo** (`app.py`). Para escalar, separar em `backend/graph.py`, `backend/rag.py`, `frontend/ui.py`.
- **LLM inicializado no módulo top-level** (linha 169), não dentro do botão. Cada rerun do Streamlit reinicializa o cliente desnecessariamente.
- **Grafo compilado no top-level** (linha 297). Mover para dentro do callback do botão ou usar `@st.cache_resource`.
- **Parallel nodes** (`set_entry_point` chamado 3x) funciona, mas LangGraph executa sequencialmente por padrão sem `async`. Os 3 agentes de análise rodam um após o outro, não em paralelo real.
- **`final_copy_state`** captura apenas o último evento `adaptacao_canais` do stream, ignorando o estado pós-crítico. Se o crítico aprovar sem refinar, o resultado já está correto; se refinar, pega a última versão.

---

## Melhorias aplicadas (de "próximos passos" → implementadas)

- [x] **`.env`** — `GOOGLE_API_KEY` movida para `.env`, carregada com `python-dotenv`. `.gitignore` cobre `.env`, `venv/`, `chroma_db/`.
- [x] **`@st.cache_resource`** — `get_compiled_graph()` cria LLM, chains e grafo uma única vez por sessão do servidor. Reruns do Streamlit reutilizam o objeto em cache.
- [x] **`st.session_state`** — `final_copy` persiste entre reruns. Botão "🗑️ Limpar" reseta e chama `st.rerun()`. Resultado exibido fora do bloco `if gerar:`.
- [x] **`START` explícito** — substituído o triplo `set_entry_point` por `add_edge(START, node)` com `from langgraph.graph import START`, que é a forma canônica do LangGraph 1.x.
- [x] **Download por canal** — cada aba tem seu próprio `st.download_button`: email `.txt`, stories `.txt`, VSL `.txt`, ads `.txt`, JSON completo `.json`.
- [x] **Debug expander** — quando `force_json` retorna `{"error": ..., "raw_content": ...}`, o frontend exibe `st.error` + `st.expander` com `st.code` do conteúdo bruto.
- [x] **Guard de API key** — se `GOOGLE_API_KEY` estiver vazia após `load_dotenv()`, exibe `st.error` e chama `st.stop()` antes de renderizar o formulário.
- [x] **Chaves alternativas nos outputs** — renderização aceita tanto `subject`/`body` quanto `assunto`/`corpo`, e `primary_text`/`texto_principal` nos ads, tornando o display robusto a variações do LLM.

## Estrutura de arquivos (atualizada)

```
D:\projetos\CopyWriter\
├── app.py           # Aplicação completa refatorada
├── .env             # GOOGLE_API_KEY (não commitar)
├── .gitignore       # Cobre .env, venv/, chroma_db/, __pycache__/
├── AGENT.md         # Este arquivo
├── requirements.txt # Dependências pip
├── venv/            # Ambiente virtual (não commitar)
└── chroma_db/       # Criado em runtime — apagado a cada execução
```
