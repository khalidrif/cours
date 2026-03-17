
mid = 1.0
bot = {"p_achat": 0.95, "p_vente": 1.05, "etape": "ACHAT"}

print("Prix actuel :", mid)

if bot["etape"] == "ACHAT" and mid <= bot["p_achat"]:
    print("🟢 Achat déclenché")
    bot["etape"] = "VENTE"

mid = 1.07
if bot["etape"] == "VENTE" and mid >= bot["p_vente"]:
    print("🔴 Vente déclenchée, gain pris !")
    bot["etape"] = "ACHAT"

