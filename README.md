# Spooky AI - Homegrown App 🛡️

A secure AI chat interface featuring Prompt Security integration.

## Setup Instructions

1. **Clone the repo**
   ```bash
   git clone github.com/simlocker/spooky-ai.git
   cd spooky-ai

2. **Configure Keys**
   Copy the example environment file and populate the required fields:
   ```bash
   cp .env.example .env
   # Open .env and paste your API Keys (Gemini, OpenAI, Prompt Security) and other information.

(Please note the app won't work unless there's at least ONE API key present for the LLMs.)

3. **Run with Docker**
   ```bash
   docker compose up -d --build

3. **Access your Instance**
   Open your browser to http://localhost:8501

