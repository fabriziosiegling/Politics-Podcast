# Mein Morgen-Briefing 🎧

Zwei automatische 5-Minuten-Podcasts jeden Morgen vor 6:00 Uhr:
**Innenpolitik Deutschland** und **Weltpolitik**. Mehrere Quellen pro Thema werden
gegengeprüft, neutral zusammengefasst (Claude) und vertont (OpenAI-TTS).
Läuft kostenlos über GitHub – kein eigener Server nötig.

---

## Was du einmalig brauchst

1. Ein **Anthropic-API-Konto** → https://console.anthropic.com (API-Key + etwas Guthaben)
2. Ein **OpenAI-API-Konto** → https://platform.openai.com (API-Key, für die Stimme)
3. Ein **GitHub-Konto** → https://github.com (kostenlos)

Die laufenden Kosten liegen erfahrungsgemäß im Bereich weniger Euro pro Monat
(Zusammenfassen wenige Cent/Tag, Vertonung wenige Cent/Tag, Hosting gratis).

---

## Einrichtung (ca. 30–45 Min, nur einmal)

### Schritt 1 – Repository anlegen
1. Auf GitHub oben rechts **+ → New repository**.
2. Name z. B. `morning-podcast`. Sichtbarkeit **Public** (nötig, damit deine
   Podcast-App den Feed laden kann). **Create repository**.
3. Lade alle Dateien aus diesem Ordner hoch (Drag & Drop ins Repo, inklusive des
   Ordners `.github/`). Achte darauf, dass die Struktur erhalten bleibt:
   ```
   morning-podcast/
   ├── main.py
   ├── config.py
   ├── requirements.txt
   ├── README.md
   └── .github/workflows/daily.yml
   ```

### Schritt 2 – Schlüssel als „Secrets" hinterlegen
GitHub speichert deine Keys sicher; sie stehen nie im Code.
1. Im Repo: **Settings → Secrets and variables → Actions**.
2. Reiter **Secrets** → **New repository secret**, zweimal:
   - Name `ANTHROPIC_API_KEY`, Wert = dein Anthropic-Key
   - Name `OPENAI_API_KEY`, Wert = dein OpenAI-Key
3. Reiter **Variables** → **New repository variable**:
   - Name `PUBLIC_BASE_URL`, Wert = `https://DEINNAME.github.io/morning-podcast`
     (ersetze `DEINNAME` durch deinen GitHub-Benutzernamen, **kein** Slash am Ende)

### Schritt 3 – GitHub Pages aktivieren (das hostet den Feed)
1. **Settings → Pages**.
2. Unter **Build and deployment → Source**: „Deploy from a branch".
3. Branch **main**, Ordner **/ (root)** auswählen → **Save**.
   (Die Audiodateien und der Feed landen im Ordner `public/`; deine Feed-Adresse
   lautet dann `https://DEINNAME.github.io/morning-podcast/public/feed.xml`.)

   ➜ Damit die Adresse genau zu `PUBLIC_BASE_URL` passt, hänge in der Variable aus
   Schritt 2 noch `/public` an, sodass dort steht:
   `https://DEINNAME.github.io/morning-podcast/public`

### Schritt 4 – Erstmal manuell testen
1. **Actions**-Tab → links **Daily Podcast** → rechts **Run workflow**.
2. Nach 1–3 Minuten sollte der Lauf grün sein. Im Repo erscheint dann ein Ordner
   `public/` mit `feed.xml` und `episodes/…mp3`.
3. Öffne im Browser deine Feed-Adresse (siehe oben) – du solltest XML sehen.

### Schritt 5 – In der Podcast-App abonnieren
- **Apple Podcasts:** Mediathek → oben rechts (•••) → „Sendung per URL folgen" →
  Feed-Adresse einfügen.
- **Pocket Casts / Overcast / AntennaPod:** „Feed-URL hinzufügen" → Adresse einfügen.
- **Spotify:** unterstützt das Hinzufügen privater RSS-Feeds nur eingeschränkt;
  Pocket Casts oder Apple Podcasts funktionieren am zuverlässigsten.

Fertig – ab jetzt erscheinen jeden Morgen automatisch zwei neue Folgen. 🎉

---

## Anpassen
Alles Wichtige steht in **`config.py`**:
- **Quellen** ändern/ergänzen (Feeds je Episode), oder eine 3. Episode anlegen
- **Stimme** (`TTS_VOICE`: onyx, nova, shimmer, …) und Qualität (`tts-1` / `tts-1-hd`)
- **Länge** (`TARGET_WORDS`) und **Sprache** (`SCRIPT_LANGUAGE`)
- **Uhrzeit:** in `.github/workflows/daily.yml` die `cron`-Zeile (in **UTC**!)

## Gut zu wissen
- **Zeitzone:** GitHub-Cron ist UTC und kennt keine Sommer-/Winterzeit. Der Standard
  `30 2 * * *` ergibt 04:30 (Sommer) bzw. 03:30 (Winter) – beides vor 6:00.
- **Download-Timing:** Podcast-Apps aktualisieren im Hintergrund. Falls morgens noch
  nichts da ist, hilft einmal manuelles Aktualisieren in der App; danach pendelt es
  sich ein.
- **Keine Artikel?** Liefert ein Tag zu wenig her, wird die Episode übersprungen
  statt mit Füllmaterial gestreckt.
- **Quellen ohne RSS** lassen sich später per Scraping ergänzen (z. B. `trafilatura`);
  für den stabilen Start nutzt dieses Setup bewusst nur RSS.
