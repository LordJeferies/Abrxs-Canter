"""Editor local: recetas, preflight, caché y exportación. Solo biblioteca estándar.

Se ejecuta como proceso separado desde Tauri. No carga modelos ni genera voz.
"""
from __future__ import annotations

import array
import contextlib
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import selectors
import subprocess
import sys
import tempfile
import time
import uuid

SCHEMA = 1
CACHE_LIMIT = 8 * 1024**3
ACTIVE_PROCESS = None
REQUEST_ID = None


def event(kind, **data):
    print("ABRXS_STAGE1_EVENT:" + json.dumps({"event": kind, "requestId": REQUEST_ID, **data}, ensure_ascii=False), flush=True)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".abrxs-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("El tiempo debe ser un número finito.")
    return value


def validate_blocks(items, duration):
    if not isinstance(items, list) or not items:
        raise ValueError("Añade al menos un bloque.")
    if len(items) > 1000:
        raise ValueError("Demasiados bloques; máximo 1000 por clip.")
    result, ids = [], set()
    for item in items:
        start, end = finite(item["start"]), finite(item["end"])
        if start < 0 or end <= start or end > duration + .001:
            raise ValueError("Un bloque está vacío o fuera de los límites del máster.")
        uid = str(item.get("uid") or uuid.uuid4().hex)
        if uid in ids:
            uid = uuid.uuid4().hex
        ids.add(uid)
        result.append({**item, "uid": uid, "start": start, "end": min(end, duration)})
    return result


def virtual_words(words, blocks):
    result, offset = [], 0.0
    for block in blocks:
        for word in words:
            start, end = float(word["start"]), float(word["end"])
            if end <= block["start"] or start >= block["end"]:
                continue
            result.append({
                "text": word.get("text", word.get("word", "")), "blockUid": block["uid"],
                "sourceStart": start, "sourceEnd": end,
                "start": offset + max(0, start - block["start"]),
                "end": offset + min(block["end"] - block["start"], end - block["start"]),
            })
        offset += block["end"] - block["start"]
    return result


def source_identity(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("El máster no es un archivo.")
    size = path.stat().st_size
    digest = hashlib.sha256(str(size).encode())
    with path.open("rb") as stream:
        digest.update(stream.read(1024 * 1024))
        stream.seek(max(0, size - 1024 * 1024))
        digest.update(stream.read(1024 * 1024))
    return {"path": str(path), "size": size, "sampleHash": digest.hexdigest(), "mtimeNs": path.stat().st_mtime_ns}


def same_source(expected, actual):
    if (expected.get("sampleHash"), expected.get("size")) != (actual.get("sampleHash"), actual.get("size")):
        return False
    return expected.get("path") != actual.get("path") or expected.get("mtimeNs") == actual.get("mtimeNs")


def command(name):
    result = shutil.which(name)
    if not result:
        raise ValueError(f"Falta {name}. Instálalo desde el actualizador con tu autorización.")
    return result


def stop_process():
    if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(ACTIVE_PROCESS.pid, signal.SIGTERM)
        try:
            ACTIVE_PROCESS.wait(timeout=3)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(ACTIVE_PROCESS.pid, signal.SIGKILL)


def cancelled(*_):
    stop_process()
    raise SystemExit(130)


def run(args, timeout=60, binary=False, input=None, include_stderr=False):
    global ACTIVE_PROCESS
    ACTIVE_PROCESS = subprocess.Popen(args, stdin=subprocess.PIPE if input is not None else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = ACTIVE_PROCESS.communicate(input=input.encode() if isinstance(input, str) else input, timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process()
        raise RuntimeError(f"Se agotó el tiempo de {Path(args[0]).name}; no se sustituyó la exportación anterior.")
    finally:
        if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is not None:
            process, ACTIVE_PROCESS = ACTIVE_PROCESS, None
    if process.returncode:
        raise RuntimeError(stderr.decode("utf-8", "replace")[-1800:] or "El proceso falló.")
    if include_stderr:
        return stdout.decode('utf-8', 'replace') + '\n' + stderr.decode('utf-8', 'replace')
    return stdout if binary else stdout.decode("utf-8", "replace")


def render_section(args, seconds, clip_id, index, total, section, count):
    """Stream FFmpeg telemetry, never buffer a video or its complete log."""
    global ACTIVE_PROCESS
    started = time.monotonic()
    with tempfile.TemporaryFile() as errors:
        ACTIVE_PROCESS = subprocess.Popen([args[0], "-nostdin", "-progress", "pipe:1", "-stats_period", "1", *args[1:]],
                                          stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
        process = ACTIVE_PROCESS
        values = {}
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                while process.poll() is None:
                    if time.monotonic() - started > 86400:
                        stop_process()
                        raise RuntimeError("La codificación superó 24 horas; se conservó la exportación anterior.")
                    for key, _ in ready.select(1):
                        line = key.fileobj.readline().decode("utf-8", "replace").strip()
                        if "=" not in line:
                            continue
                        name, value = line.split("=", 1)
                        values[name] = value
                        if name == "progress":
                            done = min(seconds, max(0, float(values.get("out_time_us", "0")) / 1e6))
                            elapsed = time.monotonic() - started
                            speed = done / elapsed if elapsed > 0 else 0
                            fraction = done / seconds if seconds else 0
                            eta = (seconds-done)/speed if done > 1 and speed > 0 else None
                            event("progress", id=clip_id,
                                  progress=100*(index+(section+fraction)/(count+1))/total,
                                  clipProgress=100*(section+fraction)/(count+1), etaSeconds=eta,
                                  detail=f"Codificando sección {section+1}/{count}: {done:.0f}/{seconds:.0f} s de video · {speed:.2f}× · " +
                                  (f"≈ {eta/60:.1f} min restantes en esta sección" if eta is not None else "Midiendo velocidad; esperando los primeros fotogramas"))
            process.wait()
            if process.returncode:
                errors.seek(0, os.SEEK_END)
                errors.seek(max(0, errors.tell()-1800))
                raise RuntimeError(errors.read().decode("utf-8", "replace") or "FFmpeg falló.")
        finally:
            stop_process()
            ACTIVE_PROCESS = None


def media_info(path):
    raw = json.loads(run([command("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    video = next((s for s in raw.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("La fuente no tiene una pista de video.")
    duration = finite(raw.get("format", {}).get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise ValueError("No se pudo verificar la duración de la fuente.")
    width, height = int(video["width"]), int(video["height"])
    rotation = next((float(s.get("rotation", 0)) for s in video.get("side_data_list", []) if "rotation" in s), float(video.get("tags", {}).get("rotate", 0)))
    if round(rotation) % 180:
        width, height = height, width
    return {"duration": duration, "width": width, "height": height,
            "hasAudio": any(s.get("codec_type") == "audio" for s in raw["streams"]),
            "codec": video.get("codec_name"), "frameRate": video.get("avg_frame_rate"),
            "previewWarning": video.get("codec_name") not in {"h264", "hevc"}}


def normalized_words(path):
    if not path:
        return []
    import abraxas_local as engine
    words, _ = engine.load_transcript(Path(path))
    return [{"text": w.text, "start": w.start, "end": w.end} for w in words]


def root_for(req):
    root = Path(req["projectPath"]).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("No existe el proyecto.")
    return root


def db_path(root):
    return root / "EDICIONES" / "CLIPS.json"


def load_db(root):
    data = read_json(db_path(root), {"schemaVersion": SCHEMA, "clips": []})
    if data.get("schemaVersion") != SCHEMA or not isinstance(data.get("clips"), list):
        raise ValueError("Formato de biblioteca no compatible. El archivo se conserva sin cambios.")
    return data


def recipe_signature(clip):
    payload = {k: clip.get(k) for k in ("source", "format")}
    payload["blocks"] = [{"start": b["start"], "end": b["end"]} for b in clip.get("blocks", [])]
    for key in ('captions', 'tracking'):
        if clip.get(key): payload[key] = clip[key]
    # Rutas y mtime no determinan si un máster relocalizado cambió de contenido.
    source = payload.get("source") or {}
    payload["source"] = {"size": source.get("size"), "sampleHash": source.get("sampleHash")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def mark_export(clip):
    last = clip.get("export") or {}
    if last.get("path") and Path(last["path"]).is_file():
        clip["exportState"] = "exported" if last.get("signature") == recipe_signature(clip) else "outdated"
    else:
        clip["exportState"] = "error" if clip.get("error") else "pending"


def migrate_reports(root, output):
    db = load_db(root)
    summary = read_json(Path(output) / "PROYECTO.json", {}) if output else {}
    if not summary.get("video") or not Path(summary["video"]).is_file():
        return db
    source = source_identity(summary["video"])
    duration = finite(summary.get("media", {}).get("duration") or media_info(source["path"])["duration"])
    for report in summary.get("pieces", []):
        raw = report.get("source") or {}
        segments = sorted(raw.get("segments", []), key=lambda s: s.get("order", 0))
        for variant in report.get("variants", {}):
            key = hashlib.sha256(f'{source["sampleHash"]}|{report.get("piece")}|{variant}'.encode()).hexdigest()[:24]
            if any(c["id"] == key for c in db["clips"]):
                continue
            blocks = []
            for seg in segments:
                use_aligned = variant in {"TEXT_ALIGNED", "VERIFIED"}
                start = seg.get("aligned_start") if use_aligned else seg.get("start")
                end = seg.get("aligned_end") if use_aligned else seg.get("end")
                if start is None or end is None:
                    blocks = []
                    break
                blocks.append({"uid": uuid.uuid4().hex, "start": max(0, float(start) - float(summary.get("padding_before_seconds", .2))),
                    "end": min(duration, float(end) + float(summary.get("padding_after_seconds", .2))), "text": seg.get("text", ""), "role": seg.get("role", "SECCION")})
            if not blocks:
                continue
            try:
                blocks = validate_blocks(blocks, duration)
            except (ValueError, TypeError):
                continue
            clip = {"id": key, "revision": 1, "title": report.get("title") or report.get("piece"), "variant": variant,
                    "source": source, "duration": duration, "blocks": blocks, "status": "review", "note": "",
                    "transcript": str(Path(output) / "TRANSCRIPCIONES/TRANSCRIPCION_PALABRA_POR_PALABRA.json"),
                    "format": {"aspect": "original", "mode": "contain", "x": .5, "y": .5},
                    "origin": report.get("piece"), "legacyExtras": {k: report.get(k, []) for k in ("sections", "xrolls", "voiceovers")}}
            file = next((p for p in report.get("videos", []) if Path(p).stem.endswith("_" + variant) and Path(p).is_file()), None)
            if file:
                clip["export"] = {"path": file, "signature": recipe_signature(clip), "revision": 1}
            mark_export(clip)
            db["clips"].append(clip)
    if db["clips"]:
        atomic_json(db_path(root), db)
    return db


def source_data(req):
    root = root_for(req)
    output = Path(req.get("outputPath") or root)
    summary = read_json(output / "PROYECTO.json", {})
    path = req.get("video") or summary.get("video")
    if not path:
        raise ValueError("Selecciona el máster del proyecto.")
    source = source_identity(path)
    media = media_info(path)
    transcript = req.get("transcript")
    normalized = output / "TRANSCRIPCIONES/TRANSCRIPCION_PALABRA_POR_PALABRA.json"
    if not transcript:
        transcript = str(normalized) if normalized.is_file() else summary.get("transcript")
    words = normalized_words(transcript)
    key = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:24]
    return {"source": source, "media": media, "transcript": transcript, "words": words,
            "freeBytes": shutil.disk_usage(root).free, "cacheBytes": cache_usage(root),
            "assets": read_json(cache_dir(root) / "assets" / key / "index.json")}


def save_clip(req):
    root = root_for(req)
    db = load_db(root)
    incoming = req["clip"]
    source = source_identity(incoming["source"]["path"])
    if not same_source(incoming["source"], source):
        raise ValueError("El contenido del máster cambió. Revisa su transcripción antes de guardar.")
    duration = media_info(source["path"])["duration"]
    blocks = validate_blocks(incoming["blocks"], duration)
    existing = next((c for c in db["clips"] if c["id"] == incoming.get("id")), None)
    if existing and incoming.get("revision") != existing["revision"]:
        raise ValueError("Existe una revisión más reciente. Recarga la ficha antes de sobrescribir.")
    clip = {**(existing or {}), **incoming, "id": incoming.get("id") or uuid.uuid4().hex,
            "source": source, "duration": duration, "blocks": blocks, "schemaVersion": SCHEMA,
            "revision": (existing or {}).get("revision", 0) + 1, "updatedAt": time.time()}
    clip["format"] = validate_format(clip.get("format", {}))
    import stage2
    if clip.get('captions'): clip['captions'] = stage2.captions_settings(clip['captions'])
    if clip.get('tracking'): clip['tracking'] = stage2.validate_tracking(clip['tracking'])
    if clip.get("status") not in {"draft", "review", "approved"}:
        clip["status"] = "draft"
    # No confiar en metadatos de exportación enviados por la interfaz.
    clip["export"] = (existing or {}).get("export")
    clip["exportHistory"] = (existing or {}).get("exportHistory", [])
    clip.pop("error", None)
    mark_export(clip)
    db["clips"] = [clip if c["id"] == clip["id"] else c for c in db["clips"]]
    if not existing:
        db["clips"].append(clip)
    atomic_json(db_path(root), db)
    return clip


def validate_format(fmt):
    aspect, mode = fmt.get("aspect", "original"), fmt.get("mode", "contain")
    if aspect not in {"original", "9:16", "16:9", "1:1"} or mode not in {"contain", "cover"}:
        raise ValueError("Formato de encuadre no válido.")
    return {"aspect": aspect, "mode": mode, "x": max(0, min(1, finite(fmt.get("x", .5)))), "y": max(0, min(1, finite(fmt.get("y", .5))))}


def crop_filter(media, fmt):
    fmt = validate_format(fmt)
    w, h = int(media["width"]), int(media["height"])
    if fmt["aspect"] == "original":
        return f"scale={w//2*2}:{h//2*2},setsar=1"
    target = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}[fmt["aspect"]]
    tw, th = target
    if fmt["mode"] == "contain":
        return f"scale={tw}:{th}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    ratio = tw / th
    cw, ch = (int(h * ratio)//2*2, h//2*2) if w / h > ratio else (w//2*2, int(w / ratio)//2*2)
    x, y = int((w-cw)*fmt["x"])//2*2, int((h-ch)*fmt["y"])//2*2
    return f"crop={cw}:{ch}:{x}:{y},scale={tw}:{th},setsar=1"


def cache_dir(root):
    path = root / ".abrxs-cache-stage1"
    if path.is_symlink():
        raise ValueError("La caché no puede ser un enlace simbólico.")
    return path


def cache_usage(root):
    folder = cache_dir(root)
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file() and not p.is_symlink()) if folder.exists() else 0


def prune_cache(root, keep=(), limit=CACHE_LIMIT):
    folder = cache_dir(root)
    if folder.is_symlink():
        raise ValueError("La caché no puede ser un enlace simbólico.")
    keep = {Path(p).resolve() for p in keep}
    files = sorted((p for p in folder.rglob("*") if p.is_file() and not p.is_symlink()), key=lambda p: p.stat().st_mtime) if folder.exists() else []
    total = sum(p.stat().st_size for p in files)
    for path in files:
        if total <= limit:
            break
        if path.resolve() in keep or path.suffix == ".lock":
            continue
        total -= path.stat().st_size
        path.unlink()
    return total


def frame_step(req):
    path, at = req["video"], finite(req["at"])
    start = max(0, at - 3)
    raw = json.loads(run([command("ffprobe"), "-v", "error", "-select_streams", "v:0", "-read_intervals", f"{start:.6f}%+7",
        "-show_frames", "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", path], timeout=30))
    times = sorted({float(f["best_effort_timestamp_time"]) for f in raw.get("frames", []) if "best_effort_timestamp_time" in f})
    eligible = [t for t in times if t > at + .00001] if req.get("direction", 1) > 0 else [t for t in times if t < at - .00001]
    if not eligible:
        raise ValueError("No se encontró otro fotograma cercano. Usa el ajuste numérico.")
    return {"time": eligible[0] if req.get("direction", 1) > 0 else eligible[-1]}


def assets(req):
    root = root_for(req)
    data = source_data(req)
    source, media = data["source"], data["media"]
    if shutil.disk_usage(root).free < int(media["duration"] * 16000) + 128 * 1024**2:
        raise ValueError("Espacio insuficiente para generar la onda de audio temporal.")
    key = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:24]
    folder = cache_dir(root) / "assets" / key
    if folder.is_symlink():
        raise ValueError("Ubicación de caché no válida.")
    manifest = read_json(folder / "index.json")
    if manifest and all(Path(f["path"]).is_file() for f in manifest.get("thumbs", [])):
        return manifest
    folder.mkdir(parents=True, exist_ok=True)
    thumbs = []
    # Una sola pasada de extracción, un máximo de doce imágenes por fuente.
    interval = max(media["duration"] / 12, .1)
    event("progress", progress=0, detail="Generando miniaturas (una pasada)")
    run([command("ffmpeg"), "-v", "error", "-i", source["path"], "-vf", f"fps=1/{interval},scale=240:-2",
         "-frames:v", "12", "-y", str(folder / "thumb-%02d.jpg")], timeout=1800)
    for i, p in enumerate(sorted(folder.glob("thumb-*.jpg"))):
        thumbs.append({"path": str(p), "time": min(media["duration"], (i + .5) * interval), "approximate": True})
    peaks = []
    if media["hasAudio"]:
        event("progress", progress=40, detail="Calculando onda de audio real")
        # PCM reducido en archivo temporal: nunca acumular el audio completo en RAM.
        pcm = folder / "audio.partial.pcm"
        try:
            run([command("ffmpeg"), "-v", "error", "-i", source["path"], "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-y", str(pcm)], timeout=1800)
            bucket = max(1, math.ceil(pcm.stat().st_size / 2 / 2400))
            with pcm.open("rb") as stream:
                while chunk := stream.read(bucket * 2):
                    samples = array.array("h")
                    samples.frombytes(chunk)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    peaks.append(max((abs(v) / 32768 for v in samples), default=0))
        finally:
            pcm.unlink(missing_ok=True)
    result = {"duration": media["duration"], "thumbs": thumbs, "peaks": peaks, "source": source}
    atomic_json(folder / "index.json", result)
    prune_cache(root, [folder / "index.json", *[t["path"] for t in thumbs]])
    return result


def import_editorial(req):
    if req.get("masters"):
        return import_multi_master(req)
    import abraxas_local as engine
    data = source_data(req)
    pieces = engine.parse_editorial(Path(req["editorial"]))
    words = [engine.Word(w["text"], w["start"], w["end"]) for w in data["words"]]
    for index, piece in enumerate(pieces):
        event("notice", detail=f"Verificando palabras de {piece.id} ({index+1}/{len(pieces)}). Fuente accesible; {len(words)} palabras con tiempos cargadas.")
        engine.align_pieces([piece], words)
    clips, warnings, target_ids = [], [], []
    if not data["words"]:
        warnings.append("Sin transcripción: solo se importan cortes con timestamps completos; no se verificó su texto.")
    root = root_for(req)
    db = load_db(root)
    for piece in pieces:
        if req.get("_pieceIds") is not None and piece.id not in req["_pieceIds"]:
            continue
        if not piece.selected or piece.kind.lower() not in {"video", "intro", "vertical", "horizontal", "clip", "reel"}:
            continue
        variants = engine.variant_ranges(piece)
        if req.get("cutMethod") == "preferred" and variants:
            preferred = next((key for key in ("VERIFIED", "TEXT_ALIGNED", "TIMESTAMP") if key in variants), next(iter(variants)))
            variants = {preferred: variants[preferred]}
        if not variants:
            warnings.append(f"{piece.id}: sin rango verificable; revisa el texto o los timestamps.")
        for name, ranges in variants.items():
            if len(ranges) != len(piece.segments):
                warnings.append(f"{piece.id}/{name}: secciones incompletas; no se importó parcialmente.")
                continue
            offset = float(req.get("_masterOffset", 0))
            if req.get("_masterOrientation") and any(start + offset < 0 or end + offset > data["media"]["duration"] for _, start, end in ranges):
                raise ValueError(f"{piece.id}: rango fuera del máster {req['_masterOrientation']}. Revisa sincronización y desfase.")
            blocks = [{"uid": uuid.uuid4().hex, "start": max(0, start + offset - .2), "end": min(data["media"]["duration"], end + offset + .2),
                       "text": seg.text, "role": seg.role} for seg, start, end in ranges]
            try:
                blocks = validate_blocks(blocks, data["media"]["duration"])
            except ValueError as exc:
                warnings.append(f"{piece.id}: {exc}")
                continue
            orientation = req.get("_masterOrientation", "")
            stable = hashlib.sha256(f'{data["source"]["sampleHash"]}|{piece.id}|{name}{"|" + orientation if orientation else ""}'.encode()).hexdigest()[:24]
            target_ids.append(stable)
            existing = next((c for c in db["clips"] if c["id"] == stable), None)
            if existing:
                warnings.append(f"{piece.id}/{name}: ficha existente conservada, sin sobrescribir ajustes.")
                continue
            clip = {"id": stable, "revision": 1, "title": piece.title, "origin": piece.id, "variant": name,
                    "source": data["source"], "transcript": data["transcript"], "duration": data["media"]["duration"],
                    "blocks": blocks, "status": "review", "note": "",
                    "format": {"aspect": "original", "mode": "contain", "x": .5, "y": .5},
                    "extras": {"voiceovers": [dataclasses.asdict(v) for v in piece.voiceovers], "xrolls": [dataclasses.asdict(x) for x in piece.xrolls]},
                    "alignment": [dataclasses.asdict(seg) for seg in piece.segments]}
            clip["textVerified"] = name in ("VERIFIED", "TEXT_ALIGNED")
            if not clip["textVerified"]:
                warnings.append(f"{piece.id}: ficha provisional. No se exportará hasta verificar el texto o revisar manualmente sus límites.")
            if orientation:
                clip["outputOrientation"] = orientation
                clip["sourceOffset"] = offset
                clip["title"] += " · " + ("Vertical" if orientation == "vertical" else "Horizontal")
            mark_export(clip)
            db["clips"].append(clip)
            clips.append(clip)
    if not clips and not warnings:
        raise ValueError("No se reconocieron clips; utiliza la plantilla editorial del proyecto.")
    if not req.get("_dryRun"):
        atomic_json(db_path(root), db)
    return {"clips": db["clips"], "warnings": warnings, "targetIds": target_ids}


def import_multi_master(req):
    """Stage both orientations before one atomic library write; never export here."""
    import abraxas_local as engine
    masters = req["masters"]
    if not req.get("sameTimelineConfirmed"):
        raise ValueError("Confirma que los másteres corresponden a la misma grabación y revisa el desfase.")
    if not isinstance(masters, list) or not 1 <= len(masters) <= 2:
        raise ValueError("Selecciona uno o dos másteres etiquetados horizontal/vertical.")
    orientations = [m.get("orientation") for m in masters]
    if len(set(orientations)) != len(orientations) or any(o not in ("horizontal", "vertical") for o in orientations):
        raise ValueError("Los másteres necesitan orientaciones diferentes y válidas.")
    pieces = engine.parse_editorial(Path(req["editorial"]))
    routes = {}
    raw = Path(req["editorial"]).read_text(encoding="utf-8-sig")
    match = re.search(r'[\{\[]', raw)
    if match:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[match.start():])
            for index, item in enumerate(obj if isinstance(obj, list) else obj.get("clips", obj.get("pieces", obj.get("videos", [])))):
                if "outputs" in item:
                    outputs = item["outputs"]
                    if not isinstance(outputs, list) or not outputs or any(o not in ("horizontal", "vertical") for o in outputs):
                        raise ValueError("outputs debe ser [horizontal], [vertical] o ambos.")
                    routes[str(item.get("id") or item.get("clip_id") or f"CLIP_{index+1:02d}")] = outputs
        except json.JSONDecodeError:
            pass  # The existing editorial parser reports malformed content first.
    assigned = {o: [] for o in orientations}
    for piece in pieces:
        if not piece.selected:
            continue
        kind = piece.kind.lower()
        targets = routes.get(piece.id)
        if targets is None:
            targets = [kind] if kind in ("horizontal", "vertical") else ["horizontal", "vertical"] if kind == "intro" else orientations if req.get("unassignedOutputs") == "both" else [req["unassignedOutputs"]] if req.get("unassignedOutputs") in orientations else None
        if targets is None:
            raise ValueError(f"{piece.id}: no indica formato. Usa type horizontal/vertical/intro, outputs en JSON o elige destino para clips sin formato.")
        for target in targets:
            if target not in assigned:
                raise ValueError(f"{piece.id}: falta el máster {target}.")
            assigned[target].append(piece.id)
    root = root_for(req)
    db = load_db(root)
    merged = {c["id"]: c for c in db["clips"]}
    warnings, ids = [], []
    for master in masters:
        orientation = master["orientation"]
        media = media_info(master["video"])
        if (orientation == "vertical") != (media["height"] > media["width"]):
            raise ValueError(f"El archivo elegido como {orientation} tiene dimensiones {media['width']}×{media['height']}. Selecciona la fuente correcta.")
        offset = finite(master.get("offset", 0))
        if not assigned[orientation]:
            continue
        result = import_editorial({**req, "masters": None, "video": master["video"], "_dryRun": True,
                                  "_pieceIds": assigned[orientation], "_masterOrientation": orientation, "_masterOffset": offset})
        merged.update({c["id"]: c for c in result["clips"]})
        warnings.extend(result["warnings"])
        ids.extend(result["targetIds"])
    db["clips"] = list(merged.values())
    atomic_json(db_path(root), db)
    return {"clips": db["clips"], "warnings": warnings, "targetIds": list(dict.fromkeys(ids))}


def export_clips(req):
    root = root_for(req)
    ids = list(dict.fromkeys(req["ids"]))
    queue = {"requestId": REQUEST_ID, "ids": ids, "status": "running", "completed": [], "failed": []}
    queue_path = root / "EDICIONES" / "COLA_EXPORTACION.json"
    atomic_json(queue_path, queue)
    try:
        for index, clip_id in enumerate(ids):
            db = load_db(root)
            clip = next((c for c in db["clips"] if c["id"] == clip_id), None)
            if not clip:
                queue["failed"].append({"id": clip_id, "error": "Ficha no encontrada"})
                continue
            event("clip_start", id=clip_id, title=clip["title"], index=index+1, total=len(ids))
            try:
                if clip.get("origin") and clip.get("variant") == "TIMESTAMP" and not clip.get("textVerified") and not clip.get("boundariesReviewed"):
                    raise ValueError("Los timestamps son orientativos: verifica el texto y guarda los límites revisados antes de exportar.")
                existing = clip.get("export") or {}
                # Reuse equivalent recipes, including exports made by earlier versions.
                for candidate in db["clips"]:
                    for saved in [candidate.get("export") or {}, *candidate.get("exportHistory", [])]:
                        path = Path(saved.get("path", ""))
                        if not path.is_file():
                            continue
                        try:
                            old = read_json(path.with_suffix(".json"), {})
                        except (ValueError, OSError):
                            continue  # A damaged old sidecar is not proof of an identical export.
                        recipe = old.get("recipe") or (candidate if saved == candidate.get("export") else None)
                        if recipe and recipe_signature(recipe) == recipe_signature(clip):
                            existing = {**saved, "signature": recipe_signature(clip)}
                            break
                if (not req.get("force") and existing.get("signature") == recipe_signature(clip)
                        and Path(existing.get("path", "")).is_file() and not req.get("sections")):
                    if not same_source(clip["source"], source_identity(clip["source"]["path"])):
                        raise ValueError("El máster cambió; revisa la transcripción.")
                    queue.setdefault("reused", []).append(clip_id)
                    clip["export"] = existing
                    mark_export(clip)
                    atomic_json(db_path(root), db)
                    event("notice", detail=f'{clip["title"]}: exportación idéntica conservada; no se recodificó.')
                else:
                    export_one(root, clip, index, len(ids), req.get("sections", False))
                queue["completed"].append(clip_id)
            except Exception as exc:
                queue["failed"].append({"id": clip_id, "error": str(exc)})
                latest = load_db(root)
                for c in latest["clips"]:
                    if c["id"] == clip_id:
                        c["error"] = str(exc)
                        c["exportState"] = "error"
                atomic_json(db_path(root), latest)
                event("clip_error", id=clip_id, detail=str(exc))
            atomic_json(queue_path, queue)
        queue["status"] = "finished"
    finally:
        if queue["status"] == "running":
            queue["status"] = "interrupted"
        atomic_json(queue_path, queue)
    return queue


def export_one(root, clip, index=0, total=1, sections=False):
    import stage2
    source = source_identity(clip["source"]["path"])
    if not same_source(clip["source"], source):
        raise ValueError("El máster cambió; no se exportará con una transcripción antigua.")
    media = media_info(source["path"])
    blocks = validate_blocks(clip["blocks"], media["duration"])
    duration = sum(b["end"]-b["start"] for b in blocks)
    required = int(duration * 40_000_000 / 8 * 2.5) + 512 * 1024**2
    if shutil.disk_usage(root).free < required:
        raise ValueError(f"Espacio insuficiente: se recomienda al menos {required/1024**3:.1f} GB para este clip.")
    words = normalized_words(clip.get("transcript"))
    captions = stage2.captions_settings(clip.get('captions'))
    if captions['mode'] != 'off' and not words:
        raise ValueError('Activa captions solo con una transcripción word-level. No se exportará un video sin los captions pedidos.')
    if captions['mode'] == 'burn' and not re.search(r'\bass\s', run([command('ffmpeg'), '-hide_banner', '-filters'])):
        raise ValueError('Tu FFmpeg no incluye ASS/libass. Usa captions separados (SRT/ASS) o un FFmpeg con libass.')
    vf = crop_filter(media, clip.get("format", {}))
    cache = cache_dir(root) / "sections"
    cache.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, block in enumerate(blocks):
        section_vf = stage2.tracking_filter(media, clip.get('format', {}), block, clip.get('tracking'), vf)
        key = hashlib.sha256(json.dumps([source, block["start"], block["end"], section_vf, captions if captions['mode']=='burn' else None, "40M-v2"], sort_keys=True).encode()).hexdigest()[:32]
        target = cache / f"{key}.mp4"
        if not target.exists():
            partial = target.with_suffix(".partial.mp4")
            try:
                if captions['mode'] == 'burn':
                    width, height = stage2.output_size(media, clip.get('format', {}))
                    ass = stage2.write_captions(cache / key, virtual_words(words, [block]), captions, width, height)
                    if any(char in str(ass) for char in "'\\:"):
                        raise ValueError('Para incrustar captions, usa una ruta sin apóstrofes, dos puntos ni barras invertidas.')
                    section_vf += f",ass=filename='{ass}'"
                for codec in ("h264_videotoolbox", "libx264"):
                    args = [command("ffmpeg"), "-v", "error", "-y", "-ss", str(block["start"]), "-i", source["path"],
                            "-t", str(block["end"]-block["start"]), "-map", "0:v:0", "-map", "0:a:0?", "-vf", section_vf,
                            "-c:v", codec, "-b:v", "40M", "-maxrate", "48M", "-bufsize", "80M", "-pix_fmt", "yuv420p"]
                    if codec == "h264_videotoolbox":
                        args.extend(["-allow_sw", "1"])
                    args.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(partial)])
                    try:
                        render_section(args, block["end"]-block["start"], clip["id"], index, total, i, len(blocks))
                        break
                    except RuntimeError:
                        if codec == "libx264":
                            raise
                        event("notice", detail="VideoToolbox no disponible; reintentando con H.264 por software.")
                check = media_info(partial)
                if abs(check["duration"]-(block["end"]-block["start"])) > .3:
                    raise ValueError("La duración de la sección exportada no coincide; no se publicará.")
                os.replace(partial, target)
            finally:
                partial.unlink(missing_ok=True)
        parts.append(target)
        event("progress", id=clip["id"], progress=round((index+(i+1)/(len(blocks)+1))/total*100),
              clipProgress=round((i+1)/(len(blocks)+1)*100), detail=f"Sección {i+1}/{len(blocks)} lista")
    videos = root / "VIDEOS"
    videos.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w -]", "_", clip["title"]).strip()[:70] or "Clip"
    signature = recipe_signature(clip)
    # Archivo inmutable por revisión: el anterior nunca se sobrescribe.
    final = videos / f'{safe}_{clip["id"][:8]}_{clip.get("variant", "MANUAL")}_r{clip["revision"]}_{signature[:8]}.mp4'
    partial = final.with_suffix(".partial.mp4")
    fd, listing = tempfile.mkstemp(suffix=".concat.txt", dir=cache)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for part in parts:
                escaped = str(part.resolve()).replace("'", "'\\''")
                stream.write(f"file '{escaped}'\n")
        run([command("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
             "-c", "copy", "-movflags", "+faststart", str(partial)], timeout=1800)
        check = media_info(partial)
        if abs(check["duration"]-duration) > max(.3, len(blocks)*.08):
            raise ValueError("La duración del montaje no coincide; se conserva la versión anterior.")
        if captions['mode'] != 'off':
            width, height = stage2.output_size(media, clip.get('format', {}))
            stage2.write_captions(final.with_suffix(''), virtual_words(words, blocks), captions, width, height)
        text = "\n".join(["ABRXS-CANTER · RECETA DE MONTAJE", f'TÍTULO: {clip["title"]}', f'MÁSTER: {source["path"]}',
            f'REVISIÓN: {clip["revision"]}', f'VARIANTE: {clip.get("variant", "MANUAL")}', f"DURACIÓN: {duration:.3f}s", "",
            *[f'{i+1:02d}. {b["start"]:.3f} → {b["end"]:.3f} | {b.get("text", "")}' for i,b in enumerate(blocks)]])
        final.with_suffix(".txt").write_text(text + "\n", encoding="utf-8")
        atomic_json(final.with_suffix(".json"), {"recipe": clip, "words": virtual_words(words, blocks), "signature": signature})
        os.replace(partial, final)
        latest = load_db(root)
        for saved in latest["clips"]:
            if saved["id"] == clip["id"]:
                if saved.get("export") and saved["export"].get("path") != str(final):
                    saved.setdefault("exportHistory", []).append(saved["export"])
                saved["export"] = {"path": str(final), "signature": signature, "revision": clip["revision"], "createdAt": time.time()}
                saved.pop("error", None)
                mark_export(saved)
        atomic_json(db_path(root), latest)
        if sections and len(blocks) > 1:
            folder = root / "RECURSOS" / clip["id"] / f'SECCIONES_r{clip["revision"]}'
            folder.mkdir(parents=True, exist_ok=True)
            registry = read_json(root / "EDICIONES" / "SECCIONES_REGISTRO.json", {})
            for i, (block, part) in enumerate(zip(blocks, parts)):
                duplicate = registry.get(part.stem)
                suffix = f"_DUPLICADA_DE_{duplicate}" if duplicate and duplicate != clip["id"] else ""
                destination = folder / f"{i+1:02d}{suffix}.mp4"
                shutil.copy2(part, destination)
                destination.with_suffix(".txt").write_text(f'MÁSTER: {source["path"]}\nINICIO: {block["start"]:.3f}\nFINAL: {block["end"]:.3f}\n{block.get("text", "")}\n', encoding="utf-8")
                registry.setdefault(part.stem, clip["id"])
            atomic_json(root / "EDICIONES" / "SECCIONES_REGISTRO.json", registry)
        extras = clip.get("extras") or {}
        if extras.get("voiceovers") or extras.get("xrolls"):
            folder = root / "RECURSOS" / clip["id"]
            folder.mkdir(parents=True, exist_ok=True)
            atomic_json(folder / "EXTRAS_EDITORIALES.json", extras)
            (folder / "EXTRAS_EDITORIALES.txt").write_text(json.dumps(extras, ensure_ascii=False, indent=2), encoding="utf-8")
        prune_cache(root, parts)
        event("clip_complete", id=clip["id"], path=str(final), progress=round((index+1)/total*100))
    finally:
        partial.unlink(missing_ok=True)
        Path(listing).unlink(missing_ok=True)


def dispatch(req):
    op = req["op"]
    root = root_for(req)
    if op.startswith("studio_"):
        import stage3
        return stage3.dispatch(req, sys.modules[__name__])
    if op in ("library", "library_snapshot"):
        db = load_db(root) if op == "library_snapshot" else migrate_reports(root, req.get("outputPath"))
        for clip in db["clips"]:
            mark_export(clip)
        manifests = []
        folder = cache_dir(root) / "assets"
        if folder.is_dir() and not folder.is_symlink():
            for p in folder.glob("*/index.json"):
                if p.is_file() and not p.is_symlink() and not p.parent.is_symlink():
                    value = read_json(p)
                    if value and all(Path(t["path"]).is_file() for t in value.get("thumbs", [])):
                        manifests.append(value)
        return {**db, "assets": manifests, "queue": read_json(root / "EDICIONES/COLA_EXPORTACION.json"),
                "draft": read_json(root / "EDICIONES/BORRADOR_STAGE1.json")}
    if op == "source":
        return source_data(req)
    if op == "save":
        return save_clip(req)
    if op == "draft":
        atomic_json(root / "EDICIONES/BORRADOR_STAGE1.json", req["draft"])
        return {"saved": True}
    if op == "frame":
        return frame_step(req)
    if op == "assets":
        return assets(req)
    if op == "visual":
        import stage2
        return stage2.visual_job(req)
    if op == "caption_style":
        import stage2
        return stage2.style(read_json(Path(req['path'])))
    if op == "import":
        return import_editorial(req)
    if op == "export":
        return export_clips(req)
    if op == "clear_cache":
        return {"cacheBytes": prune_cache(root, limit=0)}
    if op == "relink":
        source = source_identity(req["video"])
        db = load_db(root)
        clip = next(c for c in db["clips"] if c["id"] == req["id"])
        if (source["sampleHash"], source["size"]) != (clip["source"]["sampleHash"], clip["source"]["size"]):
            raise ValueError("El archivo elegido no coincide con la huella parcial del máster original.")
        for c in db["clips"]:
            if c["source"]["sampleHash"] == source["sampleHash"]:
                c["source"] = source
        atomic_json(db_path(root), db)
        return {"source": source}
    raise ValueError("Operación desconocida.")


def main():
    global REQUEST_ID
    req = json.load(sys.stdin)
    REQUEST_ID = req.get("requestId")
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    try:
        result = dispatch(req)
        print("ABRXS_STAGE1_RESULT:" + json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
