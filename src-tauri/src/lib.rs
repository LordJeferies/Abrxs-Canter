use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    fs,
    io::{BufRead, BufReader},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::Mutex,
    time::{SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Default)]
struct JobState {
    pid: Mutex<Option<u32>>,
}

#[derive(Debug, Deserialize)]
struct JobConfig {
    editorial: Option<String>,
    video: String,
    transcript: Option<String>,
    brand: Option<String>,
    structure: Option<String>,
    output: String,
    mode: String,
    export_mode: String,
    export_xrolls: bool,
}

#[derive(Debug, Serialize, Clone)]
struct FinishedPayload {
    success: bool,
    message: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ProjectRecord {
    id: String,
    name: String,
    path: String,
    created_at: u64,
    updated_at: u64,
    last_output: Option<String>,
    settings: Value,
}

fn now_seconds() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

fn safe_project_name(value: &str) -> String {
    let cleaned: String = value.trim().chars().map(|c| {
        if c.is_alphanumeric() || matches!(c, ' ' | '-' | '_') { c } else { '_' }
    }).collect();
    let compact = cleaned.split_whitespace().collect::<Vec<_>>().join(" ");
    if compact.is_empty() { "Proyecto sin nombre".into() } else { compact }
}

fn registry_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("projects.json"))
}

fn load_registry(app: &AppHandle) -> Result<Vec<ProjectRecord>, String> {
    let path = registry_path(app)?;
    if !path.exists() { return Ok(Vec::new()); }
    let raw = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| format!("La biblioteca de proyectos está dañada: {e}"))
}

fn save_registry(app: &AppHandle, projects: &[ProjectRecord]) -> Result<(), String> {
    let path = registry_path(app)?;
    let temp = path.with_extension("json.tmp");
    fs::write(&temp, serde_json::to_vec_pretty(projects).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    fs::rename(temp, path).map_err(|e| e.to_string())
}

fn write_project_meta(project: &ProjectRecord) -> Result<(), String> {
    let path = PathBuf::from(&project.path).join(".abrxs-canter.json");
    fs::write(path, serde_json::to_vec_pretty(project).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())
}

fn discover_latest_output(root: &Path) -> Option<String> {
    if root.join("PROYECTO.json").exists() { return Some(root.to_string_lossy().to_string()); }
    let mut candidates: Vec<(SystemTime, PathBuf)> = fs::read_dir(root).ok()?.flatten()
        .map(|entry| entry.path())
        .filter(|path| path.is_dir() && path.join("PROYECTO.json").exists())
        .filter_map(|path| fs::metadata(&path).ok()?.modified().ok().map(|time| (time, path)))
        .collect();
    candidates.sort_by_key(|item| item.0);
    candidates.pop().map(|item| item.1.to_string_lossy().to_string())
}

#[tauri::command]
fn list_projects(app: AppHandle) -> Result<Vec<ProjectRecord>, String> {
    let mut projects = load_registry(&app)?;
    projects.retain(|project| Path::new(&project.path).is_dir());
    projects.sort_by(|a, b| b.updated_at.cmp(&a.updated_at));
    save_registry(&app, &projects)?;
    Ok(projects)
}

#[tauri::command]
fn create_project(app: AppHandle, name: String, parent: String) -> Result<ProjectRecord, String> {
    let name = safe_project_name(&name);
    let parent = PathBuf::from(parent);
    if !parent.is_dir() { return Err("La carpeta elegida no existe.".into()); }
    let mut folder_name = name.replace(' ', "_");
    let mut root = parent.join(&folder_name);
    if root.exists() {
        folder_name = format!("{}_{}", folder_name, now_seconds());
        root = parent.join(folder_name);
    }
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let now = now_seconds();
    let project = ProjectRecord {
        id: format!("ac-{now}"), name, path: root.to_string_lossy().to_string(),
        created_at: now, updated_at: now, last_output: None, settings: json!({}),
    };
    let mut projects = load_registry(&app)?;
    projects.push(project.clone());
    save_registry(&app, &projects)?;
    write_project_meta(&project)?;
    Ok(project)
}

#[tauri::command]
fn register_project(app: AppHandle, path: String) -> Result<ProjectRecord, String> {
    let root = PathBuf::from(path).canonicalize().map_err(|e| e.to_string())?;
    if !root.is_dir() { return Err("Debes seleccionar una carpeta de proyecto.".into()); }
    let mut projects = load_registry(&app)?;
    if let Some(existing) = projects.iter_mut().find(|project| Path::new(&project.path) == root) {
        existing.updated_at = now_seconds();
        if existing.last_output.is_none() { existing.last_output = discover_latest_output(&root); }
        let result = existing.clone();
        save_registry(&app, &projects)?;
        write_project_meta(&result)?;
        return Ok(result);
    }
    let meta_path = root.join(".abrxs-canter.json");
    let now = now_seconds();
    let mut project = if meta_path.exists() {
        serde_json::from_slice::<ProjectRecord>(&fs::read(meta_path).map_err(|e| e.to_string())?)
            .unwrap_or(ProjectRecord {
                id: format!("ac-{now}"), name: root.file_name().unwrap_or_default().to_string_lossy().replace('_', " "),
                path: root.to_string_lossy().to_string(), created_at: now, updated_at: now,
                last_output: discover_latest_output(&root), settings: json!({}),
            })
    } else {
        ProjectRecord {
            id: format!("ac-{now}"), name: root.file_name().unwrap_or_default().to_string_lossy().replace('_', " "),
            path: root.to_string_lossy().to_string(), created_at: now, updated_at: now,
            last_output: discover_latest_output(&root), settings: json!({}),
        }
    };
    project.path = root.to_string_lossy().to_string();
    project.updated_at = now;
    projects.push(project.clone());
    save_registry(&app, &projects)?;
    write_project_meta(&project)?;
    Ok(project)
}

#[tauri::command]
fn update_project(app: AppHandle, id: String, last_output: Option<String>, settings: Value) -> Result<ProjectRecord, String> {
    let mut projects = load_registry(&app)?;
    let project = projects.iter_mut().find(|project| project.id == id).ok_or("Proyecto no encontrado")?;
    project.updated_at = now_seconds();
    if let Some(output) = last_output { project.last_output = Some(output); }
    if !settings.is_null() { project.settings = settings; }
    let result = project.clone();
    save_registry(&app, &projects)?;
    write_project_meta(&result)?;
    Ok(result)
}

#[tauri::command]
fn forget_project(app: AppHandle, id: String) -> Result<(), String> {
    let mut projects = load_registry(&app)?;
    projects.retain(|project| project.id != id);
    save_registry(&app, &projects)
}

fn review_file(project_path: &str) -> PathBuf {
    PathBuf::from(project_path).join("REVISIONES.json")
}

#[tauri::command]
fn load_reviews(project_path: String) -> Result<Value, String> {
    let path = review_file(&project_path);
    if !path.exists() { return Ok(json!({"videos": {}})); }
    serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_review(project_path: String, video_path: String, status: String, note: String) -> Result<Value, String> {
    let path = review_file(&project_path);
    let mut data = load_reviews(project_path)?;
    if !data.is_object() { data = json!({"videos": {}}); }
    if data.get("videos").and_then(Value::as_object).is_none() { data["videos"] = json!({}); }
    data["videos"][&video_path] = json!({"status": status, "note": note, "updatedAt": now_seconds()});
    let temp = path.with_extension("json.tmp");
    fs::write(&temp, serde_json::to_vec_pretty(&data).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    fs::rename(temp, path).map_err(|e| e.to_string())?;
    Ok(data)
}

#[tauri::command]
fn load_compact_transcript(output_path: String) -> Result<Value, String> {
    let path = PathBuf::from(output_path).join("TRANSCRIPCIONES/TRANSCRIPCION_COMPACTA.json");
    if !path.exists() { return Err("Este resultado todavía no tiene una transcripción compacta.".into()); }
    serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

fn read_json_file(path: &Path, description: &str) -> Result<Value, String> {
    if !path.exists() {
        return Err(format!("No se encontro {description}: {}", path.display()));
    }
    serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?)
        .map_err(|e| format!("{description} no es valido: {e}"))
}

#[tauri::command]
fn load_editor_data(output_path: String) -> Result<Value, String> {
    let root = PathBuf::from(&output_path);
    let project = read_json_file(&root.join("PROYECTO.json"), "el informe del proyecto")?;
    let word_path = root.join("TRANSCRIPCIONES/TRANSCRIPCION_PALABRA_POR_PALABRA.json");
    let compact_path = root.join("TRANSCRIPCIONES/TRANSCRIPCION_COMPACTA.json");
    let word_level = read_json_file(&word_path, "la transcripcion palabra por palabra")?;
    let compact = read_json_file(&compact_path, "la transcripcion compacta")?;
    let video = project.get("video").and_then(Value::as_str)
        .ok_or("El informe del proyecto no contiene la ruta del video master")?;
    if !Path::new(video).is_file() {
        return Err("El video master ya no se encuentra en su ubicacion original.".into());
    }
    Ok(json!({
        "outputPath": root.to_string_lossy(),
        "video": video,
        "transcriptPath": word_path.to_string_lossy(),
        "words": word_level.get("words").cloned().unwrap_or_else(|| json!([])),
        "phrases": compact.get("segments").cloned().unwrap_or_else(|| json!([])),
        "media": project.get("media").cloned().unwrap_or_else(|| json!({})),
        "sourceTranscript": project.get("transcript").cloned().unwrap_or(Value::Null)
    }))
}

fn editor_draft_path(project_path: &str) -> PathBuf {
    PathBuf::from(project_path).join("EDICIONES/BORRADOR_ACTUAL.json")
}

#[tauri::command]
fn load_editor_draft(project_path: String) -> Result<Value, String> {
    let path = editor_draft_path(&project_path);
    if !path.exists() { return Ok(Value::Null); }
    read_json_file(&path, "el borrador del editor")
}

#[tauri::command]
fn save_editor_draft(
    project_path: String,
    title: String,
    video_path: String,
    transcript_path: String,
    blocks: Value,
) -> Result<String, String> {
    let items = blocks.as_array().ok_or("Los bloques del editor no son validos")?;
    let folder = PathBuf::from(&project_path).join("EDICIONES");
    fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    let path = editor_draft_path(&project_path);
    let payload = json!({
        "schemaVersion": 1,
        "app": "abrxs-Canter",
        "version": "3.4.1",
        "title": safe_project_name(&title),
        "video": video_path,
        "transcript": transcript_path,
        "updatedAt": now_seconds(),
        "blocks": items
    });
    let temp = path.with_extension("json.tmp");
    fs::write(&temp, serde_json::to_vec_pretty(&payload).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    fs::rename(temp, &path).map_err(|e| e.to_string())?;
    Ok(path.to_string_lossy().to_string())
}

const EDITORIAL_REPAIR_TEMPLATE: &str = r#"PLANTILLA PARA REPARAR UN ARCHIVO EDITORIAL PARA Abrxs-Canter 3.4.1

SUBE A LA IA:
1. El archivo editorial que abrxs-Canter no reconocio.
2. La transcripcion compacta del mismo video.
3. Este archivo.
4. Opcionalmente la informacion de marca y la estructura de clips.

INSTRUCCION PARA LA IA
Convierte el archivo editorial aportado a JSON estricto. Conserva todos los clips, titulos, secciones y el orden narrativo. No resumas ni inventes texto hablado. Si una pieza usa partes lejanas del master, crea una seccion por tramo. Si hay texto sin tiempos, usa null en start/end. Si hay tiempos sin texto, conserva los tiempos y deja text vacio. Si existen ambos, conserva ambos aunque parezcan desfasados.

Devuelve UNICAMENTE JSON valido, sin Markdown ni explicaciones:
{
  "clips": [
    {
      "id": "C01",
      "title": "Titulo editorial",
      "type": "video",
      "selected": true,
      "segments": [
        {
          "id": "C01_S01",
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

VALIDACION:
- Cada clip debe tener id unico, title, type y al menos una seccion.
- Cada seccion debe tener id, order, role, start, end y text.
- Usa HH:MM:SS.mmm o null.
- No conviertas un multicorte en un intervalo continuo.
- La respuesta debe poder guardarse directamente como DECISIONES_ABRXS.json.
"#;

#[tauri::command]
fn create_editorial_template(project_path: String) -> Result<String, String> {
    let root = PathBuf::from(project_path);
    if !root.is_dir() { return Err("La carpeta del proyecto no existe.".into()); }
    let path = root.join("PLANTILLA_IA_REPARAR_EDITORIAL.txt");
    let temp = root.join("PLANTILLA_IA_REPARAR_EDITORIAL.tmp");
    fs::write(&temp, EDITORIAL_REPAIR_TEMPLATE).map_err(|e| e.to_string())?;
    fs::rename(temp, &path).map_err(|e| e.to_string())?;
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
fn save_manual_editorial(project_path: String, title: String, segments: Value) -> Result<String, String> {
    let items = segments.as_array().ok_or("La secuencia manual no es válida")?;
    if items.is_empty() { return Err("Añade al menos una sección al clip.".into()); }
    let safe_title = safe_project_name(&title);
    let id = format!("MAN-{}", now_seconds());
    let normalized: Vec<Value> = items.iter().enumerate().map(|(index, item)| json!({
        "id": format!("{}_S{:02}", id, index + 1),
        "order": index + 1,
        "role": item.get("role").and_then(Value::as_str).unwrap_or("SECCION"),
        "start": item.get("start"),
        "end": item.get("end"),
        "text": item.get("text").and_then(Value::as_str).unwrap_or("")
    })).collect();
    let payload = json!({
        "schema_version": 1,
        "created_by": "Abrxs-Canter 3.4.1 manual editor",
        "clips": [{"id": id, "title": safe_title, "type": "video", "segments": normalized}]
    });
    let folder = PathBuf::from(project_path).join("DECISIONES");
    fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    let path = folder.join(format!("{}_{}.json", safe_title.replace(' ', "_"), now_seconds()));
    let temp = path.with_extension("json.tmp");
    fs::write(&temp, serde_json::to_vec_pretty(&payload).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    fs::rename(temp, &path).map_err(|e| e.to_string())?;
    Ok(path.to_string_lossy().to_string())
}

fn python_path() -> String {
    let preferred = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3";
    if Path::new(preferred).exists() {
        preferred.to_string()
    } else {
        "python3".to_string()
    }
}

const APP_PATH: &str = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin";

fn ffmpeg_path() -> &'static str {
    if Path::new("/opt/homebrew/bin/ffmpeg").exists() { "/opt/homebrew/bin/ffmpeg" } else { "ffmpeg" }
}

fn engine_path(app: &AppHandle) -> Result<PathBuf, String> {
    let bundled = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("engine/abraxas_local.py");
    if bundled.exists() {
        return Ok(bundled);
    }
    let development = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../engine/abraxas_local.py");
    if development.exists() {
        return Ok(development);
    }
    Err("No se encontró el motor abrxs-Canter incluido en la aplicación.".into())
}

#[tauri::command]
fn inspect_editorial(app: AppHandle, editorial: String) -> Result<Value, String> {
    let output = Command::new(python_path())
        .env("PATH", APP_PATH)
        .arg(engine_path(&app)?)
        .arg("--editorial")
        .arg(editorial)
        .arg("--inspect")
        .output()
        .map_err(|e| format!("No se pudo iniciar el analizador: {e}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let line = stdout
        .lines()
        .find_map(|line| line.strip_prefix("ABRXS_CANTER_INSPECT:"))
        .ok_or_else(|| String::from_utf8_lossy(&output.stderr).to_string())?;
    serde_json::from_str(line).map_err(|e| format!("Respuesta editorial inválida: {e}"))
}

#[tauri::command]
fn start_job(app: AppHandle, state: State<JobState>, config: JobConfig) -> Result<(), String> {
    let mut pid_guard = state.pid.lock().map_err(|_| "Estado interno bloqueado")?;
    if pid_guard.is_some() {
        return Err("Ya hay un proyecto en ejecución.".into());
    }
    let mut command = Command::new(python_path());
    command
        .env("PATH", APP_PATH)
        .arg(engine_path(&app)?)
        .arg("--video").arg(&config.video)
        .arg("--output").arg(&config.output)
        .arg("--export-mode").arg(&config.export_mode)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if config.mode == "prepare" {
        command.arg("--prepare-only");
    } else if let Some(editorial) = &config.editorial {
        if !editorial.is_empty() {
            command.arg("--editorial").arg(editorial);
        }
    }
    if let Some(transcript) = &config.transcript {
        if !transcript.is_empty() {
            command.arg("--transcript").arg(transcript);
        }
    }
    if let Some(brand) = &config.brand {
        if !brand.is_empty() {
            command.arg("--brand").arg(brand);
        }
    }
    if let Some(structure) = &config.structure {
        if !structure.is_empty() {
            command.arg("--structure").arg(structure);
        }
    }
    if !config.export_xrolls {
        command.arg("--no-xrolls");
    }
    let mut child = command.spawn().map_err(|e| format!("No se pudo iniciar abrxs-Canter: {e}"))?;
    let pid = child.id();
    *pid_guard = Some(pid);
    drop(pid_guard);

    let stdout = child.stdout.take().ok_or("No se pudo leer la salida del motor")?;
    let stderr = child.stderr.take().ok_or("No se pudo leer el registro del motor")?;
    let stdout_app = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if let Some(raw) = line.strip_prefix("ABRXS_CANTER_EVENT:") {
                if let Ok(payload) = serde_json::from_str::<Value>(raw) {
                    let _ = stdout_app.emit("progress-event", payload);
                }
            } else {
                let _ = stdout_app.emit("backend-line", line);
            }
        }
    });
    let stderr_app = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = stderr_app.emit("backend-line", line);
        }
    });
    std::thread::spawn(move || {
        let result = child.wait();
        if let Some(job_state) = app.try_state::<JobState>() {
            if let Ok(mut guard) = job_state.pid.lock() {
                *guard = None;
            }
        }
        let payload = match result {
            Ok(status) if status.success() => FinishedPayload { success: true, message: "Proyecto terminado".into() },
            Ok(status) => FinishedPayload { success: false, message: format!("El motor terminó con código {}", status.code().unwrap_or(-1)) },
            Err(error) => FinishedPayload { success: false, message: error.to_string() },
        };
        let _ = app.emit("job-finished", payload);
    });
    Ok(())
}

#[tauri::command]
fn cancel_job(state: State<JobState>) -> Result<(), String> {
    let pid = *state.pid.lock().map_err(|_| "Estado interno bloqueado")?;
    if let Some(pid) = pid {
        let _ = Command::new("pkill").args(["-TERM", "-P", &pid.to_string()]).status();
        let _ = Command::new("kill").args(["-TERM", &pid.to_string()]).status();
    }
    Ok(())
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    Command::new("open").arg(path).spawn().map_err(|e| e.to_string())?;
    Ok(())
}

fn collect_videos(directory: &Path, output: &mut Vec<String>) {
    let Ok(entries) = std::fs::read_dir(directory) else { return };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_videos(&path, output);
        } else if path.extension().and_then(|value| value.to_str()).is_some_and(|ext| ext.eq_ignore_ascii_case("mp4")) {
            output.push(path.to_string_lossy().to_string());
        }
    }
}

#[tauri::command]
fn list_project_videos(path: String) -> Vec<String> {
    let mut videos = Vec::new();
    collect_videos(&PathBuf::from(path).join("VIDEOS"), &mut videos);
    videos.sort();
    videos
}

#[tauri::command]
fn trim_video(source: String, start: f64, end: f64) -> Result<String, String> {
    let source_path = PathBuf::from(&source);
    if !source_path.is_file() { return Err("No se encontró el video seleccionado.".into()); }
    if !start.is_finite() || !end.is_finite() || start < 0.0 || end <= start {
        return Err("El rango de entrada y salida no es válido.".into());
    }
    let stem = source_path.file_stem().unwrap_or_default().to_string_lossy();
    let destination = source_path.with_file_name(format!("{}_AJUSTADO_{}.mp4", stem, now_seconds()));
    let partial = destination.with_extension("partial.mp4");
    let start_arg = format!("{start:.3}");
    let end_arg = format!("{end:.3}");
    let run = |codec: &str, allow_sw: bool| -> Result<std::process::Output, String> {
        let mut command = Command::new(ffmpeg_path());
        command.env("PATH", APP_PATH)
            .args(["-y", "-ss", &start_arg, "-to", &end_arg, "-i", &source])
            .args(["-map", "0:v:0", "-map", "0:a:0?", "-c:v", codec])
            .args(["-b:v", "40M", "-maxrate", "48M", "-bufsize", "80M", "-pix_fmt", "yuv420p"]);
        if allow_sw { command.args(["-allow_sw", "1"]); }
        command.args(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]).arg(&partial);
        command.output().map_err(|e| e.to_string())
    };
    let mut output = run("h264_videotoolbox", true)?;
    if !output.status.success() {
        let _ = fs::remove_file(&partial);
        output = run("libx264", false)?;
    }
    if !output.status.success() {
        let _ = fs::remove_file(&partial);
        return Err(String::from_utf8_lossy(&output.stderr).lines().rev().take(8).collect::<Vec<_>>().join("\n"));
    }
    fs::rename(&partial, &destination).map_err(|e| e.to_string())?;
    Ok(destination.to_string_lossy().to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(JobState::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            list_projects, create_project, register_project, update_project, forget_project,
            load_reviews, save_review, load_compact_transcript, save_manual_editorial,
            load_editor_data, load_editor_draft, save_editor_draft, create_editorial_template,
            inspect_editorial, start_job, cancel_job,
            reveal_path, list_project_videos, trim_video
        ])
        .run(tauri::generate_context!())
        .expect("error al ejecutar abrxs-Canter");
}
