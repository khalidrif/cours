import streamlit as st
import ccxt
import json
import os
import time
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# === 1. GESTION DU STOCKAGE PERMANENT (RAILWAY VOLUME) ===
# On vérifie si /data existe (Volume Railway), sinon on utilise le dossier local
DATA_DIR = "/data" if os.path.exists("/data") else os.getcwd()

CONFIG_FILE = os.path.join(DATA_DIR, "bots_config.json")
HISTORY_FILE = os.path.join(DATA_DIR, "trading_history.json")

# === 2. CONFIGURATION STREAMLIT ===
st.set_page_config(page_title="⚡ XRP Sniper Pro", layout="wide")
symbol = "XRP/USDC"
# Rafraîchissement auto toutes les 20 secondes
st_autorefresh(interval=20000, key="refresh_app")

# Verrou pour éviter les doubles achats simultanés
if "achat_en_cours" not in st.session_state:
    st.session_state.achat_en_cours = False

# === 3. FONCTIONS DE SAUVEGARDE ===
def save_bots():
    with open(CONFIG_FILE, "w") as f:
        json.dump(st.session_state.bots, f, indent=2)

def load_bots():
    if not os.path.exists(CONFIG_FILE): return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except: return {}

def save_to_history(action, price, qty, gain=0):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except: history = []
    
    history.append({
        "date": time.strftime('%Y-%m-%d %H:%M:%S'),
        "action": action,
        "prix": price,
        "quantite": qty,
        "gain": round(gain, 4)
    })
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# === 4. CONNEXION COINBASE (SÉCURISÉE VIA VARIABLES) ===
@st.cache_resource
def get_exchange():
    api_key = os.getenv("CB_API_KEY")
    api_secret = os.getenv("CB_API_SECRET")
    
    if not api_key or not api_secret:
        return None

    return ccxt.coinbaseadvanced({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True
    })

exchange = get_exchange()

# === 5. INITIALISATION DES DONNÉES ===
if "bots" not in st.session_state:
    st.session_state.bots = load_bots()

if "logs" not in st.session_state:
    st.session_state.logs = []

def log(msg):
    st.session_state.logs.append(f"{time.strftime('%H:%M:%S')} | {msg}")
    if len(st.session_state.logs) > 30: st.session_state.logs.pop(0)

# === 6. RÉCUPÉRATION PRIX ET SOLDES ===
mid, usdc, xrp = 0.0, 0.0, 0.0
if exchange:
    try:
        ticker = exchange.fetch_ticker(symbol)
        mid = (ticker['bid'] + ticker['ask']) / 2
        
        balances = exchange.fetch_balance()
        usdc = float(balances['free'].get('USDC', 0))
        xrp = float(balances['free'].get('XRP', 0))
    except Exception as e:
        log(f"⚠️ Erreur API : {e}")

# === 7. INTERFACE PRINCIPALE ===
st.title("🚀 XRP Sniper Pro – Coinbase")

if not exchange:
    st.warning("⚠️ Clés API manquantes dans l'onglet Variables de Railway (CB_API_KEY & CB_API_SECRET)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("💵 USDC", f"{usdc:.2f}$")
c2.metric("💠 XRP", f"{xrp:.4f}")
c3.metric("📊 Prix XRP", f"{mid:.5f}$" if mid > 0 else "---")
c4.metric("💰 Portefeuille", f"{(usdc + (xrp * mid)):.2f}$")

# === 8. LOGIQUE DCA / SNIPER ===
if exchange and mid > 0:
    for i, b in st.session_state.bots.items():
        if not b.get("actif"): continue

        # --- CONDITION ACHAT ---
        if b["etape"] == "ACHAT" and mid <= b["p_achat"]:
            if usdc >= b["mise"] and not st.session_state.achat_en_cours:
                st.session_state.achat_en_cours = True
                try:
                    qty = round(b["mise"] / mid, 2)
                    exchange.create_market_buy_order(symbol, qty)
                    b["etape"] = "VENTE"
                    save_bots()
                    save_to_history("ACHAT", mid, qty)
                    log(f"✅ Bot {i} : Achat effectué à {mid}")
                except Exception as e: log(f"❌ Erreur Achat Bot {i}: {e}")
                finally: st.session_state.achat_en_cours = False

        # --- CONDITION VENTE ---
        elif b["etape"] == "VENTE" and mid >= b["p_vente"]:
            if xrp > 0 and not st.session_state.achat_en_cours:
                st.session_state.achat_en_cours = True
                try:
                    qty_sell = round(xrp, 2)
                    exchange.create_market_sell_order(symbol, qty_sell)
                    gain = (mid - b["p_achat"]) * qty_sell
                    b["gain_net"] = b.get("gain_net", 0) + gain
                    b["cycles"] = b.get("cycles", 0) + 1
                    b["etape"] = "ACHAT"
                    save_bots()
                    save_to_history("VENTE", mid, qty_sell, gain)
                    log(f"💰 Bot {i} : Vente effectuée (+{gain:.2f}$)")
                except Exception as e: log(f"❌ Erreur Vente Bot {i}: {e}")
                finally: st.session_state.achat_en_cours = False

# === 9. GESTION DES BOTS (UI) ===
st.divider()
with st.expander("➕ Ajouter un nouveau Bot Sniper"):
    col_a, col_v, col_m = st.columns(3)
    pa = col_a.number_input("Prix Achat", value=mid if mid > 0 else 0.50, format="%.5f")
    pv = col_v.number_input("Prix Vente", value=pa*1.02, format="%.5f")
    ms = col_m.number_input("Mise ($)", value=10.0)
    if st.button("Lancer ce Bot"):
        new_id = max(st.session_state.bots.keys() or [0]) + 1
        st.session_state.bots[new_id] = {
            "id": new_id, "p_achat": pa, "p_vente": pv, "mise": ms,
            "gain_net": 0.0, "cycles": 0, "actif": True, "etape": "ACHAT"
        }
        save_bots()
        st.rerun()

# Affichage des onglets
t1, t2, t3 = st.tabs(["🤖 Mes Bots", "📈 Historique", "📝 Logs"])

with t1:
    for i, b in sorted(st.session_state.bots.items()):
        col_info, col_btn = st.columns([4, 1])
        status = "🟢" if b["actif"] else "🔴"
        col_info.write(f"{status} **Bot {i}** | {b['etape']} | Achat: {b['p_achat']} | Vente: {b['p_vente']} | Gain: {b['gain_net']:.2f}$")
        if col_btn.button("Supprimer", key=f"del_{i}"):
            del st.session_state.bots[i]
            save_bots()
            st.rerun()

with t2:
    if os.path.exists(HISTORY_FILE):
        st.dataframe(pd.read_json(HISTORY_FILE).sort_index(ascending=False), use_container_width=True)

with t3:
    st.text("\n".join(reversed(st.session_state.logs)))
