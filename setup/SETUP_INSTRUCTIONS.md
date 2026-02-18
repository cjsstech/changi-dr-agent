# Setup Instructions

## Quick Start Guide

### Step 1: Install Python Dependencies

Open your terminal in the project directory and run:

```bash
pip install -r requirements.txt
```

### Step 2: Set Up API Key (Optional)

Your Gemini API key is already configured in `config.py`. If you want to use a different key, you can either:

**Option A:** Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_new_api_key_here
```

**Option B:** Export as environment variable:
```bash
export GEMINI_API_KEY=your_new_api_key_here
```

### Step 3: Run the Application

```bash
python app.py
```

### Step 4: Access the Application

Open your web browser and go to:
```
http://localhost:5001
```

## Testing the Chatbot

1. Click on any "Example #" button to load a pre-written prompt
2. Or type your own travel preferences
3. Click "Send" or press Enter
4. Wait for the AI to generate personalized recommendations

## Troubleshooting

### If you get "Module not found" errors:
```bash
pip install --upgrade -r requirements.txt
```

### If port 5000 is already in use:
Edit `config.py` and change the PORT value, or run:
```bash
python app.py
# Then manually edit app.py to use a different port
```

### If API calls fail:
- Check your internet connection
- Verify the API key is correct in `config.py`
- Check Gemini API quota/limits

## Project Structure

```
changi-travel-bot/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── README.md            # Project documentation
├── SETUP_INSTRUCTIONS.md # This file
├── static/
│   ├── style.css        # Styling
│   └── script.js        # Frontend logic
└── templates/
    └── index.html       # Main page template
```

## Next Steps

- Customize the SYSTEM_PROMPT in `app.py` to adjust AI behavior
- Modify `style.css` to change the look and feel
- Add more example prompts in `app.py`
- Enhance the UI with additional features

Enjoy your Travel Inspiration Hub! 🌍✈️

