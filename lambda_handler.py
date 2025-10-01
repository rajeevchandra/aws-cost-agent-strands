import json
from agent import handle

def lambda_handler(event, context):
    body = event.get("body")
    query = ""
    if body:
        try:
            obj = json.loads(body); query = obj.get("query","")
        except Exception:
            query = body
    query = (query or "").strip() or "What is my spend from 2025-09-01 to 2025-10-01?"
    result = handle(query)
    return {"statusCode":200, "headers":{"Content-Type":"application/json"}, "body":json.dumps(result)}
