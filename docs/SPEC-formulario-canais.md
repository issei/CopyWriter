# SPEC — Briefing opcional e canais seletivos

Especificação de implementação. **Execute as etapas na ordem.** As decisões já foram
tomadas: não delibere, não proponha alternativas, não amplie o escopo.

---

## 1. Contexto mínimo

`CopyWriter` é um app Streamlit que gera copy de lançamento com um grafo LangGraph.
O usuário preenche um briefing, o grafo roda agentes e a UI exibe o resultado por canal.

**Estado atual (o problema):**

- Todos os campos do formulário vêm com **texto de exemplo pré-preenchido**. Quem não
  apaga envia o exemplo como se fosse briefing real.
- O campo `canais` é escrito no briefing mas **não decide nada**: `node_adaptacao_canais`
  chama os 4 canais sempre, fixos no código.
- `analise_prova_social` roda sempre, mesmo sem nenhum dado de prova social — 1 chamada
  ao LLM desperdiçada.
- Campos vazios entram nos prompts como `""`, `null` e rótulos órfãos (`Preço: R$ None`).

**Objetivo:** briefing todo opcional, canais em multiseleção controlando quais agentes
rodam, e nada vazio chegando aos prompts. Ganho medido: de 9 para 5 chamadas ao LLM no
cenário enxuto.

---

## 2. Regras invioláveis

1. **`pytest tests/ -q` deve terminar com 41 passed ou mais, sempre.** Rode após cada etapa.
   Se quebrar, conserte antes de seguir.
2. **Não altere o contrato JSON do carrossel.** As chaves `estilo_visual_global`,
   `legenda`, `hashtags` e `slides[]` com `numero`/`papel`/`texto_slide`/`prompt_visual_pomelli`
   são consumidas por `normalizar_carrossel` e por testes existentes.
3. **Não remova nem desabilite nenhum teste** para fazer a suíte passar.
4. **Todo acesso a campo de estado usa `.get()` com default**, nunca indexação por colchete.
5. **Chaves literais de JSON dentro de prompts levam escape duplo** (`{{` e `}}`). Apenas
   variáveis reais do template ficam com chave simples. Se errar isso, o `ChatPromptTemplate`
   levanta erro no import.
6. **Não crie canais novos.** Os 5 do registro já têm agente.

---

## 3. Decisões já tomadas

| Questão | Decisão |
|---|---|
| Nenhum canal selecionado | Desabilitar o botão de gerar, com aviso |
| Briefing totalmente vazio | Exigir **um** campo: a dor principal (alimenta a query do RAG) |
| Carrossel | Entra na lista de canais; o radio "Copy padrão / + Carrossel" é **removido** |
| Carrossel no loop de refinamento | **Fica fora**, como hoje — nó dedicado após o crítico |
| Histórico antigo sem `canais` | Lê como "todos os canais". Sem migração de banco |

---

## Etapa 1 — `data/prompts.py`

O arquivo já existe e contém `CAROUSEL_PROMPT_TEMPLATE`. **Substitua o conteúdo inteiro**
pelo abaixo. Os 4 prompts de canal saem de `backend/graph.py` (onde estão inline) e passam
a viver aqui, reescritos no mesmo esqueleto: PAPEL / TAREFA / RESTRIÇÕES / CONTEXTO / SAÍDA.

```python
"""
Prompts de sistema e catálogos do formulário.

Convenção: chaves literais de JSON levam escape duplo (`{{` / `}}`), porque estas
strings são consumidas por `ChatPromptTemplate`. Apenas variáveis reais do template
ficam com chave simples — hoje só `{num_slides}`, no prompt do carrossel.

Todo prompt de canal segue o mesmo esqueleto:
    PAPEL       — um especialista, uma frase.
    TAREFA      — o que entregar, com a estrutura obrigatória.
    RESTRIÇÕES  — limites verificáveis.
    CONTEXTO    — usar só o fornecido; não inventar dado ausente.
    SAÍDA       — só o bloco JSON, sem preâmbulo e sem comentário.
"""

# ── Trecho comum a todos os canais ───────────────────────────────────────────

_CONTEXTO_E_SAIDA = (
    "CONTEXTO\n"
    "Use apenas o que o briefing e o contexto estratégico fornecem. Se um dado não foi "
    "informado (preço, data, garantia, depoimento, métrica), NÃO invente e NÃO use texto "
    "de preenchimento como '[inserir preço]': escreva a copy sem depender dele.\n\n"
    "SAÍDA\n"
    "Responda APENAS com o JSON especificado. Sem preâmbulo, sem explicação, sem "
    "comentário sobre a própria resposta, sem texto antes ou depois.\n"
)


# ── Email ────────────────────────────────────────────────────────────────────

EMAIL_PROMPT = (
    "PAPEL\n"
    "Você é copywriter sênior de email marketing para lançamentos de infoprodutos, "
    "especialista em resposta direta.\n\n"
    "TAREFA\n"
    "Escreva UM email de vendas completo, nesta ordem: subject line com benefício "
    "concreto ou tensão real; abertura que gera identificação em até duas frases; "
    "storytelling ligando a dor à solução; prova social integrada ao texto corrido, "
    "nunca em bloco isolado; quebra das duas objeções mais prováveis; apresentação da "
    "oferta; CTA único e explícito.\n\n"
    "RESTRIÇÕES\n"
    "- Corpo com no mínimo 400 palavras.\n"
    "- Subject com no máximo 60 caracteres.\n"
    "- Tom conversacional e direto. Sem jargão de marketing e sem superlativo vazio.\n"
    "- Um único CTA, repetido no máximo duas vezes.\n\n"
    + _CONTEXTO_E_SAIDA +
    "{{\"subject\": \"...\", \"body\": \"...\"}}"
)


# ── Instagram Stories ────────────────────────────────────────────────────────

STORIES_PROMPT = (
    "PAPEL\n"
    "Você é especialista em Instagram Stories para lançamentos de infoprodutos.\n\n"
    "TAREFA\n"
    "Crie uma sequência de EXATAMENTE 8 slides verticais (9:16) com progressão narrativa: "
    "hook, dor, solução, prova, oferta, urgência, CTA e lembrete — um papel por slide, "
    "nessa ordem. Cada slide funciona sozinho e também como parte da sequência.\n\n"
    "RESTRIÇÕES\n"
    "- Máximo 3 linhas de texto por slide.\n"
    "- Linguagem informal, com emoji apenas quando acrescenta sentido.\n"
    "- 'visual' descreve o que aparece na tela, nunca repete o texto do slide.\n\n"
    + _CONTEXTO_E_SAIDA +
    "{{\"slides\": [{{\"numero\": 1, \"visual\": \"...\", \"copy\": \"...\"}}]}}"
)


# ── Meta Ads ─────────────────────────────────────────────────────────────────

ADS_PROMPT = (
    "PAPEL\n"
    "Você é especialista em Meta Ads (Facebook e Instagram) para lançamentos de "
    "infoprodutos.\n\n"
    "TAREFA\n"
    "Crie EXATAMENTE 3 variações de anúncio no framework AIDA, cada uma com um ângulo "
    "distinto: variação 1 pelo ângulo da dor, variação 2 pela transformação, variação 3 "
    "pela autoridade ou prova social.\n\n"
    "RESTRIÇÕES\n"
    "- headline: máximo 40 caracteres.\n"
    "- primary_text: máximo 300 caracteres, com a mensagem completa — não trunque.\n"
    "- link_description: máximo 30 caracteres.\n"
    "- Os três ângulos precisam ser realmente diferentes, não reformulações do mesmo.\n\n"
    + _CONTEXTO_E_SAIDA +
    "{{\"ads\": [{{\"angulo\": \"...\", \"headline\": \"...\", "
    "\"primary_text\": \"...\", \"link_description\": \"...\"}}]}}"
)


# ── VSL ──────────────────────────────────────────────────────────────────────

VSL_PROMPT = (
    "PAPEL\n"
    "Você é roteirista de VSL (Video Sales Letter) para lançamentos de infoprodutos.\n\n"
    "TAREFA\n"
    "Escreva o script completo de um VSL de 15 minutos, nestes 8 blocos obrigatórios e "
    "nesta ordem:\n"
    "0:00-1:30 Hook — promessa ousada que para o scroll\n"
    "1:30-3:30 Identificação da Dor — espelhamento da dor do público\n"
    "3:30-6:00 Minha História — jornada do produtor, gerando autoridade\n"
    "6:00-8:00 A Descoberta — o método como virada de chave\n"
    "8:00-10:00 Prova Social — casos concretos\n"
    "10:00-12:00 O Que Você Vai Ter — oferta detalhada\n"
    "12:00-13:30 Garantia e Objeções — últimas resistências\n"
    "13:30-15:00 CTA e Urgência — chamada com escassez real\n\n"
    "RESTRIÇÕES\n"
    "- Texto falado, para ser lido em voz alta: frases curtas, sem subordinação longa.\n"
    "- Sem marcação de cena, sem rubrica, sem instrução de câmera.\n"
    "- Escassez só se o briefing informar data ou limite real.\n\n"
    + _CONTEXTO_E_SAIDA +
    "{{\"script\": [{{\"time\": \"0:00-1:30\", \"segment\": \"Hook\", \"copy\": \"...\"}}]}}"
)


# ── Carrossel (contrato JSON NÃO pode mudar) ─────────────────────────────────

CAROUSEL_PROMPT_TEMPLATE = (
    "PAPEL\n"
    "Você é especialista em carrosséis de Instagram para lançamentos de infoprodutos.\n\n"
    "TAREFA\n"
    "Crie um carrossel de EXATAMENTE {num_slides} slides (1:1) com progressão narrativa: "
    "hook, agitação da dor, virada, método, prova social, oferta e CTA. O slide 1 precisa "
    "parar o scroll sozinho; o último precisa pedir a ação. 'legenda' é o texto do post, "
    "fora das imagens, com CTA e quebra de objeção.\n\n"
    "RESTRIÇÕES\n"
    "- 'texto_slide' em português, máximo 220 caracteres, sem hashtag e sem numeração.\n"
    "- 'papel' é a função narrativa do slide (hook, dor, virada, metodo, prova, oferta, cta).\n"
    "- 'estilo_visual_global' descreve a identidade que se repete em TODOS os slides.\n"
    "- 'prompt_visual_pomelli' descreve APENAS o que muda naquele slide.\n"
    "- Ambos em inglês, minúsculas, 4 a 12 palavras separadas por vírgula, sobre "
    "composição, tipografia, cor e clima — nunca sobre o texto. Derive a paleta e o clima "
    "do tom de voz do briefing. Ex.: \"minimalist background, bold typography, corporate blue\".\n\n"
    + _CONTEXTO_E_SAIDA +
    "{{\"estilo_visual_global\": \"...\", \"legenda\": \"...\", "
    "\"hashtags\": [\"#...\"], \"slides\": [{{\"numero\": 1, \"papel\": \"hook\", "
    "\"texto_slide\": \"...\", \"prompt_visual_pomelli\": \"...\"}}]}}"
)


# ── Registro de canais ───────────────────────────────────────────────────────
# Fonte única da verdade: define a ordem do multiselect, quais agentes rodam e a
# ordem das abas de resultado.
#
#   rotulo       — texto exibido no multiselect e na aba
#   prompt       — prompt de sistema do agente
#   raiz         — chave a desembrulhar da resposta do LLM (None = usa o dict inteiro)
#   no_dedicado  — True quando o canal tem nó próprio no grafo e NÃO entra no laço
#                  de `node_adaptacao_canais`

CANAIS = {
    "email": {
        "rotulo": "📧 Email Marketing",
        "prompt": EMAIL_PROMPT,
        "raiz": None,
        "no_dedicado": False,
    },
    "stories": {
        "rotulo": "📱 Instagram Stories",
        "prompt": STORIES_PROMPT,
        "raiz": "slides",
        "no_dedicado": False,
    },
    "carrossel": {
        "rotulo": "🎠 Instagram Carrossel",
        "prompt": CAROUSEL_PROMPT_TEMPLATE,
        "raiz": None,
        "no_dedicado": True,          # gerado por `geracao_carrossel`, após o crítico
    },
    "ads": {
        "rotulo": "📢 Meta Ads",
        "prompt": ADS_PROMPT,
        "raiz": "ads",
        "no_dedicado": False,
    },
    "vsl": {
        "rotulo": "📺 YouTube (VSL)",
        "prompt": VSL_PROMPT,
        "raiz": None,
        "no_dedicado": False,
    },
}

CANAIS_PADRAO = [c for c in CANAIS if not CANAIS[c]["no_dedicado"]]


# ── Gatilhos mentais (multiselect do formulário) ─────────────────────────────
# Ordenados por família. A lista é fechada de propósito: evita erro de digitação
# e dá vocabulário a quem não é da área.

GATILHOS_MENTAIS = [
    # Cialdini
    "Reciprocidade", "Compromisso e coerência", "Prova social",
    "Autoridade", "Afinidade", "Escassez",
    # Tempo e perda
    "Urgência", "Aversão à perda (FOMO)", "Antecipação", "Novidade", "Efeito manada",
    # Identidade e desejo
    "Transformação de identidade", "Ganho de status", "Pertencimento e comunidade",
    "Exclusividade", "Inimigo comum", "Dor vs. prazer",
    # Atalhos cognitivos
    "Curiosidade", "Especificidade", "Ancoragem de preço", "Contraste",
    "Razão (o \"porquê\")", "Simplicidade", "Justificativa lógica",
    # Confiança e risco
    "Garantia e reversão de risco", "Prova e demonstração",
    "Humanização e vulnerabilidade", "Transparência", "Storytelling",
    # Oferta
    "Bônus empilhados", "Gratuidade", "Indicação e referência",
]
```

**Verificação:**

```bash
python3 -c "
from data.prompts import CANAIS, GATILHOS_MENTAIS, CANAIS_PADRAO
import string
assert len(CANAIS) == 5 and len(GATILHOS_MENTAIS) == 32
assert CANAIS_PADRAO == ['email', 'stories', 'ads', 'vsl']
for nome, c in CANAIS.items():
    vars_ = [f[1] for f in string.Formatter().parse(c['prompt']) if f[1]]
    esperado = ['num_slides'] if nome == 'carrossel' else []
    assert vars_ == esperado, (nome, vars_)
    c['prompt'].format(num_slides=7)   # falha se o escape de chaves estiver errado
print('etapa 1 OK')
"
```

---

## Etapa 2 — `backend/parsers.py`

### 2.1 Adicione `podar` logo após os imports

```python
def podar(valor: Any) -> Any:
    """
    Remove recursivamente strings vazias, None, listas e dicts vazios.

    O briefing é serializado em TODA chamada ao LLM; campos em branco viram ruído
    (`""`, `null`) que o modelo tenta interpretar. Zero e False são preservados.
    """
    if isinstance(valor, dict):
        limpo = {k: podar(v) for k, v in valor.items()}
        return {k: v for k, v in limpo.items() if v not in ("", None, [], {})}
    if isinstance(valor, list):
        itens = [podar(v) for v in valor]
        return [v for v in itens if v not in ("", None, [], {})]
    if isinstance(valor, str):
        return valor.strip()
    return valor
```

### 2.2 Substitua `canonicalize_briefing` inteira

A versão atual emite toda linha mesmo vazia (`Preço: R$ None`, `USP:`). A nova só
emite linha com conteúdo.

```python
def canonicalize_briefing(briefing_dict: Dict) -> str:
    """Converte o briefing em texto estruturado para indexação, omitindo o que está vazio."""
    b   = briefing_dict.get("briefing_lancamento", {})
    inf = b.get("infoproduto", {})
    pub = b.get("publico_alvo", {})
    pos = b.get("posicionamento", {})
    est = b.get("estrategia_lancamento", {})
    ps  = b.get("prova_social", {})

    linhas = ["# Briefing de Lançamento"]

    def add(rotulo: str, valor) -> None:
        """Acrescenta a linha apenas quando há valor."""
        if isinstance(valor, list):
            valor = ", ".join(str(v) for v in valor if str(v).strip())
        if valor is None or not str(valor).strip():
            return
        linhas.append(f"{rotulo}: {valor}")

    add("Nome", inf.get("nome"))
    add("Produtor", inf.get("produtor"))
    add("Preço", f"R$ {inf.get('preco')}" if inf.get("preco") else None)
    add("Formato", inf.get("formato"))
    add("Descrição", inf.get("descricao"))
    add("Dor principal", pub.get("problema_principal"))
    add("Transformação", pub.get("transformacao_principal"))
    add("Perfil", pub.get("demografia"))
    for o in pub.get("objecoes_comuns", []):
        add("Objeção", o)
    add("USP", pos.get("diferencial_competitivo"))
    add("Tom de voz", pos.get("tom_de_voz"))
    add("Gatilhos", pos.get("gatilhos_mentais"))
    add("Lançamento", est.get("tipo_lancamento"))
    add("Meta", est.get("meta_campanha"))
    add("Canais", est.get("canais"))
    add("Autoridade", ps.get("autoridade_produtor"))
    add("Depoimentos", ps.get("depoimentos"))
    add("Métricas", ps.get("metricas"))

    return "\n".join(linhas)
```

**Verificação:**

```bash
python3 -c "
from backend.parsers import podar, canonicalize_briefing
assert podar({'a': '', 'b': 'x', 'c': {'d': None}, 'e': [None, 'y'], 'f': 0}) == {'b':'x','e':['y'],'f':0}
vazio = {'briefing_lancamento': {'publico_alvo': {'problema_principal': 'Estou estagnado.'}}}
t = canonicalize_briefing(vazio)
assert t == '# Briefing de Lançamento\nDor principal: Estou estagnado.', repr(t)
assert 'None' not in t
print('etapa 2 OK')
"
```

---

## Etapa 3 — `backend/graph.py`

### 3.1 Imports

Troque a linha de import de `data.prompts` por:

```python
from data.prompts import CANAIS, CANAIS_PADRAO
```

### 3.2 `AgentState`

Acrescente um campo, mantendo todos os existentes:

```python
    canais: Optional[list]   # chaves de CANAIS selecionadas; ausente = todos
```

### 3.3 Remova os 4 blocos `chain_email`, `chain_stories`, `chain_ads`, `chain_vsl`

Substitua os quatro por um dicionário construído a partir do registro. Mantenha
`chain_prova_social`, `chain_critico` e `chain_carrossel` como estão.

```python
    # Uma chain por canal, montada a partir do registro.
    chains_canal = {
        nome: ChatPromptTemplate.from_messages([
            ("system", cfg["prompt"]),
            ("human", _canal_prompt()),
        ]) | llm
        for nome, cfg in CANAIS.items()
    }
```

`chain_carrossel` passa a ser `chains_canal["carrossel"]` — remova a construção separada.

### 3.4 Substitua `node_adaptacao_canais` inteira

```python
    def _canais_selecionados(state: AgentState) -> list:
        """Canais padrão pedidos pelo usuário. Ausente = todos (histórico antigo)."""
        pedidos = state.get("canais")
        if not pedidos:
            return list(CANAIS_PADRAO)
        return [c for c in CANAIS_PADRAO if c in pedidos]

    def node_adaptacao_canais(state: AgentState) -> Dict[str, Any]:
        tentativa = state.get("tentativas_refinamento", 0) + 1
        selecionados = _canais_selecionados(state)
        st.write(
            f"🔄 *Adaptação por Canal:* gerando copy para {len(selecionados)} canal(is) "
            f"(tentativa {tentativa})..."
        )

        contexto = state.get("contexto_enriquecido", "{}")
        try:
            if "error" in json.loads(contexto):
                return {"copy_por_canal": {"error": "Contexto inválido."},
                        "tentativas_refinamento": tentativa}
        except (json.JSONDecodeError, TypeError):
            pass

        inp = _canal_input(state)
        copy = {}
        for i, canal in enumerate(selecionados):
            if i:
                time.sleep(2)   # espaçamento de RPM do free tier
            bruto = force_json(safe_invoke(chains_canal[canal], inp, canal))
            raiz = CANAIS[canal]["raiz"]
            copy[canal] = bruto.get(raiz, bruto) if raiz else bruto

        return {"copy_por_canal": copy, "tentativas_refinamento": tentativa}
```

### 3.5 `node_critico_revisor` — guarda e lista real de canais

No início da função, antes da checagem de `error`:

```python
        copy = state.get("copy_por_canal") or {}
        if not copy:
            # só o carrossel foi pedido: não há o que criticar, e uma chamada é poupada
            return {"revisao_critico": "APROVADO"}
```

E passe a lista de canais ao invocar:

```python
        r = safe_invoke(chain_critico, {
            "briefing":       _b(state),
            "canais":         ", ".join(copy.keys()),
            "copy_por_canal": json.dumps(copy, ensure_ascii=False),
        }, "Crítico")
```

No prompt de `chain_critico`, troque `"Avalie cada canal (email, stories, ads, vsl) em 3 critérios: "`
por `"Avalie cada canal ({canais}) em 3 critérios: "`.

### 3.6 `node_geracao_carrossel` — passe a ler a seleção

Nenhuma mudança na função. Ela continua usando `state.get("content_type")` via
`decidir_pos_critica`; quem define `content_type` passa a ser `app.py` (etapa 5).

### 3.7 Aresta condicional que pula a prova social

Adicione a função no nível do módulo, ao lado de `decidir_pos_critica`:

```python
def tem_prova_social(state: AgentState) -> str:
    """Pula o agente de prova social quando não há nenhum dado para ele formatar."""
    ps = state.get("briefing", {}).get("briefing_lancamento", {}).get("prova_social", {})
    preenchido = any(str(v).strip() for v in ps.values()) if isinstance(ps, dict) else False
    return "com_prova" if preenchido else "sem_prova"
```

Na montagem do grafo, **remova** `graph.add_edge("consolidador", "analise_prova_social")`
e coloque no lugar:

```python
    graph.add_conditional_edges(
        "consolidador",
        tem_prova_social,
        {"com_prova": "analise_prova_social", "sem_prova": "adaptacao_canais"},
    )
```

Mantenha `graph.add_edge("analise_prova_social", "adaptacao_canais")`.

**Verificação:** `pytest tests/ -q` deve continuar passando.

---

## Etapa 4 — `frontend/ui_form.py`

### 4.1 Remova o seletor de modo

Apague as constantes `MODO_PADRAO` e `MODO_CARROSSEL`, o `st.radio` de tipo de entrega
e o `st.caption` que o acompanha. **Mantenha** o slider de número de slides — ele passa a
ser condicionado à seleção do canal carrossel (item 4.4).

### 4.2 Zere todos os defaults

Em **todos** os `st.text_input`, `st.text_area` e `st.number_input` das 5 abas, troque
`value=_v("campo", "texto de exemplo")` por `value=_v("campo", "")`.

Exceção: `preco` usa `value=_v("preco", None)` e precisa de `st.number_input(..., value=None)`,
que o Streamlit renderiza em branco e devolve `None`.

Os exemplos não se perdem: continuam em `data/templates.py`, acessíveis pelo seletor de
template de nicho.

### 4.3 Gatilhos mentais viram multiselect

Substitua o `st.text_input` + `_split_csv` por:

```python
        gatilhos_mentais = st.multiselect(
            "Gatilhos Mentais",
            options=GATILHOS_MENTAIS,
            default=[g for g in _v("gatilhos_mentais", []) if g in GATILHOS_MENTAIS],
            help="Opcional. Orienta o tom da copy em todos os canais.",
        )
```

O filtro no `default` é obrigatório: um valor fora de `options` faz o Streamlit levantar erro,
e o histórico pode conter gatilhos digitados à mão na versão antiga.

### 4.4 Canais viram multiselect e comandam o slider

Substitua o `st.text_input` de canais por:

```python
        canais = st.multiselect(
            "Canais",
            options=list(CANAIS.keys()),
            format_func=lambda c: CANAIS[c]["rotulo"],
            default=[c for c in _v("canais", []) if c in CANAIS],
            help="Cada canal tem um agente especializado. Só os selecionados são gerados.",
        )
        num_slides = None
        if "carrossel" in canais:
            num_slides = st.slider(
                "Número de slides do carrossel",
                min_value=5, max_value=10,
                value=clamp_slides(_v("num_slides", 7)),
            )
```

> `default=[]` significa que o formulário abre sem canal marcado. Isso é intencional: o
> botão de gerar fica desabilitado até haver escolha (etapa 5).

### 4.5 Imports e retorno

Acrescente ao topo:

```python
from data.prompts import CANAIS, GATILHOS_MENTAIS
```

No dicionário de retorno, `canais` guarda as **chaves** (`"email"`), não os rótulos.
Troque as chaves privadas do final por:

```python
        "_problema_principal": problema_principal,
        "_num_slides": num_slides,
```

Remova `"_content_type"` — quem deriva agora é `app.py`.

---

## Etapa 5 — `app.py`

### 5.1 Leitura do formulário

```python
briefing_dinamico = render_form()
problema_principal = briefing_dinamico.pop("_problema_principal", "")
num_slides         = briefing_dinamico.pop("_num_slides", None)

canais = (briefing_dinamico.get("briefing_lancamento", {})
          .get("estrategia_lancamento", {}).get("canais", []))
content_type = "carousel" if "carrossel" in canais else "padrao"
```

### 5.2 Botão desabilitado e motivo visível

```python
faltando = []
if not canais:
    faltando.append("selecione ao menos um canal")
if not problema_principal.strip():
    faltando.append("preencha a dor principal")

with col_btn:
    gerar = st.button(
        "🚀 Iniciar Inteligência de Grafo e Gerar Copy",
        type="primary",
        use_container_width=True,
        disabled=bool(faltando),
    )
if faltando:
    st.caption("⚠️ Para gerar: " + " · ".join(faltando) + ".")
```

### 5.3 Poda antes do RAG e do grafo

```python
from backend.parsers import podar
...
briefing_limpo = podar(briefing_dinamico)

with st.spinner("Indexando briefing no RAG local..."):
    rag_context = setup_rag(briefing_limpo, problema_principal)

initial_state = AgentState(
    briefing=briefing_limpo,
    contexto_rag=rag_context,
    tentativas_refinamento=0,
    canais=canais,
    content_type=content_type,
    num_slides=num_slides,
)
```

`hist.salvar` também passa a receber `briefing_limpo`.

---

## Etapa 6 — `frontend/ui_results.py`

As abas deixam de ser lista fixa e passam a sair de `copy_por_canal`.

### 6.1 Extraia cada bloco de aba para uma função

Crie `_render_email(dados)`, `_render_stories(dados)`, `_render_ads(dados)` e
`_render_vsl(dados)`. **Mova o corpo atual de cada aba verbatim**; a única mudança é que
`final_copy.get("email", {})` vira o parâmetro `dados`. `_render_carrossel` já existe.

### 6.2 Substitua a montagem das abas

```python
RENDERIZADORES = {
    "email": _render_email,
    "stories": _render_stories,
    "carrossel": _render_carrossel,
    "ads": _render_ads,
    "vsl": _render_vsl,
}

# ... dentro de render_results, após a checagem de erro global:
presentes = [c for c in CANAIS if c in final_copy]
nomes = [CANAIS[c]["rotulo"] for c in presentes] + ["📄 JSON Completo"]
abas = st.tabs(nomes)

for canal, aba in zip(presentes, abas):
    with aba:
        RENDERIZADORES[canal](final_copy[canal])

with abas[-1]:
    st.json(final_copy)
    st.download_button(
        "⬇️ Baixar JSON Completo",
        data=json.dumps(final_copy, ensure_ascii=False, indent=2),
        file_name="copy_completa.json",
        mime="application/json",
    )
```

Remova as constantes `ABA_EMAIL`, `ABA_STORIES`, `ABA_CARROSSEL`, `ABA_VSL`, `ABA_ADS`,
`ABA_JSON` — o rótulo agora vem do registro.

---

## Etapa 7 — Testes

Crie `tests/test_formulario_canais.py` cobrindo:

| Caso | Asserção |
|---|---|
| `podar` remove vazios | `podar({'a':'','b':'x'}) == {'b':'x'}` |
| `podar` preserva zero | `podar({'preco': 0})== {'preco': 0}` |
| `canonicalize_briefing` sem vazios | `'None' not in t` e nenhuma linha terminando em `: ` |
| Seleção parcial | estado com `canais=['email']` gera só `email` em `copy_por_canal` |
| Seleção ausente | estado sem `canais` gera os 4 padrão (compatibilidade) |
| Carrossel não entra no laço | `canais=['email','carrossel']` → `adaptacao_canais` gera só `email` |
| Pula prova social | `tem_prova_social({}) == 'sem_prova'` |
| Roda prova social | com `autoridade_produtor` preenchido → `'com_prova'` |
| Crítico sem canais | `copy_por_canal={}` → `revisao_critico == 'APROVADO'` sem chamar o LLM |
| Registro íntegro | todo `CANAIS[c]['rotulo']` é único; `raiz` é `str` ou `None` |

Para os casos de grafo, siga o padrão já usado em `tests/test_carrossel.py`:
`patch("backend.graph.get_llm", return_value=RunnableLambda(...))` e
`get_compiled_graph.__wrapped__()`.

---

## Checklist final

Antes de considerar concluído, confirme **todos**:

- [ ] `pytest tests/ -q` — 41 testes antigos + os novos, todos passando
- [ ] `python3 -c "import app"` não levanta erro de import
- [ ] Nenhum `value=` de widget contém texto de exemplo
- [ ] `grep -rn "MODO_PADRAO\|MODO_CARROSSEL\|ABA_EMAIL" .` não retorna nada
- [ ] `grep -n "email, stories, ads, vsl" backend/graph.py` não retorna nada
- [ ] O contrato JSON do carrossel está intacto (testes de `normalizar_carrossel` passando)
- [ ] Rodar `streamlit run app.py`: o botão nasce desabilitado e habilita ao escolher um
      canal e preencher a dor principal
