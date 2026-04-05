import streamlit as st
import pandas as pd
import plotly.express as px
from fpdf import FPDF

from auth import (
    init_db, create_user, verify_user,
    create_conversation, load_conversations, rename_conversation,
    delete_conversation, save_history_entry, load_history,
)
from agent.graph import build_graph

init_db()

st.set_page_config(page_title="Assistente de Dados", layout="wide")

st.markdown("""
<style>
:root {
    --color-layout-bg: #0D1117;
    --color-layout-surface: #161B22;
    --color-layout-border: #21262D;
    --color-layout-orange: #F26522;
    --color-layout-orange-light: #F9904A;
    --color-layout-text: #E6EDF3;
    --color-layout-muted: #8B949E;
}

.stApp { background-color: var(--color-layout-bg); color: var(--color-layout-text); }

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--color-layout-surface) !important;
    border-right: 1px solid var(--color-layout-border) !important;
}
section[data-testid="stSidebar"] * { color: var(--color-layout-text) !important; }

/* Botão nova conversa */
.btn-new-conv button {
    background-color: var(--color-layout-orange) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    width: 100%;
}
.btn-new-conv button:hover { background-color: var(--color-layout-orange-light) !important; }

/* Botões de conversa na sidebar */
.stButton > button {
    background: transparent !important;
    color: var(--color-layout-muted) !important;
    border: none !important;
    text-align: left !important;
    padding: 0.2rem 0.6rem !important;
    border-radius: 6px !important;
    font-size: 0.85rem !important;
    line-height: 1.4 !important;
    width: 100% !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* Reduz espaçamento entre linhas de conversa na sidebar */
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
    gap: 0 !important;
    margin-bottom: 0 !important;
    margin-top: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.2rem !important;
}
.stButton > button:hover {
    background-color: rgba(242,101,34,.1) !important;
    color: var(--color-layout-text) !important;
}

/* Botão ativo na sidebar */
.conv-active button {
    background-color: rgba(242,101,34,.15) !important;
    color: var(--color-layout-orange) !important;
    font-weight: 600 !important;
    border-left: 2px solid var(--color-layout-orange) !important;
}

/* Form submit */
.stFormSubmitButton > button {
    background-color: var(--color-layout-orange) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
.stFormSubmitButton > button:hover { background-color: var(--color-layout-orange-light) !important; }

/* Inputs */
input[type="text"], input[type="password"] {
    background-color: var(--color-layout-surface) !important;
    color: var(--color-layout-text) !important;
    border: 1px solid var(--color-layout-border) !important;
    border-radius: 6px !important;
}
input:focus {
    border-color: var(--color-layout-orange) !important;
    box-shadow: 0 0 0 2px rgba(242,101,34,.25) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--color-layout-border); }
.stTabs [data-baseweb="tab"] { color: var(--color-layout-muted); font-weight: 600; }
.stTabs [aria-selected="true"] {
    color: var(--color-layout-orange) !important;
    border-bottom: 2px solid var(--color-layout-orange) !important;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    background-color: var(--color-layout-surface) !important;
    border: 1px solid var(--color-layout-border) !important;
    border-radius: 12px !important;
    padding: 0.8rem 1rem !important;
    margin-bottom: 0.5rem !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: rgba(242,101,34,.07) !important;
    border-color: rgba(242,101,34,.2) !important;
}

/* Chat input */
[data-testid="stChatInput"] textarea {
    background-color: var(--color-layout-surface) !important;
    color: var(--color-layout-text) !important;
    border: 1px solid var(--color-layout-border) !important;
    border-radius: 10px !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--color-layout-orange) !important;
    box-shadow: 0 0 0 2px rgba(242,101,34,.2) !important;
}
[data-testid="stChatInput"] button {
    background-color: var(--color-layout-orange) !important;
    border-radius: 8px !important;
}

/* Expanders */
details {
    background-color: var(--color-layout-surface);
    border: 1px solid var(--color-layout-border) !important;
    border-radius: 8px;
    margin-top: 0.5rem;
}
summary { color: var(--color-layout-muted) !important; font-size: 0.82rem; }

/* Alertas */
.stSuccess  { background-color: rgba(35,134,54,.12) !important; border-left: 3px solid #2ea043 !important; border-radius: 6px !important; }
.stInfo     { background-color: rgba(242,101,34,.08) !important; border-left: 3px solid var(--color-layout-orange) !important; border-radius: 6px !important; }
.stError    { background-color: rgba(218,54,51,.12) !important; border-left: 3px solid #da3633 !important; border-radius: 6px !important; }

/* Download buttons */
.stDownloadButton > button {
    background-color: var(--color-layout-surface) !important;
    color: var(--color-layout-orange) !important;
    border: 1px solid var(--color-layout-orange) !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
}
.stDownloadButton > button:hover { background-color: rgba(242,101,34,.1) !important; }

/* Misc */
hr { border-color: var(--color-layout-border) !important; }
h1, h2, h3 { color: var(--color-layout-text) !important; font-weight: 700; }
.stCaption, small { color: var(--color-layout-muted) !important; }
.stDataFrame { border: 1px solid var(--color-layout-border); border-radius: 6px; }

/* Botão deletar conversa */
.btn-delete button {
    background: transparent !important;
    border: none !important;
    padding: 0.2rem 0.5rem !important;
    border-radius: 5px !important;
    min-width: unset !important;
    width: 100% !important;
    font-size: 0.8rem !important;
    line-height: 1 !important;
    color: transparent !important;
    transition: background-color 0.15s, color 0.15s !important;
    white-space: nowrap !important;
}
/* Mostrar ícone ao passar o mouse na linha da conversa */
div:has(> div > .btn-delete):hover .btn-delete button {
    color: #8B949E !important;
}
.btn-delete button:hover {
    background-color: rgba(218,54,51,.12) !important;
    color: #da3633 !important;
}

/* Painel de confirmação de exclusão */
.delete-confirm-panel {
    background: rgba(218,54,51,.08);
    border: 1px solid rgba(218,54,51,.3);
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    margin: 0.15rem 0 0.4rem;
}
.delete-confirm-panel p {
    color: #da3633 !important;
    font-size: 0.78rem !important;
    margin: 0 0 0.4rem !important;
    font-weight: 500;
}
.btn-cancel-delete button {
    background: transparent !important;
    color: #8B949E !important;
    border: 1px solid rgba(139,148,158,.35) !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
    padding: 0.2rem 0.4rem !important;
    width: 100% !important;
    transition: background-color 0.15s !important;
}
.btn-cancel-delete button:hover {
    background-color: rgba(139,148,158,.12) !important;
    color: var(--color-layout-text) !important;
}
.btn-confirm-delete button {
    background-color: #da3633 !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    padding: 0.2rem 0.4rem !important;
    width: 100% !important;
    transition: background-color 0.15s !important;
}
.btn-confirm-delete button:hover {
    background-color: #b52d2a !important;
}
</style>
""", unsafe_allow_html=True)

def df_to_pdf(df, answer: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Resultado da Consulta", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 8, _sanitize(answer))
    pdf.ln(4)

    col_width = pdf.epw / max(len(df.columns), 1)
    pdf.set_font("Helvetica", "B", 10)
    for col in df.columns:
        pdf.cell(col_width, 8, _sanitize(str(col)), border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(col_width, 8, _sanitize(str(val)), border=1)
        pdf.ln()

    return bytes(pdf.output())


def _sanitize(text: str) -> str:
    return text.replace("\u2022", "-").encode("latin-1", errors="replace").decode("latin-1")


def conversation_to_pdf(history: list, title: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, _sanitize(title), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, f"{len(history)} mensagens", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    for i, entry in enumerate(history, start=1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(242, 101, 34)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 7, _sanitize(f"  Pergunta {i}"), fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _sanitize(entry["question"]))
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(30, 30, 30)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 7, "  Resposta", fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _sanitize(entry["answer"]))
        pdf.ln(2)

        df = entry.get("df")
        if df is not None and not df.empty:
            col_count = len(df.columns)
            col_w = pdf.epw / max(col_count, 1)

            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(240, 240, 240)
            for col in df.columns:
                pdf.cell(col_w, 6, _sanitize(str(col))[:20], border=1, fill=True)
            pdf.ln()

            pdf.set_font("Helvetica", "", 8)
            for _, row in df.head(20).iterrows():
                for val in row:
                    pdf.cell(col_w, 6, _sanitize(str(val))[:20], border=1)
                pdf.ln()

            if len(df) > 20:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(120, 120, 120)
                pdf.cell(0, 6, f"  ... e mais {len(df) - 20} linhas", ln=True)
                pdf.set_text_color(0, 0, 0)

            pdf.ln(2)

        pdf.ln(4)

    return bytes(pdf.output())


def render_chart(df, chart):
    cols = df.columns
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]

    if chart == "bar":
        if len(num_cols) >= 1 and len(cat_cols) >= 2:
            st.plotly_chart(
                px.bar(df, x=cat_cols[0], y=num_cols[0], color=cat_cols[1], barmode="group"),
                use_container_width=True,
            )
        else:
            st.plotly_chart(px.bar(df, x=cols[0], y=cols[1]), use_container_width=True)
    elif chart == "line":
        if len(num_cols) >= 1 and len(cat_cols) >= 2:
            st.plotly_chart(
                px.line(df, x=cat_cols[0], y=num_cols[0], color=cat_cols[1]),
                use_container_width=True,
            )
        else:
            st.plotly_chart(px.line(df, x=cols[0], y=cols[1]), use_container_width=True)
    elif chart == "pie":
        st.plotly_chart(px.pie(df, names=cols[0], values=cols[1]), use_container_width=True)
    elif chart == "scatter":
        y_col = cols[2] if len(cols) >= 3 else cols[1]
        color_col = cols[2] if len(cols) >= 3 else None
        st.plotly_chart(px.scatter(df, x=cols[0], y=cols[1], color=color_col, size=y_col if pd.api.types.is_numeric_dtype(df[y_col]) else None), use_container_width=True)
    elif chart == "heatmap":
        pivot = df.pivot(index=cols[0], columns=cols[1], values=cols[2]) if len(cols) >= 3 else df
        st.plotly_chart(px.imshow(pivot, text_auto=True), use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)


def render_assistant_content(entry: dict, key_prefix: str) -> None:
    if entry.get("resolved") and entry["resolved"].lower() != entry["question"].lower():
        st.caption(f"Interpretado como: *{entry['resolved']}*")

    if entry.get("is_multi_step"):
        steps = entry.get("step_results") or []
        st.info(f"Agente multi-step · {len(steps)} queries executadas")

    st.markdown(entry["answer"])

    df = entry.get("df")
    if df is not None and not df.empty:
        render_chart(df, entry.get("chart"))

        col_csv, col_pdf = st.columns(2)
        with col_csv:
            st.download_button(
                "Baixar CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="resultado.csv",
                mime="text/csv",
                key=f"{key_prefix}_csv",
            )
        with col_pdf:
            st.download_button(
                "Baixar PDF",
                data=df_to_pdf(df, entry["answer"]),
                file_name="resultado.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_pdf",
            )

    if entry.get("is_multi_step") and entry.get("step_results"):
        with st.expander("Resultados intermediários"):
            for j, (desc, step_df) in enumerate(entry["step_results"]):
                st.markdown(f"**Passo {j + 1}:** {desc}")
                st.dataframe(step_df)

    with st.expander("Raciocínio do agente"):
        for step in entry.get("reasoning_steps", []):
            st.markdown(step)


for key, default in [
    ("user_id", None),
    ("username", None),
    ("conv_id", None),
    ("viewed_conv_id", None),
    ("history", []),
    ("pending_delete", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


if st.session_state.user_id is None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
            <div style='text-align:center;padding:2rem 0 1.5rem'>
                <span style='font-size:2rem;font-weight:800;color:#F26522;letter-spacing:-1px'>SEU</span>
                <span style='font-size:2rem;font-weight:300;color:#E6EDF3;letter-spacing:-1px'> · Assistente de Dados</span>
            </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Entrar", "Criar conta"])

        with tab_login:
            with st.form("form_login"):
                username = st.text_input("Usuário")
                password = st.text_input("Senha", type="password")
                submitted = st.form_submit_button("Entrar", use_container_width=True)

            if submitted:
                ok, uid = verify_user(username, password)
                if ok:
                    st.session_state.user_id = uid
                    st.session_state.username = username.strip()
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

        with tab_register:
            with st.form("form_register"):
                new_user = st.text_input("Usuário")
                new_pass = st.text_input("Senha", type="password")
                new_pass2 = st.text_input("Confirmar senha", type="password")
                submitted_reg = st.form_submit_button("Criar conta", use_container_width=True)

            if submitted_reg:
                if not new_user.strip():
                    st.error("Informe um nome de usuário.")
                elif new_pass != new_pass2:
                    st.error("As senhas não coincidem.")
                elif len(new_pass) < 6:
                    st.error("A senha deve ter ao menos 6 caracteres.")
                else:
                    ok, msg = create_user(new_user, new_pass)
                    if ok:
                        st.success(msg + " Acesse a aba Entrar.")
                    else:
                        st.error(msg)

    st.stop()

def _delete_if_empty(conv_id: int) -> None:
    if conv_id is None:
        return
    convs = load_conversations(st.session_state.user_id)
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if conv and conv["msg_count"] == 0:
        delete_conversation(conv_id, st.session_state.user_id)


def start_new_conversation():
    _delete_if_empty(st.session_state.conv_id)
    conv_id = create_conversation(st.session_state.user_id, "Nova conversa")
    st.session_state.conv_id = conv_id
    st.session_state.viewed_conv_id = conv_id
    st.session_state.history = []

def switch_to_conversation(conv_id: int):
    _delete_if_empty(st.session_state.conv_id)
    st.session_state.conv_id = conv_id
    st.session_state.viewed_conv_id = conv_id
    st.session_state.history = load_history(st.session_state.user_id, conv_id)

if st.session_state.conv_id is None:
    convs = load_conversations(st.session_state.user_id)
    for c in convs:
        if c["msg_count"] == 0:
            delete_conversation(c["id"], st.session_state.user_id)
    convs = [c for c in convs if c["msg_count"] > 0]
    if convs:
        most_recent = convs[0]
        st.session_state.conv_id = most_recent["id"]
        st.session_state.viewed_conv_id = most_recent["id"]
        st.session_state.history = load_history(st.session_state.user_id, most_recent["id"])
    else:
        start_new_conversation()

with st.sidebar:
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:800;color:#F26522;letter-spacing:-0.5px;"
        "padding:0.5rem 0 1rem'>Dados</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="btn-new-conv">', unsafe_allow_html=True)
    if st.button("+  Nova conversa", key="new_conv"):
        start_new_conversation()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin:0.8rem 0 0.4rem;font-size:0.72rem;color:#8B949E;text-transform:uppercase;letter-spacing:.05em'>Conversas</div>", unsafe_allow_html=True)

    convs = load_conversations(st.session_state.user_id)
    for conv in convs:
        is_active = conv["id"] == st.session_state.viewed_conv_id
        label = conv["title"]
        if len(label) > 26:
            label = label[:24] + "…"

        css_class = "conv-active" if is_active else ""
        col_conv, col_del = st.columns([5, 1])

        with col_conv:
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            if st.button(label, key=f"conv_{conv['id']}"):
                st.session_state.pending_delete = None
                switch_to_conversation(conv["id"])
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_del:
            st.markdown('<div class="btn-delete">', unsafe_allow_html=True)
            if st.button("×", key=f"del_{conv['id']}", help="Deletar conversa"):
                st.session_state.pending_delete = conv["id"]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.pending_delete == conv["id"]:
            st.markdown(
                '<div class="delete-confirm-panel">'
                '<p>Excluir esta conversa?</p>',
                unsafe_allow_html=True,
            )
            col_cancel, col_confirm = st.columns(2)
            with col_cancel:
                st.markdown('<div class="btn-cancel-delete">', unsafe_allow_html=True)
                if st.button("Cancelar", key=f"cancel_del_{conv['id']}"):
                    st.session_state.pending_delete = None
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with col_confirm:
                st.markdown('<div class="btn-confirm-delete">', unsafe_allow_html=True)
                if st.button("Excluir", key=f"confirm_del_{conv['id']}"):
                    delete_conversation(conv["id"], st.session_state.user_id)
                    st.session_state.pending_delete = None
                    if st.session_state.conv_id == conv["id"] or st.session_state.viewed_conv_id == conv["id"]:
                        remaining = [c for c in convs if c["id"] != conv["id"]]
                        if remaining:
                            st.session_state.conv_id = remaining[0]["id"]
                            st.session_state.viewed_conv_id = remaining[0]["id"]
                            st.session_state.history = load_history(st.session_state.user_id, remaining[0]["id"])
                        else:
                            start_new_conversation()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if is_active:
            st.caption(f"{conv['msg_count']} mensagens")

    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
    st.divider()

    st.caption(f"👤 {st.session_state.username}")
    if st.button("Sair", key="logout"):
        for k in ["user_id", "username", "conv_id", "viewed_conv_id", "history"]:
            st.session_state[k] = None if k != "history" else []
        st.rerun()


convs_map = {c["id"]: c for c in load_conversations(st.session_state.user_id)}
current_conv = convs_map.get(st.session_state.viewed_conv_id, {})
conv_title = current_conv.get("title", "Conversa")

header_col, export_col = st.columns([6, 1])

with header_col:
    st.markdown(
        f"<h2 style='color:#F26522;letter-spacing:-0.5px;margin-bottom:0'>{conv_title}</h2>",
        unsafe_allow_html=True,
    )

with export_col:
    if st.session_state.history:
        st.markdown("<div style='padding-top:0.4rem'>", unsafe_allow_html=True)
        st.download_button(
            "Exportar PDF",
            data=conversation_to_pdf(st.session_state.history, conv_title),
            file_name=f"{conv_title[:40]}.pdf",
            mime="application/pdf",
            key="export_conv_pdf",
            help="Exportar toda a conversa como PDF",
        )
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom:1rem'></div>", unsafe_allow_html=True)

history = st.session_state.history
for i, entry in enumerate(history):
    with st.chat_message("user"):
        st.markdown(entry["question"])
    with st.chat_message("assistant"):
        render_assistant_content(entry, key_prefix=f"msg_{i}")

question = st.chat_input("Faça sua pergunta sobre os dados…")

if question:
    conv_id = st.session_state.conv_id

    if not history:
        title = question if len(question) <= 40 else question[:38] + "…"
        rename_conversation(conv_id, title)

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analisando…"):
            graph = build_graph()
            result = graph.invoke({
                "question": question,
                "resolved_question": question,
                "reasoning_steps": [],
                "retries": 0,
                "is_multi_step": False,
                "query_plan": [],
                "current_step": 0,
                "step_results": [],
                "username": st.session_state.username,
                "conversation_history": [
                    {"question": h["question"], "answer": h["answer"]}
                    for h in history
                ],
            })

        answer = result["final_answer"]
        resolved = result.get("resolved_question", question)
        df = result.get("sql_result")
        chart = result.get("chart_type")
        is_multi = result.get("is_multi_step", False)
        step_results = result.get("step_results") or []

        entry = {
            "question": question,
            "resolved": resolved,
            "answer": answer,
            "df": df,
            "chart": chart,
            "is_multi_step": is_multi,
            "step_results": step_results,
            "reasoning_steps": result["reasoning_steps"],
        }
        render_assistant_content(entry, key_prefix="current")

    save_history_entry(
        user_id=st.session_state.user_id,
        conversation_id=conv_id,
        question=question,
        resolved_question=resolved,
        answer=answer,
        chart_type=chart,
        df=df,
        is_multi_step=is_multi,
        step_results=step_results,
        reasoning_steps=result["reasoning_steps"],
    )
    st.session_state.history.append(entry)
    st.rerun()
