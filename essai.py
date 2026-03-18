import streamlit as st
from coinbase.rest import RESTClient

st.set_page_config(page_title="Coinbase Portfolio", page_icon="💰")
st.title("📊 Mon Portefeuille Coinbase")

# Connexion via les secrets Streamlit
try:
    client = RESTClient(
        api_key=st.secrets["CB_API_KEY"], 
        api_secret=st.secrets["CB_API_SECRET"]
    )

    if st.button('Actualiser les soldes'):
        accounts = client.get_accounts()
        
        # Initialisation des variables
        balances = {"XRP": "0.00", "USDC": "0.00"}
        
        # Extraction des données
        for acc in accounts['accounts']:
            currency = acc['currency']
            if currency in balances:
                balances[currency] = acc['available_balance']['value']

        # Affichage en colonnes
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Solde XRP", value=f"{float(balances['XRP']):,.2f} XRP")
        with col2:
            st.metric(label="Solde USDC", value=f"{float(balances['USDC']):,.2f} $")

except Exception as e:
    st.error(f"Erreur : {e}")
    st.info("Vérifiez vos 'Secrets' dans les paramètres Streamlit Cloud.")
