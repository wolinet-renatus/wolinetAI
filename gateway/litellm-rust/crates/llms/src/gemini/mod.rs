use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use serde_json::{Map, Value, json};

use crate::Error;

pub const DEFAULT_GEMINI_API_BASE: &str = "https://generativelanguage.googleapis.com/v1beta";

pub fn strip_gemini_prefix(model: &str) -> &str {
    model
        .strip_prefix("gemini/")
        .or_else(|| model.strip_prefix("vertex_ai/"))
        .unwrap_or(model)
}

pub fn endpoint_url(model: &str, api_base: Option<&str>, action: &str) -> String {
    let clean_model = strip_gemini_prefix(model);
    let base = api_base
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(DEFAULT_GEMINI_API_BASE)
        .trim_end_matches('/');
    if base.ends_with("/models") {
        format!("{base}/{clean_model}:{action}")
    } else {
        format!("{base}/models/{clean_model}:{action}")
    }
}

pub fn auth_headers(api_key: &str) -> Vec<(String, String)> {
    if api_key.starts_with("ya29.") {
        vec![("authorization".to_owned(), format!("Bearer {api_key}"))]
    } else {
        vec![("x-goog-api-key".to_owned(), api_key.to_owned())]
    }
}

pub fn openai_chat_to_gemini(
    body: &Map<String, Value>,
    default_temperature: Option<f64>,
    default_top_p: Option<f64>,
) -> Result<Value, Error> {
    let messages = body
        .get("messages")
        .and_then(Value::as_array)
        .ok_or_else(|| Error::InvalidRequest("messages array is required".into()))?;

    let mut system_parts: Vec<Value> = Vec::new();
    let mut contents: Vec<Value> = Vec::new();
    let mut tool_call_names: std::collections::HashMap<String, String> =
        std::collections::HashMap::new();

    for msg in messages {
        let role = msg.get("role").and_then(Value::as_str).unwrap_or("user");
        match role {
            "system" | "developer" => {
                if let Some(text) = msg.get("content").and_then(Value::as_str) {
                    if !text.is_empty() {
                        system_parts.push(json!({ "text": text }));
                    }
                } else if let Some(arr) = msg.get("content").and_then(Value::as_array) {
                    for part in arr {
                        if let Some(text) = part.get("text").and_then(Value::as_str) {
                            system_parts.push(json!({ "text": text }));
                        }
                    }
                }
            }
            "assistant" => {
                let mut parts = content_to_gemini_parts(msg.get("content"))?;
                if let Some(tool_calls) = msg.get("tool_calls").and_then(Value::as_array) {
                    for tc in tool_calls {
                        let id = tc.get("id").and_then(Value::as_str).unwrap_or_default();
                        if let Some(func) = tc.get("function") {
                            let name = func
                                .get("name")
                                .and_then(Value::as_str)
                                .unwrap_or("function")
                                .to_owned();
                            if !id.is_empty() {
                                tool_call_names.insert(id.to_owned(), name.clone());
                            }
                            let args = match func.get("arguments") {
                                Some(Value::String(s)) => {
                                    serde_json::from_str::<Value>(s).unwrap_or_else(|_| json!({}))
                                }
                                Some(v @ Value::Object(_)) => v.clone(),
                                _ => json!({}),
                            };
                            parts.push(json!({
                                "functionCall": {
                                    "name": name,
                                    "args": args
                                }
                            }));
                        }
                    }
                }
                if !parts.is_empty() {
                    contents.push(json!({ "role": "model", "parts": parts }));
                }
            }
            "tool" => {
                let call_id = msg
                    .get("tool_call_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                let name = msg
                    .get("name")
                    .and_then(Value::as_str)
                    .or_else(|| tool_call_names.get(call_id).map(String::as_str))
                    .unwrap_or("function");
                let raw_content = msg
                    .get("content")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                let response_val = serde_json::from_str::<Value>(raw_content)
                    .unwrap_or_else(|_| json!({ "result": raw_content }));
                let response_obj = if response_val.is_object() {
                    response_val
                } else {
                    json!({ "result": response_val })
                };
                contents.push(json!({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": name,
                            "response": response_obj
                        }
                    }]
                }));
            }
            _ => {
                let parts = content_to_gemini_parts(msg.get("content"))?;
                if !parts.is_empty() {
                    contents.push(json!({ "role": "user", "parts": parts }));
                }
            }
        }
    }

    let mut payload = Map::new();
    payload.insert("contents".to_owned(), Value::Array(contents));
    if !system_parts.is_empty() {
        payload.insert(
            "systemInstruction".to_owned(),
            json!({ "parts": system_parts }),
        );
    }

    let mut generation_config = Map::new();
    if let Some(temp) = body
        .get("temperature")
        .and_then(Value::as_f64)
        .or(default_temperature)
    {
        generation_config.insert("temperature".to_owned(), json!(temp));
    }
    if let Some(top_p) = body.get("top_p").and_then(Value::as_f64).or(default_top_p) {
        generation_config.insert("topP".to_owned(), json!(top_p));
    }
    if let Some(max_tokens) = body
        .get("max_completion_tokens")
        .or_else(|| body.get("max_tokens"))
        .and_then(Value::as_u64)
    {
        generation_config.insert("maxOutputTokens".to_owned(), json!(max_tokens));
    }
    if let Some(stop) = body.get("stop") {
        match stop {
            Value::String(s) => {
                generation_config.insert("stopSequences".to_owned(), json!([s]));
            }
            Value::Array(arr) => {
                generation_config.insert("stopSequences".to_owned(), Value::Array(arr.clone()));
            }
            _ => {}
        }
    }
    if let Some(rf) = body.get("response_format").and_then(Value::as_object) {
        match rf.get("type").and_then(Value::as_str) {
            Some("json_object") => {
                generation_config.insert(
                    "responseMimeType".to_owned(),
                    Value::String("application/json".to_owned()),
                );
            }
            Some("json_schema") => {
                generation_config.insert(
                    "responseMimeType".to_owned(),
                    Value::String("application/json".to_owned()),
                );
                if let Some(schema) = rf.get("json_schema").and_then(|s| s.get("schema")) {
                    generation_config.insert("responseSchema".to_owned(), schema.clone());
                }
            }
            _ => {}
        }
    }
    if !generation_config.is_empty() {
        payload.insert(
            "generationConfig".to_owned(),
            Value::Object(generation_config),
        );
    }

    if let Some(tools) = body.get("tools").and_then(Value::as_array) {
        let mut declarations = Vec::new();
        for tool in tools {
            if tool.get("type").and_then(Value::as_str) == Some("function")
                && let Some(func) = tool.get("function")
            {
                declarations.push(func.clone());
            }
        }
        if !declarations.is_empty() {
            payload.insert(
                "tools".to_owned(),
                json!([{ "functionDeclarations": declarations }]),
            );
        }
    }

    if let Some(tool_choice) = body.get("tool_choice") {
        let mode = match tool_choice.as_str() {
            Some("none") => Some("NONE"),
            Some("required") => Some("ANY"),
            Some("auto") => Some("AUTO"),
            _ => None,
        };
        if let Some(mode_str) = mode {
            payload.insert(
                "toolConfig".to_owned(),
                json!({ "functionCallingConfig": { "mode": mode_str } }),
            );
        } else if let Some(name) = tool_choice
            .get("function")
            .and_then(|f| f.get("name"))
            .and_then(Value::as_str)
        {
            payload.insert(
                "toolConfig".to_owned(),
                json!({
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [name]
                    }
                }),
            );
        }
    }

    Ok(Value::Object(payload))
}

fn content_to_gemini_parts(content: Option<&Value>) -> Result<Vec<Value>, Error> {
    let Some(content) = content else {
        return Ok(Vec::new());
    };
    match content {
        Value::Null => Ok(Vec::new()),
        Value::String(text) => {
            if text.is_empty() {
                Ok(Vec::new())
            } else {
                Ok(vec![json!({ "text": text })])
            }
        }
        Value::Array(items) => {
            let mut parts = Vec::new();
            for item in items {
                match item.get("type").and_then(Value::as_str) {
                    Some("text") => {
                        if let Some(text) = item.get("text").and_then(Value::as_str) {
                            parts.push(json!({ "text": text }));
                        }
                    }
                    Some("image_url") => {
                        let url = item
                            .get("image_url")
                            .and_then(|u| u.get("url").or(Some(u)))
                            .and_then(Value::as_str)
                            .unwrap_or_default();
                        if let Some(part) = data_url_or_uri_to_gemini_part(url)? {
                            parts.push(part);
                        }
                    }
                    _ => {}
                }
            }
            Ok(parts)
        }
        _ => Ok(Vec::new()),
    }
}

fn data_url_or_uri_to_gemini_part(url: &str) -> Result<Option<Value>, Error> {
    if url.is_empty() {
        return Ok(None);
    }
    if let Some(rest) = url.strip_prefix("data:")
        && let Some((meta, data)) = rest.split_once(',')
    {
        let mime = meta.split(';').next().unwrap_or("image/png");
        return Ok(Some(json!({
            "inlineData": {
                "mimeType": mime,
                "data": data
            }
        })));
    }
    Ok(Some(json!({
        "fileData": {
            "fileUri": url
        }
    })))
}

pub fn gemini_response_to_openai(
    gemini: &Value,
    requested_model: &str,
    response_id: &str,
    created: u64,
) -> Value {
    let mut choices = Vec::new();
    if let Some(candidates) = gemini.get("candidates").and_then(Value::as_array) {
        for (idx, candidate) in candidates.iter().enumerate() {
            let (text, reasoning, tool_calls) = extract_candidate_parts(candidate, idx);
            let has_tools = !tool_calls.is_empty();
            let finish_reason = map_finish_reason(
                candidate.get("finishReason").and_then(Value::as_str),
                has_tools,
            );
            let mut msg = Map::new();
            msg.insert("role".to_owned(), Value::String("assistant".to_owned()));
            msg.insert(
                "content".to_owned(),
                if text.is_empty() && has_tools {
                    Value::Null
                } else {
                    Value::String(text)
                },
            );
            if !reasoning.is_empty() {
                msg.insert("reasoning_content".to_owned(), Value::String(reasoning));
            }
            if has_tools {
                msg.insert("tool_calls".to_owned(), Value::Array(tool_calls));
            }
            choices.push(json!({
                "index": candidate.get("index").and_then(Value::as_u64).unwrap_or(idx as u64),
                "message": Value::Object(msg),
                "finish_reason": finish_reason
            }));
        }
    }

    let usage = gemini_usage_to_openai(gemini.get("usageMetadata"));
    json!({
        "id": response_id,
        "object": "chat.completion",
        "created": created,
        "model": requested_model,
        "choices": choices,
        "usage": usage
    })
}

pub fn gemini_sse_chunk_to_openai(
    gemini: &Value,
    requested_model: &str,
    response_id: &str,
    created: u64,
) -> Option<Value> {
    let mut choices = Vec::new();
    if let Some(candidates) = gemini.get("candidates").and_then(Value::as_array) {
        for (idx, candidate) in candidates.iter().enumerate() {
            let (text, reasoning, tool_calls) = extract_candidate_parts(candidate, idx);
            let has_tools = !tool_calls.is_empty();
            let finish_reason = candidate
                .get("finishReason")
                .and_then(Value::as_str)
                .map(|r| map_finish_reason(Some(r), has_tools));
            let mut delta = Map::new();
            if !text.is_empty() {
                delta.insert("content".to_owned(), Value::String(text));
            }
            if !reasoning.is_empty() {
                delta.insert("reasoning_content".to_owned(), Value::String(reasoning));
            }
            if has_tools {
                let indexed_tools: Vec<Value> = tool_calls
                    .into_iter()
                    .enumerate()
                    .map(|(t_idx, mut tc)| {
                        if let Some(obj) = tc.as_object_mut() {
                            obj.insert("index".to_owned(), json!(t_idx));
                        }
                        tc
                    })
                    .collect();
                delta.insert("tool_calls".to_owned(), Value::Array(indexed_tools));
            }
            choices.push(json!({
                "index": candidate.get("index").and_then(Value::as_u64).unwrap_or(idx as u64),
                "delta": Value::Object(delta),
                "finish_reason": finish_reason
            }));
        }
    }

    let usage = gemini
        .get("usageMetadata")
        .map(|u| gemini_usage_to_openai(Some(u)));
    if choices.is_empty() && usage.is_none() {
        return None;
    }

    let mut chunk = Map::new();
    chunk.insert("id".to_owned(), Value::String(response_id.to_owned()));
    chunk.insert(
        "object".to_owned(),
        Value::String("chat.completion.chunk".to_owned()),
    );
    chunk.insert("created".to_owned(), json!(created));
    chunk.insert(
        "model".to_owned(),
        Value::String(requested_model.to_owned()),
    );
    chunk.insert("choices".to_owned(), Value::Array(choices));
    if let Some(u) = usage {
        chunk.insert("usage".to_owned(), u);
    }
    Some(Value::Object(chunk))
}

fn extract_candidate_parts(candidate: &Value, cand_idx: usize) -> (String, String, Vec<Value>) {
    let mut text = String::new();
    let mut reasoning = String::new();
    let mut tool_calls = Vec::new();
    let Some(parts) = candidate
        .get("content")
        .and_then(|c| c.get("parts"))
        .and_then(Value::as_array)
    else {
        return (text, reasoning, tool_calls);
    };

    for (part_idx, part) in parts.iter().enumerate() {
        if let Some(part_text) = part.get("text").and_then(Value::as_str) {
            if part.get("thought").and_then(Value::as_bool) == Some(true) {
                reasoning.push_str(part_text);
            } else {
                text.push_str(part_text);
            }
        }
        if let Some(fc) = part.get("functionCall") {
            let name = fc.get("name").and_then(Value::as_str).unwrap_or_default();
            let args = fc
                .get("args")
                .map(|v| serde_json::to_string(v).unwrap_or_else(|_| "{}".to_owned()))
                .unwrap_or_else(|| "{}".to_owned());
            tool_calls.push(json!({
                "id": format!("call_{cand_idx}_{part_idx}"),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args
                }
            }));
        }
    }

    (text, reasoning, tool_calls)
}

fn map_finish_reason(reason: Option<&str>, has_tools: bool) -> &'static str {
    if has_tools {
        return "tool_calls";
    }
    match reason {
        Some("MAX_TOKENS") => "length",
        Some("SAFETY") | Some("RECITATION") => "content_filter",
        _ => "stop",
    }
}

fn gemini_usage_to_openai(meta: Option<&Value>) -> Value {
    let Some(meta) = meta else {
        return json!({
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        });
    };
    let prompt_tokens = meta
        .get("promptTokenCount")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let completion_tokens = meta
        .get("candidatesTokenCount")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let total_tokens = meta
        .get("totalTokenCount")
        .and_then(Value::as_u64)
        .unwrap_or(prompt_tokens + completion_tokens);
    let cached = meta
        .get("cachedContentTokenCount")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    if cached > 0 {
        json!({
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_tokens_details": { "cached_tokens": cached }
        })
    } else {
        json!({
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        })
    }
}

pub fn openai_embeddings_to_gemini(
    upstream_model: &str,
    body: &Map<String, Value>,
) -> Result<(Value, bool), Error> {
    let clean_model = strip_gemini_prefix(upstream_model);
    let dimensions = body.get("dimensions").and_then(Value::as_u64);
    let inputs: Vec<String> = match body.get("input") {
        Some(Value::String(s)) => vec![s.clone()],
        Some(Value::Array(arr)) => arr
            .iter()
            .filter_map(|v| v.as_str().map(str::to_owned))
            .collect(),
        _ => {
            return Err(Error::InvalidRequest(
                "embeddings input must be a string or array of strings".into(),
            ));
        }
    };
    if inputs.is_empty() {
        return Err(Error::InvalidRequest(
            "embeddings input must not be empty".into(),
        ));
    }

    if inputs.len() == 1 {
        let mut req = Map::new();
        req.insert(
            "model".to_owned(),
            Value::String(format!("models/{clean_model}")),
        );
        req.insert(
            "content".to_owned(),
            json!({ "parts": [{ "text": inputs[0] }] }),
        );
        if let Some(dim) = dimensions {
            req.insert("outputDimensionality".to_owned(), json!(dim));
        }
        return Ok((Value::Object(req), false));
    }

    let requests: Vec<Value> = inputs
        .into_iter()
        .map(|text| {
            let mut req = Map::new();
            req.insert(
                "model".to_owned(),
                Value::String(format!("models/{clean_model}")),
            );
            req.insert("content".to_owned(), json!({ "parts": [{ "text": text }] }));
            if let Some(dim) = dimensions {
                req.insert("outputDimensionality".to_owned(), json!(dim));
            }
            Value::Object(req)
        })
        .collect();
    Ok((json!({ "requests": requests }), true))
}

pub fn gemini_embeddings_to_openai(gemini: &Value, requested_model: &str) -> Result<Value, Error> {
    let vectors: Vec<&Value> = if let Some(arr) = gemini.get("embeddings").and_then(Value::as_array)
    {
        arr.iter().filter_map(|item| item.get("values")).collect()
    } else if let Some(values) = gemini.get("embedding").and_then(|e| e.get("values")) {
        vec![values]
    } else {
        return Err(Error::InvalidResponse(
            "missing embedding values in Gemini response".into(),
        ));
    };

    let data: Vec<Value> = vectors
        .into_iter()
        .enumerate()
        .map(|(index, embedding)| {
            json!({
                "object": "embedding",
                "index": index,
                "embedding": embedding
            })
        })
        .collect();

    Ok(json!({
        "object": "list",
        "data": data,
        "model": requested_model,
        "usage": {
            "prompt_tokens": 0,
            "total_tokens": 0
        }
    }))
}

pub fn is_imagen_model(upstream_model: &str) -> bool {
    let clean = strip_gemini_prefix(upstream_model).to_ascii_lowercase();
    clean.starts_with("imagen") || clean.starts_with("imagegeneration")
}

pub fn openai_image_to_gemini(
    upstream_model: &str,
    body: &Map<String, Value>,
) -> Result<(Value, bool), Error> {
    let prompt = body
        .get("prompt")
        .and_then(Value::as_str)
        .filter(|p| !p.is_empty())
        .ok_or_else(|| Error::InvalidRequest("prompt is required".into()))?;
    let n = body.get("n").and_then(Value::as_u64).unwrap_or(1);
    let aspect_ratio = body
        .get("aspectRatio")
        .or_else(|| body.get("aspect_ratio"))
        .and_then(Value::as_str)
        .or_else(|| {
            body.get("size")
                .and_then(Value::as_str)
                .map(map_size_to_aspect_ratio)
        });

    if is_imagen_model(upstream_model) {
        let mut params = Map::new();
        params.insert("sampleCount".to_owned(), json!(n));
        if let Some(ar) = aspect_ratio {
            params.insert("aspectRatio".to_owned(), Value::String(ar.to_owned()));
        }
        return Ok((
            json!({
                "instances": [{ "prompt": prompt }],
                "parameters": Value::Object(params)
            }),
            true,
        ));
    }

    let mut gen_config = Map::new();
    gen_config.insert("responseModalities".to_owned(), json!(["TEXT", "IMAGE"]));
    if n > 1 {
        gen_config.insert("candidateCount".to_owned(), json!(n));
    }
    if let Some(ar) = aspect_ratio {
        gen_config.insert("imageConfig".to_owned(), json!({ "aspectRatio": ar }));
    }

    Ok((
        json!({
            "contents": [{ "role": "user", "parts": [{ "text": prompt }] }],
            "generationConfig": Value::Object(gen_config)
        }),
        false,
    ))
}

fn map_size_to_aspect_ratio(size: &str) -> &'static str {
    match size {
        "1792x1024" | "1536x1024" => "16:9",
        "1024x1792" | "1024x1536" => "9:16",
        _ => "1:1",
    }
}

pub fn gemini_image_to_openai(
    gemini: &Value,
    is_imagen_predict: bool,
    created: u64,
) -> Result<Value, Error> {
    let mut images = Vec::new();
    if is_imagen_predict {
        if let Some(preds) = gemini.get("predictions").and_then(Value::as_array) {
            for pred in preds {
                if let Some(b64) = pred.get("bytesBase64Encoded").and_then(Value::as_str) {
                    images.push(json!({ "b64_json": b64 }));
                }
            }
        }
    } else if let Some(candidates) = gemini.get("candidates").and_then(Value::as_array) {
        for candidate in candidates {
            if let Some(parts) = candidate
                .get("content")
                .and_then(|c| c.get("parts"))
                .and_then(Value::as_array)
            {
                for part in parts {
                    if let Some(inline) = part.get("inlineData")
                        && let Some(b64) = inline.get("data").and_then(Value::as_str)
                    {
                        images.push(json!({ "b64_json": b64 }));
                    }
                }
            }
        }
    }

    if images.is_empty() {
        return Err(Error::InvalidResponse(
            "Gemini image generation returned no image data".into(),
        ));
    }

    Ok(json!({
        "created": created,
        "data": images
    }))
}

pub fn audio_to_gemini_request(
    audio_bytes: &[u8],
    mime_type: Option<&str>,
    prompt: Option<&str>,
    language: Option<&str>,
) -> Value {
    let encoded = BASE64.encode(audio_bytes);
    let mime = mime_type.unwrap_or("audio/mpeg");
    let mut instruction = String::from("Transcribe the following audio accurately.");
    if let Some(lang) = language.filter(|l| !l.is_empty()) {
        instruction.push_str(&format!(" Primary language: {lang}."));
    }
    if let Some(p) = prompt.filter(|p| !p.is_empty()) {
        instruction.push_str(&format!(" Context: {p}"));
    }
    json!({
        "contents": [{
            "role": "user",
            "parts": [
                { "text": instruction },
                { "inlineData": { "mimeType": mime, "data": encoded } }
            ]
        }]
    })
}

pub fn gemini_audio_to_openai(gemini: &Value) -> Result<Value, Error> {
    let text = gemini
        .get("candidates")
        .and_then(Value::as_array)
        .and_then(|c| c.first())
        .and_then(|c| c.get("content"))
        .and_then(|c| c.get("parts"))
        .and_then(Value::as_array)
        .map(|parts| {
            parts
                .iter()
                .filter_map(|p| p.get("text").and_then(Value::as_str))
                .collect::<Vec<_>>()
                .join("")
        })
        .ok_or_else(|| {
            Error::InvalidResponse("missing transcript text in Gemini response".into())
        })?;
    Ok(json!({ "text": text.trim() }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builds_vertex_and_ai_studio_urls() {
        let vertex = "https://aiplatform.googleapis.com/v1/projects/194835052236/locations/global/publishers/google";
        assert_eq!(
            endpoint_url("gemini/gemini-3.8-flash", Some(vertex), "generateContent"),
            "https://aiplatform.googleapis.com/v1/projects/194835052236/locations/global/publishers/google/models/gemini-3.8-flash:generateContent"
        );
        assert_eq!(
            endpoint_url(
                "gemini/gemini-3.8-flash",
                Some(vertex),
                "streamGenerateContent?alt=sse"
            ),
            "https://aiplatform.googleapis.com/v1/projects/194835052236/locations/global/publishers/google/models/gemini-3.8-flash:streamGenerateContent?alt=sse"
        );
        assert_eq!(
            endpoint_url("gemini/gemini-2.5-flash", None, "generateContent"),
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        );
    }

    #[test]
    fn converts_chat_and_sse_and_images_and_embeddings() {
        let chat_req = serde_json::from_value::<Map<String, Value>>(json!({
            "model": "Wolinet Max",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"}
            ],
            "temperature": 0.3
        }))
        .unwrap();
        let gem_req = openai_chat_to_gemini(&chat_req, None, None).unwrap();
        assert_eq!(
            gem_req["systemInstruction"]["parts"][0]["text"],
            "Be concise."
        );
        assert_eq!(gem_req["contents"][0]["parts"][0]["text"], "Hello");

        let gem_resp = json!({
            "candidates": [{
                "index": 0,
                "content": { "parts": [
                    { "thought": true, "text": "thinking" },
                    { "text": "Hi there!" }
                ]},
                "finishReason": "STOP"
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
                "cachedContentTokenCount": 4
            }
        });
        let openai_resp = gemini_response_to_openai(&gem_resp, "Wolinet Max", "chatcmpl-1", 100);
        assert_eq!(openai_resp["choices"][0]["message"]["content"], "Hi there!");
        assert_eq!(
            openai_resp["choices"][0]["message"]["reasoning_content"],
            "thinking"
        );
        assert_eq!(
            openai_resp["usage"]["prompt_tokens_details"]["cached_tokens"],
            4
        );

        let chunk =
            gemini_sse_chunk_to_openai(&gem_resp, "Wolinet Max", "chatcmpl-1", 100).unwrap();
        assert_eq!(chunk["object"], "chat.completion.chunk");
        assert_eq!(chunk["choices"][0]["delta"]["content"], "Hi there!");

        let img_req = serde_json::from_value::<Map<String, Value>>(json!({
            "model": "dall-e-3",
            "prompt": "A mountain sunrise",
            "size": "1792x1024"
        }))
        .unwrap();
        let (gem_img, is_imagen) =
            openai_image_to_gemini("gemini/gemini-3.1-flash-image", &img_req).unwrap();
        assert!(!is_imagen);
        assert_eq!(
            gem_img["generationConfig"]["imageConfig"]["aspectRatio"],
            "16:9"
        );
        let img_resp = json!({
            "candidates": [{
                "content": { "parts": [{ "inlineData": { "mimeType": "image/png", "data": "QUJD" } }] }
            }]
        });
        let openai_img = gemini_image_to_openai(&img_resp, false, 100).unwrap();
        assert_eq!(openai_img["data"][0]["b64_json"], "QUJD");
    }
}
