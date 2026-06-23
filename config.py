"""
config.py — alles, was du anpassen kannst, an einem Ort.
Nur diese Datei musst du bearbeiten, wenn du Quellen, Stimme oder Länge ändern willst.
Den Code in main.py musst du nicht anfassen.
"""

# ---------------------------------------------------------------------------
# 1) DIE EPISODEN
# ---------------------------------------------------------------------------
# Jede Episode hat: einen Titel, einen Dateinamen-Präfix und eine Liste von RSS-Feeds.
# Du kannst Feeds entfernen/hinzufügen oder eine dritte Episode ergänzen.
# Tipp: pro Episode mehrere Quellen mischen (neutral + links + konservativ),
# damit die Verifizierung funktioniert.

EPISODES = [
    {
        "id": "politics-de",
        "title": "Innenpolitik Deutschland",
        "feeds": [
            # neutraler Anker (öffentlich-rechtlich)
            "https://www.tagesschau.de/inland/innenpolitik/index~rss2.xml",
            # eher linksliberal
            "https://rss.sueddeutsche.de/rss/Politik",
            # eher konservativ / wirtschaftsliberal (Gegengewicht)
            "https://www.welt.de/feeds/latest.rss",
        ],
    },
    {
        "id": "world",
        "title": "Weltpolitik – Top Events",
        "feeds": [
            # deutscher neutraler Anker
            "https://www.tagesschau.de/ausland/index~rss2.xml",
            # breite angelsächsische Perspektive
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            # deutscher Auslandssender (englisch)
            "https://rss.dw.com/rdf/rss-en-all",
            # Perspektive Globaler Süden / Nahost
            "https://www.aljazeera.com/xml/rss/all.xml",
        ],
    },
]

# ---------------------------------------------------------------------------
# 2) PODCAST-EINSTELLUNGEN
# ---------------------------------------------------------------------------
PODCAST_TITLE = "Mein Morgen-Briefing"
PODCAST_DESCRIPTION = (
    "Tägliche, quellengeprüfte 5-Minuten-Briefings zu Innenpolitik Deutschland "
    "und Weltpolitik. Automatisch generiert."
)
PODCAST_AUTHOR = "Morning Podcast Bot"
PODCAST_LANGUAGE = "en"  # Sprache der gesprochenen Folgen (Skript wird auf Englisch erzeugt)

# Wie viele Tage an Episoden im Feed behalten werden (ältere werden gelöscht).
KEEP_DAYS = 7

# Nur Artikel berücksichtigen, die nicht älter als so viele Stunden sind.
LOOKBACK_HOURS = 28  # etwas über 24h, damit nichts an der Tagesgrenze verloren geht

# Höchstzahl Artikel, die pro Feed an Claude geschickt werden (begrenzt Kosten/Länge).
MAX_ITEMS_PER_FEED = 15

# ---------------------------------------------------------------------------
# 3) ZUSAMMENFASSUNG (Claude)
# ---------------------------------------------------------------------------
CLAUDE_MODEL = "claude-sonnet-4-6"   # guter Kompromiss aus Qualität und Kosten
                                     # günstiger: "claude-haiku-4-5-20251001"
TARGET_WORDS = 750                   # ca. 5 Minuten gesprochen
SCRIPT_LANGUAGE = "English"          # in welcher Sprache das Skript geschrieben wird

# ---------------------------------------------------------------------------
# 4) STIMME (OpenAI TTS)
# ---------------------------------------------------------------------------
TTS_MODEL = "tts-1"   # günstig & schnell;  höhere Qualität: "tts-1-hd" (ca. 2x Kosten)
TTS_VOICE = "onyx"    # Optionen: alloy, echo, fable, onyx, nova, shimmer
                      # onyx = tief/seriös, nova = warm, shimmer = hell
