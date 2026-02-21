# controller.py
from dotenv import load_dotenv
load_dotenv()

import config
import json
import logging
from fastapi import FastAPI, Request, Response
from handlers.chat_handler import process

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Local Lambda API Gateway Proxy")

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_lambda(request: Request, full_path: str):
    """
    Catch-all route that simulates AWS API Gateway and calls the Lambda handler.
    """
    logger.info(f"Received {request.method} request for /{full_path}")

    # Get body
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8") if body_bytes else ""

    # Minimal Mock Lambda Event
    event = {
        "body": body,
        "httpMethod": request.method,
        "path": f"/{full_path}",
        "queryStringParameters": dict(request.query_params),
        "headers": dict(request.headers),
    }

    # Minimal Mock Lambda Context
    class MockContext:
        pass
    context = MockContext()

    # Call the Lambda handler
    try:
        response_data = process(event, context)
    except Exception as e:
        logger.error(f"Error calling Lambda handler: {e}")
        return Response(
            content=json.dumps({"error": "Internal Server Error", "details": str(e)}),
            status_code=500,
            media_type="application/json"
        )

    # Extract response details
    status_code = response_data.get("statusCode", 200)
    headers = response_data.get("headers", {})
    response_body = response_data.get("body", "")

    # Handle the case where the body is already a dict (though handler.py returns stringified JSON via json_response)
    if not isinstance(response_body, str):
        response_body = json.dumps(response_body)

    return Response(
        content=response_body,
        status_code=status_code,
        headers=headers,
        media_type=headers.get("Content-Type", "application/json")
    )

if __name__ == "__main__": 
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5008, reload=True)
