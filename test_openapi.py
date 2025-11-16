from openai import OpenAI
import os
import json

# 1) API-Key (am besten per ENV-Variable setzen)
# export OPENAI_API_KEY="sk-..."
client = OpenAI(api_key="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")

# 2) Prompt vorbereiten
prompt = """
Stelle Dir vor, Du bist ein sehr erfahrener Verkäufer von KFZ-Teilen.
Nutze die Websuche (autodoc.de, tecdoc.de, ebay.de), um reale Daten zu finden.

Aufgabe:
Erstelle für das Automobilersatzteil
"9808561380 Peugeot Expert Katalysator Partikelfilter"
eine professionelle Beschreibung in folgendem JSON-Format:

{
  "titel": "Titel",
  "SEO": "SEO-Titel",
  "Kurzbeschreibung": "Kurzbeschreibung (max. 100 Zeichen)",
  "Verkaufstext": "Verkaufstext Lang (max. 300 Zeichen)",
  "OE-Nummer": [],
  "Quelle": [],
  "kompatibilität": [
    {
      "marke": string,
      "modell": string,
      "baujahr_von": "YYYY",
      "baujahr_bis": "YYYY",
      "motorvarianten": [],
      "bemerkung": string
    }
  ]
}

Anforderungen:
- Recherchiere mit Websuche nur auf autodoc.de, tecdoc.de oder ebay.de.
- Fülle alle Felder, soweit durch die Quellen möglich.
- Die vollständige Kompatibilitätsliste (inkl. Untervarianten) muss so genau wie möglich sein. Bitte listen Sie alle Fahrzeuge auf, in denen dieses Ersatzteil oder die kompatiblen OE-Nummer verwendet werden können.
- Gib ausschließlich ein einziges, gültiges JSON-Objekt in genau dieser Struktur zurück.
- Keine zusätzlichen Erklärungen, kein Fließtext außerhalb des JSON.
"""

# 3) Request an Responses API mit Websuche + JSON-Output
response = client.responses.create(
    model="gpt-5.1",
    input=prompt,
    max_output_tokens=4000,
    tools=[
        {
            # laut aktueller Doku: Web-Suche über Responses API
            "type": "web_search"
        }
    ],
)

# 4) Text aus dem Response holen
# Option A: Komfortfeld (falls vorhanden)
try:
    json_text = response.output_text
except AttributeError:
    # Fallback auf die generische Struktur
    json_text = response.output[0].content[0].text

# 5) Vom Modell geliefertes JSON in Python-Objekt parsen
try:
    data = json.loads(json_text)
except json.JSONDecodeError:
    print("Konnte das JSON nicht parsen. Rohtext:")
    print(json_text)
    raise

# 6) Ergebnis nutzen (z.B. ausgeben oder in DB speichern)
print(json.dumps(data, indent=2, ensure_ascii=False))