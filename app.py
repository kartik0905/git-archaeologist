import streamlit as st
import os
from dotenv import load_dotenv
from chat import get_search_results 
from openai import OpenAI

st.set_page_config(page_title="Legacy Code Archaeologist", page_icon="🏛️")
load_dotenv()


os.environ["TOKENIZERS_PARALLELISM"] = "false"


with st.sidebar:
    st.title("The Archaeologist")
    st.markdown("""
    **Project:** `requests` Library
    **Database:** ChromaDB (Local)
    **Model:** GPT-4.1 nano
    """)
    if st.button("Clear Chat History"):
        st.session_state.messages = []


if "messages" not in st.session_state:
    st.session_state.messages = []


st.title("Chat with your Git History")
st.caption("Ask about commits, authors, and changes...")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if prompt := st.chat_input("Ex: Who updated the CI pipeline?"):

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)


    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("*Digging through history...*")

        try:
            context = get_search_results(prompt)
            
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            full_prompt = f"""
            You are a helpful Software Archaeologist. 
            Based ONLY on the commit history provided below, answer the user's question.
            Format your answer nicely with bullet points if needed.

            --- COMMIT HISTORY ---
            {context}
            
            --- USER QUESTION ---
            {prompt}
            """
            
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            answer = response.choices[0].message.content
            message_placeholder.markdown(answer)
            
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
        except Exception as e:
            message_placeholder.error(f"Error: {e}")