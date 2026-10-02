#!/usr/bin/env python3
"""
abrxs-Canter — transcripción, alineación, corte y edición local para macOS.

Entradas:
  * video máster
  * HTML/MD/TXT editorial
  * transcript word-level opcional (JSON/TSV/TXT)

Si falta el transcript, usa MLX Whisper con timestamps por palabra. Los cortes
se guardan una sola vez en caché y luego se copian dentro de la carpeta de cada
video. Las secciones reutilizadas se marcan como DUPLICADA_DE_<video>.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import difflib
import hashlib
import html as html_lib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Optional


APP_NAME = "abrxs-Canter"
APP_VERSION = "3.4.1"
CONFLICT_SECONDS = 1.0
DEFAULT_PAD_BEFORE = 0.20
DEFAULT_PAD_AFTER = 0.20
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
MIN_ALIGNMENT_SCORE = 0.72
VIDEO_BITRATE = "40M"
VIDEO_MAXRATE = "48M"
VIDEO_BUFSIZE = "80M"
AUDIO_BITRATE = "192k"


@dataclasses.dataclass
class Word:
    text: str
    start: float
    end: float
    probability: Optional[float] = None


@dataclasses.dataclass
class Segment:
    id: str
    order: int
    text: str = ""
    role: str = "SECCION"
    start: Optional[float] = None
    end: Optional[float] = None
    part_id: str = ""
    source_unit_id: str = ""
    aligned_start: Optional[float] = None
    aligned_end: Optional[float] = None
    alignment_score: Optional[float] = None
    alignment_status: str = "NOT_RUN"


@dataclasses.dataclass
class Voiceover:
    id: str
    label: str
    text: str
    placement: str
    duration: Optional[float] = None


@dataclasses.dataclass
class XRoll:
    id: str
    label: str
    start: Optional[float] = None       # tiempo dentro del video ensamblado
    end: Optional[float] = None
    source_start: Optional[float] = None
    source_end: Optional[float] = None
    part_id: str = ""
    info: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Piece:
    id: str
    title: str
    kind: str = "video"
    segments: list[Segment] = dataclasses.field(default_factory=list)
    voiceovers: list[Voiceover] = dataclasses.field(default_factory=list)
    xrolls: list[XRoll] = dataclasses.field(default_factory=list)
    source_format: str = ""
    selected: bool = True


def log(message: str) -> None:
    print(message, flush=True)


def emit_event(event: str, **payload: Any) -> None:
    data = {"event": event, "timestamp": time.time(), **payload}
    print("ABRXS_CANTER_EVENT:" + json.dumps(data, ensure_ascii=False), flush=True)


def safe_name(value: str, fallback: str = "SIN_NOMBRE", limit: int = 100) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return (value or fallback)[:limit]


def parse_time(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    try:
        if ":" not in text:
            return float(text)
        parts = [float(p) for p in text.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except ValueError:
        return None
    return None


def timecode(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/D"
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def normalize_token(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", text)


def editorial_tokens(text: str) -> list[str]:
    return [t for t in (normalize_token(x) for x in re.findall(r"[\wÀ-ÿ']+", text)) if t]


def extract_app_data(source: str) -> Optional[dict[str, Any]]:
    match = re.search(
        r"<script[^>]*id=[\"']app-data[\"'][^>]*>(.*?)</script>",
        source,
        re.I | re.S,
    )
    if match:
        try:
            return json.loads(html_lib.unescape(match.group(1)).strip())
        except json.JSONDecodeError:
            pass
    # Algunos visores antiguos guardan un objeto JSON directamente en una variable.
    for marker in ("const DATA=", "window.APP_DATA=", "window.__DATA__="):
        pos = source.find(marker)
        if pos < 0:
            continue
        brace = source.find("{", pos + len(marker))
        if brace < 0:
            continue
        depth = 0
        in_string = False
        escaped = False
        for i in range(brace, len(source)):
            char = source[i]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(source[brace : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def parse_html_editorial(path: Path) -> list[Piece]:
    source = path.read_text(encoding="utf-8", errors="replace")
    data = extract_app_data(source)
    if not data:
        return []
    pieces: list[Piece] = []
    for raw in data.get("pieces", []):
        piece_id = str(raw.get("canonicalId") or raw.get("id") or f"VIDEO_{len(pieces)+1:02d}")
        piece = Piece(
            id=piece_id,
            title=str(raw.get("title") or piece_id),
            kind=str(raw.get("type") or raw.get("format") or "video"),
            source_format="HTML",
            selected=raw.get("selected", True) is not False,
        )

        ranges = raw.get("sourceRanges")
        if isinstance(ranges, list) and ranges:
            for index, item in enumerate(sorted(ranges, key=lambda x: x.get("order", 999999))):
                piece.segments.append(
                    Segment(
                        id=str(item.get("id") or f"{piece_id}_S{index+1:02d}"),
                        order=int(item.get("order") or index + 1),
                        text=str(item.get("text") or item.get("literal_excerpt") or ""),
                        role=str(item.get("role") or "SECCION"),
                        start=parse_time(item.get("startTc", item.get("start"))),
                        end=parse_time(item.get("endTc", item.get("end"))),
                        part_id=str(item.get("partId") or ""),
                        source_unit_id=str(item.get("id") or ""),
                    )
                )
        else:
            parts = raw.get("parts") or []
            for index, item in enumerate(parts):
                start = parse_time(item.get("sourceStart", item.get("start")))
                end = parse_time(item.get("sourceEnd", item.get("end")))
                if start is None and end is None and not item.get("text"):
                    continue
                piece.segments.append(
                    Segment(
                        id=str(item.get("id") or item.get("partId") or f"{piece_id}_S{index+1:02d}"),
                        order=int(item.get("index") or item.get("order") or index + 1),
                        text=str(item.get("text") or item.get("literal_excerpt") or ""),
                        role=str(item.get("role") or item.get("title") or "SECCION"),
                        start=start,
                        end=end,
                        part_id=str(item.get("partId") or item.get("id") or ""),
                        source_unit_id=str(item.get("sourceUnitId") or ""),
                    )
                )
            piece.segments.sort(key=lambda s: s.order)

        options = raw.get("voiceoverOptions") or {}
        if isinstance(options, dict):
            for key, option in options.items():
                if not isinstance(option, dict):
                    continue
                placement_parts = []
                if option.get("beforeText"):
                    placement_parts.append(f"DESPUÉS DE: {option['beforeText']}")
                if option.get("afterText"):
                    placement_parts.append(f"ANTES DE: {option['afterText']}")
                piece.voiceovers.append(
                    Voiceover(
                        id=str(key),
                        label=str(option.get("label") or key),
                        text=str(option.get("text") or ""),
                        placement="\n".join(placement_parts) or "Posición indicada por el orden editorial",
                        duration=parse_time(option.get("durationSeconds")),
                    )
                )
        elif isinstance(options, list):
            for index, option in enumerate(options):
                if isinstance(option, dict):
                    piece.voiceovers.append(
                        Voiceover(
                            id=str(option.get("id") or f"VO_{index+1:02d}"),
                            label=str(option.get("label") or option.get("role") or "VOICEOVER"),
                            text=str(option.get("text") or ""),
                            placement=str(option.get("placement") or "Posición indicada por el orden editorial"),
                            duration=parse_time(option.get("durationSeconds")),
                        )
                    )

        # R10.1: X-rolls en timeline. Se usa la ruta source para no duplicar voA/voB.
        timeline_xrs = []
        for item in raw.get("timeline") or []:
            marker = " ".join(str(item.get(k, "")) for k in ("track", "type", "kind")).lower()
            routes = item.get("routes") or []
            if "xr" in marker and (not routes or "source" in routes):
                timeline_xrs.append(item)
        seen_xr: set[str] = set()
        for index, item in enumerate(timeline_xrs):
            xr_id = str(item.get("id") or f"{piece_id}_XR{index+1:02d}")
            if xr_id in seen_xr:
                continue
            seen_xr.add(xr_id)
            piece.xrolls.append(
                XRoll(
                    id=xr_id,
                    label=str(item.get("label") or item.get("function") or xr_id),
                    start=parse_time(item.get("start")),
                    end=parse_time(item.get("end")),
                    source_start=parse_time(item.get("sourceStart")),
                    source_end=parse_time(item.get("sourceEnd")),
                    part_id=str(item.get("partId") or ""),
                    info=item,
                )
            )

        # Otros visores: X-rolls directamente en piece.xrs.
        for index, item in enumerate(raw.get("xrs") or []):
            if not isinstance(item, dict):
                continue
            xr_id = str(item.get("id") or f"{piece_id}_XR{index+1:02d}")
            if xr_id in seen_xr:
                continue
            seen_xr.add(xr_id)
            piece.xrolls.append(
                XRoll(
                    id=xr_id,
                    label=str(item.get("label") or item.get("function") or xr_id),
                    start=parse_time(item.get("t0", item.get("start"))),
                    end=parse_time(item.get("t1", item.get("end"))),
                    source_start=parse_time(item.get("sourceStart")),
                    source_end=parse_time(item.get("sourceEnd")),
                    part_id=str(item.get("partId") or ""),
                    info=item,
                )
            )
        pieces.append(piece)
    return pieces


def strip_fences(text: str) -> str:
    return re.sub(r"(?m)^```(?:text|md|markdown)?\s*$|^```\s*$", "", text)


def parse_text_editorial(path: Path) -> list[Piece]:
    text = strip_fences(path.read_text(encoding="utf-8", errors="replace"))
    # Reconoce A01, **A01.txt**, INTRO_01, CH-T01 y "CLIP VERTICAL C01".
    header = re.compile(
        r"(?m)^\s*(?:#{1,6}\s*)?(?:\*\*)?"
        r"(?:(?i:CLIP(?:\s+(?:VERTICAL|HORIZONTAL|VIDEO|INTRO|REEL))?)\s+)?"
        r"([A-Z][A-Z0-9_-]{1,30})(?i:\.txt)?(?:\*\*)?\s*$"
    )
    matches = list(header.finditer(text))
    pieces: list[Piece] = []
    for index, match in enumerate(matches):
        piece_id = match.group(1)
        block = text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        start_match = re.search(r"(?im)^\s*Inicio\s*:\s*([0-9:.,]+)", block)
        end_match = re.search(r"(?im)^\s*Final\s*:\s*([0-9:.,]+)", block)
        title_match = re.search(r"(?im)^\s*T[IÍ]TULO(?:\s+EDITORIAL)?\s*:\s*(.+)$", block)
        transcript_match = re.search(
            r"(?is)TRANSCRIPCI[ÓO]N(?:\s+CONTINUA|\s+LITERAL)?(?:\s*\([^\n)]*\))?\s*\n"
            r"(.*?)(?=\n\s*(?:TRAZABILIDAD\s+DE\s+LOS\s+TRAMOS|NOTAS?\s+DE\s+VERIFICACI[ÓO]N|NOTA\s+DE\s+FUENTE|POR\s+QU[EÉ]\s+FUNCIONA|ESTRUCTURA\s+NARRATIVA|#{1,6}\s|$))",
            block,
        )
        literal = transcript_match.group(1).strip() if transcript_match else ""
        if not literal:
            hook_match = re.search(r"(?is)HOOK\s+REAL\s*:\s*[\"“](.*?)[\"”]\s*(?:\n|$)", block)
            if hook_match:
                literal = hook_match.group(1).strip()
        start = parse_time(start_match.group(1)) if start_match else None
        end = parse_time(end_match.group(1)) if end_match else None
        trace_ranges = [
            (int(item.group(1)), parse_time(item.group(2)), parse_time(item.group(3)))
            for item in re.finditer(
                r"(?im)^\s*Bloque\s+(\d+)\s*:\s*([0-9:.,]+)\s*(?:->|-->|→)\s*([0-9:.,]+)",
                block,
            )
        ]
        literal_parts: dict[int, str] = {}
        part_markers = list(re.finditer(r"(?im)^\s*\(Bloque\s+(\d+)\)\s*$", literal))
        if part_markers:
            for part_index, part_match in enumerate(part_markers):
                literal_parts[int(part_match.group(1))] = literal[
                    part_match.end() : part_markers[part_index + 1].start() if part_index + 1 < len(part_markers) else len(literal)
                ].strip()
        if start is None and end is None and not literal and not trace_ranges:
            continue
        piece = Piece(
            id=piece_id,
            title=title_match.group(1).strip() if title_match else piece_id,
            source_format=path.suffix.upper().lstrip("."),
        )
        if trace_ranges:
            for order, traced_start, traced_end in trace_ranges:
                piece.segments.append(Segment(
                    id=f"{piece_id}_S{order:02d}", order=order,
                    text=literal_parts.get(order, literal if len(trace_ranges) == 1 else ""),
                    role="CLIP", start=traced_start, end=traced_end,
                ))
        else:
            piece.segments.append(Segment(
                id=f"{piece_id}_S01", order=1, text=literal,
                role="CLIP", start=start, end=end,
            ))
        pieces.append(piece)
    return pieces


def parse_json_editorial_data(data: Any, source_format: str = "JSON") -> list[Piece]:
    if isinstance(data, list):
        raw_pieces = data
    elif isinstance(data, dict):
        raw_pieces = data.get("clips") or data.get("pieces") or data.get("videos") or []
    else:
        raw_pieces = []
    pieces: list[Piece] = []
    for index, raw in enumerate(raw_pieces):
        if not isinstance(raw, dict):
            continue
        piece_id = str(raw.get("id") or raw.get("clip_id") or f"CLIP_{index+1:02d}")
        piece = Piece(
            id=piece_id,
            title=str(raw.get("title") or raw.get("titulo") or piece_id),
            kind=str(raw.get("type") or raw.get("tipo") or "video"),
            source_format=source_format,
            selected=raw.get("selected", True) is not False,
        )
        raw_segments = raw.get("segments") or raw.get("secciones") or raw.get("parts") or []
        if not raw_segments and any(key in raw for key in ("start", "end", "inicio", "final", "text", "texto")):
            raw_segments = [raw]
        for seg_index, item in enumerate(raw_segments):
            if not isinstance(item, dict):
                continue
            piece.segments.append(Segment(
                id=str(item.get("id") or f"{piece_id}_S{seg_index+1:02d}"),
                order=int(item.get("order") or item.get("orden") or seg_index + 1),
                text=str(item.get("text") or item.get("texto") or item.get("transcript") or ""),
                role=str(item.get("role") or item.get("rol") or "SECCION"),
                start=parse_time(item.get("start", item.get("inicio"))),
                end=parse_time(item.get("end", item.get("final"))),
                part_id=str(item.get("part_id") or item.get("partId") or ""),
                source_unit_id=str(item.get("source_unit_id") or item.get("sourceUnitId") or ""),
            ))
        for vo_index, item in enumerate(raw.get("voiceovers") or []):
            if isinstance(item, dict):
                piece.voiceovers.append(Voiceover(
                    id=str(item.get("id") or f"VO_{vo_index+1:02d}"),
                    label=str(item.get("label") or item.get("role") or "VOICEOVER"),
                    text=str(item.get("text") or item.get("texto") or ""),
                    placement=str(item.get("placement") or item.get("ubicacion") or "Orden editorial"),
                    duration=parse_time(item.get("duration", item.get("duracion"))),
                ))
        for xr_index, item in enumerate(raw.get("xrolls") or raw.get("xr") or []):
            if isinstance(item, dict):
                piece.xrolls.append(XRoll(
                    id=str(item.get("id") or f"{piece_id}_XR{xr_index+1:02d}"),
                    label=str(item.get("label") or item.get("titulo") or f"XR {xr_index+1}"),
                    start=parse_time(item.get("start", item.get("inicio"))),
                    end=parse_time(item.get("end", item.get("final"))),
                    source_start=parse_time(item.get("source_start", item.get("sourceStart"))),
                    source_end=parse_time(item.get("source_end", item.get("sourceEnd"))),
                    part_id=str(item.get("part_id") or item.get("partId") or ""),
                    info=item,
                ))
        if piece.segments:
            piece.segments.sort(key=lambda segment: segment.order)
            pieces.append(piece)
    return pieces


def parse_editorial(path: Path) -> list[Piece]:
    raw_text = path.read_text(encoding="utf-8-sig", errors="replace")
    if re.search(r"(?im)^\s*PLANTILLA (?:PARA REPARAR|IA)|^\s*SUBE A LA IA\s*:", raw_text):
        raise ValueError("Seleccionaste una plantilla de instrucciones, no los cortes. Sube esa plantilla y tu editorial a la IA e importa su respuesta como DECISIONES_ABRXS.txt o .json. No se cortará el clip de ejemplo.")
    if path.suffix.lower() == ".json":
        return validate_editorial_pieces(parse_json_editorial_data(json.loads(raw_text)))
    if path.suffix.lower() in {".html", ".htm"}:
        pieces = parse_html_editorial(path)
        if pieces:
            return validate_editorial_pieces(pieces)
    if path.suffix.lower() in {".txt", ".md"}:
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", raw_text, re.I | re.S)
        candidates = fenced or [raw_text.strip()]
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate.startswith(("{", "[")):
                # Una IA puede añadir una frase antes del objeto JSON.
                match = re.search(r'\{\s*"(?:clips|pieces|videos)"\s*:', candidate)
                if not match:
                    continue
                candidate = candidate[match.start():]
            try:
                data, _ = json.JSONDecoder().raw_decode(candidate)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON editorial inválido: línea {exc.lineno}, columna {exc.colno}. No se importaron cortes.") from exc
            pieces = parse_json_editorial_data(data, path.suffix.upper().lstrip("."))
            if pieces:
                return validate_editorial_pieces(pieces)
            raise ValueError("El JSON no contiene clips con segmentos. Usa la plantilla de reparación para convertirlo.")
    return validate_editorial_pieces(parse_text_editorial(path))


def validate_editorial_pieces(pieces: list[Piece]) -> list[Piece]:
    ids = set()
    for piece in pieces:
        if piece.id in ids:
            raise ValueError(f"ID de clip duplicado: {piece.id}. Asigna un ID diferente a cada clip.")
        ids.add(piece.id)
        orders = set()
        segment_ids = set()
        for segment in piece.segments:
            if segment.order in orders or segment.id in segment_ids:
                raise ValueError(f"{piece.id}: orden o ID de sección duplicado.")
            orders.add(segment.order); segment_ids.add(segment.id)
            if (segment.start is None) != (segment.end is None):
                raise ValueError(f"{piece.id}/{segment.id}: falta Inicio o Final; aporta ambos o deja ambos en null con texto literal.")
            if segment.start is not None and (not math.isfinite(segment.start) or not math.isfinite(segment.end) or segment.start < 0 or segment.end <= segment.start):
                raise ValueError(f"{piece.id}/{segment.id}: intervalo inválido.")
            if segment.start is None and not segment.text.strip():
                raise ValueError(f"{piece.id}/{segment.id}: no hay timestamps ni texto literal para encontrar el corte.")
    return pieces


def collect_word_dicts(obj: Any, found: list[Word]) -> None:
    if isinstance(obj, dict):
        text = obj.get("word", obj.get("text", obj.get("token")))
        start = parse_time(obj.get("start", obj.get("t0")))
        end = parse_time(obj.get("end", obj.get("t1")))
        # whisper.cpp --output-json-full guarda los tiempos dentro de offsets
        # (milisegundos) o timestamps (texto), en vez de start/end.
        offsets = obj.get("offsets")
        timestamps = obj.get("timestamps")
        if (start is None or end is None) and isinstance(offsets, dict):
            raw_start, raw_end = offsets.get("from"), offsets.get("to")
            if isinstance(raw_start, (int, float)) and isinstance(raw_end, (int, float)):
                start, end = float(raw_start) / 1000.0, float(raw_end) / 1000.0
        if (start is None or end is None) and isinstance(timestamps, dict):
            start, end = parse_time(timestamps.get("from")), parse_time(timestamps.get("to"))
        if isinstance(text, str) and text.strip() and start is not None and end is not None:
            # Evita añadir segmentos completos cuando el mismo dict contiene una lista words/tokens.
            if not isinstance(obj.get("words"), list) and not isinstance(obj.get("tokens"), list):
                found.append(Word(text.strip(), start, end, obj.get("probability", obj.get("prob"))))
        for key, value in obj.items():
            if key not in {"text", "word", "token"}:
                collect_word_dicts(value, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_word_dicts(item, found)


def load_transcript(path: Path) -> tuple[list[Word], dict[str, Any]]:
    suffix = path.suffix.lower()
    words: list[Word] = []
    raw: dict[str, Any] = {"source": str(path)}
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        collect_word_dicts(data, words)
        raw["original"] = data
    elif suffix in {".tsv", ".csv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=delimiter):
                text = row.get("word") or row.get("text") or ""
                start = parse_time(row.get("start"))
                end = parse_time(row.get("end"))
                if text and start is not None and end is not None:
                    words.append(Word(text.strip(), start, end))
    else:
        # Formatos: start<TAB>end<TAB>word o [00:00:01.000 --> 00:00:01.300] word
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"\s*\[?([0-9:.,]+)\s*(?:-->|\t|\|)\s*([0-9:.,]+)\]?\s*(?:\t|\|)?\s*(.+)", line)
            if match:
                start, end = parse_time(match.group(1)), parse_time(match.group(2))
                if start is not None and end is not None:
                    words.append(Word(match.group(3).strip(), start, end))
    # Quita duplicados exactos producidos por recorridos JSON genéricos.
    unique: dict[tuple[str, float, float], Word] = {}
    for word in words:
        key = (word.text, round(word.start, 4), round(word.end, 4))
        unique[key] = word
    words = sorted(unique.values(), key=lambda w: (w.start, w.end))
    if not words:
        raise RuntimeError(f"El transcript no contiene timestamps por palabra reconocibles: {path}")
    return words, raw


def find_local_mlx_model() -> str:
    cache = Path.home() / ".cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/snapshots"
    if cache.is_dir():
        snapshots = sorted((p for p in cache.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
        if snapshots:
            return str(snapshots[0])
    return DEFAULT_MODEL


def find_whisper_cpp_model() -> Optional[str]:
    configured = os.environ.get("ABRAXAS_WHISPER_CPP_MODEL")
    if configured and Path(configured).is_file():
        return configured
    roots = [
        Path.home() / ".cache/whisper.cpp",
        Path.home() / "Library/Application Support/VAV/models/whisper",
        Path.home() / "Library/Application Support/whisper.cpp/models",
        Path("/opt/homebrew/share/whisper-cpp/models"),
        Path("/usr/local/share/whisper-cpp/models"),
    ]
    candidates: list[Path] = []
    for root in roots:
        if root.is_dir():
            candidates.extend(root.glob("ggml-*.bin"))
    if not candidates:
        return None
    preferred = sorted(candidates, key=lambda p: ("large" not in p.name, "medium" not in p.name, -p.stat().st_size))
    return str(preferred[0])


def detect_whisper_backends() -> dict[str, Any]:
    mlx_cli = shutil.which("mlx_whisper") or shutil.which("mlx-whisper")
    cpp_cli = shutil.which("whisper-cli") or shutil.which("whisper.cpp")
    cpp_model = find_whisper_cpp_model()
    return {
        "mlx_whisper": {"available": bool(mlx_cli), "executable": mlx_cli, "model": find_local_mlx_model() if mlx_cli else None},
        "whisper_cpp": {"available": bool(cpp_cli), "executable": cpp_cli, "model": cpp_model, "ready": bool(cpp_cli and cpp_model)},
        "selected": "mlx_whisper" if mlx_cli else ("whisper_cpp" if cpp_cli and cpp_model else None),
    }


def generate_transcript(video: Path, cache_dir: Path, model: Optional[str], backends: dict[str, Any]) -> Path:
    audio = cache_dir / "master_16k_mono.wav"
    output = cache_dir / "MASTER_WORD_LEVEL.json"
    if output.exists():
        try:
            load_transcript(output)
            log(f"Usando transcript en caché: {output}")
            return output
        except Exception:
            pass
    run_checked([
        require_command("ffmpeg"), "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)
    ])
    selected = backends.get("selected")
    if selected == "mlx_whisper":
        mlx_cli = backends["mlx_whisper"]["executable"]
        model_value = model or backends["mlx_whisper"]["model"] or DEFAULT_MODEL
        log(f"Transcribiendo con MLX Whisper: {model_value}")
        try:
            run_checked([
                mlx_cli, str(audio), "--model", model_value,
                "--output-name", "MASTER_WORD_LEVEL", "--output-dir", str(cache_dir),
                "--output-format", "json", "--word-timestamps", "True",
                "--verbose", "True",
            ])
        except RuntimeError:
            if not backends["whisper_cpp"]["ready"]:
                raise
            selected = "whisper_cpp"
            log("MLX Whisper falló; abrxs-Canter probará whisper.cpp.")
    if selected == "whisper_cpp":
        cpp_cli = backends["whisper_cpp"]["executable"]
        model_value = model or backends["whisper_cpp"]["model"]
        output_base = cache_dir / "MASTER_WORD_LEVEL"
        log(f"Transcribiendo con whisper.cpp: {model_value}")
        run_checked([
            cpp_cli, "-m", str(model_value), "-f", str(audio), "-l", transcription_language(),
            "-sow", "-ojf", "-of", str(output_base), "-pp",
        ])
    elif selected != "mlx_whisper":
        raise RuntimeError(
            "No hay un motor word-level listo. Instala mlx-whisper o configura "
            "ABRAXAS_WHISPER_CPP_MODEL con la ruta a un modelo ggml de whisper.cpp."
        )
    if not output.exists():
        candidates = list(cache_dir.glob("*.json"))
        if candidates:
            output = max(candidates, key=lambda p: p.stat().st_mtime)
    load_transcript(output)
    return output


def require_command(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f"No se encontró {name} en el sistema.")
    return value


def run_checked(command: list[str]) -> None:
    log("$ " + " ".join(shlex_quote(x) for x in command))
    result = subprocess.run(command)
    if result.returncode:
        raise RuntimeError(f"Falló el comando ({result.returncode}): {command[0]}")


def preflight_media(video: Path, output_root: Path) -> dict[str, Any]:
    ffprobe = require_command("ffprobe")
    probe = subprocess.run([
        ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)
    ], capture_output=True, text=True)
    if probe.returncode:
        raise RuntimeError(f"FFprobe no pudo leer el video: {probe.stderr.strip()}")
    data = json.loads(probe.stdout)
    streams = data.get("streams") or []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    if not video_stream:
        raise RuntimeError("El archivo seleccionado no contiene una pista de video.")
    duration = parse_time((data.get("format") or {}).get("duration")) or parse_time(video_stream.get("duration")) or 0.0
    output_root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(output_root).free
    source_bytes = video.stat().st_size
    recommended = max(2 * 1024**3, int(source_bytes * 1.5))
    if free_bytes < 512 * 1024**2:
        raise RuntimeError("No hay al menos 512 MB libres en la carpeta de destino.")
    payload = {
        "duration": duration, "source_bytes": source_bytes, "free_bytes": free_bytes,
        "recommended_free_bytes": recommended, "low_space_warning": free_bytes < recommended,
        "width": video_stream.get("width"), "height": video_stream.get("height"),
        "frame_rate": video_stream.get("avg_frame_rate"),
        "video_codec": video_stream.get("codec_name"),
        "has_audio": any(item.get("codec_type") == "audio" for item in streams),
    }
    emit_event("preflight_complete", **payload)
    return payload


def shlex_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=+-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def align_text(text: str, words: list[Word]) -> tuple[Optional[float], Optional[float], float]:
    query = editorial_tokens(text)
    corpus_pairs = [(normalize_token(w.text), index) for index, w in enumerate(words)]
    corpus_pairs = [(token, index) for token, index in corpus_pairs if token]
    corpus = [token for token, _ in corpus_pairs]
    if len(query) < 3 or not corpus:
        return None, None, 0.0

    # Linear exact search avoids thousands of fuzzy comparisons for long podcasts.
    prefix = [0] * len(query)
    matched = 0
    for i in range(1, len(query)):
        while matched and query[i] != query[matched]:
            matched = prefix[matched-1]
        if query[i] == query[matched]:
            matched += 1
        prefix[i] = matched
    matched = 0
    for i, token in enumerate(corpus):
        while matched and token != query[matched]:
            matched = prefix[matched-1]
        if token == query[matched]:
            matched += 1
        if matched == len(query):
            return words[corpus_pairs[i-len(query)+1][1]].start, words[corpus_pairs[i][1]].end, 1.0

    positions: dict[str, list[int]] = {}
    for pos, token in enumerate(corpus):
        positions.setdefault(token, []).append(pos)

    candidates: set[int] = set()
    indexed_query = list(enumerate(query))
    indexed_query.sort(key=lambda item: (len(positions.get(item[1], [])) or 10**9, -len(item[1])))
    for query_index, token in indexed_query[:20]:
        for pos in positions.get(token, [])[:300]:
            candidates.add(max(0, pos - query_index))
        if len(candidates) > 1200:
            break
    if not candidates:
        return None, None, 0.0

    lengths = sorted({max(3, int(len(query) * factor)) for factor in (0.72, 0.85, 1.0, 1.15, 1.32)})
    best_score = -1.0
    best_bounds: Optional[tuple[int, int]] = None
    for start in candidates:
        for length in lengths:
            end = min(len(corpus), start + length)
            if end - start < 3:
                continue
            matcher = difflib.SequenceMatcher(None, query, corpus[start:end], autojunk=False)
            score = matcher.ratio()
            if score > best_score:
                blocks = [b for b in matcher.get_matching_blocks() if b.size]
                # A high average score does not prove the opening/closing words.
                # Reject truncated matches instead of silently cutting a sentence short.
                if blocks and blocks[0].a == 0 and blocks[-1].a + blocks[-1].size == len(query):
                    first = start + blocks[0].b
                    last = start + blocks[-1].b + blocks[-1].size - 1
                    best_score = score
                    best_bounds = (first, last)
    if not best_bounds:
        return None, None, 0.0
    first_word = words[corpus_pairs[best_bounds[0]][1]]
    last_word = words[corpus_pairs[best_bounds[1]][1]]
    return first_word.start, last_word.end, round(best_score, 4)


def align_pieces(pieces: list[Piece], words: list[Word]) -> None:
    for piece in pieces:
        for segment in piece.segments:
            if not segment.text.strip():
                segment.alignment_status = "NO_TEXT"
                continue
            nearby = [w for w in words if segment.start is not None and
                      w.end >= max(0, segment.start - 60) and
                      w.start <= (segment.end if segment.end is not None else segment.start + 600) + 60]
            start, end, score = align_text(segment.text, nearby or words)
            if nearby and (start is None or score < MIN_ALIGNMENT_SCORE):
                start, end, score = align_text(segment.text, words)
            segment.alignment_score = score
            if start is None or end is None or score < MIN_ALIGNMENT_SCORE:
                segment.alignment_status = "REVIEW_REQUIRED"
                continue
            segment.aligned_start = start
            segment.aligned_end = end
            if segment.start is not None and segment.end is not None:
                delta = max(abs(segment.start - start), abs(segment.end - end))
                segment.alignment_status = "CONFLICT" if delta > CONFLICT_SECONDS else "VERIFIED"
            else:
                segment.alignment_status = "TEXT_ALIGNED"


def variant_ranges(piece: Piece) -> dict[str, list[tuple[Segment, float, float]]]:
    timestamp: list[tuple[Segment, float, float]] = []
    aligned: list[tuple[Segment, float, float]] = []
    conflict = False
    for segment in piece.segments:
        if segment.start is not None and segment.end is not None:
            timestamp.append((segment, segment.start, segment.end))
        if segment.aligned_start is not None and segment.aligned_end is not None:
            aligned.append((segment, segment.aligned_start, segment.aligned_end))
        if segment.alignment_status == "CONFLICT":
            conflict = True
    if conflict and timestamp and aligned:
        return {"TIMESTAMP": timestamp, "TEXT_ALIGNED": aligned}
    if aligned and len(aligned) == len(piece.segments):
        return {"VERIFIED" if timestamp else "TEXT_ALIGNED": aligned}
    if timestamp:
        return {"TIMESTAMP": timestamp}
    return {}


def range_key(video: Path, start: float, end: float) -> str:
    basis = f"{video.resolve()}|{video.stat().st_size}|{video.stat().st_mtime_ns}|{start:.3f}|{end:.3f}|{VIDEO_BITRATE}"
    return hashlib.sha256(basis.encode()).hexdigest()[:20]


def cut_to_cache(video: Path, start: float, end: float, cache_sections: Path) -> Path:
    start = max(0.0, start - DEFAULT_PAD_BEFORE)
    end = max(start + 0.05, end + DEFAULT_PAD_AFTER)
    key = range_key(video, start, end)
    target = cache_sections / f"{key}.mp4"
    if target.exists() and target.stat().st_size > 1024:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".partial.mp4")
    command = [
        require_command("ffmpeg"), "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video),
        "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "h264_videotoolbox",
        "-b:v", VIDEO_BITRATE, "-maxrate", VIDEO_MAXRATE, "-bufsize", VIDEO_BUFSIZE,
        "-pix_fmt", "yuv420p", "-allow_sw", "1", "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart", str(temp),
    ]
    try:
        run_checked(command)
    except RuntimeError:
        temp.unlink(missing_ok=True)
        log("VideoToolbox no estuvo disponible; reintentando con el codificador H.264 de software.")
        run_checked([
            require_command("ffmpeg"), "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video),
            "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
            "-b:v", VIDEO_BITRATE, "-maxrate", VIDEO_MAXRATE, "-bufsize", VIDEO_BUFSIZE,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-movflags", "+faststart", str(temp),
        ])
    temp.replace(target)
    return target


def copy_materialized(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def concat_sections(section_files: list[Path], destination: Path) -> None:
    if not section_files:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".partial.mp4")
    if len(section_files) == 1:
        shutil.copy2(section_files[0], temp)
        temp.replace(destination)
        return
    list_file = destination.with_suffix(".concat.txt")
    list_file.write_text("".join(f"file '{str(p).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in section_files), encoding="utf-8")
    try:
        run_checked([
            require_command("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-movflags", "+faststart", str(temp),
        ])
        temp.replace(destination)
    finally:
        list_file.unlink(missing_ok=True)
        temp.unlink(missing_ok=True)


def write_voiceovers(piece: Piece, folder: Path) -> list[str]:
    if not piece.voiceovers:
        return []
    folder.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for index, vo in enumerate(piece.voiceovers, 1):
        content = (
            f"VIDEO: {piece.id} — {piece.title}\n"
            f"VOICEOVER: {vo.label}\n"
            f"ID: {vo.id}\n"
            f"DURACIÓN ESTIMADA: {vo.duration if vo.duration is not None else 'N/D'} segundos\n\n"
            f"UBICACIÓN\n{vo.placement}\n\n"
            f"TEXTO\n{vo.text}\n\n"
            "NOTA: Este voiceover no se incluye en el video ensamblado porque no forma parte del máster.\n"
        )
        destination = folder / f"VO_{index:02d}_{safe_name(vo.label)}.txt"
        destination.write_text(content, encoding="utf-8")
        written.append(str(destination))
    return written


def map_xroll_to_source(piece: Piece, xr: XRoll, chosen: list[tuple[Segment, float, float]]) -> tuple[Optional[float], Optional[float]]:
    # Si el HTML ya trae el rango exacto del máster, es la fuente preferida.
    if xr.source_start is not None and xr.source_end is not None:
        # En R10.1 el rango puede ser la unidad completa. Si conocemos t0/t1 y partId,
        # refinamos usando la posición relativa dentro del montaje.
        if xr.start is None or xr.end is None:
            return xr.source_start, xr.source_end
    if xr.start is None or xr.end is None:
        return xr.source_start, xr.source_end
    cursor = 0.0
    overlaps: list[tuple[float, float]] = []
    for segment, source_start, source_end in chosen:
        duration = max(0.0, source_end - source_start)
        local_start, local_end = cursor, cursor + duration
        overlap_start = max(xr.start, local_start)
        overlap_end = min(xr.end, local_end)
        if overlap_end > overlap_start:
            overlaps.append((source_start + overlap_start - local_start, source_start + overlap_end - local_start))
        cursor = local_end
    if len(overlaps) == 1:
        return overlaps[0]
    return xr.source_start, xr.source_end


def export_piece(
    piece: Piece,
    video: Path,
    root: Path,
    cache_sections: Path,
    registry: dict[str, tuple[str, str]],
    export_mode: str,
    export_xrolls: bool,
) -> dict[str, Any]:
    videos_folder = root / "VIDEOS"
    videos_folder.mkdir(parents=True, exist_ok=True)
    resource_root = root / "RECURSOS" / safe_name(piece.id)
    sections_folder = resource_root / "SECCIONES"
    xroll_folder = resource_root / "XROLLS"
    voiceover_folder = resource_root / "VOICEOVERS"

    variants = variant_ranges(piece)
    report: dict[str, Any] = {
        "piece": piece.id, "title": piece.title, "variants": {}, "status": "OK",
        "videos": [], "sections": [], "xrolls": [], "voiceovers": [],
        "source": dataclasses.asdict(piece),
    }
    total_tasks = sum(len(ranges) for ranges in variants.values())
    if export_mode in {"both", "assembled"}:
        total_tasks += len(variants)
    if export_xrolls:
        total_tasks += len(piece.xrolls)
    completed_tasks = 0

    def piece_progress(stage: str, detail: str) -> None:
        emit_event(
            "piece_progress", piece_id=piece.id, title=piece.title,
            stage=stage, detail=detail, completed=completed_tasks,
            total=max(1, total_tasks),
        )

    for variant_name, ranges in variants.items():
        cached_sections: list[Path] = []
        materialized_sections: list[Path] = []
        variant_folder = sections_folder / variant_name
        for index, (segment, start, end) in enumerate(ranges, 1):
            piece_progress("cutting", f"{variant_name}: sección {index} de {len(ranges)}")
            cache_file = cut_to_cache(video, start, end, cache_sections)
            key = range_key(video, max(0.0, start - DEFAULT_PAD_BEFORE), end + DEFAULT_PAD_AFTER)
            duplicate_suffix = ""
            duplicate_of = None
            if key in registry and registry[key][0] != piece.id:
                duplicate_of = registry[key][0]
                duplicate_suffix = f"_DUPLICADA_DE_{safe_name(duplicate_of)}"
            else:
                registry[key] = (piece.id, segment.id)
            filename = f"{safe_name(piece.id)}_{index:02d}_{safe_name(segment.role)}{duplicate_suffix}.mp4"
            if export_mode == "sections" and len(ranges) == 1:
                destination = videos_folder / filename
            else:
                destination = variant_folder / filename
            should_materialize = export_mode == "sections" or (export_mode == "both" and len(ranges) > 1)
            if should_materialize:
                copy_materialized(cache_file, destination)
                materialized_sections.append(destination)
                if destination.parent == videos_folder:
                    report["videos"].append(str(destination))
                else:
                    report["sections"].append(str(destination))
                section_info = (
                    f"VIDEO: {piece.id}\nSECCIÓN: {segment.id}\nROL: {segment.role}\n"
                    f"VARIANTE: {variant_name}\nINICIO MÁSTER: {timecode(start)}\nFINAL MÁSTER: {timecode(end)}\n"
                    f"MARGEN: {DEFAULT_PAD_BEFORE:.2f}s antes / {DEFAULT_PAD_AFTER:.2f}s después\n"
                    f"ESTADO: {segment.alignment_status}\nSCORE: {segment.alignment_score}\n"
                    f"DUPLICADA DE: {duplicate_of or 'NO'}\n\nTEXTO\n{segment.text}\n"
                )
                destination.with_suffix(".txt").write_text(section_info, encoding="utf-8")
            cached_sections.append(cache_file)
            completed_tasks += 1
            piece_progress("cutting", f"{variant_name}: sección {index} terminada")
        if export_mode in {"both", "assembled"} and cached_sections:
            piece_progress("assembling", f"Ensamblando variante {variant_name}")
            complete = videos_folder / f"{safe_name(piece.id)}_{safe_name(piece.title)}_{variant_name}.mp4"
            concat_sections(cached_sections, complete)
            complete.with_suffix(".txt").write_text(
                "\n".join([
                    f"VIDEO: {piece.id}", f"TÍTULO: {piece.title}", f"VARIANTE: {variant_name}",
                    f"SECCIONES: {len(ranges)}", "",
                    *[
                        f"{idx:02d}. {segment.role} | {timecode(start)} → {timecode(end)} | {segment.text}"
                        for idx, (segment, start, end) in enumerate(ranges, 1)
                    ],
                ]) + "\n",
                encoding="utf-8",
            )
            report["videos"].append(str(complete))
            completed_tasks += 1
            piece_progress("assembling", f"Variante {variant_name} terminada")
        report["variants"][variant_name] = len(ranges)

    report["voiceovers"] = write_voiceovers(piece, voiceover_folder)

    if export_xrolls and piece.xrolls and variants:
        preferred = variants.get("TEXT_ALIGNED") or variants.get("VERIFIED") or next(iter(variants.values()))
        for index, xr in enumerate(piece.xrolls, 1):
            piece_progress("xroll", f"X-roll {index} de {len(piece.xrolls)}")
            source_start, source_end = map_xroll_to_source(piece, xr, preferred)
            info = {
                "video": piece.id, "xroll": xr.id, "label": xr.label,
                "timeline_start": xr.start, "timeline_end": xr.end,
                "source_start": source_start, "source_end": source_end,
                "part_id": xr.part_id, "editorial": xr.info,
            }
            base = f"XR_{index:02d}_{safe_name(xr.label)}"
            (xroll_folder / f"{base}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
            (xroll_folder / f"{base}.txt").write_text(
                f"X-ROLL: {xr.label}\nID: {xr.id}\n"
                f"MOMENTO EN VIDEO: {timecode(xr.start)} → {timecode(xr.end)}\n"
                f"RANGO EN MÁSTER: {timecode(source_start)} → {timecode(source_end)}\n"
                f"PARTE: {xr.part_id or 'N/D'}\n",
                encoding="utf-8",
            )
            if source_start is not None and source_end is not None and source_end > source_start:
                cache_file = cut_to_cache(video, source_start, source_end, cache_sections)
                destination = xroll_folder / f"{base}.mp4"
                copy_materialized(cache_file, destination)
                report["xrolls"].append(str(destination))
            completed_tasks += 1
            piece_progress("xroll", f"X-roll {index} terminado")

    if not variants:
        report["status"] = "REVIEW_REQUIRED"
    emit_event("piece_complete", piece_id=piece.id, title=piece.title, status=report["status"])
    return report


def build_phrase_segments(words: list[Word], max_words: int = 14, max_seconds: float = 7.0) -> list[dict[str, Any]]:
    phrases: list[dict[str, Any]] = []
    current: list[Word] = []
    for word in words:
        if current and word.start - current[-1].end > 1.2:
            phrases.append({
                "start": current[0].start, "end": current[-1].end,
                "text": " ".join(item.text.strip() for item in current).strip(),
            })
            current = []
        current.append(word)
        duration = current[-1].end - current[0].start
        closes_sentence = bool(re.search(r"[.!?…][\"'”’)]?$", word.text.strip()))
        if len(current) >= max_words or duration >= max_seconds or (closes_sentence and len(current) >= 5):
            phrases.append({
                "start": current[0].start, "end": current[-1].end,
                "text": " ".join(item.text.strip() for item in current).strip(),
            })
            current = []
    if current:
        phrases.append({
            "start": current[0].start, "end": current[-1].end,
            "text": " ".join(item.text.strip() for item in current).strip(),
        })
    return phrases


def save_normalized_transcript(words: list[Word], source: Path, root: Path) -> tuple[Path, Path]:
    transcript_dir = root / "TRANSCRIPCIONES"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "word_aligned",
        "source": str(source),
        "word_count": len(words),
        "words": [dataclasses.asdict(w) for w in words],
    }
    word_json = transcript_dir / "TRANSCRIPCION_PALABRA_POR_PALABRA.json"
    word_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (transcript_dir / "TRANSCRIPCION_PALABRA_POR_PALABRA.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["start", "end", "word", "probability"])
        for word in words:
            writer.writerow([f"{word.start:.3f}", f"{word.end:.3f}", word.text, word.probability if word.probability is not None else ""])
    phrases = build_phrase_segments(words)
    phrase_payload = {
        "status": "phrase_aligned", "source": str(source),
        "phrase_count": len(phrases), "segments": phrases,
    }
    phrase_json = transcript_dir / "TRANSCRIPCION_COMPACTA.json"
    phrase_json.write_text(json.dumps(phrase_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    phrase_txt = transcript_dir / "TRANSCRIPCION_COMPACTA.txt"
    phrase_txt.write_text("\n".join(
        f"[{timecode(item['start'])} --> {timecode(item['end'])}] {item['text']}"
        for item in phrases
    ) + "\n", encoding="utf-8")
    return word_json, phrase_txt


DEFAULT_STRUCTURE = """ESTRUCTURA EDITORIAL DE CLIPS

- Cada clip debe sostener una idea completa.
- Puede ser continuo o construirse con varias secciones reordenadas.
- Cada sección debe conservar texto literal del transcript.
- Identificar HOOK, DESARROLLO, GIRO, CIERRE y, cuando aplique, VOICEOVER o X-ROLL.
- No resumir ni inventar frases atribuidas a los hablantes.
- Incluir timestamps propuestos y el texto literal continuo de cada sección.
- Si el timestamp y el texto generan dudas, conservar ambos para revisión.
"""


AI_PROMPT = """Actúa como editor narrativo de clips para abrxs-Canter.

Recibirás:
1. Una transcripción compacta con timestamps.
2. Información de marca.
3. Una estructura editorial requerida.

Selecciona y estructura clips usando únicamente texto realmente presente en la transcripción. Puedes reordenar secciones del máster cuando la estructura lo requiera, pero no inventes frases ni conviertas un resumen en una cita literal.

Devuelve JSON válido, sin comentarios antes o después, con este contrato:
{
  "clips": [
    {
      "id": "A01",
      "title": "Título editorial",
      "type": "video",
      "why_it_works": "Explicación breve",
      "segments": [
        {
          "id": "A01_S01",
          "order": 1,
          "role": "HOOK",
          "start": "00:00:00.000",
          "end": "00:00:05.000",
          "text": "Texto literal continuo"
        }
      ],
      "voiceovers": [],
      "xrolls": []
    }
  ]
}

Reglas críticas:
- Los límites deben corresponder a palabras presentes en la transcripción.
- Mantén las secciones en el orden narrativo final mediante el campo order.
- Si un clip es continuo, usa una sola sección.
- Si una frase se compone con partes lejanas del máster, usa varias secciones.
- No añadas subtítulos ni instrucciones para quemarlos en el video.
- No inventes timestamps de precisión inferior a la evidencia disponible.
"""


NORMALIZATION_PROMPT = """PLANTILLA PARA REPARAR UN ARCHIVO EDITORIAL PARA Abrxs-Canter 3.4.1

Sube a la IA estos archivos:
1. El TXT, MD, HTML o JSON editorial que abrxs-Canter no pudo interpretar.
2. 01_TRANSCRIPCION_COMPACTA.txt del mismo video.
3. Este archivo.
4. Opcionalmente 02_MARCA.txt y 03_ESTRUCTURA_DE_CLIPS.txt.

INSTRUCCIÓN PARA LA IA

Convierte el archivo editorial aportado al contrato JSON estricto de abajo. Conserva TODOS los clips, títulos, secciones, orden narrativo, voiceovers y X-rolls existentes. No resumas, no inventes texto hablado y no elimines clips. El campo text de cada sección debe contener palabras literales de la transcripción. Si el clip une partes lejanas del video, crea una sección por cada tramo y ordénalas con order. Si solo existe texto y no hay timestamps confiables, usa null en start y end: abrxs-Canter alineará el texto. Si solo existen timestamps, conserva esos timestamps y usa text vacío. Si hay texto y timestamps, conserva ambos aunque parezcan desfasados; el programa comparará las dos evidencias.

Devuelve ÚNICAMENTE JSON válido, sin Markdown, sin bloque ```json, sin explicaciones antes o después:

{
  "clips": [
    {
      "id": "C01",
      "title": "Título editorial",
      "type": "video",
      "selected": true,
      "why_it_works": "Explicación opcional",
      "segments": [
        {
          "id": "C01_S01",
          "order": 1,
          "role": "HOOK",
          "start": "00:00:00.000",
          "end": "00:00:05.000",
          "text": "Texto literal continuo presente en la transcripción"
        }
      ],
      "voiceovers": [
        {
          "id": "C01_VO01",
          "label": "VOICEOVER",
          "text": "Texto que debe grabarse",
          "placement": "Después de C01_S01"
        }
      ],
      "xrolls": [
        {
          "id": "C01_XR01",
          "label": "Descripción del recurso",
          "start": "00:00:01.000",
          "end": "00:00:03.000"
        }
      ]
    }
  ]
}

VALIDACIÓN OBLIGATORIA ANTES DE RESPONDER
- La raíz contiene exactamente la clave clips y clips es una lista.
- Cada clip tiene id único, title, type y al menos una sección.
- Cada sección tiene id único, order numérico, role, start, end y text.
- Usa HH:MM:SS.mmm para tiempos; usa null cuando no exista evidencia.
- No conviertas una sola sección continua en múltiples secciones sin necesidad.
- No conviertas un multicorte en un intervalo continuo que incluya material no seleccionado.
- No añadas subtítulos ni instrucciones para quemar subtítulos.
- La respuesta final debe poder guardarse directamente como DECISIONES_ABRXS.json.
"""


def create_ai_package(root: Path, compact_transcript: Path, brand_path: Optional[Path], structure_path: Optional[Path]) -> Path:
    package = root / "PAQUETE_PARA_IA"
    package.mkdir(parents=True, exist_ok=True)
    shutil.copy2(compact_transcript, package / "01_TRANSCRIPCION_COMPACTA.txt")
    brand_text = brand_path.read_text(encoding="utf-8", errors="replace") if brand_path and brand_path.exists() else (
        "INFORMACIÓN DE MARCA\n\nCompleta aquí voz, audiencia, temas, límites editoriales y objetivos.\n"
    )
    structure_text = structure_path.read_text(encoding="utf-8", errors="replace") if structure_path and structure_path.exists() else DEFAULT_STRUCTURE
    (package / "02_MARCA.txt").write_text(brand_text, encoding="utf-8")
    (package / "03_ESTRUCTURA_DE_CLIPS.txt").write_text(structure_text, encoding="utf-8")
    (package / "04_PROMPT_PARA_IA.txt").write_text(AI_PROMPT, encoding="utf-8")
    (package / "05_EJEMPLO_RESPUESTA.json").write_text(json.dumps({
        "clips": [{
            "id": "A01", "title": "Ejemplo", "type": "video", "why_it_works": "",
            "segments": [{"id": "A01_S01", "order": 1, "role": "HOOK", "start": "00:00:00.000", "end": "00:00:05.000", "text": "Texto literal"}],
            "voiceovers": [], "xrolls": [],
        }]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (package / "06_REPARAR_ARCHIVO_NO_RECONOCIDO.txt").write_text(NORMALIZATION_PROMPT, encoding="utf-8")
    return package


def osascript(script: str) -> str:
    result = subprocess.run(["osascript", "-e", script], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("Selección cancelada.")
    return result.stdout.strip()


def choose_file(prompt: str, extensions: Optional[list[str]] = None, optional: bool = False) -> Optional[Path]:
    types = ""
    if extensions:
        types = " of type {" + ",".join(f'\"{x}\"' for x in extensions) + "}"
    try:
        value = osascript(f'POSIX path of (choose file with prompt "{prompt}"{types})')
        return Path(value)
    except RuntimeError:
        if optional:
            return None
        raise


def choose_folder(prompt: str) -> Path:
    return Path(osascript(f'POSIX path of (choose folder with prompt "{prompt}")'))


def gui_inputs(args: argparse.Namespace) -> None:
    args.editorial = choose_file("Selecciona el HTML, MD o TXT editorial", ["html", "htm", "md", "txt"])
    args.video = choose_file("Selecciona el video máster")
    answer = osascript('button returned of (display dialog "¿Ya tienes una transcripción con timestamps por palabra?" buttons {"No", "Sí"} default button "No")')
    if answer == "Sí":
        args.transcript = choose_file("Selecciona el transcript word-level", ["json", "tsv", "csv", "txt"])
    args.output = choose_folder("Selecciona la carpeta donde abrxs-Canter guardará el proyecto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="abrxs-Canter — prepara, alinea y corta videos")
    parser.add_argument("--editorial", type=Path, help="HTML, MD, TXT o JSON editorial")
    parser.add_argument("--video", type=Path, help="Video máster")
    parser.add_argument("--transcript", type=Path, help="Transcript word-level opcional")
    parser.add_argument("--output", type=Path, help="Carpeta de salida")
    parser.add_argument("--brand", type=Path, help="TXT o MD con información de marca")
    parser.add_argument("--structure", type=Path, help="TXT o MD con estructura requerida de clips")
    parser.add_argument("--prepare-only", action="store_true", help="Generar transcripciones y paquete para IA sin cortar clips")
    parser.add_argument("--model", help="Ruta local o repositorio MLX Whisper")
    parser.add_argument("--export-mode", choices=["both", "assembled", "sections"], default="assembled")
    parser.add_argument("--no-xrolls", action="store_true", help="No exportar cortes de X-roll")
    parser.add_argument("--include-unselected", action="store_true", help="Procesar piezas desmarcadas en el HTML")
    parser.add_argument("--parse-only", action="store_true", help="Analizar el editorial sin cortar ni transcribir")
    parser.add_argument("--inspect", action="store_true", help="Imprimir el inventario audiovisual del editorial y salir")
    parser.add_argument("--version", action="version", version=APP_VERSION)
    return parser


# =====================================================================
# ABRXS_TRANSCRIPT_QUALITY_V34
# =====================================================================

from transcript_quality import (
    load_transcript_smart as _ab_load_smart,
    save_transcript_suite as _ab_save_suite,
)

_ab_original_load_transcript = load_transcript
_ab_original_generate_transcript = generate_transcript
_ab_original_run_checked = run_checked

_ab_progress_started = None


def transcription_language() -> str:
    config = (
        Path.home()
        / "Library/Application Support/com.abrxs.canter"
        / "transcription_language"
    )

    if config.is_file():
        value = config.read_text(
            encoding="utf-8",
            errors="replace",
        ).strip().lower()

        if re.fullmatch(
            r"[a-z]{2,3}|auto",
            value,
        ):
            return value

    value = os.environ.get(
        "ABRAXAS_TRANSCRIPT_LANGUAGE",
        "auto",
    ).strip().lower()

    if re.fullmatch(
        r"[a-z]{2,3}|auto",
        value,
    ):
        return value

    return "auto"


def load_transcript(path: Path):
    return _ab_load_smart(
        path,
        Word,
        _ab_original_load_transcript,
    )


def generate_transcript(
    video: Path,
    cache_dir: Path,
    model: Optional[str],
    backends: dict[str, Any],
) -> Path:

    output = (
        cache_dir
        / "MASTER_WORD_LEVEL.json"
    )

    language = (
        transcription_language()
    )

    # Si el caché fue creado en otro idioma,
    # se conserva como backup y hacemos UNA nueva pasada.
    if (
        output.exists()
        and language != "auto"
    ):
        try:
            raw = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )

            params_language = str(
                (
                    raw.get("params")
                    or {}
                ).get(
                    "language"
                )
                or "auto"
            ).lower()

            detected_language = str(
                (
                    raw.get("result")
                    or {}
                ).get(
                    "language"
                )
                or ""
            ).lower()

            if (
                params_language
                != language
                and detected_language
                != language
            ):
                backup = (
                    cache_dir
                    / (
                        "MASTER_WORD_LEVEL."
                        "previous_"
                        f"{params_language}_"
                        f"{detected_language or 'unknown'}"
                        ".json"
                    )
                )

                if not backup.exists():
                    shutil.copy2(
                        output,
                        backup,
                    )

                output.unlink()

                log(
                    "Idioma configurado="
                    f"{language}; "
                    "el caché anterior era "
                    f"{params_language}/"
                    f"{detected_language}. "
                    "Se hará UNA nueva "
                    "transcripción y después "
                    "quedará cacheada."
                )

        except Exception:
            pass

    return _ab_original_generate_transcript(
        video,
        cache_dir,
        model,
        backends,
    )


def save_normalized_transcript(
    words,
    source,
    root,
    brand_path=None,
    video=None,
):
    return _ab_save_suite(
        words,
        source,
        root,
        brand_path=brand_path,
        video=video,
        WordClass=Word,
        log=log,
    )


def run_checked(command):
    """
    Mantiene el run_checked original para todo excepto whisper.cpp.
    Para whisper.cpp además interpreta:
        progress = XX%
    y emite progreso + ETA para la UI.
    """

    global _ab_progress_started

    command = [
        str(value)
        for value in command
    ]

    is_whisper = any(
        Path(value).name
        in {
            "whisper-cli",
            "whisper.cpp",
        }
        for value
        in command[:2]
    )

    if not is_whisper:
        return _ab_original_run_checked(
            command
        )

    import shlex as _shlex
    import subprocess as _subprocess
    import time as _time

    log(
        "$ "
        + _shlex.join(
            command
        )
    )

    _ab_progress_started = (
        _time.monotonic()
    )

    process = _subprocess.Popen(
        command,
        stdout=_subprocess.PIPE,
        stderr=_subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None

    for line in process.stdout:
        line = line.rstrip(
            "\n"
        )

        if line:
            print(
                line,
                file=sys.stderr,
                flush=True,
            )

        match = re.search(
            r"progress\s*=\s*(\d+)%",
            line,
        )

        if not match:
            continue

        progress = max(
            0,
            min(
                100,
                int(
                    match.group(1)
                ),
            ),
        )

        elapsed = (
            _time.monotonic()
            - _ab_progress_started
        )

        eta = None

        if progress > 0:
            eta = max(
                0,
                elapsed
                * (
                    100
                    - progress
                )
                / progress,
            )

        emit_event(
            "transcript_progress",
            progress=progress,
            elapsed_seconds=round(
                elapsed,
                1,
            ),
            eta_seconds=(
                round(
                    eta,
                    1,
                )
                if eta is not None
                else None
            ),
        )

    return_code = (
        process.wait()
    )

    if return_code != 0:
        raise RuntimeError(
            "Falló el comando "
            f"({return_code}): "
            + _shlex.join(
                command
            )
        )

    return None

# =====================================================================
# /ABRXS_TRANSCRIPT_QUALITY_V34
# =====================================================================

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.inspect:
        if not args.editorial:
            parser.error("--inspect requiere --editorial")
        editorial = args.editorial.expanduser().resolve()
        detected = parse_editorial(editorial)
        video_kinds = {"video", "intro", "vertical", "horizontal", "clip", "reel"}
        actionable = [
            p for p in detected
            if (args.include_unselected or p.selected) and p.segments and p.kind.lower() in video_kinds
        ]
        payload = {
            "detected": len(detected), "actionable": len(actionable),
            "omitted": len(detected) - len(actionable),
            "pieces": [
                {"id": p.id, "title": p.title, "kind": p.kind, "segments": len(p.segments),
                 "xrolls": len(p.xrolls), "voiceovers": len(p.voiceovers)}
                for p in actionable
            ],
        }
        print("ABRXS_CANTER_INSPECT:" + json.dumps(payload, ensure_ascii=False))
        return 0
    if not args.editorial and not args.video:
        gui_inputs(args)
    if not args.video or not args.output or (not args.prepare_only and not args.editorial):
        parser.error("Se requieren --video y --output; para cortar también se requiere --editorial.")

    editorial = args.editorial.expanduser().resolve() if args.editorial else None
    video = args.video.expanduser().resolve()
    output_base = args.output.expanduser().resolve()
    if not video.exists() or (editorial and not editorial.exists()):
        raise RuntimeError("No se encontró el archivo editorial o el video máster.")
    media_info = preflight_media(video, output_base)
    if args.parse_only:
        if not editorial:
            parser.error("--parse-only requiere --editorial")
        detected = parse_editorial(editorial)
        video_kinds = {"video", "intro", "vertical", "horizontal", "clip", "reel"}
        detected = [p for p in detected if p.segments and p.kind.lower() in video_kinds]
        destination = output_base / "ABRXS_CANTER_PARSE_ONLY.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps([dataclasses.asdict(p) for p in detected], ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Análisis guardado: {destination}")
        return 0

    project_name = safe_name(video.stem)
    root = output_base / project_name
    cache_seed = f"{video.resolve()}|{video.stat().st_size}|{video.stat().st_mtime_ns}"
    cache_id = hashlib.sha256(cache_seed.encode()).hexdigest()[:16]
    cache_base = Path(os.environ.get("ABRAXAS_CACHE_DIR", str(Path.home() / "Library" / "Caches" / "Abrxs-Canter")))
    cache_root = cache_base / cache_id
    cache_sections = cache_root / "SECCIONES_CODIFICADAS"
    cache_root.mkdir(parents=True, exist_ok=True)

    backends = detect_whisper_backends()
    emit_event("backend_detected", **backends)
    transcript_path = args.transcript.expanduser().resolve() if args.transcript else None
    if transcript_path:
        emit_event("transcript_start", mode="existing", detail="Leyendo transcripción seleccionada")
        words, _ = load_transcript(transcript_path)
    else:
        emit_event("transcript_start", mode="generated", detail="Generando timestamps por palabra")
        transcript_path = generate_transcript(video, cache_root, args.model, backends)
        words, _ = load_transcript(transcript_path)
    emit_event("transcript_complete", word_count=len(words), path=str(transcript_path))
    log(f"Palabras con timestamps: {len(words)}")
    _, compact_transcript = save_normalized_transcript(words, transcript_path, root, brand_path=(args.brand.expanduser().resolve() if args.brand else None), video=video)
    brand = args.brand.expanduser().resolve() if args.brand else None
    structure = args.structure.expanduser().resolve() if args.structure else None
    ai_package = create_ai_package(root, compact_transcript, brand, structure)
    if args.prepare_only:
        summary = {
            "schema_version": 1, "app": APP_NAME, "version": APP_VERSION, "mode": "prepare",
            "created": time.strftime("%Y-%m-%d %H:%M:%S"), "video": str(video),
            "transcript": str(transcript_path), "word_count": len(words),
            "ai_package": str(ai_package), "cache": str(cache_root), "whisper_backends": backends,
            "media": media_info,
        }
        (root / "PROYECTO.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "INFORME.txt").write_text(
            f"abrxs-Canter — PREPARACIÓN COMPLETA\n\nMáster: {video}\nPalabras: {len(words)}\nPaquete para IA: {ai_package}\n",
            encoding="utf-8",
        )
        emit_event("job_complete", output=str(root), total_pieces=0)
        log(f"\nPreparación terminada: {root}")
        return 0

    pieces = parse_editorial(editorial)
    if not args.include_unselected:
        pieces = [p for p in pieces if p.selected]
    detected_count = len(pieces)
    video_kinds = {"video", "intro", "vertical", "horizontal", "clip", "reel"}
    pieces = [p for p in pieces if p.segments and p.kind.lower() in video_kinds]
    omitted_count = detected_count - len(pieces)
    if omitted_count:
        log(f"Elementos editoriales no audiovisuales o sin fuente omitidos: {omitted_count}")
    if not pieces:
        raise RuntimeError("El archivo editorial no contiene piezas reconocibles con texto o timestamps.")
    log(f"Piezas editoriales detectadas: {len(pieces)}")
    emit_event("project_detected", total_pieces=len(pieces), omitted=omitted_count)

    align_pieces(pieces, words)

    registry: dict[str, tuple[str, str]] = {}
    reports = []
    for index, piece in enumerate(pieces, 1):
        log(f"[{index}/{len(pieces)}] {piece.id} — {piece.title}")
        emit_event(
            "piece_start", piece_id=piece.id, title=piece.title,
            current=index, total=len(pieces), segments=len(piece.segments),
            xrolls=len(piece.xrolls), voiceovers=len(piece.voiceovers),
        )
        reports.append(export_piece(
            piece, video, root, cache_sections, registry,
            args.export_mode, not args.no_xrolls,
        ))

    summary = {
        "schema_version": 1, "app": APP_NAME, "version": APP_VERSION, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video": str(video), "editorial": str(editorial), "transcript": str(transcript_path),
        "ai_package": str(ai_package), "cache": str(cache_root), "whisper_backends": backends,
        "media": media_info,
        "conflict_threshold_seconds": CONFLICT_SECONDS,
        "padding_before_seconds": DEFAULT_PAD_BEFORE, "padding_after_seconds": DEFAULT_PAD_AFTER,
        "pieces": reports,
    }
    (root / "PROYECTO.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    text_lines = [
        "abrxs-Canter — REPORTE GENERAL", f"Máster: {video}", f"Editorial: {editorial}",
        f"Piezas: {len(reports)}", "",
    ]
    for item in reports:
        text_lines.append(f"{item['piece']}: {item['status']} — {item['variants']}")
    (root / "INFORME.txt").write_text("\n".join(text_lines) + "\n", encoding="utf-8")
    log(f"\nTerminado. Resultado: {root}")
    emit_event("job_complete", output=str(root), total_pieces=len(reports))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
