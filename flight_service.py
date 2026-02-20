import requests
import logging
import os
from datetime import datetime, timedelta


# Set up logger for flight service
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# If no handler exists, add a console handler
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Changi Airport GraphQL API Configuration
CHANGI_API_URL = os.getenv("CHANGI_API_URL", "https://vjk4bub6rbbjrflwlroku34myi.appsync-api.ap-southeast-1.amazonaws.com/graphql")
CHANGI_API_KEY = os.getenv("CHANGI_API_KEY", "da2-rkyh2gb2kvft3oco3l6eaqmlb4")


def fetch_flight_info(flight_number, direction="DEP"):
    """
    Fetch flight information from Changi Airport GraphQL API.
    
    Args:
        flight_number: Flight number (e.g., "SQ222", "BA456")
        direction: "DEP" for departure or "ARR" for arrival
        
    Returns:
        dict with flight information or None if not found
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CHANGI_API_KEY
    }
    
    query = f'''
    query {{
        getFlights(direction: "{direction}", flight_number: "{flight_number}") {{
            flights {{
                flight_number
                scheduled_date
                terminal
                scheduled_time
                direction
                airport_details {{
                    name
                    city
                    country_code
                }}
                airline_details {{
                    name
                    logo_url
                }}
                display_timestamp
                via_airport_details {{
                    city
                }}
                display_gate
                display_belt
                pick_up_door
                status_mapping {{
                    details_status_en
                }}
            }}
        }}
    }}
    '''
    
    try:
        response = requests.post(
            CHANGI_API_URL,
            headers=headers,
            json={"query": query},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        logging.info(f"[Flight API] Fetched data for {flight_number}: {data}")
        
        result = data.get("data", {}).get("getFlights")
        if not result:
            logging.error(f"[Flight API] No 'getFlights' in response for '{flight_number}'")
            return None
        
        flights = result.get("flights", [])
        if not flights:
            logging.info(f"[Flight API] No flights found for '{flight_number}'")
            return None
        
        return flights[0]
        
    except requests.exceptions.RequestException as e:
        logging.error(f"[Flight API] Request error: {e}")
        return None
    except Exception as e:
        logging.error(f"[Flight API] Unexpected error: {e}")
        return None


def try_both_directions(flight_number):
    """
    Try to fetch flight info from both departure and arrival.
    
    Args:
        flight_number: Flight number to search
        
    Returns:
        dict with flight info or None
    """
    # Try departure first
    flight = fetch_flight_info(flight_number, "DEP")
    if flight:
        return flight
    
    # Try arrival if not found in departures
    flight = fetch_flight_info(flight_number, "ARR")
    return flight


def map_destination_to_airport_code(destination):
    """
    Map destination city name to airport code for Trip.com URLs.
    
    Args:
        destination: City name (e.g., "Kuala Lumpur", "Bangkok")
    
    Returns:
        Airport code string (e.g., "kul", "bkk")
    """
    # Normalize destination name
    dest_lower = destination.lower().strip()
    
    # Airport code mapping for common Southeast Asian destinations
    airport_map = {
        # Malaysia
        "kuala lumpur": "kul",
        "langkawi": "lgk",
        "penang": "pen",
        "kota kinabalu": "bki",
        "kuching": "kch",
        "ipoh": "iph",
        "malacca": "mkz",
        # Thailand
        "bangkok": "bkk",
        "phuket": "hkt",
        "chiang mai": "cnx",
        "krabi": "kbv",
        "koh samui": "usm",
        "hat yai": "hdv",
        # Indonesia
        "jakarta": "cgk",
        "bali": "dps",
        "denpasar": "dps",
        "surabaya": "sub",
        "yogyakarta": "jog",
        "medan": "kno",
        "bandung": "bdg",
        # Philippines
        "manila": "mnl",
        "cebu": "ceb",
        "davao": "dvo",
        # Vietnam
        "ho chi minh city": "sgn",
        "hanoi": "han",
        "da nang": "dad",
        "phu quoc": "pqc",
        # Cambodia
        "phnom penh": "pnh",
        "siem reap": "rep",
        # Myanmar
        "yangon": "rgn",
        # Japan
        "tokyo": "tyo",
        "osaka": "osa",
        "kyoto": "uky",
        # South Korea
        "seoul": "sel",
        "busan": "pus",
        # China
        "hong kong": "hkg",
        "taipei": "tpe",
        "shanghai": "sha",
        "beijing": "pek",
        # India
        "mumbai": "bom",
        "delhi": "del",
        "bangalore": "blr",
        # Australia
        "sydney": "syd",
        "melbourne": "mel",
        # Others
        "singapore": "sin",
    }
    
    # Direct match
    if dest_lower in airport_map:
        return airport_map[dest_lower]
    
    # Partial match (e.g., "Kuala Lumpur" contains "kuala")
    for key, code in airport_map.items():
        if key in dest_lower or dest_lower in key:
            return code
    
    # Default: try to extract first 3 letters or use "sin" as fallback
    logger.warning(f"[Flight Service] No airport code mapping found for '{destination}', using 'sin' as fallback")
    return "sin"


def search_flights_by_destination(destination, scheduled_dates, preferred_times=None, preferred_airline=None, limit=5):
    """
    Search flights from Singapore to destination for one or more dates.
    
    Args:
        destination: Destination city name (e.g., "Kuala Lumpur", "Bangkok")
        scheduled_dates: Single date string or list of dates in format "YYYY-MM-DD" (e.g., "2025-01-15" or ["2025-01-10", "2025-01-11"])
        preferred_times: Optional preferred departure time(s) - single string or list (e.g., "morning" or ["morning", "afternoon"])
        preferred_airline: Optional preferred airline code (e.g., "SQ", "MH")
        limit: Maximum number of flights to return across all dates
        
    Returns:
        list of flight dicts or empty list if not found
    """
    # Normalize dates to list
    if isinstance(scheduled_dates, str):
        scheduled_dates = [scheduled_dates]
    
    if not scheduled_dates:
        return []
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CHANGI_API_KEY
    }
    
    all_flights = []
    
    # Search for flights on each date
    for scheduled_date in scheduled_dates:
        # Build search query using the updated searchCA_v2 query structure
        query = f'''
        query searchAll {{
            searchCA_v2(text: "{destination}", category: FLIGHTS, page_size: 100, page_number: 1, filter: {{ terminal:"" direction:DEP scheduled_date: "{scheduled_date}" }})
            {{
                items {{
                    ... on Flight {{
                        flight_number
                        scheduled_date
                        airline
                        airport_details {{
                            name
                            name_zh
                            name_zh_hant
                            country_code
                            country
                            city_code
                            city
                        }}
                        airline_details {{
                            name
                            logo_url
                            name_zh
                            name_zh_hant
                            code
                        }}
                        via_airport_details {{
                            name
                            name_zh
                            name_zh_hant
                            country_code
                            country
                            city_code
                            city
                        }}
                        status_mapping {{
                            belt_status_en
                            belt_status_zh
                            details_status_en
                            details_status_zh
                            listing_status_en
                            listing_status_zh
                            show_gate
                            status_text_color
                        }}
                        slave_flights
                        airport
                        direction
                        display_gate
                        current_gate
                        display_timestamp
                        flight_status
                        pick_up_door
                        scheduled_time
                        terminal
                        via
                        check_in_row
                        display_belt
                    }}
                }}
                total
            }}
        }}
        '''
    
        try:
            logger.info(f"[Flight API] ===== SEARCHING DATE: {scheduled_date} =====")
            logger.info(f"[Flight API] Destination: '{destination}'")
            logger.info(f"[Flight API] Scheduled Date: '{scheduled_date}'")
            logger.info(f"[Flight API] Preferred Times: {preferred_times}")
            logger.info(f"[Flight API] Preferred Airline: '{preferred_airline}'")
            logger.info(f"[Flight API] API URL: {CHANGI_API_URL}")
            logger.info(f"[Flight API] Query:\n{query}")
            
            response = requests.post(
                CHANGI_API_URL,
                headers=headers,
                json={"query": query},
                timeout=10,
                verify=False  # Disable SSL verification for development
            )
            
            logger.info(f"[Flight API] Response status code: {response.status_code}")
            logger.info(f"[Flight API] Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"[Flight API] Response received successfully")
            logger.info(f"[Flight API] Response keys: {list(data.keys())}")
            if 'errors' in data:
                logger.error(f"[Flight API] GraphQL ERRORS FOUND for {scheduled_date}: {data['errors']}")
                continue
            
            # Get results from searchCA_v2 query
            data_obj = data.get("data", {})
            logger.info(f"[Flight API] Data object keys: {list(data_obj.keys())}")
            result = data_obj.get("searchCA_v2")
            if not result:
                logger.warning(f"[Flight API] ⚠️ No 'searchCA_v2' in response.data for {scheduled_date}")
                logger.warning(f"[Flight API] Available keys in data: {list(data_obj.keys())}")
                continue
            
            # Extract flights from items array
            items = result.get("items", [])
            logger.info(f"[Flight API] Found {len(items)} items for {scheduled_date}")
            if items:
                logger.info(f"[Flight API] First item structure: {list(items[0].keys()) if items[0] else 'Empty'}")
            
            # Filter for departure flights only (direction: "DEP")
            date_flights = [item for item in items if item.get("direction") == "DEP"]
            logger.info(f"[Flight API] Found {len(date_flights)} departure flights for {scheduled_date}")
            if date_flights:
                logger.info(f"[Flight API] Sample flight: {date_flights[0].get('flight_number', 'N/A')} - {date_flights[0].get('display_timestamp', 'N/A')}")
            
            # Add to combined results
            all_flights.extend(date_flights)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[Flight API] ❌ Request error for {scheduled_date}: {e}")
            continue
        except Exception as e:
            logger.error(f"[Flight API] ❌ Unexpected error for {scheduled_date}: {e}")
            continue
    
    # If no flights found across all dates
    if not all_flights:
        logger.warning(f"[Flight API] ⚠️ No flights found for {destination} on any of the dates: {scheduled_dates}")
        return []
    
    logger.info(f"[Flight API] ✅ Total flights found across all dates: {len(all_flights)}")
    
    logger.info(f"[Flight API] ✅ Total flights found across all dates before filtering: {len(all_flights)}")
    
    # Filter by preferred times if specified
    if preferred_times:
        logger.info(f"[Flight API] Filtering by preferred times: {preferred_times}")
        filtered_flights = filter_flights_by_time(all_flights, preferred_times)
        if filtered_flights:
            logger.info(f"[Flight API] After time filtering: {len(filtered_flights)} flights")
            all_flights = filtered_flights
        else:
            logger.warning(f"[Flight API] No flights matched preferred times, returning all flights")
    
    # Filter by preferred airline if specified
    if preferred_airline:
        logger.info(f"[Flight API] Filtering by preferred airline: {preferred_airline}")
        filtered_flights = [f for f in all_flights if f.get("flight_number", "").startswith(preferred_airline)]
        if filtered_flights:
            logger.info(f"[Flight API] After airline filtering: {len(filtered_flights)} flights")
            all_flights = filtered_flights
        else:
            logger.warning(f"[Flight API] No flights matched preferred airline, returning all flights")
    
    # Sort by scheduled time (earlier flights first) and limit results
    try:
        all_flights.sort(key=lambda x: x.get("display_timestamp", x.get("scheduled_time", "")))
    except Exception as e:
        logger.warning(f"[Flight API] Error sorting flights: {e}")
    
    final_flights = all_flights[:limit]
    logger.info(f"[Flight API] ✅ Returning {len(final_flights)} flights (limit: {limit})")
    return final_flights


def filter_flights_by_time(flights, preferred_times):
    """
    Filter flights by preferred time(s) of day.
    
    Args:
        flights: List of flight dicts
        preferred_times: Single string or list of strings (e.g., "morning" or ["morning", "afternoon"])
                         If list, matches flights to ANY of the times (OR logic)
    
    Returns:
        Filtered list of flights
    """
    # Normalize to list
    if isinstance(preferred_times, str):
        preferred_times = [preferred_times]
    
    if not preferred_times:
        return flights
    
    filtered = []
    
    for flight in flights:
        scheduled_time = flight.get("scheduled_time", "")
        display_timestamp = flight.get("display_timestamp", "")
        
        # Extract hour from timestamp
        try:
            if display_timestamp:
                dt_obj = datetime.strptime(display_timestamp, "%Y-%m-%d %H:%M")
                hour = dt_obj.hour
            elif scheduled_time:
                # Parse scheduled_time format (HH:MM)
                hour = int(scheduled_time.split(":")[0])
            else:
                continue
            
            # Check if flight matches ANY of the preferred times (OR logic)
            for time_pref in preferred_times:
                time_lower = time_pref.lower()
                
                # Match time preference
                if time_lower in ["morning", "early"] and 6 <= hour < 12:
                    filtered.append(flight)
                    break  # Found a match, no need to check other times
                elif time_lower in ["afternoon", "midday"] and 12 <= hour < 18:
                    filtered.append(flight)
                    break
                elif time_lower in ["evening", "night", "late"] and (hour >= 18 or hour < 6):
                    filtered.append(flight)
                    break
        except:
            continue
    
    return filtered if filtered else flights  # Return original if no matches


def format_flight_selection_card(flight_data, index=0):
    """
    Format flight data into a selectable HTML card for flight selection.
    
    Args:
        flight_data: Flight information dict from API
        index: Index for selection (used in onclick handler)
        
    Returns:
        str: HTML formatted selectable flight card
    """
    if not flight_data:
        return ""
    
    flight_number = flight_data.get("flight_number", "N/A")
    terminal = flight_data.get("terminal", "N/A")
    direction = flight_data.get("direction", "DEP")
    
    # Airport details - handle new structure
    airport_info = flight_data.get("airport_details", {})
    city = airport_info.get("city", airport_info.get("name", "Unknown"))
    country = airport_info.get("country_code", "")
    
    # Airline details - handle new structure
    airline_info = flight_data.get("airline_details", {})
    airline_name = airline_info.get("name", "")
    airline_logo = airline_info.get("logo_url", "")
    
    # Status and times - handle new structure
    status_mapping = flight_data.get("status_mapping", {})
    status = status_mapping.get("details_status_en", status_mapping.get("listing_status_en", "Scheduled"))
    scheduled_time = flight_data.get("scheduled_time", "N/A")
    
    # Format timestamp
    raw_ts = flight_data.get("display_timestamp")
    arrival_time = None
    try:
        if raw_ts:
            dt_obj = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M")
            display_timestamp = dt_obj.strftime("%a, %d %b • %H:%M")
            # Extract hour for arrival time calculation
            hour = dt_obj.hour
            arrival_time = f"{hour:02d}:{dt_obj.minute:02d}"
    except:
        display_timestamp = raw_ts or scheduled_time
    
    # Gate info
    gate = flight_data.get("display_gate", flight_data.get("current_gate", "-"))
    
    # Via airport - handle new structure
    via_airport = flight_data.get("via_airport_details", {})
    via_text = f" (via {via_airport.get('city', via_airport.get('name', ''))})" if via_airport and (via_airport.get('city') or via_airport.get('name')) else ""
    
    route = f"Singapore &#8594; {city}{via_text}"
    
    # Build selectable HTML card
    html = f"""
    <div class='flight-selection-card' onclick='selectFlight({index}, "{flight_number}", "{arrival_time or scheduled_time}")' data-flight-index='{index}'>
        <div class='flight-header'>
            <div class='flight-info-block'>
                <div class='flight-number'>
                    {f"<img src='{airline_logo}' class='airline-logo' alt='Airline'/>" if airline_logo else ""}
                    <strong>{flight_number}</strong>
                    {f"<span class='airline-name'>{airline_name}</span>" if airline_name else ""}
                </div>
                <div class='flight-route'>{route}</div>
            </div>
            <div class='flight-status' style='background: {"#4caf50" if "On Time" in status else "#ff9800"}; color: white; padding: 5px 12px; border-radius: 15px; font-size: 0.85em;'>{status}</div>
        </div>
        
        <div class='flight-details'>
            <div class='flight-row'>
                <div class='flight-label'>🕐 <strong>Departure</strong></div>
                <div class='flight-value'>{display_timestamp}</div>
            </div>
            <div class='flight-row'>
                <div class='flight-label'>🛫 <strong>Terminal</strong></div>
                <div class='flight-value'>T{terminal}</div>
            </div>
            {f'<div class="flight-row"><div class="flight-label">🚪 <strong>Gate</strong></div><div class="flight-value">{gate}</div></div>' if gate != "-" else ""}
        </div>
        <div class='flight-select-indicator'>Click to select</div>
    </div>
    """
    
    return html


def format_flight_card(flight_data):
    """
    Format flight data into an HTML card for display.
    
    Args:
        flight_data: Flight information dict from API
        
    Returns:
        str: HTML formatted flight card
    """
    if not flight_data:
        return "❌ Flight not found."
    
    flight_number = flight_data.get("flight_number", "N/A")
    terminal = flight_data.get("terminal", "N/A")
    direction = flight_data.get("direction", "DEP")
    
    # Airport details
    airport_info = flight_data.get("airport_details", {})
    city = airport_info.get("city", airport_info.get("name", "Unknown"))
    country = airport_info.get("country_code", "")
    
    # Airline details
    airline_info = flight_data.get("airline_details", {})
    airline_logo = airline_info.get("logo_url", "")
    
    # Status and times
    status = flight_data.get("status_mapping", {}).get("details_status_en", "Scheduled")
    scheduled_time = flight_data.get("scheduled_time", "N/A")
    
    # Format timestamp
    raw_ts = flight_data.get("display_timestamp")
    try:
        dt_obj = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M")
        display_timestamp = dt_obj.strftime("%a, %d %b • %H:%M")
    except:
        display_timestamp = raw_ts or scheduled_time
    
    # Gate/Belt info
    gate = flight_data.get("display_gate", "-")
    belt = flight_data.get("display_belt", "-")
    
    # Via airport
    via_airport = flight_data.get("via_airport_details", {})
    via_text = f" (via {via_airport.get('city')})" if via_airport else ""
    
    # Determine direction label
    direction_label = "Arrival" if direction == "ARR" else "Departure"
    route = f"{city} &#8594; Singapore{via_text}" if direction == "ARR" else f"Singapore &#8594; {city}{via_text}"
    
    # Build HTML card
    html = f"""
    <div class='flight-card'>
        <div class='flight-header'>
            <div class='flight-info-block'>
                <div class='flight-number'>
                    {f"<img src='{airline_logo}' class='airline-logo' alt='Airline'/>" if airline_logo else ""}
                    <strong>{flight_number}</strong>
                </div>
                <div class='flight-route'>{route}</div>
            </div>
            <div class='flight-status' style='background: {"#4caf50" if "On Time" in status else "#ff9800"}; color: white; padding: 5px 12px; border-radius: 15px; font-size: 0.85em;'>{status}</div>
        </div>
        
        <div class='flight-details'>
            <div class='flight-row'>
                <div class='flight-label'>🕐 <strong>{direction_label}</strong></div>
                <div class='flight-value'>{display_timestamp}</div>
            </div>
            <div class='flight-row'>
                <div class='flight-label'>🛫 <strong>Terminal</strong></div>
                <div class='flight-value'>T{terminal}</div>
            </div>
            <div class='flight-row'>
                <div class='flight-label'>🚪 <strong>{"Gate" if direction == "DEP" else "Belt"}</strong></div>
                <div class='flight-value'>{gate if direction == "DEP" else belt}</div>
            </div>
        </div>
    </div>
    """
    
    return html


def generate_trip_com_booking_url(departure_city_code, arrival_city_code, departure_date, return_date, passengers=1, trip_type='rt'):
    """
    Generate Trip.com booking URL for flights.
    
    Args:
        departure_city_code: Departure airport code (e.g., "sin" for Singapore)
        arrival_city_code: Arrival airport code (e.g., "kul" for Kuala Lumpur)
        departure_date: Departure date in format "YYYY-MM-DD"
        return_date: Return date in format "YYYY-MM-DD"
        passengers: Number of passengers (default: 1)
        trip_type: Trip type - "rt" for round trip, "ow" for one-way (default: "rt")
    
    Returns:
        str: Complete Trip.com booking URL
    """
    base_url = "https://sg.trip.com/flights/showfarefirst"
    
    params = {
        "dcity": departure_city_code,
        "acity": arrival_city_code,
        "ddate": departure_date,
        "rdate": return_date,
        "dairport": departure_city_code,
        "triptype": trip_type,
        "class": "y",  # Economy class
        "lowpricesource": "searchform",
        "quantity": str(passengers),
        "searchboxarg": "t",
        "nonstoponly": "off",
        "locale": "en-SG",
        "curr": "SGD"
    }
    
    # Build query string
    query_parts = [f"{key}={value}" for key, value in params.items()]
    query_string = "&".join(query_parts)
    
    url = f"{base_url}?{query_string}"
    logger.info(f"[Flight Service] Generated Trip.com URL: {url}")
    
    return url


def format_flight_options_for_itinerary(flights, destination, departure_date, duration):
    """
    Format flight options as HTML to be embedded in the itinerary.
    
    Args:
        flights: List of flight dicts (top 2-3 flights)
        destination: Destination city name (e.g., "Kuala Lumpur")
        departure_date: Departure date in format "YYYY-MM-DD"
        duration: Trip duration in days (e.g., "3" or "3 days")
    
    Returns:
        str: HTML formatted flight options section
    """
    if not flights:
        return ""
    
    # Extract duration as number
    duration_num = 3  # Default
    if isinstance(duration, str):
        import re
        match = re.search(r'(\d+)', duration)
        if match:
            duration_num = int(match.group(1))
    elif isinstance(duration, int):
        duration_num = duration
    
    # Calculate return date
    try:
        dep_date_obj = datetime.strptime(departure_date, "%Y-%m-%d")
        return_date_obj = dep_date_obj + timedelta(days=duration_num)
        return_date = return_date_obj.strftime("%Y-%m-%d")
    except:
        return_date = departure_date  # Fallback
    
    # Get airport codes
    arrival_code = map_destination_to_airport_code(destination)
    departure_code = "sin"  # Singapore
    
    html = '<div class="flight-options-section">'
    html += '<h3>✈️ Flight Options</h3>'
    html += '<p>Here are the best flight options for your trip:</p>'
    
    for idx, flight in enumerate(flights[:3], 1):  # Top 3 flights
        flight_number = flight.get("flight_number", "N/A")
        terminal = flight.get("terminal", "N/A")
        
        # Airport details
        airport_info = flight.get("airport_details", {})
        city = airport_info.get("city", airport_info.get("name", "Unknown"))
        
        # Airline details
        airline_info = flight.get("airline_details", {})
        airline_name = airline_info.get("name", "")
        airline_logo = airline_info.get("logo_url", "")
        
        # Status and times
        status_mapping = flight.get("status_mapping", {})
        status = status_mapping.get("details_status_en", status_mapping.get("listing_status_en", "Scheduled"))
        
        # Format timestamp
        raw_ts = flight.get("display_timestamp")
        try:
            if raw_ts:
                dt_obj = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M")
                display_timestamp = dt_obj.strftime("%a, %d %b • %H:%M")
                flight_departure_date = dt_obj.strftime("%Y-%m-%d")
            else:
                display_timestamp = flight.get("scheduled_time", "N/A")
                flight_departure_date = departure_date
        except:
            display_timestamp = flight.get("scheduled_time", "N/A")
            flight_departure_date = departure_date
        
        # Gate info
        gate = flight.get("display_gate", flight.get("current_gate", "-"))
        
        # Via airport
        via_airport = flight.get("via_airport_details", {})
        via_text = f" (via {via_airport.get('city', via_airport.get('name', ''))})" if via_airport and (via_airport.get('city') or via_airport.get('name')) else ""
        
        # Generate Trip.com URL for this flight
        trip_url = generate_trip_com_booking_url(
            departure_code,
            arrival_code,
            flight_departure_date,
            return_date,
            passengers=1,
            trip_type='rt'
        )
        
        # Flight card HTML with CSS classes for proper styling
        html += f'''
        <div class="flight-option-card">
            <div class="flight-option-header">
                <div class="flight-option-info">
                    <div class="flight-option-number">
                        {f'<img src="{airline_logo}" class="flight-airline-logo" alt="Airline"/>' if airline_logo else ''}
                        <strong>{flight_number}</strong>
                        {f'<span class="flight-airline-name">{airline_name}</span>' if airline_name else ''}
                    </div>
                    <div class="flight-option-route">Singapore → {city}{via_text}</div>
                </div>
                <div class="flight-status-badge" style="background: {"#4caf50" if "On Time" in status else "#ff9800"};">{status}</div>
            </div>
            <div class="flight-option-details">
                <div class="flight-detail-row">
                    <span class="flight-detail-label">🕐 <strong>Departure</strong></span>
                    <span class="flight-detail-value">{display_timestamp}</span>
                </div>
                <div class="flight-detail-row">
                    <span class="flight-detail-label">🛫 <strong>Terminal</strong></span>
                    <span class="flight-detail-value">T{terminal}</span>
                </div>
                <div class="flight-detail-row">
                    <span class="flight-detail-label">🚪 <strong>Gate</strong></span>
                    <span class="flight-detail-value">{gate if gate != "-" else "None"}</span>
                </div>
            </div>
            <a href="{trip_url}" target="_blank" class="flight-book-btn">Book on Trip.com →</a>
        </div>
        '''
    
    html += '</div>'
    
    return html

