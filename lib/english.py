"""Generate and cache convenient English labels with Google Translate."""

import csv

from lib.paths import data_path

CACHE = data_path("name-english.tsv")
CHUNK = 80


def load_cache(path=CACHE):
    try:
        with open(path, encoding="utf-8") as handle:
            return {row["chinese"]: row["english"]
                    for row in csv.DictReader(handle, delimiter="\t")}
    except FileNotFoundError:
        return {}


def save_cache(names, path=CACHE):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["chinese", "english"])
        writer.writerows(sorted(names.items()))


def translate_chunk(chunk, translator):
    """Translate in one request, falling back to individual names if lines drift."""
    try:
        result = translator.translate("\n".join(chunk)) or ""
    except Exception as error:
        from deep_translator.exceptions import TranslationNotFound
        if not isinstance(error, TranslationNotFound):
            raise
        if len(chunk) == 1:
            return {chunk[0]: chunk[0]}
        middle = len(chunk) // 2
        return (translate_chunk(chunk[:middle], translator)
                | translate_chunk(chunk[middle:], translator))
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    if len(lines) == len(chunk):
        return dict(zip(chunk, lines))
    if len(chunk) == 1:
        return {chunk[0]: lines[0] if lines else chunk[0]}
    middle = len(chunk) // 2
    return (translate_chunk(chunk[:middle], translator)
            | translate_chunk(chunk[middle:], translator))


def translate(missing, translator=None):
    if translator is None:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="zh-TW", target="en")
    found = {}
    for start in range(0, len(missing), CHUNK):
        found.update(translate_chunk(missing[start:start + CHUNK], translator))
    return found


def english_names(names, path=CACHE, translator=None):
    """English for every supplied label, translating and caching new labels."""
    cached = load_cache(path)
    missing = sorted({name for name in names if name and name not in cached})
    if translator is None and missing:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="zh-TW", target="en")
    for start in range(0, len(missing), CHUNK):
        cached.update(translate_chunk(missing[start:start + CHUNK], translator))
        save_cache(cached, path)
    return cached
