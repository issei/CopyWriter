"""Utilitários de parsing: JSON do LLM, texto de arquivos, extração de campos."""
import json
import re
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate


# ── JSON do LLM ──────────────────────────────────────────────────────────────

def force_json(llm_output: Any) -> Dict:
    """Extrai JSON da resposta do LLM com 4 estratégias em cascata."""
    content_str = llm_output.content if hasattr(llm_output, "content") else str(llm_output)

    for pattern in [
        r"```json\s*([\s\S]*?)\s*```",   # 1. ```json ... ```
        r"```\s*([\s\S]*?)\s*```",        # 2. ``` ... ```
    ]:
        m = re.search(pattern, content_str)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    # 3. primeiro { ... } no texto livre
    m = re.search(r"\{[\s\S]*\}", content_str)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # 4. texto limpo direto
    try:
        return json.loads(content_str.strip())
    except json.JSONDecodeError:
        pass

    return {"error": "Falha ao decodificar JSON", "raw_content": content_str[:800]}


# ── Briefing → texto para RAG ────────────────────────────────────────────────

def canonicalize_briefing(briefing_dict: Dict) -> str:
    """Converte dicionário de briefing em texto estruturado para indexação."""
    b   = briefing_dict.get("briefing_lancamento", {})
    inf = b.get("infoproduto", {})
    pub = b.get("publico_alvo", {})
    pos = b.get("posicionamento", {})
    est = b.get("estrategia_lancamento", {})
    ps  = b.get("prova_social", {})

    linhas = [
        "# Briefing de Lançamento",
        f"Nome: {inf.get('nome','')} | Produtor: {inf.get('produtor','')}",
        f"Preço: R$ {inf.get('preco','')} | Formato: {inf.get('formato','')}",
        f"Descrição: {inf.get('descricao','')}",
        f"\nDor principal: {pub.get('problema_principal','')}",
        f"Transformação: {pub.get('transformacao_principal','')}",
        f"Perfil: {pub.get('demografia','')}",
    ]
    for o in pub.get("objecoes_comuns", []):
        linhas.append(f"- Objeção: {o}")
    linhas.extend([
        f"\nUSP: {pos.get('diferencial_competitivo','')}",
        f"Tom de voz: {pos.get('tom_de_voz','')}",
        "Gatilhos: " + ", ".join(pos.get("gatilhos_mentais", [])),
        f"\nLançamento: {est.get('tipo_lancamento','')} | Meta: {est.get('meta_campanha','')}",
        "Canais: " + ", ".join(est.get("canais", [])),
    ])
    if ps.get("autoridade_produtor"):
        linhas.append(f"\nAutoridade: {ps['autoridade_produtor']}")
    if ps.get("metricas"):
        linhas.append(f"Métricas: {ps['metricas']}")
    return "\n".join(linhas)


# ── Extração de texto de arquivos ────────────────────────────────────────────

def extrair_texto_de_arquivo(uploaded_file) -> str:
    """Extrai texto de PDF, DOCX ou TXT enviados via st.file_uploader."""
    nome = uploaded_file.name.lower()

    if nome.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(uploaded_file)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            return "[pypdf não instalado — execute: pip install pypdf]"

    if nome.endswith(".docx"):
        try:
            from docx import Document
            import io
            doc = Document(io.BytesIO(uploaded_file.read()))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return "[python-docx não instalado — execute: pip install python-docx]"

    # TXT e qualquer outro: lê como texto
    try:
        return uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        return uploaded_file.read().decode("latin-1")


def extrair_campos_de_texto(texto: str, llm) -> Dict:
    """
    Chama o LLM para extrair campos do briefing a partir de texto livre.
    Retorna dict compatível com st.session_state.form_values.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Você extrai informações de briefings de marketing. "
            "Analise o texto e retorne um JSON com os campos possíveis. "
            "Use strings vazias para campos não encontrados. "
            "Retorne APENAS o bloco JSON, sem texto adicional."
        )),
        ("human", (
            "Texto do briefing:\n{texto}\n\n"
            "Retorne JSON com estas chaves (use string vazia se não encontrar):\n"
            "nome_produto, produtor, preco (número), formato, descricao,\n"
            "demografia, problema_principal, transformacao_principal, objecoes_comuns (texto com \\n entre cada),\n"
            "diferencial_competitivo, tom_de_voz, gatilhos_mentais (vírgula-separados),\n"
            "tipo_lancamento, meta_campanha, canais (vírgula-separados),\n"
            "depoimentos (texto com \\n entre cada), metricas, autoridade_produtor"
        )),
    ])
    chain = prompt | llm
    result = chain.invoke({"texto": texto[:6000]})
    parsed = force_json(result)
    if "error" in parsed:
        return {}
    return parsed


# ── Carrossel de Instagram → normalização e ponte com o Pomelli ──────────────

_ALIAS_TEXTO  = ("texto_slide", "texto", "copy", "text")
_ALIAS_VISUAL = ("prompt_visual_pomelli", "prompt_visual", "visual")
_ALIAS_PAPEL  = ("papel", "funcao", "role")

_SEP = "\n\n" + "─" * 56 + "\n\n"


def clamp_slides(n: Any) -> int:
    """Normaliza o número de slides para a faixa 5–10 (default 7)."""
    try:
        return max(5, min(10, int(n)))
    except (TypeError, ValueError):
        return 7


def _primeiro(d: Dict, chaves) -> str:
    """Primeiro valor de texto não-vazio entre as chaves informadas."""
    for k in chaves:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _normalizar_hashtags(brutas: Any) -> list:
    if isinstance(brutas, str):
        brutas = [h for h in brutas.replace(",", " ").split() if h]
    if not isinstance(brutas, list):
        return []
    tags = []
    for h in brutas:
        if not isinstance(h, str) or not h.strip():
            continue
        h = h.strip()
        tags.append(h if h.startswith("#") else f"#{h}")
    return tags


def normalizar_carrossel(bruto: Any, num_slides: int) -> Dict:
    """
    Normaliza a saída do nó de carrossel para o contrato consumido pela UI.

    Tolera as variações que o LLM produz na prática: `slides` como dict,
    slides embrulhados em {"slide_N": {...}} e aliases de nome de campo.
    Excesso de slides é truncado; falta NÃO é preenchida — slide inventado
    por template é pior que slide a menos.
    """
    if not isinstance(bruto, dict):
        return {"error": "Saída do carrossel em formato inesperado",
                "raw_content": str(bruto)[:800]}
    if "error" in bruto:
        return bruto

    slides_brutos = bruto.get("slides", [])
    if isinstance(slides_brutos, dict):
        slides_brutos = list(slides_brutos.values())
    if not isinstance(slides_brutos, list):
        slides_brutos = []

    slides = []
    for item in slides_brutos:
        if not isinstance(item, dict):
            continue
        # aceita {"slide_1": {...}} além do dict direto
        if len(item) == 1:
            interno = next(iter(item.values()))
            if isinstance(interno, dict):
                item = interno

        texto = _primeiro(item, _ALIAS_TEXTO)
        if not texto:
            continue

        slides.append({
            "numero": len(slides) + 1,          # o LLM erra a numeração com frequência
            "papel": _primeiro(item, _ALIAS_PAPEL),
            "texto_slide": texto,
            "prompt_visual_pomelli": _primeiro(item, _ALIAS_VISUAL),
        })
        if len(slides) >= num_slides:
            break

    return {
        "estilo_visual_global": str(bruto.get("estilo_visual_global") or "").strip(),
        "legenda":              str(bruto.get("legenda") or bruto.get("caption") or "").strip(),
        "hashtags":             _normalizar_hashtags(bruto.get("hashtags")),
        "slides":               slides,
    }


def bloco_pomelli_slide(slide: Dict, total: int, estilo_global: str = "") -> str:
    """Bloco de um slide, pronto para colar no Google Pomelli."""
    papel = slide.get("papel", "")
    cabecalho = f"SLIDE {slide.get('numero', '?')}/{total}" + (f" — {papel}" if papel else "")
    visual = ", ".join(p for p in (estilo_global, slide.get("prompt_visual_pomelli", "")) if p)
    return (
        f"{cabecalho}\n\n"
        f"TEXTO (vai na imagem):\n{slide.get('texto_slide', '')}\n\n"
        f"VISUAL DIRECTION (paste into Pomelli):\n{visual}"
    )


def bloco_pomelli_completo(carrossel: Dict) -> str:
    """
    Carrossel inteiro em um único bloco. Abre pelo estilo visual global —
    o Pomelli precisa da identidade constante antes das variações, senão
    cada slide vira um post diferente.
    """
    slides = carrossel.get("slides", [])
    total  = len(slides)
    estilo = carrossel.get("estilo_visual_global", "")

    partes = [f"CARROSSEL DE INSTAGRAM — {total} slides"]
    if estilo:
        partes.append(f"ESTILO VISUAL GLOBAL (aplica a todos os slides):\n{estilo}")
    # o estilo global já foi declarado acima; não repetir em cada slide
    partes.extend(bloco_pomelli_slide(s, total) for s in slides)

    legenda = carrossel.get("legenda", "")
    if legenda:
        tags = " ".join(carrossel.get("hashtags", []))
        partes.append("LEGENDA DO POST (fora das imagens):\n" + legenda + (f"\n\n{tags}" if tags else ""))

    return _SEP.join(partes)
