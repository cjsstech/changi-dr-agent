# Flight API Integration Guide

## Overview

This document explains the flight API integration using Gemini LLM for intent classification and flight number extraction.

## Architecture

```
User Input
    ↓
Gemini LLM Intent Classifier (intent_classifier.py)
    ↓
Intent Detection & Flight Number Extraction
    ↓
Flight Service (flight_service.py)
    ↓
Changi Airport GraphQL API
    ↓
Response Formatting & Display
```

## Components

### 1. Intent Classifier (`intent_classifier.py`)

**Purpose**: Uses Gemini LLM to understand user intent and extract information.

**Key Function**: `classify_intent_with_gemini(message)`

**Extracted Information**:
- `intent`: greeting, flight_info, travel_recommendation, combined_request, etc.
- `flight_number`: Extracted flight number (e.g., "SQ222", "BA456")
- `destination`: Destination city/country if mentioned
- `preferences`: Travel keywords (beach, winter, culture, etc.)

**How It Works**:
1. Sends user message to Gemini with structured prompt
2. Gemini returns JSON with classified intent and extracted data
3. Fallback regex pattern matching for flight numbers
4. Returns structured dict with all extracted information

**Example**:
```python
Input: "Tell me about flight SQ123 and suggest things to do in Paris"
Output: {
    "intent": "combined_request",
    "flight_number": "SQ123",
    "destination": "Paris",
    "preferences": []
}
```

### 2. Flight Service (`flight_service.py`)

**Purpose**: Fetches real-time flight information from Changi Airport API.

**Key Functions**:

#### `fetch_flight_info(flight_number, direction="DEP")`
- Queries Changi Airport GraphQL API
- Returns flight details: terminal, gate, status, times, etc.
- Direction: "DEP" (departure) or "ARR" (arrival)

#### `try_both_directions(flight_number)`
- Attempts to find flight in both departures and arrivals
- Returns flight data if found in either direction

#### `format_flight_card(flight_data)`
- Formats flight information into beautiful HTML card
- Includes airline logo, status, terminal, gate/belt info
- Color-coded status badges

**API Configuration**:
```python
CHANGI_API_URL = "https://cauat-appsync.lz.changiairport.com/graphql"
CHANGI_API_KEY = YOUR_API_KEY
```

**GraphQL Query**:
```graphql
query {
    getFlights(direction: "DEP", flight_number: "SQ222") {
        flights {
            flight_number
            terminal
            scheduled_time
            direction
            airport_details { name, city, country_code }
            airline_details { name, logo_url }
            display_gate
            display_belt
            status_mapping { details_status_en }
        }
    }
}
```

### 3. Main Application (`app.py`)

**Enhanced Chat Endpoint**: `/api/chat`

**Processing Flow**:

1. **Receive Message**: Get user input from frontend
2. **Classify Intent**: Use Gemini to extract intent and flight number
3. **Handle Greetings**: Respond with welcome message
4. **Fetch Flight Data**: If flight number detected, query API
5. **Format Flight Card**: Display flight information
6. **Generate Recommendations**: Use Gemini for travel suggestions
7. **Combine Responses**: Merge flight cards with recommendations
8. **Return JSON**: Send formatted HTML response to frontend

**Response Structure**:
```json
{
    "response": "<HTML content with flight cards and recommendations>",
    "success": true,
    "intent": "combined_request",
    "has_flight_info": true
}
```

## User Interaction Examples

### Example 1: Flight Information Only
```
User: "SQ222"
System: 
  1. Classifies intent as "flight_info"
  2. Extracts flight number "SQ222"
  3. Fetches flight data from API
  4. Returns formatted flight card
```

### Example 2: Travel Recommendation Only
```
User: "I want a tropical beach vacation"
System:
  1. Classifies intent as "travel_recommendation"
  2. Extracts preferences: ["beach", "tropical"]
  3. Generates recommendations using Gemini
  4. Returns destination suggestions
```

### Example 3: Combined Request
```
User: "Tell me about flight BA456 and suggest things to do in London"
System:
  1. Classifies intent as "combined_request"
  2. Extracts flight "BA456" and destination "London"
  3. Fetches BA456 flight data
  4. Formats flight card
  5. Generates London recommendations
  6. Returns combined response
```

## Frontend Integration

### Updated Example Buttons
- **Beach Vacation**: Pure travel recommendation
- **Winter Getaway**: Travel recommendation with preferences
- **City Adventure**: Cultural travel suggestions
- **Flight Status**: Direct flight number query
- **Flight + Travel**: Combined flight info and recommendations

### HTML Rendering
The frontend now renders HTML responses instead of plain text:
```javascript
if (type === 'bot') {
    messageDiv.innerHTML = text;  // Render HTML
} else {
    messageDiv.textContent = text;  // Plain text for user
}
```

### Flight Card Styling
Beautiful gradient cards with:
- Airline logos
- Color-coded status badges
- Terminal and gate information
- Responsive design

## API Error Handling

1. **Flight Not Found**: Returns friendly error message
2. **API Timeout**: 10-second timeout with error handling
3. **Invalid Response**: Logs error and returns null
4. **Network Issues**: Catches RequestException and logs

## Logging

Comprehensive logging throughout:
```python
logging.info(f"📩 User message: {message}")
logging.info(f"🎯 Intent: {intent}, Flight: {flight_number}")
logging.info(f"🔍 Fetching flight info for: {flight_number}")
logging.info(f"[Flight API] Fetched data for {flight_number}")
```

## Testing the Integration

### Test Queries

1. **Simple Flight Number**:
   - "SQ222"
   - "BA456"
   - "TR505"

2. **Flight Status Questions**:
   - "What's the status of flight SQ222?"
   - "Check flight BA456"
   - "Tell me about TR505"

3. **Combined Queries**:
   - "I'm on flight SQ123, what can I do in Tokyo?"
   - "Tell me about BA456 and suggest London attractions"

4. **Travel Only**:
   - "I want beaches and sunshine"
   - "Winter destinations with skiing"
   - "Cultural cities in Asia"

## Configuration

### Environment Variables
```
GEMINI_API_KEY=
```

### Dependencies
```
flask==3.0.0
google-generativeai==0.3.2
python-dotenv==1.0.0
requests==2.31.0
gunicorn==21.2.0
```

## Future Enhancements

1. **Session Management**: Remember flight context across conversation
2. **Multiple Flights**: Handle queries about multiple flight numbers
3. **Flight Alerts**: Notify users of gate changes or delays
4. **Airport Maps**: Show terminal locations and navigation
5. **Real-time Updates**: WebSocket for live flight status
6. **Booking Integration**: Link to flight booking systems

## Troubleshooting

### Common Issues

1. **"Flight not found"**: 
   - Check flight number format (e.g., "SQ222" not "sq 222")
   - Verify flight exists in Changi Airport system
   - Try both DEP and ARR directions

2. **API Timeout**:
   - Check network connectivity
   - Verify API key is valid
   - Check Changi API service status

3. **Gemini LLM Errors**:
   - Verify GEMINI_API_KEY is set
   - Check API quota/limits
   - Review model availability

## Summary

This integration successfully combines:
- ✅ Gemini LLM for natural language understanding
- ✅ Flight number extraction from user queries
- ✅ Real-time flight data from Changi Airport API
- ✅ Beautiful UI with flight cards
- ✅ Combined flight info + travel recommendations
- ✅ Robust error handling and logging

The system provides a seamless experience for travelers seeking both flight information and travel inspiration!

