# MCP Server Setup Guide

This guide explains how to set up and run the separate MCP (Model Context Protocol) server for the Changi Travel Bot.

## Architecture

The system now uses a separate FastAPI server (`mcp-server/`) that provides 4 MCP tools:

1. **Flight API** - Search and format flights
2. **Now Boarding Articles** - Fetch travel articles
3. **Maps & Geocoding** - Geocode locations and generate map URLs
4. **Travel Content** - Generate Lonely Planet and Trip.com URLs

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install FastAPI, uvicorn, and pydantic along with other dependencies.

### 2. Start the MCP Server

In a separate terminal, start the MCP server:

```bash
cd mcp-server
python server.py
```

Or using uvicorn directly:

```bash
cd mcp-server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

The server will start on `http://localhost:8001`

### 3. Start the Main Flask App

In another terminal, start the main Flask application:

```bash
python app.py
```

The Flask app will connect to the MCP server automatically.

## Configuration

### MCP Server URL

The MCP server URL can be configured in `config.py` or via environment variable:

```bash
export MCP_SERVER_URL=http://localhost:8001
```

Or in `.env`:
```
MCP_SERVER_URL=http://localhost:8001
```

### Enabling MCP Tools

MCP tools are enabled per agent in the admin panel. When creating/editing an agent, check the MCP tools you want to enable:

- ✅ Flight API
- ✅ Travel Content
- ✅ Now Boarding Articles
- ✅ Maps & Geocoding

## Testing

### Test MCP Server Health

```bash
curl http://localhost:8001/health
```

Should return:
```json
{"status": "healthy", "service": "mcp-server"}
```

### Test Flight Search

```bash
curl -X POST http://localhost:8001/flights/search \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Bali",
    "scheduled_dates": ["2026-01-15"],
    "preferred_times": ["morning"],
    "limit": 3
  }'
```

### Test Now Boarding Articles

```bash
curl -X POST http://localhost:8001/nowboarding/articles \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Bali",
    "limit": 3
  }'
```

## Fallback Behavior

If MCP tools are not enabled for an agent, the system will fall back to direct function calls (the old behavior). This ensures backward compatibility.

## Production Deployment

For production, you may want to:

1. Run the MCP server as a separate service (systemd, Docker, etc.)
2. Use a reverse proxy (nginx) for the MCP server
3. Configure proper CORS settings
4. Add authentication/API keys
5. Use environment variables for configuration
6. Set up monitoring and logging

## Troubleshooting

### MCP Server Not Starting

- Check if port 8001 is already in use: `lsof -i :8001`
- Check Python version (requires 3.8+)
- Verify all dependencies are installed: `pip install -r requirements.txt`

### Connection Errors

- Verify MCP server is running: `curl http://localhost:8001/health`
- Check `MCP_SERVER_URL` in config matches the server address
- Check firewall settings if running on different machines

### Tool Not Working

- Verify the tool is enabled in the agent configuration
- Check MCP server logs for errors
- Verify the tool is available in `mcp/tool_registry.py`

