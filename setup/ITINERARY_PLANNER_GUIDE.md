# Travel Itinerary Planner - Implementation Guide

## Overview

The Changi Travel Inspiration Hub is an AI-powered travel itinerary planner that generates personalized travel plans using Gemini LLM, integrated with booking via **trip.com**, destination expertise from **Lonely Planet**, and local insights from **Now Boarding Changi**.

## Core Purpose

The chatbot serves as a comprehensive travel planning assistant that:
1. ✅ Generates detailed day-by-day travel itineraries
2. ✅ Provides destination inspiration based on preferences
3. ✅ Recommends booking platforms (trip.com for flights/hotels/experiences)
4. ✅ References Lonely Planet for destination expertise
5. ✅ Cites Now Boarding articles for Singapore-relevant travel insights

## Intent Classification

### Supported Intents

The system classifies user queries into these categories:

#### 1. **itinerary_request**
User wants a detailed travel plan.

**Examples:**
- "Plan a 5-day trip to Tokyo"
- "Create an itinerary for 2 weeks in Thailand"
- "7-day Bali itinerary for honeymooners"

**Response Includes:**
- Day-by-day breakdown
- Morning/afternoon/evening activities
- Specific restaurant recommendations
- Attraction suggestions
- Transportation tips
- Booking guidance via trip.com

#### 2. **destination_inspiration**
User seeking destination suggestions.

**Examples:**
- "Weekend getaway ideas from Singapore"
- "Best adventure destinations in Southeast Asia"
- "Romantic destinations with beaches"

**Response Includes:**
- 3-5 destination recommendations
- Why each fits their criteria
- Best time to visit
- Top experiences
- Lonely Planet guide references

#### 3. **booking_assistance**
User needs help with bookings.

**Examples:**
- "Help me book a trip to Bali"
- "What flights should I book to Tokyo?"
- "Best hotels in Paris for families"

**Response Includes:**
- trip.com booking recommendations
- Optimal booking timeline
- Price tips and strategies
- Accommodation suggestions from Lonely Planet

#### 4. **experience_suggestions**
User wants activity recommendations.

**Examples:**
- "What experiences should I try in Bali?"
- "Top things to do in Tokyo for foodies"
- "Adventure activities in New Zealand"

**Response Includes:**
- Specific experiences bookable on trip.com
- Lonely Planet recommended activities
- Now Boarding article insights
- Timing and booking tips

#### 5. **destination_info**
User asking about a specific place.

**Examples:**
- "Tell me about things to do in Singapore"
- "What's Barcelona like?"
- "Best neighborhoods to stay in Tokyo"

**Response Includes:**
- Key attractions and areas
- Cultural insights
- Practical tips
- Lonely Planet destination guide references

## Information Extraction

The AI extracts these details from user messages:

### Core Fields

| Field | Description | Examples |
|-------|-------------|----------|
| **destination** | Target city/country | "Tokyo", "Thailand", "Europe" |
| **travel_dates** | When they're traveling | "next month", "December", "summer 2026" |
| **duration** | Trip length | "5 days", "2 weeks", "weekend" |
| **budget** | Spending level | "budget", "mid-range", "luxury" |
| **preferences** | Activity types | ["beach", "culture", "adventure", "food"] |
| **interests** | Specific interests | ["photography", "hiking", "nightlife"] |
| **traveler_type** | Who's going | "solo", "couple", "family", "group" |

### Example Extraction

**User Input:**
```
"Plan a 10-day trip to Japan for a family with kids, mid-range budget, 
we love food and culture"
```

**Extracted Data:**
```json
{
  "intent": "itinerary_request",
  "destination": "Japan",
  "duration": "10 days",
  "budget": "mid-range",
  "preferences": ["food", "culture"],
  "traveler_type": "family"
}
```

## Destination Handling

### Supported Destinations (44 Cities)

The chatbot ONLY creates itineraries for these Southeast Asian destinations accessible from Singapore/Changi Airport:

**Indonesia**: Balikpapan, Denpasar (Bali), Jakarta, Lombok, Majalengka, Makassar, Manado, Medan, Surabaya, Yogyakarta

**Malaysia**: Bandar Seri Begawan, Ipoh, Kota Bharu, Kota Kinabalu, Kuala Lumpur, Kuantan, Kuching, Langkawi, Malacca, Miri, Sibu

**Thailand**: Bangkok, Chiang Mai, Hat Yai, Koh Samui, Krabi, Phuket

**Philippines**: Cebu, Clark, Davao, Iloilo, Manila

**Vietnam**: Da Nang, Hanoi, Ho Chi Minh City, Phu Quoc

**Cambodia**: Phnom Penh, Siem Reap

**Myanmar**: Yangon

**Laos**: Vientiane

**East Timor**: Dili

### 🌍 Unsupported Destination Handling

When a user requests a destination NOT in the supported list (e.g., Tokyo, Paris, Maldives, Dubai):

1. **Appreciate** the user's choice positively
2. **Explain** that we specialize in Southeast Asian destinations from Changi Airport
3. **Provide clickable chip buttons** with popular supported destinations
4. **Offer categories** (Beach, City, Culture, Nature) for exploration

**Example Response:**
> That sounds like a wonderful destination! 🌍 Paris is definitely a beautiful place to visit.
> 
> However, I specialize in curating personalized itineraries for **Southeast Asian destinations** accessible from Singapore/Changi Airport.
> 
> [Chip buttons: Bangkok, Bali, Kuala Lumpur, Phuket, etc.]

### 🌤️ Vague/Weather-Based Recommendations

When users request destinations based on vague preferences (scenic views, weather, climate):

**RULE**: Always ask for **travel dates/month** FIRST before making weather-based recommendations.

**Vague Requests (require dates first):**
- "I want to go somewhere with nice beaches"
- "Recommend a destination with good weather"
- "I'm looking for scenic mountain views"
- "Where should I go for cool weather?"

**Response Format:**
> I'd love to help you find the perfect destination! 🌏
> 
> To give you the best recommendation based on your preference, I need to know **when you're planning to travel**. Different destinations have different optimal seasons!
> 
> 📅 **When are you planning to travel?** (e.g., "January 2026", "March", "next month")

**After receiving travel month**, provide weather-appropriate recommendations with chip buttons organized by:
- ☀️ Sunny & Tropical destinations
- 🌤️ Warm & Pleasant destinations  
- 🌿 Cooler & Refreshing destinations
- 🏖️ Beach & Island destinations
- 🏔️ Mountains & Nature destinations
- 🏛️ Cultural & Heritage destinations

## Integration with External Resources

### 🎫 trip.com Integration

**Purpose:** Booking platform for flights, hotels, and experiences

**How It's Used:**
- Every itinerary includes trip.com booking recommendations
- Direct links provided in response footer
- Mentioned for specific bookings (flights, hotels, activities)

**Example in Response:**
```
"Book your flights on trip.com for the best deals..."
"Reserve this experience on trip.com..."
"Check trip.com for hotel options in this area..."
```

### 📚 Lonely Planet Integration

**Purpose:** World-class destination expertise and travel guides

**How It's Referenced:**
- Destination recommendations cite Lonely Planet insights
- Best practices and cultural tips reference LP guides
- Neighborhood and attraction info based on LP expertise

**Example in Response:**
```
"According to Lonely Planet, Shibuya is perfect for first-time visitors..."
"Lonely Planet recommends visiting during cherry blossom season..."
"As featured in Lonely Planet's Tokyo guide..."
```

**URL:** https://www.lonelyplanet.com/

### ✈️ Now Boarding Changi Integration

**Purpose:** Singapore-specific travel insights and Changi Airport content

**How It's Referenced:**
- Singapore travelers get Now Boarding article links
- Changi-specific tips and guides included
- Relevant destination insights from Singapore perspective

**Example in Response:**
```
"Check out this Now Boarding article about Tokyo food scenes..."
"Now Boarding recommends these visa-free destinations from Singapore..."
"Read more on Now Boarding: https://nowboarding.changiairport.com/..."
```

**URL:** https://nowboarding.changiairport.com/

## Response Structure

### Itinerary Format

```
📍 DESTINATION OVERVIEW
Brief intro and highlights

🗓️ DAY 1: [Theme]
☀️ Morning: Activity + location + tips
🌤️ Afternoon: Activity + restaurant suggestion
🌙 Evening: Activity + booking info

🗓️ DAY 2: [Theme]
...

💡 PRACTICAL TIPS
- Transportation
- Best time to visit
- Money-saving tips

🎫 BOOKING RECOMMENDATIONS
Links to trip.com, Lonely Planet, Now Boarding

---
Call-to-action footer with booking links
```

### Booking CTA Footer

Every relevant response includes:

```html
<div style='background: linear-gradient(...); ...'>
🎫 Ready to Book Your Trip?
Visit trip.com for flights, hotels, and experiences
📚 Explore Lonely Planet for in-depth destination guides
✈️ Read Now Boarding for Singapore travel insights
</div>
```

## Example User Journeys

### Journey 1: Complete Itinerary Request

**User:** "Plan a 5-day trip to Tokyo with focus on food and culture"

**System Process:**
1. Classifies as `itinerary_request`
2. Extracts: destination="Tokyo", duration="5 days", preferences=["food", "culture"]
3. Generates day-by-day plan:
   - Day 1: Arrival + Shibuya exploration
   - Day 2: Tsukiji Market + cultural sites
   - Day 3: Traditional Tokyo + temples
   - Day 4: Modern Tokyo + shopping
   - Day 5: Day trip options
4. Includes restaurant recommendations per meal
5. References Lonely Planet Tokyo guide
6. Adds trip.com booking links
7. Includes Now Boarding Tokyo articles

**Response Length:** ~800-1200 words with structured format

### Journey 2: Destination Inspiration

**User:** "Weekend getaway ideas from Singapore for families"

**System Process:**
1. Classifies as `destination_inspiration`
2. Extracts: duration="weekend", traveler_type="family", preferences=["family-friendly"]
3. Suggests 4-5 destinations:
   - Kuala Lumpur (Kid-friendly attractions)
   - Bali (Beach resorts with kids' clubs)
   - Phuket (Family beaches)
   - Bangkok (Theme parks + culture)
4. Each includes "why it's perfect for families"
5. References Lonely Planet family travel guides
6. Links to Now Boarding family travel articles
7. Booking CTA to trip.com

**Response Length:** ~500-700 words

### Journey 3: Booking Assistance

**User:** "Help me book a romantic trip to Bali for 7 days"

**System Process:**
1. Classifies as `booking_assistance`
2. Extracts: destination="Bali", duration="7 days", preferences=["romantic"]
3. Provides booking guidance:
   - Recommended romantic areas (Ubud, Seminyak)
   - Hotel suggestions with trip.com links
   - Flight booking timeline
   - Experience bookings (spa, dining, tours)
4. References Lonely Planet Bali accommodations
5. Budget breakdown
6. Booking CTA with direct links

**Response Length:** ~400-600 words

## Technical Implementation

### Intent Classifier (`intent_classifier.py`)

```python
def classify_intent_with_gemini(message):
    """
    Uses Gemini LLM to classify intent and extract travel details
    Returns: dict with intent, destination, dates, preferences, etc.
    """
```

**Key Features:**
- Natural language understanding
- Multi-field extraction
- Flexible intent classification
- Fallback error handling

### Main Application (`app.py`)

**Enhanced Prompt Structure:**

```python
# For itinerary requests
prompt = f"""
{SYSTEM_PROMPT}
User Request: {message}
Context: {extracted_context}

Create detailed day-by-day itinerary with:
- Daily activities (morning/afternoon/evening)
- Restaurant recommendations
- Booking suggestions via trip.com
- Lonely Planet insights
- Now Boarding article references
"""
```

**Response Enhancement:**
- Adds booking CTA footer automatically
- Formats with HTML for better presentation
- Includes clickable links to trip.com, Lonely Planet, Now Boarding

## Best Practices

### For Itinerary Generation
1. ✅ Always structure by days
2. ✅ Include specific venue names
3. ✅ Add practical tips (timing, transport, booking)
4. ✅ Reference trip.com for bookings
5. ✅ Cite Lonely Planet for destination expertise
6. ✅ Link Now Boarding articles when relevant

### For Destination Inspiration
1. ✅ Suggest 3-5 destinations
2. ✅ Explain why each fits user's criteria
3. ✅ Include best time to visit
4. ✅ Reference Lonely Planet destination pages
5. ✅ Add booking CTA

### For Booking Assistance
1. ✅ Emphasize trip.com as booking platform
2. ✅ Provide timeline (book X weeks in advance)
3. ✅ Include budget considerations
4. ✅ Reference Lonely Planet accommodation tips
5. ✅ Add direct booking links

## Future Enhancements

### Planned Features
- [ ] Direct API integration with trip.com for real pricing
- [ ] Web scraping for latest Lonely Planet articles
- [ ] RSS feed integration with Now Boarding
- [ ] Multi-destination itineraries
- [ ] Budget calculator
- [ ] Packing list generator
- [ ] Weather forecasts
- [ ] Currency conversion
- [ ] Translation helper

### API Integrations (Future)
- **trip.com API**: Live flight/hotel prices
- **Lonely Planet API**: Real-time destination data
- **Now Boarding RSS**: Latest Singapore travel articles
- **Weather APIs**: Real-time weather forecasts
- **Currency APIs**: Live exchange rates

## Testing Scenarios

### Test Cases

1. **Simple Itinerary**
   - Input: "Plan a 3-day Tokyo trip"
   - Expected: 3-day structured plan with activities

2. **Complex Itinerary**
   - Input: "2-week Thailand trip, beaches and temples, mid-range, couple"
   - Expected: 14-day plan with beach/culture mix, romantic activities

3. **Destination Inspiration**
   - Input: "Best adventure destinations?"
   - Expected: 4-5 adventure-focused destinations

4. **Booking Help**
   - Input: "Book flights to Paris"
   - Expected: trip.com guidance, booking timeline, tips

5. **Experience Suggestions**
   - Input: "What to do in Bali?"
   - Expected: Activity list with trip.com/Lonely Planet references

## Summary

The Travel Itinerary Planner successfully integrates:
- ✅ Gemini AI for natural language understanding
- ✅ trip.com for booking platform
- ✅ Lonely Planet for destination expertise  
- ✅ Now Boarding for Singapore travel insights
- ✅ Comprehensive intent classification
- ✅ Detailed, actionable itineraries
- ✅ Beautiful, user-friendly interface

This creates a complete travel planning experience from inspiration to booking!

