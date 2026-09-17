import os
import sys
from datetime import date, timedelta
from html import unescape
from xml.etree.ElementTree import Element, SubElement, ElementTree

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN")

if not BROWSERLESS_TOKEN:
    print("ERREUR : la variable BROWSERLESS_TOKEN est absente.")
    sys.exit(1)


# ============================================================
# URL FFTA - COMPÉTITIONS À VENIR
# ============================================================

start_date = date.today()
end_date = start_date + timedelta(days=365)

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
    "&sort_order=ASC"
)

print("URL FFTA utilisée :")
print(FFTA_URL)
print()


# ============================================================
# BROWSERLESS
# ============================================================

BROWSERLESS_URL = (
    "https://production-sfo.browserless.io/scrape"
    f"?token={BROWSERLESS_TOKEN}"
)

payload = {
    "url": FFTA_URL,
    "elements": [
        {
            "selector": "article.competition_item"
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
# EXTRACTION DES COMPÉTITIONS
# ============================================================

data = result.get("data", [])

if not data:
    print("ERREUR : aucune donnée reçue de Browserless.")
    sys.exit(1)

competition_elements = []

for item in data:
    if item.get("selector") == "article.competition_item":
        competition_elements = item.get("results", [])
        break

print("Compétitions trouvées :", len(competition_elements))

if not competition_elements:
    print("ERREUR : aucune compétition trouvée.")
    sys.exit(1)


# ============================================================
# OUTILS
# ============================================================

def absolute_url(url):
    if not url:
        return ""

    if url.startswith("/"):
        return "https://www.ffta.fr" + url

    return url


def find_link(article, wanted_text):
    """
    Cherche dans une compétition le lien dont le texte correspond
    à wanted_text, par exemple 'Mandat' ou 'Détail'.
    """

    wanted_text = wanted_text.lower().strip()

    for link in article.find_all("a"):
        text = " ".join(link.stripped_strings).strip().lower()

        if text == wanted_text:
            href = link.get("href", "")
            return absolute_url(href)

    return ""


# ============================================================
# CONSTRUCTION DE LA LISTE
# ============================================================

competitions = []

for element in competition_elements:

    html = element.get("html", "")

    if not html:
        continue

    soup = BeautifulSoup(html, "html.parser")

    title_element = soup.select_one(".competition_item__title")

    if not title_element:
        continue

    title = " ".join(title_element.stripped_strings).strip()

    if not title:
        continue

    detail_link = find_link(soup, "Détail")
    mandat_link = find_link(soup, "Mandat")

    if not detail_link:
        continue

    competitions.append(
        {
            "title": unescape(title),
            "detail": detail_link,
            "mandat": mandat_link
        }
    )


print()
print("Compétitions exploitables :", len(competitions))

mandat_count = sum(
    1 for competition in competitions
    if competition["mandat"]
)

print("Mandats disponibles :", mandat_count)
print()


# ============================================================
# AFFICHAGE POUR VÉRIFICATION
# ============================================================

if not competitions:
    print("ERREUR : aucune compétition exploitable.")
    print("Le RSS ne sera pas remplacé.")
    sys.exit(1)

print("Compétitions qui seront placées dans le RSS :")
print()

for competition in competitions:

    print("-", competition["title"])
    print("  Détail :", competition["detail"])

    if competition["mandat"]:
        print("  Mandat :", competition["mandat"])
    else:
        print("  Mandat : non disponible")

    print()


# ============================================================
# CRÉATION DU RSS
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
).text = "FFTA - Compétitions à venir"

SubElement(
    channel,
    "description"
).text = (
    "Calendrier des compétitions FFTA à venir "
    "pour le département 58."
)

SubElement(
    channel,
    "link"
).text = "https://www.ffta.fr/competitions"

SubElement(
    channel,
    "language"
).text = "fr"


# ============================================================
# AJOUT DES COMPÉTITIONS
# ============================================================

for competition in competitions:

    item = SubElement(channel, "item")

    SubElement(
        item,
        "title"
    ).text = competition["title"]

    # Lien principal = page détail de la compétition.
    SubElement(
        item,
        "link"
    ).text = competition["detail"]

    SubElement(
        item,
        "guid"
    ).text = competition["detail"]

    # Description avec liens cliquables.
    description_parts = [
        f"Compétition à venir : {competition['title']}",
        f'<br><br><a href="{competition["detail"]}">Détail de la compétition</a>'
    ]

    if competition["mandat"]:
        description_parts.append(
            f'<br><a href="{competition["mandat"]}">Mandat</a>'
        )

    # CDATA pour conserver les liens HTML dans le RSS.
    description = "".join(description_parts)

    description_element = SubElement(
        item,
        "description"
    )

    description_element.text = description


# ============================================================
# ÉCRITURE DU RSS AVEC CDATA
# ============================================================

output_file = "FFTA_Competition_a_Venir.xml"

# ElementTree échappe normalement le HTML dans <description>.
# On remplace les descriptions concernées par du CDATA après
# génération du XML.
tree = ElementTree(rss)
tree.write(
    output_file,
    encoding="utf-8",
    xml_declaration=True
)

# Relecture et transformation des descriptions en CDATA.
with open(output_file, "r", encoding="utf-8") as f:
    xml_text = f.read()

for competition in competitions:

    description_parts = [
        f"Compétition à venir : {competition['title']}",
        f'<br><br><a href="{competition["detail"]}">Détail de la compétition</a>'
    ]

    if competition["mandat"]:
        description_parts.append(
            f'<br><a href="{competition["mandat"]}">Mandat</a>'
        )

    description = "".join(description_parts)

    escaped_description = (
        description
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    original = f"<description>{escaped_description}</description>"
    replacement = f"<description><![CDATA[{description}]]></description>"

    xml_text = xml_text.replace(
        original,
        replacement,
        1
    )

with open(output_file, "w", encoding="utf-8") as f:
    f.write(xml_text)


print()
print("========================================")
print("RSS généré avec succès !")
print("========================================")
print()
print("Fichier créé :", output_file)
print()
print(
    f"Période FFTA : {start_date.isoformat()} "
    f"→ {end_date.isoformat()}"
)
print()
print("Mandats inclus lorsqu'ils sont disponibles.")
