use std::{collections::HashMap, fs::File, io::{BufRead, BufReader, Read, Seek, SeekFrom, Write}, net::{TcpListener, TcpStream}, path::PathBuf, sync::{Arc, Mutex}, time::Duration};
#[derive(Default)]
pub struct MediaState(Mutex<Option<Server>>);
struct Server { port: u16, files: Arc<Mutex<HashMap<String, PathBuf>>> }

fn bounds(range: Option<&str>, size: u64) -> Result<(u64,u64), String> {
    if size == 0 { return Err("Archivo vacío".into()); }
    let Some(value) = range else { return Ok((0,size-1)) };
    let value = value.strip_prefix("bytes=").ok_or("Rango inválido")?;
    let (a,b) = value.split_once('-').ok_or("Rango inválido")?;
    let (start,end) = if a.is_empty() {
        let count = b.parse::<u64>().map_err(|_| "Rango inválido")?;
        if count == 0 { return Err("Rango vacío".into()); }
        (size.saturating_sub(count),size-1)
    } else {
        (a.parse::<u64>().map_err(|_| "Rango inválido")?, if b.is_empty() {size-1} else {b.parse::<u64>().map_err(|_| "Rango inválido")?.min(size-1)})
    };
    if start > end || start >= size { return Err("Rango fuera del archivo".into()); }
    Ok((start,end))
}
fn serve(stream: TcpStream, files: Arc<Mutex<HashMap<String,PathBuf>>>) -> std::io::Result<()> {
    stream.set_read_timeout(Some(Duration::from_secs(10)))?;
    stream.set_write_timeout(Some(Duration::from_secs(15)))?;
    let mut reader=BufReader::new(stream);
    let mut line=String::new();reader.read_line(&mut line)?;
    let parts:Vec<_>=line.split_whitespace().collect();
    let method=parts.first().copied().unwrap_or("").to_string();
    let token=parts.get(1).copied().unwrap_or("").trim_start_matches('/').to_string();
    if method!="GET" && method!="HEAD" { reader.get_mut().write_all(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")?;return Ok(()) }
    let mut range=None;let mut length=line.len();
    loop {line.clear();if reader.read_line(&mut line)?==0 || line=="\r\n" {break;}length+=line.len();if length>8192 {return Ok(())}if let Some((key,value))=line.split_once(':'){if key.eq_ignore_ascii_case("range"){range=Some(value.trim().to_string());}}}
    let path=files.lock().ok().and_then(|m|m.get(&token).cloned());
    let Some(path)=path else {reader.get_mut().write_all(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")?;return Ok(())};
    let mut file=File::open(path)?;let size=file.metadata()?.len();
    let Ok((start,end))=bounds(range.as_deref(),size) else {write!(reader.get_mut(),"HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */{size}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")?;return Ok(())};
    let status=if range.is_some(){"206 Partial Content"}else{"200 OK"};
    write!(reader.get_mut(),"HTTP/1.1 {status}\r\nContent-Type: video/mp4\r\nContent-Length: {}\r\nAccept-Ranges: bytes\r\nCache-Control: no-store\r\nConnection: close\r\n",end-start+1)?;
    if range.is_some(){write!(reader.get_mut(),"Content-Range: bytes {start}-{end}/{size}\r\n")?;}
    reader.get_mut().write_all(b"\r\n")?;
    if method=="GET" {file.seek(SeekFrom::Start(start))?;std::io::copy(&mut file.take(end-start+1),reader.get_mut())?;}
    Ok(())
}
#[tauri::command]
pub fn media_source(state: tauri::State<MediaState>, path: String) -> Result<String,String> {
    let path=std::fs::canonicalize(path).map_err(|e|format!("No se puede abrir el máster: {e}"))?;
    if !path.is_file(){return Err("Selecciona un archivo de video".into());}
    let mut guard=state.0.lock().map_err(|_|"Estado del reproductor bloqueado")?;
    if guard.is_none(){
        let listener=TcpListener::bind(("127.0.0.1",0)).map_err(|e|e.to_string())?;
        let port=listener.local_addr().map_err(|e|e.to_string())?.port();
        let files=Arc::new(Mutex::new(HashMap::new()));let shared=files.clone();
        std::thread::spawn(move||{for stream in listener.incoming().flatten(){let files=shared.clone();std::thread::spawn(move||{let _=serve(stream,files);});}});
        *guard=Some(Server{port,files});
    }
    let server=guard.as_ref().unwrap();let mut files=server.files.lock().map_err(|_|"Estado bloqueado")?;
    if let Some((token,_))=files.iter().find(|(_,p)|**p==path){return Ok(format!("http://127.0.0.1:{}/{}",server.port,token));}
    let mut random=[0u8;32];File::open("/dev/urandom").and_then(|mut f|f.read_exact(&mut random)).map_err(|e|e.to_string())?;
    let token=random.iter().map(|n|format!("{n:02x}")).collect::<String>();files.insert(token.clone(),path);
    Ok(format!("http://127.0.0.1:{}/{token}",server.port))
}
#[cfg(test)] mod tests {use super::*;#[test]fn range_limits(){assert_eq!(bounds(Some("bytes=5-10"),20).unwrap(),(5,10));assert_eq!(bounds(Some("bytes=-4"),20).unwrap(),(16,19));assert_eq!(bounds(None,10_000_000_000).unwrap(),(0,9_999_999_999));assert!(bounds(Some("bytes=20-"),20).is_err());assert!(bounds(Some("bytes=0-4,8-9"),20).is_err());}}
