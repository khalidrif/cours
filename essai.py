import streamlit as st
import ccxt
import json
import os
import time
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# === CONFIGURATION DES CHEMINS (PERMANENT) ===
# On utilise le dossier /data lié au Volume Railway
DATA_DIR = "/data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CONFIG_FILE = os.path.join(DATA_DIR, "bots_config.json")
HISTORY_FILE = os.path.join(DATA_DIR, "trading_history.json")

# === CONFIGURATION STREAMLIT ===
st.set_page_config(page_title="⚡ XRP Sniper Pro (Coinbase)", layout="centered")
symbol = "XRP/USDC"
st_autorefresh(interval=20000, key="refresh_app")

# === VERROU GLOBAL ===
@st.cache_resource
def obtenir_verrou_serveur():
    return {"achat_en_cours": False}

verrou_global = obtenir_verrou_serveur()

# === LOGS & ÉTAT ===
if "logs" not in st.session_state:
    st.session_state.logs = []

def log(msg): 
    st.session_state.logs.append(f"{time.strftime('%H:%M:%S')} | {msg}")
    if len(st.session_state.logs) > 50: st.session_state.logs.pop(0)

# === SAUVEGARDE / CHARGEMENT (PERMANENT) ===
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
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    
    entry = {
        "date": time.strftime('%Y-%m-%d %H:%M:%S'),
        "action": action,
        "prix": price,
        "quantite": qty,
        "gain": gain
    }
    history.append(entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# === CONNEXION COINBASE (SÉCURISÉE) ===
@st.cache_resource
def get_exchange():
    # Récupération depuis l'onglet Variables de Railway
    api_key = os.getenv("CB_API_KEY")
    api_secret = os.getenv("CB_API_SECRET")
    
    if not api_key or not api_secret:
        st.error("⚠️ Clés API manquantes dans l'onglet Variables de Railway !")
        return None

    return ccxt.coinbaseadvanced({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True
    })

exchange = get_exchange()

# === INITIALISATION ===
if "bots" not in st.session_state:
    st.session_state.bots = load_bots()

# === PRIX LIVE ET SOLDES (ANTI-CRASH) ===
mid = 0.0
bid = 0.0
ask = 0.0
usdc = 0.0
xrp = 0.0

if exchange:
    try:
        ticker = exchange.fetch_ticker(symbol)
        bid = ticker.get("bid", 0.0)
        ask = ticker.get("ask", 0.0)
        mid = (bid + ask) / 2 if bid and ask else 0.0
    except Exception as e:
        log(f"⚠️ Erreur prix : {e}")

    try:
        balances = exchange.fetch_balance()
        usdc = float(balances["free"].get("USDC", 0))
        xrp = float(balances["free"].get("XRP", 0))
    except Exception as e:
        log(f"⚠️ Erreur solde : {e}")

wallet_total = usdc + (xrp * mid)

# === INTERFACE ===
st.title("🚀 XRP Sniper Pro – Coinbase")
col1, col2, col3, col4 = st.columns(4)
col1.metric("💵 USDC", f"{usdc:.2f}$")
col2.metric("💠 XRP", f"{xrp:.2f}")
col3.metric("📊 Prix XRP", f"{mid:.5f}" if mid > 0 else "---")
col4.metric("💰 Total", f"{wallet_total:.2f}$")

total_gain = sum(b.get("gain_net", 0.0) for b in st.session_state.bots.values())
st.success(f"💰 Gains cumulés : {total_gain:.2f}$")

# === AJOUT BOT ===
with st.expander("➕ Créer un nouveau Bot"):
    c1, c2, c3 = st.columns(3)
    p_achat_new = c1.number_input("Prix Achat", value=mid if mid > 0 else 0.50, format="%.5f")
    p_vente_new = c2.number_input("Prix Vente", value=(mid*1.01) if mid > 0 else 0.51, format="%.5f")
    mise_new = c3.number_input("Mise ($)", value=10.0)

    if st.button("Lancer le Bot"):
        next_id = max(st.session_state.bots.keys()) + 1 if st.session_state.bots else 1
        st.session_state.bots[next_id] = {
            "id": next_id, "p_achat": p_achat_new, "p_vente": p_vente_new,
            "mise": mise_new, "gain_net": 0.0, "cycles": 0, "actif": True, "etape": "ACHAT"
        }
        save_bots()
        st.rerun()

# === LOGIQUE DE TRADING ===
if exchange:
    for i, b in st.session_state.bots.items():
        if not b.get("actif"): continue

        # ACHAT
        if b["etape"] == "ACHAT" and 0 < mid <= b["p_achat"]:
            if not verrou_global["achat_en_cours"] and usdc >= b["mise"]:
                verrou_global["achat_en_cours"] = True
                try:
                    qty = round(b["mise"] / mid, 2)
                    exchange.create_market_buy_order(symbol, qty)
                    b["etape"] = "VENTE"
                    save_bots()
                    save_to_history("ACHAT", mid, qty)
                    log(f"✅ Bot {i} : Achat XRP effectué")
                except Exception as e: log(f"❌ Erreur Achat {i} : {e}")
                finally: verrou_global["achat_en_cours"] = False

        # VENTE
        elif b["etape"] == "VENTE" and mid >= b["p_vente"]:
            if not verrou_global["achat_en_cours"]:
                verrou_global["achat_en_cours"] = True
                try:
                    qty_sell = round(xrp, 2) # On vend tout le XRP disponible
                    exchange.create_market_sell_order(symbol, qty_sell)
                    gain = (mid - b["p_achat"]) * qty_sell
                    b["gain_net"] += gain
                    b["mise"] += gain
                    b["cycles"] += 1
                    b["etape"] = "ACHAT"
                    save_bots()
                    save_to_history("VENTE", mid, qty_sell, gain)
                    log(f"💰 Bot {i} : Vente XRP effectuée (+{gain:.2f}$)")
                except Exception as e: log(f"❌ Erreur Vente {i} : {e}")
                finally: verrou_global["achat_en_cours"] = False

# === AFFICHAGE DES BOTS ET HISTORIQUE ===
tab1, tab2, tab3 = st.tabs(["🤖 Mes Bots", "📜 Journal", "📈 Historique"])

with tab1:
    for i, b in sorted(st.session_state.bots.items()):
        c1, c2, c3 = st.columns([4, 1, 1])
        c1.write(f"**Bot {i}** | {b['etape']} | Mise: {b['mise']:.2f}$ | Gains: {b['gain_net']:.2f}$")
        if c2.button("🛑/🚀", key=f"t_{i}"):
            b["actif"] = not b["actif"]; save_bots(); st.rerun()
        if c3.button("🗑️", key=f"d_{i}"):
            del st.session_state.bots[i]; save_bots(); st.rerun()

with tab2:
    if st.session_state.logs:
        st.text("\n".join(reversed(st.session_state.logs)))

with tab3:
    if os.path.exists(HISTORY_FILE):
        df_hist = pd.read_json(HISTORY_FILE)
        st.dataframe(df_hist.sort_values(by="date", ascending=False), use_container_width=True)
    else:
        st.info("Aucun historique pour le moment.")
