"""Funciones opcionales: captions y Vision local de macOS. Sin modelos descargados."""
from pathlib import Path
import hashlib
import json
import math
import re


def style(value=None):
    v = value or {}
    result = {'font': str(v.get('font', 'Arial')), 'size': float(v.get('size', 48)),
              'color': str(v.get('color', '#FFFFFF')), 'background': str(v.get('background', '#000000')),
              'position': v.get('position', 'bottom'), 'bold': bool(v.get('bold', True)),
              'box': bool(v.get('box', False)), 'words': int(v.get('words', 6)),
              'margin': int(v.get('margin', 80)), 'outline': float(v.get('outline', 2))}
    if not re.fullmatch(r'[\w .-]{1,64}', result['font'], re.UNICODE):
        raise ValueError('Nombre de fuente inválido en el estilo de captions.')
    if not math.isfinite(result['size']) or not 12 <= result['size'] <= 120:
        raise ValueError('Tamaño de captions: 12 a 120.')
    if not 1 <= result['words'] <= 12 or not 0 <= result['margin'] <= 400 or not 0 <= result['outline'] <= 8:
        raise ValueError('Estilo de captions fuera de rango.')
    if result['position'] not in {'bottom', 'top', 'center'}:
        raise ValueError('Posición de captions: bottom, top o center.')
    for key in ('color', 'background'):
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', result[key]):
            raise ValueError('Los colores deben tener formato #RRGGBB.')
    return result


def captions_settings(value=None):
    v = value or {}
    mode = v.get('mode', 'off')
    if mode not in {'off', 'sidecar', 'burn'}:
        raise ValueError('Modo de captions inválido.')
    return {'mode': mode, 'style': style(v.get('style'))}


def cues(words, max_words=6):
    result, batch = [], []
    for word in words:
        if batch and (word['start'] - batch[-1]['end'] > .6 or word.get('blockUid') != batch[-1].get('blockUid')):
            result.append({'start': batch[0]['start'], 'end': batch[-1]['end'], 'text': ' '.join(w['text'] for w in batch)})
            batch = []
        batch.append(word)
        if len(batch) >= max_words or re.search(r'[.!?]$', word['text']):
            result.append({'start': batch[0]['start'], 'end': batch[-1]['end'], 'text': ' '.join(w['text'] for w in batch)})
            batch = []
    if batch:
        result.append({'start': batch[0]['start'], 'end': batch[-1]['end'], 'text': ' '.join(w['text'] for w in batch)})
    return [c for c in result if c['end'] > c['start']]


def stamp(value, ass=False):
    units = 100 if ass else 1000
    n = max(0, round(value * units))
    seconds, fraction = divmod(n, units)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}.{fraction:02d}' if ass else f'{hours:02d}:{minutes:02d}:{seconds:02d},{fraction:03d}'


def ass_color(hex_color):
    return '&H00' + hex_color[5:7] + hex_color[3:5] + hex_color[1:3]


def write_captions(base, words, settings, width, height):
    s = style(settings.get('style'))
    lines = cues(words, s['words'])
    if not lines:
        raise ValueError('No hay palabras con tiempos para generar captions. Selecciona una transcripción word-level.')
    Path(str(base) + '.srt').write_text('\n\n'.join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i, c in enumerate(lines)) + '\n', encoding='utf-8')
    align = {'bottom': 2, 'top': 8, 'center': 5}[s['position']]
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{s['font']},{s['size']},{ass_color(s['color'])},&H00FFFFFF,{ass_color(s['background'])},{ass_color(s['background'])},{-1 if s['bold'] else 0},0,0,0,100,100,0,0,{3 if s['box'] else 1},{s['outline']},0,{align},60,60,{s['margin']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    for c in lines:
        # Nunca interpretar texto hablado como etiquetas ASS o saltos arbitrarios.
        text = c['text'].replace('\\', ' ').replace('{', '').replace('}', '').replace('\n', ' ').replace('\r', ' ')
        events.append(f"Dialogue: 0,{stamp(c['start'], True)},{stamp(c['end'], True)},Default,,0,0,0,,{text}")
    path = Path(str(base) + '.ass')
    path.write_text(header + '\n'.join(events) + '\n', encoding='utf-8')
    return path


def output_size(media, fmt):
    return {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080)}.get(fmt.get('aspect'), (media['width']//2*2, media['height']//2*2))


def position_at(points, time, fallback=(.5, .5)):
    if not points:
        return fallback
    previous = points[0]
    for point in points[1:]:
        if point['time'] >= time:
            fraction = max(0, min(1, (time - previous['time']) / max(.0001, point['time'] - previous['time'])))
            return tuple(previous[k] + (point[k] - previous[k]) * fraction for k in ('x', 'y'))
        previous = point
    return previous['x'], previous['y']


def validate_tracking(value):
    if not value:
        return None
    points = value.get('points', [])
    if len(points) > 600:
        raise ValueError('Demasiados puntos de seguimiento.')
    previous = -1
    for p in points:
        numbers = [float(p[k]) for k in ('time', 'x', 'y')]
        if not all(math.isfinite(n) for n in numbers) or numbers[0] <= previous or not all(0 <= n <= 1 for n in numbers[1:]):
            raise ValueError('Puntos de seguimiento inválidos.')
        previous = numbers[0]
    return value


def expression(points, axis):
    result = str(points[-1][axis])
    for left, right in reversed(list(zip(points, points[1:]))):
        span = right['time'] - left['time']
        if span <= 0: continue
        line = f"({left[axis]}+({right[axis]-left[axis]})*(t-{left['time']})/{span})"
        result = f"if(lt(t,{right['time']}),{line},{result})"
    return result


def tracking_filter(media, fmt, block, tracking, fallback):
    if not tracking or fmt.get('aspect') == 'original' or fmt.get('mode') != 'cover':
        return fallback
    validate_tracking(tracking)
    if tracking.get('format', {}).get('aspect') != fmt.get('aspect'):
        raise ValueError('El seguimiento se calculó para otro formato. Quítalo o vuelve a calcularlo.')
    if tracking.get('ranges') and not any(r.get('uid') == block.get('uid') for r in tracking['ranges']):
        return fallback
    source = tracking.get('points', [])
    if not source: return fallback
    # Se limita la expresión por sección; los puntos de origen se trasladan a t local.
    times = [block['start'], *[p['time'] for p in source if block['start'] < p['time'] < block['end']], block['end']]
    if len(times) > 100:
        stride = math.ceil(len(times) / 98)
        times = [times[0], *times[1:-1:stride], times[-1]]
    points = []
    for time in times:
        x, y = position_at(source, time, (fmt.get('x', .5), fmt.get('y', .5)))
        points.append({'time': round(time - block['start'], 6), 'x': round(x, 6), 'y': round(y, 6)})
    w, h = media['width'], media['height']
    tw, th = output_size(media, fmt)
    ratio = tw / th
    cw, ch = (int(h*ratio)//2*2, h//2*2) if w/h > ratio else (w//2*2, int(w/ratio)//2*2)
    return f"crop={cw}:{ch}:x='(iw-ow)*({expression(points,'x')})':y='(ih-oh)*({expression(points,'y')})',scale={tw}:{th},setsar=1"


def visual_job(req):
    import stage1 as m
    root = m.root_for(req)
    data = m.source_data(req)
    media = data['media']
    mode = req.get('mode', 'analysis')
    if mode not in {'analysis', 'face', 'body', 'object'}:
        raise ValueError('Modo Vision desconocido.')
    start = max(0, m.finite(req.get('start', 0)))
    end = min(media['duration'], m.finite(req.get('end', media['duration'])))
    if end <= start: raise ValueError('Rango visual inválido.')
    step = max(.25, m.finite(req.get('step', 2)), (end-start)/590)
    rect = req.get('rect', [.35, .2, .3, .6])
    if len(rect) != 4 or not all(math.isfinite(float(v)) and 0 <= float(v) <= 1 for v in rect) or rect[2] <= 0 or rect[3] <= 0 or rect[0]+rect[2] > 1 or rect[1]+rect[3] > 1:
        raise ValueError('Rectángulo de objeto inválido: x/y/ancho/alto normalizados, dentro de la imagen.')
    settings = {'video': data['source']['path'], 'start': start, 'end': end, 'step': step, 'mode': mode, 'rect': rect}
    folder = root / 'ANALISIS_VISUAL'
    folder.mkdir(exist_ok=True)
    key = hashlib.sha256(json.dumps([data['source'], settings], sort_keys=True).encode()).hexdigest()[:24]
    path = folder / f'{mode}_{key}.json'
    if path.is_file(): return m.read_json(path)
    worker = Path(__file__).parent / 'native' / 'abrxs-vision'
    if not worker.is_file(): raise ValueError('Falta el componente Vision local. Reconstruye la app Etapa 2.')
    m.event('progress', progress=1, detail=f'Vision local: hasta {math.ceil((end-start)/step)} muestras. Puede tardar; no se envía el video a internet.')
    import tempfile
    m.cache_dir(root).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vision-', dir=m.cache_dir(root)) as temporary:
        selection = f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{step})',scale=960:-2,showinfo"
        info = m.run([m.command('ffmpeg'), '-hide_banner', '-loglevel', 'info', '-ss', str(start), '-copyts',
            '-i', data['source']['path'], '-to', str(end), '-an', '-vf', selection,
            '-fps_mode', 'vfr', '-frames:v', '600', str(Path(temporary) / 'frame-%04d.jpg')], timeout=1800, include_stderr=True)
        times = [float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([-0-9.e+]+)', info)]
        images = sorted(Path(temporary).glob('frame-*.jpg'))
        if len(images) != len(times) or not images:
            raise ValueError('No se pudieron obtener fotogramas con timestamps verificables.')
        frames = [{'path':str(p), 'time':t} for p,t in zip(images,times)]
        output = m.run([str(worker), '--stdin'], input=json.dumps({**settings, 'frames':frames}), timeout=1800)
    samples = [json.loads(line.split(':', 1)[1]) for line in output.splitlines() if line.startswith('ABRXS_VISION:')]
    # Convertir centro del sujeto a posición del recorte. Anclaje central.
    points, lost, previous, last_time = [], 0, None, -1
    fmt = m.validate_format(req.get('format', {'aspect': '9:16', 'mode': 'cover'}))
    tw, th = output_size(media, fmt)
    w, h = media['width'], media['height']
    ratio = tw/th
    cw, ch = (min(w, h*ratio), h) if w/h > ratio else (w, min(h, w/ratio))
    for sample in samples:
        target = sample.get('target')
        if sample['time'] <= last_time: continue
        last_time = sample['time']
        if target:
            cx, cy = target['x'] + target['width']/2, target['y'] + target['height']/2
            position = (max(0,min(1,(cx*w-cw/2)/(w-cw))) if w>cw else .5,
                        max(0,min(1,(cy*h-ch/2)/(h-ch))) if h>ch else .5)
            if previous: position = tuple(a*.65+b*.35 for a,b in zip(previous, position))
            previous = position
        elif mode != 'analysis': lost += 1
        if previous: points.append({'time': sample['time'], 'x': previous[0], 'y': previous[1]})
    lines = []
    for s in samples:
        text = ' | '.join(t['text'].replace('\n',' ') for t in s['text'])
        lines.append(f"{s['time']:.3f}s: {len(s['faces'])} rostro(s), {len(s['bodies'])} cuerpo(s). Texto visible: {text or 'no detectado'}" + (' [SEGUIMIENTO PERDIDO]' if s.get('lost') else ''))
    result = {'source': data['source'], 'settings': settings, 'samples': samples, 'points': points, 'lost': lost,
              'format': fmt, 'path': str(path), 'textPath': str(path.with_suffix('.txt')),
              'limitations': 'Muestreo local de rostros/cuerpos/OCR. No es descripción semántica ni identifica hablantes. El seguimiento puede perder el objetivo o cambiar tras una oclusión.'}
    m.atomic_json(path, result)
    path.with_suffix('.txt').write_text('ABRXS · EVIDENCIA VISUAL LOCAL\n' + result['limitations'] + '\n\n' + '\n'.join(lines), encoding='utf-8')
    if req.get('outputPath'):
        package = Path(req['outputPath']) / 'PAQUETE_PARA_IA'
        if package.is_dir():
            import shutil
            shutil.copy2(path.with_suffix('.txt'), package / 'EVIDENCIA_VISUAL.txt')
    return result
