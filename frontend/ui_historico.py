"""Histórico de lançamentos: visualização, carregamento e exclusão."""
import json
import streamlit as st

import backend.historico as hist


def render_historico() -> None:
    """Renderiza a seção de histórico de lançamentos com opções de carregar e deletar."""
    with st.expander("📚 Histórico de Lançamentos", expanded=False):
        lancamentos = hist.listar(limit=30)

        if not lancamentos:
            st.info("Nenhum lançamento salvo ainda. Gere sua primeira copy acima!")
            return

        st.caption(f"{len(lancamentos)} lançamento(s) salvos. Clique em **Carregar** para re-usar um briefing.")

        for row in lancamentos:
            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                st.write(
                    f"**#{row['id']}** — {row['nome_produto']} *(por {row['produtor']})* "
                    f"| {row['tipo_lancamento']} | 🗓 {row['criado_em']} "
                    f"| 🔄 {row['tentativas']} refinamento(s)"
                )
            with c2:
                if st.button("📂 Carregar", key=f"load_{row['id']}"):
                    dados = hist.carregar(row["id"])
                    if dados:
                        # Extrai campos planos do briefing para preencher o form
                        bl = dados["briefing"].get("briefing_lancamento", {})
                        inf = bl.get("infoproduto", {})
                        pub = bl.get("publico_alvo", {})
                        pos = bl.get("posicionamento", {})
                        est = bl.get("estrategia_lancamento", {})
                        ps  = bl.get("prova_social", {})
                        datas = est.get("datas_chave", {})

                        st.session_state.form_values = {
                            "nome_produto":          inf.get("nome", ""),
                            "produtor":              inf.get("produtor", ""),
                            "preco":                 inf.get("preco", 0.0),
                            "formato":               inf.get("formato", ""),
                            "descricao":             inf.get("descricao", ""),
                            "demografia":            pub.get("demografia", ""),
                            "problema_principal":    pub.get("problema_principal", ""),
                            "transformacao_principal": pub.get("transformacao_principal", ""),
                            "objecoes_comuns":       "\n".join(pub.get("objecoes_comuns", [])),
                            "diferencial_competitivo": pos.get("diferencial_competitivo", ""),
                            "tom_de_voz":            pos.get("tom_de_voz", ""),
                            "gatilhos_mentais":      ", ".join(pos.get("gatilhos_mentais", [])),
                            "tipo_lancamento":       est.get("tipo_lancamento", ""),
                            "meta_campanha":         est.get("meta_campanha", ""),
                            "ini_campanha":          datas.get("inicio_campanha", ""),
                            "abert_carrinho":        datas.get("abertura_carrinho", ""),
                            "fech_carrinho":         datas.get("fechamento_carrinho", ""),
                            "canais":                ", ".join(est.get("canais", [])),
                            "autoridade_produtor":   ps.get("autoridade_produtor", ""),
                            "depoimentos":           ps.get("depoimentos", ""),
                            "metricas":              ps.get("metricas", ""),
                        }
                        st.session_state.final_copy = dados["copy"]
                        st.success(f"✅ Briefing #{row['id']} carregado!")
                        st.rerun()

            with c3:
                if st.button("🗑️ Deletar", key=f"del_{row['id']}"):
                    hist.deletar(row["id"])
                    st.warning(f"Lançamento #{row['id']} removido.")
                    st.rerun()
