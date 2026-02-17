# Spooky AI 👻 - Homegrown App 

A secure AI chat interface featuring Prompt Security (a SentinelOne company) integration.

** This app needs either a Google Gemini (Free Tier!) and/or OpenAI API key **

## Setup Instructions

1. **Clone the repo**
   ```bash
   git clone https://github.com/simlocker/spooky-ai.git
   cd spooky-ai

2. **Configure Keys and other Data**

   Copy the example environment file and populate the required fields:
   ```bash
   cp .env.example .env
   # Open .env and paste your API Keys (Gemini, OpenAI, Prompt Security) and other information.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DEMO_USER_EMAIL` | `user@example.com` | Change this depending on your Prompt Security policies defined for Homegrown Apps. |
| `PS_APP_ID` | `-` | Your Prompt Security App Id (api key) |
| `PS_GATEWAY_URL` | `https://******.prompt.security` | Change this to your Prompt Security base URL |
| `GEMINI_FREE_API_KEY` | `-` | Your Google AI Studio API key |
| `OPENAI_API_KEY` | `-` | Your OpenAI API key |

(Please note the app won't work unless there's at least ONE API key present for one of the LLMs.)

3. **Run with Docker**
   ```bash
   docker compose up -d --build

3. **Access your Instance**
   Open your browser to http://your-ip-address:8501


##

More detailed information coming soon....
