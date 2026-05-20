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

type Env = Vec<HashMap<String, Value>>;

fn lookup_binding(env: &Env, name: &str) -> Option<Value> {
    env.iter().rev().find_map(|scope| scope.get(name).cloned())
}

fn assign_binding(env: &mut Env, name: &str, value: Value) -> Result<Value, String> {
    for scope in env.iter_mut().rev() {
        if scope.contains_key(name) {
            scope.insert(name.to_string(), value.clone());
            return Ok(value);
        }
    }
    Err(format!("set {name:?} has no enclosing binding"))
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

fn split_top_level(input: &str, separator: char) -> Vec<String> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut in_string = false;
    let mut escape = false;
    let mut paren_depth = 0;
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
                '(' => paren_depth += 1,
                ')' => paren_depth -= 1,
                '[' => square_depth += 1,
                ']' => square_depth -= 1,
                '{' => brace_depth += 1,
                '}' => brace_depth -= 1,
                _ if ch == separator
                    && paren_depth == 0
                    && square_depth == 0
                    && brace_depth == 0 =>
                {
                    parts.push(current.trim().to_string());
                    current.clear();
                    continue;
                }
                _ => {}
            }
        }
        current.push(ch);
    }
    if !current.trim().is_empty() {
        parts.push(current.trim().to_string());
    }
    parts
}

fn find_top_level_keyword(input: &str, keyword: &str) -> Option<usize> {
    let mut in_string = false;
    let mut escape = false;
    let mut paren_depth = 0;
    let mut square_depth = 0;
    let mut brace_depth = 0;
    let mut positions = input.char_indices().peekable();
    while let Some((index, ch)) = positions.next() {
        if escape {
            escape = false;
            continue;
        }
        if ch == '\\' && in_string {
            escape = true;
            continue;
        }
        if ch == '"' {
            in_string = !in_string;
            continue;
        }
        if !in_string {
            match ch {
                '(' => paren_depth += 1,
                ')' => paren_depth -= 1,
                '[' => square_depth += 1,
                ']' => square_depth -= 1,
                '{' => brace_depth += 1,
                '}' => brace_depth -= 1,
                _ => {}
            }
            if paren_depth == 0
                && square_depth == 0
                && brace_depth == 0
                && input[index..].starts_with(keyword)
            {
                return Some(index);
            }
        }
    }
    None
}

fn split_head_body(input: &str) -> Result<(String, String), String> {
    let text = input.trim();
    if !text.ends_with('}') {
        return Err(format!("missing braced body in {input:?}"));
    }
    let mut in_string = false;
    let mut escape = false;
    let mut paren_depth = 0;
    let mut square_depth = 0;
    for (index, ch) in text.char_indices() {
        if escape {
            escape = false;
            continue;
        }
        if ch == '\\' && in_string {
            escape = true;
            continue;
        }
        if ch == '"' {
            in_string = !in_string;
            continue;
        }
        if in_string {
            continue;
        }
        match ch {
            '(' => paren_depth += 1,
            ')' => paren_depth -= 1,
            '[' => square_depth += 1,
            ']' => square_depth -= 1,
            '{' if paren_depth == 0 && square_depth == 0 => {
                let head = text[..index].trim().to_string();
                let body = text[index + 1..text.len() - 1].trim().to_string();
                return Ok((head, body));
            }
            _ => {}
        }
    }
    Err(format!("missing braced body in {input:?}"))
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

#[derive(Clone, Debug)]
enum ExprToken {
    Value(Value),
    Op(String),
    LParen,
    RParen,
}

fn tokenize_expr(input: &str, env: &Env) -> Result<Vec<ExprToken>, String> {
    let chars: Vec<char> = input.chars().collect();
    let mut tokens = Vec::new();
    let mut pos = 0;
    while pos < chars.len() {
        let ch = chars[pos];
        if ch.is_whitespace() {
            pos += 1;
            continue;
        }
        if ch == '"' {
            let start = pos;
            pos += 1;
            let mut escape = false;
            while pos < chars.len() {
                let current = chars[pos];
                if escape {
                    escape = false;
                } else if current == '\\' {
                    escape = true;
                } else if current == '"' {
                    pos += 1;
                    break;
                }
                pos += 1;
            }
            if pos > chars.len() || chars.get(pos.saturating_sub(1)) != Some(&'"') {
                return Err("unterminated string literal".to_string());
            }
            let raw: String = chars[start..pos].iter().collect();
            tokens.push(ExprToken::Value(Value::String(parse_string(&raw)?)));
            continue;
        }
        if ch.is_ascii_digit() {
            let start = pos;
            pos += 1;
            while pos < chars.len() && chars[pos].is_ascii_digit() {
                pos += 1;
            }
            let raw: String = chars[start..pos].iter().collect();
            let value = raw
                .parse::<i64>()
                .map_err(|err| format!("invalid integer {raw:?}: {err}"))?;
            tokens.push(ExprToken::Value(json!(value)));
            continue;
        }
        if ch.is_ascii_alphabetic() {
            let start = pos;
            pos += 1;
            while pos < chars.len() && (chars[pos].is_ascii_alphanumeric() || chars[pos] == '_') {
                pos += 1;
            }
            let raw: String = chars[start..pos].iter().collect();
            let value = match raw.as_str() {
                "true" => Value::Bool(true),
                "false" => Value::Bool(false),
                "null" => Value::Null,
                _ => lookup_binding(env, &raw)
                    .ok_or_else(|| format!("unsupported identifier {raw:?}"))?,
            };
            tokens.push(ExprToken::Value(value));
            continue;
        }
        if ch == '(' {
            tokens.push(ExprToken::LParen);
            pos += 1;
            continue;
        }
        if ch == ')' {
            tokens.push(ExprToken::RParen);
            pos += 1;
            continue;
        }
        if pos + 1 < chars.len() {
            let two: String = chars[pos..pos + 2].iter().collect();
            if matches!(two.as_str(), "==" | "!=" | "<=" | ">=" | "&&" | "||") {
                tokens.push(ExprToken::Op(two));
                pos += 2;
                continue;
            }
        }
        if matches!(ch, '+' | '-' | '*' | '/' | '%' | '<' | '>' | '!') {
            tokens.push(ExprToken::Op(ch.to_string()));
            pos += 1;
            continue;
        }
        return Err(format!("unsupported expression character {ch:?}"));
    }
    Ok(tokens)
}

struct ExprParser {
    tokens: Vec<ExprToken>,
    pos: usize,
}

impl ExprParser {
    fn parse(mut self) -> Result<Value, String> {
        let value = self.parse_or()?;
        if self.pos != self.tokens.len() {
            return Err(format!("unexpected token {:?}", self.tokens[self.pos]));
        }
        Ok(value)
    }

    fn peek_op(&self, op: &str) -> bool {
        matches!(self.tokens.get(self.pos), Some(ExprToken::Op(actual)) if actual == op)
    }

    fn take_op(&mut self, op: &str) -> bool {
        if self.peek_op(op) {
            self.pos += 1;
            return true;
        }
        false
    }

    fn parse_or(&mut self) -> Result<Value, String> {
        let mut left = self.parse_and()?;
        while self.take_op("||") {
            let right = self.parse_and()?;
            left = if truthy(&left) { left } else { right };
        }
        Ok(left)
    }

    fn parse_and(&mut self) -> Result<Value, String> {
        let mut left = self.parse_compare()?;
        while self.take_op("&&") {
            let right = self.parse_compare()?;
            left = if truthy(&left) { right } else { left };
        }
        Ok(left)
    }

    fn parse_compare(&mut self) -> Result<Value, String> {
        let mut left = self.parse_add()?;
        loop {
            let op = match self.tokens.get(self.pos) {
                Some(ExprToken::Op(op))
                    if matches!(op.as_str(), "==" | "!=" | "<" | "<=" | ">" | ">=") =>
                {
                    op.clone()
                }
                _ => break,
            };
            self.pos += 1;
            let right = self.parse_add()?;
            left = apply_compare(&op, &left, &right)?;
        }
        Ok(left)
    }

    fn parse_add(&mut self) -> Result<Value, String> {
        let mut left = self.parse_mul()?;
        loop {
            if self.take_op("+") {
                let right = self.parse_mul()?;
                left = apply_numeric("+", &left, &right)?;
            } else if self.take_op("-") {
                let right = self.parse_mul()?;
                left = apply_numeric("-", &left, &right)?;
            } else {
                break;
            }
        }
        Ok(left)
    }

    fn parse_mul(&mut self) -> Result<Value, String> {
        let mut left = self.parse_unary()?;
        loop {
            if self.take_op("*") {
                let right = self.parse_unary()?;
                left = apply_numeric("*", &left, &right)?;
            } else if self.take_op("/") {
                let right = self.parse_unary()?;
                left = apply_numeric("/", &left, &right)?;
            } else if self.take_op("%") {
                let right = self.parse_unary()?;
                left = apply_numeric("%", &left, &right)?;
            } else {
                break;
            }
        }
        Ok(left)
    }

    fn parse_unary(&mut self) -> Result<Value, String> {
        if self.take_op("-") {
            return Ok(json!(-value_as_i64(&self.parse_unary()?, "unary -")?));
        }
        if self.take_op("!") {
            return Ok(Value::Bool(!truthy(&self.parse_unary()?)));
        }
        self.parse_primary()
    }

    fn parse_primary(&mut self) -> Result<Value, String> {
        match self.tokens.get(self.pos).cloned() {
            Some(ExprToken::Value(value)) => {
                self.pos += 1;
                Ok(value)
            }
            Some(ExprToken::LParen) => {
                self.pos += 1;
                let value = self.parse_or()?;
                match self.tokens.get(self.pos) {
                    Some(ExprToken::RParen) => {
                        self.pos += 1;
                        Ok(value)
                    }
                    _ => Err("missing closing ')'".to_string()),
                }
            }
            other => Err(format!(
                "expected literal or parenthesized expression, got {other:?}"
            )),
        }
    }
}

fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(item) => *item,
        Value::Number(item) => item.as_i64().unwrap_or(0) != 0,
        Value::String(item) => !item.is_empty(),
        Value::Array(item) => !item.is_empty(),
        Value::Object(item) => !item.is_empty(),
    }
}

fn apply_numeric(op: &str, left: &Value, right: &Value) -> Result<Value, String> {
    let a = value_as_i64(left, op)?;
    let b = value_as_i64(right, op)?;
    let value = match op {
        "+" => a + b,
        "-" => a - b,
        "*" => a * b,
        "/" => a / b,
        "%" => a % b,
        _ => return Err(format!("unsupported numeric op {op:?}")),
    };
    Ok(json!(value))
}

fn apply_compare(op: &str, left: &Value, right: &Value) -> Result<Value, String> {
    let value = match op {
        "==" => left == right,
        "!=" => left != right,
        "<" => value_as_i64(left, op)? < value_as_i64(right, op)?,
        "<=" => value_as_i64(left, op)? <= value_as_i64(right, op)?,
        ">" => value_as_i64(left, op)? > value_as_i64(right, op)?,
        ">=" => value_as_i64(left, op)? >= value_as_i64(right, op)?,
        _ => return Err(format!("unsupported comparison op {op:?}")),
    };
    Ok(Value::Bool(value))
}

fn eval_expression(form: &str, env: &Env) -> Result<Value, String> {
    ExprParser {
        tokens: tokenize_expr(form, env)?,
        pos: 0,
    }
    .parse()
}

fn eval_form(state: &mut State, form: &str) -> Result<Value, String> {
    let mut env = vec![HashMap::new()];
    eval_form_in(state, form, &mut env)
}

fn eval_if(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let rest = form
        .trim()
        .strip_prefix("if ")
        .ok_or_else(|| format!("invalid if expression {form:?}"))?;
    let then_pos = find_top_level_keyword(rest, " then ")
        .ok_or_else(|| format!("if expression missing then: {form:?}"))?;
    let cond_src = rest[..then_pos].trim();
    let after_then = &rest[then_pos + " then ".len()..];
    let (then_src, else_src) = match find_top_level_keyword(after_then, " else ") {
        Some(else_pos) => (
            after_then[..else_pos].trim(),
            Some(after_then[else_pos + " else ".len()..].trim()),
        ),
        None => (after_then.trim(), None),
    };
    if truthy(&eval_form_in(state, cond_src, env)?) {
        return eval_form_in(state, then_src, env);
    }
    match else_src {
        Some(src) => eval_form_in(state, src, env),
        None => Ok(Value::Null),
    }
}

fn eval_do(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let text = form.trim();
    let inner = text
        .strip_prefix("do")
        .map(str::trim)
        .and_then(|body| body.strip_prefix('{'))
        .and_then(|body| body.strip_suffix('}'))
        .ok_or_else(|| format!("invalid do block {form:?}"))?;
    env.push(HashMap::new());
    let result = eval_statements(state, inner, env)?;
    env.pop();
    Ok(result)
}

fn eval_let(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let rest = form
        .trim()
        .strip_prefix("let ")
        .ok_or_else(|| format!("invalid let expression {form:?}"))?;
    let (name, value_src) = rest
        .split_once('=')
        .ok_or_else(|| format!("let expression missing '=': {form:?}"))?;
    let name = name.trim();
    if name.is_empty()
        || !name
            .chars()
            .all(|ch| ch == '_' || ch.is_ascii_alphanumeric())
        || name.chars().next().is_some_and(|ch| ch.is_ascii_digit())
    {
        return Err(format!("invalid let binding name {name:?}"));
    }
    let value = eval_form_in(state, value_src.trim(), env)?;
    let scope = env
        .last_mut()
        .ok_or_else(|| "internal error: missing environment scope".to_string())?;
    scope.insert(name.to_string(), value.clone());
    Ok(value)
}

fn eval_set(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let rest = form
        .trim()
        .strip_prefix("set ")
        .ok_or_else(|| format!("invalid set expression {form:?}"))?;
    let (name, value_src) = rest
        .split_once('=')
        .ok_or_else(|| format!("set expression missing '=': {form:?}"))?;
    let name = name.trim();
    if name.is_empty()
        || !name
            .chars()
            .all(|ch| ch == '_' || ch.is_ascii_alphanumeric())
        || name.chars().next().is_some_and(|ch| ch.is_ascii_digit())
    {
        return Err(format!("invalid set binding name {name:?}"));
    }
    let value = eval_form_in(state, value_src.trim(), env)?;
    assign_binding(env, name, value)
}

fn eval_array(state: &mut State, form: &str, env: &mut Env) -> Result<Vec<Value>, String> {
    let text = form.trim();
    if text == "[]" {
        return Ok(Vec::new());
    }
    if !text.starts_with('[') || !text.ends_with(']') {
        return Err(format!("invalid list {form:?}"));
    }
    split_args(&text[1..text.len() - 1])
        .into_iter()
        .map(|item| eval_form_in(state, &item, env))
        .collect()
}

fn eval_statements(state: &mut State, body: &str, env: &mut Env) -> Result<Value, String> {
    let mut result = Value::Null;
    for stmt in split_top_level(body, ';') {
        result = eval_form_in(state, &stmt, env)?;
    }
    Ok(result)
}

fn eval_for(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let rest = form
        .trim()
        .strip_prefix("for ")
        .ok_or_else(|| format!("invalid for expression {form:?}"))?;
    let in_pos = find_top_level_keyword(rest, " in ")
        .ok_or_else(|| format!("for expression missing in: {form:?}"))?;
    let var_name = rest[..in_pos].trim();
    if var_name.is_empty()
        || !var_name
            .chars()
            .all(|ch| ch == '_' || ch.is_ascii_alphanumeric())
        || var_name
            .chars()
            .next()
            .is_some_and(|ch| ch.is_ascii_digit())
    {
        return Err(format!("invalid for binding name {var_name:?}"));
    }
    let (iter_src, body_src) = split_head_body(rest[in_pos + " in ".len()..].trim())?;
    let iterable = eval_form_in(state, &iter_src, env)?;
    let items: Vec<Value> = match iterable {
        Value::Array(items) => items,
        Value::String(text) => text
            .chars()
            .map(|ch| Value::String(ch.to_string()))
            .collect(),
        other => {
            return Err(format!(
                "for expects a list or string, got {}",
                value_kind(&other)
            ))
        }
    };
    let mut results = Vec::new();
    for item in items {
        let mut scope = HashMap::new();
        scope.insert(var_name.to_string(), item);
        env.push(scope);
        let result = eval_statements(state, &body_src, env);
        env.pop();
        results.push(result?);
    }
    Ok(Value::Array(results))
}

fn eval_while(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let rest = form
        .trim()
        .strip_prefix("while ")
        .ok_or_else(|| format!("invalid while expression {form:?}"))?;
    let (cond_src, body_src) = split_head_body(rest)?;
    let mut result = Value::Null;
    let mut iterations = 0_usize;
    let max_iterations = 100_000_usize;
    while truthy(&eval_form_in(state, &cond_src, env)?) {
        result = eval_statements(state, &body_src, env)?;
        iterations += 1;
        if iterations > max_iterations {
            return Err(format!("while loop exceeded {max_iterations} iterations"));
        }
    }
    Ok(result)
}

fn value_kind(value: &Value) -> &'static str {
    match value {
        Value::Null => "null",
        Value::Bool(_) => "bool",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

fn eval_form_in(state: &mut State, form: &str, env: &mut Env) -> Result<Value, String> {
    let trimmed = form.trim();
    if trimmed.starts_with("if ") {
        return eval_if(state, trimmed, env);
    }
    if trimmed.starts_with("do") {
        return eval_do(state, trimmed, env);
    }
    if trimmed.starts_with("let ") {
        return eval_let(state, trimmed, env);
    }
    if trimmed.starts_with("set ") {
        return eval_set(state, trimmed, env);
    }
    if trimmed.starts_with("for ") {
        return eval_for(state, trimmed, env);
    }
    if trimmed.starts_with("while ") {
        return eval_while(state, trimmed, env);
    }
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
    match call_parts(trimmed) {
        Ok((name, raw_args)) => {
            let args = raw_args
                .into_iter()
                .map(|arg| eval_form_in(state, &arg, env))
                .collect::<Result<Vec<_>, _>>()?;
            eval_builtin(&name, args)
        }
        Err(_) => {
            if trimmed.starts_with('[') && trimmed.ends_with(']') {
                return Ok(Value::Array(eval_array(state, trimmed, env)?));
            }
            if trimmed.starts_with('{') && trimmed.ends_with('}') {
                return Ok(Value::Object(parse_object(trimmed)?));
            }
            eval_expression(trimmed, env)
        }
    }
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
