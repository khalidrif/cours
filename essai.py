import streamlit as st
import ccxt
import json
import os
import time
from streamlit_autorefresh import st_autorefresh

import streamlit as st
from coinbase.rest import RESTClient

st.title("Mon Solde XRP")
   accounts = client.get_accounts()
    
    # Recherche du XRP
    xrp_balance = next((acc['available_balance']['value'] for acc in accounts['accounts'] if acc['currency'] == 'XRP'), "0.00")
    
    # Affichage géant du solde
    st.metric(label="XRP disponible", value=f"{xrp_balance} XRP")

except Exception as e:
    st.error(f"Erreur : {e}")
