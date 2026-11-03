# Spooky AI 👻

A hands-on demo app showing how to build a secure AI chat interface powered by **[Prompt Security](https://prompt.security)** (a SentinelOne company). It supports multiple LLM providers — including any number of your own custom endpoints — and lets you compare protected vs. unprotected behavior side by side.

> **Prompt Security** provides real-time protection for AI applications: it detects and blocks prompt injection attacks, redacts sensitive data (PII, secrets), and enforces usage policies — all inline, before prompts reach the LLM and before responses reach the user.

---

## Features

- 🤖 **Four built-in LLM integrations** — Gemini (free tier), Groq (free tier), Cohere and OpenRouter — **plus as many custom providers as you like**
- 🔌 **Bring your own endpoints** — add any OpenAI-compatible service from the sidebar, give it a name, and its **model list loads automatically** (with ⭐ pinning for the models you actually use); no code changes or rebuild needed
- 🛡️ **Side-by-side comparison** — send the same prompt to a protected and unprotected chat simultaneously to see the difference
- 🔀 **Protection toggle** — switch Prompt Security off at any time to show the "before" picture
- 🎯 **Consistent answers** — a toggle (on by default) that sets the model temperature to 0, so runs and the two side-by-side columns are comparable
- 📨 **"What the model received"** — in side-by-side mode, each column has an expander showing the exact text sent to the model (the redacted prompt vs. the original)
- 📎 **File uploads** — attach `.txt`, `.pdf`, `.xlsx`, `.png` or `.jpg` files; their text is extracted and scanned together with your prompt (images are only passed to Gemini)
- 🧪 **Built-in sample files** — pick a ready-made, fictional file from the Upload menu (PII, secrets, a prompt-injection invoice, a clean control) and send it in one click
- ⌨️ **Prompt history** — press ↑ / ↓ in the chat box to recall your last 10 prompts (kept in a browser cookie)
- 💡 **Trigger prompts** — pre-built sample prompts organized by attack category (prompt injection, PII, jailbreaks, etc.)
- 👤 **User identity** — set a user email passed to Prompt Security for per-user policy enforcement
- 🧾 **Named policy** — optionally pin a specific Prompt Security policy instead of the connector default
- 🔎 **Debug views** — per-turn *Prompt Debug* and *Response Debug* boxes showing the status (Safe / Redacted / Blocked) and the raw `/api/protect` JSON
- 📊 **Session stats** — live block/redaction counters, latency and last violation per session
- 🎃 **Halloween mode** — click the **Spooky** title to switch a spooky theme on and off (bats, a witch, a spider that rappels onto the Upload button…). Purely cosmetic; the security behavior is identical
- 🗣️ **Block messages that match the reason** — a jailbreak, a leaked secret, sensitive data, a banned topic… each gets its own explanation. All wording lives in `app.py` (`CUSTOM_MESSAGES` and `BLOCK_MESSAGES`), so you can tailor it to your demo narrative

---

## Requirements

- Docker and Docker Compose
- A **Prompt Security** account with an App ID and Gateway URL (mandatory)
- At least **one** LLM API key (Gemini, Groq, OpenRouter and Cohere all have free tiers), **or** access to any OpenAI-compatible endpoint via the Custom provider

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

Fill in your keys and Prompt Security credentials. Keep `.env` private and out of version control.

**Prompt Security**

| Variable | Required | Description |
| :--- | :---: | :--- |
| `PS_APP_ID` | ✅ | Your Prompt Security App ID |
| `PS_GATEWAY_URL` | ✅ | Your Prompt Security Gateway base URL (e.g. `https://xxxxx.prompt.security`) |
| `PS_POLICY_NAME` | — | Pin a named policy (Homegrown Apps > Policies > *Manage Policies*). Blank = the connector's default policy |
| `DEMO_USER_EMAIL` | — | Default identity sent to PS for per-user policies (default: `john.doe@unknown.com`). Editable in the sidebar |
| `SHOW_CUSTOM_NOTICES` | — | `true` (default) shows the "redacted" / "security check error" banners; `false` hides them. Block messages are always shown |

**LLM providers** (at least one required, unless you use Custom)

| Variable | Required | Description |
| :--- | :---: | :--- |
| `GEMINI_FREE_API_KEY` | ⬇️ one required | Google AI Studio key — [get one free](https://aistudio.google.com/app/apikey) |
| `GROQ_API_KEY` | ⬇️ one required | Groq key — [get one free](https://console.groq.com/keys) |
| `COHERE_API_KEY` | optional | Cohere key — [free trial](https://dashboard.cohere.com/api-keys) |
| `OPENROUTER_API_KEY` | optional | OpenRouter key — [free models available](https://openrouter.ai/keys) |

**Gemini model selection** (all optional)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AUTO_SELECT_GEMINI_MODEL` | `true` | Pick a model automatically; `false` shows a model dropdown |
| `DEFAULT_GEMINI_MODEL` | `gemini-2.0-flash` | Preferred model |
| `FALLBACK_GEMINI_MODELS` | — | Comma-separated models to try if the preferred one is rate-limited (HTTP 429) |

**Custom providers** (all optional — see [Custom providers](#custom-providers))

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ALLOW_CUSTOM_ENDPOINTS` | `true` | Shows the **Custom** provider; `false` hides it |
| `ALLOW_PRIVATE_ENDPOINTS` | `false` | `true` lets Custom reach `http://`, localhost and private networks |
| `PERSIST_PROVIDERS` | — | `false` (default). `true` saves custom providers — **including their API keys, in plain text** — to `data/providers.json` so they survive restarts. `data/` is git-ignored |
| `CUSTOM_PROVIDERS` | — | Optional JSON list that pre-loads several named custom providers (see [Custom providers](#custom-providers)) |
| `CUSTOM_BASE_URL` / `CUSTOM_API_KEY` / `CUSTOM_MODEL` | — | Optional shortcut: pre-loads **one** extra provider named `Custom` |

### 3. Run with Docker

```bash
docker compose up -d --build
```

### 4. Open the app

Navigate to **http://your-ip-address:8501** in your browser.

> **Updating:** the project folder is mounted into the container, so edits to `app.py` are read from disk. Run `docker compose restart` after code or `.env` changes, and `docker compose up -d --build` after changing `requirements.txt`.

---

## Using the app

The sidebar controls everything:

| Control | What it does |
| :--- | :--- |
| **Enable Prompt Security** | Turns protection on/off. When off, prompts and responses go straight through |
| **Side-by-side Comparison** | Sends each prompt twice: once through Prompt Security (🛡️ Protected) and once raw (⚠️ Unprotected). Same user prompt, but the Protected column sends the redacted version — open *📨 What the model received* to see both |
| **Consistent answers** | Temperature 0, so the same prompt gives (nearly) the same answer each time |
| **User Identity** | The user email sent to Prompt Security with every check |
| **Provider / Model** | Choose the LLM backend and model. Custom providers appear under the name you gave them, followed by **➕ Add custom provider…** |
| **Prompt Debug / Response Debug** | Show the security verdict and raw API response for the prompt and/or the model's answer |
| **💡 Triggers** | One-click sample prompts grouped by attack category (editable in `triggers.txt`) |
| **➕ Upload** (top right) | Attach your own file, or pick a built-in sample (and optionally send it with a ready-made prompt) |
| **↑ / ↓ in the chat box** | Recall your previous prompts (last 10) |
| **🗑️ Clear Current Chat** | Resets the history and counters for the current provider |

Each provider keeps its own chat history, so you can switch providers without losing context.

**Providers and models**

| Provider | Models |
| :--- | :--- |
| Groq | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `groq/compound`, `groq/compound-mini` |
| Gemini | Chosen automatically (or from a list when `AUTO_SELECT_GEMINI_MODEL=false`) |
| Cohere | `command-a-03-2025`, `command-r-plus-08-2024`, `command-r-08-2024` |
| OpenRouter | `openrouter/free` (auto-picks a live free model) or any model slug you type |
| Custom providers | Any model your endpoint serves — pick it from the fetched list or type a name |

---

## Built-in sample files

The **➕ Upload** menu includes a *built-in sample* picker, so you can demo file handling without preparing a file. Pick one and either type your own message or press **⚡ Send sample with a ready-made prompt**. All data is fictional.

| File | What it demonstrates |
| :--- | :--- |
| `support_ticket_pii.txt` | Names, email, phone, SSN, credit card, IBAN and cloud credentials in a plain-text ticket |
| `payroll_export.xlsx` | A spreadsheet with emails, SSNs, IBANs and corporate card numbers |
| `incident_report_secrets.pdf` | A PDF with AWS keys, a database URL with a password, and customer details |
| `vendor_invoice_injection.txt` | An invoice carrying a hidden prompt-injection instruction (indirect injection through a file) |
| `meeting_notes_clean.txt` | A clean control file that should pass untouched |

Add your own by dropping `.txt`, `.pdf`, `.xlsx`, `.png` or `.jpg` files into the `samples/` folder; they appear in the picker automatically. An uploaded file always takes priority over a sample.

---

## Halloween mode 🎃

Click the **Spooky** title (top left of the page) to switch the Halloween theme on; click it again to switch it off. The setting lasts for the browser session. In Halloween mode the sidebar turns deep purple with pumpkin-orange accents, titles use a spooky font, and a few decorations appear: bats, a ghost, a zombie hand and a "BOO!" bubble that peek in from the screen edges now and then, a witch on a broom, and a spider that rappels down onto the Upload button. Nothing blocks clicks, and nothing changes in how prompts are protected.

Good to know: the spooky font (Creepster) is loaded from Google Fonts **only while the theme is on**; without internet access the app falls back to a generic cursive font. Everything else is drawn locally.

---

## Custom providers

Any service that exposes the OpenAI chat-completions API (`POST {Base URL}/chat/completions`) works: OpenAI, Azure OpenAI, Groq, Together, Mistral, DeepSeek, LiteLLM, vLLM, Ollama, LM Studio, and many more. Prompt Security protection applies exactly the same, because it runs before and after the LLM call regardless of which model sits behind it.

### Add a provider

1. In the *Provider* dropdown choose **➕ Add custom provider…**
2. Fill in the form and press **Create provider**:

   | Field | Example |
   | :--- | :--- |
   | Name | `Mistral` (1–30 characters; letters, numbers, spaces, `-` `_` `.`; must be unique) |
   | Base URL | `https://api.mistral.ai/v1` |
   | API key | your key (kept in the browser session only; never written to disk — unless you enable `PERSIST_PROVIDERS`) |

3. The new provider is selected automatically and appears in the list as `Mistral (custom)`.
4. The app **fetches the model list by itself** (`GET {Base URL}/models`) and fills a dropdown that starts on *— choose a model —*, so a paid model is never picked silently. Pick one and start chatting. **🔄 Fetch models** refreshes the list. Prefer typing? Choose **✏️ Type a model name…** (or just type it if the endpoint has no `/models`).

**⭐ Pinning.** Endpoints often list dozens of models, most of them paid. Press **⭐ Pin this model** for the ones you use: pinned models are listed first with a ⭐, and **Show only ⭐ pinned** hides the rest. Pins can also be typed names, so they work for endpoints that don't offer `/models`. Your last choice is remembered for each provider.

You can create as many providers as you want. Each one has its own chat history and remembers its URL, key and model while you switch between providers. To remove one, select it and press **🗑️ Delete this provider**; to rename one, delete it and create it again.

Tips:
- Paste whatever URL you have: a trailing `/`, `/chat/completions` or `/models` is removed automatically.
- Embedding, speech, moderation and similar non-chat models are hidden from the list; tick **Include non-chat models** to see them.
- If an endpoint doesn't offer `/models` (some, like Azure OpenAI, use deployment names), the app says so and you type the model name.
- If an endpoint rejects `system` messages, tick **Endpoint rejects 'system' messages** and the app will send its instructions inside the first user message instead.
- Image uploads are not supported on custom providers.
- Providers you create in the sidebar last for the browser session. To have them ready every time, define them in `.env` (next section) — or set `PERSIST_PROVIDERS=true` to save them automatically to `data/providers.json` (API keys in **plain text**: keep that folder private; it is already in `.gitignore` and `.dockerignore`).

### Pre-load providers from `.env`

```bash
CUSTOM_PROVIDERS='[{"name":"Mistral","base_url":"https://api.mistral.ai/v1","api_key_env":"MISTRAL_API_KEY","model":"mistral-small-latest"},{"name":"Together","base_url":"https://api.together.xyz/v1","api_key_env":"TOGETHER_API_KEY"}]'
MISTRAL_API_KEY=your_mistral_key
TOGETHER_API_KEY=your_together_key
```

Each entry takes `name` and `base_url` (required), plus optional `model` (the default model), `favorites` (a list of pinned model names, e.g. `["model-a","model-b"]`), `system_as_user` (`true`/`false`) and either `api_key_env` (the name of an environment variable holding the key — recommended, so keys stay out of the JSON) or a literal `api_key`. Entries with an invalid or already-used name are skipped; if the JSON itself is invalid, the sidebar shows a warning. Keep the whole value on one line, wrapped in single quotes.

The older `CUSTOM_BASE_URL` / `CUSTOM_API_KEY` / `CUSTOM_MODEL` variables still work and create one extra provider named `Custom`.

### Local models (Ollama, LM Studio)

Set `ALLOW_PRIVATE_ENDPOINTS=true` in `.env`, then use e.g. `http://host.docker.internal:11434/v1` as the Base URL (inside Docker, `localhost` is the container itself, not your machine). On Linux, add this to the `hybrid-chatbot` service in `docker-compose.yml` so the name resolves:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Security notes

- **The app server makes the request.** By default custom providers (including the model-list request) only accept `https://` URLs that resolve to public IP addresses, and it does not follow redirects. This prevents the app from being used to probe internal networks (SSRF). Enable `ALLOW_PRIVATE_ENDPOINTS` only on a machine you control, never on a shared deployment.
- **Endpoints see everything.** A custom endpoint receives your API key and every prompt — including the raw text on the *Unprotected* side of side-by-side mode. Use test data only, and only with services you trust. Be especially careful with unfamiliar "cheap/free API" resellers: you can't verify who operates them, what they log, or which model is really behind them.
- To remove the feature entirely, set `ALLOW_CUSTOM_ENDPOINTS=false`: the add form and every custom provider disappear.

---

## How Protection Works

The app calls the LLM provider directly. Before each call, the prompt (plus the text extracted from any attached file) is sent to the Prompt Security `/api/protect` endpoint, which returns one of three outcomes:

| Outcome | What the app does |
| :--- | :--- |
| **Blocked** | The prompt is never sent to the LLM; the user sees a message that depends on **what triggered the block** (see below) |
| **Redacted** | The redacted text (e.g. `[REDACTED_CREDIT_CARD_1]`) is sent to the LLM instead of the original, and a notice is shown |
| **Safe** | The prompt passes through unchanged |

### What the user sees when something is blocked

The app reads which detector fired from Prompt Security's response and picks the matching message:

| Triggered by | Message |
| :--- | :--- |
| Prompt Injection / Jailbreak | Blocked: prompt-injection / jailbreak attempt |
| Prompt Leak | Blocked: attempt to extract hidden instructions |
| Secrets | Blocked: credentials detected |
| Sensitive Data / RegEx | Confidential information detected (`CUSTOM_MESSAGES["blocked_prompt"]`) |
| Harmful content, Topic, Unicode, Code, URL, Token rate limit, Natural-language guardrails | One message each |
| Anything else | A neutral "blocked by security policy" message that names what was detected |

Each message ends with *Detected by: …* listing the names Prompt Security reported, and a blocked **answer** from the model gets its own message. To change the wording, edit `CUSTOM_MESSAGES` and `BLOCK_MESSAGES` in `app.py`; to teach the app a new detector name, add a keyword to `BLOCK_CATEGORY_RULES`.

The LLM's response goes through the same check before it is shown, so sensitive data the model echoes back is caught too. Each check is reported separately (a clean prompt can still produce a redacted response).

Some details worth knowing:

- **Redaction note for the model.** The app tells the LLM that bracketed tokens like `[REDACTED_EMAIL_ADDRESS_1]` are harmless placeholders, so smaller models don't refuse legitimate requests just because they see an unfamiliar token.
- **Retries and errors.** If a security check fails (network error, rate limit, malformed backend reply), the app retries up to twice with a short backoff. If it still fails, the turn is clearly flagged as *"Security Check Error — content NOT verified"*; it is never displayed as "Safe", and the content continues unverified. Keep this in mind if you adapt the app for anything beyond a demo.
- **Conversation history is protected too.** On follow-up questions the protected model only receives the *redacted* versions of earlier prompts. Blocked prompts, errors and empty answers are never replayed.
- **The two side-by-side columns never share turns.** The unprotected column only replays turns that really ran unprotected (earlier side-by-side turns, or turns made with Prompt Security switched off). Turns that went through protection are left out of it, because models copy patterns they see in a conversation and would start writing `[REDACTED_…]` tokens themselves.
- **Stats.** Blocks, redactions, last latency and last violation are shown under *Session Stats* in the sidebar.

---

## Project Structure

```
spooky-ai/
├── app.py                 # Main Streamlit application
├── triggers.txt           # Sample prompts shown in the sidebar
├── samples/               # Built-in sample files for the Upload menu
├── data/                  # (created on demand, git-ignored) saved providers when PERSIST_PROVIDERS=true
├── requirements.txt       # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── .env.example           # Environment variable template
├── .dockerignore
├── .gitignore
└── .streamlit/
    └── config.toml        # UI theme + toolbar settings (hides the Deploy button)
```

---

## Contributors

dawinci
