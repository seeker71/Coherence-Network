//! Minimal Rust runner for shared Form conformance vectors.

use serde_json::{json, Map, Value};
use std::collections::HashMap;
use std::env;
use std::fs;

#[derive(Default)]
struct State {
    questions: HashMap<String, Value>,
    events: Vec<Value>,
    next_question: usize,
    next_event: usize,
}

impl State {
    fn create_question(
        &mut self,
        agent_id: String,
        question: String,
        choices: Vec<String>,
        context: Map<String, Value>,
    ) -> Value {
        self.next_question += 1;
        let id = format!("question_rust_{:04}", self.next_question);
        let task_id = context
            .get("task_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let thread_id = context
            .get("thread_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let item = json!({
            "id": id,
            "agent_id": agent_id,
            "question": question,
            "task_id": task_id,
            "thread_id": thread_id,
            "choices": choices,
            "context": Value::Object(context),
            "status": "open",
            "answer": Value::Null,
            "answered_by": Value::Null
        });
        self.questions.insert(
            item["id"].as_str().unwrap_or_default().to_string(),
            item.clone(),
        );
        self.emit("question_opened", &item);
        item
    }

    fn answer_question(
        &mut self,
        question_id: &str,
        answer: &str,
        answered_by: &str,
    ) -> Result<(), String> {
        let item = self
            .questions
            .get_mut(question_id)
            .ok_or_else(|| format!("question {question_id:?} not found"))?;
        item["answer"] = Value::String(answer.to_string());
        item["answered_by"] = Value::String(answered_by.to_string());
        item["status"] = Value::String("answered".to_string());
        let cloned = item.clone();
        self.emit("question_answered", &cloned);
        Ok(())
    }

    fn emit(&mut self, event_type: &str, question: &Value) {
        self.next_event += 1;
        self.events.push(json!({
            "id": format!("event_rust_{:04}", self.next_event),
            "sequence": self.next_event,
            "event_type": event_type,
            "question_id": question["id"],
            "question": question
        }));
    }

    fn await_answer(&self, question_id: &str) -> Result<Value, String> {
        let item = self
            .questions
            .get(question_id)
            .ok_or_else(|| format!("question {question_id:?} not found"))?;
        Ok(item.get("answer").cloned().unwrap_or(Value::Null))
    }
}

fn split_args(input: &str) -> Vec<String> {
    let mut args = Vec::new();
    let mut current = String::new();
    let mut in_string = false;
    let mut escape = false;
    let mut square_depth = 0;
    let mut brace_depth = 0;
    for ch in input.chars() {
        if escape {
            current.push(ch);
            escape = false;
            continue;
        }
        if ch == '\\' && in_string {
            current.push(ch);
            escape = true;
            continue;
        }
        if ch == '"' {
            in_string = !in_string;
            current.push(ch);
            continue;
        }
        if !in_string {
            match ch {
                '[' => square_depth += 1,
                ']' => square_depth -= 1,
                '{' => brace_depth += 1,
                '}' => brace_depth -= 1,
                ',' if square_depth == 0 && brace_depth == 0 => {
                    args.push(current.trim().to_string());
                    current.clear();
                    continue;
                }
                _ => {}
            }
        }
        current.push(ch);
    }
    if !current.trim().is_empty() {
        args.push(current.trim().to_string());
    }
    args
}

fn parse_string(raw: &str) -> Result<String, String> {
    serde_json::from_str::<String>(raw.trim())
        .map_err(|err| format!("invalid string {raw:?}: {err}"))
}

fn parse_array(raw: &str) -> Result<Vec<Value>, String> {
    let text = raw.trim();
    if text == "[]" {
        return Ok(Vec::new());
    }
    if !text.starts_with('[') || !text.ends_with(']') {
        return Err(format!("invalid list {raw:?}"));
    }
    let inner = &text[1..text.len() - 1];
    split_args(inner)
        .into_iter()
        .map(|item| parse_value(&item))
        .collect()
}

fn parse_object(raw: &str) -> Result<Map<String, Value>, String> {
    let text = raw.trim();
    let mut out = Map::new();
    if text == "{}" {
        return Ok(out);
    }
    if !text.starts_with('{') || !text.ends_with('}') {
        return Err(format!("invalid context {raw:?}"));
    }
    let inner = &text[1..text.len() - 1];
    for pair in split_args(inner) {
        let (key, value) = pair
            .split_once(':')
            .ok_or_else(|| format!("invalid context pair {pair:?}"))?;
        let key = key.trim().trim_matches('"').to_string();
        out.insert(key, parse_value(value.trim())?);
    }
    Ok(out)
}

fn parse_value(raw: &str) -> Result<Value, String> {
    let text = raw.trim();
    if text.starts_with('[') && text.ends_with(']') {
        return Ok(Value::Array(parse_array(text)?));
    }
    if text.starts_with('{') && text.ends_with('}') {
        return Ok(Value::Object(parse_object(text)?));
    }
    serde_json::from_str::<Value>(text).map_err(|err| format!("unsupported literal {raw:?}: {err}"))
}

fn call_body(form: &str, name: &str) -> Result<String, String> {
    let trimmed = form.trim();
    let prefix = format!("{name}(");
    if !trimmed.starts_with(&prefix) || !trimmed.ends_with(')') {
        return Err(format!("unsupported Form expression {form:?}"));
    }
    Ok(trimmed[prefix.len()..trimmed.len() - 1].to_string())
}

fn call_parts(form: &str) -> Result<(String, Vec<String>), String> {
    let trimmed = form.trim();
    let open = trimmed
        .find('(')
        .ok_or_else(|| format!("unsupported Form expression {form:?}"))?;
    if !trimmed.ends_with(')') {
        return Err(format!("unsupported Form expression {form:?}"));
    }
    let name = trimmed[..open].trim();
    if name.is_empty()
        || !name
            .chars()
            .all(|ch| ch == '_' || ch.is_ascii_alphanumeric())
    {
        return Err(format!("unsupported Form call {form:?}"));
    }
    let body = &trimmed[open + 1..trimmed.len() - 1];
    Ok((name.to_string(), split_args(body)))
}

fn value_as_array(value: &Value, name: &str) -> Result<Vec<Value>, String> {
    value
        .as_array()
        .cloned()
        .ok_or_else(|| format!("{name} expects a list"))
}

fn value_as_i64(value: &Value, name: &str) -> Result<i64, String> {
    value
        .as_i64()
        .ok_or_else(|| format!("{name} expects integer values"))
}

fn eval_builtin(name: &str, args: Vec<Value>) -> Result<Value, String> {
    match name {
        "len" => {
            if args.len() != 1 {
                return Err(format!("len expects 1 arg, got {}", args.len()));
            }
            let n = match &args[0] {
                Value::Array(items) => items.len(),
                Value::Object(items) => items.len(),
                Value::String(text) => text.chars().count(),
                _ => return Err("len expects a list, object, or string".to_string()),
            };
            Ok(json!(n))
        }
        "head" => {
            if args.len() != 1 {
                return Err(format!("head expects 1 arg, got {}", args.len()));
            }
            let items = value_as_array(&args[0], "head")?;
            Ok(items.first().cloned().unwrap_or(Value::Null))
        }
        "tail" => {
            if args.len() != 1 {
                return Err(format!("tail expects 1 arg, got {}", args.len()));
            }
            let items = value_as_array(&args[0], "tail")?;
            Ok(Value::Array(items.into_iter().skip(1).collect()))
        }
        "sum" => {
            if args.len() != 1 {
                return Err(format!("sum expects 1 arg, got {}", args.len()));
            }
            let items = value_as_array(&args[0], "sum")?;
            let mut total = 0_i64;
            for item in &items {
                total += value_as_i64(item, "sum")?;
            }
            Ok(json!(total))
        }
        "concat" => {
            if args.len() != 2 {
                return Err(format!("concat expects 2 args, got {}", args.len()));
            }
            match (&args[0], &args[1]) {
                (Value::String(a), Value::String(b)) => Ok(Value::String(format!("{a}{b}"))),
                (Value::Array(a), Value::Array(b)) => {
                    let mut out = a.clone();
                    out.extend(b.clone());
                    Ok(Value::Array(out))
                }
                _ => Err("concat expects two strings or two lists".to_string()),
            }
        }
        "reverse" => {
            if args.len() != 1 {
                return Err(format!("reverse expects 1 arg, got {}", args.len()));
            }
            match &args[0] {
                Value::Array(items) => {
                    let mut out = items.clone();
                    out.reverse();
                    Ok(Value::Array(out))
                }
                Value::String(text) => Ok(Value::String(text.chars().rev().collect())),
                _ => Err("reverse expects a list or string".to_string()),
            }
        }
        _ => Err(format!("unsupported Form function {name:?}")),
    }
}

fn eval_form(state: &mut State, form: &str) -> Result<Value, String> {
    let trimmed = form.trim();
    if trimmed.starts_with("ask(") {
        let args = split_args(&call_body(trimmed, "ask")?);
        if args.len() < 2 || args.len() > 4 {
            return Err(format!("ask expects 2 to 4 args, got {}", args.len()));
        }
        let agent_id = parse_string(&args[0])?;
        let question = parse_string(&args[1])?;
        let choices = if args.len() >= 3 {
            parse_array(&args[2])?
                .into_iter()
                .map(|value| {
                    value
                        .as_str()
                        .map(str::to_string)
                        .ok_or_else(|| "ask choices must be strings".to_string())
                })
                .collect::<Result<Vec<_>, _>>()?
        } else {
            Vec::new()
        };
        let context = if args.len() >= 4 {
            parse_object(&args[3])?
        } else {
            Map::new()
        };
        return Ok(state.create_question(agent_id, question, choices, context));
    }
    if trimmed.starts_with("await_answer(") {
        let args = split_args(&call_body(trimmed, "await_answer")?);
        if args.len() != 1 {
            return Err(format!("await_answer expects 1 arg, got {}", args.len()));
        }
        let question_id = parse_string(&args[0])?;
        return state.await_answer(&question_id);
    }
    let (name, raw_args) = call_parts(trimmed)?;
    let args = raw_args
        .into_iter()
        .map(|arg| parse_value(&arg))
        .collect::<Result<Vec<_>, _>>()?;
    eval_builtin(&name, args)
}

fn run_case(case: &Value) -> Result<Value, String> {
    let mut state = State::default();
    let mut question_id = String::new();
    if let Some(setup) = case.get("setup") {
        if let Some(open_form) = setup.get("open_question_form").and_then(Value::as_str) {
            let opened = eval_form(&mut state, open_form)?;
            question_id = opened["id"].as_str().unwrap_or_default().to_string();
            if let Some(answer) = setup.get("answer").and_then(Value::as_str) {
                let answered_by = setup
                    .get("answered_by")
                    .and_then(Value::as_str)
                    .unwrap_or("conformance");
                state.answer_question(&question_id, answer, answered_by)?;
            }
        }
    }
    let form = case["form"]
        .as_str()
        .ok_or_else(|| "case form must be a string".to_string())?
        .replace("${question_id}", &question_id);
    let value = eval_form(&mut state, &form)?;
    if question_id.is_empty() {
        question_id = value["id"].as_str().unwrap_or_default().to_string();
    }
    Ok(json!({
        "name": case["name"],
        "question_id": question_id,
        "value": value,
        "events": state.events
    }))
}

fn main() -> Result<(), String> {
    let vector_path = env::args()
        .nth(1)
        .ok_or_else(|| "usage: form-question-kernel <vector.json>".to_string())?;
    let text = fs::read_to_string(vector_path).map_err(|err| err.to_string())?;
    let vector: Value = serde_json::from_str(&text).map_err(|err| err.to_string())?;
    let cases = vector["cases"]
        .as_array()
        .ok_or_else(|| "vector cases must be an array".to_string())?
        .iter()
        .map(run_case)
        .collect::<Result<Vec<_>, _>>()?;
    println!(
        "{}",
        json!({
            "kernel": "rust",
            "status": "pass",
            "cases": cases
        })
    );
    Ok(())
}
