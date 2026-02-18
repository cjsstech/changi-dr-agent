# MCP Architecture Overview

## What Was Implemented

We've successfully created a separate MCP (Model Context Protocol) server architecture with 4 dedicated services:

### 1. **Flight API Service** (`mcp-server/services/flight_service.py`)
- **Endpoints:**
  - `POST /flights/search` - Search flights by destination and dates
  - `POST /flights/format` - Format flight options as HTML
- **Functionality:** Wraps the existing `flight_service.py` to provide flight search and formatting via HTTP API

### 2. **Now Boarding Articles Service** (`mcp-server/services/nowboarding_service.py`)
- **Endpoints:**
  - `POST /nowboarding/articles` - Fetch articles for a destination
- **Functionality:** Fetches top articles from Now Boarding API, filters for 2025 articles

### 3. **Maps & Geocoding Service** (`mcp-server/services/maps_service.py`)
- **Endpoints:**
  - `POST /maps/geocode` - Geocode a location
  - `POST /maps/generate-url` - Generate Google Maps URL for multiple locations
  - `POST /maps/extract-locations` - Extract and geocode locations from itinerary HTML
- **Functionality:** Uses OpenStreetMap Nominatim API for geocoding, generates Google Maps URLs

### 4. **Travel Content Service** (`mcp-server/services/travel_content_service.py`)
- **Endpoints:**
  - `POST /travel/lonely-planet-url` - Generate Lonely Planet search URL
  - `POST /travel/trip-com-url` - Generate Trip.com search URL
  - `POST /travel/destination-links` - Generate destination-level links
- **Functionality:** Generates proper URLs for Lonely Planet and Trip.com

## Architecture Benefits

### ✅ Separation of Concerns
- Each service is independent and can be developed/maintained separately
- Clear boundaries between services

### ✅ Scalability
- Each service can be scaled independently
- Can run on separate servers/containers
- Better resource management

### ✅ Reusability
- Services can be used by other agents/applications
- Consistent API across all tools

### ✅ Performance
- Services can be called in parallel
- Independent caching strategies
- Load balancing per service

### ✅ Development Workflow
- Teams can work on services independently
- Services can be deployed separately
- Version services independently

## File Structure

```
changi-travel-bot/
├── mcp-server/                    # New MCP server directory
│   ├── __init__.py
│   ├── server.py                  # FastAPI server
│   ├── README.md                  # Server documentation
│   └── services/                  # Individual service implementations
│       ├── __init__.py
│       ├── flight_service.py      # Flight API service
│       ├── nowboarding_service.py # Now Boarding service
│       ├── maps_service.py        # Maps & geocoding service
│       └── travel_content_service.py # Travel content service
├── mcp/
│   ├── mcp_manager.py             # Updated to call HTTP endpoints
│   └── tool_registry.py           # Updated with new tools
├── agents/
│   └── agent_executor.py          # Updated to use MCP tools
└── config.py                      # Added MCP_SERVER_URL
```

## How It Works

1. **MCP Server** runs on port 8001, exposing REST API endpoints
2. **MCPManager** in the main app calls these endpoints via HTTP
3. **AgentExecutor** uses MCPManager to execute tools instead of direct function calls
4. **Fallback behavior** - If MCP tools aren't enabled, falls back to direct function calls

## Configuration

### Enable MCP Tools for an Agent

In the admin panel, when creating/editing an agent, check the MCP tools:
- ✅ Flight API
- ✅ Travel Content  
- ✅ Now Boarding Articles
- ✅ Maps & Geocoding

### MCP Server URL

Configure in `config.py` or `.env`:
```python
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:8001')
```

## Running the System

### Terminal 1: Start MCP Server
```bash
cd mcp-server
python server.py
```

### Terminal 2: Start Main Flask App
```bash
python app.py
```

## Migration Path

The system maintains backward compatibility:
- If MCP tools are **enabled** → Uses HTTP calls to MCP server
- If MCP tools are **disabled** → Falls back to direct function calls (old behavior)

This allows gradual migration and testing.

## Next Steps

1. **Test the MCP server** - Start it and test each endpoint
2. **Enable MCP tools** - Update agent configurations to enable MCP tools
3. **Monitor performance** - Compare MCP vs direct calls
4. **Production deployment** - Deploy MCP server separately with proper infrastructure

