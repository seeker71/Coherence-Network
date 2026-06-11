// form-kernel-rust — vertical-slice host for Form-on-top.
//
// Executes Form recipe trees and binary artifacts. The CLI still carries a
// source-to-recipe adapter for current tests; the kernel path is the
// substrate, walker, host primitives, and binary artifact loader.
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — all 22 RBasic dispatch arms
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — strings, lists, I/O, conversion
//   • Binary loader      — Form artifact bytes → recipe tree
//
// Parsers and grammars belong in Form artifacts above this layer.
//
// Usage:  form-kernel-rust <file.fk>
//         form-kernel-rust --bench
//         form-kernel-rust --expr "(add 2 3)"

use std::any::Any;
use std::backtrace::Backtrace;
use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io::{Read, Seek, SeekFrom, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::mpsc;
use std::sync::{Arc, Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

mod bp_table;
mod formats;
mod inductive;
mod quotient;

#[derive(Clone, Default)]
struct CrashTraceContext {
    mode: String,
    args: Vec<String>,
    source: String,
    source_label: String,
    operation: String,
}

#[derive(Clone)]
struct CrashDiagnosis {
    fatal_kind: &'static str,
    likely_root_cause: String,
    avoidance: String,
}

fn crash_trace_context() -> &'static Mutex<CrashTraceContext> {
    static T: OnceLock<Mutex<CrashTraceContext>> = OnceLock::new();
    T.get_or_init(|| Mutex::new(CrashTraceContext::default()))
}

thread_local! {
    static THREAD_CRASH_TRACE_CONTEXT: RefCell<Option<CrashTraceContext>> = const { RefCell::new(None) };
}

fn source_excerpt_head(src: &str, max_chars: usize) -> String {
    src.chars().take(max_chars).collect()
}

fn source_excerpt_tail(src: &str, max_chars: usize) -> String {
    let tail_rev: String = src.chars().rev().take(max_chars).collect();
    tail_rev.chars().rev().collect()
}

fn source_line_count(src: &str) -> usize {
    if src.is_empty() {
        0
    } else {
        src.matches('\n').count() + 1
    }
}

fn set_crash_trace_context(mode: &str, args: &[String], source: Option<&str>) {
    set_crash_trace_context_with_details(mode, args, source, None, None);
}

fn set_crash_trace_context_with_details(
    mode: &str,
    args: &[String],
    source: Option<&str>,
    source_label: Option<&str>,
    operation: Option<&str>,
) {
    let new_ctx = CrashTraceContext {
        mode: mode.to_string(),
        args: args.to_vec(),
        source: source.unwrap_or("").to_string(),
        source_label: source_label.unwrap_or("").to_string(),
        operation: operation.unwrap_or("").to_string(),
    };
    if let Ok(mut global_ctx) = crash_trace_context().lock() {
        *global_ctx = new_ctx.clone();
    }
    set_thread_crash_trace_context(new_ctx);
}

fn set_thread_crash_trace_context(ctx: CrashTraceContext) {
    THREAD_CRASH_TRACE_CONTEXT.with(|slot| {
        *slot.borrow_mut() = Some(ctx);
    });
}

fn current_crash_trace_context() -> CrashTraceContext {
    if let Some(ctx) = THREAD_CRASH_TRACE_CONTEXT.with(|slot| slot.borrow().clone()) {
        return ctx;
    }
    crash_trace_context()
        .lock()
        .map(|guard| guard.clone())
        .unwrap_or_default()
}

fn diagnose_kernel_panic(message: &str) -> CrashDiagnosis {
    let lower = message.to_ascii_lowercase();
    if lower.starts_with("as_str:") {
        return CrashDiagnosis {
            fatal_kind: "type_contract_violation",
            likely_root_cause: "a Form/native recipe passed a non-string value to a string-only primitive".to_string(),
            avoidance: "guard with value_kind/value-kind, convert with value_str, or use null-safe JSON constructors before calling string primitives".to_string(),
        };
    }
    if lower.starts_with("as_int:")
        || lower.starts_with("as_float:")
        || lower.starts_with("as_nid:")
    {
        return CrashDiagnosis {
            fatal_kind: "type_contract_violation",
            likely_root_cause: "a Form/native recipe passed a value with the wrong primitive kind to a typed host boundary".to_string(),
            avoidance: "validate the value kind before the native call, or route through an explicit conversion recipe".to_string(),
        };
    }
    if lower.contains("unbound identifier") || lower.contains("unbound function") {
        return CrashDiagnosis {
            fatal_kind: "name_resolution_error",
            likely_root_cause: "a recipe or route manifest referenced a name that was not bound in the loaded source/prelude set".to_string(),
            avoidance: "run the route/source check gate and include the defining prelude before serving the manifest".to_string(),
        };
    }
    if lower.contains("wants") && lower.contains("got") {
        return CrashDiagnosis {
            fatal_kind: "arity_contract_violation",
            likely_root_cause: "a closure or native was called with a different argument count than its declaration accepts".to_string(),
            avoidance: "align the call site with the function signature or add an adapter recipe at the boundary".to_string(),
        };
    }
    if lower.contains("bounds out of range") || lower.contains("index out of bounds") {
        return CrashDiagnosis {
            fatal_kind: "bounds_violation",
            likely_root_cause: "a recipe indexed outside the observed collection/string bounds".to_string(),
            avoidance: "check length/bounds before indexing or use a boundary-aware recipe that returns an explicit error value".to_string(),
        };
    }
    if lower.contains("source-compile") || lower.contains("parse error") {
        return CrashDiagnosis {
            fatal_kind: "source_compile_failure",
            likely_root_cause: "source text could not be lowered into a valid Form recipe before execution".to_string(),
            avoidance: "run the source compiler/check command and repair the reported source coordinate before serving".to_string(),
        };
    }
    CrashDiagnosis {
        fatal_kind: "kernel_panic",
        likely_root_cause: "the kernel crossed an unchecked host-language panic boundary".to_string(),
        avoidance: "inspect the trace backtrace and source excerpt, then move the failing boundary into a checked fatal/error return".to_string(),
    }
}

fn panic_payload_message(payload: &(dyn Any + Send)) -> String {
    payload
        .downcast_ref::<String>()
        .map(|s| s.to_string())
        .or_else(|| payload.downcast_ref::<&str>().map(|s| s.to_string()))
        .unwrap_or_else(|| "unknown error".to_string())
}

fn write_kernel_crash_trace(message: &str, location: Option<String>) -> Option<PathBuf> {
    let ctx = current_crash_trace_context();
    let diagnosis = diagnose_kernel_panic(message);
    let now = SystemTime::now().duration_since(UNIX_EPOCH).ok()?;
    let filename = format!(
        "crash-{}{:09}-{}.json",
        now.as_secs(),
        now.subsec_nanos(),
        std::process::id()
    );
    let report = serde_json::json!({
        "when_unix_seconds": now.as_secs(),
        "pid": std::process::id(),
        "mode": ctx.mode,
        "args": ctx.args,
        "fatal_kind": diagnosis.fatal_kind,
        "fatal_message": message,
        "panic": message,
        "likely_root_cause": diagnosis.likely_root_cause,
        "avoidance": diagnosis.avoidance,
        "location": location,
        "thread": thread::current().name().unwrap_or("unnamed"),
        "source_label": ctx.source_label,
        "operation": ctx.operation,
        "source_bytes": ctx.source.len(),
        "source_line_count": source_line_count(&ctx.source),
        "source_head": source_excerpt_head(&ctx.source, 2000),
        "source_tail": source_excerpt_tail(&ctx.source, 2000),
        "rust_backtrace": format!("{:?}", Backtrace::force_capture()),
    });
    let data = serde_json::to_vec_pretty(&report).ok()?;
    let payload = [data, b"\n".to_vec()].concat();
    let trace_dirs = [
        PathBuf::from(".cache").join("form-kernel-rust"),
        env::temp_dir().join("form-kernel-rust"),
    ];
    for dir in trace_dirs {
        if fs::create_dir_all(&dir).is_err() {
            continue;
        }
        let path = dir.join(&filename);
        if fs::write(&path, &payload).is_ok() {
            return Some(path);
        }
    }
    None
}

// --- Socket natives — L1 physical layer (TCP) ---------------------------
// Sibling parity with form-kernel-go + form-kernel-ts. Handles are
// monotone i64s; the kernel never reveals the underlying TcpListener /
// TcpStream to Form code, only the handle. -1 always means error.
enum SocketKind {
    Listener(TcpListener),
    Stream(Mutex<TcpStream>),
}

struct SocketTable {
    handles: HashMap<i64, Arc<SocketKind>>,
    next: i64,
}

fn socket_table() -> &'static Mutex<SocketTable> {
    static T: OnceLock<Mutex<SocketTable>> = OnceLock::new();
    T.get_or_init(|| {
        Mutex::new(SocketTable {
            handles: HashMap::new(),
            next: 0,
        })
    })
}

fn socket_register(s: SocketKind) -> i64 {
    let mut t = socket_table().lock().unwrap();
    t.next += 1;
    let h = t.next;
    t.handles.insert(h, Arc::new(s));
    h
}

fn socket_lookup(h: i64) -> Option<Arc<SocketKind>> {
    let t = socket_table().lock().unwrap();
    t.handles.get(&h).cloned()
}

fn socket_drop(h: i64) -> bool {
    let mut t = socket_table().lock().unwrap();
    t.handles.remove(&h).is_some()
}

// --- Postgres natives — the DB carrier of the storage port --------------
// Form-rendered SQL executed against a real Postgres. Handles are monotone
// i64s; the kernel never reveals the postgres::Client to Form, only the
// handle. -1 = error. Effectful, per-kernel reference impl — the SQL strings
// are already three-way verified by db-schema.fk + emits/sql.fk; only
// execution lives here. See docs/coherence-substrate/cell-store-architecture.md
// (the DB is the production carrier; the FS log store is dev/test).
struct PgTable {
    handles: HashMap<i64, Arc<Mutex<postgres::Client>>>,
    next: i64,
}

struct VolatileCell {
    updated_ms: i64,
    value: Value,
}

struct VolatileCellTable {
    cells: HashMap<String, VolatileCell>,
}

fn pg_table() -> &'static Mutex<PgTable> {
    static T: OnceLock<Mutex<PgTable>> = OnceLock::new();
    T.get_or_init(|| {
        Mutex::new(PgTable {
            handles: HashMap::new(),
            next: 0,
        })
    })
}

fn pg_last_error_cell() -> &'static Mutex<String> {
    static E: OnceLock<Mutex<String>> = OnceLock::new();
    E.get_or_init(|| Mutex::new(String::new()))
}

fn pg_set_error(error: Option<String>) {
    let mut slot = pg_last_error_cell().lock().unwrap();
    *slot = error.unwrap_or_default();
}

fn pg_register(c: postgres::Client) -> i64 {
    let mut t = pg_table().lock().unwrap();
    t.next += 1;
    let h = t.next;
    t.handles.insert(h, Arc::new(Mutex::new(c)));
    h
}

fn pg_lookup(h: i64) -> Option<Arc<Mutex<postgres::Client>>> {
    let t = pg_table().lock().unwrap();
    t.handles.get(&h).cloned()
}

fn pg_drop(h: i64) -> bool {
    let mut t = pg_table().lock().unwrap();
    t.handles.remove(&h).is_some()
}

fn volatile_table() -> &'static Mutex<VolatileCellTable> {
    static T: OnceLock<Mutex<VolatileCellTable>> = OnceLock::new();
    T.get_or_init(|| {
        Mutex::new(VolatileCellTable {
            cells: HashMap::new(),
        })
    })
}

fn volatile_coord(namespace: &str, key: &str) -> String {
    format!("{namespace}\0{key}")
}

fn now_unix_ms_value() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn kernel_started_unix_ms_value() -> i64 {
    static STARTED: OnceLock<i64> = OnceLock::new();
    *STARTED.get_or_init(now_unix_ms_value)
}

fn civil_from_days(days_since_epoch: i64) -> (i64, i64, i64) {
    let z = days_since_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 }.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096).div_euclid(365);
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2).div_euclid(153);
    let d = doy - (153 * mp + 2).div_euclid(5) + 1;
    let m = mp + if mp < 10 { 3 } else { -9 };
    let year = y + if m <= 2 { 1 } else { 0 };
    (year, m, d)
}

fn unix_ms_to_iso_utc(ms: i64) -> String {
    let secs = ms.div_euclid(1000);
    let days = secs.div_euclid(86_400);
    let seconds_of_day = secs.rem_euclid(86_400);
    let (year, month, day) = civil_from_days(days);
    let hour = seconds_of_day / 3600;
    let minute = (seconds_of_day % 3600) / 60;
    let second = seconds_of_day % 60;
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z")
}

fn uptime_human(seconds: i64) -> String {
    let seconds = seconds.max(0);
    let days = seconds / 86_400;
    let mut remainder = seconds % 86_400;
    let hours = remainder / 3600;
    remainder %= 3600;
    let minutes = remainder / 60;
    let secs = remainder % 60;
    if days > 0 {
        format!("{days}d {hours}h {minutes}m {secs}s")
    } else if hours > 0 {
        format!("{hours}h {minutes}m {secs}s")
    } else if minutes > 0 {
        format!("{minutes}m {secs}s")
    } else {
        format!("{secs}s")
    }
}

fn rust_kernel_config_path_cell() -> &'static Mutex<Option<String>> {
    static P: OnceLock<Mutex<Option<String>>> = OnceLock::new();
    P.get_or_init(|| Mutex::new(None))
}

fn set_rust_kernel_config_path(path: String) {
    let mut slot = rust_kernel_config_path_cell().lock().unwrap();
    *slot = Some(path);
}

fn rust_kernel_config_path() -> Option<String> {
    rust_kernel_config_path_cell().lock().unwrap().clone()
}

fn find_repo_root() -> Result<PathBuf, String> {
    let mut wd = env::current_dir().map_err(|e| e.to_string())?;
    loop {
        if wd.join("api/config/api.json").exists() {
            return Ok(wd);
        }
        if !wd.pop() {
            break;
        }
    }
    Err("could not find repo root containing api/config/api.json".to_string())
}

fn merge_json_object(
    dst: &mut serde_json::Map<String, serde_json::Value>,
    src: serde_json::Map<String, serde_json::Value>,
) {
    for (key, value) in src {
        match (dst.get_mut(&key), value) {
            (Some(serde_json::Value::Object(dst_child)), serde_json::Value::Object(src_child)) => {
                merge_json_object(dst_child, src_child);
            }
            (_, value) => {
                dst.insert(key, value);
            }
        }
    }
}

fn merge_config_file(
    dst: &mut serde_json::Map<String, serde_json::Value>,
    path: &Path,
) -> Result<(), String> {
    let body = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let parsed: serde_json::Value = serde_json::from_str(&body).map_err(|e| e.to_string())?;
    match parsed {
        serde_json::Value::Object(obj) => {
            merge_json_object(dst, obj);
            Ok(())
        }
        _ => Err(format!("{} must contain a JSON object", path.display())),
    }
}

fn home_config_path(file: &str) -> Option<PathBuf> {
    env::var_os("HOME").map(|home| PathBuf::from(home).join(".coherence-network").join(file))
}

fn github_token_from_keys(keys: &serde_json::Map<String, serde_json::Value>) -> Option<String> {
    if let Some(serde_json::Value::Object(github)) = keys.get("github") {
        for key in ["token", "api_token"] {
            if let Some(serde_json::Value::String(value)) = github.get(key) {
                let trimmed = value.trim();
                if !trimmed.is_empty() {
                    return Some(trimmed.to_string());
                }
            }
        }
    }
    if let Some(serde_json::Value::String(value)) = keys.get("github_token") {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Some(trimmed.to_string());
        }
    }
    None
}

fn merge_kernel_keys(dst: &mut serde_json::Map<String, serde_json::Value>, path: &Path) {
    let body = match fs::read_to_string(path) {
        Ok(body) => body,
        Err(_) => return,
    };
    let parsed: serde_json::Value = match serde_json::from_str(&body) {
        Ok(parsed) => parsed,
        Err(_) => return,
    };
    let serde_json::Value::Object(keys) = parsed else {
        return;
    };
    if let Some(token) = github_token_from_keys(&keys) {
        let missing = dst
            .get("github_token")
            .and_then(|v| v.as_str())
            .map(|s| s.trim().is_empty())
            .unwrap_or(true);
        if missing {
            dst.insert("github_token".to_string(), serde_json::Value::String(token));
        }
    }
    dst.insert("keys".to_string(), serde_json::Value::Object(keys));
}

fn load_kernel_config() -> Result<serde_json::Map<String, serde_json::Value>, String> {
    let root = find_repo_root()?;
    let mut merged = serde_json::Map::new();
    merge_config_file(&mut merged, &root.join("api/config/api.json"))?;
    if let Some(overlay) = rust_kernel_config_path() {
        let _ = merge_config_file(&mut merged, Path::new(&overlay));
    } else if let Some(overlay) = home_config_path("config.json") {
        let _ = merge_config_file(&mut merged, &overlay);
    }
    if let Some(keys) = home_config_path("keys.json") {
        merge_kernel_keys(&mut merged, &keys);
    }
    Ok(merged)
}

fn lookup_config_path<'a>(
    config: &'a serde_json::Map<String, serde_json::Value>,
    path: &str,
) -> Option<&'a serde_json::Value> {
    let mut current: Option<&serde_json::Value> = None;
    for (idx, part) in path.split('.').enumerate() {
        if part.is_empty() {
            return None;
        }
        let obj = if idx == 0 {
            config
        } else {
            current?.as_object()?
        };
        current = obj.get(part);
    }
    current
}

fn json_to_form_value(value: &serde_json::Value, default: &Value) -> Value {
    match value {
        serde_json::Value::String(s) => Value::Str(s.clone().into()),
        serde_json::Value::Bool(b) => Value::Bool(*b),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Value::Int(i)
            } else if let Some(f) = n.as_f64() {
                Value::Float(f)
            } else {
                default.clone()
            }
        }
        serde_json::Value::Null => default.clone(),
        other => Value::Str(other.to_string().into()),
    }
}

fn value_kind_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "null",
        Value::Int(_) => "int",
        Value::Float(_) => "float",
        Value::Str(_) => "string",
        Value::Bool(_) => "bool",
        Value::List(_) => "list",
        Value::Closure(_) => "closure",
        Value::Nid(_) => "node_id",
        Value::Record(_) => "record",
    }
}

fn load_config_value_or(path: &str, default: &Value) -> Value {
    let config = match load_kernel_config() {
        Ok(config) => config,
        Err(e) => {
            pg_set_error(Some(e));
            return default.clone();
        }
    };
    match lookup_config_path(&config, path) {
        Some(value) => json_to_form_value(value, default),
        None => default.clone(),
    }
}

fn load_configured_database_url() -> Result<String, String> {
    let config = load_kernel_config()?;
    if let Some(serde_json::Value::Object(db)) = config.get("database") {
        if let Some(serde_json::Value::String(url)) = db.get("url") {
            let trimmed = url.trim();
            if !trimmed.is_empty() {
                return Ok(trimmed.to_string());
            }
        }
    }
    if let Some(serde_json::Value::String(url)) = config.get("database_url") {
        let trimmed = url.trim();
        if !trimmed.is_empty() {
            return Ok(trimmed.to_string());
        }
    }
    Err("database.url is not configured".to_string())
}

fn source_inventory_skip_set(value: &Value) -> HashSet<String> {
    match value {
        Value::List(items) => items
            .iter()
            .filter_map(|item| match item {
                Value::Str(s) if !s.is_empty() => Some(s.to_string()),
                _ => None,
            })
            .collect(),
        _ => HashSet::new(),
    }
}

fn count_text_lines(path: &std::path::Path) -> i64 {
    match fs::read(path) {
        Ok(body) => {
            if body.is_empty() {
                0
            } else {
                let newlines = body.iter().filter(|b| **b == b'\n').count() as i64;
                if body.last() == Some(&b'\n') {
                    newlines
                } else {
                    newlines + 1
                }
            }
        }
        Err(_) => -1,
    }
}

fn source_inventory_row(rel: String, loc: i64) -> Value {
    Value::List(vec![Value::Str(rel.into()), Value::Int(loc)].into())
}

fn source_inventory_walk(
    root_abs: &std::path::Path,
    dir: &std::path::Path,
    suffix: &str,
    skip: &HashSet<String>,
    rows: &mut Vec<Value>,
) -> Result<(), std::io::Error> {
    let mut entries = fs::read_dir(dir)?.collect::<Result<Vec<_>, _>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            if skip.contains(&name) {
                continue;
            }
            source_inventory_walk(root_abs, &path, suffix, skip, rows)?;
        } else if file_type.is_file() {
            if !suffix.is_empty() && !name.ends_with(suffix) {
                continue;
            }
            let rel = path
                .strip_prefix(root_abs)
                .unwrap_or(path.as_path())
                .to_string_lossy()
                .replace('\\', "/");
            rows.push(source_inventory_row(rel, count_text_lines(&path)));
        }
    }
    Ok(())
}

// Render one column of a postgres row to a string, by its SQL type. Covers the
// substrate's portable column set (text/varchar, the integer family, bool).
// NULL → "". Unknown types → "?". try_get keeps a type mismatch from panicking.
fn pg_cell_to_string(row: &postgres::Row, ci: usize) -> String {
    let ty = row.columns()[ci].type_().name().to_string();
    match ty.as_str() {
        "text" | "varchar" | "bpchar" | "name" | "json" | "jsonb" => row
            .try_get::<usize, Option<String>>(ci)
            .ok()
            .flatten()
            .unwrap_or_default(),
        "int8" => row
            .try_get::<usize, Option<i64>>(ci)
            .ok()
            .flatten()
            .map(|v| v.to_string())
            .unwrap_or_default(),
        "int4" => row
            .try_get::<usize, Option<i32>>(ci)
            .ok()
            .flatten()
            .map(|v| v.to_string())
            .unwrap_or_default(),
        "int2" => row
            .try_get::<usize, Option<i16>>(ci)
            .ok()
            .flatten()
            .map(|v| v.to_string())
            .unwrap_or_default(),
        "bool" => row
            .try_get::<usize, Option<bool>>(ci)
            .ok()
            .flatten()
            .map(|v| if v { "t".to_string() } else { "f".to_string() })
            .unwrap_or_default(),
        _ => "?".to_string(),
    }
}

fn pg_cell_to_value(row: &postgres::Row, ci: usize) -> Value {
    let ty = row.columns()[ci].type_().name().to_string();
    match ty.as_str() {
        "text" | "varchar" | "bpchar" | "name" | "json" | "jsonb" => Value::Str(
            row.try_get::<usize, Option<String>>(ci)
                .ok()
                .flatten()
                .unwrap_or_default()
                .into(),
        ),
        "int8" => row
            .try_get::<usize, Option<i64>>(ci)
            .ok()
            .flatten()
            .map(Value::Int)
            .unwrap_or(Value::Null),
        "int4" => row
            .try_get::<usize, Option<i32>>(ci)
            .ok()
            .flatten()
            .map(|v| Value::Int(v as i64))
            .unwrap_or(Value::Null),
        "int2" => row
            .try_get::<usize, Option<i16>>(ci)
            .ok()
            .flatten()
            .map(|v| Value::Int(v as i64))
            .unwrap_or(Value::Null),
        "float8" => row
            .try_get::<usize, Option<f64>>(ci)
            .ok()
            .flatten()
            .map(Value::Float)
            .unwrap_or(Value::Null),
        "float4" => row
            .try_get::<usize, Option<f32>>(ci)
            .ok()
            .flatten()
            .map(|v| Value::Float(v as f64))
            .unwrap_or(Value::Null),
        "bool" => row
            .try_get::<usize, Option<bool>>(ci)
            .ok()
            .flatten()
            .map(Value::Bool)
            .unwrap_or(Value::Null),
        _ => Value::Str(pg_cell_to_string(row, ci).into()),
    }
}

fn form_sql_args(value: Option<&Value>) -> Vec<Box<dyn postgres::types::ToSql + Sync>> {
    let Some(Value::List(items)) = value else {
        return Vec::new();
    };
    let mut out: Vec<Box<dyn postgres::types::ToSql + Sync>> = Vec::with_capacity(items.len());
    for item in items.iter() {
        match item {
            Value::Int(n) => out.push(Box::new(*n)),
            Value::Float(f) => out.push(Box::new(*f)),
            Value::Bool(b) => out.push(Box::new(*b)),
            Value::Str(s) => out.push(Box::new(s.to_string())),
            Value::Null => out.push(Box::new(Option::<String>::None)),
            _ => out.push(Box::new(item.display())),
        }
    }
    out
}

fn dict_value(pairs: Vec<(&str, Value)>) -> Value {
    let mut out = Vec::with_capacity(pairs.len() * 2 + 1);
    out.push(Value::Str("__dict__".to_string().into()));
    for (key, value) in pairs {
        out.push(Value::Str(key.to_string().into()));
        out.push(value);
    }
    Value::List(out.into())
}

fn form_http_headers(value: Option<&Value>) -> Vec<(String, String)> {
    let Some(Value::List(rows)) = value else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for row in rows.iter() {
        let Value::List(items) = row else {
            continue;
        };
        if items.len() != 3 {
            continue;
        }
        if !matches!(items.get(0), Some(Value::Int(tag)) if *tag == KH_TAG_HEADER) {
            continue;
        }
        let (Value::Str(name), Value::Str(value)) = (&items[1], &items[2]) else {
            continue;
        };
        let name = name.trim();
        if !name.is_empty() {
            out.push((name.to_string(), value.to_string()));
        }
    }
    out
}

fn form_http_timeout(value: Option<&Value>, fallback: Duration) -> Duration {
    let Some(value) = value else {
        return fallback;
    };
    let ms = match value {
        Value::Int(n) => *n,
        Value::Float(f) => *f as i64,
        _ => return fallback,
    };
    if ms <= 0 {
        return fallback;
    }
    Duration::from_millis(ms.min(60_000) as u64)
}

fn http_header_list(response: &ureq::Response) -> Value {
    let mut rows = Vec::new();
    let mut names = response.headers_names();
    names.sort();
    for name in names {
        if let Some(value) = response.header(&name) {
            rows.push(Value::List(
                vec![
                    Value::Int(KH_TAG_HEADER),
                    Value::Str(name.into()),
                    Value::Str(value.to_string().into()),
                ]
                .into(),
            ));
        }
    }
    Value::List(rows.into())
}

fn http_get_result(
    status_code: i64,
    headers: Value,
    body: String,
    error: String,
    duration_ms: i64,
) -> Value {
    dict_value(vec![
        ("status_code", Value::Int(status_code)),
        ("body", Value::Str(body.into())),
        ("error", Value::Str(error.into())),
        ("duration_ms", Value::Int(duration_ms)),
        ("headers", headers),
    ])
}

fn external_http_get_value(url: &str, headers: Vec<(String, String)>, timeout: Duration) -> Value {
    let started = Instant::now();
    let mut request = ureq::get(url).timeout(timeout);
    for (name, value) in headers {
        request = request.set(&name, &value);
    }
    match request.call() {
        Ok(response) => {
            let status_code = response.status() as i64;
            let header_rows = http_header_list(&response);
            match response.into_string() {
                Ok(body) => http_get_result(
                    status_code,
                    header_rows,
                    body,
                    String::new(),
                    started.elapsed().as_millis() as i64,
                ),
                Err(e) => http_get_result(
                    status_code,
                    header_rows,
                    String::new(),
                    e.to_string(),
                    started.elapsed().as_millis() as i64,
                ),
            }
        }
        Err(e) => http_get_result(
            0,
            Value::List(Vec::new().into()),
            String::new(),
            e.to_string(),
            started.elapsed().as_millis() as i64,
        ),
    }
}

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

// Registered substrate ids use pkg=1. Runtime-interned composites use pkg=0
// so temporary recipe ids cannot collide with registered/basic categories
// across an execution context boundary.
#[derive(Copy, Clone, PartialEq, Eq, Hash, Debug)]
pub(crate) struct NodeID {
    pub(crate) pkg: u32,
    pub(crate) level: u32,
    pub(crate) ty: u32,
    pub(crate) inst: u32,
}

pub(crate) const LEVEL_TRIVIAL: u32 = 1;
pub(crate) const LEVEL_BASIC: u32 = 2;

// RBasic — aligned with api/app/services/substrate/category.py
const RB_UNDEFINED: u32 = 0;
const RB_WITNESS: u32 = 6; // substrate self-attestation
const RB_BLOCK: u32 = 9;
const RB_CALL: u32 = 10; // invoke external effect (I/O, tool)
const RB_COND: u32 = 11;
const RB_MATH: u32 = 12;
const RB_COMPARE: u32 = 13;
const RB_LOGIC: u32 = 14;
const RB_ACCESS: u32 = 15; // read a property / field
const RB_MATCH: u32 = 19; // match/switch by substrate key
const RB_METHOD: u32 = 27; // method on a cell-like value
const RB_TRANSMUTE: u32 = 76; // present value through Blueprint without changing identity
                              // Kernel-demo additions
const RB_FNDEF: u32 = 31;
const RB_FNCALL: u32 = 32;
const RB_IDENT: u32 = 33;
const RB_LIST: u32 = 34;
const RB_FIELD: u32 = 88;
const RB_CARRIER: u32 = 89;
const RB_TOPOLOGY: u32 = 90;
const RB_FIBER: u32 = 91;
const RB_REGION: u32 = 92;
const RB_BOUNDARY: u32 = 93;
const RB_NEIGHBORHOOD: u32 = 94;
const RB_MATCH_FIELD: u32 = 95;
const RB_DELTA: u32 = 96;
const RB_RESOLVE: u32 = 97;
const RB_COMMIT: u32 = 98;
const RB_STEP: u32 = 99;
const RB_LIFT: u32 = 100;
const RB_SAMPLE: u32 = 101;
const RB_OBSERVE: u32 = 102;
const RB_INTERVENE: u32 = 103;
const RB_RESIDUAL: u32 = 104;
const RB_RECEIPT: u32 = 105;
const RB_COST: u32 = 106;
const RB_CONSENT: u32 = 107;
const RB_EVIDENCE: u32 = 108;
#[allow(dead_code)]
const RB_FIELD_PRIMITIVES: [u32; 21] = [
    RB_FIELD,
    RB_CARRIER,
    RB_TOPOLOGY,
    RB_FIBER,
    RB_REGION,
    RB_BOUNDARY,
    RB_NEIGHBORHOOD,
    RB_MATCH_FIELD,
    RB_DELTA,
    RB_RESOLVE,
    RB_COMMIT,
    RB_STEP,
    RB_LIFT,
    RB_SAMPLE,
    RB_OBSERVE,
    RB_INTERVENE,
    RB_RESIDUAL,
    RB_RECEIPT,
    RB_COST,
    RB_CONSENT,
    RB_EVIDENCE,
];

pub(crate) const TRIV_INT: u32 = 1;
pub(crate) const TRIV_STRING: u32 = 2;
const TRIV_BOOL: u32 = 3;
const TRIV_NULL: u32 = 4;
// FLOAT32 — IEEE 754 32-bit value stored inline; the inst field carries the
// IEEE bit pattern reinterpreted as u32. No overflow table needed (32 bits fit
// the 32-bit inst slot). This kernel parses float literals only as float64, so
// nothing here CREATES a float32; the type + intern + decode exist so a float32
// leaf written by a sibling kernel reads back the same value. Aligned three-way:
// FLOAT32 = 6 across Rust/Go/TS.
pub(crate) const TRIV_FLOAT32: u32 = 6;
// FLOAT64 — value lives in the kernel's `f64s` overflow table (64 bits exceed
// the 32-bit inst slot); the inst field carries the table index. Aligned
// three-way: FLOAT64 = 7 across Rust/Go/TS. The .fkb wire format never puts
// this tag on the wire — a float64 node serializes via the dedicated
// FORM_BINARY_FLOAT64 record carrying the 8-byte value, so cross-kernel
// portability rides on the value, not the type constant.
pub(crate) const TRIV_FLOAT64: u32 = 7;

// Per-RBasic instance constants
const RMATH_PLUS: u32 = 1;
const RMATH_MINUS: u32 = 2;
const RMATH_MULTIPLY: u32 = 3;
const RMATH_DIVIDE: u32 = 4;
const RMATH_MODULO: u32 = 5;

const RCMP_EQ: u32 = 1;
const RCMP_NE: u32 = 2;
const RCMP_LT: u32 = 3;
const RCMP_LE: u32 = 4;
const RCMP_GT: u32 = 5;
const RCMP_GE: u32 = 6;

const RLOG_AND: u32 = 1;
const RLOG_OR: u32 = 2;
const RLOG_NOT: u32 = 3;

const RCOND_IF: u32 = 1;
const RCOND_IF_ELSE: u32 = 2;

const RBLK_DO: u32 = 1;
const RBLK_SEQ: u32 = 2;
const RBLK_LET: u32 = 3;
const RMATCH_SWITCH: u32 = 1;

// The eval thread's stack. TCO (see walk) removes ITERATION depth (tail-recursive
// Form loops run flat); this stack covers genuine DATA-nesting depth — a recursive-
// descent parse of a deeply nested source is inherently recursion proportional to
// nesting. Env-tunable via FORM_KERNEL_STACK_MB for sizing to a workload without a
// rebuild. (Go/V8 grow their stacks; this is the explicit equivalent.)
fn form_kernel_stack_bytes() -> usize {
    match std::env::var("FORM_KERNEL_STACK_MB") {
        Ok(s) => s.trim().parse::<usize>().unwrap_or(256) * 1024 * 1024,
        Err(_) => 256 * 1024 * 1024,
    }
}

#[derive(Clone, Debug)]
struct Recipe {
    category: NodeID,
    children: Vec<NodeID>,
}

#[derive(Clone, PartialEq, Eq, Hash)]
struct ShapeKey {
    category: NodeID,
    children: Vec<NodeID>,
}

// NativeFn now takes &mut Kernel + &mut Arena so substrate-write natives
// (intern_node, intern_trivial_*) can grow the substrate, and walk_recipe
// can re-enter the walker. Pure natives ignore the mutable handles. The
// cost: walker's children() must return owned Vec (the Breath 1 slice
// optimization is undone). Future breath: restore via Cow or split tables.
type NativeFn = fn(&mut Kernel, &mut Arena, &[Value]) -> Value;

// EnvAwareNativeFn — natives that need the caller's env (walk_recipe_here).
// Separate registry path to avoid changing the NativeFn signature across
// every existing native.
type EnvAwareNativeFn = fn(&mut Kernel, &mut Arena, FrameId, &[Value]) -> Value;

#[derive(Copy, Clone)]
struct EnvAwareNativeEntry {
    name: NameID,
    category: NodeID,
    func: EnvAwareNativeFn,
}

// NativeEntry — a native's function plus the Form category it expresses.
// Carries Blueprint attribution into the kernel: when the walker dispatches
// through a native, the trace records the category alongside the FNCALL
// arm, so reasoning about which Form-shapes did the work reaches inside
// the host-language layer. UNDEFINED is the honest marker for natives
// whose Form attribution hasn't been settled yet.
#[derive(Copy, Clone)]
struct NativeEntry {
    name: NameID,
    category: NodeID,
    func: NativeFn,
}

// NameID — interned identifier handle. The same u32 used to encode a name
// trivial's NodeID instance is what every runtime name-lookup compares.
// String comparison happens once, at parse time, never in the hot path.
type NameID = u32;

// FrameId — index into kernel.frames. Closures carry these instead of
// Rc<RefCell<Frame>>; lookup walks the chain by integer indirection. The
// arena grows monotonically per session — no freeing, no cycles, no
// reference-count traffic in the hot path.
type FrameId = u32;

// Kernel — the immutable-during-walk substrate: intern table, string
// table, native dispatch. Mutates only at parse/intern time. Held as
// `&Kernel` by the walker so children() can return borrowed slices.
pub(crate) struct Kernel {
    by_shape: HashMap<ShapeKey, NodeID>,
    by_id: HashMap<NodeID, Recipe>,
    // Source attribution side-map: NodeID → (file_name_id, line, col).
    // Populated by `intern_node_at` for Recipes emitted from parser actions
    // that carry source-location context. `node_source` reads back.
    // The satsang-load-bearing surface: every cell's state is traceable
    // back to the source line of the recipe that authored it.
    source_attr: HashMap<NodeID, (NameID, u32, u32)>,
    // walk_cache — JIT-vector memoization: pure recipes (no I/O, no
    // external state) can have their walk result cached by NodeID.
    // Content-addressing means same recipe shape → same NodeID, so
    // cache lookups are O(1) by structure. Real JIT compiles to
    // native code; memoization skips redundant interpretation.
    // For now: opt-in via `walk-cached` native; not used by default
    // `walk_recipe` to avoid invalidating semantics for impure recipes.
    walk_cache: HashMap<NodeID, Value>,
    walk_cache_hits: u64,
    walk_cache_misses: u64,
    import_seq: u32,
    strs: Vec<String>,
    str_idx: HashMap<String, NameID>,
    // Float64 overflow table — values don't fit the 32-bit `inst` field,
    // so the trivial NodeID carries an index into `f64s`. Canonicalization
    // on intern: NaN bit patterns collapse to qNaN, ±0.0 share +0.0, but
    // ±Inf stay distinct (matches the TS kernel's f64Idx behavior).
    f64s: Vec<f64>,
    f64_idx: HashMap<u64, u32>, // keyed by IEEE bit pattern after canonicalization
    next_inst: u32,
    natives: HashMap<NameID, NativeEntry>,
    env_natives: HashMap<NameID, EnvAwareNativeEntry>,
    // methods — the blueprint method table (BML/NUMS reference: methods live
    // on the blueprint/type, shared by all instances, name-dispatched). Keyed
    // by (blueprint NodeID, method-name NameID) → the method's Closure. A
    // record's blueprint tag selects its method set; method_invoke binds
    // `self` to the receiver record.
    methods: HashMap<(NodeID, NameID), Arc<Closure>>,
    // jit_aliases: Form-function-name → native-name redirect.
    // When a function call's name is in this map, the walker substitutes
    // the aliased name before native lookup. Lets a Form recipe DEFINE
    // an algorithm as canonical truth; a `register_jit` call makes its
    // calls dispatch to a kernel-resident optimized native. Removing the
    // entry falls back to walking the Form recipe.
    jit_aliases: HashMap<NameID, NameID>,
    // jit_compiled — closure-body-NodeID → loaded host-native plugin.
    // When (jit_compile "name") succeeds, the kernel generates Rust source
    // for the closure's body, builds a cdylib via `rustc`, loads it with
    // libloading, and stores the resulting plugin keyed by the closure's
    // body NodeID. Every FNCALL whose closure body matches dispatches
    // through the loaded function pointer instead of walking the recipe.
    // Sibling to the TS kernel's k.jitCompiled map.
    // Arc lets the kernel be cloned cheaply for parallel workers; the
    // Library handle inside is shared, not duplicated.
    jit_compiled: HashMap<NodeID, Arc<JitCompiled>>,
    // Measured repetition — the kernel SENSES its own hot recipes instead of
    // waiting for a manual jit_compile. jit_hits counts calls to UNDECIDED
    // closures (neither compiled nor proven un-compilable); at JIT_HOT_THRESHOLD
    // the kernel attempts the same compile jit_compile does. jit_failed marks a
    // shape outside the JIT subset (strings/lists) so a hot recipe the compiler
    // can't take is tried ONCE, never on every call. A decided recipe carries no
    // counter — the only cost is the warm-up.
    jit_hits: HashMap<NodeID, u32>,
    jit_failed: HashSet<NodeID>,
    // Content-addressed maps — the kernel's O(1) dispatch tables, keyed by the
    // NodeID (content-address) of the key. A switch (status→phrase, name→handler,
    // shape→route) becomes a direct NodeID lookup instead of a scan: two
    // structurally-identical keys land in the same slot because they share a
    // NodeID. Each (key→value) entry is a recorded edge — the dispatch table is a
    // content-addressed graph, so the lookup that routes IS the trace that
    // attests. Per-kernel (a worker builds its own at load).
    maps: HashMap<i64, HashMap<NodeID, Value>>,
    next_map: i64,
    // SWITCH recipe cache — source-level BML/Form `match` lowers to
    // RBasic.MATCH/RMatch.SWITCH. Literal arms become direct NodeID→body edges,
    // keyed by the substrate identity of the scrutinee value. The cache key is
    // the match recipe's own content-addressed NodeID, so repeated evaluation
    // pays the table build once and then dispatches by O(1) lookup.
    switch_tables: HashMap<NodeID, SwitchTable>,
    active_roots: Vec<NodeID>,
    // Optional tracing — None for hot-path runs, Some for `trace` subcommand.
    // Hooked at the top of walk() to record per-arm dispatch counts and
    // choice success/failure rates. Per lc-native-kernel-binary's
    // "tracing and observation pattern" — the body's own attestation of
    // which arms are doing the work at any moment.
    pub(crate) trace: Option<Trace>,
}

// Trace — per-(arm, inst) dispatch counters + choice success/failure tracking.
// Held inside Kernel so the walker can record without threading an extra
// reference through every recursive call. Storing (ty, inst) instead of
// just ty surfaces typed-numeric distribution — MATH.PLUS_F64 (inst=0x91)
// becomes distinguishable from MATH.PLUS_I32 (inst=0x01) in the report.
#[derive(Default)]
pub(crate) struct Trace {
    pub(crate) total_walks: u64,
    pub(crate) arm_counts: HashMap<(u32, u32), u64>, // (cat.ty, cat.inst) → count
    pub(crate) fn_counts: HashMap<String, u64>,
    pub(crate) native_counts: HashMap<String, u64>,
    pub(crate) choice_attempts: u64,
    pub(crate) choice_successes: u64,
    pub(crate) choice_failures: u64,
    pub(crate) match_lookups: u64,
    pub(crate) match_hits: u64,
    pub(crate) match_defaults: u64,
    pub(crate) match_misses: u64,
}

impl Trace {
    pub(crate) fn new() -> Self {
        Self::default()
    }

    pub(crate) fn record(&mut self, arm_ty: u32, arm_inst: u32) {
        self.total_walks += 1;
        *self.arm_counts.entry((arm_ty, arm_inst)).or_insert(0) += 1;
    }

    pub(crate) fn record_fn(&mut self, name: &str) {
        *self.fn_counts.entry(name.to_string()).or_insert(0) += 1;
    }

    pub(crate) fn record_native(&mut self, name: &str) {
        *self.native_counts.entry(name.to_string()).or_insert(0) += 1;
    }

    pub(crate) fn record_choice_attempt(&mut self) {
        self.choice_attempts += 1;
    }
    pub(crate) fn record_choice_success(&mut self) {
        self.choice_successes += 1;
    }
    pub(crate) fn record_choice_failure(&mut self) {
        self.choice_failures += 1;
    }
    pub(crate) fn record_match_lookup(&mut self) {
        self.match_lookups += 1;
    }
    pub(crate) fn record_match_hit(&mut self) {
        self.match_hits += 1;
    }
    pub(crate) fn record_match_default(&mut self) {
        self.match_defaults += 1;
    }
    pub(crate) fn record_match_miss(&mut self) {
        self.match_misses += 1;
    }

    pub(crate) fn record_route_choice(&mut self, choice: &RouteChoice<'_>) {
        for decision in &choice.decisions {
            self.record_choice_attempt();
            if decision.selected {
                self.record_choice_success();
            } else {
                self.record_choice_failure();
            }
        }
    }

    pub(crate) fn arm_name(arm_ty: u32) -> &'static str {
        match arm_ty {
            RB_BLOCK => "BLOCK",
            RB_COND => "COND",
            RB_MATH => "MATH",
            RB_COMPARE => "COMPARE",
            RB_LOGIC => "LOGIC",
            RB_MATCH => "MATCH",
            RB_IDENT => "IDENT",
            RB_FNDEF => "FNDEF",
            RB_FNCALL => "FNCALL",
            RB_LIST => "LIST",
            // Native-Blueprint attribution categories — recorded
            // alongside FNCALL when a native fires.
            RB_WITNESS => "WITNESS",
            RB_CALL => "CALL",
            RB_ACCESS => "ACCESS",
            RB_METHOD => "METHOD",
            RB_TRANSMUTE => "TRANSMUTE",
            RB_FIELD => "FIELD",
            RB_CARRIER => "CARRIER",
            RB_TOPOLOGY => "TOPOLOGY",
            RB_FIBER => "FIBER",
            RB_REGION => "REGION",
            RB_BOUNDARY => "BOUNDARY",
            RB_NEIGHBORHOOD => "NEIGHBORHOOD",
            RB_MATCH_FIELD => "MATCH_FIELD",
            RB_DELTA => "DELTA",
            RB_RESOLVE => "RESOLVE",
            RB_COMMIT => "COMMIT",
            RB_STEP => "STEP",
            RB_LIFT => "LIFT",
            RB_SAMPLE => "SAMPLE",
            RB_OBSERVE => "OBSERVE",
            RB_INTERVENE => "INTERVENE",
            RB_RESIDUAL => "RESIDUAL",
            RB_RECEIPT => "RECEIPT",
            RB_COST => "COST",
            RB_CONSENT => "CONSENT",
            RB_EVIDENCE => "EVIDENCE",
            _ => "OTHER",
        }
    }

    /// Variant name — readable label for an (arm_ty, arm_inst) pair.
    /// Returns "MATH.PLUS", "COMPARE.LE", "BLOCK.LET", etc. For arms
    /// without a known inst encoding, returns just the bare arm name.
    /// Symmetric with TS / Go variant naming so trace JSONs read the
    /// same way across kernels.
    pub(crate) fn arm_variant_name(arm_ty: u32, arm_inst: u32) -> String {
        let base = Self::arm_name(arm_ty);
        let variant = match arm_ty {
            RB_MATH => match arm_inst {
                RMATH_PLUS => "PLUS",
                RMATH_MINUS => "MINUS",
                RMATH_MULTIPLY => "MUL",
                RMATH_DIVIDE => "DIV",
                RMATH_MODULO => "MOD",
                _ => "",
            },
            RB_COMPARE => match arm_inst {
                RCMP_EQ => "EQ",
                RCMP_NE => "NE",
                RCMP_LT => "LT",
                RCMP_LE => "LE",
                RCMP_GT => "GT",
                RCMP_GE => "GE",
                _ => "",
            },
            RB_LOGIC => match arm_inst {
                RLOG_AND => "AND",
                RLOG_OR => "OR",
                RLOG_NOT => "NOT",
                _ => "",
            },
            RB_COND => match arm_inst {
                RCOND_IF => "IF",
                RCOND_IF_ELSE => "IF_ELSE",
                _ => "",
            },
            RB_BLOCK => match arm_inst {
                RBLK_DO => "DO",
                RBLK_SEQ => "SEQ",
                RBLK_LET => "LET",
                _ => "",
            },
            RB_MATCH => match arm_inst {
                RMATCH_SWITCH => "SWITCH",
                _ => "",
            },
            _ => "",
        };
        if variant.is_empty() {
            base.to_string()
        } else {
            format!("{}.{}", base, variant)
        }
    }

    pub(crate) fn to_json(&self) -> serde_json::Value {
        // Per-(ty, inst) records — preserves typed-numeric distribution.
        let mut variants: Vec<serde_json::Value> = self
            .arm_counts
            .iter()
            .map(|((ty, inst), count)| {
                serde_json::json!({
                    "arm_ty":           ty,
                    "arm_inst":         inst,
                    "arm_name":         Self::arm_name(*ty),
                    "arm_variant_name": Self::arm_variant_name(*ty, *inst),
                    "count":            count,
                })
            })
            .collect();
        variants.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        // Per-ty aggregate — kept for backward compatibility with consumers
        // that want the coarser shape (the previous trace JSON form).
        let mut by_ty: HashMap<u32, u64> = HashMap::new();
        for ((ty, _), count) in &self.arm_counts {
            *by_ty.entry(*ty).or_insert(0) += count;
        }
        let mut arms: Vec<serde_json::Value> = by_ty
            .into_iter()
            .map(|(ty, count)| {
                serde_json::json!({
                    "arm_ty":   ty,
                    "arm_name": Self::arm_name(ty),
                    "count":    count,
                })
            })
            .collect();
        arms.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        let mut functions: Vec<serde_json::Value> = self
            .fn_counts
            .iter()
            .map(|(name, count)| {
                serde_json::json!({
                    "name":  name,
                    "count": count,
                })
            })
            .collect();
        functions.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        let mut natives: Vec<serde_json::Value> = self
            .native_counts
            .iter()
            .map(|(name, count)| {
                serde_json::json!({
                    "name":  name,
                    "count": count,
                })
            })
            .collect();
        natives.sort_by_key(|v| std::cmp::Reverse(v["count"].as_u64().unwrap_or(0)));

        serde_json::json!({
            "total_walks":       self.total_walks,
            "arms":              arms,        // aggregated by ty (backward-compatible)
            "variants":          variants,    // full (ty, inst) granularity
            "functions":         functions,
            "natives":           natives,
            "choice_attempts":   self.choice_attempts,
            "choice_successes":  self.choice_successes,
            "choice_failures":   self.choice_failures,
            "choice_success_rate": if self.choice_attempts > 0 {
                (self.choice_successes as f64) / (self.choice_attempts as f64)
            } else { 0.0 },
            "match_lookups":      self.match_lookups,
            "match_hits":         self.match_hits,
            "match_defaults":     self.match_defaults,
            "match_misses":       self.match_misses,
        })
    }
}

#[derive(Clone)]
struct SwitchArm {
    pattern: NodeID,
    body: NodeID,
}

#[derive(Clone, Default)]
struct SwitchTable {
    cases: HashMap<NodeID, NodeID>,
    dynamic_arms: Vec<SwitchArm>,
    default_body: Option<NodeID>,
}

// Arena — the mutable-during-walk runtime state. Held as `&mut Arena`
// by the walker; orthogonal to the kernel so reading recipes and
// writing frames don't fight the borrow checker.
pub(crate) struct Arena {
    frames: Vec<Frame>,
    // Monotonic count of closures created during this arena's life. The `walk`
    // wrapper uses it to decide when reclaiming frames on return is sound: a
    // closure is the ONLY Value that captures a FrameId, so if no closure was
    // created during a walk call, every frame it pushed is provably dead and may
    // be truncated. Without this, frames accumulated for the whole eval — the
    // cause of the multi-GB BML parse runaway (Go stays ~10 MB because its
    // frames are GC'd *Frame pointers, reclaimed as soon as they go unreachable).
    closures_created: u64,
}

impl Arena {
    pub(crate) fn new() -> Self {
        Self {
            frames: Vec::with_capacity(256),
            closures_created: 0,
        }
    }

    pub(crate) fn new_frame(&mut self, parent: Option<FrameId>) -> FrameId {
        let id = self.frames.len() as FrameId;
        self.frames.push(Frame {
            parent,
            bindings: Vec::new(),
        });
        id
    }

    // OPT (2026-05-21): allocate a frame with pre-sized bindings vec. Used
    // by the FNCALL hot path where the exact arg count is known. Saves
    // Vec capacity reallocations during arg-binding for recursive workloads
    // (fib at 1973 calls × 1 arg = 1973 reallocations avoided).
    pub(crate) fn new_frame_with_capacity(
        &mut self,
        parent: Option<FrameId>,
        cap: usize,
    ) -> FrameId {
        let id = self.frames.len() as FrameId;
        self.frames.push(Frame {
            parent,
            bindings: Vec::with_capacity(cap),
        });
        id
    }

    pub(crate) fn bind(&mut self, fid: FrameId, name: NameID, v: Value) {
        let f = &mut self.frames[fid as usize];
        for slot in &mut f.bindings {
            if slot.0 == name {
                slot.1 = v;
                return;
            }
        }
        f.bindings.push((name, v));
    }

    pub(crate) fn lookup(&self, fid: FrameId, name: NameID) -> Option<Value> {
        let mut cur = Some(fid);
        while let Some(id) = cur {
            let f = &self.frames[id as usize];
            for slot in &f.bindings {
                if slot.0 == name {
                    return Some(slot.1.clone());
                }
            }
            cur = f.parent;
        }
        None
    }
}

impl Kernel {
    pub(crate) fn new() -> Self {
        let mut k = Self {
            by_shape: HashMap::new(),
            by_id: HashMap::new(),
            source_attr: HashMap::new(),
            walk_cache: HashMap::new(),
            walk_cache_hits: 0,
            walk_cache_misses: 0,
            import_seq: 1,
            strs: Vec::new(),
            str_idx: HashMap::new(),
            f64s: Vec::new(),
            f64_idx: HashMap::new(),
            next_inst: 1,
            natives: HashMap::new(),
            env_natives: HashMap::new(),
            methods: HashMap::new(),
            jit_aliases: HashMap::new(),
            jit_compiled: HashMap::new(),
            jit_hits: HashMap::new(),
            jit_failed: HashSet::new(),
            maps: HashMap::new(),
            next_map: 0,
            switch_tables: HashMap::new(),
            active_roots: Vec::new(),
            trace: None,
        };
        k.register_natives();
        k
    }

    // intern — content-addressed insertion. Same shape ⇒ same NodeID.
    pub(crate) fn intern(&mut self, category: NodeID, children: Vec<NodeID>) -> NodeID {
        let key = ShapeKey {
            category,
            children: children.clone(),
        };
        if let Some(&nid) = self.by_shape.get(&key) {
            return nid;
        }
        let nid = NodeID {
            pkg: 0,
            level: category.level,
            ty: category.ty,
            inst: self.next_inst,
        };
        self.next_inst += 1;
        self.by_shape.insert(key, nid);
        self.by_id.insert(nid, Recipe { category, children });
        nid
    }

    fn next_import_scope(&mut self) -> u32 {
        let scope = self.import_seq;
        self.import_seq += 1;
        scope
    }

    fn remap_imported_leaf(&mut self, scope: u32, nid: NodeID) -> NodeID {
        if nid.pkg != 0 {
            return nid;
        }
        let children = vec![
            self.intern_trivial_int(scope as i64),
            self.intern_trivial_int(nid.level as i64),
            self.intern_trivial_int(nid.ty as i64),
            self.intern_trivial_int(nid.inst as i64),
        ];
        self.intern(cat_undefined(), children)
    }

    pub(crate) fn intern_trivial_int(&self, n: i64) -> NodeID {
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_INT,
            inst: (n as i32) as u32,
        }
    }

    // intern_trivial_float64 — content-addressed insertion into the f64
    // overflow table. The trivial NodeID carries the table index in `inst`.
    // Canonicalization matches the TS sibling kernel so the same float
    // value parsed twice produces the same NodeID:
    //   - any NaN bit pattern collapses to qNaN (0x7ff8000000000000)
    //   - -0.0 collapses to +0.0
    //   - ±Inf keep distinct identity
    pub(crate) fn intern_trivial_float64(&mut self, f: f64) -> NodeID {
        let canonical = if f.is_nan() {
            f64::from_bits(0x7ff8000000000000)
        } else if f == 0.0 {
            0.0
        } else {
            f
        };
        let bits = canonical.to_bits();
        if let Some(&idx) = self.f64_idx.get(&bits) {
            return NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_FLOAT64,
                inst: idx,
            };
        }
        let idx = self.f64s.len() as u32;
        self.f64s.push(canonical);
        self.f64_idx.insert(bits, idx);
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_FLOAT64,
            inst: idx,
        }
    }

    pub(crate) fn decode_float64(&self, inst: u32) -> f64 {
        self.f64s
            .get(inst as usize)
            .copied()
            .unwrap_or_else(|| panic!("decode_float64: bad index {}", inst))
    }

    // intern_trivial_float32 — IEEE 754 32-bit inline encoding. The float's bit
    // pattern (via f32::to_bits) lives directly in the inst slot; no overflow
    // table needed. Two f32 values with the same bit pattern share the same
    // NodeID by construction. NaN bit patterns are NOT canonicalized here (f32
    // NaNs are uncommon at the substrate boundary); a typed-numeric layer above
    // collapses them if needed. Sibling parity with Go/TS internTrivialFloat32.
    // Float *literals* in .fk source still parse as float64; this constructor is
    // reached when Form code explicitly asks for a float32 via the make_float32
    // native (sibling of Go/TS make_float32), and the decode side
    // (decode_float32, the TRIV_FLOAT32 dispatch arms) carries the read-parity.
    // Constructor and decoder are now both live three-way.
    pub(crate) fn intern_trivial_float32(&self, f: f32) -> NodeID {
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_FLOAT32,
            inst: f.to_bits(),
        }
    }

    // decode_float32 — read back the IEEE bit pattern from the inst slot.
    pub(crate) fn decode_float32(&self, inst: u32) -> f32 {
        f32::from_bits(inst)
    }

    pub(crate) fn intern_string(&mut self, s: &str) -> NodeID {
        if let Some(&idx) = self.str_idx.get(s) {
            return NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_STRING,
                inst: idx,
            };
        }
        let idx = self.strs.len() as u32;
        self.strs.push(s.to_string());
        self.str_idx.insert(s.to_string(), idx);
        NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_STRING,
            inst: idx,
        }
    }

    /// Build a Record value from a blueprint and (field-name, value) pairs.
    ///
    /// The structure-access marshalling seam: the PyO3 bridge lowers a Python
    /// dict (or a model via model_dump()) onto a kernel Record so a transmuted
    /// recipe can read named fields via `record_get`. Field names intern to
    /// NameIDs here exactly as the `record_new` native does (main.rs ~2051), so
    /// a record marshalled from Python and one built by `record_new` in Form
    /// are the same shape — `record_get`/`record_has` read both identically.
    #[cfg(feature = "pyo3")]
    pub(crate) fn make_record(&mut self, blueprint: NodeID, pairs: Vec<(String, Value)>) -> Value {
        let fields: Vec<(NameID, Value)> = pairs
            .into_iter()
            .map(|(name, value)| (self.intern_string(&name).inst, value))
            .collect();
        Value::Record(Arc::new(Mutex::new(Record { blueprint, fields })))
    }

    fn substrate_mark(&self) -> Vec<Value> {
        vec![
            Value::Int(self.next_inst as i64),
            Value::Int(self.strs.len() as i64),
            Value::Int(self.by_id.len() as i64),
        ]
    }

    fn substrate_counts(&self) -> Vec<Value> {
        vec![
            Value::Int(self.by_id.len() as i64),
            Value::Int(self.strs.len() as i64),
        ]
    }

    fn substrate_release(&mut self, mark: &[Value]) -> i64 {
        if mark.len() < 2 {
            return 0;
        }
        let next_mark = mark[0].as_int() as u32;
        let str_mark = mark[1].as_int() as usize;
        if next_mark == 0 || str_mark > self.strs.len() {
            return 0;
        }
        let doomed: Vec<NodeID> = self
            .by_id
            .keys()
            .copied()
            .filter(|nid| nid.pkg == 0 && nid.inst >= next_mark)
            .collect();
        for nid in &doomed {
            self.by_id.remove(nid);
            self.source_attr.remove(nid);
            self.walk_cache.remove(nid);
            self.switch_tables.remove(nid);
        }
        self.by_shape
            .retain(|_, nid| !(nid.pkg == 0 && nid.inst >= next_mark));
        for s in self.strs.iter().skip(str_mark) {
            self.str_idx.remove(s);
        }
        self.strs.truncate(str_mark);
        self.next_inst = next_mark;
        self.walk_cache.clear();
        doomed.len() as i64
    }

    fn mark_string_node(n: NodeID, live_strings: &mut HashSet<NameID>) {
        if n.pkg == 1 && n.level == LEVEL_TRIVIAL && n.ty == TRIV_STRING {
            live_strings.insert(n.inst);
        }
    }

    fn mark_node(
        &self,
        n: NodeID,
        live_nodes: &mut HashSet<NodeID>,
        live_strings: &mut HashSet<NameID>,
    ) {
        Self::mark_string_node(n, live_strings);
        if n.pkg != 0 || live_nodes.contains(&n) {
            return;
        }
        let Some(recipe) = self.by_id.get(&n) else {
            return;
        };
        live_nodes.insert(n);
        self.mark_node(recipe.category, live_nodes, live_strings);
        for child in &recipe.children {
            self.mark_node(*child, live_nodes, live_strings);
        }
    }

    fn mark_value(
        &self,
        value: &Value,
        arena: Option<&Arena>,
        live_nodes: &mut HashSet<NodeID>,
        live_strings: &mut HashSet<NameID>,
        live_frames: &mut HashSet<FrameId>,
    ) {
        match value {
            Value::List(xs) => {
                for item in xs.iter() {
                    self.mark_value(item, arena, live_nodes, live_strings, live_frames);
                }
            }
            Value::Closure(cl) => {
                live_strings.insert(cl.name);
                self.mark_node(cl.body, live_nodes, live_strings);
                if let Some(a) = arena {
                    self.mark_frame(a, cl.env, live_nodes, live_strings, live_frames);
                }
            }
            Value::Nid(nid) => self.mark_node(*nid, live_nodes, live_strings),
            _ => {}
        }
    }

    fn mark_frame(
        &self,
        arena: &Arena,
        frame: FrameId,
        live_nodes: &mut HashSet<NodeID>,
        live_strings: &mut HashSet<NameID>,
        live_frames: &mut HashSet<FrameId>,
    ) {
        let mut cur = Some(frame);
        while let Some(id) = cur {
            if !live_frames.insert(id) {
                return;
            }
            let Some(f) = arena.frames.get(id as usize) else {
                return;
            };
            for (name, value) in &f.bindings {
                live_strings.insert(*name);
                self.mark_value(value, Some(arena), live_nodes, live_strings, live_frames);
            }
            cur = f.parent;
        }
    }

    fn substrate_gc(&mut self, roots: &[Value], stack: Option<(&Arena, FrameId)>) -> Vec<Value> {
        let mut live_nodes: HashSet<NodeID> = HashSet::new();
        let mut live_strings: HashSet<NameID> = HashSet::new();
        let mut live_frames: HashSet<FrameId> = HashSet::new();
        for name in self.natives.keys() {
            live_strings.insert(*name);
        }
        for (_, (file_id, _, _)) in &self.source_attr {
            live_strings.insert(*file_id);
        }
        for root in &self.active_roots {
            self.mark_node(*root, &mut live_nodes, &mut live_strings);
        }
        for root in roots {
            self.mark_value(
                root,
                stack.map(|(arena, _)| arena),
                &mut live_nodes,
                &mut live_strings,
                &mut live_frames,
            );
        }
        if let Some((arena, frame)) = stack {
            self.mark_frame(
                arena,
                frame,
                &mut live_nodes,
                &mut live_strings,
                &mut live_frames,
            );
        }
        let mut changed = true;
        while changed {
            let before_nodes = live_nodes.len();
            let before_strings = live_strings.len();
            for (nid, value) in &self.walk_cache {
                if live_nodes.contains(nid) {
                    self.mark_value(
                        value,
                        stack.map(|(arena, _)| arena),
                        &mut live_nodes,
                        &mut live_strings,
                        &mut live_frames,
                    );
                }
            }
            changed = live_nodes.len() != before_nodes || live_strings.len() != before_strings;
        }
        let doomed: Vec<NodeID> = self
            .by_id
            .keys()
            .copied()
            .filter(|nid| nid.pkg == 0 && !live_nodes.contains(nid))
            .collect();
        for nid in &doomed {
            self.by_id.remove(nid);
            self.source_attr.remove(nid);
            self.walk_cache.remove(nid);
            self.switch_tables.remove(nid);
        }
        self.by_shape
            .retain(|_, nid| !(nid.pkg == 0 && !live_nodes.contains(nid)));
        self.walk_cache
            .retain(|nid, _| nid.pkg != 0 || live_nodes.contains(nid));
        let mut pruned = 0usize;
        if stack.is_some() {
            while let Some(idx) = self.strs.len().checked_sub(1) {
                let name_id = idx as NameID;
                if live_strings.contains(&name_id) {
                    break;
                }
                if let Some(s) = self.strs.pop() {
                    self.str_idx.remove(&s);
                    pruned += 1;
                }
            }
        }
        vec![Value::Int(doomed.len() as i64), Value::Int(pruned as i64)]
    }

    fn category(&self, n: NodeID) -> NodeID {
        if n.level == LEVEL_TRIVIAL {
            return n;
        }
        self.by_id.get(&n).map(|r| r.category).unwrap_or(n)
    }

    // Owned children — clones the children vec. The slice version went
    // away when substrate-write natives required `&mut Kernel`; future
    // breath restores zero-copy via Cow<'_, [NodeID]>.
    pub(crate) fn children(&self, n: NodeID) -> Vec<NodeID> {
        self.by_id
            .get(&n)
            .map(|r| r.children.clone())
            .unwrap_or_default()
    }

    fn readonly_worker_clone(&self) -> Self {
        Self {
            by_shape: self.by_shape.clone(),
            by_id: self.by_id.clone(),
            source_attr: self.source_attr.clone(),
            walk_cache: HashMap::new(),
            walk_cache_hits: 0,
            walk_cache_misses: 0,
            import_seq: self.import_seq,
            strs: self.strs.clone(),
            str_idx: self.str_idx.clone(),
            f64s: self.f64s.clone(),
            f64_idx: self.f64_idx.clone(),
            next_inst: self.next_inst,
            natives: self.natives.clone(),
            env_natives: self.env_natives.clone(),
            methods: self.methods.clone(),
            jit_aliases: self.jit_aliases.clone(),
            // Arc clones — Library handles stay shared across the kernel and
            // its workers; the .so stays mapped for the duration.
            jit_compiled: self.jit_compiled.clone(),
            // Workers share the known-failed set (don't re-attempt a shape the
            // compiler already refused) but count heat independently (each senses
            // its own hot paths).
            jit_hits: HashMap::new(),
            jit_failed: self.jit_failed.clone(),
            // Dispatch tables are content (built at load); each worker carries
            // its own copy so routing needs no lock.
            maps: self.maps.clone(),
            next_map: self.next_map,
            switch_tables: self.switch_tables.clone(),
            active_roots: Vec::new(),
            trace: None,
        }
    }

    fn is_parallel_pure(&self, n: NodeID, seen: &mut HashSet<NodeID>) -> bool {
        if n.level == LEVEL_TRIVIAL {
            return true;
        }
        if !seen.insert(n) {
            return true;
        }
        let Some(recipe) = self.by_id.get(&n) else {
            return false;
        };
        match recipe.category.ty {
            RB_MATH | RB_COMPARE | RB_LOGIC | RB_COND | RB_LIST | RB_MATCH => recipe
                .children
                .iter()
                .all(|child| self.is_parallel_pure(*child, seen)),
            _ => false,
        }
    }

    pub(crate) fn trivial_value(&self, n: NodeID) -> Value {
        match n.ty {
            TRIV_INT => Value::Int((n.inst as i32) as i64),
            TRIV_STRING => Value::Str(self.strs[n.inst as usize].clone().into()),
            TRIV_BOOL => Value::Bool(n.inst != 0),
            TRIV_NULL => Value::Null,
            TRIV_FLOAT32 => Value::Float(self.decode_float32(n.inst) as f64),
            TRIV_FLOAT64 => Value::Float(self.decode_float64(n.inst)),
            _ => panic!("trivial_value: unknown trivial type {}", n.ty),
        }
    }

    // Interned name handle — the NameID this identifier resolves to. No
    // string allocation, no comparison; lookup is a u32 compare downstream.
    //
    // OPT (2026-05-21): Reads `self.by_id.get(&n)` directly instead of going
    // through `self.children(n)` which clones the children Vec. Saves one
    // Vec allocation per IDENT dispatch. With IDENT at 36.5% of dispatches
    // on python_demo.fk (viz_kernel_trace.py output), this is the single
    // hottest path in the walker.
    fn ident_id(&self, n: NodeID) -> NameID {
        if n.level == LEVEL_TRIVIAL && n.ty == TRIV_STRING {
            return n.inst;
        }
        if let Some(r) = self.by_id.get(&n) {
            let kids = &r.children;
            if kids.len() == 1 && kids[0].level == LEVEL_TRIVIAL && kids[0].ty == TRIV_STRING {
                return kids[0].inst;
            }
        }
        panic!("ident_id: {:?} is not an identifier shape", n);
    }

    // Resolve a NameID back to its source-level string. Only used in error
    // messages and on the parse-time slow path.
    fn name_str(&self, id: NameID) -> &str {
        &self.strs[id as usize]
    }
}

// ---------------------------------------------------------------------------
// Values — runtime tagged values
// ---------------------------------------------------------------------------

// `Nid` lets Form code hold NodeIDs as first-class values — the foundation
// for substrate-write natives that close form-runtime-in-form gaps W1-W3.
#[derive(Clone, Debug)]
pub(crate) enum Value {
    Null,
    Int(i64),
    Float(f64),
    Str(Arc<str>),
    Bool(bool),
    List(Arc<Vec<Value>>),
    Closure(Arc<Closure>),
    Nid(NodeID),
    // Record — a mutable struct/object with identity. The first mutable Value
    // the kernel carries; BML requires it for `self.x = v`. `blueprint` tags
    // the record's type (its method-table / class NodeID); `fields` is an
    // ordered name→value map. Arc<Mutex> gives shared mutable identity that is
    // also Send (Value crosses thread boundaries in the parallel arms), so two
    // bindings to the same record see each other's mutations — object
    // semantics, not value-copy semantics.
    Record(Arc<Mutex<Record>>),
}

#[derive(Debug)]
pub(crate) struct Record {
    blueprint: NodeID,
    fields: Vec<(NameID, Value)>,
}

impl Record {
    fn get(&self, name: NameID) -> Option<Value> {
        self.fields
            .iter()
            .rev()
            .find(|(n, _)| *n == name)
            .map(|(_, v)| v.clone())
    }
    fn set(&mut self, name: NameID, value: Value) {
        if let Some(slot) = self.fields.iter_mut().find(|(n, _)| *n == name) {
            slot.1 = value;
        } else {
            self.fields.push((name, value));
        }
    }
}

#[derive(Debug)]
pub(crate) struct Closure {
    // Interned name for display only — runtime lookup never uses it.
    name: NameID,
    params: Vec<NameID>,
    body: NodeID,
    env: FrameId,
}

// JitCompiled — a Form recipe that has been compiled to host-native code
// through the system Rust toolchain.
//
// Shape parallel to TS (compileNode → new Function → V8 JIT) and Go
// (recipe → Go source → plugin.Open). For Rust the equivalent toolchain
// is: recipe → Rust source → `rustc --crate-type=cdylib` → libloading.
//
// The C-ABI cdylib exports a single fixed symbol `compiled_fn` whose
// signature is `unsafe extern "C" fn(i64, i64, ..., i64) -> i64`. Arity
// matches the closure's param count; the field `arity` is the runtime
// signature dispatch tag (1, 2, 3, … up to JIT_MAX_ARITY).
//
// LIBRARY LIFETIME: the Library handle must outlive the function pointer
// it produced — `libloading::Symbol` borrows the Library, and dropping
// the Library unmaps the .so so the function pointer dangles. We store
// the Library + the raw function pointer together in this struct; the
// struct is held by Arc and never dropped until the kernel is dropped.
// The Library and the function pointer share that lifetime, which is
// what makes the unsafe call later sound.
pub(crate) struct JitCompiled {
    // Holds the loaded .so. Underscore prefix: read only via Drop.
    // Must not be dropped while `func` may still be invoked.
    _library: libloading::Library,
    // Raw function pointer — typed by arity at call sites.
    // For arity N, callers cast this to `unsafe extern "C" fn(i64,…,i64) -> i64`
    // with N i64 parameters and invoke it in a tight unsafe block.
    func: *const (),
    arity: usize,
    // Keep the temp dir's path so we can clean up on drop. Owning the
    // PathBuf (not a TempDir handle) lets the directory survive process
    // restart in case of crash — a tiny leak in /tmp is recoverable; an
    // unmappable .so during the cdylib's lifetime is not.
    _temp_dir: PathBuf,
}

// JitCompiled holds a *const ptr; the underlying memory is the loaded .so
// which is process-global and read-only after rustc emitted it. Send + Sync
// are sound here because the function we call is a pure i64→i64 transformer
// with no shared mutable state.
unsafe impl Send for JitCompiled {}
unsafe impl Sync for JitCompiled {}

impl std::fmt::Debug for JitCompiled {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "<JitCompiled arity={}>", self.arity)
    }
}

impl Drop for JitCompiled {
    fn drop(&mut self) {
        // Manual drop runs BEFORE field drops, so we can't depend on _library
        // having been unmapped here. Instead: on Linux removing a file that
        // libloading currently has dlopen'd is safe — the kernel keeps the
        // mapping alive until dlclose runs. So we can remove the temp dir
        // now; the dlclose that happens when _library drops (immediately
        // after this Drop::drop returns) will close the mapping cleanly even
        // though the on-disk file is gone. Best-effort: ignore errors.
        let _ = fs::remove_dir_all(&self._temp_dir);
    }
}

// Maximum arity the JIT supports — bounded so dispatch can be a static
// match instead of dynamic generation. Form recipes with more parameters
// fall back to recipe-walk; the recipe stays canonical truth.
const JIT_MAX_ARITY: usize = 8;
// How many calls to an undecided recipe before measured repetition attempts a
// host-native compile. High enough that the rustc compile cost amortizes over
// the native calls that follow; low enough that a genuinely hot loop promotes
// quickly. The trigger is heat, not a hand-placed annotation.
const JIT_HOT_THRESHOLD: u32 = 2000;

impl Value {
    pub(crate) fn display(&self) -> String {
        match self {
            Value::Null => "null".to_string(),
            Value::Int(n) => n.to_string(),
            Value::Float(f) => format_float(*f),
            Value::Str(s) => s.to_string(),
            Value::Bool(b) => {
                if *b {
                    "true".to_string()
                } else {
                    "false".to_string()
                }
            }
            Value::List(xs) => {
                let parts: Vec<String> = xs.iter().map(|x| x.display()).collect();
                format!("[{}]", parts.join(", "))
            }
            Value::Closure(c) => format!("<closure #{}>", c.name),
            Value::Nid(n) => format!("@{}.{}.{}.{}", n.pkg, n.level, n.ty, n.inst),
            Value::Record(r) => {
                let rec = r.lock().unwrap();
                format!(
                    "<record @{}.{}.{}.{} #{}fields>",
                    rec.blueprint.pkg,
                    rec.blueprint.level,
                    rec.blueprint.ty,
                    rec.blueprint.inst,
                    rec.fields.len()
                )
            }
        }
    }

    fn as_nid(&self) -> NodeID {
        match self {
            Value::Nid(n) => *n,
            _ => panic!("as_nid: {:?}", self),
        }
    }

    fn as_int(&self) -> i64 {
        match self {
            Value::Int(n) => *n,
            Value::Float(f) => *f as i64,
            Value::Bool(b) => {
                if *b {
                    1
                } else {
                    0
                }
            }
            _ => panic!("as_int: {:?}", self),
        }
    }

    fn as_float(&self) -> f64 {
        match self {
            Value::Float(f) => *f,
            Value::Int(n) => *n as f64,
            Value::Bool(b) => {
                if *b {
                    1.0
                } else {
                    0.0
                }
            }
            _ => panic!("as_float: {:?}", self),
        }
    }

    fn as_bool(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Int(n) => *n != 0,
            Value::Float(f) => *f != 0.0,
            Value::Null => false,
            _ => true,
        }
    }

    fn as_str(&self) -> &str {
        match self {
            Value::Str(s) => s,
            _ => panic!("as_str: {:?}", self),
        }
    }
}

#[derive(Clone)]
struct SourceNativeLexicon {
    keywords: HashSet<String>,
    properties: HashSet<String>,
    keyword_kind: String,
    property_kind: String,
    name_kind: String,
    int_kind: String,
    float_kind: String,
    string_kind: String,
    char_kind: String,
    op_kind: String,
    ops: Vec<String>,
    line_comment: String,
    block_open: String,
    block_close: String,
}

fn source_native_str(value: &str) -> Value {
    Value::Str(value.to_string().into())
}

fn source_native_empty_list() -> Value {
    Value::List(vec![].into())
}

fn source_native_atom(kind: &str, value: &str) -> Value {
    Value::List(
        vec![
            source_native_str("cell"),
            source_native_str(kind),
            source_native_str(value),
            source_native_empty_list(),
            Value::Null,
        ]
        .into(),
    )
}

fn source_native_string_set(value: &Value, field: &str) -> HashSet<String> {
    match value {
        Value::List(xs) => xs.iter().map(|v| v.as_str().to_string()).collect(),
        _ => panic!("source_scan_file: {} must be list", field),
    }
}

fn source_native_string_list(value: &Value, field: &str) -> Vec<String> {
    match value {
        Value::List(xs) => xs.iter().map(|v| v.as_str().to_string()).collect(),
        _ => panic!("source_scan_file: {} must be list", field),
    }
}

fn source_native_field<'a>(xs: &'a [Value], idx: usize, field: &str) -> &'a Value {
    xs.get(idx)
        .unwrap_or_else(|| panic!("source_scan_file: lexicon missing {}", field))
}

fn source_native_field_str(xs: &[Value], idx: usize, field: &str) -> String {
    source_native_field(xs, idx, field).as_str().to_string()
}

fn source_native_lexicon_from_value(value: &Value) -> SourceNativeLexicon {
    let xs = match value {
        Value::List(xs) => xs,
        _ => panic!("source_scan_file: lexicon must be a list"),
    };
    if xs.len() < 15 || source_native_field_str(xs, 0, "tag") != "source-lexicon" {
        panic!("source_scan_file: lexicon must be (source-lexicon ...)");
    }
    SourceNativeLexicon {
        keywords: source_native_string_set(source_native_field(xs, 1, "keywords"), "keywords"),
        properties: source_native_string_set(
            source_native_field(xs, 2, "properties"),
            "properties",
        ),
        keyword_kind: source_native_field_str(xs, 3, "keyword-kind"),
        property_kind: source_native_field_str(xs, 4, "property-kind"),
        name_kind: source_native_field_str(xs, 5, "name-kind"),
        int_kind: source_native_field_str(xs, 6, "int-kind"),
        float_kind: source_native_field_str(xs, 7, "float-kind"),
        string_kind: source_native_field_str(xs, 8, "string-kind"),
        char_kind: source_native_field_str(xs, 9, "char-kind"),
        op_kind: source_native_field_str(xs, 10, "op-kind"),
        ops: source_native_string_list(source_native_field(xs, 11, "ops"), "ops"),
        line_comment: source_native_field_str(xs, 12, "line-comment"),
        block_open: source_native_field_str(xs, 13, "block-open"),
        block_close: source_native_field_str(xs, 14, "block-close"),
    }
}

fn source_native_name_kind<'a>(lex: &'a SourceNativeLexicon, value: &str) -> &'a str {
    if lex.keywords.contains(value) {
        &lex.keyword_kind
    } else if lex.properties.contains(value) {
        &lex.property_kind
    } else {
        &lex.name_kind
    }
}

fn source_native_name_start(b: u8) -> bool {
    b.is_ascii_alphabetic() || b == b'_'
}

fn source_native_name_char(b: u8) -> bool {
    source_native_name_start(b) || b.is_ascii_digit()
}

fn source_native_hex_digit(b: u8) -> bool {
    b.is_ascii_hexdigit()
}

fn source_native_bin_digit(b: u8) -> bool {
    matches!(b, b'0' | b'1')
}

fn source_native_decode_escape(b: u8) -> u8 {
    match b {
        b'\\' => b'\\',
        b'\'' => b'\'',
        b'"' => b'"',
        b'n' => b'\n',
        b't' => b'\t',
        b'r' => b'\r',
        b'0' => 0,
        _ => b,
    }
}

fn source_native_scan_quoted(src: &str, i: usize, quote: u8) -> (String, usize) {
    let bytes = src.as_bytes();
    let mut j = i + 1;
    let mut out = String::new();
    while j < bytes.len() {
        let c = bytes[j];
        if c == b'\\' && j + 1 < bytes.len() {
            out.push(source_native_decode_escape(bytes[j + 1]) as char);
            j += 2;
            continue;
        }
        if c == quote {
            return (out, j + 1);
        }
        out.push(c as char);
        j += 1;
    }
    (out, j)
}

fn source_native_skip(src: &str, mut i: usize, lex: &SourceNativeLexicon) -> usize {
    let bytes = src.as_bytes();
    while i < bytes.len() {
        let c = bytes[i];
        if matches!(c, b' ' | b'\t' | b'\n' | b'\r') {
            i += 1;
            continue;
        }
        if !lex.line_comment.is_empty() && src[i..].starts_with(&lex.line_comment) {
            i += lex.line_comment.len();
            while i < bytes.len() && bytes[i] != b'\n' {
                i += 1;
            }
            continue;
        }
        if !lex.block_open.is_empty()
            && !lex.block_close.is_empty()
            && src[i..].starts_with(&lex.block_open)
        {
            if let Some(end) = src[i + lex.block_open.len()..].find(&lex.block_close) {
                i = i + lex.block_open.len() + end + lex.block_close.len();
                continue;
            }
            return bytes.len();
        }
        break;
    }
    i
}

fn source_native_scan_text(src: &str, lex: &SourceNativeLexicon) -> Value {
    let bytes = src.as_bytes();
    let mut out: Vec<Value> = vec![];
    let mut i = 0usize;
    while i < bytes.len() {
        i = source_native_skip(src, i, lex);
        if i >= bytes.len() {
            break;
        }
        let c = bytes[i];
        if c == b'"' {
            let (value, next) = source_native_scan_quoted(src, i, b'"');
            out.push(source_native_atom(&lex.string_kind, &value));
            i = next;
            continue;
        }
        if c == b'\'' {
            let (value, next) = source_native_scan_quoted(src, i, b'\'');
            out.push(source_native_atom(&lex.char_kind, &value));
            i = next;
            continue;
        }
        if c.is_ascii_digit() {
            let mut j = i + 1;
            let mut kind = lex.int_kind.as_str();
            if c == b'0' && j < bytes.len() && matches!(bytes[j], b'x' | b'X') {
                j += 1;
                while j < bytes.len() && source_native_hex_digit(bytes[j]) {
                    j += 1;
                }
            } else if c == b'0' && j < bytes.len() && matches!(bytes[j], b'b' | b'B') {
                j += 1;
                while j < bytes.len() && source_native_bin_digit(bytes[j]) {
                    j += 1;
                }
            } else {
                while j < bytes.len() && bytes[j].is_ascii_digit() {
                    j += 1;
                }
                if j < bytes.len()
                    && bytes[j] == b'.'
                    && j + 1 < bytes.len()
                    && bytes[j + 1].is_ascii_digit()
                {
                    kind = lex.float_kind.as_str();
                    j += 1;
                    while j < bytes.len() && bytes[j].is_ascii_digit() {
                        j += 1;
                    }
                    if j < bytes.len() && matches!(bytes[j], b'e' | b'E') {
                        let mut k = j + 1;
                        if k < bytes.len() && matches!(bytes[k], b'+' | b'-') {
                            k += 1;
                        }
                        if k < bytes.len() && bytes[k].is_ascii_digit() {
                            j = k + 1;
                            while j < bytes.len() && bytes[j].is_ascii_digit() {
                                j += 1;
                            }
                        }
                    }
                }
            }
            out.push(source_native_atom(kind, &src[i..j]));
            i = j;
            continue;
        }
        if source_native_name_start(c) {
            let mut j = i + 1;
            while j < bytes.len() && source_native_name_char(bytes[j]) {
                j += 1;
            }
            let value = &src[i..j];
            out.push(source_native_atom(
                source_native_name_kind(lex, value),
                value,
            ));
            i = j;
            continue;
        }
        let mut matched = "";
        for op in &lex.ops {
            if src[i..].starts_with(op) {
                matched = op;
                break;
            }
        }
        if matched.is_empty() {
            matched = &src[i..i + 1];
        }
        out.push(source_native_atom(&lex.op_kind, matched));
        i += matched.len();
    }
    Value::List(out.into())
}

// format_float — the canonical kernel float display, shared THREE-WAY. JS /
// ECMAScript `String(number)` style: integer-valued floats render WITHOUT a
// trailing ".0" (`1.0` → `"1"`), NaN → "NaN", ±Inf → "Infinity"/"-Infinity".
// This matches Go's `core.FormatFloatJS` (strconv.FormatFloat 'g' -1 64), the
// TS kernel's native `String()`, AND the Go API's JSON float output — so
// Go=Rust=TS agree on every float at the parity boundary (whole-number floats
// were the one latent divergence: Rust alone rendered Python-style "3.0").
// One standard, chosen for the JS majority (2 of 3 kernels + the API already
// did it), so Rust was the only kernel to move. Rust's `{}` is shortest
// round-trip, matching strconv 'g' -1 / JS String() for every finite value.
fn format_float(f: f64) -> String {
    if f.is_nan() {
        return "NaN".to_string();
    }
    if f.is_infinite() {
        return if f > 0.0 {
            "Infinity".to_string()
        } else {
            "-Infinity".to_string()
        };
    }
    format!("{}", f)
}

// round_ndigits_decimal — CPython `round(x, n)` for a finite double, n >= 0.
//
// CPython rounds the TRUE value of the double (a finite dyadic decimal) to n
// fractional digits using round-half-to-even, then takes the nearest double.
// The naive f64 paths (`floor(x*10^n+0.5)/10^n`, or banker's on the scaled
// f64) BOTH diverge, because the `*10^n` reintroduces representation error
// CPython's decimal path avoids. The honest path never scales in f64: it
// rounds on the EXACT decimal expansion of the double.
//
// We obtain that exact expansion with `format!("{:.1074}", |x|)`. A finite
// double `m * 2^e2` (e2 < 0) equals `m * 5^(-e2) / 10^(-e2)`, a decimal with
// exactly `-e2` fractional digits; -e2 <= 1074 for every double (the smallest
// subnormal). So 1074 places is the exact, correctly-terminating expansion for
// any double — no domain assumption, no pre-rounding at the round position.
// Verified bit-for-bit against CPython on 6.6M cases (random magnitudes at
// n=2,4; adversarial nextafter-of-half ties at n=0,2,4,6; random 64-bit
// patterns incl. subnormals) with ZERO divergences. The sibling Go kernel
// uses strconv.FormatFloat('f',1074); the TS kernel builds the same exact
// decimal from the IEEE mantissa via BigInt (its toFixed caps at 100 places).
fn round_ndigits_decimal(x: f64, n: i64) -> f64 {
    if x.is_nan() || x.is_infinite() {
        return x;
    }
    let neg = x.is_sign_negative();
    let ax = x.abs();
    // Exact fixed-point decimal of |x|. 1074 fractional places is the full
    // terminating expansion for any double; no rounding occurs at the tail.
    let s = format!("{:.1074}", ax);
    let dot = s.find('.').unwrap();
    let ipart = &s[..dot];
    let fpart = &s[dot + 1..];
    // Concatenated digit string; decimal point sits after `point` digits.
    let mut digits: Vec<u8> = Vec::with_capacity(ipart.len() + fpart.len());
    digits.extend_from_slice(ipart.as_bytes());
    digits.extend_from_slice(fpart.as_bytes());
    let point = ipart.len() as i64;
    let keep = point + n; // number of leading digits to keep
    if keep < 0 {
        // Magnitude rounds below the n-th place to zero.
        return if neg { -0.0 } else { 0.0 };
    }
    let keep = keep as usize;
    if digits.len() < keep {
        digits.resize(keep, b'0');
    }
    let kept_slice = &digits[..keep];
    let rest = &digits[keep..];
    // kept as a decimal string (avoid empty)
    let mut kept: String = if kept_slice.is_empty() {
        "0".to_string()
    } else {
        String::from_utf8_lossy(kept_slice).into_owned()
    };
    // Round-half-to-even on `rest`.
    let mut round_up = false;
    if let Some(&first) = rest.first() {
        if first > b'5' {
            round_up = true;
        } else if first < b'5' {
            round_up = false;
        } else {
            // first == '5': nonzero tail => up; exact half => to even.
            let tail_nonzero = rest[1..].iter().any(|&d| d != b'0');
            if tail_nonzero {
                round_up = true;
            } else {
                let last_kept = kept.as_bytes()[kept.len() - 1];
                round_up = (last_kept - b'0') % 2 == 1;
            }
        }
    }
    if round_up {
        kept = add_one_decimal(&kept);
    }
    // Rebuild the decimal `kept * 10^-n`, then parse to the nearest double.
    let dec = compose_scaled_decimal(&kept, n, neg);
    let out: f64 = dec.parse().unwrap_or(0.0);
    if out == 0.0 && neg {
        -0.0
    } else {
        out
    }
}

// add_one_decimal — increment a non-negative decimal digit string by 1,
// propagating carry (may grow the string by one leading digit).
fn add_one_decimal(s: &str) -> String {
    let mut bytes: Vec<u8> = s.as_bytes().to_vec();
    let mut i = bytes.len();
    loop {
        if i == 0 {
            bytes.insert(0, b'1');
            break;
        }
        i -= 1;
        if bytes[i] == b'9' {
            bytes[i] = b'0';
        } else {
            bytes[i] += 1;
            break;
        }
    }
    String::from_utf8(bytes).unwrap()
}

// compose_scaled_decimal — render the integer string `kept` scaled by 10^-n
// as a decimal literal, with the given sign. n >= 0.
fn compose_scaled_decimal(kept: &str, n: i64, neg: bool) -> String {
    let n = n as usize;
    let body = if n == 0 {
        kept.to_string()
    } else {
        let mut si = kept.to_string();
        if si.len() <= n {
            // pad to at least n+1 digits so there's a leading integer digit
            let pad = n - si.len() + 1;
            si = "0".repeat(pad) + &si;
        }
        let split = si.len() - n;
        format!("{}.{}", &si[..split], &si[split..])
    };
    if neg {
        format!("-{}", body)
    } else {
        body
    }
}

fn native_walk_parallel(k: &mut Kernel, _: &mut Arena, args: &[Value]) -> Value {
    let roots: Vec<NodeID> = match &args[0] {
        Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
        _ => panic!("walk_parallel: first argument must be a list of NodeIDs"),
    };
    let mut workers = args[1].as_int().max(1) as usize;
    if roots.is_empty() {
        return Value::List(Vec::new().into());
    }
    workers = workers.min(roots.len());
    let sequential = |k: &mut Kernel, roots: &[NodeID]| {
        let mut out = Vec::with_capacity(roots.len());
        for root in roots {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            out.push(walk(k, &mut sub_arena, *root, env));
        }
        Value::List(out.into())
    };
    if workers <= 1
        || k.trace.is_some()
        || !roots
            .iter()
            .all(|root| k.is_parallel_pure(*root, &mut HashSet::new()))
    {
        return sequential(k, &roots);
    }

    let mut buckets = vec![Vec::<(usize, NodeID)>::new(); workers];
    for (idx, root) in roots.iter().copied().enumerate() {
        buckets[idx % workers].push((idx, root));
    }
    let mut handles = Vec::with_capacity(workers);
    for bucket in buckets {
        let mut worker = k.readonly_worker_clone();
        handles.push(std::thread::spawn(move || {
            let mut chunk = Vec::with_capacity(bucket.len());
            for (idx, root) in bucket {
                let mut sub_arena = Arena::new();
                let env = sub_arena.new_frame(None);
                chunk.push((idx, walk(&mut worker, &mut sub_arena, root, env)));
            }
            chunk
        }));
    }
    let mut out: Vec<Option<Value>> = vec![None; roots.len()];
    for handle in handles {
        for (idx, value) in handle.join().expect("walk_parallel worker panicked") {
            out[idx] = Some(value);
        }
    }
    Value::List(Arc::new(
        out.into_iter()
            .map(|value| value.expect("walk_parallel missing worker result"))
            .collect(),
    ))
}

fn native_walk_parallel_cached(k: &mut Kernel, _: &mut Arena, args: &[Value]) -> Value {
    let roots: Vec<NodeID> = match &args[0] {
        Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
        _ => panic!("walk_parallel_cached: first argument must be a list of NodeIDs"),
    };
    let mut workers = args[1].as_int().max(1) as usize;
    if roots.is_empty() {
        return Value::List(Vec::new().into());
    }
    workers = workers.min(roots.len());
    let all_pure = roots
        .iter()
        .all(|root| k.is_parallel_pure(*root, &mut HashSet::new()));
    if !all_pure {
        let mut out = Vec::with_capacity(roots.len());
        for root in &roots {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            out.push(walk(k, &mut sub_arena, *root, env));
        }
        return Value::List(out.into());
    }
    if workers <= 1 || roots.len() <= 1 || k.trace.is_some() {
        let cache_enabled = k.trace.is_none();
        let mut out = Vec::with_capacity(roots.len());
        let mut local = HashMap::<NodeID, Value>::new();
        for root in &roots {
            if cache_enabled {
                if let Some(v) = k.walk_cache.get(root).cloned() {
                    k.walk_cache_hits += 1;
                    out.push(v);
                    continue;
                }
                if let Some(v) = local.get(root).cloned() {
                    k.walk_cache_hits += 1;
                    out.push(v);
                    continue;
                }
                k.walk_cache_misses += 1;
            }
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            let value = walk(k, &mut sub_arena, *root, env);
            if cache_enabled {
                k.walk_cache.insert(*root, value.clone());
                local.insert(*root, value.clone());
            }
            out.push(value);
        }
        return Value::List(out.into());
    }

    let mut out: Vec<Option<Value>> = vec![None; roots.len()];
    let mut jobs = Vec::<(usize, NodeID)>::new();
    let mut first = HashMap::<NodeID, usize>::new();
    let mut fanout = HashMap::<usize, Vec<usize>>::new();
    for (idx, root) in roots.iter().copied().enumerate() {
        if let Some(v) = k.walk_cache.get(&root).cloned() {
            k.walk_cache_hits += 1;
            out[idx] = Some(v);
        } else if let Some(primary) = first.get(&root).copied() {
            k.walk_cache_hits += 1;
            fanout.entry(primary).or_default().push(idx);
        } else {
            k.walk_cache_misses += 1;
            first.insert(root, idx);
            jobs.push((idx, root));
        }
    }
    if !jobs.is_empty() {
        let mut buckets = vec![Vec::<(usize, NodeID)>::new(); workers];
        for (pos, job) in jobs.into_iter().enumerate() {
            buckets[pos % workers].push(job);
        }
        let mut handles = Vec::with_capacity(workers);
        for bucket in buckets {
            if bucket.is_empty() {
                continue;
            }
            let mut worker = k.readonly_worker_clone();
            handles.push(std::thread::spawn(move || {
                let mut chunk = Vec::with_capacity(bucket.len());
                for (idx, root) in bucket {
                    let mut sub_arena = Arena::new();
                    let env = sub_arena.new_frame(None);
                    chunk.push((idx, root, walk(&mut worker, &mut sub_arena, root, env)));
                }
                chunk
            }));
        }
        for handle in handles {
            for (idx, root, value) in handle.join().expect("walk_parallel_cached worker panicked") {
                k.walk_cache.insert(root, value.clone());
                out[idx] = Some(value);
                if let Some(dups) = fanout.get(&idx) {
                    for dup in dups {
                        out[*dup] = out[idx].clone();
                    }
                }
            }
        }
    }
    Value::List(Arc::new(
        out.into_iter()
            .map(|value| value.expect("walk_parallel_cached missing worker result"))
            .collect(),
    ))
}

fn native_field_node(
    k: &mut Kernel,
    args: &[Value],
    ty: u32,
    inst: u32,
    native_name: &str,
) -> Value {
    let kids: Vec<NodeID> = match &args[0] {
        Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
        _ => panic!("{}: expected one list of NodeIDs", native_name),
    };
    Value::Nid(k.intern(
        NodeID {
            pkg: 1,
            level: LEVEL_BASIC,
            ty,
            inst,
        },
        kids,
    ))
}

macro_rules! native_field_constructor {
    ($fn_name:ident, $rb_ty:ident, $inst:expr, $native_name:literal) => {
        fn $fn_name(k: &mut Kernel, _: &mut Arena, args: &[Value]) -> Value {
            native_field_node(k, args, $rb_ty, $inst, $native_name)
        }
    };
}

native_field_constructor!(native_field_blueprint, RB_FIELD, 1, "field_blueprint");
native_field_constructor!(native_field_cell, RB_FIELD, 2, "field_cell");
native_field_constructor!(native_field_carrier, RB_CARRIER, 1, "field_carrier");
native_field_constructor!(native_field_topology, RB_TOPOLOGY, 1, "field_topology");
native_field_constructor!(native_field_fiber, RB_FIBER, 1, "field_fiber");
native_field_constructor!(native_field_region, RB_REGION, 1, "field_region");
native_field_constructor!(native_field_boundary, RB_BOUNDARY, 1, "field_boundary");
native_field_constructor!(
    native_field_neighborhood,
    RB_NEIGHBORHOOD,
    1,
    "field_neighborhood"
);
native_field_constructor!(native_field_match, RB_MATCH_FIELD, 1, "field_match");
native_field_constructor!(native_field_delta, RB_DELTA, 1, "field_delta");
native_field_constructor!(native_field_resolve, RB_RESOLVE, 1, "field_resolve");
native_field_constructor!(native_field_commit, RB_COMMIT, 1, "field_commit");
native_field_constructor!(native_field_step, RB_STEP, 1, "field_step");
native_field_constructor!(native_field_lift, RB_LIFT, 1, "field_lift");
native_field_constructor!(native_field_sample, RB_SAMPLE, 1, "field_sample");
native_field_constructor!(native_field_observe, RB_OBSERVE, 1, "field_observe");
native_field_constructor!(native_field_intervene, RB_INTERVENE, 1, "field_intervene");
native_field_constructor!(native_field_residual, RB_RESIDUAL, 1, "field_residual");
native_field_constructor!(native_field_receipt, RB_RECEIPT, 1, "field_receipt");
native_field_constructor!(native_field_cost, RB_COST, 1, "field_cost");
native_field_constructor!(native_field_consent, RB_CONSENT, 1, "field_consent");
native_field_constructor!(native_field_evidence, RB_EVIDENCE, 1, "field_evidence");

// ---------------------------------------------------------------------------
// Frame — scope primitive
// ---------------------------------------------------------------------------

// Frame — arena-resident scope. Bindings as a small ordered vec; the
// common case (function call with 1-3 args) beats a hash table at this
// size and keeps the data layout cache-friendly.
#[derive(Debug)]
struct Frame {
    parent: Option<FrameId>,
    bindings: Vec<(NameID, Value)>,
}

// ---------------------------------------------------------------------------
// Native functions — what Form-on-top reaches for at the leaves
// ---------------------------------------------------------------------------

impl Kernel {
    fn register_env_native(&mut self, name: &str, category: NodeID, f: EnvAwareNativeFn) {
        let id = self.intern_string(name).inst;
        self.env_natives.insert(
            id,
            EnvAwareNativeEntry {
                name: id,
                category,
                func: f,
            },
        );
    }

    fn register_native(&mut self, name: &str, category: NodeID, f: NativeFn) {
        let id = self.intern_string(name).inst;
        self.natives.insert(
            id,
            NativeEntry {
                name: id,
                category,
                func: f,
            },
        );
    }

    fn register_natives(&mut self) {
        // Blueprint attribution discipline:
        //   cat_call()      — invoke external effect (I/O, tool)
        //   cat_access()    — read a property / field (length, index, byte)
        //   cat_method()    — transform on a cell-like value (string build, format)
        //   cat_compare()   — equality / ordering
        //   cat_list_nat()  — construct or destructure a List
        //   cat_witness()   — substrate self-attestation (intern, walk, lookup)
        //   cat_undefined() — honest "no Form category settled yet"
        //
        // The category rides on each NativeEntry; the walker records it in
        // the trace when the native fires. The kernel knows itself from
        // inside, not only at its Form surface.

        self.register_native("print", cat_call(), |_, _, args| {
            for (i, a) in args.iter().enumerate() {
                if i > 0 {
                    print!(" ");
                }
                print!("{}", a.display());
            }
            println!();
            Value::Null
        });
        self.register_native("str_len", cat_access(), |_, _, args| {
            Value::Int(args[0].as_str().len() as i64)
        });
        self.register_native("substring", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let a_i = args[1].as_int();
            let b_i = args[2].as_int();
            if a_i < 0 || b_i < a_i || b_i as usize > s.len() {
                panic!(
                    "substring: bounds out of range start={} end={} len={}",
                    a_i,
                    b_i,
                    s.len()
                );
            }
            let a = a_i as usize;
            let b = b_i as usize;
            Value::Str(s[a..b].to_string().into())
        });
        self.register_native("char_at", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let i_i = args[1].as_int();
            if i_i < 0 || i_i as usize >= s.len() {
                panic!("char_at: bounds out of range index={} len={}", i_i, s.len());
            }
            let i = i_i as usize;
            Value::Str((s.as_bytes()[i] as char).to_string().into())
        });
        self.register_native("str_concat", cat_method(), |_, _, args| {
            let mut s = args[0].as_str().to_string();
            s.push_str(args[1].as_str());
            Value::Str(s.into())
        });
        self.register_native("form_error", cat_witness(), |_, _, args| {
            panic!("{}", args[0].as_str())
        });
        self.register_native("form-error", cat_witness(), |_, _, args| {
            panic!("{}", args[0].as_str())
        });
        // value_str — render ANY value as its canonical display string. The
        // companion str_concat needs for building a response document: int_to_str
        // truncates a Float to an int (its `_ => as_int()` arm), and str_concat's
        // as_str() panics on a non-Str. value_str routes through Value::display(),
        // so a Float renders Python-style (format_float: 0.8125, 1.0), an
        // Int as its digits, a List as [a, b], a Bool as true/false. This is the
        // float-correct leaf a JSON-emitting native handler concatenates into the
        // response body (e.g. production-routes.fk's /api/utils handlers). One
        // native, all leaf types — core-abstraction-first.
        self.register_native("value_str", cat_method(), |_, _, args| {
            Value::Str(args[0].display().into())
        });
        self.register_native("value_kind", cat_witness(), |_, _, args| {
            Value::Str(value_kind_name(&args[0]).to_string().into())
        });
        self.register_native("value-kind", cat_witness(), |_, _, args| {
            Value::Str(value_kind_name(&args[0]).to_string().into())
        });
        self.register_native("source_scan_file", cat_call(), |_, _, args| {
            let body = fs::read_to_string(args[0].as_str())
                .unwrap_or_else(|e| panic!("source_scan_file: {}", e));
            let lexicon = source_native_lexicon_from_value(&args[1]);
            source_native_scan_text(&body, &lexicon)
        });
        // pow — integer exponentiation in native code (no Form recursion).
        // (pow base exp) → base**exp. Negative exponents return 0 (Python's
        // int**-n is a float; floats on this path are a later breath).
        self.register_native("pow", cat_method(), |_, _, args| {
            let base = args[0].as_int();
            let exp = args[1].as_int();
            if exp < 0 {
                Value::Int(0)
            } else {
                Value::Int(base.pow(exp as u32))
            }
        });
        // --- struct/object primitive (BML reference, rung 2) ----------------
        // A Record is the kernel's first MUTABLE value: a struct/object with
        // identity. Every language's class/struct compiles onto these four
        // natives. The blueprint NodeID tags the record's type (its class /
        // method-table); fields are a name→value map.
        //
        // record_new — (record_new blueprint k1 v1 k2 v2 ...) → Record.
        // The first arg is the blueprint NodeID; the rest are alternating
        // field-name (string) and value pairs. Field names intern to NameIDs.
        self.register_native("record_new", cat_method(), |k, _, args| {
            let blueprint = args[0].as_nid();
            let mut fields: Vec<(NameID, Value)> = Vec::new();
            let mut i = 1;
            while i + 1 < args.len() {
                let name = k.intern_string(args[i].as_str()).inst;
                fields.push((name, args[i + 1].clone()));
                i += 2;
            }
            Value::Record(Arc::new(Mutex::new(Record { blueprint, fields })))
        });
        // record_get — (record_get rec "field") → value, or null if absent.
        self.register_native("record_get", cat_access(), |k, _, args| {
            let name = k.intern_string(args[1].as_str()).inst;
            match &args[0] {
                Value::Record(r) => r.lock().unwrap().get(name).unwrap_or(Value::Null),
                _ => panic!("record_get: not a record: {:?}", args[0]),
            }
        });
        // record_set — (record_set rec "field" value) → the record (mutated
        // in place; shared identity means all holders see the change). This is
        // the kernel's first in-place mutation — BML's `self.x = v`.
        self.register_native("record_set", cat_method(), |k, _, args| {
            let name = k.intern_string(args[1].as_str()).inst;
            match &args[0] {
                Value::Record(r) => {
                    r.lock().unwrap().set(name, args[2].clone());
                    args[0].clone()
                }
                _ => panic!("record_set: not a record: {:?}", args[0]),
            }
        });
        // record_has — (record_has rec "field") → bool.
        self.register_native("record_has", cat_access(), |k, _, args| {
            let name = k.intern_string(args[1].as_str()).inst;
            match &args[0] {
                Value::Record(r) => Value::Bool(r.lock().unwrap().get(name).is_some()),
                _ => Value::Bool(false),
            }
        });
        // record_blueprint — (record_blueprint rec) → the blueprint NodeID
        // (the record's class/type tag, for method dispatch by the lifter).
        self.register_native("record_blueprint", cat_access(), |_, _, args| {
            match &args[0] {
                Value::Record(r) => Value::Nid(r.lock().unwrap().blueprint),
                _ => panic!("record_blueprint: not a record: {:?}", args[0]),
            }
        });
        // record? — (record? v) → bool. Type predicate so Form code can branch.
        self.register_native("record?", cat_access(), |_, _, args| {
            Value::Bool(matches!(&args[0], Value::Record(_)))
        });
        // record_keys — (record_keys rec) → list of field-name strings, in
        // insertion order. Lets Form enumerate a record used as a hash map
        // (e.g. cell-log-store.fk's keydir for compaction).
        self.register_native("record_keys", cat_access(), |k, _, args| match &args[0] {
            Value::Record(r) => {
                let names: Vec<NameID> = r.lock().unwrap().fields.iter().map(|(n, _)| *n).collect();
                Value::List(Arc::new(
                    names
                        .into_iter()
                        .map(|n| Value::Str(k.strs[n as usize].clone().into()))
                        .collect(),
                ))
            }
            _ => Value::List(Vec::new().into()),
        });
        // --- methods on the blueprint (BML/NUMS reference, rung 2b) ---------
        // Methods live on the blueprint/type, not on instances — shared by all
        // records of that type, name-dispatched. The keystone that makes a
        // Record a real object: obj.m(args) works.
        //
        // method_define — (method_define blueprint "name" closure) → blueprint.
        // Registers the closure under (blueprint, name) in the method table.
        self.register_native("method_define", cat_method(), |k, _, args| {
            let blueprint = args[0].as_nid();
            let name = k.intern_string(args[1].as_str()).inst;
            let cl = match &args[2] {
                Value::Closure(c) => c.clone(),
                _ => panic!("method_define: third arg must be a closure"),
            };
            k.methods.insert((blueprint, name), cl);
            args[0].clone()
        });
        // method_has — (method_has record-or-blueprint "name") → bool. Accepts
        // either a record (uses its blueprint) or a blueprint NodeID directly.
        self.register_native("method_has", cat_access(), |k, _, args| {
            let blueprint = match &args[0] {
                Value::Record(r) => r.lock().unwrap().blueprint,
                Value::Nid(n) => *n,
                _ => return Value::Bool(false),
            };
            let name = k.intern_string(args[1].as_str()).inst;
            Value::Bool(k.methods.contains_key(&(blueprint, name)))
        });
        // method_invoke — (method_invoke record "name" arg1 arg2 ...) → value.
        // Dispatches by the record's blueprint, binds `self` = record (the
        // structural+behavioral base; dual-base separation is rung 2d), binds
        // the method's declared params to the remaining args, walks the body
        // in a frame extending the method closure's captured env.
        self.register_native("method_invoke", cat_method(), |k, a, args| {
            let rec = match &args[0] {
                Value::Record(r) => r.clone(),
                _ => panic!("method_invoke: first arg must be a record"),
            };
            let blueprint = rec.lock().unwrap().blueprint;
            let name_id = k.intern_string(args[1].as_str()).inst;
            let cl = k
                .methods
                .get(&(blueprint, name_id))
                .unwrap_or_else(|| {
                    panic!(
                        "method_invoke: no method '{}' on blueprint @{}.{}.{}.{}",
                        args[1].as_str(),
                        blueprint.pkg,
                        blueprint.level,
                        blueprint.ty,
                        blueprint.inst
                    )
                })
                .clone();
            // The method's FIRST param is the receiver (Python `self`
            // convention); the remaining params bind to the call args
            // (args[2..]). So a `def get(self)` method is invoked with zero
            // call args, and the receiver fills param 0.
            let call_args = &args[2..];
            if cl.params.is_empty() {
                panic!(
                    "method '{}' must declare a receiver param (self)",
                    args[1].as_str()
                );
            }
            if call_args.len() != cl.params.len() - 1 {
                panic!(
                    "method '{}' wants {} args, got {}",
                    args[1].as_str(),
                    cl.params.len() - 1,
                    call_args.len()
                );
            }
            let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            // param 0 = receiver; params 1.. = the call args in order.
            a.bind(call_frame, cl.params[0], Value::Record(rec.clone()));
            for (i, p) in cl.params[1..].iter().enumerate() {
                a.bind(call_frame, *p, call_args[i].clone());
            }
            walk(k, a, cl.body, call_frame)
        });
        // str_find — Rust-level substring search starting at index `from`.
        // (str_find s needle from) → int (index or -1). Whole search in
        // this Rust loop; no Form callback per byte, no Form recursion.
        self.register_native("str_find", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let needle = args[1].as_str();
            let from_i = args[2].as_int();
            let from = if from_i < 0 { 0 } else { from_i as usize };
            if from > s.len() {
                return Value::Int(-1);
            }
            match s[from..].find(needle) {
                Some(i) => Value::Int((from + i) as i64),
                None => Value::Int(-1),
            }
        });
        // scan_run — return the end-index where a contiguous run of bytes
        // matching `class_code` ends (exclusive). Sibling parity with Go +
        // TS scan_run. Generic per-byte loop in Rust avoids the walker
        // dispatch a pure-Form recursion would pay per character.
        // Class codes: 0=ws, 1=digit, 2=alpha, 3=identifier-char,
        //              4=non-quote-non-escape, 5=non-newline,
        //              6=json-string-safe (byte >= 0x20, not quote/backslash).
        self.register_native("scan_run", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            let from = args[1].as_int().max(0) as usize;
            let class = args[2].as_int();
            let bytes = s.as_bytes();
            let n = bytes.len();
            let mut end = from.min(n);
            match class {
                0 => {
                    while end < n && matches!(bytes[end], b' ' | b'\t' | b'\n' | b'\r') {
                        end += 1;
                    }
                }
                1 => {
                    while end < n && bytes[end].is_ascii_digit() {
                        end += 1;
                    }
                }
                2 => {
                    while end < n && bytes[end].is_ascii_alphabetic() {
                        end += 1;
                    }
                }
                3 => {
                    while end < n
                        && (bytes[end].is_ascii_alphanumeric()
                            || bytes[end] == b'_'
                            || bytes[end] == b'-')
                    {
                        end += 1;
                    }
                }
                4 => {
                    while end < n && bytes[end] != b'"' && bytes[end] != b'\\' {
                        end += 1;
                    }
                }
                5 => {
                    while end < n && bytes[end] != b'\n' {
                        end += 1;
                    }
                }
                6 => {
                    while end < n && bytes[end] >= 0x20 && bytes[end] != b'"' && bytes[end] != b'\\'
                    {
                        end += 1;
                    }
                }
                _ => panic!("scan_run: unknown class_code {} (valid: 0-6)", class),
            }
            Value::Int(end as i64)
        });
        // string_fold — Rust-level streaming iteration over a string's bytes.
        // Signature: (string_fold s init step) where step is a closure of
        // (acc, char) → acc. Whole iteration in this Rust for-loop; no Form-
        // level recursion. Lets the substrate process arbitrary-length input
        // streams without piling kernel stack frames.
        self.register_native("string_fold", cat_call(), |k, a, args| {
            let s = args[0].as_str().to_string();
            let mut acc = args[1].clone();
            let cl = match &args[2] {
                Value::Closure(c) => c.clone(),
                _ => panic!("string_fold: third arg must be a closure"),
            };
            if cl.params.len() != 2 {
                panic!(
                    "string_fold: step closure wants 2 params (acc char), got {}",
                    cl.params.len()
                );
            }
            for byte in s.as_bytes().to_vec() {
                let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
                a.bind(call_frame, cl.params[0], acc);
                a.bind(
                    call_frame,
                    cl.params[1],
                    Value::Str((byte as char).to_string().into()),
                );
                acc = walk(k, a, cl.body, call_frame);
            }
            acc
        });
        self.register_native("str_eq", cat_compare(RCMP_EQ), |_, _, args| {
            bool_int(args[0].as_str() == args[1].as_str())
        });
        // int_to_str — value-to-string for trivial leaves. Historical name
        // (first use: line numbers in cell-trace.fk); semantics is "render
        // any trivial value as text" so emit-engine.fk's leaf walker can
        // pass node_value of any leaf type through it. Multi-target emit
        // (universal codec lattice — emit.fk + emits/json.fk) depends on
        // string + bool + null passthrough.
        self.register_native("int_to_str", cat_method(), |_, _, args| match &args[0] {
            Value::Str(s) => Value::Str(s.clone()),
            Value::Bool(b) => Value::Str(if *b {
                "true".to_string().into()
            } else {
                "false".to_string().into()
            }),
            Value::Null => Value::Str("null".to_string().into()),
            Value::Float(f) => Value::Str(format_float(*f).into()),
            _ => Value::Str(args[0].as_int().to_string().into()),
        });
        self.register_native("str_to_int", cat_method(), |_, _, args| {
            Value::Int(args[0].as_str().parse().unwrap_or(0))
        });
        // float_to_int — truncate a float toward zero, exactly Python's int() on a
        // float. The missing leaf between str_to_float and an integer: it lets a
        // native handler replicate int(float(x)) (parse a numeric string that may
        // carry a fraction, then truncate) where str_to_int alone returns 0 on
        // "3.0". Total: a non-number -> 0. Rust `as i64` truncates toward zero for
        // both signs, matching int(3.5)=3 and int(-3.5)=-3.
        self.register_native("float_to_int", cat_method(), |_, _, args| {
            let f = match &args[0] {
                Value::Float(x) => *x,
                Value::Int(i) => *i as f64,
                _ => 0.0,
            };
            Value::Int(f as i64)
        });
        // str_to_float — text-to-float leaf, the float sibling of str_to_int.
        // Total like its sibling (unparseable text -> 0.0), so a handler that
        // splits a comma-separated query arg into float scores never panics on
        // a stray token. This is what lets a native route parse arbitrary
        // float inputs from the request (e.g. weighted_average's values/weights)
        // and run the real arithmetic in Form, rather than serving a constant.
        self.register_native("str_to_float", cat_method(), |_, _, args| {
            Value::Float(args[0].as_str().parse().unwrap_or(0.0))
        });
        self.register_native("ord", cat_access(), |_, _, args| {
            let s = args[0].as_str();
            if s.is_empty() {
                Value::Int(-1)
            } else {
                Value::Int(s.as_bytes()[0] as i64)
            }
        });
        self.register_native("byte_to_str", cat_access(), |_, _, args| {
            let b = args[0].as_int();
            if !(0..=255).contains(&b) {
                Value::Str(String::new().into())
            } else {
                Value::Str((b as u8 as char).to_string().into())
            }
        });
        self.register_native("list", cat_list_nat(), |_, _, args| {
            Value::List(args.to_vec().into())
        });
        self.register_native("cons", cat_list_nat(), |_, _, args| {
            let mut out = vec![args[0].clone()];
            if let Value::List(rest) = &args[1] {
                out.extend(rest.iter().cloned());
            }
            Value::List(out.into())
        });
        self.register_native("head", cat_list_nat(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                xs.first().cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            }
        });
        self.register_native("tail", cat_list_nat(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                Value::List(if xs.is_empty() {
                    vec![].into()
                } else {
                    xs[1..].to_vec().into()
                })
            } else {
                Value::Null
            }
        });
        self.register_native("len", cat_access(), |_, _, args| match &args[0] {
            Value::List(xs) => {
                // Dict-aware: tagged "__dict__" lists report pair count,
                // matching Python's `len(d)` semantics.
                if let Some(Value::Str(s)) = xs.first() {
                    if **s == *"__dict__" {
                        return Value::Int(((xs.len() - 1) / 2) as i64);
                    }
                }
                Value::Int(xs.len() as i64)
            }
            Value::Str(s) => Value::Int(s.len() as i64),
            _ => Value::Int(0),
        });
        // nth — list subscript by integer index. Sibling-parity with the
        // TS kernel; the Python emitter generates `(nth xs i)` for
        // `xs[i]`. `core.fk` has a recursive version that could replace
        // this once auto-prelude loading lands; keeping it native today
        // is what closes the parity-suite assign/imperative/substrate
        // demos against the live binary.
        self.register_native("nth", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                let i = args[1].as_int();
                if i < 0 || (i as usize) >= xs.len() {
                    return Value::Null;
                }
                return xs[i as usize].clone();
            }
            Value::Null
        });
        self.register_native("empty", cat_list_nat(), |_, _, _| {
            Value::List(vec![].into())
        });
        // _list_append — functional list extension: `(_list_append xs x)` →
        // a NEW list = xs ++ [x]. The Python adapter lowers the accumulator
        // idiom `result.append(x)` to `(let result (_list_append result x))`,
        // rebinding the name to the grown list each pass (Python mutates in
        // place; the kernel's list is an immutable value, so the name carries
        // the growth). This is what unblocks the whole class of list-returning
        // routes — softmax, distributions, vectors — without a class-method
        // dispatch on a plain list. A non-list receiver yields a single-element
        // list, matching `[].append(x)` having extended an empty accumulator.
        self.register_native("_list_append", cat_list_nat(), |_, _, args| {
            let mut xs = match &args[0] {
                Value::List(xs) => xs.as_ref().clone(),
                _ => Vec::new(),
            };
            xs.push(args[1].clone());
            Value::List(Arc::new(xs))
        });
        // _get — one polymorphic accessor over every container shape the
        // Python adapter emits. The emitter lowers BOTH attribute reads
        // (`obj.field` → `(_get obj "field")`) and subscripts (`x[i]` /
        // `d[k]` → `(_get x i)`) to the same native, so `_get` must
        // dispatch on the *shape of its receiver*, not on a fixed arity:
        //
        //   • `__dict__`-tagged list + any key  → dict alist lookup
        //   • plain alist (even slots are Str)  → record-field read
        //                                          (Python class instance)
        //   • list + int index                  → positional element
        //   • str  + int index                  → one-char string
        //
        // A single dispatch keeps the .fk identical across siblings and
        // lets a record-as-flat-alist and a positional list both flow
        // through `x[...]` without the emitter knowing the runtime type.
        // (Earlier this was two `register_native("_get", …)` calls; the
        // second silently shadowed the first, so attribute reads on class
        // instances hit the int-index path and panicked on `as_int(Str)`.)
        self.register_native("_get", cat_access(), |k, _, args| {
            // Record: a marshalled structured input (the structure-access
            // capability) or a record built by record_new. A string key reads
            // the named field; record_get returns Null for an absent field
            // (Python `obj[k]` would KeyError, but the transmuted recipes read
            // fields they know exist, and Null is the honest "absent" surface).
            if let (Value::Record(r), Value::Str(key)) = (&args[0], &args[1]) {
                let name = k.intern_string(key).inst;
                return r.lock().unwrap().get(name).unwrap_or(Value::Null);
            }
            // Dict: ["__dict__", k0, v0, …] — key match by value.
            if is_dict(&args[0]) {
                if let Value::List(xs) = &args[0] {
                    let mut i = 1;
                    while i + 1 < xs.len() {
                        if dict_key_eq(&xs[i], &args[1]) {
                            return xs[i + 1].clone();
                        }
                        i += 2;
                    }
                    return Value::Null;
                }
            }
            // String key on an untagged list → record-field read. A class
            // instance is a flat alist (list "__class__" "Counter" "n" 3 …).
            if let (Value::List(xs), Value::Str(key)) = (&args[0], &args[1]) {
                let mut i = 0;
                while i + 1 < xs.len() {
                    if let Value::Str(k) = &xs[i] {
                        if k == key {
                            return xs[i + 1].clone();
                        }
                    }
                    i += 2;
                }
                panic!("_get: no field '{}' on record", key);
            }
            // Int index on a list → positional element.
            if let Value::List(xs) = &args[0] {
                let i = args[1].as_int();
                if i < 0 || (i as usize) >= xs.len() {
                    return Value::Null;
                }
                return xs[i as usize].clone();
            }
            // Int index on a string → one-char string.
            if let Value::Str(s) = &args[0] {
                let i = args[1].as_int();
                if i < 0 || (i as usize) >= s.len() {
                    return Value::Str(String::new().into());
                }
                return Value::Str((s.as_bytes()[i as usize] as char).to_string().into());
            }
            Value::Null
        });
        // _dispatch — method-call entry. The adapter lowers `obj.m(arg, …)`
        // to `(_dispatch obj "m" arg …)`. Reads obj's "__class__" field
        // to find the function bound as `<ClassName>__<methodName>` in
        // the surrounding scope; calls it with obj as the first argument.
        // Env-aware so it can look up the method closure in the caller's
        // frame chain (which is where the lifted method `defn`s landed).
        //
        // Inheritance walk: if `<C>__<m>` is not bound, look up `<C>__base`
        // (a string holding the parent class name); try `<Parent>__<m>`;
        // continue until a method is found or the chain ends. First match
        // wins — single inheritance, MRO is just the linear chain. Walking
        // here keeps every call site honest without the emitter needing to
        // bake the dispatch order into compile-time call shape.
        self.register_env_native("_dispatch", cat_call(), |k, a, env, args| {
            let class_name = if let Value::List(xs) = &args[0] {
                let mut i = 0;
                let mut found: Option<String> = None;
                while i + 1 < xs.len() {
                    if let Value::Str(key) = &xs[i] {
                        if **key == *"__class__" {
                            if let Value::Str(c) = &xs[i + 1] {
                                found = Some(c.to_string());
                            }
                            break;
                        }
                    }
                    i += 2;
                }
                match found {
                    Some(c) => c,
                    None => panic!("_dispatch: receiver record has no '__class__' field"),
                }
            } else {
                panic!("_dispatch: receiver is not a record (got {:?})", args[0]);
            };
            let method_name = match &args[1] {
                Value::Str(s) => s.clone(),
                _ => panic!("_dispatch: second arg must be the method name string"),
            };
            let (qualified, cl) = resolve_method(k, a, env, &class_name, &method_name);
            // Build the call frame: bind self (args[0]) + the remaining
            // method args (args[2..]) to the closure's parameters.
            let call_args: Vec<&Value> =
                std::iter::once(&args[0]).chain(args[2..].iter()).collect();
            if cl.params.len() != call_args.len() {
                panic!(
                    "_dispatch: arity mismatch on {} (expected {}, got {})",
                    qualified,
                    cl.params.len(),
                    call_args.len()
                );
            }
            let frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            for (i, p) in cl.params.iter().enumerate() {
                a.bind(frame, *p, call_args[i].clone());
            }
            walk(k, a, cl.body, frame)
        });
        // --- Dict natives ---------------------------------------------------
        // Dicts are first-class but ride on Value::List with a "__dict__"
        // tag in slot 0, followed by alternating key/value pairs:
        //   ["__dict__", k0, v0, k1, v1, ...]
        // Keeps the dict model uniform with how the existing _plus / nth /
        // subscript path already moves through Value::List, and lets the TS
        // evaluator (which has no separate Dict variant) share the same
        // shape across runtimes. Keys may be strings or ints; equality uses
        // value-level compare (str==str, int==int). Updates are immutable —
        // _dict_set returns a fresh dict so closures over the original keep
        // their view. This is enough surface to write a real endpoint
        // response shape; method-style .update / .pop / .items remain
        // pending (named in PYTHON_PIPELINE_STATUS.md, not blocking #2059
        // dict transmute work).
        fn is_dict(v: &Value) -> bool {
            if let Value::List(xs) = v {
                if let Some(Value::Str(s)) = xs.first() {
                    return **s == *"__dict__";
                }
            }
            false
        }
        fn dict_key_eq(a: &Value, b: &Value) -> bool {
            match (a, b) {
                (Value::Str(x), Value::Str(y)) => x == y,
                (Value::Int(x), Value::Int(y)) => x == y,
                _ => false,
            }
        }
        self.register_native("_dict_new", cat_list_nat(), |_, _, args| {
            // (_dict_new k0 v0 k1 v1 ...) — variadic constructor used by
            // the emitter for dict literals.
            let mut out = vec![Value::Str("__dict__".to_string().into())];
            out.extend(args.iter().cloned());
            Value::List(out.into())
        });
        self.register_native("_dict_get", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if **tag == *"__dict__" {
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            if dict_key_eq(&xs[i], &args[1]) {
                                return xs[i + 1].clone();
                            }
                            i += 2;
                        }
                        return Value::Null;
                    }
                }
            }
            Value::Null
        });
        self.register_native("_dict_set", cat_method(), |_, _, args| {
            // Immutable update — return a new dict; existing references unchanged.
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if **tag == *"__dict__" {
                        let mut out = xs.as_ref().clone();
                        let mut i = 1;
                        while i + 1 < out.len() {
                            if dict_key_eq(&out[i], &args[1]) {
                                out[i + 1] = args[2].clone();
                                return Value::List(Arc::new(out));
                            }
                            i += 2;
                        }
                        out.push(args[1].clone());
                        out.push(args[2].clone());
                        return Value::List(Arc::new(out));
                    }
                }
            }
            args[0].clone()
        });
        self.register_native("_dict_has", cat_compare(RCMP_EQ), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if **tag == *"__dict__" {
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            if dict_key_eq(&xs[i], &args[1]) {
                                return Value::Bool(true);
                            }
                            i += 2;
                        }
                    }
                }
            }
            Value::Bool(false)
        });
        self.register_native("_dict_keys", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if **tag == *"__dict__" {
                        let mut out = Vec::new();
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            out.push(xs[i].clone());
                            i += 2;
                        }
                        return Value::List(out.into());
                    }
                }
            }
            Value::List(vec![].into())
        });
        self.register_native("_dict_values", cat_access(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if let Some(Value::Str(tag)) = xs.first() {
                    if **tag == *"__dict__" {
                        let mut out = Vec::new();
                        let mut i = 1;
                        while i + 1 < xs.len() {
                            out.push(xs[i + 1].clone());
                            i += 2;
                        }
                        return Value::List(out.into());
                    }
                }
            }
            Value::List(vec![].into())
        });
        // (The subscript path is folded into the single polymorphic `_get`
        // registered above — dict/record/list/str all dispatch on receiver
        // shape there. A second `register_native("_get", …)` here would
        // silently shadow it, so the subscript-only version was removed.)
        // _iter — turn any container into a flat list suitable for the
        // for-loop emitter's head/tail walk. Lists pass through; dicts
        // become their keys (Python's `for k in d:`); strings become
        // one-character strings per byte.
        self.register_native("_iter", cat_list_nat(), |_, _, args| {
            if is_dict(&args[0]) {
                if let Value::List(xs) = &args[0] {
                    let mut out = Vec::new();
                    let mut i = 1;
                    while i + 1 < xs.len() {
                        out.push(xs[i].clone());
                        i += 2;
                    }
                    return Value::List(out.into());
                }
            }
            if let Value::List(_) = &args[0] {
                return args[0].clone();
            }
            if let Value::Str(s) = &args[0] {
                return Value::List(Arc::new(
                    s.as_bytes()
                        .iter()
                        .map(|b| Value::Str((*b as char).to_string().into()))
                        .collect(),
                ));
            }
            Value::List(vec![].into())
        });
        // _in — polymorphic membership. (`k in d` → _in d k). For dicts
        // checks keys; for lists checks elements; for strings checks
        // substring presence.
        self.register_native("_in", cat_compare(RCMP_EQ), |_, _, args| {
            if is_dict(&args[1]) {
                if let Value::List(xs) = &args[1] {
                    let mut i = 1;
                    while i + 1 < xs.len() {
                        if dict_key_eq(&xs[i], &args[0]) {
                            return Value::Bool(true);
                        }
                        i += 2;
                    }
                    return Value::Bool(false);
                }
            }
            if let Value::List(xs) = &args[1] {
                for v in xs.iter() {
                    match (&args[0], v) {
                        (Value::Int(a), Value::Int(b)) if *a == *b => return Value::Bool(true),
                        (Value::Str(a), Value::Str(b)) if *a == *b => return Value::Bool(true),
                        (Value::Float(a), Value::Float(b)) if *a == *b => return Value::Bool(true),
                        (Value::Bool(a), Value::Bool(b)) if *a == *b => return Value::Bool(true),
                        _ => {}
                    }
                }
                return Value::Bool(false);
            }
            if let (Value::Str(needle), Value::Str(hay)) = (&args[0], &args[1]) {
                return Value::Bool(hay.contains(&needle[..]));
            }
            Value::Bool(false)
        });
        // _dispatch_super — super().<m>(args) entry. Adapter lowers
        // `super().m(args…)` inside a method of class C to
        // `(_dispatch_super self "C" "m" args…)`. We look up `C__base`
        // (a string holding the parent class name) and resolve `m`
        // starting at the parent — the inheritance walk continues from
        // there. Skipping the receiver's `__class__` is what makes super
        // different from a normal dispatch: a Dog calling
        // `super().speak()` always resolves to Animal.speak (or
        // Animal's chain), even though self.__class__ is "Dog".
        self.register_env_native("_dispatch_super", cat_call(), |k, a, env, args| {
            let class_name = match &args[1] {
                Value::Str(s) => s.clone(),
                _ => panic!("_dispatch_super: second arg must be the class name string"),
            };
            let method_name = match &args[2] {
                Value::Str(s) => s.clone(),
                _ => panic!("_dispatch_super: third arg must be the method name string"),
            };
            // Look up <ClassName>__base to find the parent class name.
            let base_key = format!("{}__base", class_name);
            let base_id = match k.str_idx.get(&base_key).copied() {
                Some(id) => id,
                None => panic!(
                    "_dispatch_super: no '{}' in scope — '{}' has no base class",
                    base_key, class_name
                ),
            };
            let parent_val = match a.lookup(env, base_id) {
                Some(v) => v,
                None => panic!(
                    "_dispatch_super: '{}' not bound — '{}' has no base class",
                    base_key, class_name
                ),
            };
            let parent_name = match parent_val {
                Value::Str(s) => s,
                _ => panic!("_dispatch_super: '{}' is not a string", base_key),
            };
            if parent_name.is_empty() {
                panic!(
                    "_dispatch_super: class '{}' has no base class (empty __base)",
                    class_name
                );
            }
            let (qualified, cl) = resolve_method(k, a, env, &parent_name, &method_name);
            // First arg is self (args[0]); method args follow at args[3..].
            let call_args: Vec<&Value> =
                std::iter::once(&args[0]).chain(args[3..].iter()).collect();
            if cl.params.len() != call_args.len() {
                panic!(
                    "_dispatch_super: arity mismatch on {} (expected {}, got {})",
                    qualified,
                    cl.params.len(),
                    call_args.len()
                );
            }
            let frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
            for (i, p) in cl.params.iter().enumerate() {
                a.bind(frame, *p, call_args[i].clone());
            }
            walk(k, a, cl.body, frame)
        });
        // _merge_record — child constructors that chain through
        // `super().__init__(args)` call the parent constructor (which
        // returns a full record tagged with `__class__/__base__`), then
        // merge the parent's data fields into the child's record. This
        // native strips `__class__/__base__` from the parent record and
        // appends the remaining (key, value) pairs to the child record.
        // The child's `__class__/__base__` stays (the receiver's
        // dispatch identity is the child, not the parent).
        //
        // Shape:
        //   (_merge_record <child-record> <parent-record>)
        // Returns: a new list with child's full prefix + parent's data fields.
        self.register_native("_merge_record", cat_access(), |_, _, args| {
            let child = match &args[0] {
                Value::List(xs) => xs.as_ref().clone(),
                _ => panic!("_merge_record: first arg must be a record"),
            };
            let parent = match &args[1] {
                Value::List(xs) => xs,
                _ => panic!("_merge_record: second arg must be a record"),
            };
            let mut out = child;
            let mut i = 0;
            while i + 1 < parent.len() {
                if let Value::Str(key) = &parent[i] {
                    if **key == *"__class__" || **key == *"__base__" {
                        i += 2;
                        continue;
                    }
                    // Skip if the child already has this field — child wins.
                    let mut child_has = false;
                    let mut j = 0;
                    while j + 1 < out.len() {
                        if let Value::Str(k2) = &out[j] {
                            if k2 == key {
                                child_has = true;
                                break;
                            }
                        }
                        j += 2;
                    }
                    if !child_has {
                        out.push(parent[i].clone());
                        out.push(parent[i + 1].clone());
                    }
                }
                i += 2;
            }
            Value::List(Arc::new(out))
        });
        // --- Substrate read primitives — kernel reaches the REST surface ----
        // The body's substrate lives behind /api/substrate/*. Until now the
        // kernel could compute over data it was handed but could not pull
        // its own data from the lattice. http_get + _json_get + _json_to_dict
        // are the smallest closing breath that lets a .fk recipe stand up
        // a `?lattice` or `?cell` query end-to-end without a Python shim.
        //
        // Why three minimal natives and not a fat client: the substrate's
        // REST surface is already designed for outside callers (Pydantic
        // response models, content-type JSON). The kernel just needs to
        // speak HTTP + JSON well enough to consume those responses; the
        // structural reasoning still happens in Form code over the dict
        // values that come back.
        //
        // http_get(url, headers?, timeout_ms?) → dict. This matches the Go
        // carrier shape used by the BML front-door catalog: status_code, body,
        // error, duration_ms, headers. Form owns response interpretation.
        self.register_native("http_get", cat_call(), |_, _, args| {
            let url = args[0].as_str();
            let headers = form_http_headers(args.get(1));
            let timeout = form_http_timeout(args.get(2), Duration::from_secs(10));
            external_http_get_value(url, headers, timeout)
        });
        // _json_get(json_str, key) → str|int|float|bool|null. Parse a top-level
        // JSON object and extract `obj[key]`. Returns null when key is missing
        // or the JSON is malformed — same shape http_get uses, so Form code can
        // chain (let body (http_get url)) (let n (_json_get body "key")).
        // Only top-level keys; nested traversal lives in Form code via repeated
        // _json_get on the sub-string.
        self.register_native("_json_get", cat_access(), |_, _, args| {
            let body = args[0].as_str();
            let key = args[1].as_str();
            let parsed: serde_json::Value = match serde_json::from_str(body) {
                Ok(v) => v,
                Err(_) => return Value::Null,
            };
            let val = match parsed.get(key) {
                Some(v) => v,
                None => return Value::Null,
            };
            match val {
                serde_json::Value::Null => Value::Null,
                serde_json::Value::Bool(b) => Value::Bool(*b),
                serde_json::Value::Number(n) => {
                    if let Some(i) = n.as_i64() {
                        Value::Int(i)
                    } else if let Some(f) = n.as_f64() {
                        Value::Float(f)
                    } else {
                        Value::Null
                    }
                }
                serde_json::Value::String(s) => Value::Str(s.clone().into()),
                // For arrays/objects, return the re-serialized JSON string
                // so Form code can re-parse with another _json_get call.
                // Keeps the native surface flat (no recursive Value structure
                // beyond what the kernel already has) and matches the way
                // jq pipelines compose at the shell.
                _ => Value::Str(val.to_string().into()),
            }
        });
        // _json_to_dict(json_str) → __dict__-tagged list (the kernel's dict
        // shape). Convenience for the common case where the response is a
        // small flat object — e.g. /api/substrate/lattice/stats returns
        // {blueprints_total, recipes_total, cells_total} and the calling
        // Form code wants to address it like a dict.
        // Only top-level keys; nested objects/arrays come back as JSON
        // string values (consistent with _json_get).
        self.register_native("_json_to_dict", cat_method(), |_, _, args| {
            let body = args[0].as_str();
            let parsed: serde_json::Value = match serde_json::from_str(body) {
                Ok(v) => v,
                Err(_) => return Value::Null,
            };
            let obj = match parsed.as_object() {
                Some(o) => o,
                None => return Value::Null,
            };
            let mut out = vec![Value::Str("__dict__".to_string().into())];
            for (k, v) in obj {
                out.push(Value::Str(k.clone().into()));
                out.push(match v {
                    serde_json::Value::Null => Value::Null,
                    serde_json::Value::Bool(b) => Value::Bool(*b),
                    serde_json::Value::Number(n) => {
                        if let Some(i) = n.as_i64() {
                            Value::Int(i)
                        } else if let Some(f) = n.as_f64() {
                            Value::Float(f)
                        } else {
                            Value::Null
                        }
                    }
                    serde_json::Value::String(s) => Value::Str(s.clone().into()),
                    _ => Value::Str(v.to_string().into()),
                });
            }
            Value::List(out.into())
        });
        // min / max / sum — common Python builtins applied to a list.
        // sum returns the integer sum; min/max return the smallest/largest
        // int element. All three handle empty lists honestly (sum=0,
        // min/max panic with a clear message matching CPython's TypeError).
        self.register_native("min", cat_method(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if xs.is_empty() {
                    panic!("min: empty list");
                }
                let mut best = xs[0].as_int();
                for v in &xs[1..] {
                    let x = v.as_int();
                    if x < best {
                        best = x;
                    }
                }
                return Value::Int(best);
            }
            Value::Int(args[0].as_int())
        });
        self.register_native("max", cat_method(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                if xs.is_empty() {
                    panic!("max: empty list");
                }
                let mut best = xs[0].as_int();
                for v in &xs[1..] {
                    let x = v.as_int();
                    if x > best {
                        best = x;
                    }
                }
                return Value::Int(best);
            }
            Value::Int(args[0].as_int())
        });
        // sum — integer (or float-aware) total of a list. Sibling-parity
        // with the TS kernel. The earlier compost note pointed at core.fk's
        // `(defn sum (xs) (foldl plus 0 xs))`, but core.fk is not in the
        // bootstrap load path today; restoring the native is what keeps
        // the parity gate honest until auto-prelude lands.
        self.register_native("sum", cat_method(), |_, _, args| {
            if let Value::List(xs) = &args[0] {
                // If any element is a float, promote the running total
                // to float — matches Python's behaviour for sum([1, 2.5]).
                let any_float = xs.iter().any(|v| matches!(v, Value::Float(_)));
                if any_float {
                    let mut total = 0.0f64;
                    for v in xs.iter() {
                        total += v.as_float();
                    }
                    return Value::Float(total);
                }
                let mut total: i64 = 0;
                for v in xs.iter() {
                    total += v.as_int();
                }
                return Value::Int(total);
            }
            Value::Int(0)
        });
        self.register_native("abs", cat_method(), |_, _, args| match &args[0] {
            Value::Float(f) => Value::Float(f.abs()),
            _ => {
                let n = args[0].as_int();
                Value::Int(if n < 0 { -n } else { n })
            }
        });
        // float→int conversions: the bridge between float compute and integer
        // band verdicts / quantization codes. floor/ceil/trunc are IEEE-unambiguous
        // (agree three-way); round is half-AWAY-from-zero (matches Go math.Round;
        // TS uses sign*round(abs) because JS Math.round rounds half toward +Inf).
        // An int argument passes through unchanged.
        self.register_native("floor", cat_method(), |_, _, args| match &args[0] {
            Value::Float(f) => Value::Int(f.floor() as i64),
            _ => Value::Int(args[0].as_int()),
        });
        self.register_native("ceil", cat_method(), |_, _, args| match &args[0] {
            Value::Float(f) => Value::Int(f.ceil() as i64),
            _ => Value::Int(args[0].as_int()),
        });
        self.register_native("trunc", cat_method(), |_, _, args| match &args[0] {
            Value::Float(f) => Value::Int(f.trunc() as i64),
            _ => Value::Int(args[0].as_int()),
        });
        self.register_native("round", cat_method(), |_, _, args| match &args[0] {
            Value::Float(f) => Value::Int(f.round() as i64),
            _ => Value::Int(args[0].as_int()),
        });
        // Polymorphic `+` for Python compilation: int+int→add,
        // str+str→concat, list+list→concat. The compile-time emitter
        // can't always determine operand types (variables, function
        // returns); _plus dispatches at runtime instead.
        self.register_native("_plus", cat_method(), |_, _, args| {
            match (&args[0], &args[1]) {
                (Value::Int(a), Value::Int(b)) => Value::Int(a + b),
                // Float promotion — matches Python: int+float→float,
                // float+int→float, float+float→float.
                (Value::Float(a), Value::Float(b)) => Value::Float(a + b),
                (Value::Int(a), Value::Float(b)) => Value::Float(*a as f64 + b),
                (Value::Float(a), Value::Int(b)) => Value::Float(a + *b as f64),
                (Value::Str(a), Value::Str(b)) => {
                    let mut s = a.to_string();
                    s.push_str(b);
                    Value::Str(s.into())
                }
                (Value::Str(a), Value::Int(b)) => {
                    let mut s = a.to_string();
                    s.push_str(&b.to_string());
                    Value::Str(s.into())
                }
                (Value::Int(a), Value::Str(b)) => {
                    let mut s = a.to_string();
                    s.push_str(b);
                    Value::Str(s.into())
                }
                (Value::Str(a), Value::Float(b)) => {
                    let mut s = a.to_string();
                    s.push_str(&format_float(*b));
                    Value::Str(s.into())
                }
                (Value::Float(a), Value::Str(b)) => {
                    let mut s = format_float(*a);
                    s.push_str(b);
                    Value::Str(s.into())
                }
                (Value::List(a), Value::List(b)) => {
                    let mut out = a.as_ref().clone();
                    out.extend(b.iter().cloned());
                    Value::List(Arc::new(out))
                }
                _ => panic!("_plus: unsupported operand types"),
            }
        });
        // range(n)        → [0, 1, ..., n-1]
        // range(a, b)     → [a, a+1, ..., b-1]
        // range(a, b, s)  → [a, a+s, a+2s, ..., < b] (or > b for negative step)
        // Opens `for i in range(N):` end-to-end through the kernel —
        // the most common Python loop idiom. Same semantics as CPython's
        // range builtin (returning an eager list rather than a lazy
        // iterator, which the kernel doesn't yet have iterators for).
        // Sibling-parity with TS kernel; the earlier compost note pointed
        // at core.fk's recursive (start, end) variant, but core.fk isn't
        // bootstrap-loaded today, so keeping range native is what keeps
        // python_range_demo running end-to-end against the native binary.
        self.register_native("range", cat_list_nat(), |_, _, args| {
            let (start, stop, step) = match args.len() {
                1 => (0i64, args[0].as_int(), 1i64),
                2 => (args[0].as_int(), args[1].as_int(), 1i64),
                _ => (args[0].as_int(), args[1].as_int(), args[2].as_int()),
            };
            let mut out: Vec<Value> = Vec::new();
            if step == 0 {
                return Value::List(out.into());
            }
            if step > 0 {
                let mut i = start;
                while i < stop {
                    out.push(Value::Int(i));
                    i += step;
                }
            } else {
                let mut i = start;
                while i > stop {
                    out.push(Value::Int(i));
                    i += step;
                }
            }
            Value::List(out.into())
        });
        // ── Python `math` module — a tight kernel-native shape ─────
        // The Python adapter rewrites `math.sqrt(x)` → `(math_sqrt x)`,
        // `math.pi` → `(math_pi)`, etc. at parse time, so imports
        // compile to nothing at runtime. Sibling-parity with the TS
        // kernel; the entries are tight (sqrt, pi, floor, ceil, pow) —
        // demonstrably useful for substrate code without enlarging the
        // bootstrap surface. Each entry returns the same shape CPython
        // produces so the parity gate's string compare stays honest:
        // sqrt/pi/pow → Float; floor/ceil → Int (CPython 3 behaviour).
        self.register_native("math_sqrt", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().sqrt())
        });
        self.register_native("math_pi", cat_method(), |_, _, _args| {
            Value::Float(std::f64::consts::PI)
        });
        self.register_native("math_floor", cat_method(), |_, _, args| {
            Value::Int(args[0].as_float().floor() as i64)
        });
        self.register_native("math_ceil", cat_method(), |_, _, args| {
            Value::Int(args[0].as_float().ceil() as i64)
        });
        self.register_native("math_pow", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().powf(args[1].as_float()))
        });
        self.register_native("math_log", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().ln())
        });
        self.register_native("math_exp", cat_method(), |_, _, args| {
            Value::Float(args[0].as_float().exp())
        });
        // round_ndigits(x, n) — CPython `round(x, n)` for floats, EXACTLY.
        // The Python adapter lowers `round(x, n)` → `(round_ndigits x n)`.
        // Rounds the exact decimal value of the double half-to-even at n
        // fractional places (n >= 0), matching CPython bit-for-bit. Sibling-
        // parity with the Go + TS kernels. See round_ndigits_decimal above.
        self.register_native("round_ndigits", cat_method(), |_, _, args| {
            Value::Float(round_ndigits_decimal(args[0].as_float(), args[1].as_int()))
        });
        // ── Python `typing` module — opaque sentinels ─────────────────
        // Every typing import (List, Optional, Dict, Tuple, Any, Callable,
        // Union, Iterable, Iterator, Mapping, Sequence, Set, FrozenSet)
        // binds to this one native. Type annotations are parse-and-ignored
        // at compile time, so this never fires in real code; its existence
        // makes the `from typing import …` binding round-trip honest. Any
        // accidental runtime reference returns the same opaque string
        // across CPython, TS eval, and Rust kernel.
        self.register_native("typing_opaque", cat_method(), |_, _, _args| {
            Value::Str("<typing>".to_string().into())
        });
        self.register_native(
            "read_file",
            cat_call(),
            |_, _, args| match fs::read_to_string(args[0].as_str()) {
                Ok(s) => Value::Str(s.into()),
                Err(_) => Value::Null,
            },
        );
        // Byte-level host file read — returns a list of ints (0-255), one per byte.
        self.register_native("read_file_bytes", cat_call(), |_, _, args| {
            match fs::read(args[0].as_str()) {
                Ok(bytes) => Value::List(Arc::new(
                    bytes.into_iter().map(|b| Value::Int(b as i64)).collect(),
                )),
                Err(_) => Value::Null,
            }
        });
        // source_inventory(root, suffix, skip-dir-names) — generic source
        // inventory primitive. Returns rows of [relative-path, line-count].
        // Form owns classification and aggregation; the kernel only exposes
        // filesystem walking and text line counts as primitive observation.
        self.register_native("source_inventory", cat_call(), |_, _, args| {
            let root = std::path::PathBuf::from(args[0].as_str());
            let suffix = args[1].as_str().to_string();
            let skip = source_inventory_skip_set(&args[2]);
            let root_abs = if root.is_absolute() {
                root
            } else {
                match env::current_dir() {
                    Ok(cwd) => cwd.join(root),
                    Err(_) => return Value::Null,
                }
            };
            let mut rows = Vec::new();
            match source_inventory_walk(&root_abs, &root_abs, &suffix, &skip, &mut rows) {
                Ok(_) => Value::List(rows.into()),
                Err(_) => Value::Null,
            }
        });
        // random_bytes(n) — open the doorway. Reads n bytes from
        // /dev/urandom every call. Different per invocation, per kernel
        // process. lc-divergence-is-the-doorway: this native intentionally
        // violates sibling parity when invoked — the divergence is the
        // substrate's signal of live field-touch.
        self.register_native("random_bytes", cat_call(), |_, _, args| {
            let n = args[0].as_int();
            if n <= 0 {
                return Value::List(Vec::new().into());
            }
            let mut buf = vec![0u8; n as usize];
            match fs::OpenOptions::new().read(true).open("/dev/urandom") {
                Ok(mut f) => match f.read_exact(&mut buf) {
                    Ok(_) => Value::List(Arc::new(
                        buf.into_iter().map(|b| Value::Int(b as i64)).collect(),
                    )),
                    Err(_) => Value::Null,
                },
                Err(_) => Value::Null,
            }
        });
        // ---- bitwise primitives -----------------------------------
        // True kernel primitives — cannot be expressed in pure Form
        // without exponential cost. Operate on 32-bit-unsigned semantics
        // (high bits masked out) so SHA-256-style recipes can compose
        // round functions over machine-word integers consistently.
        // Sibling parity: same masking, same shift semantics, on all
        // three kernels.
        self.register_native("band", cat_method(), |_, _, args| {
            Value::Int(args[0].as_int() & args[1].as_int())
        });
        self.register_native("bor", cat_method(), |_, _, args| {
            Value::Int(args[0].as_int() | args[1].as_int())
        });
        self.register_native("bxor", cat_method(), |_, _, args| {
            Value::Int(args[0].as_int() ^ args[1].as_int())
        });
        self.register_native("bnot_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            Value::Int((!a) as i64)
        });
        self.register_native("shl_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let n = (args[1].as_int() as u32) & 31;
            Value::Int(a.wrapping_shl(n) as i64)
        });
        self.register_native("shr_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let n = (args[1].as_int() as u32) & 31;
            Value::Int(a.wrapping_shr(n) as i64)
        });
        self.register_native("rotr_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let n = (args[1].as_int() as u32) & 31;
            Value::Int(a.rotate_right(n) as i64)
        });
        // add_u32: modular 32-bit addition — the addition discipline
        // SHA-256's round constants and message schedule both require.
        self.register_native("add_u32", cat_method(), |_, _, args| {
            let a = args[0].as_int() as u32;
            let b = args[1].as_int() as u32;
            Value::Int(a.wrapping_add(b) as i64)
        });
        // sha256_bytes / bytes_sum / bytes_hash were temporarily added
        // as natives here but composted: those are composites, not
        // primitives. SHA-256 lives in form-stdlib/sha256.fk as a Form
        // recipe over the bitwise primitives above. The real JIT path
        // (Form recipe → host machine code via cranelift/Go-source/JS
        // emission) is the next walk; this kernel currently relies on
        // recipe-walk for composite operations.
        // register_jit form-name-str native-name-str → 1 on bind, 0 if
        // native-name has no registered native (refuse silent miss).
        // Inserts (form-name → native-name) into k.jit_aliases. After this,
        // every (form-name ...) call goes through the aliased native instead
        // of walking the Form definition. Form recipes are canonical truth;
        // register_jit is the opt-in that promotes a recipe to host-native
        // execution. Removing the entry restores the Form walk.
        //
        // Discipline: the Form recipe MUST exist (or fall back to closure
        // lookup at call time); the alias is a dispatch hint, not the
        // definition. A demo: define `(defn my-count xs ...)` in Form, then
        // `(register_jit "my-count" "len")` makes (my-count xs) dispatch
        // through native `len`. Same NodeID-attested result; faster path.
        self.register_native("register_jit", cat_witness(), |k, _, args| {
            let form_name = args[0].as_str().to_string();
            let native_name = args[1].as_str().to_string();
            let native_id = k.intern_string(&native_name).inst;
            let exists =
                k.natives.contains_key(&native_id) || k.env_natives.contains_key(&native_id);
            if !exists {
                return Value::Int(0);
            }
            let form_id = k.intern_string(&form_name).inst;
            k.jit_aliases.insert(form_id, native_id);
            Value::Int(1)
        });
        // unregister_jit form-name-str → 1 if removed, 0 if no alias was
        // bound. Restores the Form-recipe walk path for that name.
        self.register_native("unregister_jit", cat_witness(), |k, _, args| {
            let form_name = args[0].as_str().to_string();
            let form_id = k.intern_string(&form_name).inst;
            if k.jit_aliases.remove(&form_id).is_some() {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        // recipe_to_bytes nid → list-of-bytes (or null on error).
        //   Serializes a Recipe subtree to the .fkb wire format (string
        //   table + tree) as a byte list — usable over ANY byte channel
        //   (socket, in-memory list, registry message) without needing
        //   a file. Sibling-parity with read_form_binary semantics: the
        //   same bytes deserialize back to the same content-addressed
        //   structure in any kernel.
        self.register_native("recipe_to_bytes", cat_witness(), |k, _, args| {
            let bytes = serialize_artifact(k, args[0].as_nid());
            Value::List(Arc::new(
                bytes.into_iter().map(|b| Value::Int(b as i64)).collect(),
            ))
        });
        // bytes_to_recipe bytes-list → nid (or null on parse error).
        //   Inverse of recipe_to_bytes. The bytes are the .fkb wire
        //   format from any sibling kernel. The receiver re-interns the
        //   structure locally and returns its NodeID — same content
        //   produces the same NodeID under the substrate's content-
        //   addressing.
        self.register_native("bytes_to_recipe", cat_witness(), |k, _, args| {
            let bytes: Vec<u8> = match &args[0] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => return Value::Null,
            };
            match deserialize_artifact(k, &bytes) {
                Ok(root) => Value::Nid(root),
                Err(_) => Value::Null,
            }
        });
        // jit_compile form-name-str → 1 if a host-JIT compile succeeded,
        //   0 if no compiler is available on this kernel build OR the
        //   recipe contains a shape outside the JIT subset OR rustc isn't
        //   in PATH OR the .so failed to load, -1 if the name isn't bound
        //   to a closure in the caller env.
        //
        // The Rust path mirrors the user-named shape: emit valid Rust
        // source from the Form recipe, invoke the system `rustc
        // --crate-type=cdylib`, load the resulting plugin.so via
        // libloading, and dispatch subsequent calls through the loaded
        // function pointer. Form recipe stays canonical truth — every
        // failure mode honestly returns 0, and recipe-walk continues
        // producing the same observable result.
        self.register_env_native("jit_compile", cat_witness(), |k, a, env, args| {
            if args.is_empty() {
                return Value::Int(-1);
            }
            let form_name = args[0].as_str().to_string();
            let form_id = k.intern_string(&form_name).inst;
            let v = match a.lookup(env, form_id) {
                Some(v) => v,
                None => return Value::Int(-1),
            };
            let cl = match v {
                Value::Closure(c) => c,
                _ => return Value::Int(-1),
            };
            // Already compiled? Idempotent: return 1.
            if k.jit_compiled.contains_key(&cl.body) {
                return Value::Int(1);
            }
            // Emit Rust source for the recipe.
            let src = match emit_rust_source(k, cl.name, &cl.params, cl.body) {
                Some(s) => s,
                None => return Value::Int(0),
            };
            // Compile + load. Any failure → honest 0.
            let jc = match compile_rust_cdylib(&src, cl.params.len()) {
                Some(j) => j,
                None => return Value::Int(0),
            };
            k.jit_compiled.insert(cl.body, Arc::new(jc));
            Value::Int(1)
        });
        // jit_aliased? form-name-str → 1 if a JIT alias is currently bound
        // for this name, else 0. Lets Form code introspect dispatch routing.
        self.register_native("jit_aliased?", cat_compare(RCMP_EQ), |k, _, args| {
            let form_name = args[0].as_str().to_string();
            let form_id = k.intern_string(&form_name).inst;
            if k.jit_aliases.contains_key(&form_id) {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        // jit_compiled? form-name-str → 1 if the recipe's body has been compiled
        // to host-native (by jit_compile OR by measured repetition), else 0. Lets
        // Form code and a benchmark observe the kernel's own promotion decisions.
        self.register_env_native("jit_compiled?", cat_compare(RCMP_EQ), |k, a, env, args| {
            let form_id = k.intern_string(args[0].as_str()).inst;
            match a.lookup(env, form_id) {
                Some(Value::Closure(c)) => {
                    if k.jit_compiled.contains_key(&c.body) {
                        Value::Int(1)
                    } else {
                        Value::Int(0)
                    }
                }
                _ => Value::Int(0),
            }
        });
        // jit-stats -> list(kind, body-nodeid, count, detail). Sibling observer
        // shape with Go/TS; Rust currently reports compiled, warming, and
        // failed bodies, with an empty detail string.
        self.register_native("jit-stats", cat_witness(), |k, _, _| {
            let mut rows: Vec<(String, String, i64, String)> = Vec::new();
            for body in k.jit_compiled.keys() {
                rows.push((
                    "compiled".to_string(),
                    format!("{}.{}.{}.{}", body.pkg, body.level, body.ty, body.inst),
                    0,
                    String::new(),
                ));
            }
            for (body, count) in &k.jit_hits {
                rows.push((
                    "warming".to_string(),
                    format!("{}.{}.{}.{}", body.pkg, body.level, body.ty, body.inst),
                    *count as i64,
                    String::new(),
                ));
            }
            for body in &k.jit_failed {
                rows.push((
                    "compile-failed".to_string(),
                    format!("{}.{}.{}.{}", body.pkg, body.level, body.ty, body.inst),
                    1,
                    String::new(),
                ));
            }
            rows.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
            Value::List(
                rows.into_iter()
                    .map(|(kind, body, count, detail)| {
                        Value::List(
                            vec![
                                Value::Str(kind.into()),
                                Value::Str(body.into()),
                                Value::Int(count),
                                Value::Str(detail.into()),
                            ]
                            .into(),
                        )
                    })
                    .collect::<Vec<_>>()
                    .into(),
            )
        });
        // ---- content-addressed maps : O(1) dispatch tables ------------------
        // The substrate's intrinsic advantage made usable: a switch becomes a
        // DIRECT lookup by the key's content-address (NodeID), not a scan. Two
        // structurally-identical keys share a NodeID, so they land in the same
        // slot — the precomputed structural hash a native compiler must re-pay at
        // every dispatch. And each (key→value) entry is a recorded edge: the
        // dispatch table is a content-addressed graph, so routing IS attesting.
        //
        // map_new → a fresh map handle (per-kernel).
        self.register_native("map_new", cat_witness(), |k, _, _args| {
            k.next_map += 1;
            let h = k.next_map;
            k.maps.insert(h, HashMap::new());
            Value::Int(h)
        });
        // map_put h key value → 1 (0 if no such map). The key MUST be a NodeID —
        // intern it first (intern_trivial_string for a name, intern_node for a
        // shape); the key's CONTENT decides the slot, not its identity.
        self.register_native("map_put", cat_witness(), |k, _, args| {
            let h = args[0].as_int();
            let key = args[1].as_nid();
            let val = args[2].clone();
            match k.maps.get_mut(&h) {
                Some(m) => {
                    m.insert(key, val);
                    Value::Int(1)
                }
                None => Value::Int(0),
            }
        });
        // map_get h key → value (or null). O(1) by the key's NodeID. No scan, no
        // re-hash of the key's bytes — the content-address is the lookup. The
        // traversal of this one edge is, itself, the trace of what was routed.
        self.register_native("map_get", cat_witness(), |k, _, args| {
            let h = args[0].as_int();
            let key = args[1].as_nid();
            match k.maps.get(&h).and_then(|m| m.get(&key)) {
                Some(v) => v.clone(),
                None => Value::Null,
            }
        });
        // seeded_bytes(seed, count) — deterministic LCG byte stream.
        // Same (seed, count) → byte-identical output across Go / Rust / TS.
        // Used by the private-channel protocol to transmit megabytes of
        // content by transmitting only (seed, count) on the wire; receiver
        // reconstructs locally. Compression ratio: arbitrary / 16 bytes.
        // LCG: glibc rand(): state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        self.register_native("seeded_bytes", cat_call(), |_, _, args| {
            let seed = args[0].as_int() as u32;
            let count = args[1].as_int();
            if count <= 0 {
                return Value::List(Vec::new().into());
            }
            let mut state: u32 = seed;
            let n = count as usize;
            let mut out: Vec<Value> = Vec::with_capacity(n);
            for _ in 0..n {
                state = state.wrapping_mul(1103515245).wrapping_add(12345) & 0x7FFFFFFF;
                out.push(Value::Int((state & 0xFF) as i64));
            }
            Value::List(out.into())
        });
        // sum_bytes_list(list) — sum all integer elements. Used for fast
        // verification that two cells' large byte-lists agree without
        // materializing them through the Form recursion. O(n) compiled.
        self.register_native("sum_bytes_list", cat_call(), |_, _, args| match &args[0] {
            Value::List(xs) => {
                let mut s: i64 = 0;
                for v in xs.iter() {
                    s = s.wrapping_add(v.as_int());
                }
                Value::Int(s)
            }
            _ => Value::Int(0),
        });
        // ── ML vector organ — sibling parity with the go carrier's trio.
        // IEEE 754 binary64 end to end, so the same vectors yield the
        // same bits on every kernel.
        self.register_native("dot_product", cat_method(), |_, _, args| {
            match (&args[0], &args[1]) {
                (Value::List(a), Value::List(b)) if a.len() == b.len() => {
                    let mut sum = 0.0f64;
                    for i in 0..a.len() {
                        sum += a[i].as_float() * b[i].as_float();
                    }
                    Value::Float(sum)
                }
                _ => panic!("dot_product requires equal length vectors"),
            }
        });
        self.register_native("magnitude", cat_method(), |_, _, args| match &args[0] {
            Value::List(v) => {
                let mut sum = 0.0f64;
                for x in v.iter() {
                    let f = x.as_float();
                    sum += f * f;
                }
                Value::Float(sum.sqrt())
            }
            _ => panic!("magnitude expects a vector"),
        });
        self.register_native("vector_cosine", cat_method(), |_, _, args| {
            match (&args[0], &args[1]) {
                (Value::List(a), Value::List(b)) if a.len() == b.len() => {
                    let (mut dot, mut na, mut nb) = (0.0f64, 0.0f64, 0.0f64);
                    for i in 0..a.len() {
                        let fa = a[i].as_float();
                        let fb = b[i].as_float();
                        dot += fa * fb;
                        na += fa * fa;
                        nb += fb * fb;
                    }
                    if na == 0.0 || nb == 0.0 {
                        Value::Float(0.0)
                    } else {
                        Value::Float(dot / (na.sqrt() * nb.sqrt()))
                    }
                }
                _ => panic!("vector_cosine requires equal length vectors"),
            }
        });
        // jit_compile_value — the Value-ABI JIT lives on the go carrier
        // today; honest 0 here so sibling-Form code can branch on
        // availability (1 compiled, 0 not compiled here, -1 missing).
        self.register_native("jit_compile_value", cat_witness(), |_, _, _args| {
            Value::Int(0)
        });
        // jit_emit_c — the recipe→C projection lives on the go carrier
        // today; honest "" here so sibling-Form code can branch on it.
        self.register_native("jit_emit_c", cat_witness(), |_, _, _args| {
            Value::Str(String::new().into())
        });
        // write_form_binary — emit a Recipe to .fkb in the full artifact
        // format (string table + tree). Sibling to read_form_binary.
        // Use when source-compile output crosses kernel invocations:
        // serialize-recipe alone drops string indices.
        self.register_native("write_form_binary", cat_call(), |k, _, args| {
            let path = args[0].as_str().to_string();
            let nid = args[1].as_nid();
            let bytes = serialize_artifact(k, nid);
            match fs::write(&path, &bytes) {
                Ok(_) => Value::Int(bytes.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("read_form_binary", cat_call(), |k, _, args| match fs::read(
            args[0].as_str(),
        ) {
            Ok(bytes) => match deserialize_artifact(k, &bytes) {
                Ok(root) => Value::Nid(root),
                Err(_) => Value::Null,
            },
            Err(_) => Value::Null,
        });
        self.register_native("write_form_binary", cat_call(), |k, _, args| {
            let bytes = serialize_artifact(k, args[1].as_nid());
            match fs::write(args[0].as_str(), &bytes) {
                Ok(_) => Value::Int(bytes.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("file_size", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) => Value::Int(meta.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // file_mtime — modification time in unix seconds; -1 if missing.
        // Sibling parity with Go + TS file_mtime; powers Form-side cache
        // layers that regenerate .fkb projections when source files drift.
        self.register_native("file_mtime", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) => match meta.modified() {
                    Ok(t) => match t.duration_since(std::time::UNIX_EPOCH) {
                        Ok(d) => Value::Int(d.as_secs() as i64),
                        Err(_) => Value::Int(-1),
                    },
                    Err(_) => Value::Int(-1),
                },
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("file_byte_at", cat_call(), |_, _, args| {
            let offset = args[1].as_int();
            if offset < 0 {
                return Value::Int(-1);
            }
            let mut file = match fs::File::open(args[0].as_str()) {
                Ok(file) => file,
                Err(_) => return Value::Int(-1),
            };
            if file.seek(SeekFrom::Start(offset as u64)).is_err() {
                return Value::Int(-1);
            }
            let mut buf = [0u8; 1];
            match file.read(&mut buf) {
                Ok(1) => Value::Int(buf[0] as i64),
                _ => Value::Int(-1),
            }
        });
        self.register_native("read_file_slice", cat_call(), |_, _, args| {
            let offset = args[1].as_int();
            let length = args[2].as_int();
            if offset < 0 || length <= 0 {
                return Value::Str(String::new().into());
            }
            let mut file = match fs::File::open(args[0].as_str()) {
                Ok(file) => file,
                Err(_) => return Value::Str(String::new().into()),
            };
            if file.seek(SeekFrom::Start(offset as u64)).is_err() {
                return Value::Str(String::new().into());
            }
            let mut buf = vec![0u8; length as usize];
            match file.read(&mut buf) {
                Ok(n) => Value::Str(String::from_utf8_lossy(&buf[..n]).to_string().into()),
                Err(_) => Value::Str(String::new().into()),
            }
        });

        // --- Filesystem CRUD natives — real directories + files --------
        // Sibling parity across Go/Rust/TS. Predicates return 1/0;
        // mutations return 0 on success, -1 on error; fs_list returns a
        // List of name-strings or Null on error.
        self.register_native("fs_exists", cat_call(), |_, _, args| {
            if fs::metadata(args[0].as_str()).is_ok() {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        self.register_native("fs_is_dir", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) if meta.is_dir() => Value::Int(1),
                _ => Value::Int(0),
            }
        });
        self.register_native(
            "fs_mkdir",
            cat_call(),
            |_, _, args| match fs::create_dir_all(args[0].as_str()) {
                Ok(_) => Value::Int(0),
                Err(_) => Value::Int(-1),
            },
        );
        self.register_native("fs_rmdir", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) if meta.is_dir() => match fs::remove_dir_all(args[0].as_str()) {
                    Ok(_) => Value::Int(0),
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("fs_remove", cat_call(), |_, _, args| {
            match fs::metadata(args[0].as_str()) {
                Ok(meta) if !meta.is_dir() => match fs::remove_file(args[0].as_str()) {
                    Ok(_) => Value::Int(0),
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("fs_rename", cat_call(), |_, _, args| {
            match fs::rename(args[0].as_str(), args[1].as_str()) {
                Ok(_) => Value::Int(0),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("fs_list", cat_call(), |_, _, args| {
            match fs::read_dir(args[0].as_str()) {
                Ok(rd) => {
                    // sort by name for cross-kernel parity (Go's os.ReadDir
                    // is name-sorted; Rust/Node are OS-arbitrary).
                    let mut names: Vec<String> = rd
                        .flatten()
                        .map(|e| e.file_name().to_string_lossy().to_string())
                        .collect();
                    names.sort();
                    Value::List(Arc::new(
                        names.into_iter().map(|s| Value::Str(s.into())).collect(),
                    ))
                }
                Err(_) => Value::Null,
            }
        });

        // --- Socket natives — L1 physical layer for inter-cell IO ------
        // Sibling parity across Go/Rust/TS. Handle = int (≥ 0 success,
        // -1 error). Connection table is a module-level OnceLock<Mutex>.
        // (socket_listen port)             → handle | -1
        // (socket_accept listener-handle)  → conn-handle | -1   (BLOCKS)
        // (socket_connect host port)       → conn-handle | -1
        // (socket_send conn bytes-string)  → bytes-sent | -1
        // (socket_recv conn max-bytes)     → received-string ("" on close)
        // (socket_close handle)            → 0 | -1
        self.register_native("socket_listen", cat_call(), |_, _, args| {
            let port = args[0].as_int();
            match TcpListener::bind(format!("127.0.0.1:{}", port)) {
                Ok(ln) => Value::Int(socket_register(SocketKind::Listener(ln))),
                Err(_) => Value::Int(-1),
            }
        });
        // (socket_port listener-handle) → bound TCP port | -1. Reports the
        // OS-assigned port of an ephemeral (port 0) listener — the basis of
        // single-process loopback.
        self.register_native("socket_port", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Int(-1),
            };
            match &*s {
                SocketKind::Listener(ln) => match ln.local_addr() {
                    Ok(addr) => Value::Int(addr.port() as i64),
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("socket_accept", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Int(-1),
            };
            match &*s {
                SocketKind::Listener(ln) => match ln.accept() {
                    Ok((stream, _)) => {
                        Value::Int(socket_register(SocketKind::Stream(Mutex::new(stream))))
                    }
                    Err(_) => Value::Int(-1),
                },
                _ => Value::Int(-1),
            }
        });
        self.register_native("socket_connect", cat_call(), |_, _, args| {
            let host = args[0].as_str().to_string();
            let port = args[1].as_int();
            match TcpStream::connect(format!("{}:{}", host, port)) {
                Ok(stream) => Value::Int(socket_register(SocketKind::Stream(Mutex::new(stream)))),
                Err(_) => Value::Int(-1),
            }
        });
        self.register_native("socket_send", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let bytes = args[1].as_str().as_bytes().to_vec();
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Int(-1),
            };
            match &*s {
                SocketKind::Stream(m) => {
                    let mut g = m.lock().unwrap();
                    match g.write(&bytes) {
                        Ok(n) => Value::Int(n as i64),
                        Err(_) => Value::Int(-1),
                    }
                }
                _ => Value::Int(-1),
            }
        });
        self.register_native("socket_recv", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let max = args[1].as_int();
            if max <= 0 {
                return Value::Str(String::new().into());
            }
            let s = match socket_lookup(h) {
                Some(s) => s,
                None => return Value::Str(String::new().into()),
            };
            match &*s {
                SocketKind::Stream(m) => {
                    let mut g = m.lock().unwrap();
                    let mut buf = vec![0u8; max as usize];
                    match g.read(&mut buf) {
                        Ok(n) if n > 0 => {
                            Value::Str(String::from_utf8_lossy(&buf[..n]).to_string().into())
                        }
                        _ => Value::Str(String::new().into()),
                    }
                }
                _ => Value::Str(String::new().into()),
            }
        });
        self.register_native("socket_close", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            if h < 0 {
                return Value::Int(-1);
            }
            if socket_drop(h) {
                Value::Int(0)
            } else {
                Value::Int(-1)
            }
        });

        // --- Host/runtime cells used by the native HTTP catalog --------
        self.register_native("volatile_cell_put", cat_call(), |_, _, args| {
            let coord = volatile_coord(args[0].as_str(), args[1].as_str());
            let mut table = volatile_table().lock().unwrap();
            table.cells.insert(
                coord,
                VolatileCell {
                    updated_ms: now_unix_ms_value(),
                    value: args[2].clone(),
                },
            );
            Value::Int(1)
        });
        self.register_native("volatile_cell_get", cat_access(), |_, _, args| {
            let coord = volatile_coord(args[0].as_str(), args[1].as_str());
            volatile_table()
                .lock()
                .unwrap()
                .cells
                .get(&coord)
                .map(|cell| cell.value.clone())
                .unwrap_or(Value::Null)
        });
        self.register_native("volatile_cell_delete", cat_call(), |_, _, args| {
            let coord = volatile_coord(args[0].as_str(), args[1].as_str());
            if volatile_table()
                .lock()
                .unwrap()
                .cells
                .remove(&coord)
                .is_some()
            {
                Value::Int(1)
            } else {
                Value::Int(0)
            }
        });
        self.register_native("volatile_cell_scan_since", cat_access(), |_, _, args| {
            let namespace = args[0].as_str();
            let cutoff = args[1].as_int();
            let prefix = format!("{namespace}\0");
            // sibling parity: Go returns (key value updated_ms) triples
            let rows = volatile_table()
                .lock()
                .unwrap()
                .cells
                .iter()
                .filter(|(coord, cell)| coord.starts_with(&prefix) && cell.updated_ms >= cutoff)
                .map(|(coord, cell)| {
                    Value::List(
                        vec![
                            Value::Str(coord[prefix.len()..].to_string().into()),
                            cell.value.clone(),
                            Value::Int(cell.updated_ms),
                        ]
                        .into(),
                    )
                })
                .collect::<Vec<_>>();
            Value::List(rows.into())
        });
        self.register_native("volatile_cell_prune_before", cat_call(), |_, _, args| {
            let namespace = args[0].as_str();
            let cutoff = args[1].as_int();
            let prefix = format!("{namespace}\0");
            let mut table = volatile_table().lock().unwrap();
            let before = table.cells.len();
            table
                .cells
                .retain(|coord, cell| !coord.starts_with(&prefix) || cell.updated_ms >= cutoff);
            Value::Int((before - table.cells.len()) as i64)
        });
        self.register_native("repo_root", cat_access(), |_, _, _| {
            find_repo_root()
                .map(|path| Value::Str(path.to_string_lossy().to_string().into()))
                .unwrap_or_else(|_| Value::Str(String::new().into()))
        });
        self.register_native("kernel_runtime_name", cat_call(), |_, _, _| {
            Value::Str("form-kernel-rust".to_string().into())
        });
        self.register_native("kernel_started_unix_ms", cat_call(), |_, _, _| {
            Value::Int(kernel_started_unix_ms_value())
        });
        self.register_native("unix_ms_to_iso_utc", cat_call(), |_, _, args| {
            Value::Str(unix_ms_to_iso_utc(args[0].as_int()).into())
        });
        self.register_native("uptime_human", cat_call(), |_, _, args| {
            Value::Str(uptime_human(args[0].as_int()).into())
        });
        self.register_native("config_value_or", cat_call(), |_, _, args| {
            load_config_value_or(args[0].as_str(), &args[1])
        });
        self.register_native("config_database_url", cat_call(), |_, _, _| {
            match load_configured_database_url() {
                Ok(url) => {
                    pg_set_error(None);
                    Value::Str(url.into())
                }
                Err(e) => {
                    pg_set_error(Some(e));
                    Value::Str(String::new().into())
                }
            }
        });

        // --- Postgres natives — the DB carrier of the storage port ------
        // (pg_connect dsn)        → handle | -1
        // (pg_exec handle sql)    → rows-affected | -1   (DDL / INSERT / UPDATE)
        // (pg_query handle sql params?)   → tab/newline result string | "ERR"
        // (pg_query_rows handle sql params?) → list of __dict__ rows
        // (pg_close handle)       → 0 | -1
        self.register_native("pg_last_error", cat_call(), |_, _, _| {
            Value::Str(pg_last_error_cell().lock().unwrap().clone().into())
        });
        self.register_native("pg_connect", cat_call(), |_, _, args| {
            let dsn = args[0].as_str().trim().to_string();
            if !dsn.starts_with("postgres://") && !dsn.starts_with("postgresql://") {
                pg_set_error(Some(
                    "pg_connect: database.url is not a PostgreSQL URL".to_string(),
                ));
                return Value::Int(-1);
            }
            match postgres::Client::connect(&dsn, postgres::NoTls) {
                Ok(c) => {
                    pg_set_error(None);
                    Value::Int(pg_register(c))
                }
                Err(e) => {
                    pg_set_error(Some(e.to_string()));
                    Value::Int(-1)
                }
            }
        });
        self.register_native("pg_ping", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let client = match pg_lookup(h) {
                Some(c) => c,
                None => {
                    pg_set_error(Some("pg_ping: unknown connection handle".to_string()));
                    return Value::Bool(false);
                }
            };
            let mut g = client.lock().unwrap();
            match g.simple_query("SELECT 1") {
                Ok(_) => {
                    pg_set_error(None);
                    Value::Bool(true)
                }
                Err(e) => {
                    pg_set_error(Some(e.to_string()));
                    Value::Bool(false)
                }
            }
        });
        self.register_native("pg_exec", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let sql = args[1].as_str().to_string();
            let client = match pg_lookup(h) {
                Some(c) => c,
                None => {
                    pg_set_error(Some("pg_exec: unknown connection handle".to_string()));
                    return Value::Int(-1);
                }
            };
            let params = form_sql_args(args.get(2));
            let param_refs = params
                .iter()
                .map(|p| p.as_ref() as &(dyn postgres::types::ToSql + Sync))
                .collect::<Vec<_>>();
            let mut g = client.lock().unwrap();
            match g.execute(&sql, &param_refs) {
                Ok(n) => {
                    pg_set_error(None);
                    Value::Int(n as i64)
                }
                Err(e) => {
                    pg_set_error(Some(e.to_string()));
                    Value::Int(-1)
                }
            }
        });
        self.register_native("pg_query", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let sql = args[1].as_str().to_string();
            let client = match pg_lookup(h) {
                Some(c) => c,
                None => {
                    pg_set_error(Some("pg_query: unknown connection handle".to_string()));
                    return Value::Str("ERR".to_string().into());
                }
            };
            let params = form_sql_args(args.get(2));
            let param_refs = params
                .iter()
                .map(|p| p.as_ref() as &(dyn postgres::types::ToSql + Sync))
                .collect::<Vec<_>>();
            let mut g = client.lock().unwrap();
            let rows = match g.query(&sql, &param_refs) {
                Ok(r) => r,
                Err(e) => {
                    pg_set_error(Some(e.to_string()));
                    return Value::Str("ERR".to_string().into());
                }
            };
            // Encode rows as tab-separated columns, newline-separated rows.
            // Columns are rendered to text via their SQL type (text/int8/bool
            // cover the substrate's portable column set). NULL → empty string.
            let mut out = String::new();
            for (ri, row) in rows.iter().enumerate() {
                if ri > 0 {
                    out.push('\n');
                }
                for ci in 0..row.len() {
                    if ci > 0 {
                        out.push('\t');
                    }
                    out.push_str(&pg_cell_to_string(row, ci));
                }
            }
            pg_set_error(None);
            Value::Str(out.into())
        });
        self.register_native("pg_query_rows", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            let sql = args[1].as_str().to_string();
            let client = match pg_lookup(h) {
                Some(c) => c,
                None => {
                    pg_set_error(Some("pg_query_rows: unknown connection handle".to_string()));
                    return Value::List(Vec::new().into());
                }
            };
            let params = form_sql_args(args.get(2));
            let param_refs = params
                .iter()
                .map(|p| p.as_ref() as &(dyn postgres::types::ToSql + Sync))
                .collect::<Vec<_>>();
            let mut g = client.lock().unwrap();
            let rows = match g.query(&sql, &param_refs) {
                Ok(r) => r,
                Err(e) => {
                    pg_set_error(Some(e.to_string()));
                    return Value::List(Vec::new().into());
                }
            };
            let mut out = Vec::new();
            for row in rows.iter() {
                let mut pairs = Vec::with_capacity(row.len() * 2 + 1);
                pairs.push(Value::Str("__dict__".to_string().into()));
                for (ci, col) in row.columns().iter().enumerate() {
                    pairs.push(Value::Str(col.name().to_string().into()));
                    pairs.push(pg_cell_to_value(row, ci));
                }
                out.push(Value::List(pairs.into()));
            }
            pg_set_error(None);
            Value::List(out.into())
        });
        self.register_native("pg_close", cat_call(), |_, _, args| {
            let h = args[0].as_int();
            if h < 0 {
                return Value::Int(-1);
            }
            if pg_drop(h) {
                pg_set_error(None);
                Value::Int(0)
            } else {
                pg_set_error(Some("pg_close: unknown connection handle".to_string()));
                Value::Int(-1)
            }
        });

        // --- Substrate write surface ------------------------------------
        // Form code holds NodeIDs as values (Value::Nid) and uses these
        // natives to construct recipes. Closes form-runtime-in-form gaps
        // W1-W3. With these, templates (Breath 2) become expressible —
        // Form code can BUILD recipes from pattern matches, not just walk
        // pre-existing ones. All attributed as WITNESS — the substrate
        // attesting to its own structure.

        self.register_native("make_nodeid", cat_witness(), |_, _, args| {
            Value::Nid(NodeID {
                pkg: args[0].as_int() as u32,
                level: args[1].as_int() as u32,
                ty: args[2].as_int() as u32,
                inst: args[3].as_int() as u32,
            })
        });
        // bp — resolve a Blueprint name to its NodeID via the generated
        // BP_ENTRIES table. Unknown name → undefined node (1,2,0,0).
        // Sibling parity with form-kernel-go + form-kernel-ts.
        self.register_native("bp", cat_witness(), |_, _, args| {
            let name = args[0].as_str();
            for (entry_name, [pkg, level, ty, inst]) in self::bp_table::BP_ENTRIES {
                if *entry_name == name {
                    return Value::Nid(NodeID {
                        pkg: *pkg,
                        level: *level,
                        ty: *ty,
                        inst: *inst,
                    });
                }
            }
            // Fail loud — never invent a NodeID for an unknown name. The old
            // silent fallback to {1,2,0,0} collapsed every unregistered name
            // onto one NodeID, so distinct blueprints collided invisibly. An
            // unregistered name is a missing registration, not a valid shape.
            // Sibling parity: Go panics, TS throws.
            panic!(
                "bp: unregistered blueprint name {:?} — register it: \
                 python3 scripts/scan_form_blueprints.py register {} (bp tables then regenerate). \
                 The substrate never invents a NodeID for an unknown name.",
                name, name
            )
        });
        self.register_native("intern_trivial_int", cat_witness(), |k, _, args| {
            Value::Nid(k.intern_trivial_int(args[0].as_int()))
        });
        self.register_native("intern_trivial_string", cat_witness(), |k, _, args| {
            let s = args[0].as_str().to_string();
            Value::Nid(k.intern_string(&s))
        });
        self.register_native("intern_trivial_bool", cat_witness(), |_, _, args| {
            Value::Nid(NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_BOOL,
                inst: if args[0].as_bool() { 1 } else { 0 },
            })
        });
        // intern_trivial_float — content-address an IEEE-754 f64 into the
        // overflow table and return its trivial NodeID. The string argument is
        // the float's source text (e.g. "0.5"); a parse failure lands on +0.0
        // so the witness is total like str_to_int's unwrap_or(0). Sibling of
        // intern_trivial_int / intern_trivial_string: the interning primitive
        // (intern_trivial_float64) already existed for the .fk-source reader;
        // this exposes it to Form code so the python-bmf float-literal lift can
        // build a PY-BMF-FLOAT leaf the walker reads back as Value::Float.
        self.register_native("intern_trivial_float", cat_witness(), |k, _, args| {
            let f: f64 = args[0].as_str().parse().unwrap_or(0.0);
            Value::Nid(k.intern_trivial_float64(f))
        });
        // make_float32 / make_float64 — intern a float-valued substrate trivial
        // from a numeric arg (int or float, coerced via as_float). Sibling
        // parity with Go (internTrivialFloat32/64 + VNodeID) and TS
        // (internTrivialFloat32/64 + boxValue). Where intern_trivial_float takes
        // the float's *source text*, these take the *value* — the verb Form code
        // calls when it holds a number and wants the substrate identity of the
        // typed float (FLOAT32 = type 6, FLOAT64 = type 7). Read back with
        // float_value. 0.5 is exact in both widths, so make_float32(0.5) and
        // make_float64(0.5) both decode to 0.5 three-way; the NODE-level type
        // tag (6 vs 7) stays distinct even where the value-level f64 collapses.
        self.register_native("make_float32", cat_witness(), |k, _, args| {
            Value::Nid(k.intern_trivial_float32(args[0].as_float() as f32))
        });
        self.register_native("make_float64", cat_witness(), |k, _, args| {
            Value::Nid(k.intern_trivial_float64(args[0].as_float()))
        });
        self.register_native("float_value", cat_method(), |k, _, args| {
            let n = args[0].as_nid();
            match n.ty {
                TRIV_FLOAT32 => Value::Float(k.decode_float32(n.inst) as f64),
                TRIV_FLOAT64 => Value::Float(k.decode_float64(n.inst)),
                _ => panic!("float_value expects a float NodeID"),
            }
        });
        self.register_native("intern_node", cat_witness(), |k, _, args| {
            // args[0]: category as Nid; args[1]: children as List of Nids
            let cat = args[0].as_nid();
            let kids: Vec<NodeID> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_nid()).collect(),
                _ => panic!("intern_node: children must be a list"),
            };
            Value::Nid(k.intern(cat, kids))
        });
        self.register_native(
            "field_blueprint",
            cat_field_primitive(RB_FIELD),
            native_field_blueprint,
        );
        self.register_native(
            "field_cell",
            cat_field_primitive(RB_FIELD),
            native_field_cell,
        );
        self.register_native(
            "field_carrier",
            cat_field_primitive(RB_CARRIER),
            native_field_carrier,
        );
        self.register_native(
            "field_topology",
            cat_field_primitive(RB_TOPOLOGY),
            native_field_topology,
        );
        self.register_native(
            "field_fiber",
            cat_field_primitive(RB_FIBER),
            native_field_fiber,
        );
        self.register_native(
            "field_region",
            cat_field_primitive(RB_REGION),
            native_field_region,
        );
        self.register_native(
            "field_boundary",
            cat_field_primitive(RB_BOUNDARY),
            native_field_boundary,
        );
        self.register_native(
            "field_neighborhood",
            cat_field_primitive(RB_NEIGHBORHOOD),
            native_field_neighborhood,
        );
        self.register_native(
            "field_match",
            cat_field_primitive(RB_MATCH_FIELD),
            native_field_match,
        );
        self.register_native(
            "field_delta",
            cat_field_primitive(RB_DELTA),
            native_field_delta,
        );
        self.register_native(
            "field_resolve",
            cat_field_primitive(RB_RESOLVE),
            native_field_resolve,
        );
        self.register_native(
            "field_commit",
            cat_field_primitive(RB_COMMIT),
            native_field_commit,
        );
        self.register_native(
            "field_step",
            cat_field_primitive(RB_STEP),
            native_field_step,
        );
        self.register_native(
            "field_lift",
            cat_field_primitive(RB_LIFT),
            native_field_lift,
        );
        self.register_native(
            "field_sample",
            cat_field_primitive(RB_SAMPLE),
            native_field_sample,
        );
        self.register_native(
            "field_observe",
            cat_field_primitive(RB_OBSERVE),
            native_field_observe,
        );
        self.register_native(
            "field_intervene",
            cat_field_primitive(RB_INTERVENE),
            native_field_intervene,
        );
        self.register_native(
            "field_residual",
            cat_field_primitive(RB_RESIDUAL),
            native_field_residual,
        );
        self.register_native(
            "field_receipt",
            cat_field_primitive(RB_RECEIPT),
            native_field_receipt,
        );
        self.register_native(
            "field_cost",
            cat_field_primitive(RB_COST),
            native_field_cost,
        );
        self.register_native(
            "field_consent",
            cat_field_primitive(RB_CONSENT),
            native_field_consent,
        );
        self.register_native(
            "field_evidence",
            cat_field_primitive(RB_EVIDENCE),
            native_field_evidence,
        );
        self.register_native("substrate_mark", cat_witness(), |k, _, _| {
            Value::List(k.substrate_mark().into())
        });
        self.register_native("substrate_counts", cat_witness(), |k, _, _| {
            Value::List(k.substrate_counts().into())
        });
        self.register_native(
            "substrate_release",
            cat_witness(),
            |k, _, args| match &args[0] {
                Value::List(mark) => Value::Int(k.substrate_release(mark)),
                _ => Value::Int(0),
            },
        );
        self.register_native("substrate_gc", cat_witness(), |k, _, args| match &args[0] {
            Value::List(roots) => Value::List(k.substrate_gc(roots, None).into()),
            _ => Value::List(k.substrate_gc(&[], None).into()),
        });
        self.register_native("node_category", cat_witness(), |k, _, args| {
            Value::Nid(k.category(args[0].as_nid()))
        });
        self.register_native("node_children", cat_witness(), |k, _, args| {
            let kids = k.children(args[0].as_nid());
            Value::List(Arc::new(kids.into_iter().map(Value::Nid).collect()))
        });
        self.register_native("node_value", cat_witness(), |k, _, args| {
            k.trivial_value(args[0].as_nid())
        });
        self.register_native("node_pkg", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().pkg as i64)
        });
        self.register_native("node_level", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().level as i64)
        });
        self.register_native("node_type", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().ty as i64)
        });
        self.register_native("node_inst", cat_witness(), |_, _, args| {
            Value::Int(args[0].as_nid().inst as i64)
        });
        // node_eq — compare two NodeIDs structurally without coercing to int.
        // The kernel's `eq` (RCMP_EQ) does as_int on both operands, which
        // panics on NodeIDs. node_eq closes that gap so Form code (like
        // emit-engine.fk's lookup-template) can dispatch on Recipe category
        // by direct NodeID equality. Sibling parity required across Go/TS.
        self.register_native("node_eq", cat_compare(RCMP_EQ), |_, _, args| {
            bool_int(args[0].as_nid() == args[1].as_nid())
        });
        // value_eq — polymorphic equality across Value kinds. Answers
        // 1 when both args have the same kind AND compare equal
        // within that kind. Cross-kind answers 0. Use when a
        // Form-side function holds tagged values that may be either
        // strings or NodeIDs — e.g. domain/lens in bmf-symbol-context.
        self.register_native("value_eq", cat_compare(RCMP_EQ), |_, _, args| {
            bool_int(value_equal(&args[0], &args[1]))
        });
        // intern_node_at — intern a composite Recipe AND record its source
        // attribution. Engine.fk's parser actions call this so every emitted
        // Recipe carries (file, line, col) provenance. The satsang teaching:
        // a cell's state can be traced back to the recipe lines that
        // authored it — the practice of self-knowing.
        //
        // Args: (category, children, file_string, line_int, col_int)
        // Returns: the interned NodeID (same as intern_node).
        self.register_native("intern_node_at", cat_witness(), |k, _, args| {
            let cat = args[0].as_nid();
            let kids: Vec<NodeID> = match &args[1] {
                Value::List(v) => v.iter().map(|x| x.as_nid()).collect(),
                _ => Vec::new(),
            };
            let nid = k.intern(cat, kids);
            let file_nid = k.intern_string(args[2].as_str());
            let file_id = file_nid.inst;
            let line = args[3].as_int() as u32;
            let col = args[4].as_int() as u32;
            k.source_attr.insert(nid, (file_id, line, col));
            Value::Nid(nid)
        });
        // node_source — read back a Recipe's source attribution.
        // Returns (list file_string line col) or empty list if none recorded.
        self.register_native("node_source", cat_witness(), |k, _, args| {
            let nid = args[0].as_nid();
            match k.source_attr.get(&nid).copied() {
                Some((file_id, line, col)) => {
                    let file = k.strs[file_id as usize].clone();
                    Value::List(
                        vec![
                            Value::Str(file.into()),
                            Value::Int(line as i64),
                            Value::Int(col as i64),
                        ]
                        .into(),
                    )
                }
                None => Value::List(vec![].into()),
            }
        });
        // framebuffer-events — return all NodeIDs that have source
        // attribution recorded. The substrate's source_attr side-map
        // IS the framebuffer: every intern_node_at write becomes a
        // discoverable trace event. Observer-side tracing: the
        // EMITTER pays only the side-map write (~O(1)); the OBSERVER
        // pays the cost of walking + filtering this list when it
        // wants to analyze hot-spots or flow.
        self.register_native("framebuffer-events", cat_witness(), |k, _, _| {
            Value::List(Arc::new(
                k.source_attr.keys().copied().map(Value::Nid).collect(),
            ))
        });
        // framebuffer-clear — reset the framebuffer. Useful for
        // bounded observation windows (subscribe → do work →
        // analyze → clear → next window).
        self.register_native("framebuffer-clear", cat_witness(), |k, _, _| {
            k.source_attr.clear();
            Value::Null
        });
        // serialize-recipe — walk a Recipe tree, emit a flat byte list
        // (each byte as Value::Int). Format per node: 5 big-endian u32
        // values (pkg, level, ty, inst, children_count) + recursively
        // each child's serialization. Trivials have children_count=0.
        // The substrate's content-addressing means deserialize re-
        // creates the same NodeID via intern.
        self.register_native("serialize-recipe", cat_witness(), |k, _, args| {
            let mut bytes: Vec<u8> = Vec::new();
            serialize_nid(k, args[0].as_nid(), &mut bytes);
            Value::List(Arc::new(
                bytes.into_iter().map(|b| Value::Int(b as i64)).collect(),
            ))
        });
        // deserialize-recipe — read flat byte list back into a Recipe
        // tree, re-interning composites so the resulting NodeIDs
        // collapse to the same identities as the original tree.
        self.register_native("deserialize-recipe", cat_witness(), |k, _, args| {
            let bytes: Vec<u8> = match &args[0] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => Vec::new(),
            };
            let scope = k.next_import_scope();
            let (nid, _pos) = deserialize_nid(k, &bytes, 0, scope);
            Value::Nid(nid)
        });
        // write_file_bytes — write a list of byte-values to a path.
        // Sibling of read_file_bytes (added with PNG binary parser).
        self.register_native("write_file_bytes", cat_call(), |_, _, args| {
            let path = args[0].as_str().to_string();
            let bytes: Vec<u8> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => Vec::new(),
            };
            match fs::write(&path, &bytes) {
                Ok(_) => Value::Int(bytes.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // file_append_bytes path bytes-list → new-file-size | -1. Atomic
        // O_APPEND write — the missing primitive for a log-structured store.
        // Unlike write_file_bytes (which truncates), this appends at end-of-
        // file and returns the new total size. Creates the file if absent.
        self.register_native("file_append_bytes", cat_call(), |_, _, args| {
            let path = args[0].as_str().to_string();
            let bytes: Vec<u8> = match &args[1] {
                Value::List(xs) => xs.iter().map(|v| v.as_int() as u8).collect(),
                _ => return Value::Int(-1),
            };
            let mut f = match fs::OpenOptions::new().append(true).create(true).open(&path) {
                Ok(f) => f,
                Err(_) => return Value::Int(-1),
            };
            if f.write_all(&bytes).is_err() {
                return Value::Int(-1);
            }
            match f.metadata() {
                Ok(meta) => Value::Int(meta.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // write_file_text — host text output. Keeps text compilers from
        // materializing byte lists while byte codecs still use write_file_bytes.
        self.register_native("write_file_text", cat_call(), |_, _, args| {
            let path = args[0].as_str().to_string();
            let text = args[1].as_str().to_string();
            match fs::write(&path, text.as_bytes()) {
                Ok(_) => Value::Int(text.len() as i64),
                Err(_) => Value::Int(-1),
            }
        });
        // walk_recipe — evaluate a NodeID in a fresh root frame. Returns
        // the value the recipe produces. Use case: Form code builds a
        // recipe via intern_node, then walks it to get the runtime result.
        self.register_native("walk_recipe", cat_witness(), |k, _, args| {
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            walk(k, &mut sub_arena, args[0].as_nid(), env)
        });
        // walk_recipe_here — walks a Recipe in the CALLER's env, so let-
        // bindings inside the Recipe land in the caller's scope. Matches
        // the Go kernel's env-aware variant.
        self.register_env_native("walk_recipe_here", cat_witness(), |k, a, env, args| {
            // Pin the recipe root as an active root so substrate_gc keeps the
            // definitions reachable. Closures bound here hold body NodeIDs
            // that aren't reachable from the source-parsed root, so without
            // this pin a subsequent substrate_gc would sweep them and leave
            // env holding closures with deleted bodies.
            let root = args[0].as_nid();
            k.active_roots.push(root);
            walk(k, a, root, env)
        });
        self.register_native("walk_parallel", cat_witness(), native_walk_parallel);
        self.register_native("walk-parallel", cat_witness(), native_walk_parallel);
        self.register_native(
            "walk_parallel_cached",
            cat_witness(),
            native_walk_parallel_cached,
        );
        self.register_native(
            "walk-parallel-cached",
            cat_witness(),
            native_walk_parallel_cached,
        );
        // walk-cached — JIT-vector memoization. Caller asserts the
        // recipe is pure (no I/O, no external state). Result cached
        // by recipe NodeID. Subsequent calls return O(1) from cache
        // instead of re-walking the tree. Demonstrates the JIT slot:
        // once a recipe is identified as a hot path (via framebuffer
        // observation), its result can be cached / pre-compiled.
        // Real JIT replaces this cache with native machine code; the
        // architectural shape stays the same.
        self.register_native("walk-cached", cat_witness(), |k, _, args| {
            let nid = args[0].as_nid();
            if let Some(v) = k.walk_cache.get(&nid).cloned() {
                k.walk_cache_hits += 1;
                return v;
            }
            k.walk_cache_misses += 1;
            let mut sub_arena = Arena::new();
            let env = sub_arena.new_frame(None);
            let v = walk(k, &mut sub_arena, nid, env);
            k.walk_cache.insert(nid, v.clone());
            v
        });
        // walk-cache-clear — reset the memoization cache. Use when
        // the substrate state changes in ways that would invalidate
        // cached results (e.g. native re-registration).
        self.register_native("walk-cache-clear", cat_witness(), |k, _, _| {
            k.walk_cache.clear();
            k.walk_cache_hits = 0;
            k.walk_cache_misses = 0;
            Value::Null
        });
        // walk-cache-size — number of cached recipes. Useful for
        // observability — when paired with framebuffer-events, lets
        // tooling compare "recipes seen" vs "recipes JIT-cached".
        self.register_native("walk-cache-size", cat_witness(), |k, _, _| {
            Value::Int(k.walk_cache.len() as i64)
        });
        self.register_native("walk-cache-stats", cat_witness(), |k, _, _| {
            Value::List(
                vec![
                    Value::Int(k.walk_cache_hits as i64),
                    Value::Int(k.walk_cache_misses as i64),
                    Value::Int(k.walk_cache.len() as i64),
                ]
                .into(),
            )
        });

        // native_blueprint — read a native's Form category from inside Form.
        // Returns the category NodeID (level=2, ty=RBasic, inst=instance) or
        // Null if the name isn't bound to a native. Makes attribution legible
        // from Form code: `(native_blueprint "intern_node")` → @1.2.6.1.
        self.register_native("native_blueprint", cat_witness(), |k, _, args| {
            let s = args[0].as_str();
            match k.str_idx.get(s).copied() {
                Some(name_id) => match k.natives.get(&name_id) {
                    Some(ne) => Value::Nid(ne.category),
                    None => Value::Null,
                },
                None => Value::Null,
            }
        });

        // --- Debug / inspection -----------------------------------------
        // `trace` — print-and-return. Drop into any Form expression to
        // inspect a value mid-computation without breaking control flow.
        // Output goes to stderr so it doesn't pollute the result on stdout.
        //   (let result (trace (filter even? xs)))
        //   (trace "label" value)   ; with a label prefix
        // `now_unix_ms` — current wall-clock as a millisecond unix timestamp.
        // External effect (reads the host clock) so it's cat_call. Sibling
        // parity holds on shape, NOT on value: every kernel returns an int,
        // every kernel's int is > a recent past epoch — but the exact
        // milliseconds diverge between invocations. Bands check shape only.
        self.register_native("now_unix_ms", cat_call(), |_, _, _| {
            Value::Int(now_unix_ms_value())
        });

        // No Form category claimed — `trace` is a debug surface, honest
        // about being outside the structural vocabulary.
        self.register_native("trace", cat_undefined(), |_, _, args| {
            if args.len() >= 2 {
                eprintln!("[trace {}] {}", args[0].as_str(), args[1].display());
                args[1].clone()
            } else {
                eprintln!("[trace] {}", args[0].display());
                args[0].clone()
            }
        });
    }
}

// ---------------------------------------------------------------------------
// resolve_method — walk the inheritance chain to find a method closure.
//
// Starts at `class_name`; tries `<C>__<m>`; if not bound, looks up
// `<C>__base` (a string) and tries the parent. First match wins.
// Single-inheritance only — MRO is the linear chain. Panics with the
// full chain walked when no method is found.
// ---------------------------------------------------------------------------

fn resolve_method(
    k: &mut Kernel,
    a: &mut Arena,
    env: FrameId,
    class_name: &str,
    method_name: &str,
) -> (String, Arc<Closure>) {
    let mut current = class_name.to_string();
    let mut chain: Vec<String> = vec![current.clone()];
    loop {
        let qualified = format!("{}__{}", current, method_name);
        if let Some(name_id) = k.str_idx.get(&qualified).copied() {
            if let Some(val) = a.lookup(env, name_id) {
                if let Value::Closure(c) = val {
                    return (qualified, c);
                }
            }
        }
        // Method not found on `current` — walk to base.
        let base_key = format!("{}__base", current);
        let base_id = match k.str_idx.get(&base_key).copied() {
            Some(id) => id,
            None => {
                panic!(
                    "_dispatch: no method '{}' in inheritance chain [{}]",
                    method_name,
                    chain.join(" -> ")
                );
            }
        };
        let parent_val = match a.lookup(env, base_id) {
            Some(v) => v,
            None => {
                panic!(
                    "_dispatch: no method '{}' in inheritance chain [{}]",
                    method_name,
                    chain.join(" -> ")
                );
            }
        };
        let parent_name = match parent_val {
            Value::Str(s) => s,
            _ => panic!("_dispatch: '{}' is not a string", base_key),
        };
        if parent_name.is_empty() {
            panic!(
                "_dispatch: no method '{}' in inheritance chain [{}]",
                method_name,
                chain.join(" -> ")
            );
        }
        current = parent_name.to_string();
        chain.push(current.clone());
    }
}

// ---------------------------------------------------------------------------
// Form → Rust source JIT
// ---------------------------------------------------------------------------
//
// Sibling to the TS kernel's compileNode (recipe → JS via `new Function`).
// Pipeline:
//   1. emit_rust_function_source(k, name, params, body) → Rust source string,
//      or None if the recipe contains a node the emitter can't yet handle.
//   2. compile_rust_cdylib(src) → JitCompiled (Library + fn ptr), or None
//      on rustc failure / load failure.
//   3. dispatch at FNCALL: when the closure body NodeID is in k.jit_compiled
//      and all args are Int, call the function pointer directly.
//
// What the emitter handles structurally (every other shape falls back to a
// `compile_fail` return that aborts the compile, so the kernel never silently
// emits broken Rust):
//   - i64 arithmetic: add / sub / mul / div / mod
//   - i64 comparisons: eq / ne / lt / le / gt / ge   (yields bool)
//   - logic on bool: and / or / not
//   - if / if-else
//   - let-bindings (body is the bound value's continuation in the block)
//   - recursive free-function calls (recipes that reference each other)
//   - parameter references
//   - integer literals
//
// Lists, native calls, substrate reflection: out of scope by design — the
// walker still owns those. The compile is best-effort acceleration; failure
// is honest (returns 0 from jit_compile, recipe-walk continues).

/// Result of trying to emit a Rust expression for a Form node.
/// `Int(src)` → expression evaluates to i64.
/// `Bool(src)` → expression evaluates to bool.
/// We track the type at emit time so comparisons-in-if and i64 returns get
/// the right casts.
enum EmittedExpr {
    Int(String),
    Bool(String),
}

impl EmittedExpr {
    fn into_i64(self) -> String {
        match self {
            EmittedExpr::Int(s) => s,
            // bool→i64 via `if b { 1 } else { 0 }` keeps it C-ABI clean.
            EmittedExpr::Bool(s) => format!("(if ({}) {{ 1i64 }} else {{ 0i64 }})", s),
        }
    }

    fn into_bool(self) -> String {
        match self {
            EmittedExpr::Bool(s) => s,
            // i64→bool via `!= 0` lets Form's truthy-int convention survive.
            EmittedExpr::Int(s) => format!("(({}) != 0i64)", s),
        }
    }
}

/// Tracks compile-time scope while emitting. `vars` maps NameID → Rust
/// variable name; `siblings` maps NameID → arity (so a recursive call can
/// emit a direct Rust function call to a sibling defn).
struct EmitScope<'a> {
    vars: HashMap<NameID, String>,
    siblings: &'a HashMap<NameID, (String, usize)>,
    uid: u32,
}

impl<'a> EmitScope<'a> {
    fn new(siblings: &'a HashMap<NameID, (String, usize)>) -> Self {
        Self {
            vars: HashMap::new(),
            siblings,
            uid: 0,
        }
    }

    fn fresh(&mut self, hint: &str) -> String {
        self.uid += 1;
        let sanitized: String = hint
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || c == '_' {
                    c
                } else {
                    '_'
                }
            })
            .collect();
        format!("v_{}_{}", sanitized, self.uid)
    }
}

/// Sanitize an arbitrary string for use as a Rust identifier.
fn sanitize_rust_ident(s: &str) -> String {
    let cleaned: String = s
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    if cleaned.is_empty() {
        return "fn_".to_string();
    }
    // Rust keywords / leading-digit guard.
    if cleaned
        .chars()
        .next()
        .map(|c| c.is_ascii_digit())
        .unwrap_or(false)
    {
        format!("f_{}", cleaned)
    } else {
        format!("fn_{}", cleaned)
    }
}

/// Collect every recipe-defined sibling function discoverable from the
/// closure body. Walks BLOCK.DO/SEQ/LET-trees looking for FNDEFs at any
/// position so mutually-recursive recipes still resolve.
///
/// Returns a map of NameID → (sanitized Rust identifier, arity, body NodeID).
/// The siblings get emitted as Rust `fn name(arg0: i64, ...) -> i64` at the
/// top of the generated .rs file so calls between them link cleanly.
fn collect_siblings(
    k: &Kernel,
    body: NodeID,
    target: NameID,
    target_arity: usize,
    target_body: NodeID,
) -> HashMap<NameID, (String, usize, NodeID)> {
    let mut out: HashMap<NameID, (String, usize, NodeID)> = HashMap::new();
    // The target itself is always a sibling — recursive calls dispatch to
    // its own Rust definition (which IS `compiled_fn` exported with C ABI).
    out.insert(
        target,
        (
            sanitize_rust_ident(k.name_str(target)),
            target_arity,
            target_body,
        ),
    );
    let mut visit: Vec<NodeID> = vec![body];
    let mut seen: HashSet<NodeID> = HashSet::new();
    while let Some(n) = visit.pop() {
        if !seen.insert(n) {
            continue;
        }
        if n.level == LEVEL_TRIVIAL {
            continue;
        }
        let cat = k.category(n);
        let kids = k.children(n);
        if cat.ty == RB_FNDEF && kids.len() >= 3 {
            let name = k.ident_id(kids[0]);
            let params: Vec<NameID> = k.children(kids[1]).iter().map(|p| p.inst).collect();
            let arity = params.len();
            let fbody = kids[2];
            out.entry(name)
                .or_insert_with(|| (sanitize_rust_ident(k.name_str(name)), arity, fbody));
        }
        for c in kids {
            visit.push(c);
        }
    }
    out
}

/// Emit a single Form expression as a Rust expression. Returns None when
/// the expression contains a shape outside the JIT subset.
fn emit_expr(k: &Kernel, n: NodeID, scope: &mut EmitScope<'_>) -> Option<EmittedExpr> {
    if n.level == LEVEL_TRIVIAL {
        return match n.ty {
            TRIV_INT => {
                let v = (n.inst as i32) as i64;
                Some(EmittedExpr::Int(format!("{}i64", v)))
            }
            TRIV_BOOL => Some(EmittedExpr::Bool(if n.inst != 0 {
                "true".to_string()
            } else {
                "false".to_string()
            })),
            // STRING / NULL / FLOAT32 / FLOAT64 — not on the JIT path.
            _ => None,
        };
    }
    let cat = k.category(n);
    let kids = k.children(n);
    match cat.ty {
        RB_IDENT => {
            let name = k.ident_id(n);
            if let Some(v) = scope.vars.get(&name) {
                Some(EmittedExpr::Int(v.clone()))
            } else {
                None
            }
        }
        RB_MATH => {
            if kids.is_empty() {
                return None;
            }
            let op = match cat.inst {
                RMATH_PLUS => "+",
                RMATH_MINUS => "-",
                RMATH_MULTIPLY => "*",
                RMATH_DIVIDE => "/",
                RMATH_MODULO => "%",
                _ => return None,
            };
            let mut parts: Vec<String> = Vec::with_capacity(kids.len());
            for c in &kids {
                parts.push(emit_expr(k, *c, scope)?.into_i64());
            }
            // Wrapping arithmetic — Form recipes treat i64 overflow as wrap,
            // matching the walker's `.wrapping_*` behavior and the TS kernel's
            // `| 0` semantics for i32. We use wrapping_* so panic-free hot loops.
            let wrap_method = match cat.inst {
                RMATH_PLUS => "wrapping_add",
                RMATH_MINUS => "wrapping_sub",
                RMATH_MULTIPLY => "wrapping_mul",
                RMATH_DIVIDE => "wrapping_div",
                RMATH_MODULO => "wrapping_rem",
                _ => return None,
            };
            let mut acc = parts[0].clone();
            for p in &parts[1..] {
                acc = format!("({}).{}({})", acc, wrap_method, p);
            }
            let _ = op; // kept for symbolic clarity; wrap_method is what we emit
            Some(EmittedExpr::Int(acc))
        }
        RB_COMPARE => {
            if kids.len() != 2 {
                return None;
            }
            let op = match cat.inst {
                RCMP_EQ => "==",
                RCMP_NE => "!=",
                RCMP_LT => "<",
                RCMP_LE => "<=",
                RCMP_GT => ">",
                RCMP_GE => ">=",
                _ => return None,
            };
            let a = emit_expr(k, kids[0], scope)?.into_i64();
            let b = emit_expr(k, kids[1], scope)?.into_i64();
            Some(EmittedExpr::Bool(format!("(({}) {} ({}))", a, op, b)))
        }
        RB_LOGIC => match cat.inst {
            RLOG_NOT => {
                if kids.len() != 1 {
                    return None;
                }
                let a = emit_expr(k, kids[0], scope)?.into_bool();
                Some(EmittedExpr::Bool(format!("(!({}))", a)))
            }
            RLOG_AND | RLOG_OR => {
                let op = if cat.inst == RLOG_AND { "&&" } else { "||" };
                let mut parts: Vec<String> = Vec::new();
                for c in &kids {
                    parts.push(emit_expr(k, *c, scope)?.into_bool());
                }
                Some(EmittedExpr::Bool(format!(
                    "({})",
                    parts.join(&format!(" {} ", op))
                )))
            }
            _ => None,
        },
        RB_COND => {
            match cat.inst {
                RCOND_IF => {
                    if kids.len() != 2 {
                        return None;
                    }
                    let c = emit_expr(k, kids[0], scope)?.into_bool();
                    let t = emit_expr(k, kids[1], scope)?.into_i64();
                    // No `else` in Form — TS encodes as `null`; we encode as 0
                    // (only sound when the recipe author never reads the result
                    // of a no-else `if`; fib/fact patterns always pair if with
                    // else, so this rarely fires).
                    Some(EmittedExpr::Int(format!(
                        "(if ({}) {{ {} }} else {{ 0i64 }})",
                        c, t
                    )))
                }
                RCOND_IF_ELSE => {
                    if kids.len() != 3 {
                        return None;
                    }
                    let c = emit_expr(k, kids[0], scope)?.into_bool();
                    let t = emit_expr(k, kids[1], scope)?.into_i64();
                    let e = emit_expr(k, kids[2], scope)?.into_i64();
                    Some(EmittedExpr::Int(format!(
                        "(if ({}) {{ {} }} else {{ {} }})",
                        c, t, e
                    )))
                }
                _ => None,
            }
        }
        RB_BLOCK => {
            // LET binds and the block evaluates to its last expression.
            // We emit a Rust block `{ let v = ...; ...; tail }`.
            match cat.inst {
                RBLK_LET => {
                    // LET shape in this kernel: kids = [name-trivial, value, ...continuation?]
                    // Form-on-top emits LET as a single (name, value) pair in
                    // most surfaces; multi-form continuations appear only inside DO.
                    if kids.len() < 2 {
                        return None;
                    }
                    let name_node = kids[0];
                    if name_node.level != LEVEL_TRIVIAL || name_node.ty != TRIV_STRING {
                        return None;
                    }
                    let name_id = name_node.inst;
                    let value_src = emit_expr(k, kids[1], scope)?.into_i64();
                    let var = scope.fresh(k.name_str(name_id));
                    // LET's expression value, in the walker, is the bound
                    // value itself. Subsequent forms in the surrounding DO
                    // pick up the binding via scope.vars.
                    scope.vars.insert(name_id, var.clone());
                    Some(EmittedExpr::Int(format!(
                        "{{ let {} = {}; {} }}",
                        var, value_src, var
                    )))
                }
                RBLK_DO | RBLK_SEQ => {
                    if kids.is_empty() {
                        return Some(EmittedExpr::Int("0i64".to_string()));
                    }
                    // DO produces a Rust block. Each inner form becomes a
                    // statement; the last is the block's expression value.
                    // LET inside DO binds for subsequent forms — we mutate
                    // scope.vars in-place, mirroring how the walker layers
                    // bindings into the same frame.
                    let mut stmts: Vec<String> = Vec::new();
                    let mut tail: Option<String> = None;
                    for (i, c) in kids.iter().enumerate() {
                        let is_last = i == kids.len() - 1;
                        // Inline LET specially so the binding stays in scope
                        // for siblings within the DO block.
                        let cat_c = k.category(*c);
                        if cat_c.ty == RB_BLOCK && cat_c.inst == RBLK_LET {
                            let kc = k.children(*c);
                            if kc.len() < 2
                                || kc[0].level != LEVEL_TRIVIAL
                                || kc[0].ty != TRIV_STRING
                            {
                                return None;
                            }
                            let name_id = kc[0].inst;
                            let value_src = emit_expr(k, kc[1], scope)?.into_i64();
                            let var = scope.fresh(k.name_str(name_id));
                            scope.vars.insert(name_id, var.clone());
                            if is_last {
                                stmts.push(format!("let {} = {};", var, value_src));
                                tail = Some(var);
                            } else {
                                stmts.push(format!("let {} = {};", var, value_src));
                            }
                        } else {
                            let expr = emit_expr(k, *c, scope)?.into_i64();
                            if is_last {
                                tail = Some(expr);
                            } else {
                                // Side-effect-bearing inner forms aren't in
                                // the JIT subset — only let-bindings, math,
                                // and tail expressions. A pure inner expression
                                // we can simply discard with `let _ = ...;`.
                                stmts.push(format!("let _ = {};", expr));
                            }
                        }
                    }
                    let body = format!(
                        "{{ {} {} }}",
                        stmts.join(" "),
                        tail.unwrap_or_else(|| "0i64".to_string())
                    );
                    Some(EmittedExpr::Int(body))
                }
                _ => None,
            }
        }
        RB_FNCALL => {
            if kids.is_empty() {
                return None;
            }
            let callee = kids[0];
            // Resolve callee name — either bare string-trivial (parser-fast
            // path) or an IDENT wrapping a string-trivial.
            let nameid = if callee.level == LEVEL_TRIVIAL && callee.ty == TRIV_STRING {
                callee.inst
            } else if k.category(callee).ty == RB_IDENT {
                k.ident_id(callee)
            } else {
                return None;
            };
            // Sibling Form fn?
            if let Some((rust_name, arity)) = scope.siblings.get(&nameid) {
                if kids.len() - 1 != *arity {
                    return None;
                }
                let mut args: Vec<String> = Vec::with_capacity(*arity);
                for a in &kids[1..] {
                    args.push(emit_expr(k, *a, scope)?.into_i64());
                }
                return Some(EmittedExpr::Int(format!(
                    "{}({})",
                    rust_name,
                    args.join(", ")
                )));
            }
            // Unknown callee — would need to call back into the walker, which
            // the JIT subset doesn't support. Caller falls back.
            None
        }
        // FNDEF appears inside DO blocks for nested recipes. The sibling
        // collector already discovered them and they get emitted as Rust
        // fns. An FNDEF expression itself evaluates to the closure value;
        // in the JIT subset we represent it as 0 (the def already happened
        // at the Rust top-level — this is a placeholder so DO continues).
        RB_FNDEF => Some(EmittedExpr::Int("0i64".to_string())),
        _ => None,
    }
}

/// Emit the full Rust source for a top-level closure. The exported symbol
/// `compiled_fn` carries the C ABI; internal sibling defns become regular
/// Rust functions in the same crate. Returns None if any node in the body
/// (or any reachable sibling body) is outside the JIT subset.
fn emit_rust_source(
    k: &Kernel,
    target_name: NameID,
    target_params: &[NameID],
    target_body: NodeID,
) -> Option<String> {
    let siblings_full = collect_siblings(
        k,
        target_body,
        target_name,
        target_params.len(),
        target_body,
    );
    // Strip body NodeIDs for the scope (the scope just needs name → (rust_name, arity)).
    let siblings: HashMap<NameID, (String, usize)> = siblings_full
        .iter()
        .map(|(k, (rn, ar, _))| (*k, (rn.clone(), *ar)))
        .collect();

    // Emit every sibling, target last.
    let mut emitted_fns: Vec<String> = Vec::new();
    let mut target_rust_name = String::new();
    for (name, (rust_name, arity, body)) in &siblings_full {
        let params: Vec<NameID> = if *name == target_name {
            target_params.to_vec()
        } else {
            // Sibling — find the FNDEF that registered it and pull params.
            // We re-traverse to recover the params list (small cost; emit is rare).
            find_fndef_params(k, target_body, *name)?
        };
        if params.len() != *arity {
            return None;
        }
        if params.len() > JIT_MAX_ARITY {
            return None;
        }
        let mut scope = EmitScope::new(&siblings);
        let mut param_decls: Vec<String> = Vec::new();
        for (i, p) in params.iter().enumerate() {
            let var = format!("a{}", i);
            scope.vars.insert(*p, var.clone());
            param_decls.push(format!("{}: i64", var));
        }
        let body_src = emit_expr(k, *body, &mut scope)?.into_i64();
        let is_target = *name == target_name;
        if is_target {
            target_rust_name = rust_name.clone();
            // Target gets two definitions: the internal one and a C-ABI
            // wrapper. This way recursive sibling calls go through the
            // internal Rust fn (zero-overhead), while the external loader
            // gets a stable symbol.
            emitted_fns.push(format!(
                "fn {}({}) -> i64 {{ {} }}",
                rust_name,
                param_decls.join(", "),
                body_src
            ));
        } else {
            emitted_fns.push(format!(
                "fn {}({}) -> i64 {{ {} }}",
                rust_name,
                param_decls.join(", "),
                body_src
            ));
        }
    }

    // C-ABI wrapper for the target. Arity-specific signature: callers
    // dispatch through a match on arity at the call site, casting the raw
    // pointer to the exactly-shaped `unsafe extern "C" fn(i64,…,i64) -> i64`.
    let arity = target_params.len();
    let params: Vec<String> = (0..arity).map(|i| format!("a{}: i64", i)).collect();
    let args: Vec<String> = (0..arity).map(|i| format!("a{}", i)).collect();
    let wrapper = format!(
        "#[no_mangle]\npub extern \"C\" fn compiled_fn({}) -> i64 {{ {}({}) }}",
        params.join(", "),
        target_rust_name,
        args.join(", ")
    );

    // Header: silence the unused-fn lint that fires when a sibling defn
    // isn't called by the body (rare but possible — author left a helper
    // they didn't end up using).
    let header = "#![allow(unused)]\n#![allow(dead_code)]\n";
    Some(format!(
        "{}\n{}\n\n{}\n",
        header,
        emitted_fns.join("\n\n"),
        wrapper
    ))
}

/// Walk the recipe tree starting at `root` and return the params NameIDs
/// for the FNDEF whose name matches `target`. Returns None if not found.
fn find_fndef_params(k: &Kernel, root: NodeID, target: NameID) -> Option<Vec<NameID>> {
    let mut visit: Vec<NodeID> = vec![root];
    let mut seen: HashSet<NodeID> = HashSet::new();
    while let Some(n) = visit.pop() {
        if !seen.insert(n) {
            continue;
        }
        if n.level == LEVEL_TRIVIAL {
            continue;
        }
        let cat = k.category(n);
        let kids = k.children(n);
        if cat.ty == RB_FNDEF && kids.len() >= 3 {
            let name = k.ident_id(kids[0]);
            if name == target {
                return Some(k.children(kids[1]).iter().map(|p| p.inst).collect());
            }
        }
        for c in kids {
            visit.push(c);
        }
    }
    None
}

/// Compile a Rust source string to a cdylib and load it. Returns None on
/// any failure — rustc not in PATH, compile error, library load error.
/// Caller treats None as honest "compile unavailable" and returns 0 from
/// jit_compile so Form code branches on availability.
fn compile_rust_cdylib(src: &str, arity: usize) -> Option<JitCompiled> {
    // Unique temp dir per compile — multiple JIT calls in one session
    // don't fight for the same lib.rs / plugin.so file.
    let mut temp = std::env::temp_dir();
    let nonce = format!(
        "form-rust-jit-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
    );
    temp.push(nonce);
    if fs::create_dir_all(&temp).is_err() {
        return None;
    }
    let src_path = temp.join("lib.rs");
    let out_path = temp.join("plugin.so");
    if fs::write(&src_path, src).is_err() {
        return None;
    }
    // Invoke rustc. -C opt-level=2 is the sweet spot — most of the gain
    // for a small fraction of the compile cost. We pass --edition=2021
    // explicitly so the host's rustc default doesn't change behavior.
    let status = Command::new("rustc")
        .arg("--crate-type=cdylib")
        .arg("--edition=2021")
        .arg("-C")
        .arg("opt-level=2")
        .arg("-o")
        .arg(&out_path)
        .arg(&src_path)
        .stderr(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .status();
    let status = match status {
        Ok(s) => s,
        Err(_) => {
            // rustc not in PATH — cleanup and bail. The Form sample stays
            // honest: compile-attempted=1 (we tried), recipe walks instead.
            let _ = fs::remove_dir_all(&temp);
            return None;
        }
    };
    if !status.success() {
        let _ = fs::remove_dir_all(&temp);
        return None;
    }
    // Load the .so. libloading::Library::new is unsafe because the dynamic
    // linker can run arbitrary init code in the loaded image. We trust the
    // .so because we just emitted its source from a Form recipe and built
    // it with the same rustc this process trusts.
    let library = match unsafe { libloading::Library::new(&out_path) } {
        Ok(l) => l,
        Err(_) => {
            let _ = fs::remove_dir_all(&temp);
            return None;
        }
    };
    // Resolve the symbol. We immediately extract the raw pointer so the
    // Library can outlive the Symbol (Symbol borrows the Library, but the
    // raw pointer is just an address that's valid as long as the .so stays
    // mapped — and the Library staying alive guarantees that).
    let func_ptr: *const () = unsafe {
        let sym: libloading::Symbol<unsafe extern "C" fn() -> i64> =
            match library.get(b"compiled_fn") {
                Ok(s) => s,
                Err(_) => {
                    let _ = fs::remove_dir_all(&temp);
                    return None;
                }
            };
        // Cast through *const () so callers can re-cast to the arity-
        // specific signature. raw_pointer is the dlsym address.
        *sym.into_raw() as *const ()
    };
    Some(JitCompiled {
        _library: library,
        func: func_ptr,
        arity,
        _temp_dir: temp,
    })
}

/// Dispatch a call through a loaded JitCompiled. Returns None if the args
/// don't all unbox to i64 (the caller must fall back to recipe-walk).
///
/// SAFETY: We loaded the .so via libloading and the Library handle is kept
/// alive by Arc<JitCompiled>. The function signature is arity-specific i64→i64.
/// The cast and call happen inside a single unsafe block so the contract is
/// localized. The body of the function was emitted from a Form recipe via
/// our own emit_rust_source — same crate this kernel was built with — so
/// ABI compatibility is guaranteed.
fn jit_dispatch(jc: &JitCompiled, args: &[Value]) -> Option<Value> {
    if args.len() != jc.arity {
        return None;
    }
    let mut i64s: Vec<i64> = Vec::with_capacity(args.len());
    for a in args {
        match a {
            Value::Int(n) => i64s.push(*n),
            Value::Bool(b) => i64s.push(if *b { 1 } else { 0 }),
            _ => return None,
        }
    }
    let p = jc.func;
    let result: i64 = unsafe {
        match i64s.len() {
            0 => {
                let f: unsafe extern "C" fn() -> i64 = std::mem::transmute(p);
                f()
            }
            1 => {
                let f: unsafe extern "C" fn(i64) -> i64 = std::mem::transmute(p);
                f(i64s[0])
            }
            2 => {
                let f: unsafe extern "C" fn(i64, i64) -> i64 = std::mem::transmute(p);
                f(i64s[0], i64s[1])
            }
            3 => {
                let f: unsafe extern "C" fn(i64, i64, i64) -> i64 = std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2])
            }
            4 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64) -> i64 = std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2], i64s[3])
            }
            5 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2], i64s[3], i64s[4])
            }
            6 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(i64s[0], i64s[1], i64s[2], i64s[3], i64s[4], i64s[5])
            }
            7 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(
                    i64s[0], i64s[1], i64s[2], i64s[3], i64s[4], i64s[5], i64s[6],
                )
            }
            8 => {
                let f: unsafe extern "C" fn(i64, i64, i64, i64, i64, i64, i64, i64) -> i64 =
                    std::mem::transmute(p);
                f(
                    i64s[0], i64s[1], i64s[2], i64s[3], i64s[4], i64s[5], i64s[6], i64s[7],
                )
            }
            _ => return None,
        }
    };
    Some(Value::Int(result))
}

// ---------------------------------------------------------------------------
// Walker — full RBasic dispatch
// ---------------------------------------------------------------------------

fn is_switch_default_pattern(k: &Kernel, pattern: NodeID) -> bool {
    if pattern.level == LEVEL_TRIVIAL {
        return false;
    }
    let cat = k.category(pattern);
    cat.ty == RB_IDENT && k.name_str(k.ident_id(pattern)) == "_"
}

fn switch_table_for(k: &mut Kernel, node: NodeID, kids: &[NodeID]) -> SwitchTable {
    if let Some(table) = k.switch_tables.get(&node) {
        return table.clone();
    }
    let mut table = SwitchTable::default();
    for i in (1..kids.len()).step_by(2) {
        let pattern = kids[i];
        let body = kids[i + 1];
        if is_switch_default_pattern(k, pattern) {
            table.default_body = Some(body);
        } else if pattern.level == LEVEL_TRIVIAL {
            table.cases.insert(pattern, body);
        } else {
            table.dynamic_arms.push(SwitchArm { pattern, body });
        }
    }
    k.switch_tables.insert(node, table.clone());
    table
}

fn switch_key_from_value(k: &mut Kernel, v: &Value) -> Option<NodeID> {
    match v {
        Value::Null => Some(NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_NULL,
            inst: 0,
        }),
        Value::Int(n) => Some(k.intern_trivial_int(*n)),
        Value::Float(f) => Some(k.intern_trivial_float64(*f)),
        Value::Str(s) => Some(k.intern_string(s)),
        Value::Bool(b) => Some(NodeID {
            pkg: 1,
            level: LEVEL_TRIVIAL,
            ty: TRIV_BOOL,
            inst: if *b { 1 } else { 0 },
        }),
        Value::Nid(nid) => Some(*nid),
        _ => None,
    }
}

// bool_int — the truth family's acknowledgment shape: 0/1 integer states
// (axiom-1) so eq/lt/and/not/node_eq/… answers feed arithmetic on every kernel.
fn bool_int(b: bool) -> Value {
    Value::Int(b as i64)
}

fn value_equal(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Int(x), Value::Int(y)) => x == y,
        (Value::Float(x), Value::Float(y)) => x == y,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::Bool(x), Value::Bool(y)) => x == y,
        (Value::Nid(x), Value::Nid(y)) => x == y,
        (Value::List(xs), Value::List(ys)) => {
            xs.len() == ys.len() && xs.iter().zip(ys.iter()).all(|(x, y)| value_equal(x, y))
        }
        _ => false,
    }
}

fn walk_match_switch(
    k: &mut Kernel,
    a: &mut Arena,
    node: NodeID,
    kids: &[NodeID],
    env: FrameId,
) -> Value {
    if kids.len() < 1 || (kids.len() - 1) % 2 != 0 {
        panic!("match: SWITCH expects scrutinee plus pattern/body pairs");
    }
    if let Some(t) = &mut k.trace {
        t.record_match_lookup();
    }
    let scrutinee = walk(k, a, kids[0], env);
    let table = switch_table_for(k, node, kids);
    if let Some(key) = switch_key_from_value(k, &scrutinee) {
        if let Some(body) = table.cases.get(&key).copied() {
            if let Some(t) = &mut k.trace {
                t.record_match_hit();
            }
            return walk(k, a, body, env);
        }
    }
    for arm in table.dynamic_arms {
        if value_equal(&walk(k, a, arm.pattern, env), &scrutinee) {
            if let Some(t) = &mut k.trace {
                t.record_match_hit();
            }
            return walk(k, a, arm.body, env);
        }
    }
    if let Some(body) = table.default_body {
        if let Some(t) = &mut k.trace {
            t.record_match_default();
        }
        return walk(k, a, body, env);
    }
    if let Some(t) = &mut k.trace {
        t.record_match_miss();
    }
    panic!(
        "match: exhausted without a matching arm for {}",
        scrutinee.display()
    );
}

// walk — public entry. Wraps walk_inner with stack-discipline frame
// reclamation: the frames pushed during this call are popped on return, unless
// a closure was created (it captures a FrameId, so its frames must survive).
// This keeps the arena bounded — the recursive-descent BML parse pushes a frame
// per combinator call and per cursor step; un-reclaimed they grew the arena to
// gigabytes on a 15 KB file. Nested walks each truncate to their OWN entry mark,
// so every pre-existing frame (including an active call frame the caller still
// needs) is preserved. Mirrors how the Go kernel's GC reclaims dead *Frames.
pub(crate) fn walk(k: &mut Kernel, a: &mut Arena, n: NodeID, env: FrameId) -> Value {
    let frame_mark = a.frames.len();
    let clo_mark = a.closures_created;
    let r = walk_inner(k, a, n, env);
    if a.closures_created == clo_mark {
        a.frames.truncate(frame_mark);
    }
    r
}

fn walk_inner(k: &mut Kernel, a: &mut Arena, n: NodeID, env: FrameId) -> Value {
    // TCO: a tail-position call — a closure body, a cond branch, or a do/seq
    // block's last expr — reassigns n/env and loops here instead of recursing,
    // so tail-recursive Form loops (gm-rep-loop, gm-sep-loop, caps-get, …) run
    // in CONSTANT stack. Result-transparent; far less stack — what lets this
    // kernel parse the full thesis grammar files without overflowing.
    let mut n = n;
    let mut env = env;
    loop {
        if n.level == LEVEL_TRIVIAL {
            return k.trivial_value(n);
        }
        let cat = k.category(n);
        // Tracing hook: when k.trace is Some, record the arm dispatch. Pure
        // counter increment — no allocation, no IO. Per lc-native-kernel-binary
        // "tracing and observation pattern". Records (ty, inst) so typed-numeric
        // distribution (MATH.PLUS_F64 vs MATH.PLUS_I32) stays distinguishable.
        if let Some(t) = &mut k.trace {
            t.record(cat.ty, cat.inst);
        }
        let kids = k.children(n);

        return match cat.ty {
            RB_MATH => {
                let lv = walk(k, a, kids[0], env);
                let rv = walk(k, a, kids[1], env);
                // Width promotion: if either operand is Float, the result is
                // Float (matches Python `int + float → float`, and IEEE 754
                // arithmetic on mixed inputs). Pure int/int stays on the
                // fast i64 path.
                if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                    let l = lv.as_float();
                    let r = rv.as_float();
                    Value::Float(match cat.inst {
                        RMATH_PLUS => l + r,
                        RMATH_MINUS => l - r,
                        RMATH_MULTIPLY => l * r,
                        RMATH_DIVIDE => l / r,
                        RMATH_MODULO => l - (l / r).floor() * r,
                        _ => panic!("math.f64: unknown op {}", cat.inst),
                    })
                } else {
                    let l = lv.as_int();
                    let r = rv.as_int();
                    Value::Int(match cat.inst {
                        RMATH_PLUS => l + r,
                        RMATH_MINUS => l - r,
                        RMATH_MULTIPLY => l * r,
                        RMATH_DIVIDE => l / r,
                        RMATH_MODULO => l % r,
                        _ => panic!("math: unknown op {}", cat.inst),
                    })
                }
            }
            RB_COMPARE => {
                let lv = walk(k, a, kids[0], env);
                let rv = walk(k, a, kids[1], env);
                // Same width-promotion rule as math: float on either side
                // forces an IEEE comparison. Pure int/int stays integer.
                // A comparison acknowledges with the 0/1 integer states
                // (axiom-1, core-axioms.form) so its answer flows directly
                // into arithmetic — the same shape the JIT's i64 ABI already
                // lands. Proven three-way by tests/eq-shape-band.fk.
                if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                    let l = lv.as_float();
                    let r = rv.as_float();
                    bool_int(match cat.inst {
                        RCMP_EQ => l == r,
                        RCMP_NE => l != r,
                        RCMP_LT => l < r,
                        RCMP_LE => l <= r,
                        RCMP_GT => l > r,
                        RCMP_GE => l >= r,
                        _ => panic!("compare.f64: unknown op {}", cat.inst),
                    })
                } else {
                    let l = lv.as_int();
                    let r = rv.as_int();
                    bool_int(match cat.inst {
                        RCMP_EQ => l == r,
                        RCMP_NE => l != r,
                        RCMP_LT => l < r,
                        RCMP_LE => l <= r,
                        RCMP_GT => l > r,
                        RCMP_GE => l >= r,
                        _ => panic!("compare: unknown op {}", cat.inst),
                    })
                }
            }
            RB_LOGIC => match cat.inst {
                // Logic answers join the comparison family's 0/1 integer
                // states (axiom-1) — truth has one value shape, so
                // (mul (and ...) n) flows exactly like (mul (eq ...) n).
                RLOG_AND => {
                    if !walk(k, a, kids[0], env).as_bool() {
                        bool_int(false)
                    } else {
                        bool_int(walk(k, a, kids[1], env).as_bool())
                    }
                }
                RLOG_OR => {
                    if walk(k, a, kids[0], env).as_bool() {
                        bool_int(true)
                    } else {
                        bool_int(walk(k, a, kids[1], env).as_bool())
                    }
                }
                RLOG_NOT => bool_int(!walk(k, a, kids[0], env).as_bool()),
                _ => panic!("logic: unknown op {}", cat.inst),
            },
            RB_COND => {
                if walk(k, a, kids[0], env).as_bool() {
                    n = kids[1]; // TCO: taken branch is in tail position
                    continue;
                } else if cat.inst == RCOND_IF_ELSE && kids.len() >= 3 {
                    n = kids[2]; // TCO: else branch is in tail position
                    continue;
                } else {
                    Value::Null
                }
            }
            RB_MATCH => {
                if cat.inst == RMATCH_SWITCH {
                    walk_match_switch(k, a, n, &kids, env)
                } else {
                    Value::Nid(n)
                }
            }
            RB_BLOCK => {
                if cat.inst == RBLK_LET {
                    let name = k.ident_id(kids[0]);
                    let v = walk(k, a, kids[1], env);
                    a.bind(env, name, v.clone());
                    return v;
                }
                if kids.is_empty() {
                    Value::Null
                } else {
                    let last = kids.len() - 1;
                    for c in &kids[..last] {
                        walk(k, a, *c, env);
                    }
                    n = kids[last]; // TCO: a do/seq block's last expr is in tail position
                    continue;
                }
            }
            RB_IDENT => {
                let id = k.ident_id(n);
                a.lookup(env, id)
                    .unwrap_or_else(|| panic!("unbound: {}", k.name_str(id)))
            }
            RB_FNDEF => {
                let name = k.ident_id(kids[0]);
                let params: Vec<NameID> = k.children(kids[1]).iter().map(|p| p.inst).collect();
                let cl = Arc::new(Closure {
                    name,
                    params,
                    body: kids[2],
                    env,
                });
                // This closure captures `env`; record it so the walk wrapper
                // will not reclaim frames at/above its definition mark.
                a.closures_created += 1;
                a.bind(env, name, Value::Closure(cl.clone()));
                Value::Closure(cl)
            }
            RB_FNCALL => {
                let raw_name = k.ident_id(kids[0]);
                // JIT alias: if a Form function-name is JIT-registered, swap to
                // the aliased native-name before native lookup. Form recipes are
                // the canonical truth; `register_jit form-name native-name` opts
                // calls into a kernel-resident optimized native.
                let name = k.jit_aliases.get(&raw_name).copied().unwrap_or(raw_name);
                // Env-aware natives first — they need caller env (walk_recipe_here).
                let env_ne_opt = k.env_natives.get(&name).copied();
                if let Some(ne) = env_ne_opt {
                    if a.lookup(env, name).is_none() {
                        let mut args = Vec::with_capacity(kids.len() - 1);
                        for arg in &kids[1..] {
                            args.push(walk(k, a, *arg, env));
                        }
                        if ne.category.ty != RB_UNDEFINED {
                            if let Some(t) = &mut k.trace {
                                t.record(ne.category.ty, ne.category.inst);
                            }
                        }
                        let native_name = k.name_str(ne.name).to_string();
                        if let Some(t) = &mut k.trace {
                            t.record_native(&native_name);
                        }
                        return (ne.func)(k, a, env, &args);
                    }
                }
                // Native takes priority unless user shadowed. Copy the entry
                // out so the natives-map borrow releases before we call &mut k.
                let ne_opt = k.natives.get(&name).copied();
                if let Some(ne) = ne_opt {
                    if a.lookup(env, name).is_none() {
                        let mut args = Vec::with_capacity(kids.len() - 1);
                        for arg in &kids[1..] {
                            args.push(walk(k, a, *arg, env));
                        }
                        // Native Blueprint attribution — record the Form
                        // category the native expresses alongside the FNCALL
                        // arm already recorded above. Trace now reflects the
                        // structural shape of the work, not just the dispatch
                        // mechanism.
                        if ne.category.ty != RB_UNDEFINED {
                            if let Some(t) = &mut k.trace {
                                t.record(ne.category.ty, ne.category.inst);
                            }
                        }
                        let native_name = k.name_str(ne.name).to_string();
                        if let Some(t) = &mut k.trace {
                            t.record_native(&native_name);
                        }
                        return (ne.func)(k, a, &args);
                    }
                }
                // Closure lookup uses the ORIGINAL function-name (not the JIT-
                // aliased one) — the user defined this function and wants to
                // call THEIR version when no JIT mapping resolved a native.
                let callee = a
                    .lookup(env, raw_name)
                    .unwrap_or_else(|| panic!("unbound function: {}", k.name_str(raw_name)));
                let cl = match callee {
                    Value::Closure(c) => c,
                    _ => panic!("not callable: {}", k.name_str(name)),
                };
                if kids.len() - 1 != cl.params.len() {
                    panic!(
                        "{} wants {} args, got {}",
                        k.name_str(name),
                        cl.params.len(),
                        kids.len() - 1
                    );
                }
                let call_frame = a.new_frame_with_capacity(Some(cl.env), cl.params.len());
                // Evaluate args in CALLER's env, then bind in call_frame.
                // We collect them into `arg_values` first so the JIT dispatch
                // path can use them directly without re-walking from the frame.
                // The clone is Arc<Closure> — bump-the-refcount, not deep.
                let cl2 = cl.clone();
                let mut arg_values: Vec<Value> = Vec::with_capacity(cl2.params.len());
                for (i, p) in cl2.params.iter().enumerate() {
                    let arg = walk(k, a, kids[i + 1], env);
                    arg_values.push(arg.clone());
                    a.bind(call_frame, *p, arg);
                }
                let fn_name = k.name_str(cl.name).to_string();
                if let Some(t) = &mut k.trace {
                    t.record_fn(&fn_name);
                }
                // JIT-compiled fast path: if (jit_compile "name") landed for
                // this closure's body, dispatch through the loaded function
                // pointer. Form recipe stays canonical truth; the .so is opt-in
                // bootstrap to host-native speed. Sibling-attested: TS uses
                // V8's `new Function`; Go uses `plugin.Open`; Rust uses
                // libloading over a rustc-produced cdylib. Same observable
                // result, three real host-native paths.
                //
                // We hold an Arc<JitCompiled> through the call so the Library
                // can't be dropped mid-call (kernel mutation is safe; the Arc
                // bumps refcount synchronously).
                if let Some(jc) = k.jit_compiled.get(&cl.body).cloned() {
                    if let Some(v) = jit_dispatch(&jc, &arg_values) {
                        return v;
                    }
                    // Args don't unbox to i64 — fall back to the walker.
                    // This preserves Form semantics for closures over non-int
                    // values (lists, strings, closures) even after jit_compile
                    // succeeded for the integer-only path.
                } else if !k.jit_failed.contains(&cl.body) {
                    // MEASURED REPETITION: no manual jit_compile needed. Count calls
                    // to this undecided recipe; at the threshold, attempt the SAME
                    // compile jit_compile does. Success → every later call dispatches
                    // native (the branch above). Failure (a shape outside the JIT
                    // subset, e.g. strings/lists) → mark it failed so it is tried
                    // once, never on every call. A decided recipe carries no counter.
                    let hits = {
                        let c = k.jit_hits.entry(cl.body).or_insert(0u32);
                        *c += 1;
                        *c
                    };
                    if hits >= JIT_HOT_THRESHOLD {
                        let compiled = emit_rust_source(k, cl.name, &cl.params, cl.body)
                            .and_then(|src| compile_rust_cdylib(&src, cl.params.len()));
                        match compiled {
                            Some(jc) => {
                                k.jit_compiled.insert(cl.body, Arc::new(jc));
                            }
                            None => {
                                k.jit_failed.insert(cl.body);
                            }
                        }
                        k.jit_hits.remove(&cl.body);
                    }
                }
                n = cl.body; // TCO: a closure body is in tail position — loop, don't recurse
                env = call_frame;
                continue;
            }
            RB_LIST => {
                let mut out = Vec::with_capacity(kids.len());
                for c in &kids {
                    out.push(walk(k, a, *c, env));
                }
                Value::List(out.into())
            }
            // Structural passthrough — categories the walker can't yet execute
            // (CHOICE_MATCH, CONSTRUCTOR, INDUCTIVE, QUOTIENT, ALIAS, BLANKET,
            // PROJECT, GENERATIVE, PROOF, INFERENCE, VECTOR, TILE, PARALLELIZE,
            // VECTORIZE, OBSERVER, TRANSMUTE, ...) intern fine and the trace
            // records their attribution. Walking returns the NodeID itself so
            // downstream structural reasoning continues. Sibling-parity with
            // TS kernel's behavior. The honest stance: "this kernel knows the
            // shape exists but cannot yet execute its semantics; the substrate
            // identity is preserved." Replaces the prior panic — kernels are
            // no longer fragile in face of recipes from richer dialects.
            _ => Value::Nid(n),
        };
    }
}

// ---------------------------------------------------------------------------
// S-expression source adapter — text → recipe tree
// ---------------------------------------------------------------------------

// SexpTok — source-reader cell. Carries 1-based line/col so parse
// errors can point at the source. Without this, every paren imbalance
// surfaces as an unhelpful "index out of bounds" panic.
#[derive(Debug, Clone)]
struct SexpTok {
    kind: &'static str,
    value: String,
    line: u32,
    col: u32,
}

fn tokenize_sexp(src: &str) -> Vec<SexpTok> {
    let bytes = src.as_bytes();
    let mut toks = Vec::with_capacity(64);
    let mut i = 0;
    let mut line: u32 = 1;
    let mut col: u32 = 1;
    while i < bytes.len() {
        let c = bytes[i];
        let (sline, scol) = (line, col);
        match c {
            b'\n' => {
                i += 1;
                line += 1;
                col = 1;
            }
            b' ' | b'\t' | b'\r' => {
                i += 1;
                col += 1;
            }
            b';' => {
                while i < bytes.len() && bytes[i] != b'\n' {
                    i += 1;
                }
                // newline handled by outer loop
            }
            b'(' => {
                toks.push(SexpTok {
                    kind: "LPAREN",
                    value: "(".into(),
                    line: sline,
                    col: scol,
                });
                i += 1;
                col += 1;
            }
            b')' => {
                toks.push(SexpTok {
                    kind: "RPAREN",
                    value: ")".into(),
                    line: sline,
                    col: scol,
                });
                i += 1;
                col += 1;
            }
            b'"' => {
                i += 1;
                col += 1;
                let start = i;
                while i < bytes.len() && bytes[i] != b'"' {
                    if bytes[i] == b'\\' && i + 1 < bytes.len() {
                        i += 2;
                        col += 2;
                        continue;
                    }
                    if bytes[i] == b'\n' {
                        line += 1;
                        col = 1;
                    } else {
                        col += 1;
                    }
                    i += 1;
                }
                let raw = &src[start..i];
                toks.push(SexpTok {
                    kind: "STRING",
                    value: unescape(raw),
                    line: sline,
                    col: scol,
                });
                if i < bytes.len() {
                    i += 1;
                    col += 1;
                }
            }
            b'0'..=b'9' => {
                let start = i;
                while i < bytes.len() && bytes[i].is_ascii_digit() {
                    i += 1;
                }
                // Float: digits '.' digits, optionally with an exponent.
                // The dot must be followed by a digit so `(.foo bar)` and
                // bare integers stay legible. Sibling-parity: TS reader
                // recognises the same shape.
                let is_float =
                    i + 1 < bytes.len() && bytes[i] == b'.' && bytes[i + 1].is_ascii_digit();
                if is_float {
                    i += 1; // consume '.'
                    while i < bytes.len() && bytes[i].is_ascii_digit() {
                        i += 1;
                    }
                    // Optional exponent: [eE][+-]?[0-9]+
                    if i < bytes.len() && (bytes[i] == b'e' || bytes[i] == b'E') {
                        i += 1;
                        if i < bytes.len() && (bytes[i] == b'+' || bytes[i] == b'-') {
                            i += 1;
                        }
                        while i < bytes.len() && bytes[i].is_ascii_digit() {
                            i += 1;
                        }
                    }
                    toks.push(SexpTok {
                        kind: "FLOAT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                } else {
                    toks.push(SexpTok {
                        kind: "INT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                }
                col += (i - start) as u32;
            }
            b'-' if i + 1 < bytes.len() && bytes[i + 1].is_ascii_digit() => {
                let start = i;
                i += 1;
                while i < bytes.len() && bytes[i].is_ascii_digit() {
                    i += 1;
                }
                let is_float =
                    i + 1 < bytes.len() && bytes[i] == b'.' && bytes[i + 1].is_ascii_digit();
                if is_float {
                    i += 1;
                    while i < bytes.len() && bytes[i].is_ascii_digit() {
                        i += 1;
                    }
                    if i < bytes.len() && (bytes[i] == b'e' || bytes[i] == b'E') {
                        i += 1;
                        if i < bytes.len() && (bytes[i] == b'+' || bytes[i] == b'-') {
                            i += 1;
                        }
                        while i < bytes.len() && bytes[i].is_ascii_digit() {
                            i += 1;
                        }
                    }
                    toks.push(SexpTok {
                        kind: "FLOAT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                } else {
                    toks.push(SexpTok {
                        kind: "INT",
                        value: src[start..i].to_string(),
                        line: sline,
                        col: scol,
                    });
                }
                col += (i - start) as u32;
            }
            _ => {
                let start = i;
                while i < bytes.len() {
                    let cc = bytes[i];
                    if cc == b' '
                        || cc == b'\t'
                        || cc == b'\n'
                        || cc == b'\r'
                        || cc == b'('
                        || cc == b')'
                        || cc == b'"'
                        || cc == b';'
                    {
                        break;
                    }
                    i += 1;
                }
                toks.push(SexpTok {
                    kind: "IDENT",
                    value: src[start..i].to_string(),
                    line: sline,
                    col: scol,
                });
                col += (i - start) as u32;
            }
        }
    }
    toks
}

fn unescape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'\\' && i + 1 < bytes.len() {
            match bytes[i + 1] {
                b'n' => out.push('\n'),
                b't' => out.push('\t'),
                b'r' => out.push('\r'),
                b'\\' => out.push('\\'),
                b'"' => out.push('"'),
                c => out.push(c as char),
            }
            i += 2;
            continue;
        }
        out.push(bytes[i] as char);
        i += 1;
    }
    out
}

// read_sexp — every error path includes line/col so paren imbalance points
// at the source instead of dying with "index out of bounds." The source
// reader is foreign-syntax-by-necessity; its job is to fail informatively
// when humans miscount.
fn read_sexp(k: &mut Kernel, toks: &[SexpTok], i: usize) -> (NodeID, usize) {
    if i >= toks.len() {
        panic!("parse error: unexpected end of input (expected an expression)");
    }
    let t = &toks[i];
    match t.kind {
        "INT" => {
            let n: i64 = t.value.parse().unwrap();
            (k.intern_trivial_int(n), i + 1)
        }
        "FLOAT" => {
            let f: f64 = t.value.parse().unwrap_or_else(|e| {
                panic!(
                    "parse error: bad float literal {:?} at line {}, col {}: {}",
                    t.value, t.line, t.col, e
                )
            });
            (k.intern_trivial_float64(f), i + 1)
        }
        "STRING" => (k.intern_string(&t.value), i + 1),
        "IDENT" => {
            // Bool literals — true/false are reserved, become trivial values at
            // parse time. Parallel to int/string literals; lets Form predicates
            // read naturally without `(eq 0 0)` constructors.
            if t.value == "true" {
                return (
                    NodeID {
                        pkg: 1,
                        level: LEVEL_TRIVIAL,
                        ty: TRIV_BOOL,
                        inst: 1,
                    },
                    i + 1,
                );
            }
            if t.value == "false" {
                return (
                    NodeID {
                        pkg: 1,
                        level: LEVEL_TRIVIAL,
                        ty: TRIV_BOOL,
                        inst: 0,
                    },
                    i + 1,
                );
            }
            let s = k.intern_string(&t.value);
            (k.intern(cat_ident(), vec![s]), i + 1)
        }
        "RPAREN" => {
            panic!(
                "parse error at line {} col {}: unmatched `)` (no `(` to close)",
                t.line, t.col
            );
        }
        "LPAREN" => {
            let (open_line, open_col) = (t.line, t.col);
            let mut j = i + 1;
            if j >= toks.len() {
                panic!(
                    "parse error: unclosed `(` opened at line {} col {} (reached end of input)",
                    open_line, open_col
                );
            }
            if toks[j].kind == "RPAREN" {
                return (
                    NodeID {
                        pkg: 1,
                        level: LEVEL_TRIVIAL,
                        ty: TRIV_NULL,
                        inst: 0,
                    },
                    j + 1,
                );
            }
            if toks[j].kind != "IDENT" {
                panic!("parse error at line {} col {}: expected verb after `(` opened at line {} col {}, got {} {:?}",
                    toks[j].line, toks[j].col, open_line, open_col, toks[j].kind, toks[j].value);
            }
            let verb = toks[j].value.clone();
            j += 1;
            let mut args = Vec::new();
            loop {
                if j >= toks.len() {
                    panic!("parse error: unclosed `(` opened at line {} col {} in `({} ...)` (reached end of input)",
                        open_line, open_col, verb);
                }
                if toks[j].kind == "RPAREN" {
                    j += 1;
                    break;
                }
                let (arg, nj) = read_sexp(k, toks, j);
                args.push(arg);
                j = nj;
            }
            (build_verb(k, &verb, args), j)
        }
        _ => panic!(
            "parse error at line {} col {}: unexpected token {} {:?}",
            t.line, t.col, t.kind, t.value
        ),
    }
}

// The kernel's surface-verb vocabulary — the verbs build_verb lowers into TYPED
// nodes (BLOCK/COND/MATH/COMPARE/LOGIC/FNDEF) rather than the FNCALL fallback.
// These resolve structurally, never as a looked-up function, so the
// name-resolution gate must seed them as `known` alongside the natives — else a
// source-compiled recipe that carries an operator as an FNCALL callee (the
// bundled compile machinery does) is falsely reported unbound. Single source of
// truth: build_verb's match must handle exactly these (the
// build_verbs_are_typed_not_fncall test drift-guards it).
const BUILD_VERBS: &[&str] = &[
    "do", "seq", "let", "if", "defn", "params", "add", "sub", "mul", "div", "mod", "eq", "ne",
    "lt", "le", "gt", "ge", "and", "or", "not",
];

fn build_verb(k: &mut Kernel, verb: &str, args: Vec<NodeID>) -> NodeID {
    match verb {
        "do" => k.intern(cat_block(RBLK_DO), args),
        "seq" => k.intern(cat_block(RBLK_SEQ), args),
        "let" => {
            // (let <ident> <value>) — args[0] is an Identifier recipe wrapping
            // a string trivial. Repackage as the bare string trivial.
            let name_id = k.ident_id(args[0]);
            let name_trivial = NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_STRING,
                inst: name_id,
            };
            k.intern(cat_block(RBLK_LET), vec![name_trivial, args[1]])
        }
        "if" => {
            if args.len() == 2 {
                k.intern(cat_cond(RCOND_IF), args)
            } else {
                k.intern(cat_cond(RCOND_IF_ELSE), args)
            }
        }
        "add" => k.intern(cat_math(RMATH_PLUS), args),
        "sub" => k.intern(cat_math(RMATH_MINUS), args),
        "mul" => k.intern(cat_math(RMATH_MULTIPLY), args),
        "div" => k.intern(cat_math(RMATH_DIVIDE), args),
        "mod" => k.intern(cat_math(RMATH_MODULO), args),
        "eq" => k.intern(cat_compare(RCMP_EQ), args),
        "ne" => k.intern(cat_compare(RCMP_NE), args),
        "lt" => k.intern(cat_compare(RCMP_LT), args),
        "le" => k.intern(cat_compare(RCMP_LE), args),
        "gt" => k.intern(cat_compare(RCMP_GT), args),
        "ge" => k.intern(cat_compare(RCMP_GE), args),
        "and" => k.intern(cat_logic(RLOG_AND), args),
        "or" => k.intern(cat_logic(RLOG_OR), args),
        "not" => k.intern(cat_logic(RLOG_NOT), args),
        "match" => k.intern(cat_match(RMATCH_SWITCH), args),
        "defn" => {
            // (defn <name> (<params>...) <body>) — repackage name + params
            // as bare string trivials so the walker reads `inst` as NameID.
            let name_id = k.ident_id(args[0]);
            let name_trivial = NodeID {
                pkg: 1,
                level: LEVEL_TRIVIAL,
                ty: TRIV_STRING,
                inst: name_id,
            };
            let param_ids: Vec<NameID> =
                k.children(args[1]).iter().map(|p| k.ident_id(*p)).collect();
            let param_trivials: Vec<NodeID> = param_ids
                .into_iter()
                .map(|id| NodeID {
                    pkg: 1,
                    level: LEVEL_TRIVIAL,
                    ty: TRIV_STRING,
                    inst: id,
                })
                .collect();
            let params_block = k.intern(cat_block(RBLK_SEQ), param_trivials);
            k.intern(cat_fndef(), vec![name_trivial, params_block, args[2]])
        }
        "params" => k.intern(cat_block(RBLK_SEQ), args),
        _ => {
            let name_str = k.intern_string(verb);
            let mut all = vec![name_str];
            all.extend(args);
            k.intern(cat_fncall(), all)
        }
    }
}

fn cat_math(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_MATH,
        inst,
    }
}
fn cat_compare(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_COMPARE,
        inst,
    }
}
fn cat_logic(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_LOGIC,
        inst,
    }
}
fn cat_cond(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_COND,
        inst,
    }
}
fn cat_block(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_BLOCK,
        inst,
    }
}
fn cat_match(inst: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_MATCH,
        inst,
    }
}
fn cat_ident() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_IDENT,
        inst: 1,
    }
}
fn cat_fndef() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_FNDEF,
        inst: 1,
    }
}
fn cat_fncall() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_FNCALL,
        inst: 1,
    }
}

// Native-attribution category constructors. Each names the Form-shape
// a native expresses; the walker records them in the trace when the
// native fires. inst:1 is the "generic instance" — when a native maps
// to a specific RBasic subop (e.g. str_eq → COMPARE.EQ), use the
// already-existing cat_compare(RCMP_EQ) instead.
fn cat_call() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_CALL,
        inst: 1,
    }
}
fn cat_witness() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_WITNESS,
        inst: 1,
    }
}
fn cat_access() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_ACCESS,
        inst: 1,
    }
}
fn cat_method() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_METHOD,
        inst: 1,
    }
}
fn cat_list_nat() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_LIST,
        inst: 1,
    }
}
fn cat_field_primitive(ty: u32) -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty,
        inst: 1,
    }
}
fn cat_undefined() -> NodeID {
    NodeID {
        pkg: 1,
        level: LEVEL_BASIC,
        ty: RB_UNDEFINED,
        inst: 0,
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn count_top_level(toks: &[SexpTok]) -> usize {
    let mut depth = 0;
    let mut count = 0;
    for t in toks {
        match t.kind {
            "LPAREN" => {
                if depth == 0 {
                    count += 1;
                }
                depth += 1;
            }
            "RPAREN" => {
                depth -= 1;
            }
            _ => {
                if depth == 0 {
                    count += 1;
                }
            }
        }
    }
    count
}

pub(crate) fn run_source(src: &str) -> Value {
    let mut k = Kernel::new();
    let root = read_root_from_source(&mut k, src);
    execute_root(&mut k, root)
}

pub(crate) fn read_root_from_source(k: &mut Kernel, src: &str) -> NodeID {
    let toks = tokenize_sexp(src);
    let wrapped: String;
    let toks = if count_top_level(&toks) == 1 {
        toks
    } else {
        wrapped = format!("(do {})", src);
        tokenize_sexp(&wrapped)
    };
    let (root, _) = read_sexp(k, &toks, 0);
    root
}

fn execute_root(k: &mut Kernel, root: NodeID) -> Value {
    let mut a = Arena::new();
    let env = a.new_frame(None);
    k.active_roots = vec![root];
    let value = walk(k, &mut a, root, env);
    k.substrate_gc(&[value.clone()], Some((&a, env)));
    value
}

// --- Native implementations — same recursive shape as the Form versions.
// `black_box` on the recursive call's argument prevents LLVM from analyzing
// the recursion and constant-folding the whole computation. Without it,
// pure functions with eventually-constant inputs collapse to a register
// load and the "native" column becomes a measurement of nothing. With it,
// the actual instructions get executed.

fn native_fib(n: i64) -> i64 {
    if n <= 1 {
        n
    } else {
        native_fib(std::hint::black_box(n - 1)) + native_fib(std::hint::black_box(n - 2))
    }
}

fn native_fact(n: i64) -> i64 {
    if n <= 1 {
        1
    } else {
        n * native_fact(std::hint::black_box(n - 1))
    }
}

fn native_sum(n: i64, acc: i64) -> i64 {
    if n == 0 {
        acc
    } else {
        native_sum(std::hint::black_box(n - 1), std::hint::black_box(acc + n))
    }
}

fn native_ack(m: i64, n: i64) -> i64 {
    if m == 0 {
        n + 1
    } else if n == 0 {
        native_ack(std::hint::black_box(m - 1), 1)
    } else {
        native_ack(
            std::hint::black_box(m - 1),
            native_ack(m, std::hint::black_box(n - 1)),
        )
    }
}

// `black_box` prevents LLVM from constant-folding pure functions called
// with constant arguments — without it, native_fact(12) gets folded to
// 479001600 at compile time and the "native" column measures register
// loads, not arithmetic. Passing args through black_box at the call site
// forces the optimizer to treat them as opaque and actually execute.
use std::hint::black_box;

fn run_bench() {
    // Native runners — each takes opaque inputs and returns an int. The
    // black_box on the entry point makes LLVM compile actual code paths.
    type Runner = fn() -> i64;
    let cases: &[(&str, &str, u32, Runner)] = &[
        (
            "fib28",
            "(do (defn fib (n) (if (le n 1) n (add (fib (sub n 1)) (fib (sub n 2))))) (fib 28))",
            100,
            || native_fib(black_box(28)),
        ),
        (
            "fact12",
            "(do (defn fact (n) (if (le n 1) 1 (mul n (fact (sub n 1))))) (fact 12))",
            5_000_000,
            || native_fact(black_box(12)),
        ),
        (
            "sum1000",
            "(do (defn sum (n acc) (if (eq n 0) acc (sum (sub n 1) (add acc n)))) (sum 1000 0))",
            50_000,
            || native_sum(black_box(1000), black_box(0)),
        ),
        (
            "ackermann",
            "(do (defn ack (m n) (if (eq m 0) (add n 1) (if (eq n 0) (ack (sub m 1) 1) (ack (sub m 1) (ack m (sub n 1)))))) (ack 3 6))",
            100,
            || native_ack(black_box(3), black_box(6)),
        ),
    ];

    const KERNEL_ITERS: u32 = 5;

    println!(
        "{:<12} {:<12} {:<14} {:<14} {}",
        "workload", "result", "native", "kernel", "overhead"
    );
    for (name, src, native_iters, native) in cases {
        // Native timing — black_box the result so the loop can't be hoisted
        let start = Instant::now();
        let mut native_result = 0i64;
        for _ in 0..*native_iters {
            native_result = black_box(native());
        }
        let native_dur = start.elapsed() / *native_iters;
        let _ = native_result;

        // Kernel timing — fresh kernel per case so intern starts clean
        let toks = tokenize_sexp(src);
        let mut k = Kernel::new();
        let (root, _) = read_sexp(&mut k, &toks, 0);
        let start = Instant::now();
        let mut kernel_result = Value::Null;
        for _ in 0..KERNEL_ITERS {
            let mut a = Arena::new();
            let env = a.new_frame(None);
            kernel_result = walk(&mut k, &mut a, root, env);
        }
        let kernel_dur = start.elapsed() / KERNEL_ITERS;

        let overhead = kernel_dur.as_nanos() as f64 / native_dur.as_nanos().max(1) as f64;
        println!(
            "{:<12} {:<12} {:<14} {:<14} {:.0}×",
            name,
            kernel_result.display(),
            format!("{:?}", native_dur),
            format!("{:?}", kernel_dur),
            overhead,
        );
    }
}

// ---------------------------------------------------------------------------
// Traced run — same as run_source but with the Trace counter enabled.
// Used by the `trace` subcommand. Hot-path runs use the un-traced version.
// ---------------------------------------------------------------------------

fn run_source_traced(src: &str) -> (Value, Trace) {
    let toks = tokenize_sexp(src);
    let wrapped: String;
    let toks = if count_top_level(&toks) == 1 {
        toks
    } else {
        wrapped = format!("(do {})", src);
        tokenize_sexp(&wrapped)
    };
    let mut k = Kernel::new();
    k.trace = Some(Trace::new());
    let (root, _) = read_sexp(&mut k, &toks, 0);
    let mut a = Arena::new();
    let env = a.new_frame(None);
    k.active_roots = vec![root];
    let value = walk(&mut k, &mut a, root, env);
    k.substrate_gc(&[value.clone()], Some((&a, env)));
    let trace = k.trace.take().unwrap_or_default();
    (value, trace)
}

// ---------------------------------------------------------------------------
// CLI subcommands — list / execute / query / trace / fetch
// ---------------------------------------------------------------------------
//
// Parallels scripts/form_cli.py at the native binary altitude. The point
// per lc-native-kernel-binary: end-to-end host-native kernel binaries that
// can access I/O, binary form objects, substrate API, and network resources
// — functionally equivalent to the Python runtime.

const RECIPES_DIR: &str = "recipes";

fn cli_help() {
    println!(
        "form-kernel-rust — native macOS / Linux Form kernel binary

Subcommands:
  --binary <file.fkb>                 execute a Form binary artifact
  --emit-binary <out.fkb> <file.fk...> write a Form binary artifact
  list <library.json>                  print library meta + recipes
  execute <library.json> <recipe> [args...]   run a recipe natively
  query <path>                         parse any file as a Form object tree
  trace [--expr \"...\" | <file.fk>]     run with arm-dispatch tracing
  fetch <url>                          GET a URL (network resource)
  run [--stdlib <dir>] <file.fk...>     source-compile section-authored files
                                       through Form stdlib, then execute
  serve --port <p> --routes <file> [--upstream <base-url>] [--stdlib <dir>] [--config <path>]\n                                       kernel front-door router: native Form handlers\n                                       for listed paths, fan-out to the Python upstream\n                                       for the rest. --routes may be raw S-expression\n                                       Form or a source-authored `section [...]`\n                                       manifest (source-compiled at load via --stdlib,\n                                       default form-stdlib)

Source adapter modes:
  <file.fk> [more.fk ...]              run .fk files
  --expr \"<form-expression>\"          evaluate a Form expression
  --bench                              benchmark run
  --numeric-bench                      numeric kernel comparison"
    );
}

// ---------------------------------------------------------------------------
// `serve` — proof-of-shape kernel-as-HTTP-listener
// ---------------------------------------------------------------------------
//
// The deepest move toward Breath 8 of `form/kernel-roadmap.md`: a tiny
// HTTP/1.0 listener that lives *inside* the kernel binary, parses the
// request into Form values, looks up a handler closure from a routes.fk
// file's top-level `routes` binding, walks the closure, and writes the
// returned value back as the response body.
//
// This is gesture, not replacement. FastAPI remains the body's primary
// doorway; this exists so the body can feel "kernel CAN be the HTTP
// layer" before betting more of the stack on it. ~50 lines of raw
// `std::net` HTTP/1.0 — no hyper, no actix, no async runtime. The whole
// dependency footprint is what already shipped (ureq for `fetch`).
//
// routes.fk shape:
//   (defn route_hello () "Hello from the kernel")
//   (defn route_echo (q) (dict_get q "msg"))
//   (let routes (list
//     (list "/hello" route_hello)
//     (list "/echo"  route_echo)))
//
// A 1-arg handler receives the query as a List of (key value) pairs
// (an alist; `dict_get` reads from it). A 0-arg handler receives no
// argument. The walker turns either return value into a string for
// the response body via `Value::display()`.

// Per-worker thread stack. The kernel value-walk is a recursive tree-walker, so
// a deeply self-recursive native handler consumes real stack. 16 MiB comfortably
// exceeds the typical main-thread stack (~8 MiB), so a pooled worker handles at
// least the recursion depth the single-threaded serve path did before the pool.
const WORKER_STACK_SIZE: usize = 16 * 1024 * 1024;

// The route manifest a worker resolves from its own kernel+arena. Path rows are
// `(path handler-closure)`. KernelHTTPRoute rows are
// `(KernelHTTPRoute name method pattern priority handler required_header budget)`,
// the lowered BML/Form HTTP surface carried by form-stdlib/kernel-http.fk.
// KernelHTTPRoute rows resolve `handler` through the already-walked manifest
// environment. Each closure's `env` is a frame index INTO THAT worker's arena,
// so route specs are NOT shareable across workers — every worker re-loads
// routes.fk into its own Kernel+Arena and resolves its own copy. This is the
// !Sync constraint the pool answers (lc-native-kernel-binary: the per-process
// intern table means a pool of kernel workers, not one shared mutable kernel).
#[derive(Clone, Debug)]
struct RouteSpec {
    name: String,
    method: String,
    pattern: String,
    priority: i64,
    handler_name: String,
    required_header: String,
    pressure_budget: i64,
    handler: Arc<Closure>,
    typed_request: bool,
}

type RouteSpecs = Vec<RouteSpec>;

#[derive(Clone, Debug, Default)]
struct RouteDataRegistry {
    routes: HashMap<String, RouteData>,
}

#[derive(Clone, Debug, serde::Deserialize)]
struct RouteDataFile {
    routes: HashMap<String, RouteData>,
}

#[derive(Clone, Debug, serde::Deserialize)]
struct RouteData {
    name: String,
    method: String,
    pattern: String,
    priority: i64,
    #[serde(default)]
    required_header: String,
    pressure_budget: i64,
}

#[derive(Clone, Debug)]
struct RoutePressureRow {
    axis: String,
    observed: Value,
    expected: Value,
    pressure: i64,
}

#[derive(Clone, Debug)]
struct RouteCandidateValue {
    route_name: String,
    route_method: String,
    route_pattern: String,
    route_priority: i64,
    route_handler_name: String,
    route_required_header: String,
    route_pressure_budget: i64,
    request_method: String,
    request_path: String,
    request_headers: Vec<(String, String)>,
    request_query: Vec<(String, String)>,
    request_body: String,
    pressure_matrix: Vec<RoutePressureRow>,
    pressure: i64,
    score: i64,
}

#[derive(Clone, Debug)]
struct RouteRequestValue {
    method: String,
    path: String,
    headers: Vec<(String, String)>,
    query: Vec<(String, String)>,
    body: String,
}

#[derive(Clone, Debug)]
struct RouteDecisionValue {
    candidate: RouteCandidateValue,
    eligible: bool,
    selected: bool,
}

#[derive(Debug)]
struct RouteSelection<'a> {
    route: &'a RouteSpec,
    candidate: RouteCandidateValue,
}

#[derive(Debug)]
struct RouteChoice<'a> {
    request: RouteRequestValue,
    decisions: Vec<RouteDecisionValue>,
    selected: Option<RouteSelection<'a>>,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
struct RouterFanoutPathCount {
    path: String,
    count: u64,
    source: String,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
struct RouterBmlCandidate {
    path: String,
    count: u64,
    source: String,
}

#[derive(Default)]
struct RouterMetrics {
    total_requests: u64,
    native_requests: u64,
    fanout_requests: u64,
    local_control_requests: u64,
    native_error_requests: u64,
    choice_attempts: u64,
    choice_successes: u64,
    choice_failures: u64,
    observed_paths: HashSet<String>,
    observed_native_paths: HashSet<String>,
    observed_fanout_paths: HashSet<String>,
    observed_fanout_path_requests: HashMap<String, u64>,
}

#[derive(Default)]
struct RouterMetricsSnapshot {
    native_route_count: usize,
    total_requests: u64,
    native_requests: u64,
    fanout_requests: u64,
    local_control_requests: u64,
    native_error_requests: u64,
    choice_attempts: u64,
    choice_successes: u64,
    choice_failures: u64,
    observed_path_count: usize,
    observed_native_route_count: usize,
    observed_fanout_path_count: usize,
    fanout_path_counts: Vec<RouterFanoutPathCount>,
    next_bml_candidate: RouterBmlCandidate,
    next_bml_candidate_path: String,
    next_bml_candidate_requests: u64,
    next_bml_candidate_source: String,
}

impl RouterMetrics {
    fn record(&mut self, path: &str, router: &str) {
        self.total_requests += 1;
        self.observed_paths.insert(path.to_string());
        match router {
            "native-kernel" => {
                self.native_requests += 1;
                self.observed_native_paths.insert(path.to_string());
            }
            "fanout-python" => {
                self.fanout_requests += 1;
                self.observed_fanout_paths.insert(path.to_string());
                *self
                    .observed_fanout_path_requests
                    .entry(path.to_string())
                    .or_insert(0) += 1;
            }
            "native-kernel-error" => {
                self.native_error_requests += 1;
                self.observed_native_paths.insert(path.to_string());
            }
            _ => {
                self.local_control_requests += 1;
            }
        }
    }

    fn fanout_path_counts(&self) -> Vec<RouterFanoutPathCount> {
        let mut counts: Vec<RouterFanoutPathCount> = self
            .observed_fanout_path_requests
            .iter()
            .map(|(path, count)| RouterFanoutPathCount {
                path: path.clone(),
                count: *count,
                source: "observed-fanout-path".to_string(),
            })
            .collect();
        counts.sort_by(|a, b| b.count.cmp(&a.count).then_with(|| a.path.cmp(&b.path)));
        counts
    }

    fn next_bml_candidate(counts: &[RouterFanoutPathCount]) -> RouterBmlCandidate {
        match counts.first() {
            Some(row) => RouterBmlCandidate {
                path: row.path.clone(),
                count: row.count,
                source: row.source.clone(),
            },
            None => RouterBmlCandidate::default(),
        }
    }

    fn record_route_choice(&mut self, choice: &RouteChoice<'_>) {
        let attempts = choice.decisions.len() as u64;
        let successes = choice
            .decisions
            .iter()
            .filter(|decision| decision.selected)
            .count() as u64;
        self.choice_attempts += attempts;
        self.choice_successes += successes;
        self.choice_failures += attempts.saturating_sub(successes);
    }

    fn snapshot(&self, native_route_count: usize) -> RouterMetricsSnapshot {
        let fanout_path_counts = self.fanout_path_counts();
        let next_bml_candidate = Self::next_bml_candidate(&fanout_path_counts);
        let next_bml_candidate_path = next_bml_candidate.path.clone();
        let next_bml_candidate_requests = next_bml_candidate.count;
        let next_bml_candidate_source = next_bml_candidate.source.clone();
        RouterMetricsSnapshot {
            native_route_count,
            total_requests: self.total_requests,
            native_requests: self.native_requests,
            fanout_requests: self.fanout_requests,
            local_control_requests: self.local_control_requests,
            native_error_requests: self.native_error_requests,
            choice_attempts: self.choice_attempts,
            choice_successes: self.choice_successes,
            choice_failures: self.choice_failures,
            observed_path_count: self.observed_paths.len(),
            observed_native_route_count: self.observed_native_paths.len(),
            observed_fanout_path_count: self.observed_fanout_paths.len(),
            fanout_path_counts,
            next_bml_candidate,
            next_bml_candidate_path,
            next_bml_candidate_requests,
            next_bml_candidate_source,
        }
    }
}

fn router_metrics_snapshot(
    metrics: &Arc<Mutex<RouterMetrics>>,
    native_route_count: usize,
) -> RouterMetricsSnapshot {
    match metrics.lock() {
        Ok(guard) => guard.snapshot(native_route_count),
        Err(_) => RouterMetricsSnapshot {
            native_route_count,
            ..RouterMetricsSnapshot::default()
        },
    }
}

fn record_router_metrics(metrics: &Arc<Mutex<RouterMetrics>>, path: &str, router: &str) {
    if let Ok(mut guard) = metrics.lock() {
        guard.record(path, router);
    }
}

fn record_router_choice_metrics(metrics: &Arc<Mutex<RouterMetrics>>, choice: &RouteChoice<'_>) {
    if let Ok(mut guard) = metrics.lock() {
        guard.record_route_choice(choice);
    }
}

const KH_TAG_HEADER: i64 = 43001;
const KH_TAG_REQUEST: i64 = 43002;
const KH_TAG_RESPONSE: i64 = 43003;
const KH_TAG_ROUTE: i64 = 43004;
const KH_TAG_PRESSURE_ROW: i64 = 43005;
const KH_TAG_ROUTE_CANDIDATE: i64 = 43006;
const KH_TAG_ROUTE_DATA_REF: i64 = 43007;
const KH_TAG_FIELD: i64 = 43008;
const KH_TAG_ROUTE_DECISION: i64 = 43009;
const KH_TAG_ROUTE_CHOICE: i64 = 43010;
const KH_TAG_ROUTE_DECISION_SIGNATURE: i64 = 43011;
const KH_TAG_ROUTE_CHOICE_SIGNATURE: i64 = 43012;
const KH_TAG_CHANNEL_POLICY: i64 = 43013;
const KH_TAG_METHOD_BRIDGE: i64 = 43014;
const NATIVE_PYTHON_FALLBACK_HEADER: &str = "X-Form-Python-Fallback";
const FANOUT_NATIVE_INVITATION_HEADER: &str = "X-Form-Native-Invitation";
const FANOUT_NATIVE_INVITATION_STATE_HEADER: &str = "X-Form-Native-Invitation-State";
const FANOUT_NATIVE_INVITATION_PROTOCOL_HEADER: &str = "X-Form-Native-Invitation-Protocol";
const FANOUT_NATIVE_INVITATION_SELECTED_PATH_HEADER: &str =
    "X-Form-Native-Invitation-Selected-Path";
const FANOUT_NATIVE_INVITATION_DECLINE_SIGNAL_HEADER: &str =
    "X-Form-Native-Invitation-Decline-Signal";
const FANOUT_NATIVE_INVITATION_DECLINE_HEADER: &str = "X-Form-Native-Invitation-Decline-Header";
const FANOUT_NATIVE_INVITATION_VALUE: &str = "offered";
const FANOUT_NATIVE_INVITATION_STATE: &str = "native-invitation-offered";
const FANOUT_NATIVE_INVITATION_PROTOCOL: &str = "Form/BML route recipe";
const FANOUT_NATIVE_INVITATION_DECLINE_SIGNAL: &str = "native_invitation_declined";

#[derive(Clone, Copy, Debug)]
struct MethodBridgePolicy {
    route_method: &'static str,
    request_method: &'static str,
    pressure: i64,
}

#[derive(Clone, Debug)]
struct ChannelPolicy {
    carrier: &'static str,
    protocol: &'static str,
    allowed_methods: &'static [&'static str],
    method_bridges: &'static [MethodBridgePolicy],
    no_body_methods: &'static [&'static str],
    allow_methods: &'static [&'static str],
    cache_policy: &'static str,
    compression_policy: &'static str,
    stream_policy: &'static str,
    identity_policy: &'static str,
    authorization_policy: &'static str,
}

const DEFAULT_HTTP_ALLOWED_METHODS: &[&str] =
    &["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"];
const DEFAULT_HTTP_METHOD_BRIDGES: &[MethodBridgePolicy] = &[MethodBridgePolicy {
    route_method: "GET",
    request_method: "HEAD",
    pressure: 20,
}];
const DEFAULT_HTTP_NO_BODY_METHODS: &[&str] = &["HEAD"];

fn default_http_channel_policy() -> ChannelPolicy {
    ChannelPolicy {
        carrier: "tcp",
        protocol: "http/1.1",
        allowed_methods: DEFAULT_HTTP_ALLOWED_METHODS,
        method_bridges: DEFAULT_HTTP_METHOD_BRIDGES,
        no_body_methods: DEFAULT_HTTP_NO_BODY_METHODS,
        allow_methods: DEFAULT_HTTP_ALLOWED_METHODS,
        cache_policy: "cache-policy-observe",
        compression_policy: "compression-policy-observe",
        stream_policy: "stream-policy-buffered",
        identity_policy: "identity-policy-claim",
        authorization_policy: "authorization-policy-capability",
    }
}

fn channel_policy_method_known(policy: &ChannelPolicy, method: &str) -> bool {
    policy.allowed_methods.iter().any(|known| *known == method)
}

fn channel_policy_route_method_valid(policy: &ChannelPolicy, method: &str) -> bool {
    method == "ANY" || channel_policy_method_known(policy, method)
}

fn channel_policy_method_bridge_pressure(
    policy: &ChannelPolicy,
    route_method: &str,
    request_method: &str,
) -> Option<i64> {
    policy
        .method_bridges
        .iter()
        .find(|bridge| {
            bridge.route_method == route_method && bridge.request_method == request_method
        })
        .map(|bridge| bridge.pressure)
}

fn channel_policy_no_body_method(policy: &ChannelPolicy, method: &str) -> bool {
    policy
        .no_body_methods
        .iter()
        .any(|no_body| *no_body == method)
}

fn channel_policy_allow_header_value(policy: &ChannelPolicy) -> String {
    policy.allow_methods.join(", ")
}

fn route_value_string(value: &Value, field: &str) -> Result<String, String> {
    match value {
        Value::Str(s) => Ok(s.to_string()),
        _ => Err(format!("KernelHTTPRoute {} must be a string", field)),
    }
}

fn route_value_i64(value: &Value, field: &str) -> Result<i64, String> {
    match value {
        Value::Int(n) => Ok(*n),
        _ => Err(format!("KernelHTTPRoute {} must be an integer", field)),
    }
}

fn route_value_closure(value: &Value, route: &str) -> Result<Arc<Closure>, String> {
    match value {
        Value::Closure(c) => Ok(c.clone()),
        _ => Err(format!("route value for {} must be a closure", route)),
    }
}

fn kernel_http_route_tagged(meta: &[Value]) -> bool {
    matches!(meta.first(), Some(Value::Int(tag)) if *tag == KH_TAG_ROUTE)
}

fn kernel_http_route_data_ref_tagged(meta: &[Value]) -> bool {
    matches!(meta.first(), Some(Value::Int(tag)) if *tag == KH_TAG_ROUTE_DATA_REF)
}

fn validate_route_spec(spec: RouteSpec) -> Result<RouteSpec, String> {
    if spec.name.is_empty() {
        return Err("KernelHTTPRoute name must not be empty".to_string());
    }
    if spec.pattern.is_empty() || !spec.pattern.starts_with('/') {
        return Err(format!(
            "KernelHTTPRoute {} pattern must start with /",
            spec.name
        ));
    }
    let policy = default_http_channel_policy();
    if !channel_policy_route_method_valid(&policy, spec.method.as_str()) {
        return Err(format!(
            "KernelHTTPRoute {} method must be a known HTTP method or ANY",
            spec.name
        ));
    }
    if spec.priority < 0 {
        return Err(format!(
            "KernelHTTPRoute {} priority must be non-negative",
            spec.name
        ));
    }
    if spec.handler_name.is_empty() {
        return Err(format!(
            "KernelHTTPRoute {} handler metadata must not be empty",
            spec.name
        ));
    }
    if spec.pressure_budget < 0 {
        return Err(format!(
            "KernelHTTPRoute {} pressure_budget must be non-negative",
            spec.name
        ));
    }
    Ok(spec)
}

fn resolve_route_handler(
    k: &mut Kernel,
    arena: &Arena,
    root_env: FrameId,
    route_name: &str,
    handler_name: &str,
) -> Result<Arc<Closure>, String> {
    let handler_id = k.intern_string(handler_name).inst;
    match arena.lookup(root_env, handler_id) {
        Some(Value::Closure(c)) => Ok(c),
        Some(_) => Err(format!(
            "KernelHTTPRoute {} handler {} must resolve to a closure",
            route_name, handler_name
        )),
        None => Err(format!(
            "KernelHTTPRoute {} handler {} is not bound",
            route_name, handler_name
        )),
    }
}

fn parse_kernel_http_route_meta(
    meta: &[Value],
    handler: Arc<Closure>,
) -> Result<RouteSpec, String> {
    if meta.len() != 8 {
        return Err("KernelHTTPRoute must have 8 fields".to_string());
    }
    if !kernel_http_route_tagged(meta) {
        return Err("route metadata must be KernelHTTPRoute".to_string());
    }
    let name = route_value_string(&meta[1], "name")?;
    let method = route_value_string(&meta[2], "method")?;
    let pattern = route_value_string(&meta[3], "pattern")?;
    let priority = route_value_i64(&meta[4], "priority")?;
    let handler_name = route_value_string(&meta[5], "handler")?;
    let required_header = route_value_string(&meta[6], "required_header")?;
    let pressure_budget = route_value_i64(&meta[7], "pressure_budget")?;
    validate_route_spec(RouteSpec {
        name,
        method,
        pattern,
        priority,
        handler_name,
        required_header,
        pressure_budget,
        handler,
        typed_request: true,
    })
}

fn parse_kernel_http_route_data_ref(
    meta: &[Value],
    route_data: &RouteDataRegistry,
    k: &Kernel,
) -> Result<RouteSpec, String> {
    if meta.len() != 3 {
        return Err("KernelHTTPRouteDataRef must have 3 fields".to_string());
    }
    if !kernel_http_route_data_ref_tagged(meta) {
        return Err("route metadata must be KernelHTTPRouteDataRef".to_string());
    }
    let route_id = route_value_string(&meta[1], "route_id")?;
    let handler = route_value_closure(&meta[2], &route_id)?;
    let data = route_data.routes.get(&route_id).ok_or_else(|| {
        format!(
            "KernelHTTPRouteDataRef {} is not present in route data",
            route_id
        )
    })?;
    validate_route_spec(RouteSpec {
        name: data.name.clone(),
        method: data.method.clone(),
        pattern: data.pattern.clone(),
        priority: data.priority,
        handler_name: k.name_str(handler.name).to_string(),
        required_header: data.required_header.clone(),
        pressure_budget: data.pressure_budget,
        handler,
        typed_request: true,
    })
}

fn parse_route_spec(
    k: &mut Kernel,
    arena: &Arena,
    root_env: FrameId,
    row: &Value,
    route_data: &RouteDataRegistry,
) -> Result<RouteSpec, String> {
    match row {
        Value::List(meta) if kernel_http_route_tagged(meta) => {
            if meta.len() != 8 {
                return Err("KernelHTTPRoute must have 8 fields".to_string());
            }
            let name = route_value_string(&meta[1], "name")?;
            let handler_name = route_value_string(&meta[5], "handler")?;
            let handler = resolve_route_handler(k, arena, root_env, &name, &handler_name)?;
            parse_kernel_http_route_meta(meta, handler)
        }
        Value::List(meta) if kernel_http_route_data_ref_tagged(meta) => {
            parse_kernel_http_route_data_ref(meta, route_data, k)
        }
        Value::List(ys) if ys.len() == 2 => match &ys[0] {
            Value::Str(path) => {
                let handler = route_value_closure(&ys[1], path)?;
                let handler_name = k.name_str(handler.name).to_string();
                Ok(RouteSpec {
                    name: path.to_string(),
                    method: "ANY".to_string(),
                    pattern: path.to_string(),
                    priority: 0,
                    handler_name,
                    required_header: String::new(),
                    pressure_budget: 40,
                    handler,
                    typed_request: false,
                })
            }
            _ => Err("route key must be a string path".to_string()),
        },
        _ => Err(
            "each route must be a path/closure row, KernelHTTPRoute row, or KernelHTTPRouteDataRef row"
                .to_string(),
        ),
    }
}

fn route_pattern_wildcard(pattern: &str) -> bool {
    pattern.ends_with('*')
}

fn route_pattern_prefix(pattern: &str) -> &str {
    if route_pattern_wildcard(pattern) {
        &pattern[..pattern.len().saturating_sub(1)]
    } else {
        pattern
    }
}

fn route_pattern_template(pattern: &str) -> bool {
    pattern.contains('{') || pattern.contains("/:")
}

fn route_template_segment(segment: &str) -> bool {
    (segment.starts_with(':') && segment.len() > 1)
        || (segment.starts_with('{') && segment.ends_with('}') && segment.len() > 2)
}

fn route_template_path_matches(pattern: &str, path: &str) -> bool {
    let pattern_parts: Vec<&str> = pattern.trim_matches('/').split('/').collect();
    let path_parts: Vec<&str> = path.trim_matches('/').split('/').collect();
    if pattern_parts.len() != path_parts.len() {
        return false;
    }
    for (pattern_part, path_part) in pattern_parts.iter().zip(path_parts.iter()) {
        if route_template_segment(pattern_part) {
            if path_part.is_empty() {
                return false;
            }
            continue;
        }
        if pattern_part != path_part {
            return false;
        }
    }
    true
}

fn route_method_pressure_with_policy(
    policy: &ChannelPolicy,
    route: &RouteSpec,
    method: &str,
) -> i64 {
    if route.method == method {
        0
    } else if let Some(pressure) =
        channel_policy_method_bridge_pressure(policy, route.method.as_str(), method)
    {
        pressure
    } else if route.method == "ANY" {
        40
    } else {
        400
    }
}

fn route_method_pressure(route: &RouteSpec, method: &str) -> i64 {
    route_method_pressure_with_policy(&default_http_channel_policy(), route, method)
}

fn route_path_pressure(route: &RouteSpec, path: &str) -> i64 {
    if route.pattern == path {
        0
    } else if route_pattern_template(&route.pattern)
        && route_template_path_matches(&route.pattern, path)
    {
        10
    } else if route_pattern_wildcard(&route.pattern)
        && path.starts_with(route_pattern_prefix(&route.pattern))
    {
        25
    } else {
        500
    }
}

fn route_header_present(headers: &[(String, String)], name: &str) -> bool {
    headers.iter().any(|(h, _)| h.eq_ignore_ascii_case(name))
}

fn route_python_fallback_requested(headers: &[(String, String)]) -> bool {
    route_header_present(headers, NATIVE_PYTHON_FALLBACK_HEADER)
}

fn route_header_pressure(route: &RouteSpec, headers: &[(String, String)]) -> i64 {
    if route.required_header.is_empty() || route_header_present(headers, &route.required_header) {
        0
    } else {
        120
    }
}

fn route_header_observation(route: &RouteSpec, headers: &[(String, String)]) -> String {
    if route.required_header.is_empty() {
        "not-required".to_string()
    } else if route_header_present(headers, &route.required_header) {
        "present".to_string()
    } else {
        "missing".to_string()
    }
}

fn route_budget_pressure(base_pressure: i64, pressure_budget: i64) -> i64 {
    if base_pressure <= pressure_budget {
        0
    } else {
        base_pressure - pressure_budget
    }
}

fn route_candidate_pressure_matrix(
    route: &RouteSpec,
    method: &str,
    path: &str,
    headers: &[(String, String)],
) -> Vec<RoutePressureRow> {
    let method_pressure = route_method_pressure(route, method);
    let path_pressure = route_path_pressure(route, path);
    let header_pressure = route_header_pressure(route, headers);
    let base_pressure = method_pressure + path_pressure + header_pressure;
    let budget_pressure = route_budget_pressure(base_pressure, route.pressure_budget);
    vec![
        RoutePressureRow {
            axis: "method".to_string(),
            observed: Value::Str(method.to_string().into()),
            expected: Value::Str(route.method.clone().into()),
            pressure: method_pressure,
        },
        RoutePressureRow {
            axis: "path".to_string(),
            observed: Value::Str(path.to_string().into()),
            expected: Value::Str(route.pattern.clone().into()),
            pressure: path_pressure,
        },
        RoutePressureRow {
            axis: "header".to_string(),
            observed: Value::Str(route_header_observation(route, headers).into()),
            expected: Value::Str(route.required_header.clone().into()),
            pressure: header_pressure,
        },
        RoutePressureRow {
            axis: "budget".to_string(),
            observed: Value::Int(base_pressure),
            expected: Value::Int(route.pressure_budget),
            pressure: budget_pressure,
        },
    ]
}

fn route_pressure_matrix_total(matrix: &[RoutePressureRow]) -> i64 {
    matrix.iter().map(|row| row.pressure).sum()
}

fn route_candidate_score(route: &RouteSpec, pressure: i64) -> i64 {
    1000 + (route.priority * 10) - pressure
}

fn route_candidate_eligible(route: &RouteSpec, pressure: i64) -> bool {
    pressure <= route.pressure_budget
}

fn route_candidate_value_for_request(
    route: &RouteSpec,
    method: &str,
    path: &str,
    headers: &[(String, String)],
    query: &[(String, String)],
    body: &str,
) -> RouteCandidateValue {
    let pressure_matrix = route_candidate_pressure_matrix(route, method, path, headers);
    let pressure = route_pressure_matrix_total(&pressure_matrix);
    let score = route_candidate_score(route, pressure);
    RouteCandidateValue {
        route_name: route.name.clone(),
        route_method: route.method.clone(),
        route_pattern: route.pattern.clone(),
        route_priority: route.priority,
        route_handler_name: route.handler_name.clone(),
        route_required_header: route.required_header.clone(),
        route_pressure_budget: route.pressure_budget,
        request_method: method.to_string(),
        request_path: path.to_string(),
        request_headers: headers.to_vec(),
        request_query: query.to_vec(),
        request_body: body.to_string(),
        pressure_matrix,
        pressure,
        score,
    }
}

fn route_choice_for_request<'a>(
    route_specs: &'a RouteSpecs,
    method: &str,
    path: &str,
    headers: &[(String, String)],
    query: &[(String, String)],
    body: &str,
) -> RouteChoice<'a> {
    let request = RouteRequestValue {
        method: method.to_string(),
        path: path.to_string(),
        headers: headers.to_vec(),
        query: query.to_vec(),
        body: body.to_string(),
    };
    let mut rows: Vec<(&'a RouteSpec, RouteCandidateValue, bool)> = Vec::new();
    let mut best_index: Option<usize> = None;
    for route in route_specs {
        let candidate =
            route_candidate_value_for_request(route, method, path, headers, query, body);
        let eligible = route_candidate_eligible(route, candidate.pressure);
        if eligible {
            let replace = match best_index {
                None => true,
                Some(current_index) => {
                    let current = &rows[current_index];
                    candidate.score > current.1.score
                        || (candidate.score == current.1.score
                            && route.priority > current.0.priority)
                }
            };
            if replace {
                best_index = Some(rows.len());
            }
        }
        rows.push((route, candidate, eligible));
    }
    let decisions = rows
        .iter()
        .enumerate()
        .map(|(index, (_, candidate, eligible))| RouteDecisionValue {
            candidate: candidate.clone(),
            eligible: *eligible,
            selected: best_index == Some(index),
        })
        .collect();
    let selected = best_index.map(|index| RouteSelection {
        route: rows[index].0,
        candidate: rows[index].1.clone(),
    });
    RouteChoice {
        request,
        decisions,
        selected,
    }
}

#[cfg(test)]
fn select_route_candidate<'a>(
    route_specs: &'a RouteSpecs,
    method: &str,
    path: &str,
    headers: &[(String, String)],
    query: &[(String, String)],
    body: &str,
) -> Option<RouteSelection<'a>> {
    route_choice_for_request(route_specs, method, path, headers, query, body).selected
}

#[cfg(test)]
fn select_route_spec<'a>(
    route_specs: &'a RouteSpecs,
    method: &str,
    path: &str,
    headers: &[(String, String)],
) -> Option<&'a RouteSpec> {
    select_route_candidate(route_specs, method, path, headers, &[], "")
        .map(|selection| selection.route)
}

// Resolve the top-level `routes` binding from a kernel+arena that has already
// walked the manifest source. Pulled out of cli_serve so BOTH the single-path
// load and each worker's per-thread load run the SAME resolution shape. Returns
// the route specs, or an error string for the caller to report.
fn build_route_specs(
    k: &mut Kernel,
    arena: &Arena,
    root_env: FrameId,
    routes_path: &str,
    route_data: &RouteDataRegistry,
) -> Result<RouteSpecs, String> {
    let routes_name = k.intern_string("routes").inst;
    let routes_val = match arena.lookup(root_env, routes_name) {
        Some(v) => v,
        None => {
            return Err(format!(
                "{} must bind a top-level `routes` list",
                routes_path
            ))
        }
    };
    match &routes_val {
        Value::List(xs) => {
            let mut specs = Vec::with_capacity(xs.len());
            for row in xs.iter() {
                specs.push(parse_route_spec(k, arena, root_env, row, route_data)?);
            }
            Ok(specs)
        }
        _ => Err("`routes` must be a list of route specs".to_string()),
    }
}

// Build a worker's OWN Kernel + Arena from the route program, resolve its own
// route specs, and return all three. Raw Form manifests still enter as source;
// Source-authored manifests enter as compiled Form Recipe object graphs produced
// once by the main thread. The returned arena owns the frames the route closures
// capture, so it must stay alive alongside the kernel for the worker's lifetime.
#[cfg(test)]
fn build_worker_kernel(
    program: &RouteProgram,
    routes_path: &str,
) -> Result<(Kernel, Arena, RouteSpecs), String> {
    let (k, arena, routes, _frame) =
        build_worker_kernel_with_route_data(program, routes_path, &RouteDataRegistry::default())?;
    Ok((k, arena, routes))
}

fn build_worker_kernel_with_route_data(
    program: &RouteProgram,
    routes_path: &str,
    route_data: &RouteDataRegistry,
) -> Result<(Kernel, Arena, RouteSpecs, FrameId), String> {
    let mut k = Kernel::new();
    let root = match program {
        RouteProgram::Source(src) => read_root_from_source(&mut k, src),
        RouteProgram::RecipeObject(compiled) => {
            k = compiled.kernel.readonly_worker_clone();
            compiled.root
        }
    };
    let mut arena = Arena::new();
    let root_env = arena.new_frame(None);
    k.active_roots = vec![root];
    let _ = walk(&mut k, &mut arena, root, root_env);
    let route_specs = build_route_specs(&mut k, &arena, root_env, routes_path, route_data)?;
    // root_env is returned so the --form serve path can resolve kh-serve / routes
    // / registry globals from it (the same global frame build_route_specs reads).
    Ok((k, arena, route_specs, root_env))
}

// Handle ONE request on a worker's own kernel+arena. This is the single factored
// serving shape (core-abstraction-first): the routing decision (native Form
// handler vs fan-out to the Python upstream vs 404) lives here ONCE, and both the
// worker pool (parallelism) and the keep-alive loop (multiple requests per
// connection) simply call it. Because `k` and `arena` belong to the calling
// worker alone, concurrent requests on different workers never share mutable
// kernel state — each request's value-walk is isolated.
//
// Returns whether the connection should be KEPT ALIVE for the next request:
// the client's intent (HTTP/1.1 default-keep-alive unless `Connection: close`;
// HTTP/1.0 close-unless-`keep-alive`) AND no server-side reason to close. An
// idle/EOF read, a 413 (body undrained — framing broken), and a handler error
// all return `false` so the keep-alive loop ends and the stream is dropped.
// `carry` holds bytes read past this request's end (pipelining) for the next
// call on the same connection.
fn handle_request(
    stream: &mut TcpStream,
    carry: &mut Vec<u8>,
    k: &mut Kernel,
    arena: &mut Arena,
    route_specs: &RouteSpecs,
    upstream: &Option<String>,
    upstream_pool: &mut UpstreamPool,
    router_metrics: &Arc<Mutex<RouterMetrics>>,
    crash_context: &ServeCrashContext,
) -> bool {
    let channel_policy = default_http_channel_policy();
    crash_context.set_operation(
        "serve-request-read",
        format!("worker={} read request", crash_context.worker_id),
    );
    // Read the FULL request: the header block, then exactly Content-Length body
    // bytes if present (read_request honors Content-Length across as many socket
    // reads as the body needs — a body larger than one buffer is fully captured —
    // and carries any over-read bytes into `carry` for the next request on this
    // persistent connection). HTTP/1.1 keep-alive with Content-Length framing;
    // chunked transfer remains a named breath (KERNEL_AS_ROUTER.md request row).
    let (head, body_bytes) = match read_request(stream, carry) {
        RequestRead::Ok(h, b) => (h, b),
        RequestRead::LargerThanWeHold { observed, limit } => {
            // The shape was observed before any "no" — its size is larger than
            // one worker can hold this moment. The body is not drained, so the
            // connection's framing can't continue: answer once, observably, then
            // close. The "no" names the shape, the threshold we hold right now,
            // and that it is a common recipe we can change together — an
            // invitation, not a wall.
            let status = "413 Payload Too Large".to_string();
            let msg = format!(
                "the request shape is {observed} bytes — larger than the shape we can hold right \
                 now ({limit} bytes). this threshold belongs in the router configuration recipe; \
                 the circulation is welcome the moment we agree on a shape we can both hold, or \
                 when it streams.\n"
            );
            let _ = stream.write_all(
                http_response(&status, &msg, "local-control", false, "", &[]).as_bytes(),
            );
            return false;
        }
        RequestRead::Error => return false, // idle close / read-timeout / EOF — loop ends
    };
    // The client's keep-alive intent for THIS connection (server may still close
    // on an error below).
    let keep_alive = head_keep_alive(&head);
    let (method, target, path, query_data) = parse_request_line(&head);
    crash_context.set_operation(
        "serve-request",
        format!(
            "worker={} request={} {}",
            crash_context.worker_id, method, target
        ),
    );
    let mut request_data = query_data.clone();
    // Parse the body by Content-Type and MERGE its fields into the same alist
    // the handler reads (core-abstraction-first: ONE request-data shape, whether
    // a field arrived as a query param or a body field). Query fields come
    // first; body fields are appended. form-urlencoded fields land as plain
    // (k v) pairs; a JSON / other body lands as a single ("__body__", raw) pair.
    let content_type = parse_content_type(&head);
    request_data.extend(parse_request_body(&content_type, &body_bytes));
    let request_body = String::from_utf8_lossy(&body_bytes).to_string();
    // The full client request header list (request line excluded), captured once
    // so the fan-out arm can forward the client's end-to-end headers
    // (Authorization, Cookie, Accept*, …) to the upstream. Native handlers don't
    // read headers from a typed KernelHTTPRequest now; the fan-out arm also needs
    // them to front authenticated routes.
    let req_headers = parse_headers(&head);

    // The router decision: a path with a native Form handler is served
    // entirely in the kernel; a path with no handler fans out to the
    // Python upstream (if --upstream is set) or 404s.
    let body: String;
    let status: String;
    let router: &str;
    // The response's Content-Type for the BUFFERED arms (native / 404). The
    // fan-out arm streams and returns early — it relays the upstream's Content-Type
    // and end-to-end headers itself, so they never reach this buffered emit. A
    // native handler emitting JSON sets the type below; a 404 leaves it empty, so
    // the ONE emit shape (http_response) defaults to text/plain. `resp_headers`
    // stays empty on both buffered arms — native/404 relay no extra end-to-end
    // headers; the router owns all framing on those arms.
    let mut resp_content_type = String::new();
    let mut resp_headers: Vec<(String, String)> = Vec::new();
    let route_choice = if route_python_fallback_requested(&req_headers) {
        None
    } else {
        Some(route_choice_for_request(
            route_specs,
            &method,
            &path,
            &req_headers,
            &query_data,
            &request_body,
        ))
    };
    if let Some(choice) = route_choice.as_ref() {
        record_router_choice_metrics(router_metrics, choice);
        if let Some(trace) = &mut k.trace {
            trace.record_route_choice(choice);
        }
    }
    if let Some(selection) = route_choice
        .as_ref()
        .and_then(|choice| choice.selected.as_ref())
    {
        let route = selection.route;
        crash_context.set_operation(
            "serve-handler",
            format!(
                "worker={} request={} {} route={} handler={}",
                crash_context.worker_id, method, path, route.pattern, route.name
            ),
        );
        // NATIVE: served entirely in Form, no Python in the path.
        // Build the compatibility handler alist as Value::List of (key, value)
        // pairs. Router context is prepended so reserved router facts win over any
        // same-named client field; query params AND body fields follow uniformly
        // (form-urlencoded merged in; JSON/other captured under "__body__"). The
        // typed KernelHTTPRequest in router context preserves method/path/headers,
        // query fields, and raw body without flattening them into this projection.
        let metrics_snapshot = router_metrics_snapshot(router_metrics, route_specs.len());
        let mut handler_data = router_context_data(
            &method,
            &target,
            &path,
            upstream,
            &metrics_snapshot,
            route_choice.as_ref(),
        );
        handler_data.extend(
            request_data
                .iter()
                .map(|(k, v)| (k.clone(), Value::Str(v.clone().into()))),
        );
        let q_alist = Value::List(Arc::new(
            handler_data
                .iter()
                .map(|(k, v)| Value::List(vec![Value::Str(k.clone().into()), v.clone()].into()))
                .collect(),
        ));
        let request_arg = if route.typed_request {
            router_http_request_value(&selection.candidate)
        } else {
            q_alist
        };
        let cl = route.handler.clone();
        let call_frame = arena.new_frame_with_capacity(Some(cl.env), cl.params.len());
        if cl.params.len() == 1 {
            arena.bind(call_frame, cl.params[0], request_arg);
        } else if cl.params.len() != 0 {
            let status = "500 Internal Server Error".to_string();
            let body = format!(
                "handler for {} wants {} params; serve passes 0 or 1\n",
                route.name,
                cl.params.len()
            );
            record_router_metrics(router_metrics, &path, "native-kernel-error");
            let _ = stream.write_all(
                http_response(&status, &body, "native-kernel-error", false, "", &[]).as_bytes(),
            );
            return false; // close on error — keep the framing unambiguous
        }
        // SECURITY: bound the eval input BEFORE running the handler. A native
        // handler recurses once per element of a param it splits into a list (a
        // `values=1,1,1,…` list), and the evaluator is not tail-call-optimized — so
        // an oversized crafted param recurses deep enough to overflow the worker
        // stack and abort the whole process (see NATIVE_HANDLER_INPUT_LIMIT). The
        // deepest possible recursion is bounded by the LARGEST single user param's
        // byte length (each param is a separate, sequential list walk; router
        // context fields are not user-controlled and are excluded). Answer an
        // oversized param with a 413 observably instead of evaluating it. A real
        // native query's params are tiny.
        let max_param_bytes: usize = request_data.iter().map(|(_, v)| v.len()).max().unwrap_or(0);
        if max_param_bytes > NATIVE_HANDLER_INPUT_LIMIT {
            let status = "413 Payload Too Large".to_string();
            let body = format!(
                "native handler param {} bytes exceeds the {}-byte limit\n",
                max_param_bytes, NATIVE_HANDLER_INPUT_LIMIT
            );
            record_router_metrics(router_metrics, &path, "native-kernel-error");
            let _ = stream.write_all(
                http_response(&status, &body, "native-kernel-error", false, "", &[]).as_bytes(),
            );
            return false; // close — the oversized request was fully read; drop it
        }
        let result = walk(k, arena, cl.body, call_frame);
        router = "native-kernel";
        // A native handler can return the first-class KernelHTTPResponse cell:
        //   kh-response(status, list(kh-header(name, value)...), body)
        // The router reads that Form value directly and emits exact
        // status/header/body framing. The older `(respond code body)` shape stays
        // accepted as a status-only compatibility projection.
        match handler_native_response(&result) {
            Some(native_response) => {
                status = format!(
                    "{} {}",
                    native_response.status_code,
                    http_reason(native_response.status_code)
                );
                body = native_response.body;
                resp_content_type = native_response.content_type;
                resp_headers = native_response.headers;
            }
            None => {
                status = "200 OK".to_string();
                body = result.display();
            }
        }
        // A native handler that emits a JSON document (its rendered body opens
        // with `{` or `[`) is served as application/json, so a route promoted
        // from the CPython upstream returns the SAME Content-Type its FastAPI
        // twin did — byte-identical body AND type. A scalar handler ("ok",
        // "0.8125", "39") opens with neither, so it keeps the text/plain
        // default. The router header (X-Form-Router: native-kernel) still tells
        // the honest provenance: the kernel served this, not CPython.
        if resp_content_type.trim().is_empty() {
            if let Some(c) = body.trim_start().as_bytes().first() {
                if *c == b'{' || *c == b'[' {
                    resp_content_type = "application/json".to_string();
                }
            }
        }
    } else if let Some(upstream_base) = upstream {
        // FAN-OUT (STREAMING): no native handler — forward to the Python upstream
        // and PIPE its response body straight back to the client, with the whole
        // body NEVER held in one buffer. The kernel owns the front door; Python is
        // the upstream for the not-yet-native tail. Each worker issues its own
        // independent fan-out hop over its OWN per-worker upstream connection pool
        // (no locking — the worker is serial and owns the pool the way it owns its
        // Kernel + Arena), so repeated fan-outs REUSE one keep-alive connection to
        // the upstream and amortize the TCP handshake. The client's METHOD, BODY,
        // and end-to-end request headers (Authorization, Cookie, Accept*, …) are
        // forwarded so an authenticated/content-typed route is fronted truthfully;
        // the UPSTREAM's response status, Content-Type, and end-to-end headers
        // (Set-Cookie, Cache-Control, Location, …) are relayed back, then the body
        // is streamed byte-identical (raw bytes, no UTF-8 round-trip) in fixed 64
        // KiB chunks. Hop-by-hop headers are stripped both ways; the router owns
        // the client-hop framing (Content-Length echoed for a Length body,
        // Transfer-Encoding: chunked relayed for a chunked body, close-framing for
        // an unframed one; Connection per the client's intent). This arm does its
        // OWN client write (head + streamed body) and returns the client keep-alive
        // verdict directly — it does NOT fall through to the buffered emit below.
        record_router_metrics(router_metrics, &path, "fanout-python");
        return fanout_stream_to_client(
            stream,
            keep_alive,
            upstream_base,
            &method,
            &target,
            &req_headers,
            &body_bytes,
            upstream_pool,
        );
    } else if method == "OPTIONS" && channel_policy_method_known(&channel_policy, "OPTIONS") {
        // A router with no matching native route and no upstream can still answer
        // protocol discovery as a native no-body invitation. Exact OPTIONS routes
        // still win above through the ordinary route-choice path.
        status = "204 No Content".to_string();
        body = String::new();
        router = "local-control";
        resp_headers.push((
            "Allow".to_string(),
            channel_policy_allow_header_value(&channel_policy),
        ));
    } else {
        // No native handler and no upstream configured.
        status = "404 Not Found".to_string();
        body = format!("no route for {}\n", path);
        router = "local-control";
    }
    record_router_metrics(router_metrics, &path, router);
    // Frame the response with an accurate Content-Length and the keep-alive
    // verdict, the upstream's Content-Type + relayed end-to-end headers on a
    // fan-out (empty -> text/plain + no extra headers on native/404). The router
    // owns Content-Length + Connection; the relayed set was already filtered to
    // exclude those. If the write fails the peer is gone — close the loop.
    if stream
        .write_all(
            http_response(
                &status,
                buffered_response_body_for_method_with_policy(&channel_policy, &method, &body),
                router,
                keep_alive,
                &resp_content_type,
                &resp_headers,
            )
            .as_bytes(),
        )
        .is_err()
    {
        return false;
    }
    keep_alive
}

// How long an idle kept-alive connection may sit between requests before the
// server closes it and frees the worker. HTTP/1.1 keep-alive holds the socket
// open after a response so the next request reuses the same TCP connection
// (saving a handshake each time); without a cap an idle client would pin a
// worker forever and starve the pool (thread-per-connection: a worker serving
// one keep-alive client is unavailable to others until the connection closes or
// this timeout fires). 5s is a conservative default — long enough that a normal
// client's back-to-back requests stay on one connection, short enough that an
// abandoned connection frees its worker quickly. The production tuning knobs are
// THIS value and the worker count (cli_serve --workers).
const KEEPALIVE_IDLE_TIMEOUT: Duration = Duration::from_secs(5);

// Fan-out hop timeouts so a SLOW or HUNG upstream cannot pin a worker forever.
// The client-hop already reaps an IDLE connection (KEEPALIVE_IDLE_TIMEOUT above);
// these are the symmetric robustness on the UPSTREAM hop, but for a HUNG (not
// merely idle) upstream they must bound the ACTIVE request — connect, write, and
// read each get a deadline, and an expiry returns a clean 504 to the client
// instead of blocking the worker indefinitely. Without these, the worker pool
// (--workers) starves under load: enough hung fan-outs and no worker is free to
// serve other requests.
//
//   - CONNECT (~5s): the upstream must accept the TCP connection within this; a
//     non-listening / blackholed / unreachable upstream addr that never completes
//     the handshake times out here rather than blocking forever.
//   - READ (~30s): the TOTAL per-read deadline once connected. 30s is long enough
//     for a legitimately slow endpoint to respond, short enough that a genuinely
//     hung upstream (accepts the connection but never sends the response) frees
//     the worker rather than pinning it. A read that hits TimedOut/WouldBlock is
//     treated as an upstream timeout -> 504.
//   - WRITE (~30s): so a stuck write (an upstream that accepts but never drains
//     its receive buffer) cannot hang the worker either.
//
// These are host-boundary defaults. Route-specific timeout policy belongs in
// Form-visible router configuration, not environment variables; until that
// config cell exists, the kernel surface stays explicit and fixed here.
const FANOUT_CONNECT_TIMEOUT_DEFAULT_MS: u64 = 5_000;
const FANOUT_READ_TIMEOUT_DEFAULT_MS: u64 = 30_000;

fn fanout_connect_timeout() -> Duration {
    Duration::from_millis(FANOUT_CONNECT_TIMEOUT_DEFAULT_MS)
}

fn fanout_read_timeout() -> Duration {
    Duration::from_millis(FANOUT_READ_TIMEOUT_DEFAULT_MS)
}

// The TOTAL wall-clock a client gets to deliver one whole request (request line +
// headers + body). KEEPALIVE_IDLE_TIMEOUT bounds a single stalled read, but it is
// a per-read IDLE timer: a slowloris that trickles one byte every few seconds
// resets it forever and never finishes the request, pinning a worker. This is the
// symmetric client-hop bound to the fan-out read timeout above — a deadline
// checked across ALL reads of one request, so a request not fully received within
// it is dropped and the worker freed. 30s is far longer than a legitimate client
// needs to send a (small, mostly-GET) request even on a slow link, short enough
// that a trickle attacker cannot hold a worker indefinitely.
const MAX_REQUEST_READ_TIMEOUT_DEFAULT_MS: u64 = 30_000;

fn max_request_read_timeout() -> Duration {
    Duration::from_millis(MAX_REQUEST_READ_TIMEOUT_DEFAULT_MS)
}

// SECURITY: the largest TOTAL input (query + body param bytes) a NATIVE Form
// handler will evaluate. The Form evaluator is a tree-walker WITHOUT tail-call
// optimization, and the native handlers recurse once per input list element
// (`ints_of`, `split_commas`, the score folds, …). So a crafted param like
// `values=1,1,1,…` with hundreds of thousands of elements — a few hundred KB,
// still UNDER the request-body shape cap — recurses deep enough to OVERFLOW the
// worker stack and ABORT THE WHOLE PROCESS (every worker dies): a one-request
// remote kill, confirmed empirically (~200k elements aborts). A real native-route
// query is a handful of small params; this caps the eval input far above any
// legitimate use and far below the overflow, so an oversized input is answered
// (413) instead of evaluated. (The proper fix — TCO in the evaluator — is a
// separate, parity-bearing change; this serve-path bound makes native routes safe
// to serve in the meantime.)
const NATIVE_HANDLER_INPUT_LIMIT: usize = 16 * 1024;

// A fan-out hop failure, classified so the caller knows whether to RETRY or 504:
//   - Timeout: the upstream is reachable but SLOW/HUNG — connect, write, or read
//     hit its deadline (TimedOut / WouldBlock). Retrying does NOT help (the
//     upstream is hung, a retry only doubles the latency before the same timeout),
//     so this becomes a 504 Gateway Timeout, never a retry.
//   - Closed: the connection was CLOSED by the upstream (immediate EOF / broken
//     pipe on a pooled-connection reuse — the upstream idle-closed it). This is
//     the stale-pool path: a fresh connection + ONE retry of the same request.
//   - Other: a resolve failure, a malformed response, an oversized body — neither
//     a timeout nor a stale-close; surfaced as a 502-class error, not retried.
// This is what keeps a timeout from becoming an infinite retry loop: only Closed
// retries (once), and only on a POOLED connection; a Timeout is terminal -> 504.
enum FanoutError {
    Timeout(String),
    Closed(String),
    Other(String),
}

// Classify an io::Error from a fan-out connect/write/read into the retry-vs-504
// decision:
//   - TimedOut / WouldBlock -> Timeout. TimedOut is the connect deadline (and the
//     read/write deadline on Windows); WouldBlock is the read/write deadline on
//     Unix (set_read_timeout/set_write_timeout surface as WouldBlock there). A
//     hung upstream lands here -> 504, never retried.
//   - BrokenPipe / ConnectionReset / ConnectionAborted / UnexpectedEof -> Closed.
//     A POOLED connection the upstream already closed can surface as a write EPIPE
//     or a reset BEFORE the read sees EOF; treating these as Closed preserves the
//     stale-pool reconnect+retry-once path (the same robustness the pre-timeout
//     code had when ANY pooled error retried).
//   - everything else -> Other (a 502-class error; not retried).
fn classify_io_error(e: &std::io::Error, context: &str) -> FanoutError {
    use std::io::ErrorKind::*;
    match e.kind() {
        TimedOut | WouldBlock => FanoutError::Timeout(format!("{}: {}", context, e)),
        BrokenPipe | ConnectionReset | ConnectionAborted | UnexpectedEof => {
            FanoutError::Closed(format!("{}: {}", context, e))
        }
        _ => FanoutError::Other(format!("{}: {}", context, e)),
    }
}

// Serve a connection's full keep-alive LIFETIME: repeatedly handle requests on
// the SAME TcpStream until the client closes it, an error/EOF arrives, the idle
// read-timeout fires, or a response forces close (client `Connection: close`,
// 413, handler error). This wraps the per-request handle_request in a loop —
// the per-request serving shape stays ONE factored function (core-abstraction-
// first); keep-alive is the loop around it, not a fork of the logic.
//
// An idle read-timeout (KEEPALIVE_IDLE_TIMEOUT) is set on the stream so a
// connection that goes quiet between requests does not pin this worker forever:
// the next read_request returns Error (the timeout surfaces as a read error),
// the loop ends, the stream drops, and the worker returns to the queue free to
// serve another connection.
fn serve_connection(
    mut stream: TcpStream,
    k: &mut Kernel,
    arena: &mut Arena,
    route_specs: &RouteSpecs,
    upstream: &Option<String>,
    upstream_pool: &mut UpstreamPool,
    router_metrics: &Arc<Mutex<RouterMetrics>>,
    crash_context: &ServeCrashContext,
) {
    // Idle timeout so a held-open keep-alive connection cannot starve the pool.
    let _ = stream.set_read_timeout(Some(KEEPALIVE_IDLE_TIMEOUT));
    // WRITE timeout too: a client that stops READING its response (a slow-read
    // attack, or one that opened the connection only to stall) would otherwise
    // block the worker in `write_all` on TCP backpressure indefinitely. Each write
    // must make progress within this or the connection is dropped, freeing the
    // worker. Per-write (not a total), so a legitimate client on a slow link that
    // keeps accepting chunks is unaffected.
    let _ = stream.set_write_timeout(Some(KEEPALIVE_IDLE_TIMEOUT));
    // Bytes already read past one request's end belong to the NEXT request on
    // this connection (pipelining) — carried across loop iterations so no byte
    // is dropped between requests.
    let mut carry: Vec<u8> = Vec::new();
    // Serve requests on this one connection until handle_request says to close.
    // The worker's upstream connection pool (`upstream_pool`) outlives a single
    // client connection — it is owned by the worker and threaded through every
    // connection it serves, so a keep-alive upstream connection opened while
    // serving client A is reused for client B on the same worker.
    while handle_request(
        &mut stream,
        &mut carry,
        k,
        arena,
        route_specs,
        upstream,
        upstream_pool,
        router_metrics,
        crash_context,
    ) {}
}

#[derive(Clone)]
struct ServeCrashContext {
    worker_id: usize,
    routes_path: Arc<String>,
    routes_source: Arc<String>,
}

impl ServeCrashContext {
    fn set_operation(&self, mode: &str, operation: String) {
        let args = vec![
            "serve".to_string(),
            "--routes".to_string(),
            self.routes_path.as_ref().clone(),
        ];
        set_thread_crash_trace_context(CrashTraceContext {
            mode: mode.to_string(),
            args,
            source: self.routes_source.as_ref().clone(),
            source_label: self.routes_path.as_ref().clone(),
            operation,
        });
    }
}

// One kernel worker. Builds its OWN Kernel + Arena (the routes.fk loaded once
// into it at startup — !Sync, never shared), then pulls accepted streams from
// the shared work queue and serves each connection's full keep-alive lifetime
// via serve_connection (which loops handle_request on the one stream). N of
// these run concurrently behind the accept loop; because each owns its kernel,
// concurrent requests never corrupt one another's state.
fn worker_loop(
    id: usize,
    program: Arc<RouteProgram>,
    routes_path: Arc<String>,
    routes_source: Arc<String>,
    route_data: Arc<RouteDataRegistry>,
    upstream: Arc<Option<String>>,
    rx: Arc<Mutex<mpsc::Receiver<TcpStream>>>,
    router_metrics: Arc<Mutex<RouterMetrics>>,
    form_mode: bool,
) {
    let crash_context = ServeCrashContext {
        worker_id: id,
        routes_path: Arc::clone(&routes_path),
        routes_source,
    };
    crash_context.set_operation("serve-worker-load", format!("worker={} load routes", id));
    let (mut k, mut arena, route_specs, root_env) =
        match build_worker_kernel_with_route_data(&program, &routes_path, &route_data) {
            Ok(t) => t,
            Err(e) => {
                eprintln!("serve: worker {} failed to load routes: {}", id, e);
                return;
            }
        };
    // --form: resolve the kh-serve closure + routes + registry globals ONCE, so
    // every connection runs the Form serve pipeline directly — Form does parse,
    // route, dispatch, render; the kernel only opens the socket and walks it.
    let form_serve: Option<(Arc<Closure>, Value, Value)> = if form_mode {
        // kh-serve-conn (http-socket.fk) is the STREAMING entry: it takes the
        // socket handle and owns the I/O. (kh-serve, the pure string-in/string-out
        // core, is what kh-serve-conn calls between the recv and send loops.)
        let kh_id = k.intern_string("kh-serve-conn").inst;
        match arena.lookup(root_env, kh_id) {
            Some(Value::Closure(c)) => {
                let routes_id = k.intern_string("routes").inst;
                let registry_id = k.intern_string("registry").inst;
                let routes_val = arena
                    .lookup(root_env, routes_id)
                    .unwrap_or(Value::List(vec![].into()));
                let registry_val = arena
                    .lookup(root_env, registry_id)
                    .unwrap_or(Value::List(vec![].into()));
                Some((c, routes_val, registry_val))
            }
            _ => {
                eprintln!(
                    "serve --form: worker {} could not resolve kh-serve-conn as a closure \
                     (the manifest must prelude http-socket.fk)",
                    id
                );
                return;
            }
        }
    } else {
        None
    };
    // This worker's OWN upstream connection pool — keep-alive connections to the
    // fan-out upstream, reused across every client connection this worker serves.
    // No locking: the worker is serial (it serves one client connection at a
    // time) and owns its pool exactly as it owns its Kernel + Arena (the !Sync
    // isolation from the worker pool). Repeated fan-outs therefore amortize the
    // TCP handshake to the upstream instead of paying a fresh connect each time.
    let mut upstream_pool = UpstreamPool::new();
    loop {
        // Lock only to dequeue one stream, then release before serving so the
        // workers truly run in parallel (the lock guards the queue, not the
        // request handling).
        let stream = {
            let guard = match rx.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            guard.recv()
        };
        match stream {
            Ok(s) => {
                crash_context.set_operation(
                    "serve-connection",
                    format!("worker={} connection accepted", id),
                );
                let served = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    if let Some((ref cl, ref routes_val, ref registry_val)) = form_serve {
                        serve_connection_form(
                            s,
                            &mut k,
                            &mut arena,
                            cl,
                            routes_val,
                            registry_val,
                            &crash_context,
                        );
                    } else {
                        serve_connection(
                            s,
                            &mut k,
                            &mut arena,
                            &route_specs,
                            &upstream,
                            &mut upstream_pool,
                            &router_metrics,
                            &crash_context,
                        );
                    }
                }));
                if let Err(payload) = served {
                    let msg = panic_payload_message(payload.as_ref());
                    eprintln!(
                        "form-kernel-rust serve: recovered fatal in worker {}: {}; \
                         connection closed; worker continues",
                        id, msg
                    );
                }
            }
            // Sender dropped (listener closed) — drain done, worker exits.
            Err(_) => return,
        }
    }
}

// The form-stdlib preludes a source manifest is source-compiled through, in load
// order: the ontology loader asks the kernel-native bp table for coordinates,
// then bml-source.fk names reusable BML source cells, and source-compiler.fk
// lowers a `section [...]` against those bindings.
// This is the SAME prelude set + lowering `form/validate.sh prepare_sources`
// runs to source-compile a `section [...]` file — the router reuses the body's
// own compiler, not a Rust reimplementation of a source-language parser.
const SOURCE_COMPILE_PRELUDES: [&str; 7] = [
    "form-ontology-loader.fk",
    "line-grammar.fk",
    "bmf-core.fk",
    "bmf-grammar.fk",
    "bml.fk",
    "bml-source.fk",
    "source-compiler.fk",
];

// Source-language model that must be present in the worker kernels whenever a
// route manifest uses high-level classes/templates. These are compiled into the
// same Form Recipe object as the manifest in this order. That keeps the runtime
// carrier explicit: source entry plus Form stdlib language model yields one
// executable Recipe object whose walk binds KernelHTTPRoute cells.
const SOURCE_ROUTE_LANGUAGE_PRELUDES: [&str; 5] = [
    "json.fk",
    "core.fk",
    "sha256.fk",
    "kernel-http.fk",
    "language-model.fk",
];

// A routes manifest is source-authored (vs raw S-expression) iff it opens a
// `section [...]` block — the source-compiler's own section marker. The check
// is the same `section [` line-prefix scan form-source-compile-loop uses to
// find sections, so "needs lowering" and "has a section" are the one judgement.
fn manifest_has_source_sections(src: &str) -> bool {
    src.lines()
        .any(|line| line.trim_start().starts_with("section ["))
}

fn source_compile_cwd_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

#[derive(Clone)]
enum RouteProgram {
    Source(Arc<String>),
    RecipeObject(Arc<CompiledRouteProgram>),
}

struct CompiledRouteProgram {
    kernel: Kernel,
    root: NodeID,
}

// In-process cache of the self-contained BMF bootstrap .fkb, keyed by stdlib dir.
fn bmf_bootstrap_cache() -> &'static Mutex<std::collections::HashMap<PathBuf, Arc<Vec<u8>>>> {
    static C: OnceLock<Mutex<std::collections::HashMap<PathBuf, Arc<Vec<u8>>>>> = OnceLock::new();
    C.get_or_init(|| Mutex::new(std::collections::HashMap::new()))
}

// The BMF bootstrap as ONE self-contained .fkb: the source-compile preludes parsed
// into a single recipe tree — every defn the source-compiler uses (g-parse, the BML
// grammar, the verb tables, the ontology loader) bundled in one artifact. The source-
// compile loads THIS instead of re-reading the .fk preludes live on every section
// compile, so a stdlib edit can no longer reach into a compile mid-flight: the
// machinery is PINNED per build. It is emitted-if-stale (any prelude newer than the
// cached .fkb) by THIS kernel binary, so the binary and the bootstrap can never drift
// apart — the version mismatch that made a fresh stdlib panic an old kernel is gone.
// (A residual data-coupling remains: the ontology loader still reads form-ontology.json
// at load; pinning that DATA into the artifact is a follow-up. The recipes are pinned.)
fn ensure_bmf_bootstrap(stdlib_abs: &std::path::Path) -> Result<Arc<Vec<u8>>, String> {
    if let Some(b) = bmf_bootstrap_cache()
        .lock()
        .map_err(|_| "bmf bootstrap cache poisoned".to_string())?
        .get(stdlib_abs)
    {
        return Ok(b.clone());
    }
    let fkb_path = stdlib_abs.join(".cache").join("bmf-bootstrap.fkb");
    let prelude_paths: Vec<PathBuf> = SOURCE_COMPILE_PRELUDES
        .iter()
        .map(|n| stdlib_abs.join(n))
        .collect();
    let fkb_mtime = fs::metadata(&fkb_path).and_then(|m| m.modified()).ok();
    let stale = match fkb_mtime {
        None => true,
        Some(t) => prelude_paths.iter().any(|p| {
            fs::metadata(p)
                .and_then(|m| m.modified())
                .map(|pt| pt > t)
                .unwrap_or(true)
        }),
    };
    let bytes = if stale {
        let mut parts = Vec::with_capacity(prelude_paths.len());
        for p in &prelude_paths {
            parts.push(fs::read_to_string(p).map_err(|e| {
                format!(
                    "bmf bootstrap: read prelude {}: {} (is --stdlib {} correct?)",
                    p.display(),
                    e,
                    stdlib_abs.display()
                )
            })?);
        }
        let src = parts.join("\n");
        let emitted = std::thread::Builder::new()
            .name("bmf-bootstrap-emit".to_string())
            .stack_size(form_kernel_stack_bytes())
            .spawn(move || {
                let mut k = Kernel::new();
                let root = read_root_from_source(&mut k, &src);
                serialize_artifact(&k, root)
            })
            .map_err(|e| format!("bmf bootstrap: spawn emit: {}", e))?
            .join()
            .map_err(|_| "bmf bootstrap: emit panicked".to_string())?;
        let _ = fs::create_dir_all(stdlib_abs.join(".cache"));
        let _ = fs::write(&fkb_path, &emitted); // best-effort disk cache; in-process map is source of truth
        emitted
    } else {
        fs::read(&fkb_path)
            .map_err(|e| format!("bmf bootstrap: read {}: {}", fkb_path.display(), e))?
    };
    let arc = Arc::new(bytes);
    bmf_bootstrap_cache()
        .lock()
        .map_err(|_| "bmf bootstrap cache poisoned".to_string())?
        .insert(stdlib_abs.to_path_buf(), arc.clone());
    Ok(arc)
}

// Run a source-compile driver against the PINNED bootstrap: deserialize the bootstrap
// .fkb's recipes (binding the machinery), then run the driver in the SAME env, so the
// driver resolves every name against the pinned machinery — never the live .fk on disk.
// `(do bootstrap driver)` shares one env: the bootstrap's defns bind, the driver uses them.
fn run_source_with_bootstrap(
    name: &str,
    bootstrap: Arc<Vec<u8>>,
    driver_body: String,
) -> Result<(Kernel, Value), String> {
    let handle = std::thread::Builder::new()
        .name(name.to_string())
        .stack_size(form_kernel_stack_bytes())
        .spawn(move || -> Result<(Kernel, Value), String> {
            let mut k = Kernel::new();
            let bootstrap_root = deserialize_artifact(&mut k, &bootstrap)
                .map_err(|e| format!("source-compile: load bootstrap: {}", e))?;
            let driver_root = read_root_from_source(&mut k, &driver_body);
            let combined = k.intern(cat_block(RBLK_DO), vec![bootstrap_root, driver_root]);
            let value = execute_root(&mut k, combined);
            Ok((k, value))
        })
        .map_err(|e| format!("source-compile: spawn {} thread: {}", name, e))?;
    handle
        .join()
        .map_err(|_| format!("source-compile: {} panicked", name))?
}

fn compile_source_section_to_recipe_node(
    dialect_name: &str,
    body: &str,
    stdlib_abs: &std::path::Path,
) -> Result<(Kernel, NodeID), String> {
    let bootstrap = ensure_bmf_bootstrap(stdlib_abs)?;
    let driver_body = format!(
        "(fsc-compile-section-recipe {} {})",
        sexp_string_literal(dialect_name),
        sexp_string_literal(body)
    );
    let (kernel, value) =
        run_source_with_bootstrap("route-section-compile", bootstrap, driver_body)?;
    match value {
        Value::Nid(root) => Ok((kernel, root)),
        _ => Err("source-compile: fsc-compile-section-recipe did not return a recipe".to_string()),
    }
}

fn import_recipe_leaf(dst: &mut Kernel, src: &Kernel, nid: NodeID) -> NodeID {
    if nid.level == LEVEL_TRIVIAL {
        return match nid.ty {
            TRIV_INT => dst.intern_trivial_int((nid.inst as i32) as i64),
            TRIV_STRING => dst.intern_string(src.name_str(nid.inst)),
            TRIV_BOOL | TRIV_NULL => nid,
            TRIV_FLOAT32 => dst.intern_trivial_float32(src.decode_float32(nid.inst)),
            TRIV_FLOAT64 => dst.intern_trivial_float64(src.decode_float64(nid.inst)),
            _ => nid,
        };
    }
    nid
}

fn import_recipe_node(
    dst: &mut Kernel,
    src: &Kernel,
    nid: NodeID,
    memo: &mut HashMap<NodeID, NodeID>,
) -> NodeID {
    if let Some(imported) = memo.get(&nid) {
        return *imported;
    }
    let imported = match src.by_id.get(&nid) {
        Some(recipe) => {
            let category = import_recipe_node(dst, src, recipe.category, memo);
            let children = recipe
                .children
                .iter()
                .map(|child| import_recipe_node(dst, src, *child, memo))
                .collect();
            dst.intern(category, children)
        }
        None => import_recipe_leaf(dst, src, nid),
    };
    memo.insert(nid, imported);
    imported
}

fn import_recipe_from(dst: &mut Kernel, src: &Kernel, root: NodeID) -> NodeID {
    let mut memo = HashMap::new();
    import_recipe_node(dst, src, root, &mut memo)
}

fn line_next(src: &str, i: usize) -> usize {
    match src[i..].find('\n') {
        Some(offset) => i + offset + 1,
        None => src.len(),
    }
}

fn line_end(src: &str, i: usize) -> usize {
    match src[i..].find('\n') {
        Some(offset) => i + offset,
        None => src.len(),
    }
}

fn find_section_from(src: &str, mut i: usize) -> Option<usize> {
    while i < src.len() {
        let end = line_end(src, i);
        let line = &src[i..end];
        let leading = line.len() - line.trim_start().len();
        if line.trim_start().starts_with("section [") {
            return Some(i + leading);
        }
        i = line_next(src, i);
    }
    None
}

fn find_section_close(src: &str, body_start: usize) -> Result<usize, String> {
    let mut i = body_start;
    let mut depth: i64 = 0;
    while i < src.len() {
        let end = line_end(src, i);
        let line = src[i..end].trim();
        if line == "}" {
            if depth == 0 {
                return Ok(i);
            }
            depth -= 1;
        } else if line.ends_with('{') {
            depth += 1;
        }
        i = line_next(src, i);
    }
    Err("source-compile: unterminated section block".to_string())
}

fn parse_raw_route_segment(k: &mut Kernel, roots: &mut Vec<NodeID>, src: &str) {
    let toks = tokenize_sexp(src);
    if toks.is_empty() {
        return;
    }
    let root = if count_top_level(&toks) == 1 {
        let (root, _) = read_sexp(k, &toks, 0);
        root
    } else {
        let wrapped = format!("(do {})", src);
        read_root_from_source(k, &wrapped)
    };
    roots.push(root);
}

fn compile_route_source_into_recipe(
    k: &mut Kernel,
    roots: &mut Vec<NodeID>,
    source_label: &str,
    src: &str,
    stdlib_abs: &std::path::Path,
) -> Result<(), String> {
    let mut cursor = 0;
    while let Some(section_pos) = find_section_from(src, cursor) {
        parse_raw_route_segment(k, roots, &src[cursor..section_pos]);

        let dialect_start = section_pos + "section [".len();
        let dialect_end = src[dialect_start..]
            .find(']')
            .map(|offset| dialect_start + offset)
            .ok_or_else(|| format!("source-compile: {} section missing ]", source_label))?;
        let open = src[dialect_end..]
            .find('{')
            .map(|offset| dialect_end + offset)
            .ok_or_else(|| format!("source-compile: {} section missing {{", source_label))?;
        let close = find_section_close(src, open + 1)?;
        let dialect_name = src[dialect_start..dialect_end].trim();
        let body = &src[open + 1..close];
        let (section_kernel, section_root) =
            compile_source_section_to_recipe_node(dialect_name, body, stdlib_abs)?;
        let section_root = import_recipe_from(k, &section_kernel, section_root);
        roots.push(section_root);
        cursor = line_next(src, close);
    }
    parse_raw_route_segment(k, roots, &src[cursor..]);
    Ok(())
}

// Source-compile a routes manifest to one in-memory Form Recipe object. This is
// PATH A: source-compile AT LOAD. The router accepts a source manifest directly,
// lowers it through the body's own form-stdlib
// source-compiler, and gives worker kernels an object graph to clone/import from
// directly. No worker reparses lowered source; no route-runtime serialization or
// sidecar is required. Source text remains the human entry point, while Form
// objects are the runtime carrier.
fn source_compile_manifest_recipe_object(
    routes_path: &str,
    stdlib_dir: &str,
) -> Result<CompiledRouteProgram, String> {
    let _cwd_guard = source_compile_cwd_lock()
        .lock()
        .map_err(|_| "source-compile: cwd lock poisoned".to_string())?;

    // Source compilation shares validate.sh's form/ cwd shape. The compiler
    // prelude now reads its coordinates from the kernel-native bp table, but
    // route-language source files may still use repo-relative stdlib paths, so
    // object compilation temporarily runs from the PARENT of the stdlib dir and
    // then restores the previous cwd.
    let stdlib_path = std::path::Path::new(stdlib_dir);
    let stdlib_abs = stdlib_path
        .canonicalize()
        .map_err(|e| format!("source-compile: --stdlib {}: {}", stdlib_dir, e))?;
    let stdlib_parent = stdlib_abs
        .parent()
        .ok_or_else(|| format!("source-compile: --stdlib {} has no parent dir", stdlib_dir))?
        .to_path_buf();
    let stdlib_name = stdlib_abs
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| "form-stdlib".to_string());
    let routes_abs = std::path::Path::new(routes_path)
        .canonicalize()
        .map_err(|e| format!("source-compile: --routes {}: {}", routes_path, e))?
        .to_string_lossy()
        .to_string();

    // Set cwd to the stdlib's parent so the ontology loader's "form-stdlib/..."
    // relative reads resolve, run the compile, then restore cwd. Restoring is
    // important: the rest of cli_serve (and the workers) expect the original cwd.
    let prev_cwd = env::current_dir().map_err(|e| format!("source-compile: read cwd: {}", e))?;
    // Guard against a surprising layout where the requested stdlib directory
    // is not the form-stdlib source tree the compiler prelude expects.
    if stdlib_name != "form-stdlib" {
        return Err(format!(
            "source-compile: --stdlib must point at a directory named 'form-stdlib' \
             (the source-compiler loads form-ontology-loader.fk and source-compiler.fk from it); \
             got {}",
            stdlib_abs.display()
        ));
    }
    env::set_current_dir(&stdlib_parent)
        .map_err(|e| format!("source-compile: chdir {}: {}", stdlib_parent.display(), e))?;

    let compile_result = (|| {
        let mut k = Kernel::new();
        let mut roots = Vec::new();
        for name in SOURCE_ROUTE_LANGUAGE_PRELUDES {
            let source_path = stdlib_abs.join(name);
            let source = fs::read_to_string(&source_path).map_err(|e| {
                format!(
                    "source-compile: route-language prelude {}: {} (is --stdlib {} correct?)",
                    source_path.display(),
                    e,
                    stdlib_dir
                )
            })?;
            compile_route_source_into_recipe(
                &mut k,
                &mut roots,
                &source_path.to_string_lossy(),
                &source,
                &stdlib_abs,
            )?;
        }
        let route_source = fs::read_to_string(&routes_abs)
            .map_err(|e| format!("source-compile: read routes {}: {}", routes_abs, e))?;
        compile_route_source_into_recipe(
            &mut k,
            &mut roots,
            &routes_abs,
            &route_source,
            &stdlib_abs,
        )?;
        let root = if roots.len() == 1 {
            roots[0]
        } else {
            k.intern(cat_block(RBLK_DO), roots)
        };
        Ok(CompiledRouteProgram { kernel: k, root })
    })();

    // Restore cwd before propagating any compile error, so a failed compile never
    // leaves the process in the stdlib's parent.
    let _ = env::set_current_dir(&prev_cwd);
    compile_result
}

// Source-compile an ordinary workload file list to one executable Form Recipe
// object. This is the non-router sibling of source_compile_manifest_recipe_object:
// caller-provided files load in order, `section [...]` blocks lower through the
// Form source compiler, and raw S-expression segments stay raw.
fn source_compile_file_workload_recipe_object(
    paths: &[String],
    stdlib_dir: &str,
) -> Result<CompiledRouteProgram, String> {
    let _cwd_guard = source_compile_cwd_lock()
        .lock()
        .map_err(|_| "source-compile: cwd lock poisoned".to_string())?;
    let stdlib_path = std::path::Path::new(stdlib_dir);
    let stdlib_abs = stdlib_path
        .canonicalize()
        .map_err(|e| format!("source-compile: --stdlib {}: {}", stdlib_dir, e))?;
    let stdlib_parent = stdlib_abs
        .parent()
        .ok_or_else(|| format!("source-compile: --stdlib {} has no parent dir", stdlib_dir))?
        .to_path_buf();
    let stdlib_name = stdlib_abs
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| "form-stdlib".to_string());
    if stdlib_name != "form-stdlib" {
        return Err(format!(
            "source-compile: --stdlib must point at a directory named 'form-stdlib'; got {}",
            stdlib_abs.display()
        ));
    }
    let input_paths: Result<Vec<PathBuf>, String> = paths
        .iter()
        .map(|path| {
            std::path::Path::new(path)
                .canonicalize()
                .map_err(|e| format!("source-compile: input {}: {}", path, e))
        })
        .collect();
    let input_paths = input_paths?;

    let prev_cwd = env::current_dir().map_err(|e| format!("source-compile: read cwd: {}", e))?;
    env::set_current_dir(&stdlib_parent)
        .map_err(|e| format!("source-compile: chdir {}: {}", stdlib_parent.display(), e))?;

    let compile_result = (|| {
        let mut k = Kernel::new();
        let mut roots = Vec::new();
        for source_path in &input_paths {
            let source = fs::read_to_string(source_path)
                .map_err(|e| format!("source-compile: read {}: {}", source_path.display(), e))?;
            compile_route_source_into_recipe(
                &mut k,
                &mut roots,
                &source_path.to_string_lossy(),
                &source,
                &stdlib_abs,
            )?;
        }
        let root = if roots.len() == 1 {
            roots[0]
        } else {
            k.intern(cat_block(RBLK_DO), roots)
        };
        Ok(CompiledRouteProgram { kernel: k, root })
    })();

    let _ = env::set_current_dir(&prev_cwd);
    compile_result
}

// Resolve every name in a compiled route recipe, returning the unresolved ones.
// The evaluator resolves names LAZILY — it raises `unbound: <name>` only when the
// walk reaches that node at serve time (RB_IDENT) — so a manifest with a dangling
// reference compiles to a recipe and only fails in production. This runs the Form
// resolution walk (form-stdlib/name-check.fk, scope-aware) over the lowered recipe
// so the dangling reference is found BEFORE anything is served. The resolver IS
// Form: this loads it into the route kernel and applies its `name-check` closure
// to the route recipe — no resolution logic duplicated in Rust.
fn name_check_route_recipe(
    k: &mut Kernel,
    stdlib_abs: &std::path::Path,
    route_root: NodeID,
) -> Result<Vec<String>, String> {
    let nc_path = stdlib_abs.join("name-check.fk");
    let nc_src = fs::read_to_string(&nc_path)
        .map_err(|e| format!("check: read {}: {}", nc_path.display(), e))?;
    let nc_root = read_root_from_source(k, &nc_src);
    let mut a = Arena::new();
    let env = a.new_frame(None);
    // Walk name-check.fk so `name-check` / `name-check-clean?` / `nc-*` bind in env.
    walk(k, &mut a, nc_root, env);
    // `known` seeds the resolvable set with every kernel native name. The manifest's
    // own defns are collected from the recipe by name-check's PASS 1; the natives are
    // NOT in the recipe, so they must be named here or every native call would report.
    let native_ids: Vec<NameID> = k
        .natives
        .keys()
        .copied()
        .chain(k.env_natives.keys().copied())
        .collect();
    let mut known: Vec<Value> = native_ids
        .into_iter()
        .map(|id| Value::Str(Arc::from(k.name_str(id))))
        .collect();
    // Seed the kernel's surface-verb vocabulary (build_verb): operators and
    // structural verbs resolve as typed nodes, not function lookups, so they are
    // known, not unbound. Without this the gate false-flags add/sub/…/and/or when
    // they ride as FNCALL callees in source-compiled machinery (verified: a
    // manifest using (add 6 2)/(mul 6 2) serves {"sum":8,"prod":12} while the gate
    // reported those very verbs unbound).
    known.extend(BUILD_VERBS.iter().map(|v| Value::Str(Arc::from(*v))));
    let known_val = Value::List(Arc::new(known));
    // Apply name-check(route_root, known) directly — the same closure resolution the
    // serve path uses for route handlers (resolve_route_handler -> arena.lookup).
    let nc_name = k.intern_string("name-check").inst;
    let cl = match a.lookup(env, nc_name) {
        Some(Value::Closure(c)) => c,
        _ => return Err("check: name-check not bound after loading name-check.fk".to_string()),
    };
    if cl.params.len() != 2 {
        return Err(format!(
            "check: name-check expects 2 params (program known), found {}",
            cl.params.len()
        ));
    }
    let frame = a.new_frame_with_capacity(Some(cl.env), 2);
    a.bind(frame, cl.params[0], Value::Nid(route_root));
    a.bind(frame, cl.params[1], known_val);
    let result = walk(k, &mut a, cl.body, frame);
    let mut unbound: Vec<String> = Vec::new();
    if let Value::List(xs) = result {
        for v in xs.iter() {
            if let Value::Str(s) = v {
                let name = s.to_string();
                if !unbound.contains(&name) {
                    unbound.push(name); // name-check cons-es one entry per reference; dedup
                }
            }
        }
    }
    Ok(unbound)
}

// check --routes <file> [--stdlib <dir>] — source-compile a routes manifest and
// resolve every name in the lowered recipe BEFORE serving. Exit non-zero, naming
// the unresolved symbols, if any reference is dangling. This is the compile-time
// gate the lazy evaluator lacks: a manifest that references an unbound symbol (e.g.
// production-routes.fk's `health_route_from_class`) becomes a clean error here
// instead of a serve-time panic — the silent-rot class. CI runs this over the
// manifests so a dangling reference can never reach main.
fn cli_check(args: &[String]) -> i32 {
    let mut routes_path: Option<String> = None;
    let mut stdlib_dir: String = "form-stdlib".to_string();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--routes" => {
                if i + 1 >= args.len() {
                    eprintln!("check: --routes requires an argument");
                    return 2;
                }
                routes_path = Some(args[i + 1].clone());
                i += 2;
            }
            "--stdlib" => {
                if i + 1 >= args.len() {
                    eprintln!("check: --stdlib requires an argument");
                    return 2;
                }
                stdlib_dir = args[i + 1].clone();
                i += 2;
            }
            other => {
                eprintln!("check: unknown argument: {}", other);
                return 2;
            }
        }
    }
    let routes_path = match routes_path {
        Some(p) => p,
        None => {
            eprintln!("check: --routes <file> is required");
            return 2;
        }
    };
    let stdlib_abs = match std::path::Path::new(&stdlib_dir).canonicalize() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("check: --stdlib {}: {}", stdlib_dir, e);
            return 2;
        }
    };
    let mut prog = match source_compile_manifest_recipe_object(&routes_path, &stdlib_dir) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("check: {}", e);
            return 1;
        }
    };
    match name_check_route_recipe(&mut prog.kernel, &stdlib_abs, prog.root) {
        Ok(unbound) if unbound.is_empty() => {
            println!("check: {} — every name resolves (0 unbound)", routes_path);
            0
        }
        Ok(unbound) => {
            eprintln!(
                "check: {} — {} unresolved name(s) — would panic at serve time:",
                routes_path,
                unbound.len()
            );
            for name in &unbound {
                eprintln!("  unbound: {}", name);
            }
            1
        }
        Err(e) => {
            eprintln!("check: {}", e);
            1
        }
    }
}

#[cfg(test)]
mod gate_known_set_tests {
    use super::*;

    // The name-resolution gate seeds `known` with BUILD_VERBS so a source-compiled
    // operator carried as an FNCALL callee isn't false-flagged unbound. That is only
    // safe if every BUILD_VERBS entry is a verb build_verb lowers to a TYPED node
    // (never the FNCALL fallback) — else seeding it would mask a genuinely-unbound
    // FNCALL of that name. This drift-guards that invariant: add a verb to
    // BUILD_VERBS without teaching build_verb to specialize it, and this fails.
    #[test]
    fn build_verbs_are_typed_not_fncall() {
        let mut k = Kernel::new();
        let a = k.intern_trivial_int(2);
        let b = k.intern_trivial_int(3);
        // operators + block-verbs take uniform args; `not` is unary.
        let uniform = [
            "add", "sub", "mul", "div", "mod", "eq", "ne", "lt", "le", "gt", "ge", "and", "or",
            "do", "seq", "params",
        ];
        for v in uniform {
            let node = build_verb(&mut k, v, vec![a, b]);
            assert_ne!(
                k.category(node),
                cat_fncall(),
                "build_verb({v}) fell through to FNCALL — the gate would mask a real unbound {v}"
            );
        }
        let not_node = build_verb(&mut k, "not", vec![a]);
        assert_ne!(k.category(not_node), cat_fncall());
        // let/if/defn carry special arg shapes (name/params repackaging); they are
        // structural by construction. Assert the test covers every BUILD_VERBS entry
        // so a new verb can't be added to the gate's known-set untested.
        let covered: Vec<&str> = uniform
            .iter()
            .copied()
            .chain(["not", "let", "if", "defn"])
            .collect();
        for v in BUILD_VERBS {
            assert!(
                covered.contains(v),
                "BUILD_VERBS has {v} but this test doesn't cover it"
            );
        }
        // and a verb build_verb does NOT know must hit the FNCALL fallback, so the
        // gate still flags genuinely-unbound names (e.g. health_route_from_class).
        let unknown = build_verb(&mut k, "health_route_from_class", vec![a, b]);
        assert_eq!(
            k.category(unknown),
            cat_fncall(),
            "an unknown verb must be FNCALL so the gate can flag it"
        );
    }
}

// Quote a path/string as an S-expression string literal for the compile driver:
// wrap in double quotes, escaping backslash and double-quote. Paths with a quote
// or backslash are exotic but must not break the driver's parse.
fn sexp_string_literal(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for ch in s.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            _ => out.push(ch),
        }
    }
    out.push('"');
    out
}

fn default_route_data_path(routes_path: &str) -> PathBuf {
    let mut path = PathBuf::from(routes_path);
    let stem = path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| "routes".to_string());
    path.set_file_name(format!("{}-data.json", stem));
    path
}

fn load_route_data_registry(
    routes_path: &str,
    route_data_path: Option<&str>,
) -> Result<RouteDataRegistry, String> {
    let path = match route_data_path {
        Some(path) => PathBuf::from(path),
        None => {
            let default_path = default_route_data_path(routes_path);
            if default_path.exists() {
                default_path
            } else {
                return Ok(RouteDataRegistry::default());
            }
        }
    };
    let body = fs::read_to_string(&path)
        .map_err(|e| format!("serve: read route data {}: {}", path.display(), e))?;
    let parsed: RouteDataFile = serde_json::from_str(&body)
        .map_err(|e| format!("serve: parse route data {}: {}", path.display(), e))?;
    Ok(RouteDataRegistry {
        routes: parsed.routes,
    })
}

// serve_connection_form — the Form-native serve path. Read the raw request and
// hand it to kh-serve; Form does parse, route, dispatch, and render; write the
// wire string it returns. No Rust parse/route/render, no fear-cap on the way in:
// the HTTP IS the recipe (kernel-http.fk + http-*.fk), and the kernel only opens
// the socket and walks the closure. One request per connection for now (the load
// balancer / client reconnects); keep-alive is a later breath. Because the load
// balancer routes only native paths here, a 404 from kh-serve means a path the
// balancer should not have sent — honest, not a fan-out concern.
fn serve_connection_form(
    stream: TcpStream,
    k: &mut Kernel,
    arena: &mut Arena,
    kh_serve_conn: &Arc<Closure>,
    routes_val: &Value,
    registry_val: &Value,
    crash_context: &ServeCrashContext,
) {
    crash_context.set_operation(
        "serve-form-handler",
        format!("worker={} form-mode kh-serve-conn", crash_context.worker_id),
    );
    // STREAMING: the kernel does NOT pre-read a buffer. It registers the accepted
    // connection as a Form socket handle and hands that handle to the recipe;
    // kh-serve-conn (http-socket.fk) owns ALL the I/O — loop-recv the request
    // (socket_recv until framed), run kh-serve, loop-send the response
    // (socket_send until drained), close. The bytes flow through Form, not a Rust
    // buffer. kh-serve-conn(conn, routes, registry).
    if kh_serve_conn.params.len() != 3 {
        return;
    }
    let h = socket_register(SocketKind::Stream(Mutex::new(stream)));
    let frame = arena.new_frame_with_capacity(Some(kh_serve_conn.env), 3);
    arena.bind(frame, kh_serve_conn.params[0], Value::Int(h));
    arena.bind(frame, kh_serve_conn.params[1], routes_val.clone());
    arena.bind(frame, kh_serve_conn.params[2], registry_val.clone());
    let _ = walk(k, arena, kh_serve_conn.body, frame);
    // The recipe closes the handle (socket_close); drop it here too so a recipe
    // that returned early never leaks a handle per connection.
    socket_drop(h);
}

fn cli_serve(args: &[String]) -> i32 {
    // --port <p> --routes <file.fk> [--upstream <http-base-url>] [--host <addr>]
    let mut port: u16 = 8001;
    let mut routes_path: Option<String> = None;
    let mut route_data_path: Option<String> = None;
    // --upstream <base-url> turns the listener into the front-door ROUTER:
    // a path with a native Form handler is served entirely in the kernel
    // (no Python in the path); a path with no native handler fans out to
    // the Python upstream (the running FastAPI app) over HTTP. Absent this
    // flag an unmatched path is a 404 — the original proof-of-shape behavior,
    // unchanged, so existing callers see no difference.
    let mut upstream: Option<String> = None;
    // --workers <n> sizes the pool of kernel workers behind the accept loop.
    // Each worker owns its own Kernel + Arena (the !Sync constraint), so the
    // pool gives REAL concurrency, not one shared mutable kernel serialized.
    // Default: the host's available parallelism (capped sane), so the box's
    // cores are used out of the box; 0 or unset falls back to the default.
    let mut workers: Option<usize> = None;
    // --stdlib <dir> points at the form-stdlib directory whose source-compiler a
    // source-authored manifest is lowered through (PATH A — source-compile at load).
    // It is used ONLY when the manifest opens a `section [...]` block; a raw
    // S-expression manifest never touches it. Default: "form-stdlib" relative to
    // the cwd, the same relative path validate.sh uses.
    let mut stdlib_dir: String = "form-stdlib".to_string();
    // --host <addr> is the interface the listener binds. Default 127.0.0.1 keeps
    // the loopback-only behavior every existing caller relies on (a local proof
    // harness curls the listener on the same loopback). A FRONT-DOOR deployment
    // — the kernel-router image behind Docker/Traefik — must bind a routable
    // interface (0.0.0.0), because Docker's host port-forward and Traefik reach
    // a container over its bridge IP, NOT its loopback; a loopback-only listener
    // is unreachable across the container boundary. The container entrypoint sets
    // --host 0.0.0.0; isolation comes from Docker's `-p 127.0.0.1:<port>` host
    // binding, not from the in-container bind address.
    let mut host: String = "127.0.0.1".to_string();
    // --form routes EVERY request through the Form HTTP stack (kh-serve in
    // http-server.fk) instead of the Rust parse/route/render path: the manifest
    // defines `routes` + `registry` + handlers and preludes kernel-http.fk /
    // http-*.fk. The kernel only opens the socket and walks the recipe — the
    // 11.5K-line Rust HTTP and its fear-caps are out of this path entirely.
    let mut form_mode = false;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--port" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --port requires an argument");
                    return 2;
                }
                port = match args[i + 1].parse() {
                    Ok(p) => p,
                    Err(_) => {
                        eprintln!("serve: --port must be a number");
                        return 2;
                    }
                };
                i += 2;
            }
            "--form" => {
                form_mode = true;
                i += 1;
            }
            "--routes" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --routes requires an argument");
                    return 2;
                }
                routes_path = Some(args[i + 1].clone());
                i += 2;
            }
            "--route-data" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --route-data requires a file argument");
                    return 2;
                }
                route_data_path = Some(args[i + 1].clone());
                i += 2;
            }
            "--upstream" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --upstream requires a base-url argument");
                    return 2;
                }
                upstream = Some(args[i + 1].trim_end_matches('/').to_string());
                i += 2;
            }
            "--workers" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --workers requires a number");
                    return 2;
                }
                workers = match args[i + 1].parse() {
                    Ok(w) => Some(w),
                    Err(_) => {
                        eprintln!("serve: --workers must be a number");
                        return 2;
                    }
                };
                i += 2;
            }
            "--host" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --host requires an address argument");
                    return 2;
                }
                host = args[i + 1].clone();
                i += 2;
            }
            "--stdlib" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --stdlib requires a directory argument");
                    return 2;
                }
                stdlib_dir = args[i + 1].clone();
                i += 2;
            }
            "--config" => {
                if i + 1 >= args.len() {
                    eprintln!("serve: --config requires a path argument");
                    return 2;
                }
                set_rust_kernel_config_path(args[i + 1].clone());
                i += 2;
            }
            other => {
                eprintln!("serve: unknown argument: {}", other);
                return 2;
            }
        }
    }
    let routes_path = match routes_path {
        Some(p) => p,
        None => {
            eprintln!("serve: --routes <file.fk> is required");
            return 2;
        }
    };
    let raw_src = match fs::read_to_string(&routes_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("serve: read {}: {}", routes_path, e);
            return 1;
        }
    };
    let routes_source = Arc::new(raw_src);
    let mut serve_context_args = vec!["serve".to_string()];
    serve_context_args.extend(args.iter().cloned());
    set_crash_trace_context_with_details(
        "serve",
        &serve_context_args,
        Some(routes_source.as_str()),
        Some(&routes_path),
        Some("serve startup"),
    );
    let route_data = match load_route_data_registry(&routes_path, route_data_path.as_deref()) {
        Ok(data) => data,
        Err(e) => {
            eprintln!("{}", e);
            return 1;
        }
    };

    // PATH A — source-compile at load. If the manifest is source-authored (opens a
    // `section [...]` block), lower it ONCE here in the main thread through the
    // body's own form-stdlib source-compiler into one Form Recipe object. Worker
    // kernels clone/import from that object graph directly; raw S-expression
    // manifests keep the existing source reader path.
    let program = if manifest_has_source_sections(routes_source.as_str()) {
        match source_compile_manifest_recipe_object(&routes_path, &stdlib_dir) {
            Ok(compiled) => {
                eprintln!(
                    "form-kernel-rust serve: source manifest {} compiled via {} to Form recipe object",
                    routes_path, stdlib_dir
                );
                RouteProgram::RecipeObject(Arc::new(compiled))
            }
            Err(e) => {
                eprintln!("serve: {}", e);
                return 1;
            }
        }
    } else {
        RouteProgram::Source(Arc::clone(&routes_source))
    };

    // Validate the manifest ONCE up front (in the main thread) so a broken
    // routes.fk fails fast with a clear message before any worker spins up.
    // Each worker re-loads the same program into its OWN kernel+arena below.
    if let Err(e) = build_worker_kernel_with_route_data(&program, &routes_path, &route_data) {
        eprintln!("serve: {}", e);
        return 1;
    }

    // Size the pool. Default to the host's available parallelism so the box's
    // cores are used; cap at 64 so a pathological --workers can't exhaust the
    // thread table; floor at 1 so the pool always has at least one worker.
    let default_workers = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4);
    let n_workers = workers.unwrap_or(default_workers).clamp(1, 64);

    let listener = match TcpListener::bind((host.as_str(), port)) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("serve: bind {}:{}: {}", host, port, e);
            return 1;
        }
    };

    // The shared work queue: the accept loop sends each accepted stream; the
    // receiver is shared across workers behind a Mutex (the classic std
    // threadpool — mpsc + Arc<Mutex<Receiver>>). The lock guards only the
    // dequeue; request handling runs lock-free on each worker's own kernel,
    // so N workers serve N requests truly in parallel.
    let (tx, rx) = mpsc::channel::<TcpStream>();
    let rx = Arc::new(Mutex::new(rx));
    let program = Arc::new(program);
    let route_data = Arc::new(route_data);
    let routes_path_arc = Arc::new(routes_path);
    let routes_source_arc = Arc::clone(&routes_source);
    let upstream_arc = Arc::new(upstream);
    let router_metrics = Arc::new(Mutex::new(RouterMetrics::default()));

    // Spawn the pool. Each worker builds its OWN Kernel + Arena from the route
    // program (source for raw Form, Recipe object graph for source-authored manifests),
    // then drains the queue.
    // Workers get an EXPLICIT generous stack: the kernel's value-walk is a
    // recursive tree-walker, so a deeply self-recursive native handler needs
    // real stack depth. A spawned thread's default stack (~2 MiB on many
    // platforms) is smaller than the main thread's (~8 MiB), and a Rust stack
    // overflow ABORTS THE PROCESS (it is not a catchable panic) — so an
    // under-sized worker stack would let one pathological request take the
    // whole server down. WORKER_STACK_SIZE exceeds the typical main-thread
    // stack so a worker handles at least the recursion depth the single-thread
    // path did. (Unbounded recursion is still the handler's responsibility; the
    // generous stack matches the prior behavior rather than promising infinity.)
    let mut handles = Vec::with_capacity(n_workers);
    for id in 0..n_workers {
        let program = Arc::clone(&program);
        let route_data = Arc::clone(&route_data);
        let routes_path = Arc::clone(&routes_path_arc);
        let routes_source = Arc::clone(&routes_source_arc);
        let upstream = Arc::clone(&upstream_arc);
        let rx = Arc::clone(&rx);
        let router_metrics = Arc::clone(&router_metrics);
        let builder = thread::Builder::new()
            .name(format!("kernel-worker-{}", id))
            .stack_size(WORKER_STACK_SIZE);
        match builder.spawn(move || {
            worker_loop(
                id,
                program,
                routes_path,
                routes_source,
                route_data,
                upstream,
                rx,
                router_metrics,
                form_mode,
            );
        }) {
            Ok(h) => handles.push(h),
            Err(e) => {
                eprintln!("serve: failed to spawn worker {}: {}", id, e);
                // Workers already spawned keep serving; a partial pool is
                // better than none. If NONE spawned, the accept loop's send
                // will fail and we stop cleanly below.
            }
        }
    }
    if handles.is_empty() {
        eprintln!("serve: no workers could be spawned");
        return 1;
    }

    // Re-resolve the route list once (in the main thread, throwaway kernel)
    // purely to print the startup banner — the workers hold the live copies.
    if let Ok((_, _, route_specs, _)) =
        build_worker_kernel_with_route_data(&program, &routes_path_arc, &route_data)
    {
        eprintln!(
            "form-kernel-rust serve: listening on {}:{} ({} worker{}, {} native route{})",
            host,
            port,
            n_workers,
            if n_workers == 1 { "" } else { "s" },
            route_specs.len(),
            if route_specs.len() == 1 { "" } else { "s" }
        );
        for r in &route_specs {
            eprintln!(
                "  {} {} -> native (Form handler {})",
                r.method, r.pattern, r.name
            );
        }
    }
    match upstream_arc.as_ref() {
        Some(u) => eprintln!("  *  -> fan-out to Python upstream {}", u),
        None => eprintln!("  *  -> 404 (no --upstream; fan-out arm inactive)"),
    }

    // The accept loop is now thin: it only hands each accepted stream to the
    // pool. The kernel work happens on the workers, concurrently.
    for incoming in listener.incoming() {
        let stream = match incoming {
            Ok(s) => s,
            Err(_) => continue,
        };
        if tx.send(stream).is_err() {
            // All workers gone — nothing can serve; stop accepting.
            break;
        }
    }

    // Listener ended: drop the sender so workers see the channel close and
    // exit, then join them so no thread is leaked.
    drop(tx);
    for h in handles {
        let _ = h.join();
    }
    0
}

// The largest shape, in bytes, the router holds in memory for one request body
// or one upstream response. Being aware of a shape is a different act than
// preventing it: this is not a fear-wall and not a verdict on the sender. It
// names one resource reality — a body is read fully into memory, so a truly
// unbounded read would exhaust the worker — held as a COMMON RECIPE we both
// accept in THIS moment. The shape is observed first; a "no" above the threshold
// is a sensed invitation, returned observably ("this is larger than we can hold
// right now — change the router configuration recipe, or let it stream"), never
// a silent prevention.
//
// The defaults are generous, so any real request or API response circulates
// freely. Request and response share the awareness-shape on purpose: a request
// body is not "untrusted input" to be policed here — in this space the sender is
// us, and circulation is welcome whenever its shape can be observed. (The
// asymmetric 1 MiB-request / 64 MiB-response split this replaces was the
// inherited fear posture: control by wall, before observing.) True streaming
// (unbounded, no buffering) is a named-later breath; until then the ceiling is
// simply what one worker can hold — named honestly, then lifted into
// Form-visible router configuration when runtime tuning is needed.
const DEFAULT_REQUEST_SHAPE_BYTES: usize = 64 * 1024 * 1024;
const DEFAULT_RESPONSE_SHAPE_BYTES: usize = 64 * 1024 * 1024;

// The shape we can hold for one incoming request body.
fn request_shape_limit() -> usize {
    DEFAULT_REQUEST_SHAPE_BYTES
}

// The shape we can hold for one upstream (fan-out) response.
fn response_shape_limit() -> usize {
    DEFAULT_RESPONSE_SHAPE_BYTES
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct NativeHandlerResponse {
    status_code: i64,
    content_type: String,
    headers: Vec<(String, String)>,
    body: String,
}

fn response_body_string(value: &Value) -> String {
    match value {
        Value::Str(s) => s.to_string(),
        _ => value.display(),
    }
}

fn kernel_http_header(value: &Value) -> Option<(String, String)> {
    match value {
        Value::List(items) if items.len() == 3 => {
            if let (Value::Int(tag), Value::Str(name), Value::Str(header_value)) =
                (&items[0], &items[1], &items[2])
            {
                if *tag == KH_TAG_HEADER && !name.trim().is_empty() {
                    return Some((name.to_string(), header_value.to_string()));
                }
            }
            None
        }
        _ => None,
    }
}

fn kernel_http_headers(value: &Value) -> Option<(String, Vec<(String, String)>)> {
    let mut content_type = String::new();
    let mut relayed = Vec::new();
    match value {
        Value::List(items) => {
            for item in items.iter() {
                let (name, header_value) = kernel_http_header(item)?;
                if name.trim().eq_ignore_ascii_case("content-type") {
                    content_type = header_value;
                } else if relay_response_header(&name) {
                    relayed.push((name, header_value));
                }
            }
            Some((content_type, relayed))
        }
        _ => None,
    }
}

fn handler_kernel_http_response(result: &Value) -> Option<NativeHandlerResponse> {
    if let Value::List(items) = result {
        if items.len() == 4 {
            if let (Value::Int(tag), Value::Int(status_code), headers, body) =
                (&items[0], &items[1], &items[2], &items[3])
            {
                if *tag == KH_TAG_RESPONSE && (100..=599).contains(status_code) {
                    let (content_type, headers) = kernel_http_headers(headers)?;
                    return Some(NativeHandlerResponse {
                        status_code: *status_code,
                        content_type,
                        headers,
                        body: response_body_string(body),
                    });
                }
            }
        }
    }
    None
}

// A native handler's observable, status-bearing compatibility shape. Older
// routes that want a non-200 return (respond <code> <body>) — a 3-element List
// [Str("__http_status__"), Int(code), Str(body)] (the `respond` helper in the
// routes manifest builds it). New typed routes should return KernelHTTPResponse:
// kh-response(status, headers, body).
fn handler_status_response(result: &Value) -> Option<NativeHandlerResponse> {
    if let Value::List(items) = result {
        if items.len() == 3 {
            if let (Value::Str(tag), Value::Int(code), Value::Str(body)) =
                (&items[0], &items[1], &items[2])
            {
                if **tag == *"__http_status__" && (100..=599).contains(code) {
                    return Some(NativeHandlerResponse {
                        status_code: *code,
                        content_type: String::new(),
                        headers: Vec::new(),
                        body: body.to_string(),
                    });
                }
            }
        }
    }
    None
}

fn handler_native_response(result: &Value) -> Option<NativeHandlerResponse> {
    handler_kernel_http_response(result).or_else(|| handler_status_response(result))
}

// The reason phrase for a status a native handler can emit. Only the codes we
// actually use are named; anything else gets a neutral phrase (the numeric code
// is what clients key on).
fn http_reason(code: i64) -> &'static str {
    match code {
        200 => "OK",
        201 => "Created",
        204 => "No Content",
        400 => "Bad Request",
        401 => "Unauthorized",
        403 => "Forbidden",
        404 => "Not Found",
        409 => "Conflict",
        422 => "Unprocessable Entity",
        429 => "Too Many Requests",
        418 => "I'm a Teapot",
        500 => "Internal Server Error",
        502 => "Bad Gateway",
        503 => "Service Unavailable",
        504 => "Gateway Timeout",
        _ => "Status",
    }
}

// The outcome of reading a request: either the parsed (head, body), or a sensed
// signal that the request shape is larger than we can hold right now — carrying
// the observed size and the threshold so the caller answers observably (naming
// the shape, the recipe, and that it is changeable) — or a read error / empty
// peer (the caller drops the connection silently).
enum RequestRead {
    Ok(String, Vec<u8>),
    LargerThanWeHold { observed: usize, limit: usize },
    Error,
}

// Read a full HTTP request: the header block (up to the `\r\n\r\n` terminator)
// followed by exactly `Content-Length` body bytes if that header is present.
// The first read may already contain some or all of the body (it arrived in the
// same TCP segment), so bytes captured past the terminator are counted toward
// the body and only the remainder is read from the socket. Returns the raw head
// string (request line + headers, terminator excluded) and the body bytes.
//
// This replaces the old single 8 KiB read: it honors Content-Length across as
// many `read` calls as the body needs, so a body larger than one buffer is
// fully captured (the correctness property the single-buffer read failed).
//
// KEEP-ALIVE: `carry` holds bytes that arrived on this persistent connection
// but belong to the NEXT request — the classic pipelining hazard. A single
// `read` can pull the tail of request N AND the head (or all) of request N+1;
// those extra bytes must NOT be dropped between requests. So this fn (1) seeds
// its read buffer from `carry` before touching the socket, and (2) stashes any
// bytes captured past this request's end (header terminator + Content-Length)
// back into `carry` for the next call. The next iteration of the keep-alive
// loop therefore starts exactly at the next request's first byte. A clean EOF
// with no bytes buffered (idle connection closed or read-timeout fired) returns
// `Error`, which the keep-alive loop reads as "connection done — stop looping."
fn read_request(stream: &mut TcpStream, carry: &mut Vec<u8>) -> RequestRead {
    // Seed from any leftover bytes carried in from the previous request on this
    // same connection (drained out of `carry`), then read more as needed.
    let mut raw: Vec<u8> = std::mem::take(carry);
    let mut buf = [0u8; 8192];
    // The shape we can hold for this request right now — read once (the live,
    // changeable recipe), then sensed against the observed bytes below.
    let request_limit = request_shape_limit();
    // The whole request must arrive within this wall-clock deadline. The 5s idle
    // read-timeout reaps a single stalled read, but a slowloris that trickles one
    // byte every few seconds resets that idle timer forever and never completes;
    // this total deadline, checked before every read of THIS request, reaps such a
    // connection so it cannot pin a worker. (A pipelined request whose bytes were
    // already carried in skips the read loops entirely and is unaffected.)
    let read_deadline = Instant::now() + max_request_read_timeout();
    // Phase 1: read until the header terminator is seen (or EOF / cap). The
    // carried bytes may ALREADY contain the full header block, so check before
    // the first socket read — otherwise a pipelined request would block on a
    // read that never comes.
    let header_end: Option<usize> = if let Some(t) = find_header_end(&raw) {
        Some(t)
    } else {
        loop {
            if Instant::now() >= read_deadline {
                return RequestRead::Error; // slow client never finished the head
            }
            match stream.read(&mut buf) {
                Ok(0) => break find_header_end(&raw), // peer closed; use what we have
                Ok(n) => {
                    raw.extend_from_slice(&buf[..n]);
                    if let Some(t) = find_header_end(&raw) {
                        break Some(t);
                    }
                    // The header block, too, is a shape we observe as it grows;
                    // past what one worker can hold right now we answer observably.
                    if raw.len() > request_limit {
                        return RequestRead::LargerThanWeHold {
                            observed: raw.len(),
                            limit: request_limit,
                        };
                    }
                }
                // A read error here also covers the idle read-timeout firing on
                // a kept-alive connection (WouldBlock/TimedOut) — the loop ends.
                Err(_) => return RequestRead::Error,
            }
        }
    };
    if raw.is_empty() {
        return RequestRead::Error; // nothing arrived at all (clean EOF / idle close)
    }
    // `header_end` is the index just past "\r\n\r\n" when found. The head text
    // (terminator excluded) is everything before it; if no terminator was seen
    // the whole buffer is the head and there is no body.
    let (head_end_excl_term, body_start) = match header_end {
        Some(t) => (t - 4, t),
        None => (raw.len(), raw.len()),
    };
    let head = String::from_utf8_lossy(&raw[..head_end_excl_term]).to_string();

    // Phase 2: if Content-Length says there's a body, read exactly that many
    // bytes, counting whatever already arrived past the header terminator. With
    // NO Content-Length there is no body — everything past the terminator
    // belongs to the NEXT request and is carried forward (not mis-read as this
    // request's body, which would corrupt a keep-alive connection).
    let total = match parse_content_length(&head) {
        Some(t) => {
            // Content-Length declares the shape before it arrives — sense it now,
            // so a body larger than we can hold is answered without draining it.
            if t > request_limit {
                return RequestRead::LargerThanWeHold {
                    observed: t,
                    limit: request_limit,
                };
            }
            t
        }
        None => 0,
    };
    let mut body: Vec<u8> = raw[body_start..].to_vec();
    while body.len() < total {
        if Instant::now() >= read_deadline {
            return RequestRead::Error; // slow client never finished the body
        }
        match stream.read(&mut buf) {
            Ok(0) => break, // peer closed early; return the partial body honestly
            Ok(n) => body.extend_from_slice(&buf[..n]),
            Err(_) => break,
        }
    }
    // Any bytes captured past this request's body belong to the NEXT request on
    // the connection — carry them forward so the next read_request starts there.
    if body.len() > total {
        carry.extend_from_slice(&body[total..]);
        body.truncate(total);
    }
    RequestRead::Ok(head, body)
}

// Find the index just past the first "\r\n\r\n" header terminator, if present.
fn find_header_end(raw: &[u8]) -> Option<usize> {
    raw.windows(4).position(|w| w == b"\r\n\r\n").map(|i| i + 4)
}

// Parse a raw header block (the lines AFTER the request/status line, terminator
// excluded) into an ordered list of (name, value) pairs — names kept as sent so
// they relay verbatim, values trimmed. The first line (request line on the way
// up, status line on the way back) is the caller's; this skips it. This is the
// ONE header-capture shape both hops use: the request headers forwarded to the
// upstream and the upstream's response headers relayed to the client both come
// from here, so a header is never silently dropped because two code paths parsed
// the block differently.
fn parse_headers(head: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    for line in head.lines().skip(1) {
        if line.is_empty() {
            continue;
        }
        if let Some((name, value)) = line.split_once(':') {
            let (name, value) = (name.trim(), value.trim());
            // Drop any header carrying a raw CR, LF, or NUL in its name or value.
            // `head.lines()` splits on `\n` and strips a trailing `\r`, but a LONE
            // CR (a `\r` not followed by `\n`) survives INSIDE a value — a header /
            // request-injection (smuggling) and response-splitting vector when this
            // header is relayed verbatim to the next hop (the upstream on the
            // request hop, the client on the response hop). A legitimate header
            // never contains these control bytes; dropping such a header forwards
            // no control character to either hop, regardless of how lenient the
            // far end's parser is.
            if name
                .bytes()
                .chain(value.bytes())
                .any(|b| b == b'\r' || b == b'\n' || b == 0)
            {
                continue;
            }
            out.push((name.to_string(), value.to_string()));
        }
    }
    out
}

// HOP-BY-HOP headers (RFC 7230 §6.1) — meaningful only for a SINGLE transport
// hop, NEVER forwarded by a proxy to the next hop. The router is a hop on both
// sides: it owns its client-hop framing (Connection/Content-Length) and its
// upstream-hop framing independently, so these must be stripped in BOTH
// directions rather than blindly relayed. `Connection`, `Keep-Alive`,
// `Transfer-Encoding`, `Upgrade`, the `Proxy-*` set, plus the rarely-seen TE /
// Trailer. `Proxy-Connection` is the non-standard-but-widespread connection-
// management header — a proxy must never pass it on, exactly because the router
// now writes its OWN `Connection` for upstream reuse and a leaked
// `Proxy-Connection` would carry the client's stale connection intent past the
// hop. Content-Length is handled separately (the router sets its own from the
// body it holds), so it is treated as framing the router owns, not relayed.
fn is_hop_by_hop(name: &str) -> bool {
    let n = name.trim();
    n.eq_ignore_ascii_case("connection")
        || n.eq_ignore_ascii_case("keep-alive")
        || n.eq_ignore_ascii_case("transfer-encoding")
        || n.eq_ignore_ascii_case("upgrade")
        || n.eq_ignore_ascii_case("proxy-authenticate")
        || n.eq_ignore_ascii_case("proxy-authorization")
        || n.eq_ignore_ascii_case("proxy-connection")
        || n.eq_ignore_ascii_case("te")
        || n.eq_ignore_ascii_case("trailer")
}

// Whether a request header should be forwarded UP to the upstream. Strips the
// hop-by-hop set (the router owns its upstream-hop framing) AND the framing the
// router re-derives from the body it captured: `Host` is rewritten to the
// upstream host, and `Content-Length` is set from the captured body's true
// length (a forwarded client Content-Length could disagree with the bytes the
// router actually holds — double-framing). Everything end-to-end —
// Authorization, Cookie, Accept*, User-Agent, X-*, Content-Type, … — passes.
fn forward_request_header(name: &str) -> bool {
    let n = name.trim();
    !(is_hop_by_hop(n)
        || router_owned_http_header(n)
        || n.eq_ignore_ascii_case("host")
        || n.eq_ignore_ascii_case("content-length"))
}

// Whether an upstream RESPONSE header should be relayed DOWN to the client.
// Strips the hop-by-hop set AND the framing the router owns on its client hop:
// `Content-Length` (the router sets its own from the body it relays) and
// `Content-Type` (relayed via the dedicated content_type slot in the emit shape,
// so it is not duplicated here). Everything else end-to-end — Set-Cookie,
// Cache-Control, Location, ETag, X-*, … — passes through to the client.
fn relay_response_header(name: &str) -> bool {
    let n = name.trim();
    !(is_hop_by_hop(n)
        || router_owned_http_header(n)
        || n.eq_ignore_ascii_case("content-length")
        || n.eq_ignore_ascii_case("content-type"))
}

fn router_owned_http_header(name: &str) -> bool {
    let n = name.trim();
    n.eq_ignore_ascii_case("x-form-router")
        || n.eq_ignore_ascii_case(FANOUT_NATIVE_INVITATION_HEADER)
        || n.eq_ignore_ascii_case(FANOUT_NATIVE_INVITATION_STATE_HEADER)
        || n.eq_ignore_ascii_case(FANOUT_NATIVE_INVITATION_PROTOCOL_HEADER)
        || n.eq_ignore_ascii_case(FANOUT_NATIVE_INVITATION_SELECTED_PATH_HEADER)
        || n.eq_ignore_ascii_case(FANOUT_NATIVE_INVITATION_DECLINE_SIGNAL_HEADER)
        || n.eq_ignore_ascii_case(FANOUT_NATIVE_INVITATION_DECLINE_HEADER)
}

fn fanout_native_invitation_headers() -> [(&'static str, &'static str); 6] {
    [
        (
            FANOUT_NATIVE_INVITATION_HEADER,
            FANOUT_NATIVE_INVITATION_VALUE,
        ),
        (
            FANOUT_NATIVE_INVITATION_STATE_HEADER,
            FANOUT_NATIVE_INVITATION_STATE,
        ),
        (
            FANOUT_NATIVE_INVITATION_PROTOCOL_HEADER,
            FANOUT_NATIVE_INVITATION_PROTOCOL,
        ),
        (
            FANOUT_NATIVE_INVITATION_SELECTED_PATH_HEADER,
            "fanout-python",
        ),
        (
            FANOUT_NATIVE_INVITATION_DECLINE_SIGNAL_HEADER,
            FANOUT_NATIVE_INVITATION_DECLINE_SIGNAL,
        ),
        (
            FANOUT_NATIVE_INVITATION_DECLINE_HEADER,
            NATIVE_PYTHON_FALLBACK_HEADER,
        ),
    ]
}

fn push_fanout_native_invitation_headers(out: &mut String, router: &str) {
    if router != "fanout-python" {
        return;
    }
    for (name, value) in fanout_native_invitation_headers() {
        out.push_str(name);
        out.push_str(": ");
        out.push_str(value);
        out.push_str("\r\n");
    }
}

// Pull the Content-Length value out of a raw header block (case-insensitive
// header name). Returns None when absent or unparseable.
fn parse_content_length(head: &str) -> Option<usize> {
    for line in head.lines() {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("content-length") {
                return value.trim().parse::<usize>().ok();
            }
        }
    }
    None
}

// Pull the Content-Type value (lowercased, parameters stripped) out of a raw
// header block. "application/json; charset=utf-8" -> "application/json".
fn parse_content_type(head: &str) -> String {
    for line in head.lines() {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("content-type") {
                let v = value.trim();
                let main = v.split(';').next().unwrap_or(v);
                return main.trim().to_ascii_lowercase();
            }
        }
    }
    String::new()
}

// Decide whether the CLIENT wants the connection kept alive, per RFC 7230. The
// request line's HTTP version sets the default; an explicit `Connection` header
// overrides it:
//   HTTP/1.1 (and higher) -> keep-alive by default; close only if the client
//     sent `Connection: close`.
//   HTTP/1.0 -> close by default; keep-alive only if the client sent
//     `Connection: keep-alive`.
// The server may still force-close on top of this (e.g. an error whose framing
// is uncertain) — that is the caller's decision; this only reads client intent.
fn head_keep_alive(head: &str) -> bool {
    let request_line = head.lines().next().unwrap_or("");
    let is_http11_or_higher = request_line
        .rsplit(' ')
        .next()
        .map(|v| v == "HTTP/1.1" || (v.starts_with("HTTP/") && v > "HTTP/1.0"))
        .unwrap_or(false);
    // The Connection header value (lowercased) if present.
    let mut connection: Option<String> = None;
    for line in head.lines().skip(1) {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("connection") {
                connection = Some(value.trim().to_ascii_lowercase());
                break;
            }
        }
    }
    match connection.as_deref() {
        Some(v) if v.split(',').any(|t| t.trim() == "close") => false,
        Some(v) if v.split(',').any(|t| t.trim() == "keep-alive") => true,
        // No explicit token -> the HTTP version's default.
        _ => is_http11_or_higher,
    }
}

// Parse a request body into the SAME (key, value) alist shape the query string
// already uses, so a handler reads body fields exactly like query fields
// (core-abstraction-first: ONE request-data shape regardless of how the data
// arrived). The marshalling depends on Content-Type:
//   - application/x-www-form-urlencoded -> each `k=v&...` pair url-decoded into
//     the alist (reuses the query-pair parsing), so a form-POST handler sees its
//     fields uniformly with query params.
//   - application/json -> the raw JSON string is captured under the reserved key
//     `__body__` so a handler CAN read it via (assoc "__body__" q). A full
//     JSON->Form-value parse is a deeper, named-later breath; raw-capture is the
//     honest first step that already lets a handler process the payload.
//   - anything else (with a non-empty body) -> the raw bytes captured under
//     `__body__`. The handler always gets a well-formed alist.
fn parse_request_body(content_type: &str, body: &[u8]) -> Vec<(String, String)> {
    if body.is_empty() {
        return Vec::new();
    }
    if content_type == "application/x-www-form-urlencoded" {
        let s = String::from_utf8_lossy(body);
        let mut pairs = Vec::new();
        for pair in s.split('&') {
            if pair.is_empty() {
                continue;
            }
            let (k, v) = match pair.find('=') {
                Some(i) => (pair[..i].to_string(), pair[i + 1..].to_string()),
                None => (pair.to_string(), String::new()),
            };
            pairs.push((url_decode(&k), url_decode(&v)));
        }
        pairs
    } else {
        // application/json and everything else: capture the raw body so the
        // handler can process it. JSON is left as the raw string by design
        // (raw-capture, not yet a structural parse).
        vec![(
            "__body__".to_string(),
            String::from_utf8_lossy(body).to_string(),
        )]
    }
}

// Parse the request line "GET /path?k=v HTTP/1.0" into
// (method, target, path, query).
// Query string is decoded as a flat list of (key, value) pairs — sufficient
// for the proof-of-shape; no percent-decoding beyond '+' → ' '.
fn parse_request_line(req: &str) -> (String, String, String, Vec<(String, String)>) {
    let line = req.lines().next().unwrap_or("");
    let mut parts = line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let target = parts.next().unwrap_or("/").to_string();
    let (path, qs) = match target.find('?') {
        Some(i) => (target[..i].to_string(), target[i + 1..].to_string()),
        None => (target.clone(), String::new()),
    };
    let mut query = Vec::new();
    if !qs.is_empty() {
        for pair in qs.split('&') {
            let (k, v) = match pair.find('=') {
                Some(i) => (pair[..i].to_string(), pair[i + 1..].to_string()),
                None => (pair.to_string(), String::new()),
            };
            query.push((url_decode(&k), url_decode(&v)));
        }
    }
    (method, target, path, query)
}

fn router_count_value(count: u64) -> Value {
    Value::Int(count.min(i64::MAX as u64) as i64)
}

fn router_dict_value(entries: Vec<(&str, Value)>) -> Value {
    let mut values = vec![Value::Str("__dict__".to_string().into())];
    for (key, value) in entries {
        values.push(Value::Str(key.to_string().into()));
        values.push(value);
    }
    Value::List(values.into())
}

fn router_fanout_path_count_value(row: &RouterFanoutPathCount) -> Value {
    router_dict_value(vec![
        ("path", Value::Str(row.path.clone().into())),
        ("count", router_count_value(row.count)),
        ("source", Value::Str(row.source.clone().into())),
    ])
}

fn router_bml_candidate_value(candidate: &RouterBmlCandidate) -> Value {
    router_dict_value(vec![
        ("path", Value::Str(candidate.path.clone().into())),
        ("count", router_count_value(candidate.count)),
        ("source", Value::Str(candidate.source.clone().into())),
    ])
}

fn router_http_header_value(name: &str, value: &str) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_HEADER),
            Value::Str(name.to_string().into()),
            Value::Str(value.to_string().into()),
        ]
        .into(),
    )
}

fn router_http_field_value(name: &str, value: &str) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_FIELD),
            Value::Str(name.to_string().into()),
            Value::Str(value.to_string().into()),
        ]
        .into(),
    )
}

fn router_http_route_value(candidate: &RouteCandidateValue) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_ROUTE),
            Value::Str(candidate.route_name.clone().into()),
            Value::Str(candidate.route_method.clone().into()),
            Value::Str(candidate.route_pattern.clone().into()),
            Value::Int(candidate.route_priority),
            Value::Str(candidate.route_handler_name.clone().into()),
            Value::Str(candidate.route_required_header.clone().into()),
            Value::Int(candidate.route_pressure_budget),
        ]
        .into(),
    )
}

fn router_http_request_parts_value(
    method: &str,
    path: &str,
    headers: &[(String, String)],
    query: &[(String, String)],
    body: &str,
) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_REQUEST),
            Value::Str(method.to_string().into()),
            Value::Str(path.to_string().into()),
            Value::List(Arc::new(
                headers
                    .iter()
                    .map(|(name, value)| router_http_header_value(name, value))
                    .collect(),
            )),
            Value::List(Arc::new(
                query
                    .iter()
                    .map(|(name, value)| router_http_field_value(name, value))
                    .collect(),
            )),
            Value::Str(body.to_string().into()),
        ]
        .into(),
    )
}

fn router_http_request_value(candidate: &RouteCandidateValue) -> Value {
    router_http_request_parts_value(
        &candidate.request_method,
        &candidate.request_path,
        &candidate.request_headers,
        &candidate.request_query,
        &candidate.request_body,
    )
}

fn router_string_list_value(items: &[&str]) -> Value {
    Value::List(Arc::new(
        items
            .iter()
            .map(|item| Value::Str((*item).to_string().into()))
            .collect(),
    ))
}

fn router_method_bridge_policy_value(bridge: &MethodBridgePolicy) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_METHOD_BRIDGE),
            Value::Str(bridge.route_method.to_string().into()),
            Value::Str(bridge.request_method.to_string().into()),
            Value::Int(bridge.pressure),
        ]
        .into(),
    )
}

fn router_channel_policy_value(policy: &ChannelPolicy) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_CHANNEL_POLICY),
            Value::Str(policy.carrier.to_string().into()),
            Value::Str(policy.protocol.to_string().into()),
            router_string_list_value(policy.allowed_methods),
            Value::List(Arc::new(
                policy
                    .method_bridges
                    .iter()
                    .map(router_method_bridge_policy_value)
                    .collect(),
            )),
            router_string_list_value(policy.no_body_methods),
            router_string_list_value(policy.allow_methods),
            Value::Str(policy.cache_policy.to_string().into()),
            Value::Str(policy.compression_policy.to_string().into()),
            Value::Str(policy.stream_policy.to_string().into()),
            Value::Str(policy.identity_policy.to_string().into()),
            Value::Str(policy.authorization_policy.to_string().into()),
        ]
        .into(),
    )
}

fn router_http_choice_request_value(request: &RouteRequestValue) -> Value {
    router_http_request_parts_value(
        &request.method,
        &request.path,
        &request.headers,
        &request.query,
        &request.body,
    )
}

fn router_pressure_row_value(row: &RoutePressureRow) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_PRESSURE_ROW),
            Value::Str(row.axis.clone().into()),
            row.observed.clone(),
            row.expected.clone(),
            Value::Int(row.pressure),
        ]
        .into(),
    )
}

fn route_pressure_bucket(pressure: i64) -> i64 {
    if pressure == 0 {
        0
    } else if pressure <= 25 {
        1
    } else if pressure <= 120 {
        2
    } else if pressure <= 400 {
        3
    } else if pressure <= 500 {
        4
    } else {
        5
    }
}

fn route_score_bucket(score: i64) -> i64 {
    if score < 0 {
        0
    } else if score < 500 {
        1
    } else if score < 900 {
        2
    } else if score < 1000 {
        3
    } else if score < 1100 {
        4
    } else {
        5
    }
}

fn router_pressure_code_value(row: &RoutePressureRow) -> Value {
    Value::List(
        vec![
            Value::Str(row.axis.clone().into()),
            Value::Int(route_pressure_bucket(row.pressure)),
        ]
        .into(),
    )
}

fn router_route_candidate_value(candidate: &RouteCandidateValue) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_ROUTE_CANDIDATE),
            router_http_route_value(candidate),
            router_http_request_value(candidate),
            Value::List(Arc::new(
                candidate
                    .pressure_matrix
                    .iter()
                    .map(router_pressure_row_value)
                    .collect(),
            )),
            Value::Int(candidate.pressure),
            Value::Int(candidate.score),
        ]
        .into(),
    )
}

fn router_route_decision_signature_value(decision: &RouteDecisionValue) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_ROUTE_DECISION_SIGNATURE),
            Value::Str(decision.candidate.route_name.clone().into()),
            Value::Str(decision.candidate.route_handler_name.clone().into()),
            Value::List(Arc::new(
                decision
                    .candidate
                    .pressure_matrix
                    .iter()
                    .map(router_pressure_code_value)
                    .collect(),
            )),
            Value::Int(route_pressure_bucket(decision.candidate.pressure)),
            Value::Int(route_score_bucket(decision.candidate.score)),
            Value::Bool(decision.eligible),
            Value::Bool(decision.selected),
        ]
        .into(),
    )
}

fn router_route_choice_decision_signatures_value(choice: &RouteChoice<'_>) -> Value {
    Value::List(Arc::new(
        choice
            .decisions
            .iter()
            .map(router_route_decision_signature_value)
            .collect(),
    ))
}

fn router_route_choice_signature_value(choice: &RouteChoice<'_>) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_ROUTE_CHOICE_SIGNATURE),
            Value::Str(choice.request.method.clone().into()),
            Value::Str(choice.request.path.clone().into()),
            router_route_choice_decision_signatures_value(choice),
        ]
        .into(),
    )
}

fn router_route_candidate_matrix_value(candidate: &RouteCandidateValue) -> Value {
    Value::List(Arc::new(
        candidate
            .pressure_matrix
            .iter()
            .map(router_pressure_row_value)
            .collect(),
    ))
}

fn router_route_decision_value(decision: &RouteDecisionValue) -> Value {
    Value::List(
        vec![
            Value::Int(KH_TAG_ROUTE_DECISION),
            router_route_candidate_value(&decision.candidate),
            Value::Bool(decision.eligible),
            Value::Bool(decision.selected),
        ]
        .into(),
    )
}

fn router_route_choice_candidates_value(choice: &RouteChoice<'_>) -> Value {
    Value::List(Arc::new(
        choice
            .decisions
            .iter()
            .map(|decision| router_route_candidate_value(&decision.candidate))
            .collect(),
    ))
}

fn router_route_choice_decisions_value(choice: &RouteChoice<'_>) -> Value {
    Value::List(Arc::new(
        choice
            .decisions
            .iter()
            .map(router_route_decision_value)
            .collect(),
    ))
}

fn router_route_choice_value(choice: &RouteChoice<'_>) -> Value {
    let selected = choice
        .selected
        .as_ref()
        .map(|selection| router_route_candidate_value(&selection.candidate))
        .unwrap_or_else(|| Value::List(Arc::new(Vec::new())));
    Value::List(
        vec![
            Value::Int(KH_TAG_ROUTE_CHOICE),
            router_http_choice_request_value(&choice.request),
            router_route_choice_candidates_value(choice),
            router_route_choice_decisions_value(choice),
            selected,
        ]
        .into(),
    )
}

fn router_observation_value(metrics: &RouterMetricsSnapshot) -> Value {
    router_dict_value(vec![
        (
            "fanout_path_counts",
            Value::List(Arc::new(
                metrics
                    .fanout_path_counts
                    .iter()
                    .map(router_fanout_path_count_value)
                    .collect(),
            )),
        ),
        (
            "next_bml_candidate",
            router_bml_candidate_value(&metrics.next_bml_candidate),
        ),
        (
            "choice_attempts",
            Value::Int(metrics.choice_attempts as i64),
        ),
        (
            "choice_successes",
            Value::Int(metrics.choice_successes as i64),
        ),
        (
            "choice_failures",
            Value::Int(metrics.choice_failures as i64),
        ),
    ])
}

// Router-owned request context for native handlers. These pairs are prepended
// to the handler alist, so client query/body fields cannot override reserved
// router facts when a Form/BML handler uses the ordinary assoc helper.
fn router_context_data(
    method: &str,
    target: &str,
    path: &str,
    upstream: &Option<String>,
    metrics: &RouterMetricsSnapshot,
    route_choice: Option<&RouteChoice<'_>>,
) -> Vec<(String, Value)> {
    let mut pairs = vec![
        (
            "__request_method__".to_string(),
            Value::Str(method.to_string().into()),
        ),
        (
            "__request_target__".to_string(),
            Value::Str(target.to_string().into()),
        ),
        (
            "__request_path__".to_string(),
            Value::Str(path.to_string().into()),
        ),
        (
            "__router_channel_policy__".to_string(),
            router_channel_policy_value(&default_http_channel_policy()),
        ),
        (
            "__router_native_route_count__".to_string(),
            Value::Str(metrics.native_route_count.to_string().into()),
        ),
        (
            "__router_observed_path_count__".to_string(),
            Value::Str(metrics.observed_path_count.to_string().into()),
        ),
        (
            "__router_observed_native_route_count__".to_string(),
            Value::Str(metrics.observed_native_route_count.to_string().into()),
        ),
        (
            "__router_observed_fanout_path_count__".to_string(),
            Value::Str(metrics.observed_fanout_path_count.to_string().into()),
        ),
        (
            "__router_total_requests__".to_string(),
            Value::Str(metrics.total_requests.to_string().into()),
        ),
        (
            "__router_native_requests__".to_string(),
            Value::Str(metrics.native_requests.to_string().into()),
        ),
        (
            "__router_fanout_requests__".to_string(),
            Value::Str(metrics.fanout_requests.to_string().into()),
        ),
        (
            "__router_local_control_requests__".to_string(),
            Value::Str(metrics.local_control_requests.to_string().into()),
        ),
        (
            "__router_native_error_requests__".to_string(),
            Value::Str(metrics.native_error_requests.to_string().into()),
        ),
        (
            "__router_choice_attempts__".to_string(),
            Value::Str(metrics.choice_attempts.to_string().into()),
        ),
        (
            "__router_choice_successes__".to_string(),
            Value::Str(metrics.choice_successes.to_string().into()),
        ),
        (
            "__router_choice_failures__".to_string(),
            Value::Str(metrics.choice_failures.to_string().into()),
        ),
        (
            "__router_observation__".to_string(),
            router_observation_value(metrics),
        ),
        (
            "__router_next_bml_candidate_path__".to_string(),
            Value::Str(metrics.next_bml_candidate_path.clone().into()),
        ),
        (
            "__router_next_bml_candidate_requests__".to_string(),
            Value::Str(metrics.next_bml_candidate_requests.to_string().into()),
        ),
        (
            "__router_next_bml_candidate_source__".to_string(),
            Value::Str(metrics.next_bml_candidate_source.clone().into()),
        ),
    ];
    if let Some(choice) = route_choice {
        pairs.push((
            "__router_route_choice__".to_string(),
            router_route_choice_value(choice),
        ));
        pairs.push((
            "__router_route_candidates__".to_string(),
            router_route_choice_candidates_value(choice),
        ));
        pairs.push((
            "__router_route_decisions__".to_string(),
            router_route_choice_decisions_value(choice),
        ));
        pairs.push((
            "__router_route_choice_signature__".to_string(),
            router_route_choice_signature_value(choice),
        ));
        pairs.push((
            "__router_route_decision_signatures__".to_string(),
            router_route_choice_decision_signatures_value(choice),
        ));
        if let Some(selection) = choice.selected.as_ref() {
            let candidate = &selection.candidate;
            pairs.push((
                "__kernel_request__".to_string(),
                router_http_request_value(candidate),
            ));
            pairs.push((
                "__router_route_candidate__".to_string(),
                router_route_candidate_value(candidate),
            ));
            pairs.push((
                "__router_route_candidate_matrix__".to_string(),
                router_route_candidate_matrix_value(candidate),
            ));
        }
    }
    if let Some(upstream_base) = upstream {
        pairs.push((
            "__router_upstream__".to_string(),
            Value::Str(upstream_base.clone().into()),
        ));
        match parse_http_upstream(upstream_base) {
            Ok((host, port, base_path)) => {
                pairs.push((
                    "__router_upstream_host__".to_string(),
                    Value::Str(host.into()),
                ));
                pairs.push((
                    "__router_upstream_port__".to_string(),
                    Value::Str(port.to_string().into()),
                ));
                pairs.push((
                    "__router_upstream_base_path__".to_string(),
                    Value::Str(base_path.into()),
                ));
            }
            Err(e) => {
                pairs.push((
                    "__router_upstream_parse_error__".to_string(),
                    Value::Str(e.into()),
                ));
            }
        }
    }
    pairs
}

#[cfg(test)]
mod router_context_tests {
    use super::*;

    fn value_for<'a>(pairs: &'a [(String, Value)], key: &str) -> &'a Value {
        pairs
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v)
            .unwrap_or(&Value::Null)
    }

    fn str_for(pairs: &[(String, Value)], key: &str) -> String {
        match value_for(pairs, key) {
            Value::Str(s) => s.to_string(),
            Value::Int(i) => i.to_string(),
            v => v.display(),
        }
    }

    fn dict_get<'a>(dict: &'a Value, key: &str) -> &'a Value {
        if let Value::List(xs) = dict {
            let mut i = 1;
            while i + 1 < xs.len() {
                if matches!(&xs[i], Value::Str(k) if k.as_ref() == key) {
                    return &xs[i + 1];
                }
                i += 2;
            }
        }
        &Value::Null
    }

    fn dict_str(dict: &Value, key: &str) -> String {
        match dict_get(dict, key) {
            Value::Str(s) => s.to_string(),
            Value::Int(i) => i.to_string(),
            v => v.display(),
        }
    }

    #[test]
    fn parse_headers_drops_control_char_injection() {
        // A lone CR inside a value (the request-smuggling / response-splitting
        // vector) survives head.lines() — which splits on \n and strips only a
        // TRAILING \r — so "X-Smuggle: v\rContent-Length: 0" arrives as one line
        // with a raw \r in the value. parse_headers MUST drop it, not relay it
        // verbatim to the next hop.
        let head = "GET / HTTP/1.1\nHost: x\nX-Smuggle: v\rContent-Length: 0\nAccept: text/html\n";
        let hs = parse_headers(head);
        let names: Vec<&str> = hs.iter().map(|(n, _)| n.as_str()).collect();
        assert!(
            names.contains(&"Host") && names.contains(&"Accept"),
            "legit header dropped: {:?}",
            hs
        );
        assert!(
            !names.contains(&"X-Smuggle"),
            "CR-injected header was relayed: {:?}",
            hs
        );
        // NO relayed header carries ANY control byte (CR / LF / NUL).
        for (n, v) in &hs {
            assert!(
                !n.bytes()
                    .chain(v.bytes())
                    .any(|b| b == b'\r' || b == b'\n' || b == 0),
                "control byte survived in header {:?}: {:?}",
                n,
                v
            );
        }
        // A NUL in a value is likewise dropped; a clean header beside it survives.
        let hs2 = parse_headers("GET / HTTP/1.1\nX-Nul: a\0b\nOk: yes\n");
        assert_eq!(
            hs2.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>(),
            vec!["Ok"],
            "{:?}",
            hs2
        );
    }

    #[test]
    fn router_context_carries_configured_upstream_parts() {
        let upstream = Some("http://api:8000/base".to_string());
        let metrics = RouterMetricsSnapshot {
            native_route_count: 13,
            total_requests: 21,
            native_requests: 17,
            fanout_requests: 3,
            local_control_requests: 1,
            native_error_requests: 0,
            choice_attempts: 52,
            choice_successes: 18,
            choice_failures: 34,
            observed_path_count: 5,
            observed_native_route_count: 4,
            observed_fanout_path_count: 1,
            fanout_path_counts: vec![RouterFanoutPathCount {
                path: "/api/ideas".to_string(),
                count: 3,
                source: "observed-fanout-path".to_string(),
            }],
            next_bml_candidate: RouterBmlCandidate {
                path: "/api/ideas".to_string(),
                count: 3,
                source: "observed-fanout-path".to_string(),
            },
            next_bml_candidate_path: "/api/ideas".to_string(),
            next_bml_candidate_requests: 3,
            next_bml_candidate_source: "observed-fanout-path".to_string(),
        };
        let pairs = router_context_data("GET", "/native?x=1", "/native", &upstream, &metrics, None);

        assert_eq!(str_for(&pairs, "__request_method__"), "GET");
        assert_eq!(str_for(&pairs, "__request_target__"), "/native?x=1");
        assert_eq!(str_for(&pairs, "__request_path__"), "/native");
        assert_eq!(
            str_for(&pairs, "__router_upstream__"),
            "http://api:8000/base"
        );
        assert_eq!(str_for(&pairs, "__router_upstream_host__"), "api");
        assert_eq!(str_for(&pairs, "__router_upstream_port__"), "8000");
        assert_eq!(str_for(&pairs, "__router_upstream_base_path__"), "/base");
        assert_eq!(str_for(&pairs, "__router_native_route_count__"), "13");
        assert_eq!(str_for(&pairs, "__router_total_requests__"), "21");
        assert_eq!(str_for(&pairs, "__router_native_requests__"), "17");
        assert_eq!(str_for(&pairs, "__router_fanout_requests__"), "3");
        assert_eq!(str_for(&pairs, "__router_local_control_requests__"), "1");
        assert_eq!(str_for(&pairs, "__router_choice_attempts__"), "52");
        assert_eq!(str_for(&pairs, "__router_choice_successes__"), "18");
        assert_eq!(str_for(&pairs, "__router_choice_failures__"), "34");
        assert_eq!(str_for(&pairs, "__router_observed_path_count__"), "5");
        assert_eq!(
            str_for(&pairs, "__router_observed_native_route_count__"),
            "4"
        );
        assert_eq!(
            str_for(&pairs, "__router_observed_fanout_path_count__"),
            "1"
        );
        assert_eq!(
            str_for(&pairs, "__router_next_bml_candidate_path__"),
            "/api/ideas"
        );
        assert_eq!(
            str_for(&pairs, "__router_next_bml_candidate_requests__"),
            "3"
        );
        assert_eq!(
            str_for(&pairs, "__router_next_bml_candidate_source__"),
            "observed-fanout-path"
        );
        let channel_policy = value_for(&pairs, "__router_channel_policy__");
        assert_eq!(list_tag(channel_policy), KH_TAG_CHANNEL_POLICY);
        let policy_rows = match channel_policy {
            Value::List(xs) => xs,
            _ => panic!("router channel policy must be a Form list value"),
        };
        assert!(matches!(&policy_rows[1], Value::Str(carrier) if carrier.as_ref() == "tcp"));
        assert!(matches!(&policy_rows[2], Value::Str(protocol) if protocol.as_ref() == "http/1.1"));
        assert!(matches!(&policy_rows[3], Value::List(methods) if methods.len() == 7));
        assert!(
            matches!(&policy_rows[4], Value::List(bridges) if bridges.len() == 1 && list_tag(&bridges[0]) == KH_TAG_METHOD_BRIDGE)
        );
        assert!(
            matches!(&policy_rows[5], Value::List(methods) if matches!(&methods[0], Value::Str(method) if method.as_ref() == "HEAD"))
        );
        assert!(matches!(&policy_rows[6], Value::List(methods) if methods.len() == 7));
        let observation = value_for(&pairs, "__router_observation__");
        let rows = dict_get(observation, "fanout_path_counts");
        assert!(matches!(rows, Value::List(xs) if xs.len() == 1));
        let first_row = match rows {
            Value::List(xs) => &xs[0],
            _ => &Value::Null,
        };
        assert_eq!(dict_str(first_row, "path"), "/api/ideas");
        assert_eq!(dict_str(first_row, "count"), "3");
        assert_eq!(dict_str(first_row, "source"), "observed-fanout-path");
        let candidate = dict_get(observation, "next_bml_candidate");
        assert_eq!(dict_str(candidate, "path"), "/api/ideas");
        assert_eq!(dict_str(candidate, "count"), "3");
        assert_eq!(dict_str(candidate, "source"), "observed-fanout-path");
    }

    fn test_closure(inst: u32) -> Arc<Closure> {
        Arc::new(Closure {
            name: inst,
            params: Vec::new(),
            body: NodeID {
                pkg: 0,
                level: 0,
                ty: 0,
                inst,
            },
            env: 0,
        })
    }

    fn route(
        name: &str,
        method: &str,
        pattern: &str,
        priority: i64,
        handler_name: &str,
        required_header: &str,
        pressure_budget: i64,
    ) -> RouteSpec {
        RouteSpec {
            name: name.to_string(),
            method: method.to_string(),
            pattern: pattern.to_string(),
            priority,
            handler_name: handler_name.to_string(),
            required_header: required_header.to_string(),
            pressure_budget,
            handler: test_closure(priority as u32 + 1),
            typed_request: false,
        }
    }

    fn list_tag(value: &Value) -> i64 {
        match value {
            Value::List(xs) => match xs.first() {
                Some(Value::Int(tag)) => *tag,
                _ => 0,
            },
            _ => 0,
        }
    }

    #[test]
    fn router_context_carries_selected_route_candidate_form_value() {
        let upstream = None;
        let metrics = RouterMetricsSnapshot {
            native_route_count: 1,
            ..RouterMetricsSnapshot::default()
        };
        let headers = vec![("Accept".to_string(), "application/json".to_string())];
        let exact_route = route(
            "runtime-health",
            "GET",
            "/api/runtime/health",
            9,
            "route_runtime_health",
            "Accept",
            0,
        );
        let blocked_route = route(
            "blocked-runtime",
            "GET",
            "/api/runtime/health",
            99,
            "route_blocked_runtime",
            "X-Missing",
            0,
        );
        let query = vec![("limit".to_string(), "20".to_string())];
        let routes = vec![blocked_route, exact_route];
        let route_choice = route_choice_for_request(
            &routes,
            "GET",
            "/api/runtime/health",
            &headers,
            &query,
            "{\"alive\":true}",
        );
        let pairs = router_context_data(
            "GET",
            "/api/runtime/health",
            "/api/runtime/health",
            &upstream,
            &metrics,
            Some(&route_choice),
        );

        let candidate_value = value_for(&pairs, "__router_route_candidate__");
        assert_eq!(list_tag(candidate_value), KH_TAG_ROUTE_CANDIDATE);
        let choice_value = value_for(&pairs, "__router_route_choice__");
        assert_eq!(list_tag(choice_value), KH_TAG_ROUTE_CHOICE);
        let candidates_value = value_for(&pairs, "__router_route_candidates__");
        assert!(matches!(candidates_value, Value::List(xs) if xs.len() == 2));
        let decisions_value = value_for(&pairs, "__router_route_decisions__");
        assert!(matches!(decisions_value, Value::List(xs) if xs.len() == 2));
        let signature_value = value_for(&pairs, "__router_route_choice_signature__");
        assert_eq!(list_tag(signature_value), KH_TAG_ROUTE_CHOICE_SIGNATURE);
        let decision_signatures_value = value_for(&pairs, "__router_route_decision_signatures__");
        assert!(matches!(decision_signatures_value, Value::List(xs) if xs.len() == 2));
        let signature_rows = match decision_signatures_value {
            Value::List(xs) => xs,
            _ => panic!("route decision signatures must be a Form list value"),
        };
        assert_eq!(
            list_tag(&signature_rows[0]),
            KH_TAG_ROUTE_DECISION_SIGNATURE
        );
        assert!(matches!(
            &signature_rows[0],
            Value::List(xs)
                if matches!(&xs[4], Value::Int(3))
                    && matches!(&xs[5], Value::Int(5))
                    && matches!(&xs[6], Value::Bool(false))
                    && matches!(&xs[7], Value::Bool(false))
        ));
        assert!(matches!(
            &signature_rows[1],
            Value::List(xs)
                if matches!(&xs[4], Value::Int(0))
                    && matches!(&xs[5], Value::Int(4))
                    && matches!(&xs[6], Value::Bool(true))
                    && matches!(&xs[7], Value::Bool(true))
        ));
        let decision_rows = match decisions_value {
            Value::List(xs) => xs,
            _ => panic!("route decisions must be a Form list value"),
        };
        assert_eq!(list_tag(&decision_rows[0]), KH_TAG_ROUTE_DECISION);
        assert!(matches!(
            &decision_rows[0],
            Value::List(xs)
                if matches!(&xs[2], Value::Bool(false))
                    && matches!(&xs[3], Value::Bool(false))
        ));
        assert!(matches!(
            &decision_rows[1],
            Value::List(xs)
                if matches!(&xs[2], Value::Bool(true))
                    && matches!(&xs[3], Value::Bool(true))
        ));
        let request_value = value_for(&pairs, "__kernel_request__");
        assert_eq!(list_tag(request_value), KH_TAG_REQUEST);
        let matrix_value = value_for(&pairs, "__router_route_candidate_matrix__");
        assert!(matches!(matrix_value, Value::List(xs) if xs.len() == 4));
        let request_rows = match request_value {
            Value::List(xs) => xs,
            _ => panic!("kernel request must be a Form list value"),
        };
        assert!(matches!(&request_rows[1], Value::Str(method) if method.as_ref() == "GET"));
        assert!(
            matches!(&request_rows[2], Value::Str(path) if path.as_ref() == "/api/runtime/health")
        );
        let request_headers = match &request_rows[3] {
            Value::List(xs) => xs,
            _ => panic!("kernel request headers must be a Form list value"),
        };
        assert_eq!(list_tag(&request_headers[0]), KH_TAG_HEADER);
        let request_query = match &request_rows[4] {
            Value::List(xs) => xs,
            _ => panic!("kernel request query must be a Form list value"),
        };
        assert_eq!(list_tag(&request_query[0]), KH_TAG_FIELD);
        assert!(
            matches!(&request_rows[5], Value::Str(body) if body.as_ref() == "{\"alive\":true}")
        );
        let rows = match candidate_value {
            Value::List(xs) => xs,
            _ => panic!("route candidate must be a Form list value"),
        };
        assert_eq!(list_tag(&rows[1]), KH_TAG_ROUTE);
        assert_eq!(list_tag(&rows[2]), KH_TAG_REQUEST);
        let candidate_request = match &rows[2] {
            Value::List(xs) => xs,
            _ => panic!("candidate request must be a Form list value"),
        };
        let candidate_query = match &candidate_request[4] {
            Value::List(xs) => xs,
            _ => panic!("candidate request query must be a Form list value"),
        };
        assert_eq!(list_tag(&candidate_query[0]), KH_TAG_FIELD);
        let candidate_matrix = match &rows[3] {
            Value::List(xs) => xs,
            _ => panic!("route candidate matrix must be a Form list value"),
        };
        assert_eq!(candidate_matrix.len(), 4);
        assert_eq!(list_tag(&candidate_matrix[0]), KH_TAG_PRESSURE_ROW);
        assert_eq!(str_for(&pairs, "__request_method__"), "GET");
        assert!(matches!(&rows[4], Value::Int(0)));
        assert!(matches!(&rows[5], Value::Int(1090)));
    }
}

#[cfg(test)]
mod route_spec_tests {
    use super::*;

    fn test_closure(inst: u32) -> Arc<Closure> {
        Arc::new(Closure {
            name: inst,
            params: Vec::new(),
            body: NodeID {
                pkg: 0,
                level: 0,
                ty: 0,
                inst,
            },
            env: 0,
        })
    }

    fn route(
        name: &str,
        method: &str,
        pattern: &str,
        priority: i64,
        required_header: &str,
        pressure_budget: i64,
    ) -> RouteSpec {
        RouteSpec {
            name: name.to_string(),
            method: method.to_string(),
            pattern: pattern.to_string(),
            priority,
            handler_name: format!("route_{}", name),
            required_header: required_header.to_string(),
            pressure_budget,
            handler: test_closure(priority as u32 + 1),
            typed_request: false,
        }
    }

    fn build_worker_kernel_from_source(
        src: &str,
        routes_path: &str,
    ) -> Result<(Kernel, Arena, RouteSpecs), String> {
        let program = RouteProgram::Source(Arc::new(src.to_string()));
        build_worker_kernel(&program, routes_path)
    }

    #[test]
    fn path_closure_row_remains_path_only_native_route() {
        let src = r#"
            (defn route_health () "ok")
            (let routes (list (list "/health" route_health)))
        "#;
        let (_, _, routes) = build_worker_kernel_from_source(src, "path-row-routes.fk")
            .expect("path/closure route manifest loads");
        let spec = &routes[0];

        assert_eq!(spec.name, "/health");
        assert_eq!(spec.method, "ANY");
        assert_eq!(spec.pattern, "/health");
        assert_eq!(spec.priority, 0);
        assert_eq!(spec.handler_name, "route_health");
        assert_eq!(spec.pressure_budget, 40);

        assert_eq!(
            select_route_spec(&routes, "POST", "/health", &[]).map(|r| r.name.as_str()),
            Some("/health")
        );
        assert!(select_route_spec(&routes, "GET", "/missing", &[]).is_none());
    }

    #[test]
    fn kernel_http_response_result_carries_status_headers_and_body() {
        let result = Value::List(Arc::new(vec![
            Value::Int(KH_TAG_RESPONSE),
            Value::Int(418),
            Value::List(Arc::new(vec![
                Value::List(Arc::new(vec![
                    Value::Int(KH_TAG_HEADER),
                    Value::Str("Content-Type".into()),
                    Value::Str("application/problem+json".into()),
                ])),
                Value::List(Arc::new(vec![
                    Value::Int(KH_TAG_HEADER),
                    Value::Str("X-Kernel-Response".into()),
                    Value::Str("native".into()),
                ])),
                Value::List(Arc::new(vec![
                    Value::Int(KH_TAG_HEADER),
                    Value::Str("Content-Length".into()),
                    Value::Str("999".into()),
                ])),
            ])),
            Value::Str("{\"detail\":\"teapot\"}".into()),
        ]));

        let parsed = handler_native_response(&result).expect("kh-response parses");
        assert_eq!(parsed.status_code, 418);
        assert_eq!(parsed.content_type, "application/problem+json");
        assert_eq!(parsed.body, "{\"detail\":\"teapot\"}");
        assert_eq!(
            parsed.headers,
            vec![("X-Kernel-Response".to_string(), "native".to_string())]
        );
    }

    #[test]
    fn status_response_tag_stays_compatible() {
        let result = Value::List(Arc::new(vec![
            Value::Str("__http_status__".into()),
            Value::Int(422),
            Value::Str("{\"detail\":\"invalid\"}".into()),
        ]));

        let parsed = handler_native_response(&result).expect("status tag parses");
        assert_eq!(parsed.status_code, 422);
        assert_eq!(parsed.content_type, "");
        assert!(parsed.headers.is_empty());
        assert_eq!(parsed.body, "{\"detail\":\"invalid\"}");
    }

    #[test]
    fn kernel_http_route_row_resolves_handler_from_manifest() {
        let src = r#"
            (defn route_weighted_average () "ok")
            (let routes
              (list
                (list 43004 "weighted-average" "GET"
                      "/api/utils/weighted_average" 7
                      "route_weighted_average" "Accept" 0)))
        "#;
        let (_, _, routes) = build_worker_kernel_from_source(src, "kernel-http-route.fk")
            .expect("KernelHTTPRoute manifest loads");
        let spec = &routes[0];

        assert_eq!(spec.name, "weighted-average");
        assert_eq!(spec.method, "GET");
        assert_eq!(spec.pattern, "/api/utils/weighted_average");
        assert_eq!(spec.priority, 7);
        assert_eq!(spec.handler_name, "route_weighted_average");
        assert_eq!(spec.required_header, "Accept");
        assert_eq!(spec.pressure_budget, 0);
    }

    // Route classes export their methods as `Class_method` closures. The raw
    // route list consumes the generated handler through a route-data ref, so it
    // does not rely on a section-local alias escaping into the following Form.
    #[test]
    fn source_route_manifest_compiles_to_recipe_object_program() {
        let manifest = r#"
            section [form.route] {
                template RouteCell<TRequest, TResponse> {
                    member request: TRequest;
                    member response: TResponse;
                    member route: KernelHTTPRoute;
                }

                class HealthRoute : RouteCell<KernelHTTPRequest, KernelHTTPResponse> {
                    def handle(request) {
                        "ok";
                    }

                    route = route_data(health, handle);
                }

            }

            (let routes (list (kh-route-data-ref "health" HealthRoute_handle)))
        "#;
        let path = env::temp_dir().join(format!(
            "form-router-source-route-object-{}.fk",
            std::process::id()
        ));
        fs::write(&path, manifest).expect("write source route manifest");
        let path_str = path.to_string_lossy().to_string();
        let compiled = source_compile_manifest_recipe_object(&path_str, "../form-stdlib")
            .expect("source route manifest compiles to recipe object");
        assert!(compiled.kernel.by_id.contains_key(&compiled.root));

        let program = RouteProgram::RecipeObject(Arc::new(compiled));
        let route_data = RouteDataRegistry {
            routes: HashMap::from([(
                "health".to_string(),
                RouteData {
                    name: "health".to_string(),
                    method: "ANY".to_string(),
                    pattern: "/health".to_string(),
                    priority: 0,
                    required_header: String::new(),
                    pressure_budget: 40,
                },
            )]),
        };
        let (_, _, routes, _) =
            build_worker_kernel_with_route_data(&program, &path_str, &route_data)
                .expect("recipe-object route program loads");
        let spec = &routes[0];
        assert_eq!(spec.name, "health");
        assert_eq!(spec.method, "ANY");
        assert_eq!(spec.pattern, "/health");
        assert_eq!(spec.handler_name, "HealthRoute_handle");
        assert_eq!(spec.pressure_budget, 40);

        let _ = fs::remove_file(path);
    }

    #[test]
    fn source_compiled_workload_executes_bml_tending_cells() {
        let paths = vec![
            "../form-stdlib/core.fk".to_string(),
            "../form-stdlib/kernel-http.fk".to_string(),
            "../form-stdlib/native-route-goal-cells.fk".to_string(),
            "../form-stdlib/queries/native-route-goal-tending.fk".to_string(),
        ];
        let mut compiled = source_compile_file_workload_recipe_object(&paths, "../form-stdlib")
            .expect("source-authored workload compiles");
        let value = execute_root(&mut compiled.kernel, compiled.root);
        let rendered = value.display();
        assert!(rendered.contains("native-route-front-door-loop"));
        assert!(rendered.contains("author-high-grammar-handler"));
        assert!(rendered.contains("prove-byte-identity"));
    }

    #[test]
    fn kernel_http_route_row_requires_bound_handler_closure() {
        let src = r#"
            (let routes
              (list
                (list 43004 "missing" "GET"
                      "/api/missing" 0 "route_missing" "" 0)))
        "#;
        let err = match build_worker_kernel_from_source(src, "kernel-http-missing-handler.fk") {
            Ok(_) => panic!("missing handler should fail manifest loading"),
            Err(e) => e,
        };

        assert!(err.contains("KernelHTTPRoute missing handler route_missing is not bound"));
    }

    #[test]
    fn kernel_http_route_selection_bridges_head_through_get() {
        let routes = vec![route("get-only", "GET", "/api/items", 0, "", 20)];

        assert!(select_route_spec(&routes, "POST", "/api/items", &[]).is_none());
        assert_eq!(
            select_route_spec(&routes, "GET", "/api/items", &[]).map(|r| r.name.as_str()),
            Some("get-only")
        );
        let head_choice = route_choice_for_request(&routes, "HEAD", "/api/items", &[], &[], "");
        assert_eq!(
            head_choice
                .selected
                .as_ref()
                .map(|selection| selection.route.name.as_str()),
            Some("get-only")
        );
        assert_eq!(head_choice.decisions[0].candidate.pressure, 20);
    }

    #[test]
    fn kernel_http_route_selection_uses_priority_after_pressure_budget() {
        let routes = vec![
            route("low", "GET", "/api/items", 1, "", 0),
            route("high", "GET", "/api/items", 5, "", 0),
        ];

        assert_eq!(
            select_route_spec(&routes, "GET", "/api/items", &[]).map(|r| r.name.as_str()),
            Some("high")
        );
    }

    #[test]
    fn kernel_http_route_selection_honors_wildcard_budget_and_required_header() {
        let routes = vec![route("tail", "GET", "/api/items/*", 0, "X-Form", 25)];
        let headers = vec![("x-form".to_string(), "yes".to_string())];

        assert!(select_route_spec(&routes, "GET", "/api/items/42", &[]).is_none());
        assert_eq!(
            select_route_spec(&routes, "GET", "/api/items/42", &headers).map(|r| r.name.as_str()),
            Some("tail")
        );
        assert!(select_route_spec(&routes, "GET", "/api/other", &headers).is_none());
    }

    #[test]
    fn kernel_http_route_selection_honors_template_segments() {
        let routes = vec![
            route("wildcard", "GET", "/api/items/*", 1, "", 25),
            route("braced-template", "GET", "/api/items/{item_id}", 2, "", 10),
            route("colon-template", "GET", "/api/colon/:item_id", 2, "", 10),
            route("exact", "GET", "/api/items/fixed", 3, "", 0),
        ];

        assert_eq!(
            select_route_spec(&routes, "GET", "/api/items/42", &[]).map(|r| r.name.as_str()),
            Some("braced-template")
        );
        assert_eq!(
            select_route_candidate(&routes, "GET", "/api/items/42", &[], &[], "")
                .map(|selection| selection.candidate.pressure),
            Some(10)
        );
        assert_eq!(
            select_route_spec(&routes, "GET", "/api/items/fixed", &[]).map(|r| r.name.as_str()),
            Some("exact")
        );
        assert_eq!(
            select_route_spec(&routes, "GET", "/api/colon/42", &[]).map(|r| r.name.as_str()),
            Some("colon-template")
        );
        assert_eq!(
            select_route_spec(&routes, "GET", "/api/items/42/extra", &[]).map(|r| r.name.as_str()),
            Some("wildcard")
        );

        let template_only = vec![route(
            "braced-template",
            "GET",
            "/api/items/{item_id}",
            2,
            "",
            10,
        )];
        assert!(select_route_spec(&template_only, "GET", "/api/items/42/extra", &[]).is_none());
        assert!(select_route_spec(&template_only, "GET", "/api/items/", &[]).is_none());
    }

    #[test]
    fn source_bml_catalog_template_routes_select_natively_in_rust() {
        let manifest = fs::read_to_string("../../deploy/front-door/api.bml")
            .expect("read BML front-door catalog");
        let path = env::temp_dir().join(format!(
            "form-rust-router-template-catalog-{}.bml",
            std::process::id()
        ));
        fs::write(&path, manifest).expect("write route manifest copy");
        let path_str = path.to_string_lossy().to_string();
        let compiled = source_compile_manifest_recipe_object(&path_str, "../form-stdlib")
            .expect("source route manifest compiles");
        let program = RouteProgram::RecipeObject(Arc::new(compiled));
        let (_, _, routes, _) =
            build_worker_kernel_with_route_data(&program, &path_str, &RouteDataRegistry::default())
                .expect("BML route catalog loads");

        let headers = vec![("Accept".to_string(), "application/json".to_string())];
        let probes = vec![
            ("runtime-events-index", "GET", "/api/runtime/events"),
            ("spec-registry-index", "GET", "/api/spec-registry"),
            (
                "spec-registry-detail",
                "GET",
                "/api/spec-registry/web-ideas-specs-usage-pages",
            ),
            ("idea-specs", "GET", "/api/ideas/user-surfaces/specs"),
            ("views-stats", "GET", "/api/views/stats/lc-attuned-spaces"),
            (
                "reaction-concept-summary",
                "GET",
                "/api/reactions/concept/lc-attuned-spaces/summary",
            ),
            (
                "reaction-concept-threads",
                "GET",
                "/api/reactions/concept/lc-attuned-spaces/threads",
            ),
            (
                "concept-voices",
                "GET",
                "/api/concepts/lc-attuned-spaces/voices",
            ),
            (
                "household-request-detail",
                "GET",
                "/api/household/requests/request_123",
            ),
        ];

        for (name, method, path) in probes {
            assert_eq!(
                select_route_spec(&routes, method, path, &headers).map(|r| r.name.as_str()),
                Some(name),
                "{method} {path} should select {name}"
            );
        }

        let _ = fs::remove_file(path);
    }

    #[test]
    fn kernel_http_route_manifest_accepts_head_and_options_methods() {
        let src = r#"
            (defn route_probe () "ok")
            (defn route_options () "ok")
            (let routes
              (list
                (list 43004 "probe" "HEAD" "/probe" 0 "route_probe" "" 20)
                (list 43004 "probe-options" "OPTIONS" "/probe" 0 "route_options" "" 0)))
        "#;
        let (_, _, routes) = build_worker_kernel_from_source(src, "kernel-http-methods.fk")
            .expect("HEAD/OPTIONS KernelHTTPRoute manifest loads");

        assert_eq!(routes[0].method, "HEAD");
        assert_eq!(routes[1].method, "OPTIONS");
        assert_eq!(
            select_route_spec(&routes, "HEAD", "/probe", &[]).map(|r| r.name.as_str()),
            Some("probe")
        );
        assert_eq!(
            select_route_spec(&routes, "OPTIONS", "/probe", &[]).map(|r| r.name.as_str()),
            Some("probe-options")
        );
    }

    #[test]
    fn kernel_http_channel_policy_defaults_drive_protocol_invitation() {
        let policy = default_http_channel_policy();
        let route = route("probe", "GET", "/probe", 0, "", 25);

        assert!(channel_policy_route_method_valid(&policy, "OPTIONS"));
        assert_eq!(
            channel_policy_allow_header_value(&policy),
            "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
        );
        assert_eq!(
            route_method_pressure_with_policy(&policy, &route, "HEAD"),
            20
        );
        assert_eq!(
            buffered_response_body_for_method_with_policy(&policy, "HEAD", "ok"),
            ""
        );
        assert_eq!(
            buffered_response_body_for_method_with_policy(&policy, "GET", "ok"),
            "ok"
        );
    }

    #[test]
    fn buffered_response_body_for_method_omits_head_body() {
        assert_eq!(buffered_response_body_for_method("GET", "ok"), "ok");
        assert_eq!(buffered_response_body_for_method("HEAD", "ok"), "");
    }
}

fn url_decode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => {
                out.push(' ');
                i += 1;
            }
            b'%' if i + 2 < bytes.len() => {
                let hi = (bytes[i + 1] as char).to_digit(16);
                let lo = (bytes[i + 2] as char).to_digit(16);
                if let (Some(h), Some(l)) = (hi, lo) {
                    out.push(((h * 16 + l) as u8) as char);
                    i += 3;
                } else {
                    out.push(bytes[i] as char);
                    i += 1;
                }
            }
            other => {
                out.push(other as char);
                i += 1;
            }
        }
    }
    out
}

// A single pooled upstream connection: the live keep-alive TcpStream plus any
// bytes read past one response's end (pipelining/over-read on the upstream hop —
// the SAME hazard the client hop's `carry` solves). The over-read bytes belong
// to the NEXT response on this connection and must be seeded into the next read,
// never dropped — a mis-framed pooled connection corrupts the next request, the
// classic keep-alive proxy bug.
struct PooledConn {
    stream: TcpStream,
    carry: Vec<u8>,
}

// A per-worker cache of keep-alive upstream connections, keyed by (host, port).
// Because a worker handles requests SERIALLY on its own thread (the per-worker
// Kernel + Arena isolation from the worker pool), this needs NO locking: the
// worker OWNS its pool the way it owns its kernel. For a single upstream this is
// effectively one reusable connection that amortizes the TCP handshake across
// every fan-out the worker serves, the symmetric saving to the client-hop
// keep-alive (the router→upstream hop, where the client→router hop already
// reuses connections). The connection is taken out on use and returned only if
// the upstream kept it alive (Content-Length-framed, no `Connection: close`),
// so a half-consumed or close-marked connection is never reused.
//
// Honest scope of reuse: a connection is pooled only when its response was
// Content-Length-framed AND the upstream did not signal close. A chunked or
// unframed (read-to-close) response is read correctly but its connection is
// dropped, not pooled — chunked-body reuse remains a named-later breath.
#[derive(Default)]
struct UpstreamPool {
    conns: HashMap<(String, u16), PooledConn>,
}

impl UpstreamPool {
    fn new() -> Self {
        UpstreamPool {
            conns: HashMap::new(),
        }
    }
    // Take the pooled connection for this upstream if one is cached (removing it
    // so an error path can drop it without leaving a poisoned entry; a clean
    // response puts it back via `store`).
    fn take(&mut self, host: &str, port: u16) -> Option<PooledConn> {
        self.conns.remove(&(host.to_string(), port))
    }
    // Return a still-good connection to the pool for the next fan-out to reuse.
    fn store(&mut self, host: &str, port: u16, conn: PooledConn) {
        self.conns.insert((host.to_string(), port), conn);
    }
}

// How the upstream framed its response body, which decides how the router frames
// the SAME body to the client and whether the body can be PIPED chunk-by-chunk
// without ever holding it whole. The router never buffers the body — it observes
// it AS IT FLOWS — so the framing is all the router needs to relay byte-identical:
//   - Length(n)  -> Content-Length present: pipe exactly `n` body bytes upstream
//     →client. The client gets the SAME Content-Length; both connections stay
//     framed (the client knows precisely where the body ends), so the upstream
//     connection is REUSABLE (unless it signalled close) and the client's
//     keep-alive intent is honored.
//   - Chunked    -> Transfer-Encoding: chunked: relay the raw chunk framing
//     straight through to the client (NOT de-chunked) until the terminating
//     0-length chunk. Chunked is self-delimiting, so the client stays framed and
//     its keep-alive intent is honored; the upstream connection is NOT pooled
//     (chunked-body reuse is a named-later breath).
//   - Close      -> neither Content-Length nor chunked: the body's length is only
//     knowable by the upstream closing. Pipe upstream→client until EOF, then the
//     client connection MUST close too (no other way to mark the body's end), so
//     keep-alive is forced off on this hop.
enum ResponseFraming {
    Length(usize),
    Chunked,
    Close,
}

// The PARSED HEAD of one upstream response — everything the router needs to write
// the client response head and decide how to pipe the body — WITHOUT the body. The
// body never lands in a buffer; only the small head is read whole (it must be, to
// parse status + framing + relayed headers). `body_prefix` is the leading body
// bytes that arrived in the SAME read as the head terminator (the head read always
// over-reads a little); they are written to the client first, then the rest of the
// body is piped straight from the socket.
struct UpstreamHead {
    status: String,
    content_type: String,
    headers: Vec<(String, String)>,
    // The upstream connection's keep-alive intent (false on `Connection: close`
    // or HTTP/1.0 default). Combined with Length framing to decide pooling.
    upstream_keep_alive: bool,
    framing: ResponseFraming,
    // Body bytes already read past the head terminator (the head read's natural
    // over-read). Piped to the client before the rest of the body is streamed.
    body_prefix: Vec<u8>,
}

// Read ONLY the HEAD of one upstream response from a (possibly reused) connection,
// framing it so the BODY can be piped chunk-by-chunk afterward without ever being
// held whole. `carry` seeds the read with any bytes left over from the PREVIOUS
// response on this same connection (the over-read hazard, mirrored from the client
// hop's read_request). The head is small and must be buffered to parse; the body
// is NOT read here — it streams in `stream_body_to_client` after the client head
// is written. This split is what lets the stale-pooled-connection retry stay safe:
// a `Closed` (EOF before any byte) is detectable HERE, before a single body byte
// has been relayed to the client, so the caller can transparently reconnect+retry.
//
// Errors (a broken pipe, an immediate EOF before any byte) propagate up so the
// caller can transparently reconnect+retry on a stale pooled connection.
fn read_upstream_head(stream: &mut TcpStream, carry: Vec<u8>) -> Result<UpstreamHead, FanoutError> {
    // Read until the header terminator, seeding from carried bytes. Only the head
    // accumulates in `raw`; the body is streamed afterward, never buffered.
    let mut raw: Vec<u8> = carry;
    let mut buf = [0u8; 8192];
    // The HEAD is the only thing we hold whole; the shape-threshold here bounds the
    // head alone (a runaway header block), never the body — the body streams, so
    // its size is no longer a memory gate.
    let response_limit = response_shape_limit();
    let header_end: usize = match find_header_end(&raw) {
        Some(t) => t,
        None => loop {
            match stream.read(&mut buf) {
                Ok(0) => {
                    // EOF before any header terminator. If NOTHING arrived this
                    // was a dead/stale connection — signal CLOSED so the caller
                    // reconnects+retries ONCE (distinct from a Timeout, which is
                    // terminal). This is the pooled-connection stale-close path.
                    if raw.is_empty() {
                        return Err(FanoutError::Closed(
                            "upstream closed before response (stale connection)".to_string(),
                        ));
                    }
                    // Some bytes but no terminator — a malformed/truncated head.
                    break raw.len();
                }
                Ok(n) => {
                    raw.extend_from_slice(&buf[..n]);
                    if let Some(t) = find_header_end(&raw) {
                        break t;
                    }
                    if raw.len() > response_limit {
                        return Err(FanoutError::Other(format!(
                            "upstream response head is larger than we can hold right now \
                             ({} bytes observed, threshold {}; change the router configuration recipe)",
                            raw.len(),
                            response_limit,
                        )));
                    }
                }
                // A read deadline (FANOUT_READ_TIMEOUT) surfaces here as
                // WouldBlock/TimedOut on a HUNG upstream that accepted the
                // connection but never sent the head -> Timeout -> 504.
                Err(e) => return Err(classify_io_error(&e, "read upstream response head")),
            }
        },
    };
    let (head_end_excl_term, body_start) = if header_end >= 4 && raw.len() >= header_end {
        (header_end - 4, header_end)
    } else {
        (raw.len(), raw.len())
    };
    let head = String::from_utf8_lossy(&raw[..head_end_excl_term]).to_string();
    // The status line is everything after "HTTP/x.y " on the first head line.
    let status = head
        .lines()
        .next()
        .and_then(|line| line.split_once(' ').map(|(_, rest)| rest.to_string()))
        .unwrap_or_else(|| "502 Bad Gateway".to_string());
    let content_type = parse_content_type(&head);
    let headers: Vec<(String, String)> = parse_headers(&head)
        .into_iter()
        .filter(|(name, _)| relay_response_header(name))
        .collect();
    // Does the UPSTREAM intend to keep this connection alive? It is an HTTP/1.x
    // peer; honor an explicit `Connection: close` (and HTTP/1.0's close default).
    let upstream_keep_alive = upstream_response_keep_alive(&head);
    // The framing decides how the body is piped (and whether the connection pools).
    // Content-Length wins; else chunked (self-delimiting, relayed raw); else close.
    let framing = if let Some(total) = parse_content_length(&head) {
        ResponseFraming::Length(total)
    } else if head_is_chunked(&head) {
        ResponseFraming::Chunked
    } else {
        ResponseFraming::Close
    };
    // The leading body bytes that arrived alongside the head terminator. Piped to
    // the client first; the head itself is dropped (the client gets the router's
    // own framed head, not the upstream's raw one).
    let body_prefix = raw[body_start..].to_vec();
    Ok(UpstreamHead {
        status,
        content_type,
        headers,
        upstream_keep_alive,
        framing,
        body_prefix,
    })
}

// The outcome of piping ONE response body upstream→client: whether the upstream
// connection may be REUSED (pooled) and any bytes read past this response's framed
// end (the next response's head/body on a reused connection, carried forward so the
// next read starts exactly there). Mirrors the old UpstreamResponse's reuse verdict,
// but the BODY itself never appears here — it has already flowed to the client.
struct BodyOutcome {
    reusable: bool,
    leftover: Vec<u8>,
}

// PIPE one response body from the upstream stream straight to the client stream,
// in fixed-size chunks reused across reads — the whole body is NEVER held in one
// buffer. `body_prefix` is the leading body bytes already read with the head; they
// go to the client first, then the rest streams from the socket. The framing tells
// us where the body ends:
//   - Length(total): write exactly `total` body bytes (prefix counted), then any
//     surplus read past them is the NEXT response's bytes -> leftover; the
//     connection is REUSABLE iff the upstream kept it alive.
//   - Chunked: relay the raw chunk framing through until the terminating 0-length
//     chunk (`0\r\n\r\n`); the client stays framed, the connection is NOT pooled.
//   - Close: relay until the upstream closes (EOF); the connection is dropped and
//     the client connection must close too.
//
// Honest mid-stream failure: once the client head is written (the caller's job,
// BEFORE calling this), a stall or close mid-body can no longer become a clean 504
// — the head already went out. A read deadline / upstream close mid-body surfaces
// as an Err here; the caller closes the client connection, and the client sees a
// truncated body — the truthful outcome of an upstream that died mid-stream.
fn stream_body_to_client(
    upstream: &mut TcpStream,
    client: &mut TcpStream,
    framing: &ResponseFraming,
    body_prefix: &[u8],
) -> Result<BodyOutcome, FanoutError> {
    // 64 KiB pipe buffer, reused across every read — the only body-sized memory the
    // router ever holds is this one fixed chunk, regardless of the body's length.
    let mut buf = [0u8; 65536];
    match *framing {
        ResponseFraming::Length(total) => {
            // Write the prefix first, but only up to `total` (a prefix can over-read
            // into the NEXT response on a reused connection — that surplus is the
            // leftover, never written to this client).
            let from_prefix = body_prefix.len().min(total);
            if from_prefix > 0 {
                client
                    .write_all(&body_prefix[..from_prefix])
                    .map_err(|e| classify_io_error(&e, "write response body prefix to client"))?;
            }
            let mut written = from_prefix;
            // The leftover is any prefix bytes past `total` (the next response).
            let leftover: Vec<u8> = if body_prefix.len() > total {
                body_prefix[total..].to_vec()
            } else {
                Vec::new()
            };
            // Pipe the remaining body bytes straight from the upstream socket.
            while written < total {
                let want = (total - written).min(buf.len());
                match upstream.read(&mut buf[..want]) {
                    Ok(0) => {
                        // Upstream closed before the full framed body — the response
                        // is incomplete and the client head already went out, so the
                        // client sees a truncated body. NOT a clean error path.
                        return Err(FanoutError::Other(
                            "upstream closed mid-body (short Content-Length read)".to_string(),
                        ));
                    }
                    Ok(n) => {
                        client
                            .write_all(&buf[..n])
                            .map_err(|e| classify_io_error(&e, "write response body to client"))?;
                        written += n;
                    }
                    // A read deadline mid-body on a stalled upstream. The head is
                    // already sent, so this can't be a 504; it propagates and the
                    // caller closes the client connection.
                    Err(e) => return Err(classify_io_error(&e, "read upstream response body")),
                }
            }
            // Content-Length framing is the precondition for reuse; the caller ANDs
            // this with the upstream's keep-alive intent (from the head) before
            // pooling. The leftover is meaningful only on a reused connection, but
            // the caller drops it if it decides not to pool — so it is returned as-is.
            Ok(BodyOutcome {
                reusable: true,
                leftover,
            })
        }
        ResponseFraming::Chunked => {
            // Relay the raw chunk framing straight through (NOT de-chunked) to the
            // client, while a small incremental PARSER tracks the chunk boundaries so
            // we stop at the TRUE terminating 0-length chunk — never at a `0\r\n\r\n`
            // byte sequence that merely happens to appear inside chunk DATA (the
            // hazard a naive byte-scan has). The parser consumes the same bytes it
            // relays; it never accumulates the body, only the current chunk's
            // size-line and a tiny amount of framing. The connection is never pooled.
            let mut parser = ChunkParser::new();
            // The prefix (chunk framing that arrived with the head) is relayed first
            // and fed through the parser — the body may have started, or even fully
            // arrived, in the same read as the head.
            if !body_prefix.is_empty() {
                client
                    .write_all(body_prefix)
                    .map_err(|e| classify_io_error(&e, "write chunked body prefix to client"))?;
                if parser.feed(body_prefix)? {
                    // The whole chunked body (through the terminating 0-chunk) already
                    // arrived with the head.
                    return Ok(BodyOutcome {
                        reusable: false,
                        leftover: Vec::new(),
                    });
                }
            }
            loop {
                match upstream.read(&mut buf) {
                    Ok(0) => break, // upstream closed — relay ends (best-effort)
                    Ok(n) => {
                        client
                            .write_all(&buf[..n])
                            .map_err(|e| classify_io_error(&e, "write chunked body to client"))?;
                        if parser.feed(&buf[..n])? {
                            break; // terminating 0-length chunk relayed — body done
                        }
                    }
                    Err(e) => {
                        return Err(classify_io_error(&e, "read upstream chunked response body"))
                    }
                }
            }
            // Chunked is relayed raw and the connection is never pooled.
            Ok(BodyOutcome {
                reusable: false,
                leftover: Vec::new(),
            })
        }
        ResponseFraming::Close => {
            // No Content-Length, no chunked: the body ends when the upstream closes.
            // Pipe the prefix, then everything until EOF; the connection is dropped.
            if !body_prefix.is_empty() {
                client
                    .write_all(body_prefix)
                    .map_err(|e| classify_io_error(&e, "write unframed body prefix to client"))?;
            }
            loop {
                match upstream.read(&mut buf) {
                    Ok(0) => break, // upstream closed — the unframed body is complete
                    Ok(n) => {
                        client
                            .write_all(&buf[..n])
                            .map_err(|e| classify_io_error(&e, "write unframed body to client"))?;
                    }
                    Err(e) => {
                        return Err(classify_io_error(
                            &e,
                            "read upstream response body (to close)",
                        ))
                    }
                }
            }
            Ok(BodyOutcome {
                reusable: false,
                leftover: Vec::new(),
            })
        }
    }
}

// An incremental HTTP/1.1 chunked-transfer parser that tracks chunk BOUNDARIES so
// the streaming relay stops at the TRUE terminating 0-length chunk — not at a
// `0\r\n\r\n` byte run that merely appears inside chunk DATA. It is fed the same
// bytes the relay writes to the client and never accumulates the body: it holds
// only the current size/trailer LINE (tiny) and the remaining-bytes counter for the
// chunk currently being skipped over. `feed` returns true once the terminating
// 0-length chunk (and its trailer section) has been consumed. This is FRAMING
// tracking, not de-chunking — the bytes still relay raw and verbatim.
enum ChunkPhase {
    // Reading a chunk-size line (hex digits + optional `;extension`) up to CRLF.
    Size,
    // Skipping `remaining` data bytes of the current chunk.
    Data { remaining: usize },
    // Consuming the 2-byte CRLF that follows a chunk's data (`have` seen so far).
    DataCrlf { have: u8 },
    // After the 0-length chunk: consuming the trailer section line-by-line until the
    // terminating empty line.
    Trailer,
}

struct ChunkParser {
    phase: ChunkPhase,
    // The current size or trailer LINE being accumulated until its CRLF. Bounded by
    // a sanity cap so a malformed upstream can't grow it without limit.
    line: Vec<u8>,
}

impl ChunkParser {
    fn new() -> Self {
        ChunkParser {
            phase: ChunkPhase::Size,
            line: Vec::new(),
        }
    }

    // Feed the next slice of relayed bytes. Returns Ok(true) when the terminating
    // 0-length chunk + trailer have been fully consumed (the body is complete), else
    // Ok(false) (more bytes expected). A malformed size line is an Other error.
    fn feed(&mut self, mut data: &[u8]) -> Result<bool, FanoutError> {
        // A chunk-size / trailer line longer than this is treated as malformed — a
        // real size line is a handful of bytes; this only guards against a runaway
        // upstream, it is not a body-size limit (the body itself never lands here).
        const MAX_LINE: usize = 16 * 1024;
        while !data.is_empty() {
            match self.phase {
                ChunkPhase::Size => {
                    // Accumulate up to and including the CRLF that ends the size line.
                    if let Some(pos) = data.iter().position(|&b| b == b'\n') {
                        self.line.extend_from_slice(&data[..pos]); // up to (excl) \n
                        data = &data[pos + 1..];
                        // The size is the hex prefix before any `;` extension or CR.
                        let line = std::mem::take(&mut self.line);
                        let size = parse_chunk_size(&line)?;
                        if size == 0 {
                            self.phase = ChunkPhase::Trailer;
                        } else {
                            self.phase = ChunkPhase::Data { remaining: size };
                        }
                    } else {
                        self.line.extend_from_slice(data);
                        data = &[];
                        if self.line.len() > MAX_LINE {
                            return Err(FanoutError::Other(
                                "chunked size line too long (malformed upstream)".to_string(),
                            ));
                        }
                    }
                }
                ChunkPhase::Data { remaining } => {
                    let take = remaining.min(data.len());
                    data = &data[take..];
                    let left = remaining - take;
                    self.phase = if left == 0 {
                        ChunkPhase::DataCrlf { have: 0 }
                    } else {
                        ChunkPhase::Data { remaining: left }
                    };
                }
                ChunkPhase::DataCrlf { have } => {
                    // Consume exactly two bytes (CR LF) following the chunk data.
                    let need = 2 - have as usize;
                    let take = need.min(data.len());
                    data = &data[take..];
                    let now = have + take as u8;
                    self.phase = if now >= 2 {
                        ChunkPhase::Size
                    } else {
                        ChunkPhase::DataCrlf { have: now }
                    };
                }
                ChunkPhase::Trailer => {
                    // Consume trailer lines until the terminating empty line. Each
                    // line ends at `\n`; an empty line (just CR before it, or nothing)
                    // ends the body.
                    if let Some(pos) = data.iter().position(|&b| b == b'\n') {
                        self.line.extend_from_slice(&data[..pos]);
                        data = &data[pos + 1..];
                        let line = std::mem::take(&mut self.line);
                        // Empty (after trimming a trailing CR) => end of body.
                        let trimmed: &[u8] = if line.last() == Some(&b'\r') {
                            &line[..line.len() - 1]
                        } else {
                            &line
                        };
                        if trimmed.is_empty() {
                            return Ok(true);
                        }
                        // A non-empty trailer header line — keep consuming.
                    } else {
                        self.line.extend_from_slice(data);
                        data = &[];
                        if self.line.len() > MAX_LINE {
                            return Err(FanoutError::Other(
                                "chunked trailer line too long (malformed upstream)".to_string(),
                            ));
                        }
                    }
                }
            }
        }
        Ok(false)
    }
}

// Parse a chunk-size line's hex value — the digits BEFORE any `;extension` or CR.
// e.g. `1a3f`, `1a3f;name=val`, `0`. An empty or non-hex prefix is malformed.
fn parse_chunk_size(line: &[u8]) -> Result<usize, FanoutError> {
    // Cut at the first `;` (chunk extension) or CR, whichever comes first.
    let end = line
        .iter()
        .position(|&b| b == b';' || b == b'\r')
        .unwrap_or(line.len());
    let hex = &line[..end];
    let s = std::str::from_utf8(hex)
        .map_err(|_| FanoutError::Other("chunked size not UTF-8 (malformed)".to_string()))?
        .trim();
    usize::from_str_radix(s, 16)
        .map_err(|_| FanoutError::Other(format!("bad chunked size line: {:?}", s)))
}

// Whether the UPSTREAM signalled it will keep its connection open after this
// response, per RFC 7230: HTTP/1.1 stays open unless `Connection: close`;
// HTTP/1.0 closes unless `Connection: keep-alive`. Mirrors head_keep_alive but
// reads a RESPONSE's status line (the HTTP version sits in the same first token).
fn upstream_response_keep_alive(head: &str) -> bool {
    let status_line = head.lines().next().unwrap_or("");
    let is_http11_or_higher = status_line
        .split(' ')
        .next()
        .map(|proto| proto >= "HTTP/1.1")
        .unwrap_or(false);
    let mut explicit: Option<bool> = None;
    for line in head.lines().skip(1) {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("connection") {
                let v = value.trim().to_ascii_lowercase();
                if v.contains("close") {
                    explicit = Some(false);
                } else if v.contains("keep-alive") {
                    explicit = Some(true);
                }
            }
        }
    }
    explicit.unwrap_or(is_http11_or_higher)
}

// Whether the upstream response uses chunked transfer encoding (so the body is
// NOT Content-Length-framed). Used only to make the no-Content-Length fall-through
// a conscious, named decision: chunked bodies are read-to-close and not pooled.
fn head_is_chunked(head: &str) -> bool {
    for line in head.lines() {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("transfer-encoding")
                && value.trim().to_ascii_lowercase().contains("chunked")
            {
                return true;
            }
        }
    }
    false
}

// Map a fan-out hop failure that happened BEFORE any body byte reached the client
// (connect/write failed, the head read failed, the stale-pool retry failed) into a
// small BUFFERED error response written through the ONE emit shape. A TIMEOUT
// (hung/slow upstream: connect, write, or head-read deadline expired) becomes a
// clean 504 Gateway Timeout; a Closed or Other failure is a 502 Bad Gateway. This
// is the single place the fan-out error maps to a status — and it is only reachable
// while the client head is UNWRITTEN, so a clean framed error is still possible
// (once the head is out and the body is streaming, a mid-stream failure can no
// longer become a status — it closes the client connection instead).
fn fanout_error_response(err: &FanoutError) -> (String, String) {
    match err {
        FanoutError::Timeout(e) => (
            "504 Gateway Timeout".to_string(),
            format!("upstream timeout: {}\n", e),
        ),
        FanoutError::Closed(e) | FanoutError::Other(e) => (
            "502 Bad Gateway".to_string(),
            format!("fan-out upstream error: {}\n", e),
        ),
    }
}

// Resolve + connect to the upstream with a BOUNDED connect timeout, then set the
// per-use read AND write deadlines on the fresh stream. Every fan-out connection
// (the first, the no-pool path, and the stale-pool retry) goes through here, so
// the deadlines are set in ONE place and a pooled connection that may carry the
// client-hop's idle timeout is re-armed with the fan-out deadlines on each use.
//   - resolve failure -> Other (a 502; the host name is bad, not a timeout).
//   - connect_timeout expiry -> TimedOut io error -> Timeout (a 504).
// connect_timeout needs a concrete SocketAddr (not a (host,port) tuple), so the
// host is resolved first and the first resolved address is dialed.
fn connect_upstream_with_timeout(host: &str, port: u16) -> Result<TcpStream, FanoutError> {
    let connect_timeout = fanout_connect_timeout();
    let read_timeout = fanout_read_timeout();
    let addr = (host, port)
        .to_socket_addrs()
        .map_err(|e| FanoutError::Other(format!("resolve {}:{}: {}", host, port, e)))?
        .next()
        .ok_or_else(|| FanoutError::Other(format!("resolve {}:{}: no address", host, port)))?;
    let stream = TcpStream::connect_timeout(&addr, connect_timeout)
        .map_err(|e| classify_io_error(&e, &format!("connect {}:{}", host, port)))?;
    // Bound every active read and write so a HUNG upstream (accepts the connection
    // but never responds, or never drains its receive buffer) cannot pin the worker
    // — the deadline surfaces as a TimedOut/WouldBlock io error -> Timeout -> 504.
    stream
        .set_read_timeout(Some(read_timeout))
        .map_err(|e| FanoutError::Other(format!("set read timeout: {}", e)))?;
    stream
        .set_write_timeout(Some(read_timeout))
        .map_err(|e| FanoutError::Other(format!("set write timeout: {}", e)))?;
    Ok(stream)
}

// The ONE response-emit shape — core-abstraction-first: every response (native,
// fan-out, error) is written here, so the framing the router owns is written in
// exactly one place and cannot diverge between arms.
//
// FRAMING THE ROUTER OWNS (always, on every response):
//   - Content-Length: ACCURATE, from the body it holds — that is what makes
//     keep-alive work without chunked encoding (the client knows precisely where
//     the body ends and the next response begins).
//   - Connection: `keep-alive` when the connection will serve more requests,
//     `close` on the final response (client asked to close, idle timeout, EOF,
//     or an error whose framing is uncertain).
//   - X-Form-Router: which arm served this (`native-kernel` / `fanout-python` /
//     a control marker).
// These are the router's client-hop framing; a relayed upstream header can NEVER
// clobber them (hop-by-hop + Content-Length/Content-Type are filtered out of
// `relayed` by relay_response_header before they reach here).
//
// `content_type` is the response's Content-Type: the upstream's real one on a
// fan-out (so a JSON/HTML route survives the proxy instead of being flattened to
// text/plain), or the native default `text/plain; charset=utf-8` when empty.
// `relayed` is the upstream's other end-to-end headers (Set-Cookie,
// Cache-Control, Location, ETag, X-*, …) on a fan-out, EMPTY for native/error
// responses. Chunked transfer encoding remains a named-later breath
// (KERNEL_AS_ROUTER.md HTTP-version row).
fn http_response(
    status: &str,
    body: &str,
    router: &str,
    keep_alive: bool,
    content_type: &str,
    relayed: &[(String, String)],
) -> String {
    let ct = if content_type.trim().is_empty() {
        "text/plain; charset=utf-8"
    } else {
        content_type.trim()
    };
    // Start with the framing the router owns, then append the relayed end-to-end
    // headers verbatim (each already filtered to exclude hop-by-hop and the
    // router-owned framing). Content-Type carries its own dedicated line.
    let mut out = format!(
        "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nX-Form-Router: {}\r\nConnection: {}\r\n",
        status,
        ct,
        body.as_bytes().len(),
        router,
        if keep_alive { "keep-alive" } else { "close" },
    );
    push_fanout_native_invitation_headers(&mut out, router);
    for (name, value) in relayed {
        out.push_str(&format!("{}: {}\r\n", name, value));
    }
    out.push_str("\r\n");
    out.push_str(body);
    out
}

fn buffered_response_body_for_method_with_policy<'a>(
    policy: &ChannelPolicy,
    method: &str,
    body: &'a str,
) -> &'a str {
    if channel_policy_no_body_method(policy, method) {
        ""
    } else {
        body
    }
}

#[cfg(test)]
fn buffered_response_body_for_method<'a>(method: &str, body: &'a str) -> &'a str {
    buffered_response_body_for_method_with_policy(&default_http_channel_policy(), method, body)
}

// Write ONLY the client response HEAD for a STREAMING fan-out, then the body is
// piped separately (so the body never lands in a buffer). The framing the router
// owns is authored here exactly as `http_response` authors it, except the
// body-length line varies with how the body will be streamed:
//   - Length(n): `Content-Length: n` — the SAME length the upstream declared, so
//     the client knows precisely where the body ends; both connections stay framed.
//   - Chunked: `Transfer-Encoding: chunked` (NO Content-Length) — the raw chunk
//     framing is relayed through, self-delimiting, so the client stays framed.
//   - Close: neither line — the body's end is the connection close itself, so the
//     client reads to close (and `keep_alive` must already be false here).
// X-Form-Router and the relayed end-to-end headers (Set-Cookie, Cache-Control, …)
// are written the same as the buffered path; a relayed upstream header can NEVER
// clobber the router-owned framing (Content-Length/Content-Type/Connection +
// Transfer-Encoding are filtered out of `relayed` by relay_response_header /
// is_hop_by_hop before they reach here).
fn write_response_head(
    client: &mut TcpStream,
    status: &str,
    router: &str,
    keep_alive: bool,
    content_type: &str,
    relayed: &[(String, String)],
    framing: &ResponseFraming,
) -> Result<(), FanoutError> {
    let ct = if content_type.trim().is_empty() {
        "text/plain; charset=utf-8"
    } else {
        content_type.trim()
    };
    let mut out = format!("HTTP/1.1 {}\r\nContent-Type: {}\r\n", status, ct);
    match *framing {
        ResponseFraming::Length(n) => {
            out.push_str(&format!("Content-Length: {}\r\n", n));
        }
        ResponseFraming::Chunked => {
            // The router relays the upstream's chunk framing verbatim, so the
            // client hop is chunked too — it owns this Transfer-Encoding (the
            // upstream's was stripped as hop-by-hop on the way in).
            out.push_str("Transfer-Encoding: chunked\r\n");
        }
        ResponseFraming::Close => {
            // No length line: the body ends at connection close. keep_alive is
            // forced false by the caller on this framing.
        }
    }
    out.push_str(&format!(
        "X-Form-Router: {}\r\nConnection: {}\r\n",
        router,
        if keep_alive { "keep-alive" } else { "close" },
    ));
    push_fanout_native_invitation_headers(&mut out, router);
    for (name, value) in relayed {
        out.push_str(&format!("{}: {}\r\n", name, value));
    }
    out.push_str("\r\n");
    client
        .write_all(out.as_bytes())
        .map_err(|e| classify_io_error(&e, "write response head to client"))
}

// Send a fully-built request on `stream` and read exactly ONE response HEAD back,
// seeding the read with `carry` (bytes left over from a PRIOR response on this same
// reused connection). The BODY is NOT read here — it streams afterward, straight to
// the client, never buffered. Factored out so the stale-pooled-connection RETRY
// path runs the identical send+read-head shape — one fan-out hop logic, used for
// both the first attempt and the retry (core-abstraction-first: the retry is not a
// fork, it is the same shape on a fresh socket). The retry is SAFE precisely because
// it ends at the head: a `Closed` here means no body byte has reached the client.
fn send_and_read_head(
    stream: &mut TcpStream,
    request: &[u8],
    carry: Vec<u8>,
) -> Result<UpstreamHead, FanoutError> {
    // A write deadline (FANOUT_READ_TIMEOUT, set as the write timeout too) surfaces
    // here as Timeout if the upstream accepts but never drains its receive buffer.
    // A broken pipe / reset on a POOLED connection the upstream already closed is
    // classified Closed by classify_io_error -> the stale-pool reconnect+retry. A
    // clean stale-close that buffers the write and only EOFs on the read is caught
    // on the read side (also Closed). Either way a stale pooled connection retries
    // once; a Timeout never does.
    stream
        .write_all(request)
        .map_err(|e| classify_io_error(&e, "write request"))?;
    read_upstream_head(stream, carry)
}

// The verdict a streaming fan-out returns to the keep-alive serve loop: whether the
// CLIENT connection may serve another request. `true` keeps it open; `false` closes
// it (the client asked to close, the response was close-framed/unframed, OR a
// mid-stream failure left the connection in an uncertain state — the only honest
// move is to close). It is the same bool `handle_request` returns on its other arms,
// named for intent at the streaming boundary.
type ClientKeepAlive = bool;

// STREAM a fan-out: forward the client's request to the upstream and PIPE the
// upstream's response body straight back to the client, with the whole body NEVER
// held in one buffer. This replaces the old buffer-then-emit fan-out: the router
// observes the circulation AS IT FLOWS.
//
// The shape, end to end:
//   1. Build the upstream request ONCE (reused verbatim for the stale-pool retry).
//   2. Get-or-create the pooled upstream connection; send the request and read the
//      response HEAD (small, buffered to parse). A `Closed` here — and ONLY here,
//      before any body byte has reached the client — triggers a transparent
//      reconnect+retry (the stale-pool path), exactly as before. A Timeout/Other
//      before the head propagates to a buffered 504/502 written to the client.
//   3. Once the head is parsed, decide the CLIENT framing (Length echoes the
//      upstream's Content-Length; Chunked relays the chunk framing; Close means the
//      body ends at connection close so the client connection must close too), write
//      the client response head, then PIPE the body upstream→client in fixed chunks.
//   4. On a Length-framed response the upstream connection is pooled IFF the upstream
//      kept it alive; chunked/unframed connections are dropped (never pooled).
//
// Honest mid-stream truncation: after the client head is written, a stall or close
// mid-body can no longer become a clean 504 — the head already went out. Such a
// failure closes the client connection (returns false); the client sees a truncated
// body, the truthful outcome of an upstream that died mid-stream.
fn fanout_stream_to_client(
    client: &mut TcpStream,
    client_keep_alive: ClientKeepAlive,
    upstream: &str,
    method: &str,
    target: &str,
    req_headers: &[(String, String)],
    body: &[u8],
    pool: &mut UpstreamPool,
) -> ClientKeepAlive {
    // Parse the upstream + build the request bytes. A bad upstream URL is an Other
    // error -> a buffered 502 (the head is unwritten, so a clean status is possible).
    let (host, port, base_path) = match parse_http_upstream(upstream) {
        Ok(v) => v,
        Err(e) => {
            return emit_buffered_fanout_error(client, client_keep_alive, &FanoutError::Other(e))
        }
    };
    let request_target = format!(
        "{}{}",
        base_path,
        if target.starts_with('/') { target } else { "/" }
    );
    // Build the request bytes ONCE — reused verbatim for the first attempt and the
    // stale-connection retry. The router owns the upstream-hop framing: `Host` is
    // rewritten to the upstream; `Connection: keep-alive` asks the upstream to hold
    // the connection open so the NEXT fan-out reuses it; HTTP/1.1 so keep-alive is
    // the default and the response can be Content-Length-framed. Content-Length is
    // set from the body the router actually captured. The CLIENT's end-to-end
    // headers (Authorization, Cookie, Accept*, …) are forwarded verbatim; hop-by-hop
    // and router-owned framing headers are filtered by forward_request_header.
    let mut head = format!(
        "{} {} HTTP/1.1\r\nHost: {}\r\nConnection: keep-alive\r\n",
        method, request_target, host
    );
    for (name, value) in req_headers {
        if forward_request_header(name) {
            head.push_str(&format!("{}: {}\r\n", name, value));
        }
    }
    head.push_str("X-Form-Router: fanout-python\r\n");
    push_fanout_native_invitation_headers(&mut head, "fanout-python");
    if !body.is_empty() {
        head.push_str(&format!("Content-Length: {}\r\n", body.len()));
    }
    head.push_str("\r\n");
    let mut request: Vec<u8> = head.into_bytes();
    request.extend_from_slice(body);

    // GET-OR-CREATE FROM POOL + read the HEAD, with the stale-pool retry living in
    // the error CLASSIFICATION (not a fork): a Closed pooled connection reconnects
    // and retries the SAME request ONCE; a Timeout/Other propagates. The connection
    // is taken OUT of the pool before use, so any error path drops it (never pooled)
    // and the worker is freed. This whole step ends at the HEAD — no body byte has
    // reached the client yet — so a retry here is safe and an error here can still
    // be a clean buffered 504/502.
    let (mut upstream_stream, head) = match pool.take(&host, port) {
        Some(mut pooled) => {
            let carry = std::mem::take(&mut pooled.carry);
            match send_and_read_head(&mut pooled.stream, &request, carry) {
                Ok(h) => (pooled.stream, h),
                // ONLY a Closed (stale pooled connection) reconnects+retries once.
                Err(FanoutError::Closed(_)) => {
                    drop(pooled);
                    let mut fresh = match connect_upstream_with_timeout(&host, port) {
                        Ok(s) => s,
                        Err(e) => return emit_buffered_fanout_error(client, client_keep_alive, &e),
                    };
                    match send_and_read_head(&mut fresh, &request, Vec::new()) {
                        Ok(h) => (fresh, h),
                        Err(e) => return emit_buffered_fanout_error(client, client_keep_alive, &e),
                    }
                }
                // Timeout (hung upstream) or Other (bad head) — drop the connection
                // and emit a buffered 504/502; the client head is still unwritten.
                Err(e) => {
                    drop(pooled);
                    return emit_buffered_fanout_error(client, client_keep_alive, &e);
                }
            }
        }
        None => {
            // No pooled connection — open a fresh one (the first fan-out, or after a
            // non-reusable response dropped the previous connection).
            let mut fresh = match connect_upstream_with_timeout(&host, port) {
                Ok(s) => s,
                Err(e) => return emit_buffered_fanout_error(client, client_keep_alive, &e),
            };
            match send_and_read_head(&mut fresh, &request, Vec::new()) {
                Ok(h) => (fresh, h),
                Err(e) => return emit_buffered_fanout_error(client, client_keep_alive, &e),
            }
        }
    };

    // The head is in hand. Decide the CLIENT-hop framing + keep-alive, write the
    // client head, then PIPE the body. Close-framed/unframed bodies force the client
    // connection closed (no body-end marker but the close itself); Length/Chunked
    // self-delimit, so the client's own keep-alive intent is honored.
    let client_kept = match head.framing {
        ResponseFraming::Close => false,
        _ => client_keep_alive,
    };
    if write_response_head(
        client,
        &head.status,
        "fanout-python",
        client_kept,
        &head.content_type,
        &head.headers,
        &head.framing,
    )
    .is_err()
    {
        // The client is gone before the body even started — close the connection.
        return false;
    }

    // PIPE the body straight from the upstream to the client. The body never lands
    // in a buffer; only a fixed 64 KiB chunk moves at a time.
    let upstream_kept = head.upstream_keep_alive;
    match stream_body_to_client(
        &mut upstream_stream,
        client,
        &head.framing,
        &head.body_prefix,
    ) {
        Ok(outcome) => {
            // Pool the upstream connection IFF the body was Length-framed AND the
            // upstream kept it alive — exactly the old reuse rule, now decided after
            // the body has streamed rather than after it was buffered.
            if outcome.reusable && upstream_kept {
                pool.store(
                    &host,
                    port,
                    PooledConn {
                        stream: upstream_stream,
                        carry: outcome.leftover,
                    },
                );
            }
            client_kept
        }
        // A mid-body failure (upstream stalled/closed after the head went out). The
        // client head is already written, so this can't be a clean status — the
        // client connection closes and the client sees a truncated body, the honest
        // outcome. The upstream connection is dropped (not pooled).
        Err(_) => false,
    }
}

// Emit a small BUFFERED 504/502 to the client through the ONE emit shape, then
// return the client keep-alive verdict. Reachable ONLY while the client head is
// unwritten (a pre-body fan-out failure), so a clean framed error is still possible.
// A successful write keeps the client connection's intent (a 502 is a complete,
// framed response — the connection can serve more); a failed write closes it.
fn emit_buffered_fanout_error(
    client: &mut TcpStream,
    client_keep_alive: ClientKeepAlive,
    err: &FanoutError,
) -> ClientKeepAlive {
    let (status, body) = fanout_error_response(err);
    if client
        .write_all(
            http_response(&status, &body, "fanout-python", client_keep_alive, "", &[]).as_bytes(),
        )
        .is_err()
    {
        return false;
    }
    client_keep_alive
}

fn parse_http_upstream(upstream: &str) -> Result<(String, u16, String), String> {
    let rest = upstream
        .strip_prefix("http://")
        .ok_or_else(|| "only http:// upstream URLs are supported".to_string())?;
    let (host_port, path) = match rest.split_once('/') {
        Some((hp, p)) => (hp, format!("/{}", p.trim_end_matches('/'))),
        None => (rest, String::new()),
    };
    if host_port.is_empty() {
        return Err("upstream host is empty".to_string());
    }
    let (host, port) = match host_port.rsplit_once(':') {
        Some((h, p)) => {
            let port = p
                .parse::<u16>()
                .map_err(|_| format!("bad upstream port: {}", p))?;
            (h.to_string(), port)
        }
        None => (host_port.to_string(), 80),
    };
    if host.is_empty() {
        return Err("upstream host is empty".to_string());
    }
    Ok((host, port, path))
}

fn cli_list(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust list <library.json>");
        return 2;
    }
    let path = &args[0];
    let bytes = match fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("read {}: {}", path, e);
            return 1;
        }
    };
    let lib: serde_json::Value = match serde_json::from_str(&bytes) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("parse {}: {}", path, e);
            return 1;
        }
    };
    let meta = &lib["library_meta"];
    println!(
        "library: {}  v{}",
        meta["name"].as_str().unwrap_or("?"),
        meta["version"].as_str().unwrap_or("?")
    );
    println!("  path: {}", path);
    if let Some(langs) = lib["language_cells"].as_array() {
        let names: Vec<String> = langs
            .iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect();
        println!("  language_cells: {}", names.join(", "));
    }
    let recipes = lib["recipes"].as_array().cloned().unwrap_or_default();
    println!("  recipes ({}):", recipes.len());
    for r in &recipes {
        let name = r["name"].as_str().unwrap_or("?");
        let bp = &r["blueprint"];
        let in_types: Vec<String> = bp["input_types"]
            .as_array()
            .map(|a| {
                a.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        let out_type = bp["output_type"].as_str().unwrap_or("?");
        let hint = r["node_id_hint"].as_str().unwrap_or("?");
        // Check if a .fk variant exists in the recipes/ directory
        let fk_path = format!("{}/{}.fk", RECIPES_DIR, name);
        let runnable = std::path::Path::new(&fk_path).exists();
        let marker = if runnable { "▶" } else { "·" };
        println!(
            "    {} {:<18} ({}) → {}  @recipe({})",
            marker,
            name,
            in_types.join(", "),
            out_type,
            hint
        );
    }
    0
}

fn cli_execute(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: form-kernel-rust execute <library.json> <recipe> [arg-json ...]");
        return 2;
    }
    let library_path = &args[0];
    let recipe_name = &args[1];
    let call_args = &args[2..];

    // Verify the recipe exists in the library (for the @recipe() hint)
    let lib_bytes = match fs::read_to_string(library_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("read {}: {}", library_path, e);
            return 1;
        }
    };
    let lib: serde_json::Value = match serde_json::from_str(&lib_bytes) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("parse {}: {}", library_path, e);
            return 1;
        }
    };
    let found = lib["recipes"]
        .as_array()
        .map(|rs| {
            rs.iter()
                .any(|r| r["name"].as_str() == Some(recipe_name.as_str()))
        })
        .unwrap_or(false);
    if !found {
        eprintln!("recipe '{}' not in library {}", recipe_name, library_path);
        return 2;
    }

    // Load the .fk implementation. Today recipes live in
    // form/form-kernel-rust/recipes/<name>.fk — hand-authored
    // until the Form→fk auto-generator lands. Honest GAP-NK1.
    let fk_path = format!("{}/{}.fk", RECIPES_DIR, recipe_name);
    let fk_src = match fs::read_to_string(&fk_path) {
        Ok(s) => s,
        Err(_) => {
            eprintln!(
                "form-kernel-rust: no .fk implementation for '{}'.

The library declares the recipe; the Rust kernel needs an .fk source.
Expected at: {}
Today these are hand-authored. The Form→fk auto-generator (consuming
tongue_caches.form from the library and emitting S-expression source)
is named in lc-native-kernel-binary as the next breath.",
                recipe_name, fk_path
            );
            return 2;
        }
    };

    // Build a call expression that wraps the recipe definition + invocation.
    // Convention: the .fk file defines the recipe with `(defn recipe_name ...)`;
    // we append a call form using the JSON-parsed args.
    let mut argv_form = String::new();
    for a in call_args {
        // Each arg is JSON; convert to .fk syntax.
        let v: serde_json::Value = match serde_json::from_str(a) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("parse arg {:?}: {}", a, e);
                return 2;
            }
        };
        argv_form.push(' ');
        argv_form.push_str(&json_to_fk(&v));
    }
    let full_src = format!("{}\n({}{})", fk_src, recipe_name, argv_form);

    let value = run_source(&full_src);
    println!("{}", value.display());
    0
}

fn json_to_fk(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::Null => "null".to_string(),
        serde_json::Value::Bool(b) => {
            if *b {
                "true".to_string()
            } else {
                "false".to_string()
            }
        }
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => format!("{:?}", s),
        serde_json::Value::Array(xs) => {
            let parts: Vec<String> = xs.iter().map(json_to_fk).collect();
            format!("(list {})", parts.join(" "))
        }
        serde_json::Value::Object(_) => {
            // Object → list-of-pairs would need a per-recipe convention;
            // honest about the gap for now.
            "null".to_string()
        }
    }
}

fn cli_query(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust query <path>");
        return 2;
    }
    let path = &args[0];
    let text = match fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("read {}: {}", path, e);
            return 1;
        }
    };

    let lang = if path.ends_with(".json") || path.ends_with(".recipelib.json") {
        "json"
    } else if path.ends_with(".fk") {
        "fk"
    } else {
        "raw"
    };

    let tree = match lang {
        "json" => match serde_json::from_str::<serde_json::Value>(&text) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("parse {}: {}", path, e);
                return 1;
            }
        },
        "fk" => {
            // Parse via the kernel's reader, return a structural sketch.
            // Full Form-object tree requires walking by_id with categories;
            // a flat sketch is the first move.
            let toks = tokenize_sexp(&text);
            let mut k = Kernel::new();
            let (root, _) = read_sexp(&mut k, &toks, 0);
            serde_json::json!({
                "source_tongue": "fk",
                "source_path":   path,
                "root_node_id":  format!("{}.{}.{}.{}", root.pkg, root.level, root.ty, root.inst),
                "node_count":    k.by_id.len(),
                "string_count":  k.strs.len(),
            })
        }
        _ => serde_json::json!({
            "source_tongue": "raw",
            "source_path":   path,
            "bytes":         text.len(),
            "lines":         text.lines().count(),
            "note":          "no Language cell wired for this extension yet",
        }),
    };
    println!("{}", serde_json::to_string_pretty(&tree).unwrap());
    0
}

fn cli_trace(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust trace [--expr \"...\" | <file.fk>]");
        return 2;
    }
    let src = if args[0] == "--expr" {
        if args.len() < 2 {
            eprintln!("--expr requires an argument");
            return 2;
        }
        args[1].clone()
    } else {
        match fs::read_to_string(&args[0]) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("read {}: {}", args[0], e);
                return 1;
            }
        }
    };
    set_crash_trace_context("trace", args, Some(&src));

    let start = Instant::now();
    let (value, trace) = run_source_traced(&src);
    let elapsed = start.elapsed();

    let report = serde_json::json!({
        "result":            value.display(),
        "elapsed_us":        elapsed.as_micros(),
        "elapsed_human":     format!("{:?}", elapsed),
        "trace":             trace.to_json(),
    });
    println!("{}", serde_json::to_string_pretty(&report).unwrap());
    0
}

fn cli_fetch(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust fetch <url>");
        return 2;
    }
    let url = &args[0];
    match ureq::get(url).call() {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.into_string().unwrap_or_default();
            let report = serde_json::json!({
                "url":     url,
                "status":  status,
                "body":    body,
                "bytes":   body.len(),
            });
            println!("{}", serde_json::to_string_pretty(&report).unwrap());
            0
        }
        Err(e) => {
            eprintln!("fetch {}: {}", url, e);
            1
        }
    }
}

fn cli_run(args: &[String]) -> i32 {
    let mut stdlib_dir: String = "form-stdlib".to_string();
    let mut paths: Vec<String> = Vec::new();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--stdlib" => {
                if i + 1 >= args.len() {
                    eprintln!("run: --stdlib requires a directory argument");
                    return 2;
                }
                stdlib_dir = args[i + 1].clone();
                i += 2;
            }
            other => {
                paths.push(other.to_string());
                i += 1;
            }
        }
    }
    if paths.is_empty() {
        eprintln!("usage: form-kernel-rust run [--stdlib <dir>] <file.fk> [more.fk ...]");
        return 2;
    }
    set_crash_trace_context("run", args, None);
    let mut prog = match source_compile_file_workload_recipe_object(&paths, &stdlib_dir) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("run: {}", e);
            return 1;
        }
    };
    let value = execute_root(&mut prog.kernel, prog.root);
    println!("{}", value.display());
    0
}

fn cli_binary(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: form-kernel-rust --binary <file.fkb>");
        return 2;
    }
    set_crash_trace_context("binary", args, None);
    let bytes = match fs::read(&args[0]) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("read {}: {}", args[0], e);
            return 1;
        }
    };
    let mut k = Kernel::new();
    let root = match deserialize_artifact(&mut k, &bytes) {
        Ok(root) => root,
        Err(e) => {
            eprintln!("form-kernel-rust: {}", e);
            return 1;
        }
    };
    let value = execute_root(&mut k, root);
    println!("{}", value.display());
    0
}

fn cli_emit_binary(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: form-kernel-rust --emit-binary <out.fkb> <file.fk> [more.fk ...]");
        return 2;
    }
    let mut parts = Vec::new();
    for path in &args[1..] {
        match fs::read_to_string(path) {
            Ok(s) => parts.push(s),
            Err(e) => {
                eprintln!("read {}: {}", path, e);
                return 1;
            }
        }
    }
    let src = parts.join("\n");
    set_crash_trace_context("emit-binary", args, Some(&src));
    let mut k = Kernel::new();
    let root = read_root_from_source(&mut k, &src);
    let bytes = serialize_artifact(&k, root);
    if let Err(e) = fs::write(&args[0], bytes) {
        eprintln!("write {}: {}", args[0], e);
        return 1;
    }
    0
}

fn install_panic_hook() {
    // Override Rust's default panic handler so Form authors see a clean
    // "parse error at line X col Y: ..." message instead of Rust's internal
    // backtrace. Kernel devs can set RUST_BACKTRACE=1 to get the full
    // story when debugging the kernel itself.
    std::panic::set_hook(Box::new(|info| {
        let msg = info
            .payload()
            .downcast_ref::<String>()
            .map(|s| s.as_str())
            .or_else(|| info.payload().downcast_ref::<&str>().copied())
            .unwrap_or("unknown error");
        let diagnosis = diagnose_kernel_panic(msg);
        eprintln!("form-kernel-rust: fatal[{}]: {}", diagnosis.fatal_kind, msg);
        eprintln!(
            "form-kernel-rust: likely root cause: {}",
            diagnosis.likely_root_cause
        );
        eprintln!("form-kernel-rust: avoidance: {}", diagnosis.avoidance);
        let location = info
            .location()
            .map(|loc| format!("{}:{}:{}", loc.file(), loc.line(), loc.column()));
        if let Some(path) = write_kernel_crash_trace(msg, location) {
            eprintln!("form-kernel-rust: crash trace: {}", path.display());
        }
    }));
}

#[cfg(test)]
mod crash_diagnostics_tests {
    use super::*;

    #[test]
    fn diagnose_null_string_contract_as_type_violation() {
        let diagnosis = diagnose_kernel_panic("as_str: Null");
        assert_eq!(diagnosis.fatal_kind, "type_contract_violation");
        assert!(diagnosis.likely_root_cause.contains("non-string"));
        assert!(diagnosis.avoidance.contains("value_kind"));
    }

    #[test]
    fn crash_trace_records_diagnosis_source_and_operation() {
        set_thread_crash_trace_context(CrashTraceContext {
            mode: "serve-handler".to_string(),
            args: vec![
                "serve".to_string(),
                "--routes".to_string(),
                "test-routes.fk".to_string(),
            ],
            source: "(defn route () (str_concat null \"x\"))".to_string(),
            source_label: "test-routes.fk".to_string(),
            operation: "worker=7 request=GET /boom route=/boom handler=route".to_string(),
        });
        let path = write_kernel_crash_trace(
            "as_str: Null",
            Some("form/form-kernel-rust/src/main.rs:1:1".to_string()),
        )
        .expect("trace path");
        let body = fs::read_to_string(&path).expect("trace body");
        let json: serde_json::Value = serde_json::from_str(&body).expect("trace json");
        assert_eq!(json["fatal_kind"], "type_contract_violation");
        assert_eq!(json["source_label"], "test-routes.fk");
        assert_eq!(
            json["operation"],
            "worker=7 request=GET /boom route=/boom handler=route"
        );
        assert!(json["likely_root_cause"]
            .as_str()
            .unwrap_or("")
            .contains("non-string"));
        set_thread_crash_trace_context(CrashTraceContext::default());
        let _ = fs::remove_file(path);
    }
}

fn main_with_args(args: Vec<String>) -> i32 {
    set_crash_trace_context("startup", &args, None);
    if args.is_empty() {
        cli_help();
        return 2;
    }

    match args[0].as_str() {
        "--help" | "help" => {
            cli_help();
            0
        }
        "--bench" => {
            run_bench();
            0
        }
        "--numeric-bench" => {
            formats::run_numeric_bench();
            0
        }
        "--binary" => cli_binary(&args[1..]),
        "--emit-binary" => cli_emit_binary(&args[1..]),
        "list" => cli_list(&args[1..]),
        "execute" => cli_execute(&args[1..]),
        "query" => cli_query(&args[1..]),
        "trace" => cli_trace(&args[1..]),
        "fetch" => cli_fetch(&args[1..]),
        "run" => cli_run(&args[1..]),
        "serve" => cli_serve(&args[1..]),
        "check" => cli_check(&args[1..]),
        _ => {
            // Source adapter: --expr or <file.fk> [more.fk ...]
            let src = if args[0] == "--expr" {
                if args.len() < 2 {
                    eprintln!("--expr requires an argument");
                    std::process::exit(2);
                }
                args[1].clone()
            } else {
                let mut parts = Vec::with_capacity(args.len());
                for path in &args {
                    match fs::read_to_string(path) {
                        Ok(s) => parts.push(s),
                        Err(e) => {
                            eprintln!("read {}: {}", path, e);
                            std::process::exit(1);
                        }
                    }
                }
                parts.join("\n")
            };
            let mode = if args[0] == "--expr" {
                "expr"
            } else {
                "source"
            };
            set_crash_trace_context(mode, &args, Some(&src));
            let result = run_source(&src);
            println!("{}", result.display());
            0
        }
    }
}

fn main() {
    install_panic_hook();

    let args: Vec<String> = env::args().skip(1).collect();
    let handle = std::thread::Builder::new()
        .name("form-kernel-rust".to_string())
        .stack_size(form_kernel_stack_bytes())
        .spawn(move || main_with_args(args))
        .unwrap_or_else(|e| {
            eprintln!("form-kernel-rust: failed to start execution worker: {}", e);
            std::process::exit(1);
        });
    let exit_code = match handle.join() {
        Ok(code) => code,
        Err(_) => 1,
    };
    std::process::exit(exit_code);
}

// ---------------------------------------------------------------------------
// Form binary artifact format
// ---------------------------------------------------------------------------
// Each node record is tagged. Leaves store their local 4-tuple value.
// Composites store the full category node followed by children. That keeps
// temporary, unregistered blueprint/recipe categories scoped to the artifact
// shape instead of treating their context-local NodeID numbers as global.

fn push_u32(bytes: &mut Vec<u8>, v: u32) {
    bytes.push((v >> 24) as u8);
    bytes.push((v >> 16) as u8);
    bytes.push((v >> 8) as u8);
    bytes.push(v as u8);
}

fn read_u32(bytes: &[u8], pos: usize) -> (u32, usize) {
    let v = ((bytes[pos] as u32) << 24)
        | ((bytes[pos + 1] as u32) << 16)
        | ((bytes[pos + 2] as u32) << 8)
        | (bytes[pos + 3] as u32);
    (v, pos + 4)
}

// read_f64_le — 8-byte IEEE-754 little-endian f64, the payload of a
// FORM_BINARY_FLOAT64 node. Sibling parity with Go/TS little-endian readers.
fn read_f64_le(bytes: &[u8], pos: usize) -> (f64, usize) {
    let mut buf = [0u8; 8];
    buf.copy_from_slice(&bytes[pos..pos + 8]);
    (f64::from_le_bytes(buf), pos + 8)
}

const FORM_BINARY_LEAF: u32 = 0;
const FORM_BINARY_COMPOSITE: u32 = 1;
// FLOAT64 carries its VALUE, not its index. A float64 trivial NodeID's `inst`
// is a per-kernel f64s-table index — meaningless in another kernel. So a float
// node serializes as [FORM_BINARY_FLOAT64][8 bytes IEEE-754 little-endian] and
// each kernel re-interns the value on read (fresh local index). The trivial
// float `ty` numbering is aligned three-way (FLOAT64 = 7 across Rust/Go/TS),
// and it never rides the wire anyway: the value, not the index nor the local
// type-tag, travels in bytes, so the .fkb stays portable by construction.
const FORM_BINARY_FLOAT64: u32 = 2;

fn serialize_nid(k: &Kernel, nid: NodeID, bytes: &mut Vec<u8>) {
    if let Some(recipe) = k.by_id.get(&nid) {
        push_u32(bytes, FORM_BINARY_COMPOSITE);
        serialize_nid(k, recipe.category, bytes);
        push_u32(bytes, recipe.children.len() as u32);
        for &c in &recipe.children {
            serialize_nid(k, c, bytes);
        }
    } else if nid.level == LEVEL_TRIVIAL && nid.ty == TRIV_FLOAT64 {
        push_u32(bytes, FORM_BINARY_FLOAT64);
        bytes.extend_from_slice(&k.decode_float64(nid.inst).to_le_bytes());
    } else {
        push_u32(bytes, FORM_BINARY_LEAF);
        push_u32(bytes, nid.pkg);
        push_u32(bytes, nid.level);
        push_u32(bytes, nid.ty);
        push_u32(bytes, nid.inst);
    }
}

fn deserialize_nid(k: &mut Kernel, bytes: &[u8], pos: usize, scope: u32) -> (NodeID, usize) {
    let (tag, p) = read_u32(bytes, pos);
    if tag == FORM_BINARY_FLOAT64 {
        let (value, p) = read_f64_le(bytes, p);
        return (k.intern_trivial_float64(value), p);
    }
    if tag == FORM_BINARY_LEAF {
        let (pkg, p) = read_u32(bytes, p);
        let (level, p) = read_u32(bytes, p);
        let (ty, p) = read_u32(bytes, p);
        let (inst, p) = read_u32(bytes, p);
        return (
            k.remap_imported_leaf(
                scope,
                NodeID {
                    pkg,
                    level,
                    ty,
                    inst,
                },
            ),
            p,
        );
    }
    let (category, p) = deserialize_nid(k, bytes, p, scope);
    let (count, mut p) = read_u32(bytes, p);
    let mut children = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let (c, np) = deserialize_nid(k, bytes, p, scope);
        children.push(c);
        p = np;
    }
    (k.intern(category, children), p)
}

const FORM_BINARY_MAGIC_V1: &[u8] = b"FORMBIN1";
const FORM_BINARY_MAGIC: &[u8] = b"FORMBIN2";

fn serialize_artifact(k: &Kernel, root: NodeID) -> Vec<u8> {
    let mut bytes = FORM_BINARY_MAGIC.to_vec();
    push_u32(&mut bytes, k.strs.len() as u32);
    for s in &k.strs {
        let raw = s.as_bytes();
        push_u32(&mut bytes, raw.len() as u32);
        bytes.extend_from_slice(raw);
    }
    serialize_nid(k, root, &mut bytes);
    bytes
}

fn deserialize_artifact(k: &mut Kernel, bytes: &[u8]) -> Result<NodeID, String> {
    let is_v1 = bytes.len() >= FORM_BINARY_MAGIC_V1.len()
        && &bytes[..FORM_BINARY_MAGIC_V1.len()] == FORM_BINARY_MAGIC_V1;
    let is_v2 = bytes.len() >= FORM_BINARY_MAGIC.len()
        && &bytes[..FORM_BINARY_MAGIC.len()] == FORM_BINARY_MAGIC;
    if !is_v1 && !is_v2 {
        return Err("form binary: bad magic".to_string());
    }
    let mut pos = if is_v1 {
        FORM_BINARY_MAGIC_V1.len()
    } else {
        FORM_BINARY_MAGIC.len()
    };
    let (string_count, p) = read_u32(bytes, pos);
    pos = p;
    let mut strings = Vec::with_capacity(string_count as usize);
    for _ in 0..string_count {
        let (len, p) = read_u32(bytes, pos);
        pos = p;
        let end = pos + len as usize;
        if end > bytes.len() {
            return Err("form binary: truncated string".to_string());
        }
        let value = std::str::from_utf8(&bytes[pos..end])
            .map_err(|e| format!("form binary: invalid utf8: {}", e))?
            .to_string();
        strings.push(value);
        pos = end;
    }
    let scope = k.next_import_scope();
    let (root, end) = if is_v1 {
        deserialize_nid_with_strings_v1(k, bytes, pos, &strings, scope)?
    } else {
        deserialize_nid_with_strings(k, bytes, pos, &strings, scope)?
    };
    if end != bytes.len() {
        return Err("form binary: trailing bytes".to_string());
    }
    Ok(root)
}

fn deserialize_nid_with_strings(
    k: &mut Kernel,
    bytes: &[u8],
    pos: usize,
    strings: &[String],
    scope: u32,
) -> Result<(NodeID, usize), String> {
    let (tag, p) = read_u32(bytes, pos);
    if tag == FORM_BINARY_FLOAT64 {
        if p + 8 > bytes.len() {
            return Err("form binary: truncated float64".to_string());
        }
        let (value, p) = read_f64_le(bytes, p);
        return Ok((k.intern_trivial_float64(value), p));
    }
    if tag == FORM_BINARY_LEAF {
        let (pkg, p) = read_u32(bytes, p);
        let (level, p) = read_u32(bytes, p);
        let (ty, p) = read_u32(bytes, p);
        let (inst, p) = read_u32(bytes, p);
        if level == LEVEL_TRIVIAL && ty == TRIV_STRING {
            let value = strings
                .get(inst as usize)
                .ok_or_else(|| format!("form binary: bad string index {}", inst))?;
            return Ok((k.intern_string(value), p));
        }
        return Ok((
            k.remap_imported_leaf(
                scope,
                NodeID {
                    pkg,
                    level,
                    ty,
                    inst,
                },
            ),
            p,
        ));
    }
    let (category, p) = deserialize_nid_with_strings(k, bytes, p, strings, scope)?;
    let (count, mut p) = read_u32(bytes, p);
    let mut children = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let (c, np) = deserialize_nid_with_strings(k, bytes, p, strings, scope)?;
        children.push(c);
        p = np;
    }
    Ok((k.intern(category, children), p))
}

fn deserialize_nid_with_strings_v1(
    k: &mut Kernel,
    bytes: &[u8],
    pos: usize,
    strings: &[String],
    scope: u32,
) -> Result<(NodeID, usize), String> {
    let (pkg, p) = read_u32(bytes, pos);
    let (level, p) = read_u32(bytes, p);
    let (ty, p) = read_u32(bytes, p);
    let (inst, p) = read_u32(bytes, p);
    let (count, mut p) = read_u32(bytes, p);
    if count == 0 {
        if level == LEVEL_TRIVIAL && ty == TRIV_STRING {
            let value = strings
                .get(inst as usize)
                .ok_or_else(|| format!("form binary: bad string index {}", inst))?;
            return Ok((k.intern_string(value), p));
        }
        return Ok((
            k.remap_imported_leaf(
                scope,
                NodeID {
                    pkg,
                    level,
                    ty,
                    inst,
                },
            ),
            p,
        ));
    }
    let category = if level == LEVEL_TRIVIAL && ty == TRIV_STRING {
        let value = strings
            .get(inst as usize)
            .ok_or_else(|| format!("form binary: bad string index {}", inst))?;
        k.intern_string(value)
    } else {
        NodeID {
            pkg,
            level,
            ty,
            inst,
        }
    };
    let mut children = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let (c, np) = deserialize_nid_with_strings_v1(k, bytes, p, strings, scope)?;
        children.push(c);
        p = np;
    }
    Ok((k.intern(category, children), p))
}
