import os
import sys
from datetime import date, timedelta
from xml.etree.ElementTree import Element, SubElement, ElementTree

import requests


# ============================================================
# CONFIGURATION
# ============================================================

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN")

if not BROWSERLESS_TOKEN:
    print("ERREUR : la variable BROWSERLESS_TOKEN est absente.")
    sys.exit(1)


# ============================================================
# CONSTRUCTION AUTOMATIQUE DE L'URL FFTA
# ============================================================

# Date de fin = aujourd'hui
end_date = date.today()

# Date de début = 12 mois avant
# On utilise 365 jours pour éviter les problèmes avec le 29 février.
start_date = end_date - timedelta(days=365)

FFTA_URL = (
    "https://www.ffta.fr/competitions"
    "?search="
    f"&start={start_date.isoformat()}"
    f"&end={end_date.isoformat()}"
    "&dep%5B%5D=58"
    "&discipline=103"
    "&univers=299"
    "&inter=All"
    "&sort_by=start"
    "&sort_order=DESC"
)

print("URL FFTA utilisée :")
print(FFTA_URL)
print()


# ============================================================
# URL BROWSERLESS
# ============================================================

BROWSERLESS_URL = (
    "https://production-sfo.browserless.io/scrape"
    f"?token={BROWSERLESS_TOKEN}"
)


# ============================================================
# REQUÊTE BROWSERLESS
# ============================================================

payload = {
    "url": FFTA_URL,

    "elements": [
        {
            "selector": "article.competition_item"
        },
        {
            "selector": ".competition_item__title"
        },
        {
            "selector": "a.competition_item__results_btn"
        }
    ],

    "waitForSelector": {
        "selector": "article.competition_item",
        "timeout": 30000
    }
}


print("Interrogation de Browserless...")

try:
    response = requests.post(
        BROWSERLESS_URL,
        json=payload,
        timeout=60
    )

except requests.RequestException as e:
    print("ERREUR lors de la connexion à Browserless :")
    print(e)
    sys.exit(1)


if response.status_code != 200:
    print("ERREUR Browserless.")
    print("Code HTTP :", response.status_code)
    print(response.text)
    sys.exit(1)


try:
    result = response.json()

except ValueError:
    print("ERREUR : Browserless n'a pas retourné du JSON valide.")
    print(response.text)
    sys.exit(1)


# ============================================================
# EXTRACTION DES DONNÉES
# ============================================================

data = result.get("data", [])

if not data:
    print("ERREUR : aucune donnée reçue de Browserless.")
    sys.exit(1)


competition_elements = []
title_elements = []
result_elements = []


for item in data:

    selector = item.get("selector")
    results = item.get("results", [])

    if selector == "article.competition_item":
        competition_elements = results

    elif selector == ".competition_item__title":
        title_elements = results

    elif selector == "a.competition_item__results_btn":
        result_elements = results


print("Compétitions trouvées :", len(competition_elements))
print("Titres trouvés :", len(title_elements))
print("Liens résultats trouvés :", len(result_elements))


# ============================================================
# CRÉATION DE LA LISTE DES COMPÉTITIONS
# ============================================================

competitions = []

count = min(
    len(title_elements),
    len(result_elements)
)


for i in range(count):

    title = title_elements[i].get("text", "").strip()

    result_item = result_elements[i]

    # Browserless peut retourner une liste pour le résultat
    # du sélecteur du lien.
    if isinstance(result_item, list):
        if not result_item:
            continue
        result_item = result_item[0]

    link = result_item.get("attributes", {}).get("href", "")

    if not title:
        continue

    if not link:
        continue

    # Certains liens peuvent éventuellement être relatifs.
    if link.startswith("/"):
        link = "https://www.ffta.fr" + link

    competitions.append(
        {
            "title": title,
            "link": link
        }
    )

# ============================================================
# VÉRIFICATION
# ============================================================

if not competitions:
    print()
    print("ERREUR : aucune compétition exploitable.")
    print("Le RSS ne sera pas remplacé.")
    sys.exit(1)


print()
print("Compétitions qui seront placées dans le RSS :")

for competition in competitions:
    print("-", competition["title"])
    print("  ", competition["link"])


# ============================================================
# CRÉATION DU FICHIER RSS
# ============================================================

rss = Element(
    "rss",
    {
        "version": "2.0"
    }
)

channel = SubElement(rss, "channel")

SubElement(
    channel,
    "title"
).text = "FFTA - Résultats des compétitions"

SubElement(
    channel,
    "description"
).text = (
    "Résultats des compétitions FFTA "
    "pour le département 57."
)

SubElement(
    channel,
    "link"
).text = (
    "https://www.ffta.fr/competitions"
)

SubElement(
    channel,
    "language"
).text = "fr"


# ============================================================
# AJOUT DES ARTICLES
# ============================================================

for competition in competitions:

    item = SubElement(channel, "item")

    SubElement(
        item,
        "title"
    ).text = competition["title"]

    SubElement(
        item,
        "link"
    ).text = competition["link"]

    SubElement(
        item,
        "guid"
    ).text = competition["link"]

    SubElement(
        item,
        "description"
    ).text = (
        f"Résultats : {competition['title']}"
    )


# ============================================================
# ÉCRITURE DU FICHIER
# ============================================================

tree = ElementTree(rss)

tree.write(
    "FFTA_Resultats.xml",
    encoding="utf-8",
    xml_declaration=True
)

print()
print("========================================")
print("RSS généré avec succès !")
print("========================================")
print()
print("Fichier créé : FFTA_Resultats.xml")
print()
print(
    f"Période FFTA : {start_date.isoformat()} "
    f"→ {end_date.isoformat()}"
)
print()
