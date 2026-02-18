# Debugging MCP and Date Extraction

## Issue 1: travel_dates is Empty []

### How to Debug

1. **Check date extraction logs:**
   ```bash
   tail -f /tmp/app.log | grep -E "Date extraction|travel_dates|Extracted travel dates"
   ```

2. **What to look for:**
   - `user_mentions_date` - Should be `True` if user mentioned a date
   - `current travel_dates` - Should show existing dates from session
   - `search_text` - Shows what text was searched for dates
   - `Extracted travel dates` - Shows what dates were found

3. **Common issues:**
   - Date format not recognized (e.g., "21st jan" should work, but check logs)
   - Year not specified (defaults to next year if past January)
   - Date extraction happens but not saved to session

### Date Format Support

The system supports these formats:
- "21st jan" or "21 jan" (without year - uses default)
- "jan 21" or "january 21" (without year - uses default)
- "21st jan 2026" or "21 jan 2026" (with year)
- "jan 21, 2026" or "january 21, 2026" (with year)
- "21/01/2026" or "21-01-2026" (DD/MM/YYYY)

## Issue 2: Confirming MCP Flight API Calls

### How to Verify

1. **Check MCP Manager logs:**
   ```bash
   tail -f /tmp/app.log | grep -E "MCP Manager|MCP Flight API"
   ```

2. **Check MCP Server logs:**
   ```bash
   tail -f /tmp/mcp-server.log
   ```

3. **What to look for:**

   **In app.log (MCP Manager):**
   - `[MCP Manager] 🔌 Calling MCP tool: flight_api.search` - Shows MCP is being called
   - `[MCP Manager] 📤 Request args:` - Shows what arguments were sent
   - `[MCP Manager] ✅ MCP tool returned: success=True` - Shows response
   - `[MCP Manager] ✈️ Flight search result: X flights found` - Shows flight count

   **In mcp-server.log:**
   - `POST /flights/search HTTP/1.1" 200 OK` - Shows successful API call
   - Any errors or exceptions

4. **If MCP server is not running:**
   - You'll see: `Failed to call MCP server: Connection refused`
   - System will automatically fall back to direct function calls
   - Check logs for: `falling back to direct call`

### Quick Test

```bash
# Terminal 1: Start MCP server
cd mcp-server && python3 server.py

# Terminal 2: Monitor logs
tail -f /tmp/app.log | grep -E "MCP|travel_dates|Flight"

# Terminal 3: Test the chatbot
# Send a message like: "planning a trip to bali, 3 days, 21st jan"
```

### Expected Log Flow

1. **Date Extraction:**
   ```
   [Agent Executor] Date extraction check: user_mentions_date=True, current travel_dates=[], user_message='21st jan'
   [Agent Executor] Date without year detected, using default year: 2026
   [Agent Executor] ✅ Extracted travel dates: ['2026-01-21']
   ```

2. **Flight Search Trigger:**
   ```
   [Agent Executor] Flight search check: has_all_info=True, destination=Bali, travel_dates=['2026-01-21'], needs_flight_search=True
   🚀 Auto-searching flights immediately: Bali on ['2026-01-21']
   ```

3. **MCP Call:**
   ```
   [Agent Executor] 🚀 Calling MCP Flight API: destination=Bali, dates=['2026-01-21'], times=[]
   [MCP Manager] 🔌 Calling MCP tool: flight_api.search at http://localhost:8001/flights/search
   [MCP Manager] 📤 Request args: {'destination': 'Bali', 'scheduled_dates': ['2026-01-21'], ...}
   [MCP Manager] ✅ MCP tool flight_api.search returned: success=True
   [MCP Manager] ✈️ Flight search result: 3 flights found
   ```

4. **MCP Server Log:**
   ```
   INFO:     127.0.0.1:xxxxx - "POST /flights/search HTTP/1.1" 200 OK
   ```

## Troubleshooting

### travel_dates is empty

1. Check if date was mentioned in user message
2. Check if date format is supported
3. Check if date extraction regex matched
4. Check if extracted_dates was populated
5. Check if session_context was updated

### MCP Flight API not called

1. Check if MCP tools are enabled in agent config
2. Check if `needs_flight_search` is True
3. Check if `travel_dates` is not empty
4. Check if MCP server is running
5. Check for connection errors in logs

