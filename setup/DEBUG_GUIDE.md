# Debugging Guide

## Check if Server is Running

```bash
# Check if port 5001 is in use
lsof -ti:5001

# Or check for Python processes
ps aux | grep "python3 app.py"
```

## Start Server with Logging

Instead of running in background, start the server in foreground to see logs:

```bash
cd /Users/sowmiyavijayaraghavan/Documents/Projects/changi-travel-bot
python3 app.py
```

This will show:
- Server startup messages
- Request logs
- Error messages
- API call logs

## Check Browser Console

1. Open your browser (Chrome/Firefox)
2. Press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
3. Go to the "Console" tab
4. Look for:
   - Network errors (red)
   - API response errors
   - JavaScript errors

## Check Network Tab

1. Open Developer Tools (`F12`)
2. Go to "Network" tab
3. Make a request in the chat
4. Look for the `/agent/{agent_id}/chat` request
5. Click on it to see:
   - Request payload
   - Response status
   - Response body

## Common Issues

### Issue: "I had trouble with that" error

**Check:**
1. Browser console for errors
2. Server logs for exceptions
3. Network tab for API response

**Debug steps:**
```bash
# Check server logs
tail -f /path/to/logfile  # if logging to file
# Or run server in foreground to see logs

# Test API directly
curl -X POST http://localhost:5001/agent/agent-1766209064262-gch4g8m0q/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "im planning to travel to malaysia"}' \
  -v
```

### Issue: Server not responding

**Check:**
```bash
# Kill existing server
lsof -ti:5001 | xargs kill -9

# Start fresh
python3 app.py
```

### Issue: Agent not found

**Check:**
```bash
# Verify agent exists
cat storage/agents.json | grep "agent-1766209064262-gch4g8m0q"
```

## Enable Verbose Logging

Edit `app.py` and change logging level:

```python
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
```

## Test Agent Executor Directly

Create a test script `test_agent.py`:

```python
from core.agents import AgentExecutor

executor = AgentExecutor('agent-1766209064262-gch4g8m0q')
session_context = {}
result = executor.chat('im planning to travel to malaysia', session_context)
print(result)
```

Run it:
```bash
python3 test_agent.py
```

