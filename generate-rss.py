import json
import os
import urllib.request
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape


# ============================================================
# CONFIGURATION
# ============================================================

BROWSERLESS_TOKEN = os.environ["BROWSERLESS_TOKEN"]

FFTA_URL = (
    "https://www.ffta.fr/competitions"
    "?search="
    "&start=2025-09-01"
    "&end=2026-09-01"
    "&dep%5B%5D=58"
    "&discipline=103"
    "&univers=299"
    "&inter=All"
    "&sort_by=start"
    "&sort_order=DESC"
)

API_URL = (
    "https://production-sfo.browserless.io/scrape"
    "?token=" + BROWSERLESS_TOKEN
)


# ============================================================
# APPEL BROWSERLESS
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


request = urllib.request.Request(
    API_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    },
    method="POST"
)


print("Connexion à Browserless...")

with urllib.request.urlopen(request, timeout=90) as response:
    result = json.loads(
        response.read().decode("utf-8")
    )


print("Réponse Browserless reçue.")


# ============================================================
# EXTRACTION DES DONNÉES
# ============================================================

data = result.get("data", [])

if not data:
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise RuntimeError(
        "Browserless n'a retourné aucune donnée."
    )


competitions = []
titles = []
links = []


for block in data:

    selector = block.get("selector")
    results = block.get("results", [])

    if selector == "article.competition_item":
        competitions = results

    elif selector == ".competition_item__title":
        titles = results

    elif selector == "a.competition_item__results_btn":
        links = results


print()
print("Compétitions trouvées :", len(competitions))
print("Titres trouvés :", len(titles))
print("Liens résultats trouvés :", len(links))
print()


if not competitions:
    raise RuntimeError(
        "Aucune compétition FFTA trouvée."
    )


if not titles:
    raise RuntimeError(
        "Aucun titre de compétition trouvé."
    )


if not links:
    raise RuntimeError(
        "Aucun lien de résultats trouvé."
    )


# ============================================================
# EXTRACTION TITRES / LIENS
# ============================================================

rss_items = []

count = min(
    len(titles),
    len(links)
)


for i in range(count):

    title_result = titles[i]
    link_result = links[i]

    title = (
        title_result.get("text")
        or title_result.get("html")
        or ""
    ).strip()

    link = ""


    # Recherche de l'attribut href
    attributes = link_result.get(
        "attributes",
        []
    )

    for attribute in attributes:

        if attribute.get("name") == "href":

            link = (
                attribute.get("value")
                or ""
            ).strip()

            break


    # Sécurité supplémentaire
    if not link:

        link = (
            link_result.get("href")
            or ""
        ).strip()


    if not title or not link:

        print(
            "Élément ignoré :",
            title,
            link
        )

        continue


    title_xml = escape(title)
    link_xml = escape(link)


    rss_items.append(
        f"""    <item>
      <title>{title_xml}</title>
      <link>{link_xml}</link>
      <guid isPermaLink="true">{link_xml}</guid>
      <description>{escape("Résultats : " + title)}</description>
    </item>"""
    )


# ============================================================
# VÉRIFICATION
# ============================================================

if not rss_items:

    raise RuntimeError(
        "Les compétitions ont été trouvées, "
        "mais aucun article RSS n'a pu être créé."
    )


# ============================================================
# GÉNÉRATION DU RSS
# ============================================================

now = datetime.now().astimezone()

rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">

  <channel>

    <title>FFTA — Résultats des compétitions</title>

    <link>
      https://www.ffta.fr/competitions
    </link>

    <description>
      Résultats des compétitions FFTA — Département 58
    </description>

    <language>fr-fr</language>

    <lastBuildDate>
      {format_datetime(now)}
    </lastBuildDate>

{chr(10).join(rss_items)}

  </channel>

</rss>
"""


# ============================================================
# ÉCRITURE DU FICHIER
# ============================================================

with open(
    "ffta.xml",
    "w",
    encoding="utf-8"
) as file:

    file.write(rss)


print()
print("======================================")
print("RSS FFTA généré avec succès")
print("Nombre d'articles :", len(rss_items))
print("Fichier : ffta.xml")
print("======================================")
