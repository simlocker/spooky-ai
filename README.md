# Spooky AI 👻

A hands-on demo app showing how to build a secure AI chat interface powered by **[Prompt Security](https://prompt.security)** (a SentinelOne company). It supports multiple LLM providers and two integration methods — direct API calls and AI Gateway (reverse proxy) — so you can compare protected vs. unprotected behavior side by side.

> **Prompt Security** provides real-time protection for AI applications: it detects and blocks prompt injection attacks, redacts sensitive data (PII, secrets), and enforces usage policies — all inline, before prompts reach the LLM and before responses reach the user.

---

## Features

- 🔀 **Two integration methods**
  - **API mode** — app calls the LLM directly; Prompt Security checks prompts/responses via its `/api/protect` endpoint
  - **AI Gateway mode** — all traffic is routed through the Prompt Security reverse proxy, which intercepts and inspects requests inline
- 🤖 **Six LLM integrations** — Gemini (free tier), Groq (free tier), Cohere, OpenRouter, OpenAI, and Gemini via AI Gateway
- 🛡️ **Side-by-side comparison** — send the same prompt to a protected and unprotected chat simultaneously to see the difference
- 📎 **File uploads** — attach `.txt`, `.pdf`, or image files to your prompts
- 💡 **Trigger prompts** — pre-built sample prompts organized by attack category (prompt injection, PII, jailbreaks, etc.)
- 👤 **User identity** — set a user email passed to Prompt Security for per-user policy enforcement
- 📊 **Session stats** — live block/redaction counters and latency per session

---

## Requirements

- Docker and Docker Compose
- A **Prompt Security** account with an App ID and Gateway URL (mandatory)
- At least **one** LLM API key (Gemini Free Tier and Groq are both free)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/simlocker/spooky-ai.git
cd spooky-ai
```

### 2. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Fill in your keys and Prompt Security credentials:

| Variable | Required | Description |
| :--- | :---: | :--- |
| `PS_APP_ID` | ✅ | Your Prompt Security App ID |
| `PS_GATEWAY_URL` | ✅ | Your Prompt Security Gateway base URL (e.g. `https://xxxxx.prompt.security`) |
| `DEMO_USER_EMAIL` | — | Email identity sent to PS for per-user policies (default: `user@example.com`) |
| `GEMINI_FREE_API_KEY` | ⬇️ one required | Google AI Studio key — [get one free](https://aistudio.google.com/app/apikey) |
| `GROQ_API_KEY` | ⬇️ one required | Groq key — [get one free](https://console.groq.com/keys) |
| `COHERE_API_KEY` | optional | Cohere key — [free trial](https://dashboard.cohere.com/api-keys) |
| `OPENROUTER_API_KEY` | optional | OpenRouter key — [free models available](https://openrouter.ai/keys) |
| `OPENAI_API_KEY` | optional | OpenAI key (also required for AI Gateway OpenAI mode) |

### 3. Run with Docker

```bash
docker compose up -d --build
```

### 4. Open the app

Navigate to **http://your-ip-address:8501** in your browser.

---

## Integration Methods Explained

### API Mode
The app calls the LLM provider directly. Before each call, the prompt is sent to the Prompt Security `/api/protect` endpoint — which either blocks it, redacts sensitive content, or passes it through clean. The LLM response goes through the same check before being shown to the user.

### AI Gateway Mode (Reverse Proxy)
All LLM traffic is routed through the Prompt Security Gateway (`PS_GATEWAY_URL/v1/`). The gateway inspects requests inline and forwards them to the provider using a `forward-domain` header. Currently supported providers via gateway: **OpenAI** and **Gemini**.

---

## Project Structure

```
spooky-ai/
├── app.py                 # Main Streamlit application
├── triggers.txt           # Sample prompts shown in the sidebar
├── requirements.txt       # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── .env.example           # Environment variable template
└── .streamlit/
    └── config.toml        # UI theme configuration
```

---

## Contributors

- **dawinci**
- **Gastón Z** — 2025
