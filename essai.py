import streamlit as st
import ccxt
import json
import os
import time
from streamlit_autorefresh import st_autorefresh

# === CONFIGURATION ===
st.set_page_config(page_title="⚡ XRP Sniper Pro (Coinbase)", layout="centered")
symbol = "XRP/USDC"
CONFIG_FILE = "bots_config.json"
st_autorefresh(interval=20000, key="refresh_app")

# === VERROU GLOBAL ===
@st.cache_resource
def obtenir_verrou_serveur():
    return {"achat_en_cours": False}

verrou_global = obtenir_verrou_serveur()

# === LOGS & ÉTAT ===
if "logs" not in st.session_state:
    st.session_state.logs = []

if "achat_en_cours" not in st.session_state:
    st.session_state.achat_en_cours = False

def log(msg): 
    st.session_state.logs.append(f"{time.strftime('%H:%M:%S')} | {msg}")
    if len(st.session_state.logs) > 50: st.session_state.logs.pop(0)

# === SAUVEGARDE / CHARGEMENT JSON ===
def save_bots():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(st.session_state.bots, f, indent=2)
    except Exception as e:
        log(f"⚠️ Erreur sauvegarde JSON : {e}")

def load_bots():
    if not os.path.exists(CONFIG_FILE): return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except: return {}

# === CONNEXION COINBASE ===
@st.cache_resource
def get_exchange():
    return ccxt.coinbaseadvanced({
        "apiKey": st.secrets["COINBASE_API_KEY"],
        "secret": st.secrets["COINBASE_API_SECRET"],
        "enableRateLimit": True
    })
exchange = get_exchange()

# === INITIALISATION DES BOTS ===
if "bots" not in st.session_state:
    st.session_state.bots = load_bots()
for b in st.session_state.bots.values():
    b.setdefault("actif", True)
    b.setdefault("etape", "ACHAT")
    b.setdefault("gain_net", 0.0)
    b.setdefault("cycles", 0)

# === PRIX LIVE ET SOLDES ===
try:
    ticker = exchange.fetch_ticker(symbol)
    bid, ask = ticker["bid"], ticker["ask"]
    mid = (bid + ask) / 2
except Exception as e:
    mid = 0.0
    log(f"⚠️ Erreur prix : {e}")

try:
    balances = exchange.fetch_balance()
    usdc = float(balances["free"].get("USDC", 0))
    xrp = float(balances["free"].get("XRP", 0))
except:
    usdc = xrp = 0.0

wallet_total = usdc + (xrp * mid)

# === EN‑TÊTE ===
st.title("🚀 XRP Sniper Pro – Coinbase")
col1, col2, col3, col4 = st.columns(4)
col1.metric("💵 USDC libres", f"{usdc:.2f}$")
col2.metric("💠 XRP libres", f"{xrp:.2f}")
col3.metric("📊 Prix XRP", f"{mid:.5f}")
col4.metric("💰 Total (USDC)", f"{wallet_total:.2f}$")
st.divider()
# === TOTAL DES GAINS ===
total_gain = sum(b["gain_net"] for b in st.session_state.bots.values())
st.success(f"💰 Gains cumulés de tous les bots : {total_gain:.2f}$")
st.divider()

# === AJOUT D’UN BOT ===
st.subheader("➕ Ajouter un bot")
c1, c2, c3 = st.columns(3)
p_achat_new = c1.number_input("Prix Achat", value=1.0, step=0.00001, format="%.5f")
p_vente_new = c2.number_input("Prix Vente", value=1.01, step=0.00001, format="%.5f")
mise_new = c3.number_input("Mise ($)", value=10.0, step=0.1)

if st.button("✅ Créer le bot"):
    next_id = max(st.session_state.bots.keys()) + 1 if st.session_state.bots else 1
    st.session_state.bots[next_id] = {
        "id": next_id, "p_achat": p_achat_new, "p_vente": p_vente_new,
        "mise": mise_new, "gain_net": 0.0, "cycles": 0, "actif": True, "etape": "ACHAT"
    }
    save_bots(); st.rerun()

# === LOGIQUE TRADING ===
for i, b in st.session_state.bots.items():
    if not b.get("actif"): continue
    qty_precision = 2 

    # ACHAT
    if b["etape"] == "ACHAT" and mid > 0 and mid <= b["p_achat"]:
        if not verrou_global["achat_en_cours"] and usdc >= b["mise"]:
            verrou_global["achat_en_cours"] = True
            try:
                qty = round(b["mise"] / b["p_achat"], qty_precision)
                exchange.create_limit_buy_order(symbol, qty, b["p_achat"])
                log(f"✅ Bot {i} : Achat envoyé")
                b["etape"] = "VENTE"
                save_bots()
            except Exception as e: log(f"❌ Erreur Achat {i} : {e}")
            finally: verrou_global["achat_en_cours"] = False

    # VENTE
    elif b["etape"] == "VENTE" and mid >= b["p_vente"]:
        if not verrou_global["achat_en_cours"]:
            verrou_global["achat_en_cours"] = True
            try:
                qty_sell = round(b["mise"] / b["p_achat"], qty_precision)
                exchange.create_limit_sell_order(symbol, qty_sell, b["p_vente"])
                gain = (b["p_vente"] - b["p_achat"]) * qty_sell
                log(f"💰 Bot {i} : Vente @ {b['p_vente']:.5f} (+{gain:.2f}$)")
                
                # --- EFFET BOULE DE NEIGE ICI ---
                b["gain_net"] += gain
                b["mise"] += gain  # On rajoute le gain à la mise pour le prochain achat
                # -------------------------------
                
                b["cycles"] += 1
                b["etape"] = "ACHAT"
                save_bots()
            except Exception as e: log(f"❌ Erreur Vente {i} : {e}")
            finally: verrou_global["achat_en_cours"] = False

# === AFFICHAGE DES BOTS ===
st.subheader("📊 Mes bots actifs")
for i, b in sorted(st.session_state.bots.items()):
    actif = b.get("actif", True)
    couleur = "⚫️" if not actif else "🟢"
    if actif and mid <= b["p_achat"]: couleur = "🟡"
    elif actif and mid >= b["p_vente"]: couleur = "🔴"

    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.info(
            f"{couleur} **Bot {i}** | Achat {b['p_achat']:.5f} | Vente {b['p_vente']:.5f} | "
            f"Mise :{b['mise']:.2f}$ | Gain :{b['gain_net']:.2f}$ | Cycles :{b['cycles']} | Étape :{b['etape']}"
        )
    with col2:
        if st.button("🛑" if actif else "🚀", key=f"t_{i}"):
            b["actif"] = not actif; save_bots(); st.rerun()
    with col3:
        if st.button("🗑️", key=f"d_{i}"):
            del st.session_state.bots[i]; save_bots(); st.rerun()

st.divider()
st.subheader("📜 Journal complet")
if st.session_state.logs:
    st.text_area("Derniers évènements", "\n".join(reversed(st.session_state.logs[-200:])), height=220)
else:
    st.info("Aucune activité pour le moment.")

st.divider()
st.subheader("💹 Prix en temps réel Kraken")
c1,c2,c3=st.columns(3)
c1.metric("Bid", f"{bid:.5f}")
c2.metric("Ask", f"{ask:.5f}")
c3.metric("Mid", f"{mid:.5f}")

