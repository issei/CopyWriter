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
