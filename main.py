"""
main.py — die komplette Pipeline.

Ablauf pro Episode:
  1. RSS-Feeds einlesen, Artikel der letzten Stunden sammeln
  2. Titel + Teaser an Claude schicken -> englisches ~5-Minuten-Skript (quellengeprüft)
  3. Skript mit OpenAI-TTS in eine MP3 verwandeln
  4. Episode in public/episodes.json eintragen, alte Folgen ausmisten
  5. public/feed.xml (Podcast-RSS) neu erzeugen

Benötigte Umgebungsvariablen (in GitHub als "Secrets"/"Variables" gesetzt):
  ANTHROPIC_API_KEY   – dein Anthropic-Schlüssel
  OPENAI_API_KEY      – dein OpenAI-Schlüssel
  PUBLIC_BASE_URL     – z.B. https://deinname.github.io/morning-podcast
                         (ohne abschließenden Slash; muss zum GitHub-Pages-Pfad passen)
"""

import os
import json
import html
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime

import feedparser
from dateutil import parser as dateparser

import anthropic
from openai import OpenAI
from feedgen.feed import FeedGenerator
from pydub import AudioSegment

import config

# --- Pfade -----------------------------------------------------------------
PUBLIC_DIR = "public"
EPISODES_DIR = os.path.join(PUBLIC_DIR, "episodes")
MANIFEST_PATH = os.path.join(PUBLIC_DIR, "episodes.json")
FEED_PATH = os.path.join(PUBLIC_DIR, "feed.xml")

# --- Umgebung --------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"].rstrip("/")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# ===========================================================================
# 1) FEEDS EINLESEN
# ===========================================================================
def fetch_items(feed_urls):
    """Holt aktuelle Artikel aus mehreren Feeds. Gibt Liste von dicts zurück:
    {source, title, summary}. Es wird nur Titel + Teaser genutzt (robust,
    keine Paywall-/Scraping-Probleme, urheberrechtlich unkritisch)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.LOOKBACK_HOURS)
    items = []
    for url in feed_urls:
        parsed = feedparser.parse(url)
        source = parsed.feed.get("title", url)
        count = 0
        for entry in parsed.entries:
            # Veröffentlichungszeit bestimmen (nicht jeder Feed liefert sie sauber)
            published = None
            for key in ("published", "updated", "pubDate"):
                if entry.get(key):
                    try:
                        published = dateparser.parse(entry.get(key))
                        break
                    except (ValueError, TypeError):
                        pass
            if published is not None:
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if published < cutoff:
                    continue  # zu alt

            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            # HTML aus dem Teaser entfernen (grob)
            summary = _strip_html(summary)
            if not title:
                continue
            items.append({"source": source, "title": title, "summary": summary})
            count += 1
            if count >= config.MAX_ITEMS_PER_FEED:
                break
    return items


def _strip_html(text):
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ===========================================================================
# 2) ZUSAMMENFASSEN MIT CLAUDE
# ===========================================================================
def build_prompt(episode_title, items, date_str):
    lines = []
    for it in items:
        teaser = it["summary"][:400]
        lines.append(f"- [SOURCE: {it['source']}] {it['title']}. {teaser}")
    sources_block = "\n".join(lines) if lines else "(no articles found today)"

    return f"""You are the writer and host of a short daily news podcast episode titled "{episode_title}". Today is {date_str}.

Below are news items collected from several independent outlets in the last day. Each line is tagged with its SOURCE. The sources span the political spectrum on purpose.

Write a spoken-word podcast script in {config.SCRIPT_LANGUAGE}, about {config.TARGET_WORDS} words (roughly 5 minutes when read aloud).

Strict editorial rules:
- Lead with the stories that are reported by at least TWO independent sources — those are the confirmed, important ones.
- Clearly separate facts from opinion/analysis. Attribute opinions ("according to ...").
- Where outlets frame the same event differently, briefly note the difference instead of picking a side. Stay neutral.
- Do NOT invent any fact that is not supported by the items below. If little happened, write a shorter episode rather than padding.
- Paraphrase in your own words; do not copy sentences from the sources.

Format:
- A brief spoken intro with the date and episode topic.
- The stories, in descending order of importance, in flowing spoken prose (no bullet points, no headings, no stage directions).
- A short sign-off.
- Output ONLY the script text that should be read aloud. No notes, no markdown.

News items:
{sources_block}
"""


def write_script(episode_title, items, date_str):
    prompt = build_prompt(episode_title, items, date_str)
    msg = anthropic_client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    # Antwort kann aus mehreren Textblöcken bestehen
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()


# ===========================================================================
# 3) VERTONEN MIT OPENAI-TTS
# ===========================================================================
def synthesize(script_text, out_path):
    """OpenAI-TTS hat ein Limit von ~4096 Zeichen pro Anfrage. Wir teilen das
    Skript in Stücke an Satzgrenzen, vertonen jedes Stück und fügen die MP3s
    sauber zusammen."""
    chunks = _split_text(script_text, max_chars=3500)
    segments = []
    tmp_files = []
    for i, chunk in enumerate(chunks):
        tmp = out_path + f".part{i}.mp3"
        with openai_client.audio.speech.with_streaming_response.create(
            model=config.TTS_MODEL,
            voice=config.TTS_VOICE,
            input=chunk,
        ) as response:
            response.stream_to_file(tmp)
        tmp_files.append(tmp)
        segments.append(AudioSegment.from_mp3(tmp))

    combined = segments[0]
    for seg in segments[1:]:
        combined += seg
    combined.export(out_path, format="mp3")

    for f in tmp_files:
        try:
            os.remove(f)
        except OSError:
            pass


def _split_text(text, max_chars=3500):
    import re
    sentences = re.split(r"(?<=[.!?]) +", text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = s
        else:
            current = (current + " " + s).strip()
    if current:
        chunks.append(current.strip())
    return chunks or [text]


# ===========================================================================
# 4) MANIFEST PFLEGEN + 5) FEED BAUEN
# ===========================================================================
def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def prune_old(manifest):
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.KEEP_DAYS)
    kept = []
    for ep in manifest:
        pub = dateparser.parse(ep["pubdate"])
        if pub >= cutoff:
            kept.append(ep)
        else:
            path = os.path.join(EPISODES_DIR, ep["file"])
            if os.path.exists(path):
                os.remove(path)
    return kept


def build_feed(manifest):
    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(config.PODCAST_TITLE)
    fg.description(config.PODCAST_DESCRIPTION)
    fg.author({"name": config.PODCAST_AUTHOR})
    fg.link(href=PUBLIC_BASE_URL, rel="alternate")
    fg.language(config.PODCAST_LANGUAGE)
    fg.podcast.itunes_author(config.PODCAST_AUTHOR)
    fg.podcast.itunes_category("News")
    # Feed-Selbstlink
    fg.link(href=f"{PUBLIC_BASE_URL}/feed.xml", rel="self")

    # neueste zuerst
    for ep in sorted(manifest, key=lambda e: e["pubdate"], reverse=True):
        fe = fg.add_entry()
        url = f"{PUBLIC_BASE_URL}/episodes/{ep['file']}"
        fe.id(url)
        fe.title(ep["title"])
        fe.description(ep.get("description", ep["title"]))
        fe.enclosure(url, str(ep.get("length", 0)), "audio/mpeg")
        fe.pubDate(ep["pubdate"])

    fg.rss_file(FEED_PATH, pretty=True)


# ===========================================================================
# HAUPTPROGRAMM
# ===========================================================================
def main():
    os.makedirs(EPISODES_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %d %B %Y")
    day_tag = now.strftime("%Y-%m-%d")

    manifest = load_manifest()

    for ep in config.EPISODES:
        print(f"==> Episode: {ep['title']}")
        items = fetch_items(ep["feeds"])
        print(f"    {len(items)} Artikel gesammelt")
        if not items:
            print("    keine Artikel – Episode wird heute übersprungen")
            continue

        script = write_script(ep["title"], items, date_str)
        print(f"    Skript: {len(script.split())} Wörter")

        filename = f"{ep['id']}-{day_tag}.mp3"
        out_path = os.path.join(EPISODES_DIR, filename)
        synthesize(script, out_path)
        length = os.path.getsize(out_path)
        print(f"    MP3 erzeugt ({length} Bytes)")

        # alten Eintrag desselben Tags/derselben Episode ersetzen, falls vorhanden
        manifest = [m for m in manifest if m["file"] != filename]
        manifest.append({
            "title": f"{ep['title']} – {now.strftime('%d.%m.%Y')}",
            "file": filename,
            "description": f"Quellengeprüftes Briefing vom {now.strftime('%d.%m.%Y')}.",
            "pubdate": format_datetime(now),
            "length": length,
        })

    manifest = prune_old(manifest)
    save_manifest(manifest)
    build_feed(manifest)
    print("Fertig. Feed geschrieben nach", FEED_PATH)


if __name__ == "__main__":
    main()
