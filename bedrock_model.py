import boto3
import json
import os

BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

def _as_user_text(messages):
    return "\n".join([m.get("content","") for m in messages if m.get("role") == "user"])

def invoke_bedrock(messages, system_prompt="You are helpful."):
    model_id = BEDROCK_MODEL_ID

    if model_id.startswith("anthropic."):
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": _as_user_text(messages)}],
            "system": system_prompt,
            "temperature": 0.2
        }
    elif model_id.startswith("openai."):
        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _as_user_text(messages)}
            ],
            "temperature": 0.2,
            "max_tokens": 600
        }
    else:
        body = {
            "inputText": f"{system_prompt}\n\n{_as_user_text(messages)}",
            "textGenerationConfig": {"maxTokenCount": 600, "temperature": 0.2}
        }

    resp = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body).encode("utf-8"),
    )
    payload = json.loads(resp["body"].read())

    if model_id.startswith("anthropic."):
        parts = payload.get("content", [])
        out = [p.get("text","") for p in parts if isinstance(p, dict)]
        return "\n".join([s for s in out if s]).strip() or "(no text)"
    elif model_id.startswith("openai."):
        choices = payload.get("choices") or []
        if choices and isinstance(choices[0], dict) and "message" in choices[0]:
            return (choices[0]["message"].get("content") or "").strip() or "(no text)"
        if "output_text" in payload:
            return (payload["output_text"] or "").strip() or "(no text)"
        return "(no text)"
    else:
        if "results" in payload and payload["results"]:
            return (payload["results"][0].get("outputText") or "").strip() or "(no text)"
        if "outputText" in payload:
            return (payload["outputText"] or "").strip() or "(no text)"
        return "(no text)"
