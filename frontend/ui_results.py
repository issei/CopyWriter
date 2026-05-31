"""Exibição dos resultados: 5 abas com download por canal."""
import json
from typing import Dict

import streamlit as st


def render_results(final_copy: Dict) -> None:
    """Renderiza as abas de output com download individual por canal."""
    st.header("📋 Resultados Finais da Copy")

    # ── Erro de parsing → expander de debug ──────────────────────────────────
    if "error" in final_copy:
        st.error(f"Erro no processamento da IA: {final_copy['error']}")
        with st.expander("🔍 Ver conteúdo bruto para debug"):
            st.code(final_copy.get("raw_content", "sem conteúdo"), language="text")
        return

    t1, t2, t3, t4, t5 = st.tabs([
        "📧 Email Marketing",
        "📱 Instagram Stories",
        "📺 YouTube (VSL)",
        "📢 Meta Ads",
        "📄 JSON Completo",
    ])

    # ── Email ─────────────────────────────────────────────────────────────────
    with t1:
        email = final_copy.get("email", {})
        subject = email.get("subject", email.get("assunto", ""))
        body    = email.get("body",    email.get("corpo",   ""))

        st.subheader(f"✉️ {subject}" if subject else "✉️ Email Marketing")
        st.text_area("Corpo", body, height=420, disabled=True, key="email_body_view")

        txt = f"ASSUNTO:\n{subject}\n\n{'─'*60}\n\n{body}"
        st.download_button("⬇️ Baixar Email (.txt)", data=txt,
                           file_name="email_marketing.txt", mime="text/plain")

    # ── Stories ───────────────────────────────────────────────────────────────
    with t2:
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

    # ── VSL ───────────────────────────────────────────────────────────────────
    with t3:
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
    with t4:
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
    with t5:
        st.json(final_copy)
        st.download_button(
            "⬇️ Baixar JSON Completo",
            data=json.dumps(final_copy, ensure_ascii=False, indent=2),
            file_name="copy_completa.json",
            mime="application/json",
        )
