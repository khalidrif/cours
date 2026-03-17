import streamlit as st
import time

st.title("🧪 Simulation XRP Coinbase")

# Variables test
mid = 1.02
usdc = 100.0
xrp = 50.0

st.metric("💵 USDC libres", f"{usdc:.2f}$")
st.metric("💠 XRP libres", f"{xrp:.2f}")
st.metric("📊 Prix XRP", f"{mid:.5f}")
st.caption(f"Dernière mise à jour : {time.strftime('%H:%M:%S')}")
