import streamlit as st

st.title("🔍 Test Streamlit")
name = st.text_input("Quel est ton nom ?")
if st.button("Dire bonjour"):
    st.write(f"Salut {name} 👋")

