import streamlit as st

mid = 1.02
usdc = 50.0
xrp = 20.0

st.metric("Prix XRP", f"{mid:.5f}")
st.metric("Solde USDC", f"{usdc:.2f}$")
st.metric("Solde XRP", f"{xrp:.2f}")
