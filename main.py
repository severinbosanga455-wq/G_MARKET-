from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB = "gmarket.db"
dernier_recu = {}

def get_db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL,
            prix REAL NOT NULL,
            prix_achat REAL DEFAULT 0,
            stock INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produit TEXT NOT NULL,
            quantite INTEGER NOT NULL,
            total REAL NOT NULL,
            benefice REAL DEFAULT 0,
            paiement TEXT NOT NULL,
            telephone TEXT,
            date TEXT NOT NULL
        )
    """)
    conn.commit(); conn.close()

init_db()
panier = []

HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>G-MARKET V2</title>
<style>
body{font-family:Arial;background:#f2f2f2;margin:0;padding:10px}
.header{background:#1a7a3a;color:white;padding:15px;border-radius:10px;text-align:center}
.card{background:white;padding:15px;margin:10px 0;border-radius:10px;box-shadow:0 2px 5px #ccc}
button{background:#1a7a3a;color:white;border:none;padding:10px 15px;border-radius:8px;font-weight:bold;cursor:pointer}
.btn-orange{background:#ff8c00}.btn-rouge{background:#d32f2f}
input,select{padding:10px;width:95%;margin:5px 0;border:1px solid #ccc;border-radius:8px}
.total{font-size:20px;font-weight:bold;color:#1a7a3a;text-align:center}
.benef{font-size:18px;font-weight:bold;color:#ff8c00;text-align:center}
.paiement label{display:block;background:#f9f9f9;padding:12px;margin:5px 0;border-radius:8px;border:1px solid #ddd}
</style></head><body>
<div class="header">
<h1>🛒 G-MARKET V2</h1><p>Paiement Marchand - Kinshasa</p>
<p>Total vendu aujourd'hui : <b>{{ total_jour }} CDF</b></p>
<p>💰 Bénéfice aujourd'hui : <b>{{ benef_jour }} CDF</b></p>
</div>

<div class="card">
<h3>➕ Ajouter un produit</h3>
<form action="/ajouter" method="post">
<input name="nom" placeholder="Nom ex: Riz" required>
<input name="prix_achat" type="number" placeholder="Prix d'achat ex: 4000" required>
<input name="prix" type="number" placeholder="Prix de vente ex: 5000" required>
<input name="stock" type="number" placeholder="Stock ex: 100" required>
<button type="submit">Ajouter au magasin</button>
</form>
</div>

<div class="card"><h3>🏪 Boutique</h3>
{% for p in produits %}
<div style="display:flex;justify-content:space-between;align-items:center">
<div><b>{{ p['nom'] }}</b><br>Vente: {{ p['prix'] }} CDF | Achat: {{ p['prix_achat'] }} CDF | Bénéfice/unité: <b style="color:#ff8c00">{{ p['prix']-p['prix_achat'] }} CDF</b><br>Stock: {{ p['stock'] }}</div>
<form action="/ajouter_panier/{{ p['id'] }}" method="post">
<input type="number" name="qte" value="1" min="1" max="{{ p['stock'] }}" style="width:60px">
<button type="submit">+ Panier</button></form></div><hr>
{% else %}<p>Aucun produit.</p>{% endfor %}</div>

<div class="card"><h3>🧺 Panier - {{ panier|length }} article(s)</h3>
{% for item in panier %}<p>{{ item['qte'] }} x {{ item['nom'] }} = <b>{{ item['total'] }} CDF</b> <small>(Bénéf: {{ item['benefice'] }} CDF)</small></p>{% endfor %}
<p class="total">TOTAL À PAYER : {{ total_panier }} CDF</p>
<p class="benef">BÉNÉFICE SUR CE PANIER : {{ benef_panier }} CDF</p>
<a href="/vider"><button class="btn-rouge">Vider panier</button></a></div>

{% if panier %}
<div class="card" style="border:2px solid #1a7a3a"><h3>💳 PAIEMENT MARCHAND</h3>
<form action="/payer" method="post">
<div class="paiement">
<label><input type="radio" name="paiement" value="Espèces" checked> 💵 Espèces</label>
<label><input type="radio" name="paiement" value="Orange Money"> 🟠 Orange Money</label>
<label><input type="radio" name="paiement" value="Airtel Money"> 🔴 Airtel Money</label>
<label><input type="radio" name="paiement" value="M-Pesa"> 🟢 M-Pesa</label>
</div>
<input name="telephone" placeholder="Numéro du client ex: 081...">
<button class="btn-orange" style="width:100%;font-size:18px;padding:15px" type="submit">✅ CONFIRMER PAIEMENT - {{ total_panier }} CDF</button>
</form></div>{% endif %}

<div class="card"><h3>📜 Historique des ventes</h3>
{% for v in ventes %}
<p><b>{{ v['produit'] }}</b> - {{ v['quantite'] }} x - {{ v['total'] }} CDF - Bénéf: {{ v['benefice'] }} CDF - {{ v['paiement'] }} - {{ v['telephone'] or '' }}<br><small>{{ v['date'] }}</small></p><hr>
{% endfor %}</div>
</body></html>
"""

RECU_HTML = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reçu G-MARKET</title>
<style>body{font-family:Arial;background:#f2f2f2;padding:10px}.recu{background:white;max-width:400px;margin:auto;padding:20px;border-radius:10px;text-align:center}table{width:100%;text-align:left}td{padding:5px 0}button{background:#1a7a3a;color:white;border:none;padding:12px;width:100%;border-radius:8px;font-weight:bold;margin-top:10px}</style>
</head><body><div class="recu">
<h2>🛒 G-MARKET</h2><p>Kinshasa - Reçu de Paiement</p><p>{{ date }}<br>Client: {{ tel }}<br>Paiement: {{ paiement }}</p><hr>
<table>{% for i in items %}<tr><td>{{ i['qte'] }} x {{ i['nom'] }}</td><td style="text-align:right">{{ i['total'] }} CDF</td></tr>{% endfor %}</table><hr>
<h3>TOTAL PAYÉ : {{ total }} CDF</h3><p>Merci pour votre achat !<br>À très bientôt chez G-MARKET</p>
<button onclick="window.print()">🖨️ IMPRIMER / PARTAGER</button>
<a href="/"><button style="background:#ff8c00">⬅️ Retour à la boutique</button></a>
</div></body></html>
"""

@app.route("/")
def index():
    conn = get_db()
    produits = conn.execute("SELECT * FROM produits ORDER BY nom").fetchall()
    ventes = conn.execute("SELECT * FROM ventes ORDER BY id DESC LIMIT 20").fetchall()
    aujourd = datetime.now().strftime("%Y-%m-%d")
    r = conn.execute("SELECT SUM(total), SUM(benefice) FROM ventes WHERE date LIKE ?", (aujourd+"%",)).fetchone()
    total_jour = r[0] if r[0] else 0
    benef_jour = r[1] if r[1] else 0
    conn.close()
    total_panier = sum(i['total'] for i in panier)
    benef_panier = sum(i['benefice'] for i in panier)
    return render_template_string(HTML, produits=produits, ventes=ventes, panier=panier, total_panier=total_panier, benef_panier=benef_panier, total_jour=total_jour, benef_jour=benef_jour)

@app.route("/ajouter", methods=["POST"])
def ajouter():
    nom = request.form['nom'].strip().title()
    prix = float(request.form['prix']); prix_achat = float(request.form['prix_achat']); stock = int(request.form['stock'])
    try:
        conn = get_db()
        conn.execute("INSERT INTO produits (nom,prix,prix_achat,stock) VALUES (?,?,?,?)", (nom,prix,prix_achat,stock))
        conn.commit(); conn.close()
    except: pass
    return redirect("/")

@app.route("/ajouter_panier/<int:pid>", methods=["POST"])
def ajouter_panier(pid):
    qte = int(request.form['qte'])
    conn = get_db(); p = conn.execute("SELECT * FROM produits WHERE id=?", (pid,)).fetchone(); conn.close()
    if p and qte <= p['stock']:
        benef = (p['prix'] - p['prix_achat']) * qte
        panier.append({"nom": p['nom'], "id": p['id'], "qte": qte, "prix": p['prix'], "total": p['prix']*qte, "benefice": benef})
    return redirect("/")

@app.route("/vider")
def vider():
    panier.clear(); return redirect("/")

@app.route("/payer", methods=["POST"])
def payer():
    global dernier_recu
    paiement = request.form['paiement']; tel = request.form.get('telephone','')
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = sum(i['total'] for i in panier)
    dernier_recu = {"items": list(panier), "total": total, "paiement": paiement, "tel": tel, "date": date_now}
    conn = get_db()
    for item in panier:
        conn.execute("UPDATE produits SET stock = stock - ? WHERE id=?", (item['qte'], item['id']))
        conn.execute("INSERT INTO ventes (produit,quantite,total,benefice,paiement,telephone,date) VALUES (?,?,?,?,?,?,?)",
                     (item['nom'], item['qte'], item['total'], item['benefice'], paiement, tel, date_now))
    conn.commit(); conn.close()
    panier.clear()
    return redirect("/recu")

@app.route("/recu")
def recu():
    if not dernier_recu: return redirect("/")
    return render_template_string(RECU_HTML, items=dernier_recu['items'], total=dernier_recu['total'], paiement=dernier_recu['paiement'], tel=dernier_recu['tel'] or "Client", date=dernier_recu['date'])
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)