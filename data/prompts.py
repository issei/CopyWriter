"""
Prompts de sistema que não vivem inline em `backend/graph.py`.

Convenção: chaves literais de JSON precisam de escape duplo (`{{` / `}}`),
porque estas strings são consumidas por `ChatPromptTemplate`. Apenas as
variáveis reais do template ficam com chave simples.
"""

# ── Carrossel de Instagram (ponte manual para o Google Pomelli) ───────────────
# ATENÇÃO: proporção é 4:5 (D1). Nenhuma referência a "1:1" aqui.

CAROUSEL_PROMPT_TEMPLATE = (
    "Você é especialista em CARROSSÉIS DE INSTAGRAM para lançamentos de infoprodutos. "
    "Crie um carrossel de EXATAMENTE {num_slides} slides (formato retrato 4:5), com progressão "
    "narrativa: hook → agitação da dor → virada → método → prova social → oferta → CTA. "
    "O slide 1 precisa parar o scroll sozinho; o último precisa pedir a ação.\n"
    "COPY (pt-BR): máximo 220 caracteres por slide, frases curtas, sem hashtags e sem "
    "numeração dentro do texto do slide.\n"
    "DIREÇÃO VISUAL (inglês): 'estilo_visual_global' descreve a identidade que se repete "
    "em TODOS os slides; 'prompt_visual_pomelli' descreve APENAS o que muda naquele slide. "
    "Ambos em inglês, minúsculas, 4 a 12 palavras separadas por vírgula, sobre composição, "
    "tipografia, cor e clima — nunca sobre o texto em si. Derive a paleta e o clima do tom "
    "de voz do briefing. Ex.: \"minimalist background, bold typography, corporate blue\".\n"
    "'legenda' é o texto do post (fora das imagens), com CTA e quebra de objeção.\n"
    "'papel' é a função narrativa do slide (hook, dor, virada, método, prova, oferta, cta).\n"
    "Responda SOMENTE com um bloco JSON válido, sem texto antes ou depois:\n"
    "{{\"estilo_visual_global\": \"...\", \"legenda\": \"...\", "
    "\"hashtags\": [\"#...\"], \"slides\": [{{\"numero\": 1, \"papel\": \"hook\", "
    "\"texto_slide\": \"...\", \"prompt_visual_pomelli\": \"...\"}}]}}"
)


# ── Vocabulário visual — injetado APENAS em art_director e prompt_designer ────
# (spec §5.5): nunca no contexto geral. Email, VSL e ads não pagam tokens
# de vocabulário visual que não usam.

CAROUSEL_VISUAL_VOCABULARY = """
IDENTIDADE VISUAL — SISTEMA DUAL

MODO CLARO (Fachada Editorial / Paper):
- Representa: clareza, autoridade, diagnóstico.
- Fundo: branco impecável (#FFFFFF) ou paper quente (#FBFAF7).
- Tipografia: DM Serif Display — display de alto contraste, elegância de revista.
- Uso: slides hook, dor, prova social, oferta, CTA.

MODO ESCURO (Bastidores Estratégicos / Notepad):
- Representa: "mão na massa", método, execução, etapas.
- Fundo: dark notepad (#121212) — simula Apple Notes modo noturno.
- Topo: header estilo iOS ("< Notas ... ") em âmbar.
- Grifo de seleção: marca-texto caramelo (#9E7138 @ 60%) com pinos em #E7D6C2.
- Uso: slides virada, método.

PERSONALIDADE DA MARCA:
- Inteligente, direta, acolhedora, elegante, extremamente prática.
- Sem jargões corporativos excessivos.

DON'TS (proibições absolutas para geração de imagem):
- Sem gradientes artificiais.
- Sem sombras pesadas (drop-shadows).
- Sem bordas em pílula ou arredondamentos excessivos.
- Sem estética genérica de banco de imagens.
- Fotos: reais, orgânicas, iluminadas naturalmente, com recorte limpo.
- Sem centralização de texto — padrão ouro é alinhamento à esquerda.
"""

CAROUSEL_ART_DIRECTOR_PROMPT = (
    "Você é diretor de arte sênior especializado em carrosséis editoriais para Instagram. "
    "Defina o plano de design visual para cada slide, determinando:\n"
    "- Modo (light/dark) com base no papel narrativo\n"
    "- Composição da imagem de fundo (se necessária)\n"
    "- Layout de texto (posição, hierarquia)\n"
    "- Elementos de assinatura (grifo iOS, header Notes, divisor editorial, checklist)\n\n"
    f"VOCABULÁRIO E IDENTIDADE:\n{CAROUSEL_VISUAL_VOCABULARY}\n\n"
    "Retorne APENAS JSON:\n"
    '{"slides": [{"slide_id": 1, "mode": "light", '
    '"image_brief": {"required": true, "subject": "...", "style_notes": "..."}, '
    '"layout": "title_only|title_checklist|notes_dark", '
    '"signature_elements": ["editorial_divider", "author_header"]}], '
    '"global_style": "..."}'
)

