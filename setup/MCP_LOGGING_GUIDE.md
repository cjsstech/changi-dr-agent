# MCP Logging Guide

## Overview

MCP (Model Context Protocol) tools are used during itinerary generation for:
1. **Flight Search** - When destination, dates, and duration are gathered
2. **Flight Formatting** - When flights are found and need to be embedded in itinerary
3. **Now Boarding Articles** - After itinerary is generated, to fetch related articles
4. **Maps/Location Extraction** - After itinerary is generated, to extract locations for Google Maps
5. **Travel Content URLs** - For generating Lonely Planet and Trip.com links

## MCP Server Logs

The MCP server runs on port 8001 and logs to stdout. To start it with logging:

```bash
# Start MCP server with logs
cd mcp-server
python server.py > /tmp/mcp_server.log 2>&1 &

# Or with uvicorn directly
uvicorn server:app --host 0.0.0.0 --port 8001 --log-level info > /tmp/mcp_server.log 2>&1 &
```

### View MCP Server Logs

```bash
# View all MCP server logs
tail -f /tmp/mcp_server.log

# Filter for specific operations
tail -f /tmp/mcp_server.log | grep -E "Flight search|Now Boarding|Maps|Travel Content"

# Filter for errors
tail -f /tmp/mcp_server.log | grep -E "Error|error|❌"
```

## Main App Logs (MCP Manager)

The MCP Manager in the main Flask app logs all MCP tool calls to `/tmp/app.log`:

```bash
# View MCP-related logs from main app
tail -f /tmp/app.log | grep -E "MCP|mcp_manager|execute_tool"

# Filter for specific MCP tools
tail -f /tmp/app.log | grep -E "flight_api|nowboarding|maps|travel_content"

# View flight search logs
tail -f /tmp/app.log | grep -E "Flight search|flight_api.search"

# View article fetching logs
tail -f /tmp/app.log | grep -E "Now Boarding|nowboarding.fetch"

# View maps logs
tail -f /tmp/app.log | grep -E "Maps|maps.extract|maps.geocode"
```

## MCP Tools Called During Itinerary Generation

### 1. Flight Search (Before Itinerary)
**When**: After gathering destination, travel dates, and duration
**Tool**: `flight_api.search`
**Inputs**:
- `destination`: e.g., "bali"
- `scheduled_dates`: e.g., ["2026-01-21"]
- `preferred_times`: e.g., ["morning", "afternoon", "evening"]
- `limit`: 3

**Logs to check**:
```bash
tail -f /tmp/app.log | grep -E "Flight search|flight_api.search|MCP.*Flight"
```

### 2. Flight Formatting (After Flights Found)
**When**: When flights are found and need to be embedded in itinerary
**Tool**: `flight_api.format`
**Inputs**:
- `flights`: List of flight objects
- `destination`: e.g., "bali"
- `departure_date`: e.g., "2026-01-21"
- `duration`: e.g., "3 days"

**Logs to check**:
```bash
tail -f /tmp/app.log | grep -E "flight_api.format|format_flights|Flight format"
```

### 3. Now Boarding Articles (After Itinerary Generated)
**When**: After itinerary HTML is generated
**Tool**: `nowboarding.fetch_articles`
**Inputs**:
- `destination`: e.g., "bali"
- `limit`: 3

**Logs to check**:
```bash
tail -f /tmp/app.log | grep -E "Now Boarding|nowboarding.fetch|articles"
```

### 4. Maps/Location Extraction (After Itinerary Generated)
**When**: After itinerary HTML is generated
**Tool**: `maps.extract_locations`
**Inputs**:
- `itinerary_html`: The generated itinerary HTML
- `destination`: e.g., "bali"

**Logs to check**:
```bash
tail -f /tmp/app.log | grep -E "maps.extract|extract_locations|Locations"
```

### 5. Google Maps URL Generation (After Locations Extracted)
**When**: After locations are extracted
**Tool**: `maps.generate_url`
**Inputs**:
- `locations`: List of location objects with coordinates
- `destination`: e.g., "bali"

**Logs to check**:
```bash
tail -f /tmp/app.log | grep -E "maps.generate|generate_url|Google Maps"
```

## Complete Logging Command

To see all MCP-related activity during itinerary generation:

```bash
# In one terminal - MCP Server logs
tail -f /tmp/mcp_server.log

# In another terminal - Main app MCP logs
tail -f /tmp/app.log | grep -E "MCP|flight_api|nowboarding|maps|travel_content"
```

## Debugging Empty Cards Issue

If itinerary cards are empty, check:

```bash
# Check if MCP tools are being called
tail -f /tmp/app.log | grep -E "MCP.*tool|execute_tool"

# Check if flight search happened
tail -f /tmp/app.log | grep -E "Flight search|flights found"

# Check if articles were fetched
tail -f /tmp/app.log | grep -E "Now Boarding|articles"

# Check if locations were extracted
tail -f /tmp/app.log | grep -E "extract_locations|Locations"
```

## MCP Server Health Check

To verify MCP server is running:

```bash
curl http://localhost:8001/health
```

Should return: `{"status":"healthy","service":"mcp-server"}`

## No Inputs Required

**Important**: MCP tools do NOT require manual inputs. They are automatically called by the system when:
- All required information is gathered (for flight search)
- Itinerary is generated (for articles and maps)

You just need to:
1. Start the MCP server
2. Start the main Flask app
3. Test with a query like "bali, 3 days, 21st jan"
4. Check the logs to see MCP tool calls

