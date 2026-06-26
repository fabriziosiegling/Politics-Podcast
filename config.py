"""
config.py — alles, was du anpassen kannst, an einem Ort.
Nur diese Datei musst du bearbeiten, wenn du Quellen, Stimme oder Länge ändern willst.
Den Code in main.py musst du nicht anfassen.
"""

# ---------------------------------------------------------------------------
# 1) DIE EPISODEN
# ---------------------------------------------------------------------------
# Jede Episode hat:
#   id      – Präfix für die Audiodatei
#   title   – Sendungsname / Folgentitel
#   kind    – "news" (Standard) oder "finance" (Börsenfolge mit Live-Kursen)
#   scope   – worüber die Folge AUSSCHLIESSLICH gehen soll
#   exclude – was bewusst weggelassen wird (Off-Topic / gehört in andere Folge)
#   feeds   – RSS-Quellen
# Die scope/exclude-Texte sind wichtig: Sie sorgen dafür, dass deutsche Themen,
# Weltthemen und Finanzthemen sauber getrennt bleiben und nichts doppelt kommt.

EPISODES = [
    {
        "id": "politics-de",
        "title": "Innenpolitik Deutschland",
        "kind": "news",
        "scope": (
            "ONLY German DOMESTIC politics: the federal government and chancellor, "
            "Bundestag and Bundesrat, the political parties and coalition, and "
            "domestic policy debates (migration, social/pension/labour policy, "
            "internal security, budget, federal and state-level politics)."
        ),
        "exclude": (
            "foreign and international news, wars or politics abroad, other "
            "countries' domestic affairs, EU matters that are not about Germany, "
            "sports, celebrities, lifestyle, weather, market/stock prices, "
            "tech-product news, and crime without national political significance."
        ),
        "feeds": [
            "https://www.tagesschau.de/inland/innenpolitik/index~rss2.xml",  # ö.-r. Anker
            "https://rss.sueddeutsche.de/rss/Politik",                       # linksliberal
            "https://www.welt.de/feeds/section/politik.rss",                 # konservativ
            "https://newsfeed.zeit.de/politik/index",                        # ZEIT
            "https://www.deutschlandfunk.de/politikportal-100.rss",          # DLF (sachlich)
            "https://www.faz.net/rss/aktuell/politik/inland/",               # FAZ Inland
        ],
    },
    {
        "id": "world",
        "title": "Weltpolitik – Top Events",
        "kind": "news",
        "scope": (
            "INTERNATIONAL politics and geopolitics: wars and conflicts, diplomacy, "
            "elections and governments OUTSIDE Germany, the EU as an international "
            "actor, and major powers (US, China, Russia, Middle East, etc.). "
            "Germany's FOREIGN policy and its role abroad is allowed."
        ),
        "exclude": (
            "purely German DOMESTIC politics (that is the German show), sports, "
            "celebrities, lifestyle, weather, market/stock prices, tech-product news."
        ),
        "feeds": [
            "https://www.tagesschau.de/ausland/index~rss2.xml",   # deutscher Anker
            "https://feeds.bbci.co.uk/news/world/rss.xml",        # BBC World
            "https://www.theguardian.com/world/rss",              # Guardian World
            "https://www.france24.com/en/rss",                    # France 24
            "https://rss.dw.com/xml/rss-en-all",                  # Deutsche Welle (EN)
            "https://www.aljazeera.com/xml/rss/all.xml",          # Al Jazeera
        ],
    },
    {
        "id": "finance",
        "title": "Finance & Markets",
        "kind": "finance",
        "scope": "financial markets and macroeconomics",
        "exclude": "politics already covered in the other shows, sports, lifestyle",
        # Makro-/Wirtschaftsquellen für den erklärenden Teil
        "feeds": [
            "https://www.tagesschau.de/wirtschaft/index~rss2.xml",  # Tagesschau Wirtschaft
            "https://feeds.bbci.co.uk/news/business/rss.xml",       # BBC Business
            "https://www.theguardian.com/business/rss",             # Guardian Business
        ],
        # Live-Kurse (Label, Yahoo-Finance-Symbol, Einheit). "yield" = Anleiherendite.
        "instruments": [
            ("DAX",                   "^GDAXI",  ""),
            ("FTSE 100",              "^FTSE",   ""),
            ("Nasdaq Composite",      "^IXIC",   ""),
            ("S&P 500",               "^GSPC",   ""),
            ("Gold",                  "GC=F",    "USD/oz"),
            ("Bitcoin",               "BTC-USD", "USD"),
            ("US 10Y Treasury yield", "^TNX",    "yield"),
            # Hinweis: Für die 10-jährige deutsche Bundesanleihe gibt es bei Yahoo
            # keine zuverlässige kostenlose Kennung. Statt eine Zahl zu raten, wird
            # sie weggelassen. Auf Wunsch binde ich dafür eine eigene Datenquelle
            # (Bundesbank/EZB) ein – dann lässt sie sich hier ergänzen.
        ],
    },
]

# ---------------------------------------------------------------------------
# 2) PODCAST-EINSTELLUNGEN
# ---------------------------------------------------------------------------
PODCAST_TITLE = "Good Morning Fabrizio"
PODCAST_DESCRIPTION = (
    "Tägliche, quellengeprüfte 5-Minuten-Briefings zu Innenpolitik Deutschland "
    "und Weltpolitik. Automatisch generiert."
)
PODCAST_AUTHOR = "Morning Podcast Bot"
# WICHTIG für Spotify: Hier deine echte E-Mail eintragen. Spotify prüft darüber
# die Inhaberschaft des Feeds. Diese Adresse wird im Feed öffentlich sichtbar.
PODCAST_EMAIL = "ibaf005@gmail.com"
PODCAST_LANGUAGE = "en"  # Sprache der gesprochenen Folgen (Skript wird auf Englisch erzeugt)

# Wie viele Tage an Episoden im Feed behalten werden (ältere werden gelöscht).
KEEP_DAYS = 7

# Nur Artikel berücksichtigen, die nicht älter als so viele Stunden sind.
LOOKBACK_HOURS = 28  # etwas über 24h, damit nichts an der Tagesgrenze verloren geht

# Höchstzahl Artikel, die pro Feed an Claude geschickt werden (begrenzt Kosten/Länge).
MAX_ITEMS_PER_FEED = 12

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
# Modell: gpt-4o-mini-tts ist das neue, steuerbare Modell (natürlicher Klang +
# Stil per Anweisung). Günstiger/einfacher: "tts-1" oder "tts-1-hd".
TTS_MODEL = "gpt-4o-mini-tts"

# Stimme. Neutral: alloy, sage. Tiefer/männlich: onyx, echo. Warm/weiblich: nova,
# coral, shimmer. (Für tts-1/tts-1-hd nur: alloy, ash, coral, echo, fable, onyx,
# nova, sage, shimmer.)
TTS_VOICE = "alloy"

# STIL: So soll die Stimme klingen (nur beim Modell gpt-4o-mini-tts wirksam).
# Hier in normaler Sprache Ton, Stimmung UND Tempo beschreiben.
TTS_INSTRUCTIONS = (
    "Speak in a lively, energetic and upbeat tone, like a sharp, engaged morning "
    "news host. Keep a clear, neutral accent. Use a brisk, slightly faster-than-"
    "average pace while staying easy to follow. Sound dynamic and awake, never flat "
    "or monotone."
)

# TEMPO für die einfacheren Modelle tts-1 / tts-1-hd (1.0 = normal, >1 schneller,
# <1 langsamer). Beim Modell gpt-4o-mini-tts wird das Tempo über die Anweisung
# oben gesteuert, nicht über diesen Wert.
TTS_SPEED = 1.12
