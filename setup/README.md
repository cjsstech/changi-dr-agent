# Changi Travel Inspiration Hub - AI Itinerary Planner

An intelligent travel itinerary planner powered by Google's Gemini AI, designed to create personalized travel plans with inspiration from **Lonely Planet**, booking via **trip.com**, and local insights from **Now Boarding Changi**.

## Features

- 🗓️ **AI-Powered Itinerary Generation** - Create detailed day-by-day travel plans
- 🌍 **Destination Inspiration** - Discover perfect destinations based on your preferences
- 🎯 **Smart Intent Classification** - Gemini LLM understands natural language travel requests
- 🎫 **Booking Integration** - Seamlessly book flights, hotels, and experiences via [trip.com](https://www.trip.com)
- 📚 **Lonely Planet Insights** - Access world-class travel expertise from [Lonely Planet](https://www.lonelyplanet.com/)
- ✈️ **Now Boarding Articles** - Get Singapore-relevant travel tips from [Now Boarding](https://nowboarding.changiairport.com/)
- 💬 **Interactive Chat Interface** - Natural conversation with context-aware responses
- 📱 **Beautiful Responsive Design** - Works seamlessly on all devices

## Setup

### Prerequisites

- Python 3.8 or higher
- OpenAI API key or Google Gemini API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/cag-isc/isc-travel-recommender.git
   cd isc-travel-recommender
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and add your API keys:
   - `OPENAI_API_KEY` - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
   - `GEMINI_API_KEY` - Get from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Running the Application

1. Start the MCP Server (required for tools):
   ```bash
   cd mcp-server
   python server.py
   ```

2. In a new terminal, start the Flask server:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:5008
   ```

### For Production

Use gunicorn for production deployment:
```bash
gunicorn -w 4 -b 0.0.0.0:5008 app:app
```

## Project Structure

```
changi-travel-bot/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables (API keys)
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── static/
│   ├── style.css         # CSS styling
│   └── script.js         # Frontend JavaScript
└── templates/
    └── index.html        # Main HTML template
```

## Usage

### Create Travel Itineraries
Generate detailed day-by-day plans:
- "Plan a 5-day trip to Tokyo with focus on food and culture"
- "Create an itinerary for 2 weeks in Thailand - beaches and temples"
- "7-day Bali itinerary for honeymooners, mid-range budget"

### Get Destination Inspiration
Discover perfect destinations:
- "Weekend getaway ideas from Singapore for families"
- "What are the best adventure destinations in Southeast Asia?"
- "Romantic destinations with beaches and luxury resorts"

### Book Your Trip
Get booking guidance:
- "Help me book a romantic trip to Bali for 7 days"
- "What flights and hotels should I book for Tokyo?"
- "Best experiences to book in Paris"

### Explore Activities
Find experiences and attractions:
- "What experiences should I try in Bali?"
- "Top things to do in Tokyo for foodies"
- "Adventure activities in New Zealand"

### Example Prompts

- 🗾 **Tokyo Trip**: "Plan a 5-day trip to Tokyo with focus on food and culture"
- 👨‍👩‍👧 **Family Weekend**: "Weekend getaway ideas from Singapore for families"
- 🏝️ **Thailand 2 Weeks**: "Create an itinerary for 2 weeks in Thailand"
- 🏔️ **Adventure SEA**: "What are the best adventure destinations in Southeast Asia?"
- 💑 **Romantic Bali**: "Help me book a romantic trip to Bali for 7 days"

## Technology Stack

- **Backend**: Flask (Python web framework)
- **AI/ML**: Google Gemini Pro (Intent classification & itinerary generation)
- **Travel Resources**: 
  - [Lonely Planet](https://www.lonelyplanet.com/) - Destination expertise
  - [trip.com](https://www.trip.com) - Flight, hotel & experience bookings
  - [Now Boarding](https://nowboarding.changiairport.com/) - Singapore travel insights
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **API Architecture**: RESTful endpoints

## How It Works

1. **User Input** → User describes their travel needs (destination, duration, preferences)
2. **Intent Classification** → Gemini LLM analyzes and extracts:
   - Intent (itinerary_request, destination_inspiration, booking_assistance, etc.)
   - Destination & travel dates
   - Duration & budget level
   - Preferences (beach, culture, adventure, food)
   - Interests & traveler type (solo, couple, family)
3. **Context Building** → System compiles extracted information
4. **Itinerary Generation** → Gemini creates detailed plans including:
   - Day-by-day activities
   - Restaurant and attraction recommendations
   - Booking suggestions via trip.com
   - Lonely Planet destination insights
   - Now Boarding article references
5. **Response Formatting** → Beautiful, structured itinerary with booking links

## API Endpoints

- `GET /` - Main page
- `POST /api/chat` - Send message and get AI response
- `GET /api/example/<id>` - Get example prompt by ID

## Integration Partners

### 🎫 trip.com
Users are directed to [trip.com](https://www.trip.com) for:
- Flight bookings
- Hotel reservations
- Experience and activity bookings
- Package deals

### 📚 Lonely Planet
Itineraries reference [Lonely Planet](https://www.lonelyplanet.com/) for:
- In-depth destination guides
- Expert travel recommendations
- Cultural insights and tips
- Best places to visit

### ✈️ Now Boarding
Singapore travelers benefit from [Now Boarding Changi](https://nowboarding.changiairport.com/) with:
- Singapore-specific travel articles
- Airport tips and guides
- Destination insights from Singapore perspective
- Travel inspiration for Changi passengers

## Environment Variables

- `GEMINI_API_KEY` - Your Google Gemini API key

## Notes

- Optimized for destinations accessible from Singapore/Changi Airport
- Generates detailed, actionable itineraries with specific recommendations
- Includes booking guidance and practical travel tips
- References real travel resources (Lonely Planet, Now Boarding)
- All responses are AI-generated and should be verified for accuracy

## License

MIT License - Feel free to use and modify as needed.

