from __future__ import annotations

import argparse
import csv
import difflib
import html
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path


SPECIAL_RE = re.compile(r"^\[_[A-Z0-9]+(?:_[A-Z0-9]+)*_\]$")
TT_RE = re.compile(r"^\[_TT_\d+\]$")

PUNCT_ONLY_RE = re.compile(
    r"""^[\.,;:!?¿¡…\)\]\}»”'"-]+$"""
)


def _time_value(value, fallback=None):
    if value is None:
        return fallback

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace(",", ".")

    m = re.match(
        r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?$",
        s,
    )

    if not m:
        try:
            return float(s)
        except Exception:
            return fallback

    hours = int(m.group(1) or 0)
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    millis = int((m.group(4) or "0").ljust(3, "0")[:3])

    return (
        hours * 3600
        + minutes * 60
        + seconds
        + millis / 1000.0
    )


def _token_time(token, side):
    offsets = token.get("offsets") or {}

    if side in offsets:
        try:
            return float(offsets[side]) / 1000.0
        except Exception:
            pass

    timestamps = token.get("timestamps") or {}

    return _time_value(
        timestamps.get(side),
        None,
    )


def _is_special(text):
    value = str(text or "").strip()

    if not value:
        return True

    if SPECIAL_RE.match(value):
        return True

    if TT_RE.match(value):
        return True

    if value.startswith("[_") and value.endswith("]"):
        return True

    return False


def parse_whisper_cpp_json(path: Path, WordClass):
    """
    whisper.cpp --output-json-full devuelve TOKENS, no palabras.

    La frontera de palabra se reconstruye usando el espacio inicial
    de los tokens Whisper.

    Ejemplos:

       " J" + "ock"          -> "Jock"
       " present" + "ación"  -> "presentación"
       " psic" + "ot" + ...  -> "psicoterapeuta"

    [_BEG_] y [_TT_xxx] nunca llegan al transcript visible.
    """

    data = json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )

    segments = data.get("transcription")

    if not isinstance(segments, list):
        return None

    words = []

    for segment in segments:
        tokens = segment.get("tokens") or []

        current = None

        for token in tokens:
            raw = str(
                token.get("text") or ""
            )

            value = raw.strip()

            if _is_special(value):
                continue

            start = _token_time(
                token,
                "from",
            )

            end = _token_time(
                token,
                "to",
            )

            probability = token.get(
                "p",
                token.get("probability"),
            )

            try:
                if probability is not None:
                    probability = float(
                        probability
                    )
            except Exception:
                probability = None

            leading_space = bool(
                raw[:1].isspace()
            )

            punctuation = bool(
                PUNCT_ONLY_RE.match(value)
            )

            if current is None:
                current = {
                    "text": value,
                    "start": start,
                    "end": end,
                    "probs": (
                        [probability]
                        if probability is not None
                        else []
                    ),
                }

                continue

            # puntuación pertenece a la palabra anterior
            if punctuation:
                current["text"] += value

                if end is not None:
                    current["end"] = end

                if probability is not None:
                    current["probs"].append(
                        probability
                    )

                continue

            # espacio inicial = palabra nueva
            if leading_space:
                probs = current["probs"]

                confidence = (
                    sum(probs) / len(probs)
                    if probs
                    else None
                )

                if current["text"]:
                    words.append(
                        WordClass(
                            current["text"],
                            float(
                                current["start"]
                                or 0
                            ),
                            float(
                                current["end"]
                                or current["start"]
                                or 0
                            ),
                            confidence,
                        )
                    )

                current = {
                    "text": value,
                    "start": start,
                    "end": end,
                    "probs": (
                        [probability]
                        if probability is not None
                        else []
                    ),
                }

            # sin espacio inicial = continuación del token
            else:
                current["text"] += value

                if end is not None:
                    current["end"] = end

                if probability is not None:
                    current["probs"].append(
                        probability
                    )

        if current and current["text"]:
            probs = current["probs"]

            confidence = (
                sum(probs) / len(probs)
                if probs
                else None
            )

            words.append(
                WordClass(
                    current["text"],
                    float(
                        current["start"]
                        or 0
                    ),
                    float(
                        current["end"]
                        or current["start"]
                        or 0
                    ),
                    confidence,
                )
            )

    return words, data


def load_transcript_smart(
    path,
    WordClass,
    fallback,
):
    path = Path(path)

    if path.suffix.lower() == ".json":
        try:
            parsed = parse_whisper_cpp_json(
                path,
                WordClass,
            )

            if parsed and parsed[0]:
                return parsed

        except Exception:
            pass

    return fallback(path)


def _norm(value):
    value = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.lower()

    return re.sub(
        r"[^a-z0-9]+",
        "",
        value,
    )


def _join(parts):
    text = " ".join(
        str(value).strip()
        for value in parts
        if str(value).strip()
    )

    text = re.sub(
        r"\s+([,.;:!?…])",
        r"\1",
        text,
    )

    text = re.sub(
        r"([¿¡])\s+",
        r"\1",
        text,
    )

    text = re.sub(
        r"(?<=[A-Za-zÁÉÍÓÚÑÜáéíóúñü0-9,.;:!?])([¿¡])",
        r" \1",
        text,
    )

    text = re.sub(
        r"\s+([)\]»”’])",
        r"\1",
        text,
    )

    text = re.sub(
        r"([(\[«“‘])\s+",
        r"\1",
        text,
    )

    return re.sub(
        r"\s{2,}",
        " ",
        text,
    ).strip()


###############################################################################
# CONTEXTO / MARCA / GLOSARIO
###############################################################################

def extract_brand_terms(brand_path):
    if not brand_path:
        return []

    brand_path = Path(brand_path)

    if not brand_path.is_file():
        return []

    text = brand_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    terms = set()

    # contenido entre comillas
    for value in re.findall(
        r'["“”]([^"“”]{2,80})["“”]',
        text,
    ):
        terms.add(
            value.strip()
        )

    for line in text.splitlines():
        line = re.sub(
            r"^[\s#>*\-•]+",
            "",
            line,
        ).strip()

        if not line:
            continue

        if len(line) > 120:
            continue

        if ":" in line:
            key, value = line.split(
                ":",
                1,
            )

            if re.search(
                r"nombre|marca|producto|servicio|persona|host|speaker|"
                r"termin|glosario|programa|evento",
                key,
                re.I,
            ):
                for candidate in re.split(
                    r"[,;|/]",
                    value,
                ):
                    candidate = candidate.strip(
                        " ."
                    )

                    if (
                        2
                        <= len(candidate)
                        <= 80
                    ):
                        terms.add(
                            candidate
                        )

        # nombres propios / términos capitalizados
        for match in re.finditer(
            r"\b(?:"
            r"[A-ZÁÉÍÓÚÑ]"
            r"[\wÁÉÍÓÚÑáéíóúñ-]+"
            r"(?:\s+|$)"
            r"){1,4}",
            line,
        ):
            candidate = (
                match.group(0)
                .strip()
            )

            if (
                2
                <= len(candidate)
                <= 80
            ):
                terms.add(
                    candidate
                )

    return sorted(
        terms,
        key=lambda value: (
            -len(value.split()),
            -len(value),
        ),
    )


###############################################################################
# CORRECCIONES MANUALES
###############################################################################

def _manual_file(root):
    return (
        Path(root)
        / "TRANSCRIPCIONES"
        / "CORRECCIONES_TRANSCRIPCION.json"
    )


def load_manual(root):
    path = _manual_file(root)

    if not path.is_file():
        return {
            "corrections": [],
            "speaker_names": {},
        }

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data,
            dict,
        ):
            return data

    except Exception:
        pass

    return {
        "corrections": [],
        "speaker_names": {},
    }


def apply_manual(
    words,
    root,
    WordClass,
):
    settings = load_manual(
        root
    )

    corrections = (
        settings.get("corrections")
        or []
    )

    if not corrections:
        return words, []

    output = list(words)
    applied = []

    for correction in corrections:
        corrected = str(
            correction.get(
                "corrected"
            )
            or ""
        ).strip()

        if not corrected:
            continue

        try:
            start = float(
                correction.get(
                    "start"
                )
            )

            end = float(
                correction.get(
                    "end"
                )
            )

        except Exception:
            continue

        indexes = [
            index
            for index, word in enumerate(output)
            if (
                ((word.start + word.end) / 2)
                >= start - 0.15
                and
                ((word.start + word.end) / 2)
                <= end + 0.15
            )
        ]

        if not indexes:
            continue

        first = indexes[0]
        last = indexes[-1]

        original = _join(
            [
                output[index].text
                for index
                in range(
                    first,
                    last + 1,
                )
            ]
        )

        probabilities = [
            output[index].probability
            for index
            in range(
                first,
                last + 1,
            )
            if (
                output[index].probability
                is not None
            )
        ]

        confidence = (
            sum(probabilities)
            / len(probabilities)
            if probabilities
            else None
        )

        replacement = WordClass(
            corrected,
            output[first].start,
            output[last].end,
            confidence,
        )

        output = (
            output[:first]
            + [replacement]
            + output[last + 1:]
        )

        applied.append(
            {
                "start": start,
                "end": end,
                "original": original,
                "corrected": corrected,
                "reason": "manual",
            }
        )

    return output, applied


###############################################################################
# CORRECCIONES / SUGERENCIAS DE MARCA
###############################################################################

def brand_quality(
    words,
    terms,
):
    review = []
    automatic = []

    if not terms:
        return review, automatic

    one_word_terms = []

    for term in terms:
        normalized = _norm(term)

        if (
            normalized
            and len(term.split()) == 1
        ):
            one_word_terms.append(
                (
                    term,
                    normalized,
                )
            )

    for word in words:
        current_norm = _norm(
            word.text
        )

        if len(current_norm) < 3:
            continue

        best = None

        for term, term_norm in one_word_terms:
            ratio = (
                difflib.SequenceMatcher(
                    None,
                    current_norm,
                    term_norm,
                )
                .ratio()
            )

            if (
                ratio >= 0.78
                and (
                    best is None
                    or ratio > best[0]
                )
            ):
                best = (
                    ratio,
                    term,
                    term_norm,
                )

        if not best:
            continue

        ratio, term, term_norm = best

        # misma palabra normalizada:
        # solo restauramos mayúsculas / acentos / spelling de marca
        if (
            current_norm
            == term_norm
            and
            word.text.strip(
                ".,;:!?"
            )
            != term
        ):
            original = word.text

            punctuation = ""

            match = re.search(
                r"([,.;:!?…]+)$",
                original,
            )

            if match:
                punctuation = (
                    match.group(1)
                )

            word.text = (
                term
                + punctuation
            )

            automatic.append(
                {
                    "start": word.start,
                    "end": word.end,
                    "original": original,
                    "corrected": word.text,
                    "reason": (
                        "brand_exact_normalized"
                    ),
                    "confidence": round(
                        ratio,
                        3,
                    ),
                }
            )

        # parecido, pero no idéntico:
        # NO cambiamos silenciosamente
        elif (
            ratio >= 0.88
            and
            word.text.strip(
                ".,;:!?"
            ).lower()
            != term.lower()
        ):
            review.append(
                {
                    "start": word.start,
                    "end": word.end,
                    "original": word.text,
                    "suggested": term,
                    "reason": (
                        "brand_near_match"
                    ),
                    "confidence": round(
                        ratio,
                        3,
                    ),
                }
            )

    return review, automatic


###############################################################################
# QC
###############################################################################

def quality_issues(words):
    issues = []

    for index, word in enumerate(
        words
    ):
        text = word.text.strip()

        if (
            not text
            or _is_special(text)
        ):
            continue

        reasons = []

        probability = (
            word.probability
        )

        if (
            probability is not None
            and probability < 0.45
        ):
            reasons.append(
                "low_confidence"
            )

        if (
            len(text) > 30
            and not re.match(
                r"https?://",
                text,
            )
        ):
            reasons.append(
                "unusually_long"
            )

        if re.search(
            r"[A-Za-zÁÉÍÓÚÑáéíóúñ]\d"
            r"|\d[A-Za-zÁÉÍÓÚÑáéíóúñ]",
            text,
        ):
            reasons.append(
                "mixed_alnum"
            )

        if not reasons:
            continue

        context = _join(
            [
                value.text
                for value
                in words[
                    max(
                        0,
                        index - 5,
                    ):
                    min(
                        len(words),
                        index + 6,
                    )
                ]
            ]
        )

        issues.append(
            {
                "start": word.start,
                "end": word.end,
                "original": word.text,
                "suggested": "",
                "reason": "+".join(
                    reasons
                ),
                "confidence": probability,
                "context": context,
            }
        )

    return issues


###############################################################################
# FRASES
###############################################################################

def phrase(words):
    probabilities = [
        word.probability
        for word in words
        if (
            word.probability
            is not None
        )
    ]

    confidence = (
        sum(probabilities)
        / len(probabilities)
        if probabilities
        else None
    )

    return {
        "start": words[0].start,
        "end": words[-1].end,
        "text": _join(
            [
                word.text
                for word in words
            ]
        ),
        "confidence": confidence,
    }


def build_phrases(
    words,
    max_words=30,
    max_seconds=12.0,
):
    output = []
    current = []

    for word in words:

        if (
            current
            and
            (
                word.start
                - current[-1].end
            )
            > 1.0
        ):
            output.append(
                phrase(current)
            )

            current = []

        current.append(
            word
        )

        duration = (
            current[-1].end
            - current[0].start
        )

        closes_sentence = bool(
            re.search(
                r"""[.!?…]["'”’)]?$""",
                word.text.strip(),
            )
        )

        if (
            len(current)
            >= max_words
            or duration
            >= max_seconds
            or (
                closes_sentence
                and len(current) >= 5
            )
        ):
            output.append(
                phrase(current)
            )

            current = []

    if current:
        output.append(
            phrase(current)
        )

    return output


###############################################################################
# TIMECODE
###############################################################################

def tc(
    seconds,
    srt=False,
):
    seconds = max(
        0,
        float(seconds),
    )

    whole = int(
        seconds
    )

    millis = round(
        (
            seconds
            - whole
        )
        * 1000
    )

    if millis == 1000:
        whole += 1
        millis = 0

    hours = (
        whole // 3600
    )

    minutes = (
        (whole % 3600)
        // 60
    )

    secs = (
        whole % 60
    )

    separator = (
        ","
        if srt
        else "."
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}"
        f"{separator}"
        f"{millis:03d}"
    )


###############################################################################
# SPEAKERS
###############################################################################

def load_speakers(root):
    path = (
        Path(root)
        / "TRANSCRIPCIONES"
        / "SPEAKER_SEGMENTS.json"
    )

    if not path.is_file():
        return []

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data,
            dict,
        ):
            return (
                data.get("segments")
                or []
            )

        if isinstance(
            data,
            list,
        ):
            return data

    except Exception:
        pass

    return []


def speaker_for(
    start,
    end,
    segments,
):
    best_overlap = 0
    best_speaker = None

    for segment in segments:
        try:
            segment_start = float(
                segment["start"]
            )

            segment_end = float(
                segment["end"]
            )

        except Exception:
            continue

        overlap = max(
            0,
            min(
                end,
                segment_end,
            )
            - max(
                start,
                segment_start,
            ),
        )

        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = (
                segment.get(
                    "speaker"
                )
            )

    return best_speaker


def speaker_names(root):
    transcript_dir = (
        Path(root)
        / "TRANSCRIPCIONES"
    )

    names = {}

    path = (
        transcript_dir
        / "SPEAKER_NAMES.json"
    )

    if path.is_file():
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(
                data,
                dict,
            ):
                names.update(
                    data
                )

        except Exception:
            pass

    manual = (
        load_manual(root)
        .get("speaker_names")
        or {}
    )

    if isinstance(
        manual,
        dict,
    ):
        names.update(
            manual
        )

    return names


###############################################################################
# DIARIZACIÓN
###############################################################################

def run_diarization(
    root,
    source,
    log=None,
):
    transcript_dir = (
        Path(root)
        / "TRANSCRIPCIONES"
    )

    output = (
        transcript_dir
        / "SPEAKER_SEGMENTS.json"
    )

    # una vez generada, nunca repetimos sin necesidad
    if output.is_file():
        return output

    support = (
        Path.home()
        / "Library/Application Support/com.abrxs.canter"
    )

    token_file = (
        support
        / "hf_token"
    )

    python = (
        support
        / "pyannote-venv/bin/python"
    )

    audio = (
        Path(source).parent
        / "master_16k_mono.wav"
    )

    if not (
        token_file.is_file()
        and python.is_file()
        and audio.is_file()
    ):
        return None

    token = token_file.read_text(
        encoding="utf-8"
    ).strip()

    if not token:
        return None

    runner = (
        transcript_dir
        / "_abrxs_diarize.py"
    )

    runner.write_text(
        r'''
from pyannote.audio import Pipeline
import json
import sys

audio, output, token = sys.argv[1:4]

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-community-1",
    token=token,
)

result = pipeline(audio)

annotation = (
    getattr(
        result,
        "exclusive_speaker_diarization",
        None,
    )
    or
    getattr(
        result,
        "speaker_diarization",
        result,
    )
)

segments = []

for turn, _, speaker in annotation.itertracks(
    yield_label=True
):
    segments.append(
        {
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker": str(speaker),
        }
    )

with open(
    output,
    "w",
    encoding="utf-8",
) as handle:
    json.dump(
        {
            "segments": segments
        },
        handle,
        ensure_ascii=False,
        indent=2,
    )
'''.strip()
        + "\n",
        encoding="utf-8",
    )

    try:
        if log:
            log(
                "Diarización: detectando "
                "Speaker 1, Speaker 2, etc."
            )

        subprocess.run(
            [
                str(python),
                str(runner),
                str(audio),
                str(output),
                token,
            ],
            check=True,
        )

        return output

    except Exception as exc:

        if log:
            log(
                "Diarización no disponible: "
                f"{exc}"
            )

        return None

    finally:
        try:
            runner.unlink()
        except Exception:
            pass


###############################################################################
# REVISIÓN HTML
###############################################################################

def write_review(
    transcript_dir,
    video,
    issues,
    speakers,
    names,
):
    transcript_dir = Path(
        transcript_dir
    )

    detected_speakers = sorted(
        set(
            segment.get(
                "speaker"
            )
            for segment
            in speakers
            if segment.get(
                "speaker"
            )
        )
    )

    review_data = {
        "issues": issues,
        "speakers": (
            detected_speakers
        ),
        "speaker_names": names,
    }

    (
        transcript_dir
        / "REVISION_TRANSCRIPCION.json"
    ).write_text(
        json.dumps(
            review_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    media_name = ""

    if (
        video
        and Path(video).is_file()
    ):
        extension = (
            Path(video).suffix.lower()
            or ".mp4"
        )

        media_link = (
            transcript_dir
            / (
                "MASTER_PARA_REVISION"
                + extension
            )
        )

        try:
            if (
                media_link.exists()
                or media_link.is_symlink()
            ):
                media_link.unlink()

            media_link.symlink_to(
                Path(video)
            )

            media_name = (
                media_link.name
            )

        except Exception:
            media_name = (
                Path(video).as_uri()
            )

    payload = (
        json.dumps(
            review_data,
            ensure_ascii=False,
        )
        .replace(
            "</",
            "<\\/",
        )
    )

    page = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Revisar transcripción · Abrxs-Canter</title>

<style>
body {{
  font: 15px -apple-system, BlinkMacSystemFont, sans-serif;
  margin: 24px;
  max-width: 1200px;
  line-height: 1.45;
}}

video {{
  width: 100%;
  max-height: 420px;
  background: #111;
  border-radius: 12px;
}}

.row {{
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 12px;
  margin: 10px 0;
}}

.meta {{
  color: #666;
  font-size: 12px;
}}

input {{
  font: inherit;
  padding: 7px;
  width: 44%;
}}

button {{
  padding: 7px 11px;
  margin: 4px;
}}
</style>
</head>

<body>

<h1>Revisar transcripción</h1>

<p>
Aquí aparecen palabras que Abrxs-Canter considera dudosas.
Puedes escucharlas en el máster, aceptar una sugerencia o
escribir la corrección manual.
</p>

<p>
Al terminar pulsa <b>Exportar correcciones</b> y guarda
<code>CORRECCIONES_TRANSCRIPCION.json</code> dentro de esta
misma carpeta <code>TRANSCRIPCIONES</code>.
La próxima regeneración las aplicará sin volver a ejecutar Whisper.
</p>

<video
  id="video"
  controls
  src="{html.escape(media_name)}">
</video>

<h2>Speakers</h2>
<div id="speakers"></div>

<h2>Palabras para revisar</h2>
<div id="issues"></div>

<button onclick="saveCorrections()">
Exportar correcciones
</button>

<script>
const DATA = {payload};

const corrections = [];
const names = {{ ...DATA.speaker_names }};
const video = document.getElementById("video");

function playAt(start, end) {{
  video.currentTime = Math.max(0, start - 2);
  video.play();

  const milliseconds =
    Math.max(3000, (end - start + 4) * 1000);

  setTimeout(() => {{
    if (video.currentTime > end + 1.5) {{
      video.pause();
    }}
  }}, milliseconds);
}}

function renderSpeakers() {{
  const box = document.getElementById("speakers");

  DATA.speakers.forEach((speaker) => {{
    const row = document.createElement("div");
    row.className = "row";

    row.innerHTML = `
      <b>${{speaker}}</b>
      →
      <input
        placeholder="Nombre, por ejemplo Pamela"
        value="${{names[speaker] || ""}}">
    `;

    row.querySelector("input").oninput = (event) => {{
      names[speaker] = event.target.value;
    }};

    box.appendChild(row);
  }});
}}

function renderIssues() {{
  const box = document.getElementById("issues");

  DATA.issues.forEach((item) => {{
    const row = document.createElement("div");
    row.className = "row";

    const probability =
      item.confidence === null ||
      item.confidence === undefined
      ? "—"
      : Number(item.confidence).toFixed(3);

    row.innerHTML = `
      <div class="meta">
        ${{Number(item.start).toFixed(3)}} –
        ${{Number(item.end).toFixed(3)}}
        · ${{item.reason}}
        · confianza ${{probability}}
      </div>

      <p>
        <b>Original:</b>
        ${{item.original}}
      </p>

      <p>
        ${{item.context || ""}}
      </p>

      <button class="listen">
        ▶ Escuchar
      </button>

      <input
        class="correction"
        placeholder="Escribe la corrección"
        value="${{item.suggested || ""}}">

      <button class="accept">
        Aceptar
      </button>
    `;

    row.querySelector(".listen").onclick = () => {{
      playAt(
        Number(item.start),
        Number(item.end)
      );
    }};

    row.querySelector(".accept").onclick = () => {{
      const corrected =
        row.querySelector(".correction")
        .value
        .trim();

      if (!corrected) {{
        return;
      }}

      corrections.push({{
        start: Number(item.start),
        end: Number(item.end),
        original: item.original,
        corrected,
        reason: "manual_review"
      }});

      row.style.opacity = "0.45";
    }};

    box.appendChild(row);
  }});
}}

function saveCorrections() {{
  const content = {{
    corrections,
    speaker_names: names
  }};

  const blob = new Blob(
    [
      JSON.stringify(
        content,
        null,
        2
      )
    ],
    {{
      type: "application/json"
    }}
  );

  const link = document.createElement("a");

  link.href =
    URL.createObjectURL(blob);

  link.download =
    "CORRECCIONES_TRANSCRIPCION.json";

  link.click();

  URL.revokeObjectURL(
    link.href
  );
}}

renderSpeakers();
renderIssues();
</script>

</body>
</html>
"""

    (
        transcript_dir
        / "REVISAR_TRANSCRIPCION.html"
    ).write_text(
        page,
        encoding="utf-8",
    )


###############################################################################
# SALIDAS
###############################################################################

def save_transcript_suite(
    words,
    source,
    root,
    brand_path=None,
    video=None,
    WordClass=None,
    log=None,
):
    root = Path(root)

    transcript_dir = (
        root
        / "TRANSCRIPCIONES"
    )

    transcript_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        WordClass is None
        and words
    ):
        WordClass = type(
            words[0]
        )

    # correcciones manuales existentes
    words, manual_applied = (
        apply_manual(
            words,
            root,
            WordClass,
        )
    )

    # marca / glosario
    brand_terms = (
        extract_brand_terms(
            brand_path
        )
    )

    (
        brand_review,
        brand_auto,
    ) = brand_quality(
        words,
        brand_terms,
    )

    # otras dudas
    issues = (
        quality_issues(words)
        + brand_review
    )

    # diarización opcional y cacheada
    run_diarization(
        root,
        source,
        log,
    )

    speakers = load_speakers(
        root
    )

    names = speaker_names(
        root
    )

    payload = {
        "status": (
            "word_aligned_clean"
        ),
        "source": str(source),
        "word_count": len(words),
        "words": [],
    }

    for word in words:
        data = {
            "text": word.text,
            "start": word.start,
            "end": word.end,
            "probability": (
                word.probability
            ),
        }

        speaker = speaker_for(
            word.start,
            word.end,
            speakers,
        )

        if speaker:
            data["speaker"] = (
                speaker
            )

            data["speaker_name"] = (
                names.get(speaker)
                or speaker
            )

        payload["words"].append(
            data
        )

    word_json = (
        transcript_dir
        / "TRANSCRIPCION_PALABRA_POR_PALABRA.json"
    )

    word_json.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    word_tsv = (
        transcript_dir
        / "TRANSCRIPCION_PALABRA_POR_PALABRA.tsv"
    )

    with word_tsv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
        )

        writer.writerow(
            [
                "start",
                "end",
                "speaker",
                "word",
                "probability",
            ]
        )

        for word in payload["words"]:
            writer.writerow(
                [
                    f'{word["start"]:.3f}',
                    f'{word["end"]:.3f}',
                    word.get(
                        "speaker_name",
                        "",
                    ),
                    word["text"],
                    (
                        ""
                        if (
                            word["probability"]
                            is None
                        )
                        else word["probability"]
                    ),
                ]
            )

    phrases = build_phrases(
        words
    )

    for item in phrases:
        speaker = speaker_for(
            item["start"],
            item["end"],
            speakers,
        )

        if speaker:
            item["speaker"] = (
                speaker
            )

            item["speaker_name"] = (
                names.get(speaker)
                or speaker
            )

    compact_json = (
        transcript_dir
        / "TRANSCRIPCION_COMPACTA.json"
    )

    compact_json.write_text(
        json.dumps(
            {
                "status": (
                    "phrase_aligned_clean"
                ),
                "source": str(source),
                "phrase_count": (
                    len(phrases)
                ),
                "segments": phrases,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # TXT limpio estilo SRT,
    # pero sin corchetes técnicos
    lines = []

    srt_lines = []

    clean_lines = []

    for index, item in enumerate(
        phrases,
        1,
    ):
        speaker_name = (
            item.get(
                "speaker_name"
            )
        )

        prefix = (
            f"{speaker_name}: "
            if speaker_name
            else ""
        )

        lines.extend(
            [
                (
                    f'{tc(item["start"])}'
                    " → "
                    f'{tc(item["end"])}'
                ),
                prefix + item["text"],
                "",
            ]
        )

        srt_lines.extend(
            [
                str(index),
                (
                    f'{tc(item["start"], True)}'
                    " --> "
                    f'{tc(item["end"], True)}'
                ),
                prefix + item["text"],
                "",
            ]
        )

        clean_lines.append(
            prefix
            + item["text"]
        )

    compact_txt = (
        transcript_dir
        / "TRANSCRIPCION_COMPACTA.txt"
    )

    compact_txt.write_text(
        "\n".join(lines).rstrip()
        + "\n",
        encoding="utf-8",
    )

    (
        transcript_dir
        / "TRANSCRIPCION.srt"
    ).write_text(
        "\n".join(
            srt_lines
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )

    (
        transcript_dir
        / "TRANSCRIPCION_LIMPIA.txt"
    ).write_text(
        "\n".join(
            clean_lines
        )
        + "\n",
        encoding="utf-8",
    )

    (
        transcript_dir
        / "CORRECCIONES_Y_DUDAS.json"
    ).write_text(
        json.dumps(
            {
                "automatic": (
                    brand_auto
                ),
                "manual_applied": (
                    manual_applied
                ),
                "review_required": (
                    issues
                ),
                "brand_terms": (
                    brand_terms
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if (
        speakers
        and not (
            transcript_dir
            / "SPEAKER_NAMES.json"
        ).exists()
    ):
        unique_speakers = sorted(
            set(
                segment.get(
                    "speaker"
                )
                for segment
                in speakers
                if segment.get(
                    "speaker"
                )
            )
        )

        (
            transcript_dir
            / "SPEAKER_NAMES.json"
        ).write_text(
            json.dumps(
                {
                    speaker: ""
                    for speaker
                    in unique_speakers
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    write_review(
        transcript_dir,
        video,
        issues,
        speakers,
        names,
    )

    if log:
        log(
            "Transcripción limpia: "
            f"{len(words)} palabras · "
            f"{len(phrases)} bloques · "
            f"{len(issues)} elementos para revisar."
        )

        log(
            "Revisión interactiva: "
            + str(
                transcript_dir
                / "REVISAR_TRANSCRIPCION.html"
            )
        )

    return (
        word_json,
        compact_txt,
    )


###############################################################################
# REPARAR UNA TRANSCRIPCIÓN EXISTENTE SIN WHISPER
###############################################################################

def repair_existing(
    raw_json,
    root,
    video=None,
    brand=None,
):
    class Word:
        def __init__(
            self,
            text,
            start,
            end,
            probability=None,
        ):
            self.text = text
            self.start = start
            self.end = end
            self.probability = probability

    parsed = parse_whisper_cpp_json(
        Path(raw_json),
        Word,
    )

    if not parsed:
        raise SystemExit(
            "No se reconoce el JSON de whisper.cpp."
        )

    words, _ = parsed

    return save_transcript_suite(
        words,
        Path(raw_json),
        Path(root),
        brand,
        video,
        Word,
        print,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repair-existing",
        action="store_true",
    )

    parser.add_argument(
        "--raw",
    )

    parser.add_argument(
        "--root",
    )

    parser.add_argument(
        "--video",
    )

    parser.add_argument(
        "--brand",
    )

    args = parser.parse_args()

    if args.repair_existing:
        repair_existing(
            args.raw,
            args.root,
            args.video,
            args.brand,
        )


if __name__ == "__main__":
    main()
