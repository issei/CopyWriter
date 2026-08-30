"""Exibição dos resultados: uma aba por canal, com download individual."""
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import streamlit as st

from backend.parsers import bloco_pomelli_completo, bloco_pomelli_slide
from backend.carousel_jobs import friendly_node_label

ABA_EMAIL     = "📧 Email Marketing"
ABA_STORIES   = "📱 Instagram Stories"
ABA_CARROSSEL = "🎠 Carrossel"
ABA_VSL       = "📺 YouTube (VSL)"
ABA_ADS       = "📢 Meta Ads"
ABA_JSON      = "📄 JSON Completo"


def render_results(final_copy: Dict) -> None:
    """Renderiza as abas de output com download individual por canal."""
    st.header("📋 Resultados Finais da Copy")

    # ── Erro de parsing → expander de debug ──────────────────────────────────
    if "error" in final_copy:
        st.error(f"Erro no processamento da IA: {final_copy['error']}")
        with st.expander("🔍 Ver conteúdo bruto para debug"):
            st.code(final_copy.get("raw_content", "sem conteúdo"), language="text")
        return

    # Acesso nominal às abas: a do carrossel é condicional e entra no meio da
    # lista, o que quebraria o desempacotamento posicional.
    nomes = [ABA_EMAIL, ABA_STORIES]
    if final_copy.get("carrossel"):
        nomes.append(ABA_CARROSSEL)
    nomes += [ABA_VSL, ABA_ADS, ABA_JSON]
    tabs = dict(zip(nomes, st.tabs(nomes)))

    # ── Email ─────────────────────────────────────────────────────────────────
    with tabs[ABA_EMAIL]:
        email = final_copy.get("email", {})
        subject = email.get("subject", email.get("assunto", ""))
        body    = email.get("body",    email.get("corpo",   ""))

        st.subheader(f"✉️ {subject}" if subject else "✉️ Email Marketing")
        st.text_area("Corpo", body, height=420, disabled=True, key="email_body_view")

        txt = f"ASSUNTO:\n{subject}\n\n{'─'*60}\n\n{body}"
        st.download_button("⬇️ Baixar Email (.txt)", data=txt,
                           file_name="email_marketing.txt", mime="text/plain")

    # ── Stories ───────────────────────────────────────────────────────────────
    with tabs[ABA_STORIES]:
        slides = final_copy.get("stories", [])
        # normaliza: aceita lista de dicts com ou sem chave slide_N
        if isinstance(slides, dict):
            slides = list(slides.values())

        if not slides:
            st.info("Nenhum slide gerado.")
        else:
            txt_lines = []
            cols_per_row = 2
            for i in range(0, len(slides), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(slides):
                        break
                    slide = slides[idx]
                    if not isinstance(slide, dict):
                        continue
                    # suporta {slide_N: {visual, copy}} e {visual, copy} direto
                    inner_key = f"slide_{idx+1}"
                    data = slide.get(inner_key, slide)
                    visual = data.get("visual", data.get("imagem", ""))
                    copy   = data.get("copy",   data.get("texto",  ""))
                    with col:
                        with st.container(border=True):
                            st.caption(f"**Slide {idx+1}**")
                            st.info(f"🎬 {visual}")
                            st.write(copy)
                    txt_lines.append(f"SLIDE {idx+1}\nVisual: {visual}\nTexto: {copy}\n")

            st.download_button(
                "⬇️ Baixar Stories (.txt)",
                data="\n".join(txt_lines),
                file_name="instagram_stories.txt",
                mime="text/plain",
            )

    # ── Carrossel (ponte manual com o Google Pomelli) ─────────────────────────
    if ABA_CARROSSEL in tabs:
        with tabs[ABA_CARROSSEL]:
            _render_carrossel(final_copy["carrossel"])

    # ── VSL ───────────────────────────────────────────────────────────────────
    with tabs[ABA_VSL]:
        vsl = final_copy.get("vsl", {})
        blocks = vsl.get("script", []) if isinstance(vsl, dict) else []

        if not blocks:
            st.info("Nenhum script VSL gerado.")
        else:
            vsl_lines = []
            for b in blocks:
                tm  = b.get("time", "")
                seg = b.get("segment", "")
                cp  = b.get("copy", "")
                with st.expander(f"⏱️ **{tm}** — {seg}"):
                    st.write(cp)
                vsl_lines.append(f"[{tm}] {seg}\n{cp}\n")

            st.download_button(
                "⬇️ Baixar Script VSL (.txt)",
                data="\n".join(vsl_lines),
                file_name="script_vsl.txt",
                mime="text/plain",
            )

    # ── Meta Ads ──────────────────────────────────────────────────────────────
    with tabs[ABA_ADS]:
        ads = final_copy.get("ads", [])
        if isinstance(ads, dict):
            ads = [ads]

        if not ads:
            st.info("Nenhum anúncio gerado.")
        else:
            ads_lines = []
            for i, ad in enumerate(ads):
                angulo   = ad.get("angulo", f"Variação {i+1}")
                headline = ad.get("headline", "")
                primary  = ad.get("primary_text", ad.get("texto_principal", ""))
                link     = ad.get("link_description", ad.get("descricao_link", ""))

                with st.container(border=True):
                    st.markdown(f"#### 🎯 {angulo}")
                    c1, c2, c3 = st.columns([2, 4, 2])
                    with c1:
                        st.metric("Headline", "")
                        st.write(headline)
                    with c2:
                        st.metric("Primary Text", "")
                        st.write(primary)
                    with c3:
                        st.metric("Link Description", "")
                        st.write(link)

                ads_lines.append(
                    f"VARIAÇÃO {i+1} — {angulo}\n"
                    f"Headline: {headline}\nTexto: {primary}\nLink: {link}\n"
                )

            st.download_button(
                "⬇️ Baixar Anúncios (.txt)",
                data="\n".join(ads_lines),
                file_name="meta_ads.txt",
                mime="text/plain",
            )

    # ── JSON Completo ─────────────────────────────────────────────────────────
    with tabs[ABA_JSON]:
        st.json(final_copy)
        st.download_button(
            "⬇️ Baixar JSON Completo",
            data=json.dumps(final_copy, ensure_ascii=False, indent=2),
            file_name="copy_completa.json",
            mime="application/json",
        )


# ── Carrossel ─────────────────────────────────────────────────────────────────

def _render_carrossel(carrossel: Dict) -> None:
    """
    Cards em grade, cada um com o bloco pronto para colar no Google Pomelli.

    A cópia usa `st.code`, que já traz o ícone nativo de copiar: `st.button`
    roda no servidor e não alcança a área de transferência do navegador, e
    `pyperclip` escreveria no clipboard da máquina que hospeda o app.
    """
    if not isinstance(carrossel, dict) or "error" in carrossel:
        erro = carrossel.get("error", "formato inesperado") if isinstance(carrossel, dict) else "formato inesperado"
        st.error(f"Erro ao gerar o carrossel: {erro}")
        with st.expander("🔍 Ver conteúdo bruto para debug"):
            bruto = carrossel.get("raw_content", "sem conteúdo") if isinstance(carrossel, dict) else str(carrossel)
            st.code(bruto, language="text")
        return

    slides = carrossel.get("slides", [])
    if not slides:
        st.info("Nenhum slide de carrossel gerado.")
        return

    estilo = carrossel.get("estilo_visual_global", "")
    total  = len(slides)

    st.subheader(f"🎠 Carrossel de {total} slides")
    if estilo:
        st.info(f"🎨 **Estilo visual global** (repete em todos os slides): `{estilo}`")

    with st.expander("📋 Copiar TODAS as diretrizes para o Google Pomelli", expanded=False):
        st.caption(
            "Use o ícone de copiar no canto do bloco. O estilo global vem primeiro — "
            "o Pomelli precisa da identidade constante antes das variações de cada slide."
        )
        st.code(bloco_pomelli_completo(carrossel), language="text")

    st.divider()

    # ── Grade de cards ────────────────────────────────────────────────────────
    cols_per_row = 2
    for i in range(0, total, cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= total:
                break
            slide = slides[idx]
            with col:
                with st.container(border=True):
                    papel = slide.get("papel", "")
                    st.caption(f"**Slide {slide.get('numero', idx+1)}/{total}**"
                               + (f" · {papel}" if papel else ""))
                    st.write(slide.get("texto_slide", ""))
                    visual = slide.get("prompt_visual_pomelli", "")
                    if visual:
                        st.info(f"🎬 `{visual}`")
                    with st.popover("📋 Copiar diretrizes para o Pomelli",
                                    use_container_width=True):
                        st.code(bloco_pomelli_slide(slide, total, estilo), language="text")

    # ── Legenda do post ───────────────────────────────────────────────────────
    legenda = carrossel.get("legenda", "")
    hashtags = " ".join(carrossel.get("hashtags", []))
    if legenda:
        st.divider()
        st.markdown("#### 📝 Legenda do post (fora das imagens)")
        st.code(legenda + (f"\n\n{hashtags}" if hashtags else ""), language="text")

    st.download_button(
        "⬇️ Baixar Carrossel (.txt)",
        data=bloco_pomelli_completo(carrossel),
        file_name="carrossel_pomelli.txt",
        mime="text/plain",
        key="dl_carrossel",
    )


# ── render_carousel_job_status — 3 estados de renderização ───────────────────

def render_carousel_job_status(job: dict, thread_id: str) -> None:
    """
    Renderiza o status de um job de carrossel com 3 estados (spec v2 §6.2):
    1. Em andamento (queued/running): progresso + polling
    2. Aguardando aprovação humana (awaiting_approval): tela de aprovação
    3. Concluído (completed): grade de cards com miniaturas
    + Estado failed: mensagem segura + retry
    """
    status = job.get("status", "")
    short_id = thread_id[:8]

    with st.container(border=True):
        # ── 1. Em andamento ────────────────────────────────────────────────────
        if status in ("queued", "running"):
            current_node = job.get("current_node")
            label        = friendly_node_label(current_node)
            st.markdown(f"**🔄 Carrossel Visual `{short_id}...`** — {label}")
            st.progress(0.5 if status == "running" else 0.1, text=label)
            st.caption("Atualizando em 2 segundos...")
            time.sleep(2)
            st.rerun()

        # ── 2. Aguardando aprovação humana ─────────────────────────────────────
        elif status == "awaiting_approval":
            st.markdown(f"**⏸️ Carrossel `{short_id}...` — Aguardando sua aprovação**")
            reason = job.get("progress_summary", {}).get("human_review_reason", "")
            if reason:
                st.warning(f"Motivo da pausa: {reason}")

            progress = job.get("progress_summary") or {}
            if progress.get("carousel_plan"):
                with st.expander("📋 Plano Editorial Atual"):
                    st.json(progress["carousel_plan"])

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Aprovar", key=f"approve_{thread_id}", type="primary"):
                    st.info("Aprovação registrada — retomando o grafo...")
                    # Futuro: retomar via checkpoint com mesmo thread_id

            with col2:
                revision_text = st.text_input("Instruções de revisão", key=f"rev_text_{thread_id}")
                if st.button("🔄 Solicitar Revisão", key=f"revise_{thread_id}"):
                    st.info(f"Revisão solicitada: {revision_text}")

            with col3:
                if st.button("❌ Cancelar", key=f"cancel_{thread_id}"):
                    st.warning("Job cancelado.")

        # ── 3. Concluído ───────────────────────────────────────────────────────
        elif status == "completed":
            st.markdown(f"**✅ Carrossel `{short_id}...` — Concluído**")

            progress    = job.get("progress_summary") or {}
            manifest_p  = job.get("manifest_path")

            # Tenta carregar o manifest
            manifest = None
            if manifest_p and os.path.exists(manifest_p):
                try:
                    with open(manifest_p, encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception:
                    pass

            if manifest:
                slides_info = manifest.get("slides", [])
                total = len(slides_info)
                score = manifest.get("quality_score")

                if score is not None:
                    st.metric("Score de qualidade", f"{score:.0f}/100")

                st.markdown(f"**{total} slides gerados**")

                # Grade de cards com miniaturas
                cols_per_row = 3
                for i in range(0, total, cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, col in enumerate(cols):
                        idx = i + j
                        if idx >= total:
                            break
                        slide_info = slides_info[idx]
                        sid        = slide_info.get("slide_id", idx + 1)
                        fpath      = slide_info.get("file_path")
                        degraded   = slide_info.get("degraded", False)

                        with col:
                            with st.container(border=True):
                                caption = f"Slide {sid}"
                                if degraded:
                                    caption += " ⚠️"
                                st.caption(caption)
                                if fpath and os.path.exists(fpath):
                                    st.image(fpath, use_container_width=True)
                                    if degraded:
                                        st.caption("⚠️ Composição tipográfica (sem asset visual)")
                                else:
                                    st.info("🖼️ Slide não encontrado em disco")

                # Downloads
                if manifest_p:
                    with open(manifest_p, encoding="utf-8") as f:
                        manifest_json = f.read()
                    st.download_button(
                        "⬇️ Baixar manifest.json",
                        data=manifest_json,
                        file_name=f"manifest_{short_id}.json",
                        mime="application/json",
                        key=f"dl_manifest_{thread_id}",
                    )
            else:
                st.info("Carrossel concluído — manifest não encontrado em disco.")

        # ── Failed ────────────────────────────────────────────────────────────
        elif status == "failed":
            error_msg = job.get("error_message", "Erro desconhecido")
            st.error(f"**❌ Carrossel `{short_id}...` — Falhou**")
            st.warning(f"Mensagem: {error_msg}")
            if st.button("🔄 Tentar novamente", key=f"retry_{thread_id}"):
                st.info("Para tentar novamente, gere uma nova copy com carrossel.")

        else:
            st.caption(f"Job `{short_id}...` — status: {status}")

