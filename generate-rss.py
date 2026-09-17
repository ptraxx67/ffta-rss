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
# URL FFTA - 12 MOIS GLISSANTS
# ============================================================

end_date = date.today()
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
# EXTRACTION DES BLOCS
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
# FONCTIONS DE LECTURE DES RÉSULTATS BROWSERLESS
# ============================================================

def extract_text(item):
    """
    Récupère le texte même si Browserless retourne
    une structure légèrement différente.
    """

    if isinstance(item, list):

        if not item:
            return ""

        return extract_text(item[0])

    if isinstance(item, dict):

        text = item.get("text")

        if isinstance(text, str):
            return text.strip()

        # Certaines réponses peuvent utiliser textContent.
        text_content = item.get("textContent")

        if isinstance(text_content, str):
            return text_content.strip()

    return ""


def extract_href(item):
    """
    Récupère le href dans la structure retournée par Browserless.
    Browserless retourne les attributs sous forme de liste :
    [
        {"name": "class", "value": "..."},
        {"name": "href", "value": "..."}
    ]
    """

    if isinstance(item, list):

        for subitem in item:

            href = extract_href(subitem)

            if href:
                return href

        return ""

    if isinstance(item, dict):

        # Cas Browserless :
        # {"name": "href", "value": "https://..."}
        if item.get("name") == "href":

            value = item.get("value")

            if isinstance(value, str) and value:
                return value

        # Cas éventuel où href serait directement présent.
        href = item.get("href")

        if isinstance(href, str) and href:
            return href

        # Cas :
        # {"attributes": [{"name": "href", "value": "..."}]}
        attributes = item.get("attributes")

        if isinstance(attributes, list):

            for attribute in attributes:

                if (
                    isinstance(attribute, dict)
                    and attribute.get("name") == "href"
                ):

                    value = attribute.get("value")

                    if isinstance(value, str) and value:
                        return value

        # Recherche récursive dans les autres champs.
        for key, value in item.items():

            if key == "attributes":
                continue

            if isinstance(value, (dict, list)):

                href = extract_href(value)

                if href:
                    return href

    return ""
    
# ============================================================
# CRÉATION DE LA LISTE DES COMPÉTITIONS
# ============================================================

competitions = []

count = min(
    len(title_elements),
    len(result_elements)
)


for i in range(count):

    title = extract_text(title_elements[i])

    link = extract_href(result_elements[i])

    if not title:
        continue

    if not link:
        continue

    # Si le lien est relatif.
    if link.startswith("/"):
        link = "https://www.ffta.fr" + link

    competitions.append(
        {
            "title": title,
            "link": link
        }
    )


print()
print("Compétitions avec titre + lien :", len(competitions))


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
print()

for competition in competitions:

    print("-", competition["title"])
    print("  ", competition["link"])


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
).text = "FFTA - Résultats des compétitions"

SubElement(
    channel,
    "description"
).text = (
    "Résultats des compétitions FFTA "
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
# ÉCRITURE DU FICHIER RSS
# ============================================================

output_file = "FFTA_Resultats.xml"

tree = ElementTree(rss)

tree.write(
    output_file,
    encoding="utf-8",
    xml_declaration=True
)


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
