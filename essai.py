import ccxt

exchange = ccxt.coinbaseadvanced({
    "apiKey": "TA_API_KEY",
    "secret": "TON_SECRET",
    "enableRateLimit": True
})

markets = exchange.load_markets()
print("✅ Connexion réussie. Nombre de paires disponibles :", len(markets))
print("Exemple :", list(markets.keys())[:5])
