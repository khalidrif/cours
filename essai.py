import streamlit as st
import ccxt
import json
import os
import time
from streamlit_autorefresh import st_autorefresh
mport requests

def get_xrp_price():
    # URL de l'API publique de Coinbase pour le XRP
    url = "https://api.coinbase.com"
    
    try:
        response = requests.get(url)
        # Vérification si la requête a réussi
        response.raise_for_status()
        
        data = response.json()
        prix = data['data']['amount']
        devise = data['data']['currency']
        
        print(f"Prix actuel du XRP sur Coinbase : {prix} {devise}")
        
    except Exception as e:
        print(f"Erreur lors de la récupération du prix : {e}")

if __name__ == "__main__":
    get_xrp_price()
