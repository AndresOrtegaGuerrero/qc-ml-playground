import streamlit as st
from rag.answer import answer


st.set_page_config(page_title="ORCA Assistant", page_icon="⚛️")
st.title("ORCA Assistant")
st.caption("Ask questions about the ORCA quantum chemistry program using the manual content.")


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.markdown(f"**{source['heading']}** (p. {source['page']})")
                    st.code(source["text"][:800])


if question := st.chat_input("Ask a question about ORCA"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Reading the manual ..."):
            answer_text, hits = answer(question)
            st.markdown(answer_text)
            st.session_state.messages.append({"role": "assistant", "content": answer_text, "sources": hits})
            st.rerun()
