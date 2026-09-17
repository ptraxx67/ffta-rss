import json
import os
import urllib.request
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape


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


payload = {
    "url": FFTA_URL,
    "elements": [
        {
            "selector": "article.competition_item",
            "type": "css",
            "results": [
                {
                    "type": "text",
                    "selector": ".competition_item__title"
                },
                {
                    "type": "attribute",
                    "selector": "a.competition_item__results_btn",
                    "attribute": "href"
                }
            ]
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
        "Content-Type": "application/json"
    },
    method="POST"
)


with urllib.request.urlopen(request, timeout=90) as response:
    result = json.loads(response.read().decode("utf-8"))


print(json.dumps(result, indent=2, ensure_ascii=False))


# Recherche des résultats
data = result.get("data", [])

if not data:
    raise RuntimeError("Browserless n'a retourné aucune donnée.")


# On accepte plusieurs formats possibles de réponse Browserless
items = []

for block in data:
    if block.get("selector") == "article.competition_item":
        items = block.get("results", [])
        break


if not items:
    raise RuntimeError(
        "Aucune compétition FFTA trouvée dans la réponse Browserless."
    )


rss_items = []

now = datetime.now().astimezone()

for index, item in enumerate(items):

    # Selon le format retourné par Browserless
    title = ""
    link = ""

    if isinstance(item, dict):

        # Cas courant : texte directement dans l'objet
        title = (
            item.get("text")
            or item.get("title")
            or ""
        ).strip()

        link = (
            item.get("href")
            or item.get("link")
            or ""
        ).strip()

        # Cas où Browserless retourne les résultats
        results = item.get("results", [])

        for result_item in results:
            if not isinstance(result_item, dict):
                continue

            selector = result_item.get("selector", "")

            value = (
                result_item.get("value")
                or result_item.get("text")
                or result_item.get("href")
                or ""
            )

            if "title" in selector:
                title = str(value).strip()

            if "results_btn" in selector:
                link = str(value).strip()

    if not title or not link:
        continue

    title_xml = escape(title)
    link_xml = escape(link)

    rss_items.append(
        f"""    <item>
      <title>{title_xml}</title>
      <link>{link_xml}</link>
      <guid isPermaLink="true">{link_xml}</guid>
      <description>{escape("Résultats : " + title)}</description>
      <pubDate>{format_datetime(now)}</pubDate>
    </item>"""
    )


if not rss_items:
    raise RuntimeError(
        "Les compétitions ont été trouvées, "
        "mais aucun titre/lien n'a pu être extrait."
    )


rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>FFTA — Résultats des compétitions</title>
    <link>https://www.ffta.fr/competitions</link>
    <description>Résultats des compétitions FFTA — Département 58</description>
    <language>fr-fr</language>
    <lastBuildDate>{format_datetime(now)}</lastBuildDate>
{chr(10).join(rss_items)}
  </channel>
</rss>
"""


with open("ffta.xml", "w", encoding="utf-8") as file:
    file.write(rss)


print()
print("======================================")
print("RSS FFTA généré avec succès")
print("Nombre d'articles :", len(rss_items))
print("Fichier : ffta.xml")
print("======================================")
