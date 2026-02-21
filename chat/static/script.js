// Global variable to store the current itinerary
let currentItinerary = null;
let currentTripData = null;

// MCP Server URL for visa checking
// MCP Server URL for visa checking
// MCP_SERVER_URL is injected from index.html
// define a local variable to avoid conflict with global const if script.js is loaded after
const mcpApiUrl = (typeof MCP_SERVER_URL !== 'undefined') ? MCP_SERVER_URL : 'http://localhost:8002/mcp';
const apiBase = (typeof API_BASE !== 'undefined') ? API_BASE : '';

// Store current destination for visa check
let currentVisaDestination = null;

// Global function to open itinerary panel (must be outside DOMContentLoaded)
function openItineraryPanel() {
    const resultsPanel = document.getElementById('resultsPanel');
    const resultsContent = document.getElementById('resultsContent');
    const appContainer = document.querySelector('.app-container');

    if (currentItinerary && resultsPanel) {
        // Update panel header
        const headerContent = resultsPanel.querySelector('.results-header-content h2');
        if (headerContent) {
            headerContent.textContent = currentTripData?.destination ?
                `${currentTripData.destination} Itinerary` : 'Your Travel Itinerary';
        }

        // Generate Now Boarding articles section
        const articlesSection = generateArticlesSection(currentTripData?.articles, currentTripData?.destination);

        // Get flight options HTML (pre-formatted by backend)
        const flightOptionsHtml = currentTripData?.flight_options_html || '';

        // Generate Google Maps section
        const mapsSection = generateGoogleMapsSection(currentTripData?.locations, currentTripData?.destination);

        // Generate Visa Checker section
        const visaSection = generateVisaCheckerSection(currentTripData?.destination);

        // Update panel content: Itinerary → Visa Checker → Now Boarding → Flight Options → Maps
        if (resultsContent) {
            resultsContent.innerHTML = `
                <div class="itinerary-panel-content">
                    ${currentItinerary}
                    ${visaSection}
                    ${articlesSection}
                    ${flightOptionsHtml}
                    ${mapsSection}
                </div>
            `;
        }

        // Show the panel
        resultsPanel.classList.add('open');
        appContainer.classList.add('split-view');
    } else {
        console.log('No itinerary available yet');
    }
}

// Generate Now Boarding articles section with real API data
function generateArticlesSection(articles, destination) {
    if (!articles || articles.length === 0) {
        return '';
    }

    const searchUrl = `https://nowboarding.changiairport.com/search.html?searchTerm=${encodeURIComponent(destination || '')}`;

    // Generate article cards with title, excerpt, and date
    const articleCardsHTML = articles.map(article => `
        <a href="${article.url}" class="nb-article-card" target="_blank">
            <div class="nb-article-content">
                <h5 class="nb-article-title">${article.title}</h5>
                <p class="nb-article-excerpt">${article.description || ''}</p>
                ${article.date ? `<span class="nb-article-meta">${article.date}${article.category ? ' • ' + article.category : ''}</span>` : ''}
            </div>
            <span class="nb-article-arrow">→</span>
        </a>
    `).join('');

    return `
        <div class="nb-articles-section">
            <div class="nb-section-header">
                <span class="nb-icon">📖</span>
                <h4>Discover More About ${destination || 'Your Destination'}</h4>
            </div>
            <div class="nb-articles-list">
                ${articleCardsHTML}
            </div>
            <a href="${searchUrl}" class="nb-see-all-link" target="_blank">
                See all articles on Now Boarding →
            </a>
        </div>
    `;
}

// Generate Google Maps URL for directions with multiple stops
function generateGoogleMapsDirectionsURL(locations) {
    if (!locations || locations.length === 0) return '#';

    // Google Maps directions URL format:
    // https://www.google.com/maps/dir/Place1/Place2/Place3
    const baseURL = 'https://www.google.com/maps/dir/';

    // Use location names for the URL
    const stops = locations.map(loc => encodeURIComponent(loc.name)).join('/');

    return baseURL + stops;
}

// Generate Google Maps URL for a single location search
function generateGoogleMapsSearchURL(locationName) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locationName)}`;
}

// Generate simple Google Maps section with save button
function generateGoogleMapsSection(locations, destination) {
    // Always show Google Maps section if we have a destination
    if (!destination) {
        console.log('[Frontend] No destination provided for map');
        return '';
    }

    // If no specific locations, show a simple map link for the destination
    if (!locations || locations.length === 0) {
        console.log('[Frontend] No specific locations, showing destination-only map link');
        const mapsURL = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(destination)}`;

        return `
        <div class="map-card">
            <div class="map-preview">
                <div class="map-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                        <circle cx="12" cy="9" r="2.5"/>
                    </svg>
                </div>
                <div class="map-info">
                    <h4>Explore ${destination}</h4>
                    <p>View on Google Maps</p>
                </div>
            </div>
            <a href="${mapsURL}" class="save-maps-btn" target="_blank">
                <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                </svg>
                Open in Google Maps
            </a>
        </div>
    `;
    }

    console.log(`[Frontend] Generating map with ${locations.length} locations:`, locations.map(loc => loc.name));
    console.log(`[Frontend] Location details:`, locations);

    // Group locations by day
    const locationsByDay = {};
    locations.forEach(loc => {
        const day = loc.day || 1;
        if (!locationsByDay[day]) {
            locationsByDay[day] = [];
        }
        locationsByDay[day].push(loc);
    });

    // Generate location list HTML grouped by day
    const dayColors = ['#667eea', '#34a853', '#ea4335', '#fbbc04', '#4285f4', '#9334ea'];
    let locationListHTML = '<div class="map-locations-list">';

    Object.keys(locationsByDay).sort((a, b) => parseInt(a) - parseInt(b)).forEach(day => {
        const dayLocs = locationsByDay[day];
        const dayColor = dayColors[(parseInt(day) - 1) % dayColors.length];

        locationListHTML += `<div class="map-day-group">
            <div class="map-day-header" style="border-left: 3px solid ${dayColor};">
                <span class="map-day-label">Day ${day}</span>
            </div>
            <div class="map-day-locations">`;

        dayLocs.forEach((loc, idx) => {
            const hasCoords = loc.lat && loc.lon;
            const pinIcon = hasCoords ? '📍' : '📌';
            locationListHTML += `
                <div class="map-location-item">
                    <span class="location-pin" style="color: ${dayColor};">${pinIcon}</span>
                    <span class="location-name">${loc.name}</span>
                </div>`;
        });

        locationListHTML += `</div></div>`;
    });

    locationListHTML += '</div>';

    // Build Google Maps URL with all locations
    // Use coordinates if available for more accurate pins
    const locationsWithCoords = locations.filter(loc => loc.lat && loc.lon);
    const locationsWithoutCoords = locations.filter(loc => !loc.lat || !loc.lon);

    let mapsURL;
    if (locationsWithCoords.length > 0) {
        // Use directions URL with coordinates for locations that have them
        const allPlaces = locations.map(loc => {
            if (loc.lat && loc.lon) {
                return `${loc.lat},${loc.lon}`;
            } else {
                return encodeURIComponent(loc.name + ', ' + (destination || ''));
            }
        }).join('/');
        mapsURL = `https://www.google.com/maps/dir/${allPlaces}`;
        console.log(`[Frontend] Generated Maps URL with ${locationsWithCoords.length} geocoded locations`);
    } else {
        // Fallback: use place names
        const placeNames = locations.map(loc => encodeURIComponent(loc.name + ', ' + destination)).join('/');
        mapsURL = `https://www.google.com/maps/dir/${placeNames}`;
        console.log(`[Frontend] Generated Maps URL with place names (no coordinates)`);
    }

    // Count total places and geocoded places
    const totalPlaces = locations.length;
    const geocodedPlaces = locationsWithCoords.length;
    const statusText = geocodedPlaces > 0
        ? `${totalPlaces} places with ${geocodedPlaces} pinned locations`
        : `${totalPlaces} places to visit`;

    return `
        <div class="map-card map-card-expanded">
            <div class="map-header">
                <div class="map-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                        <circle cx="12" cy="9" r="2.5"/>
                    </svg>
                </div>
                <div class="map-info">
                    <h4>📍 ${destination} Itinerary Map</h4>
                    <p>${statusText}</p>
                </div>
            </div>
            ${locationListHTML}
            <a href="${mapsURL}" class="save-maps-btn" target="_blank">
                <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                </svg>
                Open Itinerary Route in Google Maps
            </a>
        </div>
    `;
}

// Generate Visa Checker Section
function generateVisaCheckerSection(destination) {
    if (!destination) {
        return '';
    }

    // Store destination globally for the visa check function
    currentVisaDestination = destination;

    // Escape destination for safe HTML display
    const safeDestination = destination.replace(/'/g, "\\'").replace(/"/g, "&quot;");

    // Nationality options with country flags
    const nationalities = [
        { value: 'Singapore', flag: '🇸🇬' },
        { value: 'Malaysia', flag: '🇲🇾' },
        { value: 'Indonesia', flag: '🇮🇩' },
        { value: 'Philippines', flag: '🇵🇭' },
        { value: 'India', flag: '🇮🇳' },
        { value: 'China', flag: '🇨🇳' },
        { value: 'Japan', flag: '🇯🇵' },
        { value: 'South Korea', flag: '🇰🇷' },
        { value: 'United States', flag: '🇺🇸' },
        { value: 'United Kingdom', flag: '🇬🇧' },
        { value: 'Australia', flag: '🇦🇺' }
    ];

    // Generate dropdown options
    const nationalityOptions = nationalities.map(nat =>
        `<option value="${nat.value}">${nat.flag} ${nat.value}</option>`
    ).join('');

    return `
        <div class="visa-checker-section" id="visaCheckerSection">
            <div class="visa-section-header">
                <span class="visa-icon">🛂</span>
                <h4>Visa Requirements</h4>
            </div>
            <button class="visa-checker-btn" onclick="toggleVisaForm()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                Check Visa Requirements for ${safeDestination}
            </button>
            <div class="visa-nationality-form" id="visaNationalityForm">
                <label for="nationalitySelect">Select your nationality:</label>
                <select id="nationalitySelect" class="visa-nationality-select">
                    <option value="">-- Select your nationality --</option>
                    ${nationalityOptions}
                </select>
                <button class="visa-check-submit-btn" id="visaCheckBtn" onclick="checkVisaRequirements()" disabled>
                    Check Requirements
                </button>
                <div id="visaResultContainer"></div>
            </div>
        </div>
    `;
}

// Toggle visa form visibility
function toggleVisaForm() {
    const form = document.getElementById('visaNationalityForm');
    if (form) {
        form.classList.toggle('active');
    }
}

// Enable/disable visa check button based on selection
document.addEventListener('change', function (e) {
    if (e.target && e.target.id === 'nationalitySelect') {
        const checkBtn = document.getElementById('visaCheckBtn');
        if (checkBtn) {
            checkBtn.disabled = !e.target.value;
        }
    }
});

// Check visa requirements via MCP server
async function checkVisaRequirements() {
    const nationalitySelect = document.getElementById('nationalitySelect');
    const resultContainer = document.getElementById('visaResultContainer');
    const checkBtn = document.getElementById('visaCheckBtn');

    if (!nationalitySelect || !resultContainer) return;

    const nationality = nationalitySelect.value;
    if (!nationality) {
        resultContainer.innerHTML = '<div class="visa-error-message">Please select your nationality first.</div>';
        return;
    }

    // Use the globally stored destination
    const destination = currentVisaDestination;
    if (!destination) {
        resultContainer.innerHTML = '<div class="visa-error-message">Destination not found. Please try again.</div>';
        return;
    }

    // Show loading
    resultContainer.innerHTML = `
        <div class="visa-loading">
            <div class="visa-loading-spinner"></div>
            <span>Checking visa requirements...</span>
        </div>
    `;
    checkBtn.disabled = true;

    try {
        const response = await fetch(mcpApiUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                id: crypto.randomUUID(),
                method: "tools/call",
                params: {
                    name: "visa.requirements",
                    arguments: {
                        nationality: nationality,
                        destination: destination
                    }
                }
            })
        });

        const data = await response.json();

        if (data.result?.success) {
            resultContainer.innerHTML = generateVisaResultCard(data.result);
        } else {
            resultContainer.innerHTML = `
                <div class="visa-error-message">
                    ${data.result?.error || 'Unable to find visa information.'}<br>
                    ${data.result?.suggestion || 'Please check with the destination country\'s embassy.'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error checking visa requirements:', error);
        resultContainer.innerHTML = `
            <div class="visa-error-message">
                Unable to check visa requirements. Please try again later or visit 
                <a href="https://www.mfa.gov.sg/" target="_blank">MFA Singapore</a> for official information.
            </div>
        `;
    } finally {
        checkBtn.disabled = false;
    }
}

// Generate visa result card HTML
function generateVisaResultCard(data) {
    const statusClass = data.status.replace(/-/g, '-').replace(' ', '-');
    const statusIcons = {
        'visa-free': '✅',
        'visa-on-arrival': '🛂',
        'visa-required': '📋',
        'e-visa': '💻'
    };
    const statusLabels = {
        'visa-free': 'Visa-Free Entry',
        'visa-on-arrival': 'Visa on Arrival',
        'visa-required': 'Visa Required',
        'e-visa': 'e-Visa Required'
    };

    const icon = statusIcons[data.status] || '❓';
    const label = statusLabels[data.status] || data.status;

    return `
        <div class="visa-result-card ${statusClass}">
            <div class="visa-result-header">
                <span class="visa-status-icon">${icon}</span>
                <span class="visa-status-label">${label}</span>
            </div>
            <div class="visa-result-details">
                <p><strong>${data.nationality}</strong> passport holders traveling to <strong>${data.destination}</strong>:</p>
                <p>📅 <strong>Stay Duration:</strong> Up to ${data.days_allowed} days</p>
                ${data.note ? `<p>ℹ️ <strong>Note:</strong> ${data.note}</p>` : ''}
            </div>
            <div class="visa-disclaimer">
                ⚠️ ${data.disclaimer || 'This information is for reference only.'}<br>
                Always verify with official sources: <a href="${data.mfa_link || 'https://www.mfa.gov.sg/'}" target="_blank">Singapore MFA</a>
            </div>
        </div>
    `;
}

// Generate Flights section for the results panel
function generateFlightsSection(flights, departureDate, destination) {
    if (!flights || flights.length === 0) {
        return '';
    }

    // Format the departure date for display
    let dateDisplay = '';
    if (departureDate) {
        try {
            const dateObj = new Date(departureDate);
            dateDisplay = dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
        } catch (e) {
            dateDisplay = departureDate;
        }
    }

    // Generate flight cards
    const flightCardsHTML = flights.map((flight, index) => {
        const flightNumber = flight.flight_no || flight.flightNumber || 'N/A';
        const airline = flight.airline || 'Singapore Airlines';
        const departureTime = flight.scheduled_departure || flight.departureTime || 'N/A';
        const arrivalTime = flight.scheduled_arrival || flight.arrivalTime || 'N/A';
        const origin = flight.origin || 'SIN';
        const dest = flight.destination || destination?.toUpperCase()?.substring(0, 3) || 'N/A';

        // Extract just the time portion
        const depTimeDisplay = departureTime.includes('T') ? departureTime.split('T')[1]?.substring(0, 5) : departureTime;
        const arrTimeDisplay = arrivalTime.includes('T') ? arrivalTime.split('T')[1]?.substring(0, 5) : arrivalTime;

        return `
            <div class="flight-card">
                <div class="flight-header">
                    <span class="airline-name">✈️ ${airline}</span>
                    <span class="flight-number">${flightNumber}</span>
                </div>
                <div class="flight-route">
                    <div class="flight-time">
                        <span class="time">${depTimeDisplay}</span>
                        <span class="airport">${origin}</span>
                    </div>
                    <div class="flight-duration">
                        <span class="arrow">→</span>
                    </div>
                    <div class="flight-time">
                        <span class="time">${arrTimeDisplay}</span>
                        <span class="airport">${dest}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Generate Trip.com booking link
    const tripcomUrl = `https://www.trip.com/flights/${destination ? destination.toLowerCase().replace(/\s+/g, '-') : 'international'}`;

    return `
        <div class="flights-section">
            <div class="flights-section-header">
                <span class="flights-icon">✈️</span>
                <h4>Flight Options${dateDisplay ? ` for ${dateDisplay}` : ''}</h4>
            </div>
            <div class="flights-list">
                ${flightCardsHTML}
            </div>
            <a href="${tripcomUrl}" class="book-flights-btn" target="_blank">
                🎫 View More Flights on Trip.com →
            </a>
        </div>
    `;
}

document.addEventListener('DOMContentLoaded', function () {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const newChatBtn = document.getElementById('newChatBtn');
    const promptChips = document.querySelectorAll('.prompt-chip');
    const tripResults = document.getElementById('tripResults');
    const resultsPanel = document.getElementById('resultsPanel');
    const appContainer = document.querySelector('.app-container');
    const closePanelBtn = document.getElementById('closePanelBtn');
    const quickPromptsContainer = document.getElementById('quickPromptsContainer');
    const resultsContent = document.getElementById('resultsContent');

    // Destination images for different locations
    const destinationImages = {
        'tokyo': 'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=800',
        'japan': 'https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=800',
        'bali': 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=800',
        'thailand': 'https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?w=800',
        'singapore': 'https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=800',
        'paris': 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800',
        'london': 'https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=800',
        'korea': 'https://images.unsplash.com/photo-1517154421773-0529f29ea451?w=800',
        'seoul': 'https://images.unsplash.com/photo-1534274988757-a28bf1a57c17?w=800',
        'vietnam': 'https://images.unsplash.com/photo-1557750255-c76072a7aad1?w=800',
        'default': 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800'
    };

    // Show initial greeting
    setTimeout(() => {
        const agentName = document.querySelector('.header-badge')?.textContent || 'Travel Assistant';
        addMessage(`Hello! I'm ${agentName}! 👋✈️<br><br>I'm here to help you. How can I assist you today?`, 'bot');
    }, 500);

    // Auto-resize textarea
    userInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });

    // Send message handlers
    sendBtn.addEventListener('click', sendMessage);

    userInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // New chat handler
    newChatBtn.addEventListener('click', async function () {
        chatMessages.innerHTML = '';
        if (tripResults) tripResults.style.display = 'none';

        // Close right panel
        appContainer.classList.remove('split-view');
        if (quickPromptsContainer) quickPromptsContainer.style.display = 'block';

        // Reset session
        try {
            await fetch(`${apiBase}/api/reset`, { method: 'POST' });
        } catch (e) {
            console.error('Reset error:', e);
        }

        // Show greeting again
        setTimeout(() => {
            const agentName = document.querySelector('.header-badge')?.textContent || 'Travel Assistant';
            addMessage(`Hello! I'm ${agentName}! 👋✈️<br><br>Ready for a new adventure? Tell me how I can help!`, 'bot');
        }, 300);
    });

    // Close panel handler
    if (closePanelBtn) {
        closePanelBtn.addEventListener('click', function () {
            resultsPanel.classList.remove('open');
            appContainer.classList.remove('split-view');
        });
    }


    // Prompt chip handlers
    promptChips.forEach(chip => {
        chip.addEventListener('click', function () {
            userInput.value = this.dataset.prompt;
            userInput.focus();
            sendMessage();
        });
    });

    // Get agent ID from URL
    /*
    OLD Code to read path variable
    function getAgentId() {
        const path = window.location.pathname;
        const match = path.match(/\/agent\/([^\/]+)/);
        return match ? match[1] : null;
    }
    */
    function getAgentId() {
        // 1. Use the global agentId injected from the template
        if (typeof agentId !== 'undefined' && agentId) {
            return agentId;
        }
        // 2. Try URL path: /agent/<agent_id>
        const path = window.location.pathname;
        const match = path.match(/\/agent\/([^\/\?]+)/);
        if (match) return match[1];
        // 3. Try query param: /agent?agent_id=<agent_id>
        const params = new URLSearchParams(window.location.search);
        return params.get("agent_id");
    }

    // Main send function (non-streaming for full context support)
    async function sendMessage() {
        const message = userInput.value.trim();

        if (!message) return;

        // Add user message
        addMessage(message, 'user');

        // Clear input
        userInput.value = '';
        userInput.style.height = 'auto';

        // Show loading
        sendBtn.disabled = true;
        userInput.disabled = true;
        if (loadingOverlay) loadingOverlay.classList.add('active');

        try {
            // Get agent ID from URL
            const agentId = getAgentId();
            if (!agentId) {
                throw new Error('Agent ID not found in URL');
            }

            // Determine the correct chat endpoint
            const _isWorkflow = (typeof isWorkflow !== 'undefined') && isWorkflow;
            const chatUrl = _isWorkflow
                ? `${apiBase}/workflow/chat?workflow_id=${agentId}`
                : `${apiBase}/agent/chat?agent_id=${agentId}`;

            const response = await fetch(chatUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();

            if (data.success) {
                // Flight options are now embedded in the itinerary, no special handling needed
                addMessage(data.response, 'bot');

                // Store full itinerary if provided
                if (data.full_itinerary) {
                    console.log('[Frontend] Received full itinerary, length:', data.full_itinerary.length);
                    currentItinerary = data.full_itinerary;
                    currentTripData = {
                        destination: data.destination,
                        duration: data.duration,
                        locations: data.locations || [],
                        articles: data.articles || [],
                        flights: data.flights || [],
                        flight_options_html: data.flight_options_html || '',
                        departure_date: data.departure_date
                    };

                    // Panel will open when user clicks "View complete Itinerary" button
                    // Auto-open disabled - user controls when to view the panel
                    console.log('[Frontend] Itinerary ready - waiting for user to click View complete Itinerary');
                } else {
                    console.log('[Frontend] No full_itinerary in response');
                }
            } else {
                addMessage('I had trouble with that. Could you try rephrasing? 🤔', 'bot');
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('Oops! Connection issue. Please try again. 🔄', 'bot');
        } finally {
            sendBtn.disabled = false;
            userInput.disabled = false;
            if (loadingOverlay) loadingOverlay.classList.remove('active');
            userInput.focus();
        }
    }

    function addMessage(text, type) {
        const messageWrapper = document.createElement('div');
        messageWrapper.className = `message ${type}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';

        const content = document.createElement('div');
        content.className = 'message-content';

        if (type === 'bot') {
            // Add flight icon before the text
            content.innerHTML = '<span class="inline-flight-icon">✈️</span>' + text;

            // Add disclaimer for bot messages
            const disclaimer = document.createElement('p');
            disclaimer.className = 'bot-disclaimer';
            disclaimer.textContent = 'AI Assistant (beta) may not always get things right. Verify important details.';
            content.appendChild(disclaimer);
        } else {
            content.textContent = text;
        }

        messageWrapper.appendChild(avatar);
        messageWrapper.appendChild(content);
        chatMessages.appendChild(messageWrapper);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Event delegation for destination chip buttons
    // This handles dynamically added chip buttons in bot responses
    chatMessages.addEventListener('click', function (e) {
        const chipButton = e.target.closest('.chip-button');
        if (chipButton) {
            const destination = chipButton.dataset.destination;
            if (destination) {
                // Send the destination as a user message
                userInput.value = `I'd like to go to ${destination}`;
                sendMessage();
            }
        }
    });

    function updateResultsPanel(data) {
        const destination = data.destination || 'Your Destination';
        const context = data.context || {};

        // Show split view and results
        appContainer.classList.add('split-view');
        tripResults.style.display = 'flex';

        // Hide quick prompts when results show
        quickPromptsContainer.style.display = 'none';

        // Update destination card
        const destImage = document.getElementById('destinationImage');
        const destName = document.getElementById('destinationName');
        const destDuration = document.getElementById('destinationDuration');

        // Find matching image
        const destLower = destination.toLowerCase();
        let imageUrl = destinationImages.default;
        for (const [key, url] of Object.entries(destinationImages)) {
            if (destLower.includes(key)) {
                imageUrl = url;
                break;
            }
        }

        destImage.src = imageUrl;
        destImage.alt = destination;
        destName.textContent = destination;
        destDuration.textContent = context.duration || 'Your upcoming adventure';

        // Update itinerary (sample data - would be parsed from response)
        updateItinerary(destination, context);

        // Update experiences
        updateExperiences(destination);
    }

    function updateItinerary(destination, context) {
        const itineraryContent = document.getElementById('itineraryContent');

        // Generate sample itinerary based on destination
        const days = parseInt(context.duration) || 5;
        let html = '';

        for (let i = 1; i <= Math.min(days, 5); i++) {
            html += `
                <div class="itinerary-day">
                    <div class="day-number">${i}</div>
                    <div class="day-content">
                        <h5>Day ${i}</h5>
                        <p>Explore ${destination}'s highlights and local experiences</p>
                    </div>
                </div>
            `;
        }

        if (days > 5) {
            html += `
                <div class="itinerary-day">
                    <div class="day-number">+${days - 5}</div>
                    <div class="day-content">
                        <h5>${days - 5} More Days</h5>
                        <p>Continue your adventure with more experiences</p>
                    </div>
                </div>
            `;
        }

        itineraryContent.innerHTML = html;
    }

    function updateExperiences(destination) {
        const experiencesGrid = document.getElementById('experiencesGrid');

        const experiences = [
            { icon: '🍜', name: 'Local Cuisine', desc: 'Food tours & dining' },
            { icon: '🏛️', name: 'Cultural Sites', desc: 'Temples & museums' },
            { icon: '🛍️', name: 'Shopping', desc: 'Markets & boutiques' },
            { icon: '🌿', name: 'Nature', desc: 'Parks & gardens' }
        ];

        let html = '';
        experiences.forEach(exp => {
            html += `
                <div class="experience-card">
                    <span class="experience-icon">${exp.icon}</span>
                    <div class="experience-info">
                        <h5>${exp.name}</h5>
                        <p>${exp.desc}</p>
                    </div>
                </div>
            `;
        });

        experiencesGrid.innerHTML = html;
    }

    // Flight selection handler - make it globally accessible
    window.selectFlight = async function (flightIndex, flightNumber, arrivalTime) {
        // Mark selected card
        document.querySelectorAll('.flight-selection-card').forEach((card, idx) => {
            if (idx === flightIndex) {
                card.classList.add('selected');
                const indicator = card.querySelector('.flight-select-indicator');
                if (indicator) indicator.textContent = '✓ Selected';
            } else {
                card.classList.remove('selected');
            }
        });

        // Get agent ID
        const agentId = getAgentId();
        if (!agentId) {
            console.error('Agent ID not found');
            return;
        }

        // Show loading
        const loadingOverlay = document.querySelector('.loading-overlay');
        if (loadingOverlay) loadingOverlay.classList.add('active');

        try {
            // Send flight selection to backend
            const response = await fetch(`${apiBase}/agent/chat?agent_id=${agentId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: '',
                    selected_flight_index: flightIndex
                })
            });

            const data = await response.json();

            if (data.success) {
                // Add confirmation message
                addMessage(`Great! I've selected flight ${flightNumber}. Generating your itinerary now... ✈️`, 'bot');

                // Wait a moment, then show the itinerary response
                setTimeout(() => {
                    if (data.response) {
                        addMessage(data.response, 'bot');
                    }

                    // Store full itinerary if provided
                    if (data.full_itinerary) {
                        currentItinerary = data.full_itinerary;
                        currentTripData = {
                            destination: data.destination,
                            duration: data.duration,
                            locations: data.locations || [],
                            articles: data.articles || []
                        };

                        // Open itinerary panel if available
                        if (currentItinerary) {
                            openItineraryPanel();
                        }
                    }
                }, 500);
            } else {
                addMessage('I had trouble processing your flight selection. Please try again. 🤔', 'bot');
            }
        } catch (error) {
            console.error('Error selecting flight:', error);
            addMessage('Oops! Connection issue. Please try again. 🔄', 'bot');
        } finally {
            if (loadingOverlay) loadingOverlay.classList.remove('active');
        }
    };
});
