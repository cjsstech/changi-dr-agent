import json
import base64
from urllib.parse import parse_qs
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class LambdaRequest:
    path:str
    method: str
    headers: Dict[str, Any]
    args: Dict[str, Any]
    body: Dict[str, Any]
    stage: str = ""

    @property
    def is_json(self) -> bool:
        ct = (self.headers.get("Content-Type") or self.headers.get("content-type") or "").lower()
        return "application/json" in ct


def build_lambda_request(event) -> LambdaRequest:
    headers = event.get("headers") or {}
    method = event.get("httpMethod")
    path = event.get("path") or "/"
    request_params = event.get("queryStringParameters") or {}

    # Extract API Gateway stage (e.g., "Prod")
    request_context = event.get("requestContext") or {}
    stage = request_context.get("stage", "")

    # Strip stage prefix from path if present (to normalize routing)
    if stage and path.startswith(f"/{stage}/"):
        path = path[len(f"/{stage}"):]
    elif stage and path == f"/{stage}":
        path = "/"

    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    content_type = (
        headers.get("Content-Type")
        or headers.get("content-type")
        or ""
    ).lower()

    body = {}

    if raw_body:
        if "application/json" in content_type:
            try:
                body = json.loads(raw_body)
            except Exception:
                body = {}
        elif "application/x-www-form-urlencoded" in content_type:
            parsed = parse_qs(raw_body)
            body = {k: v[0] for k, v in parsed.items()}

    return LambdaRequest(
        path=path,
        method=method,
        headers=headers,
        args=request_params,
        body=body,
        stage=stage
    )
