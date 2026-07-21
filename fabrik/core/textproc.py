"""Textverarbeitung für Skripte: Satz-Splitting (Englisch + CJK),
Chunking für die TTS und sprachneutrale Längenmessung."""

import hashlib
import re

_ABBREV = re.compile(
    r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|approx|dept|est|govt|'
    r'max|min|no|vol|fig|ed|rev|repr|incl|excl|Capt|Col|Gen|Lt|Sgt)\.'
)

# CJK-Satzenden inkl. eventuell folgender schließender Anführungszeichen/Klammern
_CJK_SENT_END = re.compile(r'([。！？；…]+[」』”’）]*)')

# CJK Unified Ideographs (+ Extension A, Kompatibilitätszeichen)
_CJK_CHAR = re.compile(r'[㐀-䶿一-鿿豈-﫿]')


def split_into_sentences(text):
    """Splittet an westlichen (. ! ?) und chinesischen (。！？；…) Satzenden.
    Chinesische Satzzeichen brauchen kein folgendes Leerzeichen."""
    # Abkürzungspunkte maskieren, damit sie keinen Split auslösen
    masked = _ABBREV.sub(lambda m: m.group().replace('.', '\x00'), text.strip())
    # CJK-Satzenden mit einem Marker versehen, dann daran splitten
    masked = _CJK_SENT_END.sub('\\1\x01', masked)
    sentences = []
    for segment in masked.split('\x01'):
        sentences.extend(re.split(r'(?<=[.!?])\s+', segment))
    return [s.replace('\x00', '.').strip() for s in sentences if s.strip()]


def chunk_sentences(sentences, max_chars):
    chunks = []
    current = []
    current_len = 0
    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def count_cjk(text):
    return len(_CJK_CHAR.findall(text))


def is_speakable(text):
    """False bei reinen Interpunktions-Chunks ('—', '...') — Dramaturgie-
    Pausen im Skripttext, für die kein TTS-Backend brauchbares Audio
    liefert (Plausibilitätsprüfung schlägt IMMER an, auch nach MAX_RETRIES
    Versuchen). Aufrufer rendern solche Chunks als Stille statt sie an das
    Backend zu schicken."""
    return any(ch.isalnum() for ch in text)


def count_length_units(text):
    """Sprachneutrale Länge: 1 CJK-Zeichen = 1 Einheit, 1 lateinisches Wort =
    1 Einheit. len(text.split()) würde chinesischen Text absurd kurz zählen
    (kein Leerzeichen zwischen Wörtern) und damit jedes Wortbudget sprengen."""
    cjk = count_cjk(text)
    latin_only = _CJK_CHAR.sub(' ', text)
    words = len(re.findall(r"[A-Za-z0-9À-ɏ]+(?:['’-][A-Za-z0-9À-ɏ]+)*", latin_only))
    return cjk + words


def sfx_asset_hash(description):
    """Deterministischer Dateiname-Baustein für generierte SFX-Assets
    (<hash>.mp3) — Podcast-Fabrik (beim Schreiben) und Lolfi (beim Lesen,
    eigene Kopie dieser Funktion in lolfi/discovery.py, siehe
    Lolfi/CLAUDE.md Kopplungspunkte) berechnen unabhängig denselben Hash
    aus demselben Cue-Text und finden so ohne Zuordnungsdatei dieselbe
    Datei. Normalisiert (strip+lower) vor dem Hashen, damit Groß-/
    Kleinschreibung oder Rand-Whitespace keinen neuen Dateinamen erzeugen."""
    return hashlib.sha1(description.strip().lower().encode("utf-8")).hexdigest()[:16]


def chunk_prose_by_words(text, max_words, mode="narration"):
    """Deterministisches Chunking für bereits fertigen Prosa-Text (Story-
    Import, siehe import_story.py): der Text wird an Leerzeilen in Absätze
    gesplittet und greedy zu Chunks bis max_words gruppiert, ohne den Inhalt
    zu verändern. Kein Minimum wird erzwungen — der letzte Chunk eines
    Textes darf kürzer sein; die Quelle bestimmt die Gesamtlänge, max_words
    steuert nur, wie fein sie in PARTs geschnitten wird. Ein einzelner
    Absatz, der allein schon über dem Limit liegt, wird wie chunk_sentences
    satzweise weiter aufgetrennt (nur wortbasiert statt zeichenbasiert)."""
    def length(t):
        return count_length_units(t) if mode == "drama" else len(t.split())

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    chunks = []
    current = []
    current_len = 0

    def flush():
        if current:
            chunks.append("\n\n".join(current))
            current.clear()

    for para in paragraphs:
        para_len = length(para)
        if para_len > max_words:
            flush()
            current_len_local = 0
            piece = []
            for sentence in split_into_sentences(para):
                sent_len = length(sentence)
                if piece and current_len_local + sent_len > max_words:
                    chunks.append(" ".join(piece))
                    piece, current_len_local = [], 0
                piece.append(sentence)
                current_len_local += sent_len
            if piece:
                chunks.append(" ".join(piece))
            current_len = 0
            continue
        if current and current_len + para_len > max_words:
            flush()
            current_len = 0
        current.append(para)
        current_len += para_len

    flush()
    return chunks


def format_eta(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"
