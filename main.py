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
COVER_PATH = os.path.join(PUBLIC_DIR, "cover.png")

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
# 2) MARKTDATEN (für die Finance-Folge)
# ===========================================================================
def fetch_quotes(instruments):
    """Holt aktuelle Kurse via Yahoo Finance (yfinance). Gibt je Instrument
    {label, unit, ok, price, change_abs, change_pct} zurück. Schlägt eine Abfrage
    fehl, wird ok=False gesetzt und das Instrument später NICHT erwähnt – so
    erfindet das Modell niemals Zahlen."""
    import yfinance as yf
    out = []
    for label, symbol, unit in instruments:
        rec = {"label": label, "unit": unit, "ok": False}
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            closes = [c for c in hist["Close"].tolist() if c == c]  # NaN entfernen
            if len(closes) >= 2:
                price, prev = closes[-1], closes[-2]
                rec.update(
                    ok=True,
                    price=round(price, 2),
                    change_abs=round(price - prev, 2),
                    change_pct=round((price - prev) / prev * 100, 2),
                )
        except Exception as e:  # yfinance kann zeitweise leer liefern
            print(f"    Kurs fehlgeschlagen für {label} ({symbol}): {e}")
        out.append(rec)
    return out


# ===========================================================================
# 3) ZUSAMMENFASSEN MIT CLAUDE
# ===========================================================================
COVERED_MARKER = "===COVERED==="


def _covered_block(already_covered):
    if not already_covered:
        return ""
    joined = "\n".join(f"- {t}" for t in already_covered)
    return (
        "\nALREADY COVERED in earlier shows today — do NOT repeat these (a brief "
        "cross-reference is fine, but no re-explaining):\n" + joined + "\n"
    )


def _common_rules():
    return (
        f"Write a spoken-word podcast script in {config.SCRIPT_LANGUAGE}, about "
        f"{config.TARGET_WORDS} words (~5 minutes read aloud).\n\n"
        "Editorial rules:\n"
        "- Merge duplicates: if several sources report the SAME event, cover it ONCE.\n"
        "- Lead with stories confirmed by at least TWO independent sources.\n"
        "- Separate facts from opinion; attribute opinions (\"according to ...\").\n"
        "- Where outlets frame an event differently, note it briefly; stay neutral.\n"
        "- Invent nothing not supported below. If little happened, be shorter.\n"
        "- Paraphrase; never copy sentences from the sources.\n"
        "- Flowing spoken prose: no bullet points, no headings, no stage directions.\n"
    )


def build_news_prompt(ep, items, date_str, already_covered):
    lines = [f"- [SOURCE: {it['source']}] {it['title']}. {it['summary'][:400]}" for it in items]
    sources_block = "\n".join(lines) if lines else "(no articles found today)"
    return f"""You are the host of a daily news podcast: "{ep['title']}". Today is {date_str}.

THIS SHOW IS STRICTLY ABOUT: {ep['scope']}
DO NOT INCLUDE (off-topic or belongs to another show): {ep['exclude']}
Read every item below and DROP anything that does not fit THIS show's topic, even though it appears in the feeds.
{_covered_block(already_covered)}
{_common_rules()}
Structure: brief spoken intro with the date and topic; the stories in descending importance; a short sign-off.

After the script, on a new line write exactly {COVERED_MARKER} followed by a short bullet list (3-8 words each) of the distinct stories you actually covered. This list is for de-duplication and will NOT be read aloud.

News items:
{sources_block}
"""


def build_finance_prompt(ep, quotes, macro_items, date_str, already_covered):
    qlines = []
    for q in quotes:
        if not q.get("ok"):
            continue
        if q["unit"] == "yield":
            qlines.append(f"- {q['label']}: {q['price']}% ({q['change_abs']:+} pts vs previous close)")
        else:
            suffix = f" {q['unit']}" if q["unit"] else ""
            qlines.append(f"- {q['label']}: {q['price']}{suffix} ({q['change_pct']:+}% vs previous close)")
    data_block = "\n".join(qlines) if qlines else "(market data unavailable today)"
    macro_lines = [f"- [SOURCE: {it['source']}] {it['title']}. {it['summary'][:400]}" for it in macro_items]
    macro_block = "\n".join(macro_lines) if macro_lines else "(no macro news found today)"
    return f"""You are the host of a daily finance & markets podcast: "{ep['title']}". Today is {date_str}.
{_covered_block(already_covered)}
{_common_rules()}
PART 1 — Markets. Using ONLY the DATA block below, give the current level and ONE sentence on the move for each instrument present. If an instrument is missing from the data, simply skip it — NEVER invent a number. Group naturally: equity indices first, then commodities & crypto, then government bond yields.

PART 2 — Macro. Explain the day's genuinely important macroeconomic developments (central banks, interest rates, inflation, jobs, growth, major economic policy) drawn from the macro news below. Skip minor single-company or stock-tip stories. Keep it understandable for a non-expert.

The DATA is ALWAYS reportable (the "already covered" rule applies only to the macro narrative, not to the market levels).
Structure: brief spoken intro with the date; Part 1; Part 2; short sign-off.

After the script, on a new line write exactly {COVERED_MARKER} followed by a short bullet list (3-8 words each) of the MACRO stories you covered (not the market levels). It will NOT be read aloud.

DATA (live market levels):
{data_block}

Macro news:
{macro_block}
"""


def write_script(prompt):
    msg = anthropic_client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()


def split_script_and_covered(text):
    """Trennt das vorzulesende Skript vom internen COVERED-Block."""
    if COVERED_MARKER in text:
        spoken, _, rest = text.partition(COVERED_MARKER)
        covered = [
            ln.lstrip("-*\u2022 ").strip()
            for ln in rest.splitlines()
            if ln.strip() and ln.lstrip()[:1] in "-*\u2022"
        ]
        return spoken.strip(), covered
    return text.strip(), []


# ===========================================================================
# 3) VERTONEN MIT OPENAI-TTS
# ===========================================================================
def synthesize(script_text, out_path):
    """OpenAI-TTS hat ein Eingabelimit pro Anfrage. Wir teilen das Skript an
    Satzgrenzen, vertonen jedes Stück und fügen die MP3s sauber zusammen.
    Das steuerbare Modell gpt-4o-mini-tts erlaubt eine Stil-Anweisung; die
    einfacheren Modelle tts-1/tts-1-hd erlauben dafür einen Tempo-Wert."""
    steerable = config.TTS_MODEL.startswith("gpt-4o")
    # gpt-4o-mini-tts hat ein kleineres Limit (~2000 Zeichen) als tts-1 (4096)
    max_chars = 1800 if steerable else 3500
    chunks = _split_text(script_text, max_chars=max_chars)
    segments = []
    tmp_files = []
    for i, chunk in enumerate(chunks):
        tmp = out_path + f".part{i}.mp3"
        kwargs = {
            "model": config.TTS_MODEL,
            "voice": config.TTS_VOICE,
            "input": chunk,
        }
        if steerable:
            # Ton, Stimmung und Tempo per Anweisung
            if getattr(config, "TTS_INSTRUCTIONS", ""):
                kwargs["instructions"] = config.TTS_INSTRUCTIONS
        else:
            # Tempo per Parameter (nur tts-1 / tts-1-hd zuverlässig)
            kwargs["speed"] = getattr(config, "TTS_SPEED", 1.0)
        with openai_client.audio.speech.with_streaming_response.create(**kwargs) as response:
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


def ensure_cover(path):
    """Erzeugt einmalig ein einfaches Cover-Bild (1500x1500 PNG), falls keins
    existiert. Spotify verlangt ein quadratisches Cover (1400–3000 px)."""
    if os.path.exists(path):
        return
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    size = 1500
    img = Image.new("RGB", (size, size), (18, 24, 38))   # dunkles Marineblau
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, size - 200, size, size], fill=(196, 60, 60))  # Akzentbalken

    def load_font(pt, bold=False):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        for p in (f"/usr/share/fonts/truetype/dejavu/{name}", name):
            try:
                return ImageFont.truetype(p, pt)
            except OSError:
                continue
        return ImageFont.load_default()

    font_big = load_font(150, bold=True)
    font_small = load_font(64)

    # Titel mittig, bei Bedarf umgebrochen
    lines = textwrap.wrap(config.PODCAST_TITLE, width=12) or [config.PODCAST_TITLE]
    line_h = font_big.getbbox("Ag")[3] + 24
    total_h = line_h * len(lines)
    y = (size - 200 - total_h) // 2
    for line in lines:
        w = draw.textlength(line, font=font_big)
        draw.text(((size - w) // 2, y), line, font=font_big, fill=(245, 247, 250))
        y += line_h

    sub = "Täglich · Politik & Welt"
    w = draw.textlength(sub, font=font_small)
    draw.text(((size - w) // 2, size - 150), sub, font=font_small, fill=(255, 255, 255))

    img.save(path, "PNG")


def build_feed(manifest):
    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(config.PODCAST_TITLE)
    fg.description(config.PODCAST_DESCRIPTION)
    fg.author({"name": config.PODCAST_AUTHOR, "email": config.PODCAST_EMAIL})
    fg.link(href=PUBLIC_BASE_URL, rel="alternate")
    fg.language(config.PODCAST_LANGUAGE)
    fg.podcast.itunes_author(config.PODCAST_AUTHOR)
    fg.podcast.itunes_category("News")
    fg.podcast.itunes_explicit("no")
    # Spotify-Pflicht: Cover-Bild und Inhaber-E-Mail
    fg.podcast.itunes_image(f"{PUBLIC_BASE_URL}/cover.png")
    fg.podcast.itunes_owner(name=config.PODCAST_AUTHOR, email=config.PODCAST_EMAIL)
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
        fe.podcast.itunes_explicit("no")

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
    already_covered = []   # für Entdopplung über die Folgen hinweg

    for ep in config.EPISODES:
        print(f"==> Episode: {ep['title']}")
        kind = ep.get("kind", "news")

        if kind == "finance":
            quotes = fetch_quotes(ep.get("instruments", []))
            ok_n = sum(1 for q in quotes if q.get("ok"))
            macro_items = fetch_items(ep.get("feeds", []))
            print(f"    {ok_n} Kurse, {len(macro_items)} Makro-Artikel")
            if ok_n == 0 and not macro_items:
                print("    keine Daten – Episode wird übersprungen")
                continue
            prompt = build_finance_prompt(ep, quotes, macro_items, date_str, already_covered)
        else:
            items = fetch_items(ep["feeds"])
            print(f"    {len(items)} Artikel gesammelt")
            if not items:
                print("    keine Artikel – Episode wird übersprungen")
                continue
            prompt = build_news_prompt(ep, items, date_str, already_covered)

        full = write_script(prompt)
        script, covered = split_script_and_covered(full)
        already_covered.extend(covered)
        print(f"    Skript: {len(script.split())} Wörter, {len(covered)} Themen erfasst")

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
    ensure_cover(COVER_PATH)
    build_feed(manifest)
    print("Fertig. Feed geschrieben nach", FEED_PATH)


if __name__ == "__main__":
    main()
