"""Estado editorial y contexto del estudio. Sin modelos ni red."""
import json
import math
from pathlib import Path
import re
import time
import uuid

def default_workspace():
    return {"schemaVersion": 1, "fragments": [], "positions": {}, "view": "grid", "visual": None}

def validate_workspace(value):
    if not isinstance(value, dict):
        raise ValueError("Estado del estudio no válido.")
    result = default_workspace()
    fragments = value.get("fragments", [])
    if not isinstance(fragments, list) or len(fragments) > 1000:
        raise ValueError("La bandeja admite hasta 1000 fragmentos.")
    ids = set()
    for item in fragments:
        start, end = float(item["start"]), float(item["end"])
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            raise ValueError("Fragmento vacío o tiempo no válido.")
        identity = str(item.get("id") or uuid.uuid4())
        if identity in ids:
            raise ValueError("ID de fragmento duplicado.")
        ids.add(identity)
        result["fragments"].append({"id": identity, "start": start, "end": end,
            "text": str(item.get("text", ""))[:12000], "sourceHash": str(item.get("sourceHash", ""))[:128]})
    for key, point in list(value.get("positions", {}).items())[:3000]:
        x, y = float(point["x"]), float(point["y"])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Posición no válida.")
        result["positions"][str(key)[:200]] = {"x": max(0, min(100000, x)), "y": max(0, min(100000, y))}
    result["view"] = value.get("view") if value.get("view") in {"grid", "list", "kanban", "map"} else "grid"
    result["visual"] = str(value["visual"])[:4096] if value.get("visual") else None
    return result

def dispatch(req, m):
    root = m.root_for(req)
    path = root / "EDICIONES/ESTUDIO.json"
    op = req["op"]
    if op == "studio_load":
        return validate_workspace(m.read_json(path, default_workspace()))
    if op == "studio_save":
        value = validate_workspace(req["workspace"])
        m.atomic_json(path, value)
        return value
    if op == "studio_visual":
        report = m.read_json(path, default_workspace()).get("visual")
        if not report:
            return {"samples": []}
        candidate = Path(report).resolve()
        candidate.relative_to(root.resolve())
        data = m.read_json(candidate, {})
        if req.get("video") and data.get("source", {}).get("sampleHash") != m.source_identity(req["video"])["sampleHash"]:
            return {"samples": [], "limitations": "El informe pertenece a otro máster. Vuelve a analizar."}
        return {"samples": data.get("samples", [])[:600], "limitations": data.get("limitations", ""), "textPath": data.get("textPath")}
    data = m.source_data(req)
    if op == "studio_suggest":
        maximum = max(10, min(120, float(req.get("seconds", 45))))
        keywords = set(re.findall(r"\w{4,}", str(req.get("keywords", "")).lower()))
        chunks, batch = [], []
        for word in data["words"]:
            batch.append(word)
            length = word["end"] - batch[0]["start"]
            if length >= maximum or (length >= maximum * .65 and re.search(r"[.!?]$", word["text"])):
                chunks.append(batch)
                batch = []
        if batch and batch[-1]["end"] - batch[0]["start"] >= 5:
            chunks.append(batch)
        proposed = []
        for chunk in chunks:
            text = " ".join(w["text"] for w in chunk)
            matches = sorted(keywords & set(re.findall(r"\w{4,}", text.lower())))
            proposed.append({"start": chunk[0]["start"], "end": chunk[-1]["end"], "text": text,
                "score": len(matches), "reason": "Regla local: duración y frases" + ("; coincidencias: " + ", ".join(matches) if matches else "")})
        proposed.sort(key=lambda v: (-v["score"], v["start"]))
        return {"items": proposed[:12], "source": data["source"], "limitations": "Propuestas locales para revisar; no evalúan significado ni potencial viral."}
    if op == "studio_context":
        visual = dispatch({**req, "op": "studio_visual", "video": data["source"]["path"]}, m)
        references = {}
        for name in ("brand", "structure"):
            if req.get(name):
                candidate = Path(req[name])
                if candidate.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("Los archivos de contexto deben pesar menos de 2 MB.")
                references[name] = candidate.read_text(encoding="utf-8-sig")
        bundle = {"schemaVersion": 1, "source": data["source"], "duration": data["media"]["duration"],
            "words": data["words"], "visual": visual, "criteria": references,
            "clips": [c for c in m.load_db(root)["clips"] if c.get("source", {}).get("sampleHash") == data["source"]["sampleHash"]],
            "instructions": "Devuelve JSON {clips:[{id,title,segments:[{start,end}]}]}. Tiempos en segundos del máster. No inventes evidencia ni tiempos."}
        folder = root / "CONTEXTO_IA" / str(time.time_ns())
        folder.mkdir(parents=True)
        m.atomic_json(folder / "CONTEXTO.json", bundle)
        lines = ["ABRXS-CANTER · CONTEXTO DEL MÁSTER", json.dumps({k: v for k, v in bundle.items() if k != "words"}, ensure_ascii=False, indent=2), "TRANSCRIPCIÓN"]
        lines.extend(f'{w["start"]:.3f} → {w["end"]:.3f} | {w["text"]}' for w in data["words"])
        (folder / "CONTEXTO.txt").write_text("\n".join(lines), encoding="utf-8")
        return {"path": str(folder), "textPath": str(folder / "CONTEXTO.txt")}
    raise ValueError("Operación de estudio desconocida.")
