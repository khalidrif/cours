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
META_FILE = "meta.json"
LOG_FILE = "logs.txt"
LOCK_FILE = "order_lock.txt"   # 🔒 Fichier de verrou global persistant
st_autorefresh(interval=20000, key="refresh_app")

# === VERROU GLOBAL STREAMLIT ===
@st.cache_resource
def obtenir_verrou_serveur():
    return {"achat_en_cours": False}
verrou_global = obtenir_verrou_serveur()

# === VERROU PERSISTANT SUR DISQUE ===
def lock_active():
    """Renvoie True si un achat est déjà en cours"""
    return os.path.exists(LOCK_FILE)

def activate_lock():
    """Créé un fichier temporaire pour bloquer les doublons"""
    with open(LOCK_FILE, "w") as f:
        f.write(str(time.time()))

def release_lock():
    """Supprime le fichier quand le processus est terminé"""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# === LOGS INTELLIGENTS ===
def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return f.read().splitlines()[-500:]
    except:
        return []

def log(msg):
    """Ajoute une entrée au journal seulement si changement réel"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    new_line = f"{timestamp} | {msg}"
    if "logs" not in st.session_state:
        st.session_state.logs = []
    last_entry = st.session_state.logs[-1] if st.session_state.logs else ""
    if last_entry.split("|")[-1].strip() != msg.strip():
        st.session_state.logs.append(new_line)
        if len(st.session_state.logs) > 500:
            st.session_state.logs.pop(0)
        # Écrit sur disque
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.logs))
        except Exception as e:
            print(f"Erreur sauvegarde {LOG_FILE} : {e}")

# === INITIALISATION LOGS ===
if "logs" not in st.session_state:
    st.session_state.logs = load_logs()
if not st.session_state.logs:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.logs.append(f"{now} | 🚀 Application Coinbase démarrée.")
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(st.session_state.logs))

# === SAUVEGARDE / CHARGEMENT JSON ===
def save_bots():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.bots, f, indent=2)
    except Exception as e:
        log(f"⚠️ Erreur sauvegarde bots : {e}")

def load_bots():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except:
        return {}

def save_meta(data: dict):
    try:
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log(
            f"💾 Sauvegarde globale – XRP vente :{data['xrp_en_vente']} | "
            f"Gains :{data['total_gain']}$ | Portefeuille :{data['wallet_total']}$"
        )
    except Exception as e:
        log(f"⚠️ Erreur sauvegarde meta : {e}")

def load_meta():
    if not os.path.exists(META_FILE):
        return None
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

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
    b.setdefault("mise_initiale", b.get("mise", 0.0))

# === META ===
meta_data = load_meta()

# === PRIX LIVE ET SOLDES ===
try:
    ticker = exchange.fetch_ticker(symbol)
    bid, ask = ticker["bid"], ticker["ask"]
    mid = (bid + ask) / 2
except Exception as e:
    bid = ask = mid = 0.0
    log(f"⚠️ Erreur prix : {e}")

try:
    balances = exchange.fetch_balance()
    usdc = float(balances["free"].get("USDC", 0))
    xrp = float(balances["free"].get("XRP", 0))
except:
    if meta_data:
        usdc = meta_data.get("wallet_total", 0)
        xrp = 0.0
    else:
        usdc = xrp = 0.0

wallet_total = usdc + (xrp * mid)

# === TOTAL XRP EN VENTE ===
xrp_en_vente = sum(
    round(b["mise"] / b["p_achat"], 4)
    for b in st.session_state.bots.values()
    if b.get("etape") == "VENTE" and b.get("actif", True)
)

# === EN-TÊTE ===
st.title("🚀 XRP Sniper Pro – Coinbase")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💵 USDC libres", f"{usdc:.2f}$")
col2.metric("💠 XRP libres", f"{xrp:.2f}")
col3.metric("📊 Prix XRP", f"{mid:.5f}")
col4.metric("💰 Total (USDC)", f"{wallet_total:.2f}$")
col5.metric("📦 XRP en vente (bots)", f"{xrp_en_vente:.2f}")
st.caption(f"Dernière mise à jour : {time.strftime('%H:%M:%S')}")
st.divider()

# === TOTAL GAINS ===
total_gain = sum(b["gain_net"] for b in st.session_state.bots.values())
st.success(f"💰 Gains cumulés : {total_gain:.2f}$")
st.divider()

save_meta({
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "total_gain": round(total_gain, 2),
    "xrp_en_vente": round(xrp_en_vente, 2),
    "wallet_total": round(wallet_total, 2)
})

# === AJOUT D’UN BOT ===
st.subheader("➕ Ajouter un bot")
c1, c2, c3 = st.columns(3)
p_achat_new = c1.number_input("Prix Achat", value=1.0, step=0.00001, format="%.5f")
p_vente_new = c2.number_input("Prix Vente", value=1.01, step=0.00001, format="%.5f")
mise_new = c3.number_input("Mise ($)", value=10.0, step=0.1)

if st.button("✅ Créer le bot"):
    next_id = max(st.session_state.bots.keys()) + 1 if st.session_state.bots else 1
    st.session_state.bots[next_id] = {
        "id": next_id,
        "p_achat": p_achat_new,
        "p_vente": p_vente_new,
        "mise": mise_new,
        "mise_initiale": mise_new,
        "gain_net": 0.0,
        "cycles": 0,
        "actif": True,
        "etape": "ACHAT"
    }
    save_bots()
    log(f"🆕 Bot {next_id} ajouté : Achat {p_achat_new} / Vente {p_vente_new}")
    st.rerun()

# === LOGIQUE TRADING (avec verrou anti multi-achat) ===
for i, b in st.session_state.bots.items():
    if not b.get("actif"):
        continue

    qty_precision = 2

    # ACHAT sécurisé
    if b["etape"] == "ACHAT" and mid > 0 and mid <= b["p_achat"]:
        if not verrou_global["achat_en_cours"] and not lock_active() and usdc >= b["mise"]:
            verrou_global["achat_en_cours"] = True
            activate_lock()
            try:
                qty = round(b["mise"] / b["p_achat"], qty_precision)
                exchange.create_limit_buy_order(symbol, qty, b["p_achat"])
                log(f"✅ Bot {i} : Achat UNIQUE {qty} XRP @ {b['p_achat']:.5f}")
                b["etape"] = "VENTE"
                save_bots()
            except Exception as e:
                log(f"❌ Erreur Achat {i} : {e}")
            finally:
                release_lock()
                verrou_global["achat_en_cours"] = False

    # VENTE
    elif b["etape"] == "VENTE" and mid >= b["p_vente"]:
        if not verrou_global["achat_en_cours"] and not lock_active():
            verrou_global["achat_en_cours"] = True
            activate_lock()
            try:
                qty_sell = round(b["mise"] / b["p_achat"], qty_precision)
                exchange.create_limit_sell_order(symbol, qty_sell, b["p_vente"])
                gain = (b["p_vente"] - b["p_achat"]) * qty_sell
                log(f"💰 Bot {i} : Vente {qty_sell} XRP @ {b['p_vente']:.5f} (+{gain:.2f}$)")
                b["gain_net"] += gain
                b["mise"] += gain
                b["cycles"] += 1
                b["etape"] = "ACHAT"
                save_bots()
            except Exception as e:
                log(f"❌ Erreur Vente {i} : {e}")
            finally:
                release_lock()
                verrou_global["achat_en_cours"] = False

save_bots()

# === AFFICHAGE DES BOTS ===
st.subheader("📊 Mes bots actifs")
for i, b in sorted(st.session_state.bots.items()):
    actif = b.get("actif", True)
    couleur = "⚫️" if not actif else "🟢"
    if actif and mid <= b["p_achat"]:
        couleur = "🟡"
    elif actif and mid >= b["p_vente"]:
        couleur = "🔴"
    qty_xrp = b["mise"] / b["p_achat"]
    mise_init = b.get("mise_initiale", b["mise"])
    gain_boule = b["mise"] - mise_init
    croissance = (gain_boule / mise_init * 100) if mise_init else 0

    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.info(
            f"{couleur} **Bot {i}** | Achat {b['p_achat']:.5f} | Vente {b['p_vente']:.5f} | "
            f"Mise :{b['mise']:.2f}$ (+{gain_boule:.2f}$ / {croissance:+.2f}%) | "
            f"Qte :{qty_xrp:.2f} XRP | Gain :{b['gain_net']:.2f}$ | "
            f"Cycles :{b['cycles']} | Étape :{b['etape']}"
        )
    with col2:
        if st.button("🛑" if actif else "🚀", key=f"t_{i}"):
            b["actif"] = not actif
            save_bots()
            log(f"🔁 Bot {i} {'désactivé' if actif else 'activé'}")
            st.rerun()
    with col3:
        if st.button("🗑️", key=f"d_{i}"):
            del st.session_state.bots[i]
            save_bots()
            log(f"🗑️ Bot {i} supprimé")
            st.rerun()

# === JOURNAL ===
st.divider()
st.subheader("📜 Journal complet")
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        st.download_button(
            label="📥 Télécharger le log complet",
            data=f.read(),
            file_name="logs.txt",
            mime="text/plain"
        )

if st.session_state.logs:
    st.text_area(
        "Derniers évènements",
        "\n".join(reversed(st.session_state.logs[-200:])),
        height=220
    )
else:
    st.info("Aucune activité pour le moment.")

# === PRIX LIVE ===
st.divider()
st.subheader("💹 Prix en temps réel Coinbase")
c1, c2, c3 = st.columns(3)
c1.metric("Bid", f"{bid:.5f}")
c2.metric("Ask", f"{ask:.5f}")
c3.metric("Mid", f"{mid:.5f}")
