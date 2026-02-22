"""
Agent Executor - Executes agent conversations
"""
import logging
import re
import requests
import urllib3
from typing import Dict, Optional, List, Any, Generator
from core.web.app_tools import session
from core.agents.agent_service import agent_service
from core.llm.llm_factory import LLMFactory
from core.agents.mcp_manager import mcp_manager
from core.prompts.prompt_loader import load_prompt

# Suppress SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class AgentExecutor:
    """Executes agent conversations"""
    
    def __init__(self, agent_id: str):
        """
        Initialize agent executor
        
        Args:
            agent_id: ID of the agent to execute
        """
        self.agent_id = agent_id
        self.agent_config = agent_service.get_agent(agent_id)
        
        if not self.agent_config:
            raise ValueError(f"Agent {agent_id} not found")
        
        # Initialize LLM client
        self.llm_client = LLMFactory.create_llm_client(
            provider=self.agent_config['llm_provider'],
            model=self.agent_config['llm_model']
        )

        logger.info(f"Initialized executor for agent: {agent_id}")
    
    def get_system_prompt(self) -> str:
        """Get the agent's system prompt"""
        # Check if prompt_file is specified
        prompt_file = self.agent_config.get('prompt_file')
        if prompt_file:
            prompt = load_prompt(prompt_file)
            if prompt:
                return prompt
        
        # Fall back to system_prompt if no file specified
        return self.agent_config.get('system_prompt', '')
    
    def get_agent_name(self) -> str:
        """Get the agent's name"""
        return self.agent_config.get('name', 'Assistant')
    
    def get_agent_description(self) -> str:
        """Get the agent's description"""
        return self.agent_config.get('description', '')
    
    # _handle_tool_calls method removed (replaced by native tool calling)
    
    def _execute_flight_search(self, params: Dict, session_context: Dict) -> Dict:
        """Execute flight search tool"""
        destination = params.get('destination')
        dates = params.get('dates', [])
        times = params.get('times', ['morning', 'afternoon', 'evening'])
        limit = params.get('limit', 3)
        
        logger.info(f"[Flight Search Tool] Searching flights: {destination}, {dates}")
        
        try:
            # Use MCP tool if enabled
            if mcp_manager.is_tool_enabled('flights.search'):
                result = mcp_manager.call_tool(
                    tool_name='flights.search',
                    arguments={
                        'destination': destination,
                        'scheduled_dates': dates,
                        'preferred_times': times,
                        'limit': limit
                    }
                )
                if result.get('success'):
                    # Store flights in session context
                    session_context['selected_flights'] = result.get('flights', [])
                    session_context['primary_departure_date'] = dates[0] if dates else None
                    session_context['destination'] = destination
                    logger.info(f"[Flight Search Tool] Found {len(result.get('flights', []))} flights")
                    return result
                else:
                    logger.warning(f"[Flight Search Tool] MCP search failed: {result.get('error')}")
                    return result
            else:
                # Fallback to direct call
                from changi_flight_service import search_flights_by_destination
                flights = search_flights_by_destination(
                    destination, 
                    dates,
                    preferred_times=times,
                    limit=limit
                )
                session_context['selected_flights'] = flights
                session_context['primary_departure_date'] = dates[0] if dates else None
                session_context['destination'] = destination
                return {
                    'success': True,
                    'flights': flights,
                    'count': len(flights)
                }
        except Exception as e:
            logger.error(f"[Flight Search Tool] Error: {e}")
            return {
                'success': False,
                'error': str(e),
                'flights': []
            }
    
    def _execute_fetch_articles(self, params: Dict, session_context: Dict) -> Dict:
        """Execute Now Boarding articles fetch tool"""
        destination = params.get('destination')
        limit = params.get('limit', 3)
        
        logger.info(f"[Fetch Articles Tool] Fetching articles for: {destination}")
        
        try:
            if mcp_manager.is_tool_enabled('nowboarding.fetch_articles'):
                result = mcp_manager.call_tool(
                    tool_name='nowboarding.fetch_articles',
                    arguments={
                        'destination': destination,
                        'limit': limit
                    }
                )
                return result
            else:
                # Fallback to direct method
                articles = self._fetch_nowboarding_articles(destination, limit)
                return {
                    'success': True,
                    'articles': articles,
                    'count': len(articles)
                }
        except Exception as e:
            logger.error(f"[Fetch Articles Tool] Error: {e}")
            return {
                'success': False,
                'error': str(e),
                'articles': []
            }
    
    def chat(self, user_message: str, session_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a chat conversation
        
        Args:
            user_message: User's message
            session_context: Optional session context (for conversation state)
        
        Returns:
            Response dictionary with 'response', 'success', etc.
        """
        try:
            # Initialize session context if not provided
            if session_context is None:
                session_context = session.get('context', {})
            
            # Check if this agent is a travel/itinerary agent
            agent_name_lower = self.get_agent_name().lower()
            agent_desc_lower = self.get_agent_description().lower()
            is_travel_agent = any(keyword in agent_name_lower or keyword in agent_desc_lower for keyword in [
                'travel', 'itinerary', 'trip planner', 'destination'
            ])
            
            # Check if this is likely a travel-related request (only for travel agents)
            # Prompt-driven: we don't validate fields, just detect travel intent
            user_lower = user_message.lower()
            travel_keywords = [
                'itinerary', 'trip', 'travel', 'visit', 'days', 'day trip',
                'schedule', 'itinerary for', 'plan a trip', 'create itinerary',
                'planning', 'plannig', 'plan', 'going to', 'want to go', 'looking to',
                'holiday', 'vacation', 'journey', 'destination'
            ]
            has_plan_keyword = 'plan' in user_lower or any(word in user_lower for word in ['going', 'visit', 'trip', 'travel'])
            is_travel_request = is_travel_agent and (any(keyword in user_lower for keyword in travel_keywords) or has_plan_keyword)
            
            # NOTE: All extraction logic moved to prompt
            # LLM will extract destination, duration, dates from conversation using prompt instructions
            # We only read from session_context (no auto-extraction)
            destination = session_context.get('destination')
            
            # Build the user prompt - let the prompt handle everything
            user_prompt = user_message
            
            # If it's a travel request, add HTML formatting instructions
            # The prompt will decide when to generate the itinerary based on its own rules
            html_formatting_instructions = ""  # Initialize to empty string
            if is_travel_request:
                # Check if we have all info - if so, explicitly tell LLM to generate itinerary NOW
                # Only require: destination, duration, and travel dates (removed holiday_type requirement)
                # CRITICAL: Properly validate travel_dates - must be non-empty string or non-empty list
                travel_date_valid = False
                current_destination = session_context.get('destination') or destination
                current_duration = session_context.get('duration')
                
                if session_context.get('travel_date'):
                    travel_date_valid = True
                elif session_context.get('travel_dates'):
                    travel_dates_list = session_context.get('travel_dates')
                    if isinstance(travel_dates_list, list) and len(travel_dates_list) > 0 and all(d for d in travel_dates_list):
                        travel_date_valid = True
                elif session_context.get('primary_departure_date'):
                    travel_date_valid = True
                
                has_all_required_info = bool(
                    current_destination and
                    current_duration and
                    travel_date_valid
                )
                
                # Also check if we're forcing itinerary generation (after flights found)
                force_generation = session_context.get('force_itinerary_generation', False)
                
                if has_all_required_info or force_generation:
                    if force_generation:
                        logger.info(f"[Agent Executor] 🚨 FORCING itinerary generation - flights found and all info available")
                        html_formatting_instructions = """

🚨🚨🚨 CRITICAL: You have ALL the required information AND flights have been found. You MUST generate the COMPLETE itinerary NOW in clean HTML format. 

DO NOT:
- Say "I'll generate" or "hold on" or "please wait"
- Ask for more information (preferred time, destination confirmation, etc.)
- Say "before we move on" or "now, before we create"
- Ask any questions

DO THIS IMMEDIATELY:
- Generate the full day-by-day itinerary RIGHT NOW
- Use the HTML structure below
- Include ALL days (e.g., if duration is 5 days, create Day 1, Day 2, Day 3, Day 4, Day 5)
- The flight options will automatically appear at the top - you don't need to mention them

Use this structure:

<div class="itinerary-intro">
A brief exciting intro paragraph with emojis
</div>

<div class="day-card">
<h3>🗓️ Day 1: Title</h3>
<div class="time-block">
<span class="time">🌅 Morning</span>
<strong>Activity Name</strong>
<p>Description of what to do, tips, etc.</p>
<a href="https://www.lonelyplanet.com/search?q=Activity+Name&sortBy=pois" target="_blank" class="booking-link">📚 Explore on Lonely Planet →</a>
</div>
<div class="time-block">
<span class="time">☀️ Afternoon</span>
<strong>Activity Name</strong>
<p>Description</p>
<a href="https://www.trip.com/global-search/searchlist/search/?keyword=Activity%20Name&from=home" target="_blank" class="booking-link">🎫 Book on Trip.com →</a>
</div>
<div class="time-block">
<span class="time">🌙 Evening</span>
<strong>Activity Name</strong>
<p>Description including dinner recommendation</p>
<a href="https://www.lonelyplanet.com/search?q=Activity+Name&sortBy=pois" target="_blank" class="booking-link">📚 Explore on Lonely Planet →</a>
</div>
</div>

FUNCTIONAL LINKING RULES:
- The system will automatically generate Lonely Planet and Trip.com links using MCP tools
- Include 1-2 booking links per day section (preferably Lonely Planet for exploration, Trip.com for booking)
- Links will be automatically formatted - you don't need to construct URLs manually
- Repeat the day-card structure for EACH day of the trip (e.g., if 5 days, create Day 1, Day 2, Day 3, Day 4, Day 5)
- DO NOT use markdown formatting (###, **, etc.). Use HTML only.
- Generate the complete itinerary NOW - do not delay or say you will generate it later.
- DO NOT ask questions - just generate the itinerary immediately.

🚨 CRITICAL REMINDER: Before formatting as HTML itinerary, you MUST have gathered ALL THREE required pieces of information:
1. Duration (number of days)
2. When (travel dates)
3. Destination

If you are missing ANY of these, DO NOT format as HTML itinerary. Instead, ask for the missing information conversationally.

**ONCE YOU HAVE ALL THREE (Duration, Travel Dates, Destination), IMMEDIATELY generate the full itinerary in HTML format. Do NOT ask for confirmation. Do NOT say "Let me know if that's correct". Do NOT ask any questions. Just generate the complete itinerary NOW. Do NOT ask for preferred departure time or any other information. Do NOT wait for flights. Generate the itinerary NOW.**
"""
                    else:
                        # has_all_required_info is True but force_generation is False
                        html_formatting_instructions = """

CRITICAL: You have ALL the required information (Duration, Travel Dates, Destination). Generate the COMPLETE itinerary NOW in clean HTML format. 

🚨 DO NOT ask for confirmation. DO NOT say "Let me know if that's correct". DO NOT say "I'll get started". DO NOT ask any questions. Just generate the full itinerary immediately.

Do NOT ask for preferred departure time. Do NOT say "I'll generate" or "hold on" - create the full day-by-day itinerary immediately.

🚨 MANDATORY: Each day-card MUST contain at least 2-3 time-block divs (Morning, Afternoon, Evening). DO NOT create empty day-card divs. Every day-card must have complete time-block content inside.

Use this EXACT structure:

<div class="itinerary-intro">
A brief exciting intro paragraph with emojis
</div>

<div class="day-card">
<h3>🗓️ Day 1: Title</h3>
<div class="time-block">
<span class="time">🌅 Morning</span>
<strong>Activity Name</strong>
<p>Description of what to do, tips, etc.</p>
<a href="https://www.lonelyplanet.com/search?q=Activity+Name&sortBy=pois" target="_blank" class="booking-link">📚 Explore on Lonely Planet →</a>
</div>
<div class="time-block">
<span class="time">☀️ Afternoon</span>
<strong>Activity Name</strong>
<p>Description</p>
<a href="https://www.trip.com/global-search/searchlist/search/?keyword=Activity%20Name&from=home" target="_blank" class="booking-link">🎫 Book on Trip.com →</a>
</div>
<div class="time-block">
<span class="time">🌙 Evening</span>
<strong>Activity Name</strong>
<p>Description including dinner recommendation</p>
<a href="https://www.lonelyplanet.com/search?q=Activity+Name&sortBy=pois" target="_blank" class="booking-link">📚 Explore on Lonely Planet →</a>
</div>
</div>

FUNCTIONAL LINKING RULES:
- The system will automatically generate Lonely Planet and Trip.com links using MCP tools
- Include 1-2 booking links per day section (preferably Lonely Planet for exploration, Trip.com for booking)
- Links will be automatically formatted - you don't need to construct URLs manually
- Repeat the day-card structure for each day. Use emojis appropriately.
- DO NOT use markdown formatting (###, **, etc.). Use HTML only.

NOTE: Once you have Duration, Travel Dates, and Destination, IMMEDIATELY format as HTML itinerary. Do NOT ask for confirmation. Do NOT say "Let me know if that's correct". Do NOT ask any questions. Just generate the complete itinerary NOW. Do NOT ask for preferred departure time or any other information. Generate it NOW.
"""
                # html_formatting_instructions is already set above
            # If not a travel request or conditions not met, html_formatting_instructions remains empty string
            
            # Add formatting instructions to user prompt
            user_prompt = user_message + html_formatting_instructions
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_prompt}
            ]
            
            # Add conversation history if available
            if 'conversation_history' in session_context:
                # Add more messages for better context (last 10 messages = 5 exchanges)
                history = session_context['conversation_history'][-10:]  # Last 10 messages
                for msg in history:
                    messages.insert(-1, msg)  # Insert before user message
            
            # NOTE: Auto-extraction and auto-trigger logic removed
            # The LLM now handles extraction and decides when to call tools via prompts
            
            # Generate response
            # Get available tools for the LLM
            llm_tools = list(mcp_manager.tools.values())
            logger.info(f"[Agent Executor] Available tools for LLM: {[t['name'] for t in llm_tools]}")
            
            # Generate response
            logger.info(f"Generating response for agent {self.agent_id}")
            
            # Initial LLM call
            response_data = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=4096,
                tools=llm_tools
            )
            
            # Handle potential null response
            if response_data is None:
                logger.error("[Agent Executor] LLM returned None")
                return {"response": "I encountered an error. Please try again.", "success": False}
                
            # Check if response is a string (text) or dict (function call)
            response_text = ""
            if isinstance(response_data, str):
                response_text = response_data
            
            # Handle tool calls loop
            max_tool_iterations = 5
            tool_iteration = 0
            
            while tool_iteration < max_tool_iterations:
                # If response is text, we're done (unless it happens to contain old-style regex, which we're deprecating)
                if isinstance(response_data, str):
                    response_text = response_data
                    break
                    
                # If response is a function call
                if isinstance(response_data, dict) and "function_call" in response_data:
                    function_call = response_data["function_call"]
                    mcp_tool_name = function_call.get("name")
                    mcp_tool_args = function_call.get("arguments", {})
                    
                    logger.info(f"[Agent Executor] 🛠️ Processing tool call: {mcp_tool_name}")
                    logger.info(f"[Agent Executor] Args: {mcp_tool_args}")

                    # Parse tool name (format: toolid_funcname)
                    # We need to find the matching tool config
                    # Heuristic: split by first underscore, but some tool IDs have underscores
                    # Better: check known tool IDs



                    if not mcp_manager.is_tool_enabled(mcp_tool_name) :
                        error_msg = f"Unknown tool: {mcp_tool_name}"
                        logger.error(error_msg)
                        # Feed error back to LLM
                        messages.append({"role": "assistant", "content": None, "function_call": function_call}) # Track call?
                        # Actually standard Gemini chat flow usually expects function response
                        # For simplicity in this loop, we mimic the tool result message
                        messages.append({"role": "user", "content": f"Tool '{mcp_tool_name}' execution failed: {error_msg}"})
                    else:
                        # Execute tool
                        try:
                            # Parse args if they are string (Gemini sometimes returns dict, sometimes string? Usually dict from our provider)
                            if isinstance(mcp_tool_args, str):
                                import json
                                try:
                                    mcp_tool_args = json.loads(mcp_tool_args)
                                except:
                                    pass # Keep as string if not json
                                    
                            result = mcp_manager.call_tool(
                                tool_name=mcp_tool_name,
                                arguments=mcp_tool_args
                            )
                            
                            # Store context if needed (flight search)
                            if mcp_tool_name == 'flights.search':
                                    session_context['selected_flights'] = result.get('flights', [])
                                    session_context['destination'] = mcp_tool_args.get('destination')
                                    # Normalize dates
                                    dates_arg = mcp_tool_args.get('scheduled_dates', [])
                                    if isinstance(dates_arg, str): dates_arg = [dates_arg]
                                    session_context['primary_departure_date'] = dates_arg[0] if dates_arg else None
                                    
                                    # Set force_itinerary_generation flag to True after flight search success
                                    session_context['force_itinerary_generation'] = True
                                    logger.info(f"[Agent Executor] ✅ Set force_itinerary_generation=True after flight search")

                            # Store articles if fetched (for use in non-itinerary responses)
                            elif mcp_tool_name == 'nowboarding.fetch_articles':
                                if result.get('success'):
                                    session_context['recent_articles'] = result.get('articles', [])

                            # Format result for LLM
                            import json
                            result_str = json.dumps(result, default=str)
                            
                            logger.info(f"[Agent Executor] Tool '{mcp_tool_name}' execution success.")
                            logger.info(f"[Agent Executor] Result (first 1000 chars): {result_str[:1000]}")
                            if len(result_str) > 1000:
                                logger.info(f"[Agent Executor] ... (truncated, total length: {len(result_str)})")
                            
                            # Append interaction to history/messages
                            # Note: To correctly maintain conversation state with Gemini, we should ideally send the function response 
                            # as a specific "function_response" part. 
                            # However, our abstraction layer uses a list of dicts. 
                            # We'll treat the function result as a SYSTEM or USER message for the LLM to digest.
                            # A common pattern for generic generic adaptation:
                            # 1. Assistant: Function Call
                            # 2. User: Function Result
                            
                            messages.append({"role": "user", "content": f"Function '{mcp_tool_name}' result:\n{result_str}"})
                            
                        except Exception as e:
                            logger.error(f"[Agent Executor] Tool execution error: {e}")
                            messages.append({"role": "user", "content": f"Function '{mcp_tool_name}' failed: {str(e)}"})
                    
                    # Get next response
                    response_data = self.llm_client.chat_completion(
                        messages=messages,
                        temperature=0.7,
                        max_tokens=4096,
                        tools=llm_tools
                    )
                    
                    tool_iteration += 1
                else:
                    # Unknown response type or end of conversation
                    break
            
            if tool_iteration >= max_tool_iterations:
                logger.warning("[Agent Executor] Max tool iterations reached")
                if isinstance(response_data, dict):
                    response_text = "I'm sorry, I'm getting stuck in a loop of operations. Please try again."
                
            # Clean up markdown code blocks if present
            # Assign final text response
            if isinstance(response_data, str):
                response_text = response_data
            
            # Clean up standard markdown
            response_text = response_text.strip()
            if response_text.startswith('```html'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Legacy regex tool handling REMOVED
            # We now rely fully on the native function calling loop above
            
            # Convert common markdown to HTML (for all agents that return HTML)
            # Check if response contains HTML-like structure or recommendation cards
            has_html_structure = '<div' in response_text or '<recommendation-card' in response_text.lower()
            
            if has_html_structure:
                # Convert markdown headers to HTML
                response_text = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', response_text, flags=re.MULTILINE)
                response_text = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', response_text, flags=re.MULTILINE)
                response_text = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', response_text, flags=re.MULTILINE)
                # Convert bold markdown to HTML
                response_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', response_text)
                # Convert markdown links to HTML
                response_text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" target="_blank">\1</a>', response_text)
            
            # Check if response contains itinerary content (prompt-driven detection)
            # NEW VALIDATION LOGIC: If flights were found, the LLM had all info (prompt-driven)
            has_flights = bool(session_context.get('selected_flights'))
            has_destination = session_context.get('destination') or destination
            
            # If flights exist, we know the LLM extracted all required info
            # (duration, dates, destination) to make the tool call
            if has_flights:
                has_duration = True  # LLM had duration to call flight search
                has_travel_date = True  # LLM had dates to call flight search
                logger.info(f"[Agent Executor] ✅ Flights found - LLM had all required info")
            else:
                # Fallback: check session_context (for backward compatibility)
                has_duration = bool(session_context.get('duration'))
            has_travel_date = False
            if session_context.get('travel_date'):
                has_travel_date = True
            elif session_context.get('travel_dates'):
                travel_dates_check = session_context.get('travel_dates')
                if isinstance(travel_dates_check, list) and len(travel_dates_check) > 0 and all(d for d in travel_dates_check):
                    has_travel_date = True
            elif session_context.get('primary_departure_date'):
                # If flights were found, we have a travel date
                    has_travel_date = True
            
            logger.info(f"[Agent Executor] INFO STATUS CHECK - has_flights: {has_flights}, has_destination: {has_destination}, has_duration: {has_duration}, has_travel_date: {has_travel_date}")
            logger.info(f"[Agent Executor] Session context keys: {list(session_context.keys())}")
            logger.info(f"[Agent Executor] Session context duration: {session_context.get('duration')}")
            
            # Check if response contains ACTUAL itinerary content (must have day-by-day structure)
            # Be strict - require actual day cards or day headers, not just mention of "day"
            has_itinerary_content = (
                ('day 1' in response_text.lower() and ('morning' in response_text.lower() or 'afternoon' in response_text.lower() or 'evening' in response_text.lower())) or
                '<div class="day-card">' in response_text or
                '<div class="itinerary-intro">' in response_text
            )
            
            logger.info(f"[Agent Executor] Itinerary detection: has_itinerary_content={has_itinerary_content}, response_length={len(response_text)}")
            logger.info(f"[Agent Executor] Response preview (first 500 chars): {response_text[:500]}")
            has_day1 = 'day 1' in response_text.lower()
            has_day_card = '<div class="day-card">' in response_text
            has_intro = '<div class="itinerary-intro">' in response_text
            logger.info(f"[Agent Executor] Checking for: 'day 1'={has_day1}, 'day-card'={has_day_card}, 'itinerary-intro'={has_intro}")
            
            # If itinerary content detected but missing required info, inject a reminder
            # Only require: destination, duration, and travel dates (removed holiday_type requirement)
            # BLOCK REMOVED: Trust the LLM's output.
            # Previously, we intercepted responses that looked like itineraries but were missing
            # strict metadata (duration, dates) and replaced them with a generic "I need info" message.
            # This caused valid itineraries inferred from context to be hidden.
            # We now allow the LLM to manage the conversation flow.
            
            # if has_itinerary_content and is_travel_agent and not (has_destination and has_duration and has_travel_date):
            #     ... (logic removed) ...
            #     has_itinerary_content = False
            
            # --- ITINERARY DETECTION & METADATA EXTRACTION ---
            # Retrieve destination from session context (set by flight search tool)
            # destination_from_context = session_context.get('destination') or destination
            # duration_from_context = session_context.get('duration')
            
            # Extract metadata for summary card and flight formatting
            metadata_destination = session_context.get('destination') or self._extract_destination(user_message, response_text) or "your destination"
            metadata_duration = session_context.get('duration') or self._extract_duration(user_message, response_text) or "Trip"
            metadata_pace = self._extract_pace(user_message, response_text) or "Relaxed"
            
            # Handle dates
            metadata_departure_date = session_context.get('primary_departure_date') or session_context.get('travel_date') or "Upcoming"
            
            # 1. Generate Flight Options HTML if flights were found
            selected_flights = session_context.get('selected_flights', [])
            flight_options_html = ""
            if selected_flights:
                logger.info(f"[Agent Executor] Adding {len(selected_flights)} flight options for UI display")
                try:
                    from changi_flight_service import format_flight_options_for_itinerary
                    flight_options_html = format_flight_options_for_itinerary(
                        selected_flights,
                        metadata_destination,
                        metadata_departure_date,
                        metadata_duration
                    )
                except Exception as e:
                    logger.error(f"[Agent Executor] Error formatting standalone flight options: {e}")
            
            # 2. Fetch Now Boarding articles if not already present
            articles = session_context.get('recent_articles', [])
            if not articles and metadata_destination:
                try:
                    # Clean destination for API calls
                    clean_dest = re.sub(r'^(go to|i\'d like to go to|going to|let\'s go to)\s+', '', metadata_destination, flags=re.IGNORECASE).strip().title()
                    articles = self._fetch_nowboarding_articles(clean_dest, limit=3)
                except Exception as e:
                    logger.error(f"[Agent Executor] Error fetching articles: {e}")

            # If it's a travel agent and response contains itinerary, format it for display
            # Only proceed if we have all required information (destination, duration, travel_date)
            logger.info(f"[Agent Executor] Checking itinerary conditions: is_travel_agent={is_travel_agent}, has_itinerary_content={has_itinerary_content}, has_destination={has_destination}, has_duration={has_duration}, has_travel_date={has_travel_date}")
            if is_travel_agent and has_itinerary_content:
                logger.info(f"[Agent Executor] ✅ ITINERARY DETECTED - Processing for display")
                
                # Use the common metadata
                destination = metadata_destination
                duration = metadata_duration
                pace = metadata_pace
                primary_departure_date = metadata_departure_date
                
                # Get arrival time from first flight if available
                arrival_time = None
                if selected_flights:
                    first_flight = selected_flights[0]
                    try:
                        display_ts = first_flight.get("display_timestamp")
                        if display_ts:
                            from datetime import datetime
                            dt_obj = datetime.strptime(display_ts, "%Y-%m-%d %H:%M")
                            hour = dt_obj.hour
                            arrival_time = f"{hour:02d}:{dt_obj.minute:02d}"
                    except:
                        pass
                
                # Check if response already has HTML structure but might be incomplete
                has_html_structure = '<div class="day-card">' in response_text
                has_time_blocks = '<div class="time-block">' in response_text
                
                logger.info(f"[Agent Executor] HTML check: has_html_structure={has_html_structure}, has_time_blocks={has_time_blocks}")
                
                # If response is in markdown, convert it to proper HTML format for right panel
                if '###' in response_text or '##' in response_text or '**' in response_text:
                    # Convert markdown to HTML structure
                    logger.info(f"[Agent Executor] Converting markdown to HTML")
                    response_text = self._convert_markdown_itinerary_to_html(response_text, destination, arrival_time)
                elif has_html_structure and not has_time_blocks:
                    # HTML structure exists but time blocks are missing - this is a problem!
                    logger.error(f"[Agent Executor] ⚠️ HTML day-card structure found but NO time-block content!")
                    logger.error(f"[Agent Executor] Response preview: {response_text[:500]}")
                    # Try to extract from text or regenerate
                    response_text = self._extract_and_add_time_blocks(response_text, destination)
                elif has_html_structure and has_time_blocks:
                    # HTML is complete, just adjust for arrival time if needed
                    logger.info(f"[Agent Executor] ✅ Complete HTML structure with time blocks found")
                    if arrival_time:
                        response_text = self._adjust_itinerary_by_arrival_time(response_text, arrival_time)
                elif arrival_time:
                    # Adjust Day 1 based on arrival time even if already in HTML
                    response_text = self._adjust_itinerary_by_arrival_time(response_text, arrival_time)
                
                # Flight options already generated above as flight_options_html
                # We can just log success here if they were found
                if flight_options_html:
                    logger.info(f"[Agent Executor] ✅ Consistent flight options HTML available (length: {len(flight_options_html)})")
                
                # No changes needed to response_text here, it's already processed or will be enhanced below
                
                # Enhance itinerary with MCP-generated travel content links
                travel_content_enabled = mcp_manager.is_tool_enabled('travel_content.links') #previously tool_name is travel_content
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Tool enabled check: {travel_content_enabled}")
                
                if travel_content_enabled:
                    # Ensure we have destination from session_context if not already set
                    final_destination = destination or session_context.get('destination')
                    logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Enhancing itinerary with MCP-generated links")
                    logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Destination: '{final_destination}' (from variable: '{destination}', from context: '{session_context.get('destination')}'), HTML length: {len(response_text)}")
                    try:
                        response_text = self._enhance_itinerary_with_mcp_links(response_text, final_destination)
                        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Itinerary enhanced with MCP links (final length: {len(response_text)})")
                    except Exception as e:
                        logger.error(f"[Agent Executor] ❌ [Travel Content MCP] Error enhancing itinerary with links: {e}")
                        import traceback
                        logger.error(f"[Agent Executor] Traceback: {traceback.format_exc()}")
                else:
                    logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Tool not enabled, skipping link enhancement")
                
                # Extract locations from itinerary using MCP tool, with fallback if it fails
                locations = []
                if mcp_manager.is_tool_enabled('maps.extract_locations') and destination: #previously tool_name is maps
                    try:
                        maps_result = mcp_manager.call_tool(
                            tool_name='maps.extract_locations',
                            arguments={
                                'itinerary_html': response_text,
                                'destination': destination
                            }
                        )
                        if maps_result.get('success'):
                            locations = maps_result.get('locations', [])
                        else:
                            logger.warning(f"[Agent Executor] MCP maps extraction failed: {maps_result.get('error')}, falling back to direct method")
                            locations = self._extract_locations_from_itinerary(response_text, destination)
                    except Exception as e:
                        logger.warning(f"[Agent Executor] MCP maps extraction error: {e}, falling back to direct method")
                        locations = self._extract_locations_from_itinerary(response_text, destination)
                else:
                    # Direct method if MCP not enabled
                    locations = self._extract_locations_from_itinerary(response_text, destination)
                
                # Fetch Now Boarding articles - already handled in the shared block above
                # Use clean_destination for API call results if needed for logging
                clean_destination = destination.title()
                
                # Create summary card for chat
                summary_card = self._create_summary_card(destination, duration, pace)
                
                # Update conversation history
                if 'conversation_history' not in session_context:
                    session_context['conversation_history'] = []
                
                session_context['conversation_history'].append({
                    "role": "user",
                    "content": user_message
                })
                session_context['conversation_history'].append({
                    "role": "assistant",
                    "content": response_text
                })
                
                # Keep only last 10 messages
                if len(session_context['conversation_history']) > 10:
                    session_context['conversation_history'] = session_context['conversation_history'][-10:]
                
                # Save to session
                session['context'] = session_context
                
                logger.info(f"[Agent Executor] ✅ Returning itinerary response:")
                logger.info(f"[Agent Executor]   - Summary card length: {len(summary_card)}")
                logger.info(f"[Agent Executor]   - Full itinerary length: {len(response_text)}")
                logger.info(f"[Agent Executor]   - Destination: {clean_destination}")
                logger.info(f"[Agent Executor]   - Duration: {duration}")
                logger.info(f"[Agent Executor]   - Locations: {len(locations)}")
                logger.info(f"[Agent Executor]   - Articles: {len(articles)}")
                logger.info(f"[Agent Executor]   - Flights: {len(selected_flights) if selected_flights else 0}")
                logger.info(f"[Agent Executor]   - Flight HTML length: {len(flight_options_html) if flight_options_html else 0}")
                logger.info(f"[Agent Executor]   - Show panel: True")
                
                return {
                    'response': summary_card,
                    'full_itinerary': response_text,
                    'success': True,
                    'agent_id': self.agent_id,
                    'agent_name': self.get_agent_name(),
                    'destination': clean_destination,
                    'duration': duration,
                    'show_panel': True,
                    'locations': locations,
                    'articles': articles,
                    'flights': selected_flights or [],
                    'flight_options_html': flight_options_html,  # Pre-formatted flight HTML for panel
                    'departure_date': primary_departure_date
                }
            
            # For non-travel agents, check if response contains recommendation cards
            # If it does, extract the summary card and full content for panel display
            if not is_travel_agent and ('recommendation-card' in response_text.lower() or 'get-plan-btn' in response_text.lower()):
                # Try to extract summary card (first recommendation-card div)
                # Pattern: <div class="recommendation-card">...content...</div></div>
                rec_card_pattern = r'(<div class="recommendation-card"[^>]*>.*?</div>\s*</div>)'
                rec_card_match = re.search(rec_card_pattern, response_text, re.DOTALL)
                
                if rec_card_match:
                    summary_card = rec_card_match.group(1)
                    # Full content is the entire response
                    full_content = response_text
                    
                    # Update conversation history
                    if 'conversation_history' not in session_context:
                        session_context['conversation_history'] = []
                    
                    session_context['conversation_history'].append({
                        "role": "user",
                        "content": user_message
                    })
                    session_context['conversation_history'].append({
                        "role": "assistant",
                        "content": full_content
                    })
                    
                    # Keep only last 10 messages
                    if len(session_context['conversation_history']) > 10:
                        session_context['conversation_history'] = session_context['conversation_history'][-10:]
                    
                    # Save to session
                    session['context'] = session_context
                    
                    return {
                        'response': summary_card,
                        'full_itinerary': full_content,
                        'success': True,
                        'agent_id': self.agent_id,
                        'agent_name': self.get_agent_name(),
                        'show_panel': True
                    }
            
            # Update conversation history
            if 'conversation_history' not in session_context:
                session_context['conversation_history'] = []
            
            session_context['conversation_history'].append({
                "role": "user",
                "content": user_message
            })
            session_context['conversation_history'].append({
                "role": "assistant",
                "content": response_text
            })
            
            # Keep only last 10 messages
            if len(session_context['conversation_history']) > 10:
                session_context['conversation_history'] = session_context['conversation_history'][-10:]
            
            # Save to session
            session['context'] = session_context
            
            logger.info(f"[Agent Executor] ⚠️ Returning DEFAULT response (no full_itinerary)")
            logger.info(f"[Agent Executor]   - has_itinerary_content: {has_itinerary_content}")
            logger.info(f"[Agent Executor]   - is_travel_agent: {is_travel_agent}")
            logger.info(f"[Agent Executor]   - Conditions check: has_destination={has_destination}, has_duration={has_duration}, has_travel_date={has_travel_date}")
            
            response_dict = {
                'response': response_text,
                'success': True,
                'agent_id': self.agent_id,
                'agent_name': self.get_agent_name(),
                'destination': metadata_destination,
                'duration': metadata_duration,
                'departure_date': metadata_departure_date
            }
            
            # If the agent just fetched flights or articles, display them even without an itinerary
            if articles:
                response_dict['articles'] = articles
                response_dict['show_panel'] = True
                
            if flight_options_html:
                response_dict['flight_options_html'] = flight_options_html
                response_dict['show_panel'] = True
                response_dict['flights'] = selected_flights
                logger.info(f"[Agent Executor] Added flight_options_html to default response (length: {len(flight_options_html)})")
                
            return response_dict
            
        except Exception as e:
            logger.error(f"Error executing agent chat: {e}")
            return {
                'error': str(e),
                'success': False,
                'agent_id': self.agent_id
            }
    
    def chat_stream(self, user_message: str, session_context: Optional[Dict] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Execute a streaming chat conversation.
        Yields chunks of text as they arrive, then yields a final 'done' event with metadata.
        
        Args:
            user_message: User's message
            session_context: Optional session context
            
        Yields:
            Dict with either 'chunk' (text fragment) or 'done' (final result with metadata)
        """
        try:
            # Initialize session context if not provided
            # Note: Cannot access Flask session from generator, use provided context
            if session_context is None:
                session_context = {}
            
            # Build messages for LLM (simplified - uses same logic as chat())
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_message}
            ]
            
            # Add conversation history if available
            if 'conversation_history' in session_context:
                history = session_context['conversation_history'][-10:]
                for msg in history:
                    messages.insert(-1, msg)
            
            logger.info(f"[Agent Executor] Starting streaming response for agent {self.agent_id}")
            
            # Stream the response
            full_response = ""
            
            # Check if LLM client supports streaming
            if hasattr(self.llm_client, 'stream_chat_completion'):
                for chunk in self.llm_client.stream_chat_completion(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=8192
                ):
                    full_response += chunk
                    yield {"type": "chunk", "content": chunk}
            else:
                # Fallback to non-streaming
                full_response = self.llm_client.chat_completion(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=8192
                )
                yield {"type": "chunk", "content": full_response}
            
            # Clean up markdown code blocks
            response_text = full_response.strip()
            if response_text.startswith('```html'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Update conversation history
            if 'conversation_history' not in session_context:
                session_context['conversation_history'] = []
            
            session_context['conversation_history'].append({
                "role": "user",
                "content": user_message
            })
            session_context['conversation_history'].append({
                "role": "assistant",
                "content": response_text
            })
            
            # Keep only last 10 messages
            if len(session_context['conversation_history']) > 10:
                session_context['conversation_history'] = session_context['conversation_history'][-10:]
            
            # Note: session_context is passed by reference, so modifications persist
            # Cannot access Flask session from generator (outside request context)
            
            logger.info(f"[Agent Executor] Streaming complete, response length: {len(response_text)}")
            
            # Yield final 'done' event with the complete response for post-processing
            yield {
                "type": "done",
                "response": response_text,
                "success": True,
                "agent_id": self.agent_id,
                "agent_name": self.get_agent_name()
            }
            
        except Exception as e:
            logger.error(f"Error in streaming chat: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "success": False,
                "agent_id": self.agent_id
            }
    
    def _extract_destination(self, user_message: str, response_text: str) -> Optional[str]:
        """Extract destination from user message or response"""
        # Common destination patterns
        destinations = ['tokyo', 'bali', 'bangkok', 'singapore', 'seoul', 'paris', 'london', 
                       'new york', 'sydney', 'melbourne', 'hong kong', 'taipei', 'osaka']
        
        text_lower = (user_message + ' ' + response_text).lower()
        for dest in destinations:
            if dest in text_lower:
                return dest.title()
        
        # Try to extract from patterns like "trip to X" or "visit X"
        patterns = [
            r'trip to ([A-Z][a-zA-Z\s]+)',
            r'visit ([A-Z][a-zA-Z\s]+)',
            r'in ([A-Z][a-zA-Z\s]+)',
            r'to ([A-Z][a-zA-Z\s]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_duration(self, user_message: str, response_text: str) -> Optional[str]:
        """Extract duration from user message"""
        # Normalize message for matching
        msg_lower = user_message.lower()
        
        # First check for natural language patterns like "a week", "one week", "two days"
        word_to_num = {
            'a': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        
        # Match "a week", "one week", "two weeks"
        week_match = re.search(r'\b(a|one|two|three|four)\s+weeks?\b', msg_lower)
        if week_match:
            word = week_match.group(1)
            num = word_to_num.get(word, 1)
            days = num * 7
            return f'{days} days'
        
        # Match "a day", "one day", "two days", etc.
        day_match = re.search(r'\b(a|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\b', msg_lower)
        if day_match:
            word = day_match.group(1)
            num = word_to_num.get(word, 1)
            return f'{num} days'
        
        # Standard numeric patterns
        patterns = [
            r'(\d+)\s*days?',
            r'(\d+)\s*day trip',
            r'(\d+)\s*week',
            r'weekend'
        ]
        for pattern in patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                if 'weekend' in match.group(0).lower():
                    return 'Weekend'
                return match.group(0)
        return None
    
    def _extract_pace(self, user_message: str, response_text: str) -> Optional[str]:
        """Extract pace preference"""
        text_lower = (user_message + ' ' + response_text).lower()
        if any(word in text_lower for word in ['packed', 'busy', 'see everything', 'action']):
            return 'packed'
        elif any(word in text_lower for word in ['relaxed', 'chill', 'slow', 'downtime']):
            return 'relaxed'
        return None
    
    def _extract_locations_from_itinerary(self, itinerary_html: str, destination: Optional[str]) -> List[Dict]:
        """Extract locations from itinerary HTML and geocode them"""
        locations = []
        
        logger.info(f"[Agent Executor] 🔍 Extracting locations from itinerary HTML (length: {len(itinerary_html)})")
        
        # Method 1: Try to find day-card divs with simpler pattern
        day_pattern = r'<div[^>]*class="day-card"[^>]*>(.*?)</div>\s*</div>'
        day_matches = re.findall(day_pattern, itinerary_html, re.DOTALL | re.IGNORECASE)
        
        logger.info(f"[Agent Executor] 🔍 Method 1 (day-card): Found {len(day_matches)} matches")
        
        # Method 2: If no day-card matches, try finding h3 Day headers with content between them
        if not day_matches:
            # Split by Day header patterns
            day_sections = re.split(r'(?=<h3[^>]*>.*?Day\s*\d+)', itinerary_html, flags=re.IGNORECASE | re.DOTALL)
            for i, section in enumerate(day_sections[1:], 1):  # Skip first empty section
                # Extract day number
                day_num_match = re.search(r'Day\s*(\d+)', section, re.IGNORECASE)
                day_num = day_num_match.group(1) if day_num_match else str(i)
                day_matches.append(section)
            logger.info(f"[Agent Executor] 🔍 Method 2 (h3 Days): Found {len(day_matches)} day sections")
        
        # Method 3: Direct extraction from all <strong> tags as fallback
        if not day_matches:
            logger.info(f"[Agent Executor] 🔍 Method 3: Falling back to direct <strong> extraction")
            # Find all strong tags directly from the entire HTML
            strong_pattern = r'<strong>([^<]+)</strong>'
            all_attractions = re.findall(strong_pattern, itinerary_html, re.IGNORECASE)
            
            skip_words = ['morning', 'afternoon', 'evening', 'breakfast', 'lunch', 'dinner', 
                          'arrival', 'departure', 'check-in', 'check out', 'day', 'note', 'tip',
                          'stay duration', 'note:']
            skip_phrases = ['relax', 'enjoy', 'head to', 'visit the', 'explore the', 'dine', 
                            'dinner at', 'lunch at', 'free visa', 'passport holder']
            
            for attraction in all_attractions:
                attraction = attraction.strip()
                if len(attraction) > 3 and not any(word in attraction.lower() for word in skip_words):
                    if not any(phrase in attraction.lower() for phrase in skip_phrases):
                        locations.append({
                            'name': attraction,
                            'day': 1
                        })
            
            logger.info(f"[Agent Executor] ✅ Method 3: Extracted {len(locations)} locations from <strong> tags")
            # Geocode the extracted locations
            locations = self._geocode_locations(locations[:20], destination)
            return locations
        
        # Extract from day sections
        for idx, content in enumerate(day_matches[:5]):
            day_num = idx + 1
            
            # Find attraction names in <strong> tags (activity titles)
            strong_pattern = r'<strong>([^<]+)</strong>'
            attractions = re.findall(strong_pattern, content, re.IGNORECASE)
            
            logger.debug(f"[Agent Executor] 🔍 Day {day_num}: Found {len(attractions)} <strong> tags")
            
            # Filter and add locations
            skip_words = ['morning', 'afternoon', 'evening', 'breakfast', 'lunch', 'dinner', 
                          'arrival', 'departure', 'check-in', 'check out', 'day', 'note', 'tip']
            skip_phrases = ['relax', 'enjoy', 'head to', 'visit', 'explore', 'dine', 
                            'dinner at', 'lunch at']
            
            for attraction in attractions:
                attraction = attraction.strip()
                if len(attraction) > 3 and not any(word in attraction.lower() for word in skip_words):
                    if not any(phrase in attraction.lower() for phrase in skip_phrases):
                        locations.append({
                            'name': attraction,
                            'day': day_num
                        })
                        logger.debug(f"[Agent Executor] ✅ Added location: {attraction} (Day {day_num})")
        
        logger.info(f"[Agent Executor] ✅ Extracted {len(locations)} locations total: {[loc['name'] for loc in locations[:5]]}")
        
        # Geocode the extracted locations to get lat/lon coordinates
        locations = self._geocode_locations(locations[:20], destination)
        
        return locations
    
    def _geocode_locations(self, locations: List[Dict], destination: Optional[str]) -> List[Dict]:
        """Geocode a list of locations using OpenStreetMap Nominatim API"""
        if not locations:
            return locations
        
        logger.info(f"[Agent Executor] 🗺️ Geocoding {len(locations)} locations for {destination}")
        
        geocoded_locations = []
        for loc in locations:
            try:
                # Build search query with destination context
                query = f"{loc['name']}, {destination}" if destination else loc['name']
                
                url = "https://nominatim.openstreetmap.org/search"
                params = {
                    'q': query,
                    'format': 'json',
                    'limit': 1,
                    'addressdetails': 1
                }
                headers = {
                    'User-Agent': 'ChangiTravelBot/1.0'
                }
                
                response = requests.get(url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        result = data[0]
                        geocoded_loc = {
                            'name': loc['name'],
                            'day': loc.get('day', 1),
                            'lat': float(result['lat']),
                            'lon': float(result['lon']),
                            'display_name': result.get('display_name', loc['name'])
                        }
                        geocoded_locations.append(geocoded_loc)
                        logger.debug(f"[Agent Executor] ✅ Geocoded: {loc['name']} -> {result['lat']}, {result['lon']}")
                    else:
                        # Keep location without coordinates
                        geocoded_locations.append(loc)
                        logger.debug(f"[Agent Executor] ⚠️ No geocode result for: {loc['name']}")
                else:
                    geocoded_locations.append(loc)
                    
            except Exception as e:
                logger.debug(f"[Agent Executor] ⚠️ Geocoding error for {loc['name']}: {e}")
                geocoded_locations.append(loc)
        
        geocoded_count = sum(1 for loc in geocoded_locations if 'lat' in loc and 'lon' in loc)
        logger.info(f"[Agent Executor] ✅ Geocoded {geocoded_count}/{len(locations)} locations successfully")
        
        return geocoded_locations
    
    
    def _fetch_nowboarding_articles(self, destination: Optional[str], limit: int = 3) -> List[Dict]:
        """Fetch Now Boarding articles for destination"""
        if not destination:
            return []
        
        articles = []
        try:
            # URL-encode destination name for API (spaces become %20)
            import urllib.parse
            search_term = urllib.parse.quote(destination.lower())
            api_url = f"https://nowboarding.changiairport.com/search.nbsearch.{search_term}.0.data"
            
            logger.info(f"[Agent Executor] Fetching Now Boarding articles from: {api_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(api_url, headers=headers, timeout=10, verify=False)
            
            logger.info(f"[Agent Executor] Now Boarding API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                search_results = data.get('searchResults', [])
                logger.info(f"[Agent Executor] Now Boarding found {len(search_results)} articles for '{destination}'")
                
                # Filter for 2025/2026 articles first
                recent_articles = [r for r in search_results if '2025' in r.get('date', '') or '2026' in r.get('date', '')]
                other_articles = [r for r in search_results if '2025' not in r.get('date', '') and '2026' not in r.get('date', '')]
                
                selected_results = recent_articles[:limit]
                if len(selected_results) < limit:
                    selected_results.extend(other_articles[:limit - len(selected_results)])
                
                for result in selected_results:
                    article = {
                        'title': result.get('title', f'Discover {destination}'),
                        'description': result.get('excerpt', result.get('description', ''))[:150],
                        'url': f"https://nowboarding.changiairport.com{result.get('pageUrl', '')}",
                        'date': result.get('formattedDate', ''),
                        'category': result.get('category', {}).get('title', '')
                    }
                    articles.append(article)
                    
                logger.info(f"[Agent Executor] Now Boarding returning {len(articles)} articles")
        except Exception as e:
            logger.error(f"Error fetching Now Boarding articles: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        return articles

    def _adjust_itinerary_by_arrival_time(self, itinerary_html: str, arrival_time: str) -> str:
        """Adjust Day 1 itinerary based on arrival time"""
        import re
        from datetime import datetime
        
        try:
            # Parse arrival time (HH:MM format)
            hour = int(arrival_time.split(':')[0])
            
            # Find Day 1 content
            day1_pattern = r'(<div class="day-card">.*?<h3[^>]*>.*?Day\s*1[^<]*</h3>)(.*?)(</div>\s*(?=<div class="day-card"|$))'
            match = re.search(day1_pattern, itinerary_html, re.DOTALL | re.IGNORECASE)
            
            if not match:
                return itinerary_html
            
            day1_header = match.group(1)
            day1_content = match.group(2)
            day1_close = match.group(3)
            
            # Determine which time blocks to keep based on arrival time
            if hour < 12:  # Morning arrival - keep all
                adjusted_content = day1_content
            elif hour < 16:  # Afternoon arrival - remove morning
                # Remove morning time-block
                adjusted_content = re.sub(
                    r'<div class="time-block">.*?<span class="time">[🌅🌄].*?Morning.*?</span>.*?</div>',
                    '',
                    day1_content,
                    flags=re.DOTALL
                )
                # Add note about arrival
                adjusted_content = f'<div class="time-block"><span class="time">✈️ Arrival</span><strong>Flight Arrives at {arrival_time}</strong><p>After clearing immigration and collecting luggage, you\'ll be ready to start your adventure!</p></div>' + adjusted_content
            else:  # Evening arrival - keep only evening
                # Remove morning and afternoon
                adjusted_content = re.sub(
                    r'<div class="time-block">.*?<span class="time">[🌅🌄☀️].*?(Morning|Afternoon).*?</span>.*?</div>',
                    '',
                    day1_content,
                    flags=re.DOTALL
                )
                # Add note about arrival
                adjusted_content = f'<div class="time-block"><span class="time">✈️ Arrival</span><strong>Flight Arrives at {arrival_time}</strong><p>After clearing immigration and collecting luggage, check into your hotel and enjoy dinner!</p></div>' + adjusted_content
            
            # Reconstruct Day 1
            adjusted_day1 = day1_header + adjusted_content + day1_close
            
            # Replace in original HTML
            return itinerary_html.replace(match.group(0), adjusted_day1)
            
        except Exception as e:
            logger.error(f"Error adjusting itinerary by arrival time: {e}")
            return itinerary_html
    
    def _convert_markdown_itinerary_to_html(self, markdown_text: str, destination: Optional[str], arrival_time: Optional[str] = None) -> str:
        """Convert markdown itinerary to HTML format for right panel"""
        import re
        
        # Start with intro
        html = f'<div class="itinerary-intro">\nGet ready for an exciting adventure in {destination or "your destination"}! ✨ '
        html += 'This itinerary will take you on a journey filled with amazing experiences. Let\'s explore!\n</div>\n\n'
        
        # Split by day headers (### Day X or ## Day X)
        day_pattern = r'(?:###|##)\s*Day\s*(\d+)[:\s\-–]+([^\n]+)'
        days = re.findall(day_pattern, markdown_text, re.IGNORECASE)
        
        if not days:
            # Try alternative pattern
            day_pattern = r'Day\s*(\d+)[:\s\-–]+([^\n]+)'
            days = re.findall(day_pattern, markdown_text, re.IGNORECASE)
        
        # Process each day
        for day_num, day_title in days:
            html += f'<div class="day-card">\n<h3>🗓️ Day {day_num}: {day_title.strip()}</h3>\n'
            
            # Extract time blocks (Morning, Afternoon, Evening)
            # Try multiple day header patterns
            day_patterns = [
                f'Day {day_num}',
                f'#### Day {day_num}',
                f'### Day {day_num}',
                f'## Day {day_num}',
            ]
            day_start = -1
            for pattern in day_patterns:
                day_start = markdown_text.find(pattern)
                if day_start != -1:
                    logger.debug(f"[Agent Executor] 🔍 [Travel Content MCP] Found day header with pattern: '{pattern}' at position {day_start}")
                    break
            
            if day_start == -1:
                logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Could not find Day {day_num} header in markdown")
                continue
                
            day_content = markdown_text[day_start:]
            # Find next day or end of text
            next_day_patterns = [
                f'Day {int(day_num) + 1}',
                f'#### Day {int(day_num) + 1}',
                f'### Day {int(day_num) + 1}',
                f'## Day {int(day_num) + 1}',
            ]
            next_day_pos = -1
            for pattern in next_day_patterns:
                pos = markdown_text.find(pattern, day_start + 1)
                if pos > 0:
                    next_day_pos = pos
                    break
            
            if next_day_pos > 0:
                day_content = markdown_text[day_start:next_day_pos]
                logger.debug(f"[Agent Executor] 🔍 [Travel Content MCP] Extracted day content from position {day_start} to {next_day_pos} (length: {len(day_content)})")
            else:
                logger.debug(f"[Agent Executor] 🔍 [Travel Content MCP] No next day found, using content from position {day_start} to end (length: {len(day_content)})")
            
            # Find time blocks - try multiple patterns
            logger.info(f"[Agent Executor] 🔍 [Travel Content MCP] Searching for time blocks in Day {day_num}. Content preview: {day_content[:500]}")
            time_patterns = [
                # Pattern 1: Bullet point with bold time WITHOUT colon (LLM format): - **Morning**\n  - content
                # This matches: - **Morning**\n  - line1\n  - line2\n\n- **Afternoon**
                r'-\s*\*\*(Morning|Afternoon|Evening|Breakfast|Lunch|Dinner)\*\*\s*\n\s*((?:-\s+[^\n]+(?:\n|$))+(?=\n\s*-\s*\*\*(?:Morning|Afternoon|Evening|Breakfast|Lunch|Dinner)\*\*|\n\s*Day \d+|$))',
                # Pattern 2: Bullet point with bold time WITH colon: - **Morning**: content
                r'-\s*\*\*(Morning|Afternoon|Evening|Breakfast|Lunch|Dinner):\*\*\s*([^\n]+(?:\n(?!-\s*\*\*(?:Morning|Afternoon|Evening|Breakfast|Lunch|Dinner|Day \d))[^\n]+)*)',
                # Pattern 3: Bold time without bullet: **Morning**: content
                r'\*\*(Morning|Afternoon|Evening|Breakfast|Lunch|Dinner):\*\*\s*([^\*]+?)(?=\*\*(?:Morning|Afternoon|Evening|Breakfast|Lunch|Dinner|Day \d+)|$)',
                # Pattern 4: Time colon with bold activity: Morning: **Activity** content
                r'(Morning|Afternoon|Evening|Breakfast|Lunch|Dinner):\s*\*\*([^\*]+)\*\*\s*([^\n]+(?:\n(?!Morning|Afternoon|Evening|Day \d)[^\n]+)*)',
                # Pattern 5: Emoji patterns
                r'🌅\s*(Morning|Afternoon|Evening)[:\s]+([^\n]+(?:\n(?!🌅|☀️|🌙|Day \d)[^\n]+)*)',
                r'☀️\s*(Morning|Afternoon|Evening)[:\s]+([^\n]+(?:\n(?!🌅|☀️|🌙|Day \d)[^\n]+)*)',
                r'🌙\s*(Morning|Afternoon|Evening)[:\s]+([^\n]+(?:\n(?!🌅|☀️|🌙|Day \d)[^\n]+)*)',
            ]
            
            time_blocks = []
            for idx, pattern in enumerate(time_patterns):
                matches = re.findall(pattern, day_content, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if matches:
                    time_blocks = matches
                    logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Found {len(time_blocks)} time blocks using pattern #{idx+1}")
                    logger.info(f"[Agent Executor] 🔍 [Travel Content MCP] First match: time='{matches[0][0] if matches else 'N/A'}', content_preview='{matches[0][1][:150] if matches and len(matches[0]) > 1 else 'N/A'}'")
                    break
                else:
                    logger.debug(f"[Agent Executor] 🔍 [Travel Content MCP] Pattern #{idx+1} did not match")
            
            if not time_blocks:
                logger.error(f"[Agent Executor] ❌ [Travel Content MCP] CRITICAL: No time blocks found for Day {day_num}")
                logger.error(f"[Agent Executor] 🔍 [Travel Content MCP] Day content (first 800 chars):\n{repr(day_content[:800])}")
                # CRITICAL FIX: Try a simpler pattern as last resort
                simple_pattern = r'-\s*\*\*(Morning|Afternoon|Evening)\*\*'
                simple_matches = re.findall(simple_pattern, day_content, re.IGNORECASE)
                if simple_matches:
                    logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Found time headers but not content. Creating fallback blocks.")
                    # Extract content between time headers manually
                    for time_name in ['Morning', 'Afternoon', 'Evening']:
                        time_header = f'- **{time_name}**'
                        if time_header.lower() in day_content.lower():
                            # Find content after this header until next time or day
                            header_pos = day_content.lower().find(time_header.lower())
                            if header_pos >= 0:
                                next_header_pos = len(day_content)
                                for next_time in ['Morning', 'Afternoon', 'Evening', 'Day']:
                                    if next_time.lower() != time_name.lower():
                                        next_pos = day_content.lower().find(f'- **{next_time}**', header_pos + len(time_header))
                                        if next_pos > 0 and next_pos < next_header_pos:
                                            next_header_pos = next_pos
                                    next_day_pos = day_content.lower().find(f'day {int(day_num) + 1}', header_pos)
                                    if next_day_pos > 0 and next_day_pos < next_header_pos:
                                        next_header_pos = next_day_pos
                                
                                content = day_content[header_pos + len(time_header):next_header_pos].strip()
                                if content:
                                    time_blocks.append((time_name, content))
                                    logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Extracted {time_name} content manually: {content[:100]}")
                
                if not time_blocks:
                    logger.error(f"[Agent Executor] ❌ [Travel Content MCP] Still no time blocks. Full content:\n{repr(day_content)}")
                    # Last resort: create placeholder blocks
                    time_blocks = [('Morning', day_content[:200]), ('Afternoon', day_content[200:400] if len(day_content) > 200 else ''), ('Evening', day_content[400:600] if len(day_content) > 400 else '')]
            
            time_emojis = {
                'morning': '🌅',
                'afternoon': '☀️',
                'evening': '🌙',
                'breakfast': '🍳',
                'lunch': '🍽️',
                'dinner': '🍴'
            }
            
            logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Processing {len(time_blocks[:3])} time blocks for Day {day_num}")
            for idx, time_block in enumerate(time_blocks[:3]):  # Limit to 3 time blocks per day
                # Handle different pattern match formats
                if len(time_block) == 2:
                    time_name, time_content = time_block
                elif len(time_block) == 3:
                    time_name, activity_part, time_content = time_block
                    time_content = f"**{activity_part}** {time_content}"
                else:
                    logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Unexpected time block format: {time_block}")
                    continue
                
                emoji = time_emojis.get(time_name.lower(), '⏰')
                
                # Clean up time_content - handle bullet points and indentation
                # Remove leading dashes and indentation from bullet points
                time_content_clean = re.sub(r'^\s*-\s+', '', time_content, flags=re.MULTILINE)
                time_content_clean = re.sub(r'\n\s*-\s+', '. ', time_content_clean)  # Convert bullet points to sentences
                time_content_clean = re.sub(r'\n+', ' ', time_content_clean).strip()
                
                # Extract activity name (first line or bold text)
                activity_match = re.search(r'\*\*([^\*]+)\*\*', time_content_clean)
                if activity_match:
                    activity_name = activity_match.group(1).strip()
                else:
                    # Try to extract first meaningful phrase (skip common words)
                    first_sentence = time_content_clean.split('.')[0].strip()
                    # Remove common prefixes
                    first_sentence = re.sub(r'^(Arrive|Visit|Enjoy|Head|Take|Have|Relax|Check|Spend|Explore|Go|Grab|Return)\s+(?:at|to|for|up|in|on)\s+', '', first_sentence, flags=re.IGNORECASE)
                    # Extract first capitalized phrase or first 3-4 words
                    words = first_sentence.split()
                    if len(words) > 0:
                        # Try to find a proper noun or capitalized phrase
                        activity_candidates = []
                        for i, word in enumerate(words[:6]):  # Check first 6 words
                            # Remove punctuation
                            clean_word = word.strip('.,!?;:')
                            if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
                                activity_candidates.append(clean_word)
                                if len(activity_candidates) >= 2:  # Get 2-3 word phrase
                                    break
                        activity_name = ' '.join(activity_candidates) if activity_candidates else ' '.join([w.strip('.,!?;:') for w in words[:3] if w.strip('.,!?;:')])
                    else:
                        activity_name = first_sentence[:50]  # Fallback to first 50 chars
                
                # If still no good activity name, use first few words
                if not activity_name or len(activity_name) < 3:
                    words = time_content_clean.split()
                    activity_name = ' '.join([w.strip('.,!?;:') for w in words[:4] if w.strip('.,!?;:')]) or 'Activity'
                
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Time block {idx+1}: time_name='{time_name}', activity_name='{activity_name}'")
                
                # Final content cleanup for display
                time_content_clean = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', time_content_clean)
                time_content_clean = re.sub(r'\s+', ' ', time_content_clean).strip()
                
                html += f'<div class="time-block">\n'
                html += f'<span class="time">{emoji} {time_name.capitalize()}</span>\n'
                html += f'<strong>{activity_name}</strong>\n'
                html += f'<p>{time_content_clean}</p>\n'
                
                # Add booking links for activities using MCP tools
                if activity_name and len(activity_name) > 3:
                    logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Attempting to generate links for activity: '{activity_name}'")
                    links_html = self._generate_activity_links(activity_name)
                    if links_html:
                        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Successfully generated links for '{activity_name}', adding to HTML")
                        html += links_html
                    else:
                        logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] No links generated for '{activity_name}'")
                else:
                    logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Skipping link generation - activity_name too short or empty: '{activity_name}'")
                
                html += '</div>\n'
            
            html += '</div>\n\n'
        
        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Markdown conversion complete. Generated HTML length: {len(html)} chars")
        logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Final HTML preview (first 500 chars):\n{html[:500]}")
        return html
    
    def _generate_activity_links(self, activity_name: str, destination: Optional[str] = None) -> str:
        """
        Generate Lonely Planet and Trip.com links for an activity using MCP tools
        
        Args:
            activity_name: Name of the activity/attraction
            destination: Destination name to include in search query (e.g., "Bali")
            
        Returns:
            HTML string with booking links
        """
        logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Starting link generation for activity: '{activity_name}'")
        links_html = ''
        
        # Clean activity name: strip emojis, time indicators, and special characters
        import re
        cleaned_activity = activity_name
        
        # Remove emojis (common unicode ranges for emojis)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols extended-A
            "\U00002600-\U000026FF"  # misc symbols
            "]+", 
            flags=re.UNICODE
        )
        cleaned_activity = emoji_pattern.sub('', cleaned_activity)
        
        # Remove time indicators that might be in the activity name
        time_indicators = [
            r'^(Morning|Afternoon|Evening|Night|Dawn|Dusk)\s*[:\-–]\s*',  # "Morning: ", "Afternoon - "
            r'^(Early|Late|Mid)\s+(Morning|Afternoon|Evening)\s*[:\-–]\s*',  # "Early Morning: "
            r'^\d{1,2}:\d{2}\s*(AM|PM|am|pm)?\s*[:\-–]\s*',  # "9:00 AM: "
            r'^\d{1,2}\s*(AM|PM|am|pm)\s*[:\-–]\s*',  # "9 AM: "
        ]
        for pattern in time_indicators:
            cleaned_activity = re.sub(pattern, '', cleaned_activity, flags=re.IGNORECASE)
        
        # Remove leading/trailing whitespace and special characters
        cleaned_activity = cleaned_activity.strip(' \t\n\r-–—:')
        
        # If cleaning resulted in empty string, use original
        if not cleaned_activity or len(cleaned_activity) < 3:
            cleaned_activity = activity_name.strip()
        
        logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Cleaned activity name: '{activity_name}' -> '{cleaned_activity}'")
        
        # Check if travel_content tool is enabled
        is_enabled = mcp_manager.is_tool_enabled('travel_content.links') #previously tool_name is travel_content
        logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Tool enabled: {is_enabled}")
        
        # Build search query with destination if available
        search_query = cleaned_activity
        if destination and destination.strip():
            # Combine destination and cleaned activity for better search results
            # Format: "Destination ActivityName" (e.g., "Bali Motel Mexicola")
            search_query = f"{destination.strip()} {cleaned_activity}"
            logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Using search query with destination: '{search_query}'")
        else:
            logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] No destination provided (destination={destination}), using cleaned activity name only: '{cleaned_activity}'")
        
        # Generate Lonely Planet link using MCP tool
        lp_url = None
        if is_enabled:
            try:
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Calling lonely_planet_url for: '{search_query}'")
                lp_result = mcp_manager.call_tool(
                    tool_name='travel_content.links', #previously tool_name is travel_content
                    arguments={
                        'link_type': 'lonely_planet_url',
                        'attraction_name': search_query
                    }
                )
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Lonely Planet result: {lp_result}")
                if lp_result.get('success'):
                    lp_url = lp_result.get('url')
                    logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Lonely Planet URL generated successfully: {lp_url}")
                else:
                    error_msg = lp_result.get('error', 'Unknown error')
                    logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Lonely Planet URL generation failed: {error_msg}")
            except Exception as e:
                logger.error(f"[Agent Executor] ❌ [Travel Content MCP] Exception calling MCP for Lonely Planet URL: {e}", exc_info=True)
        
        # Fallback to hardcoded URL if MCP fails
        if not lp_url:
            search_encoded = search_query.replace(' ', '+')
            lp_url = f"https://www.lonelyplanet.com/search?q={search_encoded}&sortBy=pois"
            logger.info(f"[Agent Executor] 🔄 [Travel Content MCP] Using fallback Lonely Planet URL: {lp_url}")
        
        # Generate Trip.com link using MCP tool
        trip_url = None
        if is_enabled:
            try:
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Calling trip_com_url for: '{search_query}'")
                trip_result = mcp_manager.call_tool( #previously tool_name is travel_content
                    tool_name='travel_content.links',
                    arguments={
                        'link_type': 'trip_com_url',
                        'attraction_name': search_query
                    }
                )
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Trip.com result: {trip_result}")
                if trip_result.get('success'):
                    trip_url = trip_result.get('url')
                    logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Trip.com URL generated successfully: {trip_url}")
                else:
                    error_msg = trip_result.get('error', 'Unknown error')
                    logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Trip.com URL generation failed: {error_msg}")
            except Exception as e:
                logger.error(f"[Agent Executor] ❌ [Travel Content MCP] Exception calling MCP for Trip.com URL: {e}", exc_info=True)
        
        # Fallback to hardcoded URL if MCP fails
        if not trip_url:
            from urllib.parse import quote
            search_encoded = quote(search_query)
            trip_url = f"https://www.trip.com/global-search/searchlist/search/?keyword={search_encoded}&from=home"
            logger.info(f"[Agent Executor] 🔄 [Travel Content MCP] Using fallback Trip.com URL (search_query='{search_query}'): {trip_url}")
        
        # Add links to HTML (alternate between Lonely Planet and Trip.com for variety)
        # Use Lonely Planet for exploration, Trip.com for booking
        # Match prompt format: 📚 for Lonely Planet, 🎫 for Trip.com
        links_html += f'<a href="{lp_url}" target="_blank" class="booking-link">📚 Explore on Lonely Planet →</a>\n'
        links_html += f'<a href="{trip_url}" target="_blank" class="booking-link">🎫 Book on Trip.com →</a>\n'
        
        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Link generation complete. Generated HTML length: {len(links_html)} chars")
        logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Generated HTML: {links_html[:200]}...")
        
        return links_html
    
    def _enhance_itinerary_with_mcp_links(self, itinerary_html: str, destination: Optional[str] = None) -> str:
        """
        Extract activity names from itinerary HTML and generate proper links using MCP tools.
        Replaces or adds booking links for each activity.
        
        Args:
            itinerary_html: The itinerary HTML content
            destination: Destination name to include in search queries (e.g., "Bali")
            
        Returns:
            Enhanced HTML with MCP-generated links
        """
        import re
        
        logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Starting itinerary enhancement (HTML length: {len(itinerary_html)})")
        logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Destination: {destination}")
        
        if not itinerary_html or len(itinerary_html) < 50:
            logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] Itinerary HTML too short or empty, skipping enhancement")
            return itinerary_html
        
        # Find all time blocks (using non-greedy match with DOTALL to handle nested content)
        # Pattern captures the full time-block div including opening and closing tags
        # More robust pattern that handles whitespace and different attribute orders
        time_block_pattern = r'(<div\s+class\s*=\s*["\']time-block["\'][^>]*>.*?</div>)'
        time_blocks = re.finditer(time_block_pattern, itinerary_html, re.DOTALL | re.IGNORECASE)
        
        # Collect all matches with their positions first
        matches_with_positions = []
        for match in time_blocks:
            matches_with_positions.append((match.start(), match.end(), match.group(1)))
        
        if not matches_with_positions:
            logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] No time blocks found in itinerary HTML")
            logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] HTML preview (first 500 chars): {itinerary_html[:500]}")
            return itinerary_html
        
        # Process in reverse order to maintain string positions
        enhanced_html = itinerary_html
        enhanced_count = 0
        skipped_count = 0
        error_count = 0
        
        logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Found {len(matches_with_positions)} time blocks to process")
        
        for start, end, full_match in reversed(matches_with_positions):
            time_block = full_match
            
            try:
                # Extract activity name from <h3> tag (format: "🌅 Morning: Activity Name")
                # or from <strong> tag as fallback
                h3_match = re.search(r'<h3>[^:]*:\s*([^<]+)</h3>', time_block)
                strong_match = re.search(r'<strong>([^<]+)</strong>', time_block)
                
                if h3_match:
                    activity_name = h3_match.group(1).strip()
                    logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Extracted activity from h3: '{activity_name}'")
                elif strong_match:
                    activity_name = strong_match.group(1).strip()
                    logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Extracted activity from strong: '{activity_name}'")
                else:
                    # Try to extract from <li> items - get the first substantial activity
                    li_matches = re.findall(r'<li>([^<]+)', time_block)
                    activity_name = None
                    for li_text in li_matches:
                        li_clean = li_text.strip()
                        # Skip short or generic entries
                        if len(li_clean) > 15 and not any(skip in li_clean.lower() for skip in ['arrive at', 'transfer to', 'check-in', 'check out']):
                            # Extract key words (first few meaningful words)
                            words = li_clean.split()[:5]
                            activity_name = ' '.join(words)
                            break
                    
                    if not activity_name:
                        logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] No activity found in time block, skipping")
                    skipped_count += 1
                    continue
                
                # Skip generic phrases that aren't actual bookable activities
                # Expanded list of non-bookable generic activities
                skip_phrases = [
                    # Travel actions
                    'arrival', 'departure', 'depart', 'arrive', 'transfer', 'check-in', 'check out',
                    'settle in', 'head to', 'make your way', 'proceed to',
                    # Generic time/farewell
                    'farewell', 'leisure', 'free time', 'relax', 'rest', 'unwind',
                    'at your own pace', 'explore at leisure', 'day at leisure',
                    # Generic meals without specific venue
                    'breakfast at hotel', 'lunch break', 'dinner at resort', 'hotel breakfast',
                    'in-room dining', 'room service', 'quick bite', 'grab lunch',
                    # Generic travel phrases
                    'pack your bags', 'last minute', 'final moments', 'say goodbye',
                    'end of trip', 'return journey', 'head back', 'fly home'
                ]
                activity_lower = activity_name.lower()
                
                # Check if activity matches any skip phrase
                is_generic = False
                for phrase in skip_phrases:
                    if phrase in activity_lower or activity_lower.startswith(phrase):
                        is_generic = True
                        break
                
                if is_generic:
                    logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Skipping generic activity: '{activity_name}'")
                    skipped_count += 1
                    continue
                
                # Skip if too short
                if len(activity_name) < 3:
                    logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Activity name too short: '{activity_name}', skipping")
                    skipped_count += 1
                    continue
                
                # Positive matching: only generate links for bookable activity types
                bookable_keywords = [
                    # Attractions
                    'temple', 'beach', 'museum', 'park', 'waterfall', 'viewpoint', 'palace',
                    'monument', 'ruins', 'sanctuary', 'garden', 'island', 'cave', 'lake',
                    'mountain', 'volcano', 'market', 'village', 'fort', 'castle',
                    # Experiences & Tours
                    'tour', 'cruise', 'spa', 'massage', 'cooking class', 'diving', 'snorkeling',
                    'kayaking', 'rafting', 'trekking', 'hiking', 'safari', 'excursion',
                    'adventure', 'experience', 'workshop', 'lesson', 'ride', 'boat trip',
                    # Dining (specific venues)
                    'restaurant', 'cafe', 'bar', 'bistro', 'rooftop', 'dinner cruise',
                    # Cultural
                    'show', 'performance', 'dance', 'festival', 'ceremony'
                ]
                
                # Check if activity contains any bookable keyword
                has_bookable_keyword = any(kw in activity_lower for kw in bookable_keywords)
                
                # Check if it's a proper noun (likely a specific place name)
                # Proper nouns typically have capitalized words that aren't common words
                words = activity_name.split()
                common_words = {'the', 'a', 'an', 'and', 'or', 'at', 'in', 'on', 'to', 'for', 'with', 'by', 'of'}
                is_proper_noun = any(
                    word[0].isupper() and word.lower() not in common_words and len(word) > 2
                    for word in words if word
                )
                
                if not has_bookable_keyword and not is_proper_noun:
                    logger.debug(f"[Agent Executor] 🔗 [Travel Content MCP] Activity '{activity_name}' has no bookable keywords and is not a proper noun, skipping")
                    skipped_count += 1
                    continue
                
                logger.info(f"[Agent Executor] 🔗 [Travel Content MCP] Processing activity: '{activity_name}' (destination: '{destination}', bookable_keyword: {has_bookable_keyword}, proper_noun: {is_proper_noun})")
                
                # Generate links using MCP tools (include destination in search query)
                links_html = self._generate_activity_links(activity_name, destination)
                
                if not links_html:
                    logger.warning(f"[Agent Executor] ⚠️ [Travel Content MCP] No links generated for '{activity_name}'")
                    skipped_count += 1
                    continue
                
                # Check if links already exist in this time block
                if 'booking-link' in time_block:
                    # Replace existing links with MCP-generated ones
                    existing_links_pattern = r'(<a[^>]*class="booking-link"[^>]*>.*?</a>\s*)'
                    existing_links = re.findall(existing_links_pattern, time_block, re.DOTALL)
                    
                    if existing_links:
                        # Remove existing links
                        time_block_cleaned = re.sub(existing_links_pattern, '', time_block, flags=re.DOTALL)
                        # Add new MCP-generated links before closing </div>
                        time_block_enhanced = time_block_cleaned.replace('</div>', links_html + '</div>')
                        # Replace at specific position
                        enhanced_html = enhanced_html[:start] + time_block_enhanced + enhanced_html[end:]
                        enhanced_count += 1
                        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Replaced existing links for '{activity_name}'")
                    else:
                        # Links detected but pattern didn't match - add new ones anyway
                        time_block_enhanced = time_block.replace('</div>', links_html + '</div>')
                        enhanced_html = enhanced_html[:start] + time_block_enhanced + enhanced_html[end:]
                        enhanced_count += 1
                        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Added new links (replacing existing) for '{activity_name}'")
                else:
                    # Add links before closing </div> of time-block
                    time_block_enhanced = time_block.replace('</div>', links_html + '</div>')
                    # Replace at specific position
                    enhanced_html = enhanced_html[:start] + time_block_enhanced + enhanced_html[end:]
                    enhanced_count += 1
                    logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Added new links for '{activity_name}'")
            except Exception as e:
                error_count += 1
                logger.error(f"[Agent Executor] ❌ [Travel Content MCP] Error processing time block: {e}")
                import traceback
                logger.error(f"[Agent Executor] Traceback: {traceback.format_exc()}")
                continue
        
        logger.info(f"[Agent Executor] ✅ [Travel Content MCP] Enhancement complete: {enhanced_count} enhanced, {skipped_count} skipped, {error_count} errors")
        return enhanced_html

    
    def _extract_and_add_time_blocks(self, html_text: str, destination: Optional[str]) -> str:
        """Extract time blocks from HTML that has day cards but missing time blocks"""
        import re
        logger.warning(f"[Agent Executor] HTML structure found but time blocks missing - cannot auto-extract")
        return html_text

    
    def _create_summary_card(self, destination: Optional[str], duration: Optional[str], pace: Optional[str]) -> str:
        """Create a summary card HTML for the chat"""
        dest_display = destination or 'Your Destination'
        dur_display = duration or 'Custom Duration'
        pace_display = pace.title() if pace else 'Customized'
        
        return f"""<div class="recommendation-card">
<div class="rec-header">
    <span class="rec-badge">✨ Recommended for you</span>
    <span class="best-offer">Best Itinerary</span>
</div>
<div class="rec-content">
    <h3 class="rec-title">🗾 {dest_display} Adventure</h3>
    <p class="rec-subtitle">{dur_display} • {pace_display} Pace</p>
</div>
<div class="rec-details">
    <p><strong>Personalized for you:</strong> A carefully crafted itinerary featuring the best of {dest_display}, tailored to your preferences for a {pace_display.lower() if pace else 'memorable'} experience.</p>
</div>
<div class="rec-actions">
    <button class="get-plan-btn" onclick="openItineraryPanel()">View complete itinerary</button>
</div>
</div>"""

