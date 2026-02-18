# Changi Travel Assistant - Sequence Diagrams

## 1. Complete Travel Itinerary Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant LLM
    participant FlightAPI
    participant MCPTools

    User->>Frontend: "Yogyakarta, jan 30, 7 days"
    Frontend->>Backend: POST /api/chat
    
    Backend->>Backend: Extract info (destination, dates, duration)
    Backend->>Backend: Validate: All info present? ✓
    
    Backend->>FlightAPI: Search flights
    FlightAPI-->>Backend: Flight options
    
    Backend->>LLM: Generate itinerary
    LLM-->>Backend: HTML itinerary
    
    Backend->>MCPTools: Enhance (links, maps, articles)
    MCPTools-->>Backend: Enhanced content
    
    Backend-->>Frontend: {itinerary, flights, articles}
    Frontend-->>User: Display full itinerary
```

## 2. Missing Information Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant LLM

    User->>Frontend: "Planning 4 days to Bali"
    Frontend->>Backend: POST /api/chat
    
    Backend->>Backend: Extract: destination ✓, duration ✓
    Backend->>Backend: Extract: travel_dates ✗
    Backend->>Backend: Validation: Missing dates!
    
    Backend->>LLM: Ask for missing info
    LLM-->>Backend: "When are you traveling?"
    
    Backend-->>Frontend: Response
    Frontend-->>User: "When are you traveling?"
    
    User->>Frontend: "January 30"
    Frontend->>Backend: POST /api/chat
    Backend->>Backend: Extract date ✓
    Backend->>Backend: All info complete!
    Note over Backend: Continue with flight search & itinerary
```

## 3. Flight API Integration

```mermaid
sequenceDiagram
    participant Backend
    participant MCPServer
    participant FlightService
    participant ChangiAPI

    Backend->>MCPServer: POST /flights/search<br/>{destination, dates, limit}
    
    MCPServer->>FlightService: search_flights_by_destination()
    
    loop For each date
        FlightService->>ChangiAPI: GraphQL getFlights query
        ChangiAPI-->>FlightService: Flight data
    end
    
    FlightService->>FlightService: Filter & sort by time
    FlightService-->>MCPServer: Top 3 flights
    
    MCPServer-->>Backend: {success: true, flights: [...]}
    Backend->>Backend: Store flights in session
```

## 4. Content Enhancement Flow

```mermaid
sequenceDiagram
    participant Backend
    participant MCPServer
    participant ExternalAPIs

    Note over Backend: LLM generated HTML itinerary
    
    Backend->>MCPServer: Generate booking links
    MCPServer-->>Backend: Lonely Planet & Trip.com URLs
    
    Backend->>MCPServer: Extract & geocode locations
    MCPServer->>ExternalAPIs: Nominatim geocoding
    ExternalAPIs-->>MCPServer: Coordinates
    MCPServer-->>Backend: Location data
    
    Backend->>MCPServer: Fetch travel articles
    MCPServer->>ExternalAPIs: Now Boarding API
    ExternalAPIs-->>MCPServer: Articles
    MCPServer-->>Backend: Top 3 articles
    
    Note over Backend: Return complete itinerary with<br/>flights + links + map + articles
```

## 5. Session Management

```mermaid
sequenceDiagram
    participant User
    participant Backend
    participant Session

    User->>Backend: First request
    Backend->>Session: Check session
    
    alt New Session
        Session-->>Backend: Create empty context
    else Existing Session
        Session-->>Backend: Load saved context
    end
    
    Backend->>Backend: Process & extract info
    Backend->>Session: Save updated context
    Backend-->>User: Response
    
    Note over Session: Stores: destination, dates,<br/>duration, conversation history<br/>Timeout: 2 hours
    
    User->>Backend: Follow-up request
    Backend->>Session: Load context
    Note over Backend: Bot remembers previous info
    Backend-->>User: Contextual response
```

## Validation Rules

### Information Extraction
1. **Destination** → Check against Southeast Asia list
2. **Duration** → Extract from patterns like "3 days", "5 day"
3. **Travel Dates** → Parse formats like "Jan 30", "January 21, 2025"

### Validation Checkpoints
- ✅ **has_destination**: Destination extracted from message
- ✅ **has_duration**: Duration extracted and saved
- ✅ **has_travel_dates**: Valid dates (not empty list/null)
- ✅ **has_all_info**: All three present → Trigger flight search

### Flight Search Conditions
```
needs_flight_search = (
    has_destination AND
    has_duration AND
    has_travel_dates AND
    NOT already_searched
)
```

## Key Components

| Component | Responsibility |
|-----------|---------------|
| **Frontend** | User interface, API calls |
| **Backend** | Orchestration, validation, extraction |
| **LLM (Gemini)** | Natural language understanding, itinerary generation |
| **FlightAPI** | Search Changi Airport flights |
| **MCPTools** | Content enhancement (links, maps, articles) |
| **Session** | Context persistence (2-hour timeout) |
