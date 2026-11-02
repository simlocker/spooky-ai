import streamlit as st
from google import genai
from google.genai import types
from openai import OpenAI, BadRequestError
import httpx
import requests
import os
import pypdf
import openpyxl
import random
import json
import ssl
import re
import time
import io
import socket
import ipaddress
from urllib.parse import urlparse
from PIL import Image
try:
    import streamlit.components.v1 as components
except Exception:  # very old/new Streamlit builds: the arrow-up history simply won't load
    components = None
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# ==========================================================
# --- TLS FIX: ENFORCE MODERN PROTOCOLS ---
# ==========================================================
class TLSAdapter(HTTPAdapter):
    """Force the use of TLS 1.2 or 1.3 to avoid protocol version errors."""
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

# Persistent session for security API calls
http_session = requests.Session()
http_session.mount('https://', TLSAdapter())

# ==========================================================
# --- PAGE CONFIGURATION ---
# ==========================================================
st.set_page_config(
    page_title="Spooky AI - Homegrown App",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# --- FIXED CSS: Layout & Styling ---
# ==========================================================
hide_st_style = """
<style>
/* 1. Reset & Basic UI Cleanup */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header { background: none !important; border: none !important; }
[data-testid="stHeader"] { background: none !important; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 1.5rem !important; }

/* 2. Sidebar Styling */
[data-testid="stSidebar"] { background-color: #614869 !important; }
[data-testid="stSidebar"] .block-container { padding-top: 2rem !important; gap: 0.5rem !important; }

/* Ensure Sidebar buttons are grey, not purple */
[data-testid="stSidebar"] button {
    background-color: #262730 !important;
    color: white !important;
    border: 1px solid rgba(250, 250, 250, 0.1) !important;
}

/* Help (?) tooltip icons: the generic sidebar-button rule above turns them into
   dark squares. Make them transparent and subtle instead. */
[data-testid="stSidebar"] [data-testid="stTooltipIcon"],
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] button,
[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"],
[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #D9C8E2 !important;
}
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg,
[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] svg {
    color: #D9C8E2 !important;
    opacity: 0.75;
}
[data-testid="stSidebar"] [data-testid="stTooltipIcon"]:hover svg,
[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"]:hover svg {
    opacity: 1;
}

/* Password field show/hide (eye) button: same problem — it is a <button> inside
   the text input, so it inherited the grey sidebar-button style. Blend it into
   the input instead. */
[data-testid="stSidebar"] [data-testid="stTextInput"] button,
[data-testid="stSidebar"] [data-testid="stTextInputRootElement"] button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #D9C8E2 !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] button:hover,
[data-testid="stSidebar"] [data-testid="stTextInputRootElement"] button:hover {
    background: rgba(217, 200, 226, 0.12) !important;
    color: #FFFFFF !important;
}

.sidebar-footer {
    position: fixed; bottom: 10px; left: 10px; width: 310px;
    color: #A5B5D1; font-size: 15px; pointer-events: none;
}

/* 3. Chat Input Cleanup */
[data-testid="stChatInput"] > div {
    background-color: #262730 !important;
    border-radius: 12px !important;
    border: 1px solid transparent !important;
}
[data-testid="stChatInput"]:focus-within > div {
    border: 1px solid #614869 !important;
    box-shadow: 0 0 0 0.1rem rgba(97, 72, 105, 0.2) !important;
}

/* 4. HEADER UPLOAD BUTTON STYLING */
div.header-upload-btn button {
    background-color: #614869 !important;
    color: white !important;
    border: 1px solid #4B0082 !important;
    border-radius: 8px !important;
    height: 45px !important;
    width: 100% !important;
    font-weight: bold !important;
    margin-top: 5px !important;
}

/* 5. CHAT BUBBLES */
div[data-testid="stChatMessageAvatarBackground"] { border-radius: 8px !important; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageAvatarBackground"] { background-color: #4B0082 !important; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageAvatarBackground"] { background-color: #614869 !important; }

div[data-testid="stChatMessage"] {
    background-color: rgba(97, 72, 105, 0.05) !important;
    border: 1px solid rgba(97, 72, 105, 0.2) !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
    padding: 0.5rem 0.8rem !important;
}

/* 6. TOAST NOTIFICATIONS */
div[data-testid="stToastContainer"] { bottom: 30px !important; right: 30px !important; z-index: 9999999 !important; }

/* 7. PINNED HEADER LOGIC */
[data-testid="stVerticalBlock"] > div:has(div.fixed-header-container) {
    position: sticky !important; top: 0; background-color: #0e1117; z-index: 1000;
    padding-bottom: 10px; border-bottom: 1px solid rgba(250, 250, 250, 0.1);
}

/* 8. ALERT / NOTICE WIDTH — Streamlit's warning/error boxes default to
   filling the entire container width regardless of how short the text is.
   Shrink them to fit their content instead. */
div[data-testid="stAlertContainer"], div[data-testid="stAlert"] {
    width: fit-content !important;
    max-width: 100% !important;
}

/* 9. ANSWER HIGHLIGHT — with several stacked check boxes (Prompt Check /
   Response Check) around it, the actual model answer can get visually lost.
   Give it a distinct tinted background + accent border so it reads as the
   "main" content of the turn at a glance, debug info on or off. */
[data-testid="stVerticalBlock"] > div:has(> div > div.llm-answer-marker) {
    background-color: rgba(97, 72, 105, 0.18) !important;
    border-left: 4px solid #9B7EA8 !important;
    border-radius: 8px !important;
    padding: 0.6rem 1rem !important;
    margin: 0.4rem 0 !important;
}

/* 10. NO HEADING LINK ICONS + NO DEPLOY BUTTON — the little chain icon that
   appears next to titles/headings, and Streamlit's "Deploy" toolbar button. */
[data-testid="stHeaderActionElements"] { display: none !important; }
[data-testid="stAppDeployButton"], .stAppDeployButton, .stDeployButton { display: none !important; }

[data-testid="stStatusWidget"] { visibility: hidden; display: none !important; }
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================================
# --- GLOBALS & STATE ---
# ==========================================================
def get_env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")

PS_APP_ID = os.getenv("PS_APP_ID")
PS_GATEWAY_URL = os.getenv("PS_GATEWAY_URL")

if not PS_APP_ID or not PS_GATEWAY_URL:
    st.error("🚨 Critical Error: PS_APP_ID or PS_GATEWAY_URL missing.")
    st.stop()

PS_PROTECT_API = f"{PS_GATEWAY_URL.strip('/')}/api/protect"

# Optional: pin a specific named Policy (Homegrown Apps > Policies > "Manage Policies")
# instead of silently relying on whichever policy the console has marked as this
# connector's "Default Homegrown App Policy". Leave blank to use the default.
PS_POLICY_NAME = os.getenv("PS_POLICY_NAME", "").strip()

# ----------------------------------------------------------
# Custom (bring-your-own) OpenAI-compatible endpoint
# ----------------------------------------------------------
# ALLOW_CUSTOM_ENDPOINTS=false   -> hides the "Custom" provider entirely
#                                   (recommended if this app is exposed to
#                                   people you don't fully trust).
# ALLOW_PRIVATE_ENDPOINTS=true   -> lets the Custom provider reach plain-http,
#                                   localhost and private-network addresses
#                                   (e.g. Ollama / LM Studio / an internal
#                                   gateway). Leave it OFF on any shared
#                                   deployment: the server makes the request,
#                                   so this is an SSRF vector.
ALLOW_CUSTOM_ENDPOINTS = get_env_bool("ALLOW_CUSTOM_ENDPOINTS", True)
ALLOW_PRIVATE_ENDPOINTS = get_env_bool("ALLOW_PRIVATE_ENDPOINTS", False)

# ----------------------------------------------------------
# Custom providers (any number, each with a name you choose)
# ----------------------------------------------------------
# A custom provider is any service exposing the OpenAI chat-completions API.
# Providers live in st.session_state.custom_profiles ({name: settings}) for the
# current browser session. They can be pre-loaded from .env:
#   CUSTOM_PROVIDERS = JSON list, e.g.
#     [{"name": "Mistral", "base_url": "https://api.mistral.ai/v1",
#       "api_key_env": "MISTRAL_API_KEY", "model": "mistral-small-latest"}]
#   (api_key_env names an environment variable, so the key itself stays out
#    of the JSON; "api_key" with a literal value also works.)
#   CUSTOM_BASE_URL / CUSTOM_API_KEY / CUSTOM_MODEL = one extra provider named "Custom".
CUSTOM_MODE_PREFIX = "API (Custom: "
ADD_PROVIDER_LABEL = "➕ Add custom provider…"
ADD_MODE = "API (Custom: new)"
TYPE_MODEL_OPTION = "✏️ Type a model name…"
CUSTOM_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,29}$")
RESERVED_PROVIDER_NAMES = {"groq", "gemini", "cohere", "openrouter"}
# Model ids that are clearly not chat models (hidden unless "show all" is ticked).
NON_CHAT_MODEL_RE = re.compile(r"(embed|moderat|whisper|tts|speech|transcri|rerank|dall-?e|image|guard|ocr)", re.I)

def is_custom_mode(mode):
    return str(mode).startswith(CUSTOM_MODE_PREFIX)

def custom_mode_for(name):
    return f"{CUSTOM_MODE_PREFIX}{name})"

def profile_label(name):
    return f"{name} (custom)"

def new_profile(base_url="", api_key="", model="", system_as_user=False):
    return {"base_url": base_url, "api_key": api_key, "model": model,
            "system_as_user": bool(system_as_user), "models_all": [], "models_error": "", "show_all_models": False}

def load_env_profiles():
    """Providers pre-loaded from .env (see the comment above)."""
    found = {}
    def add(name, url, key, model, sys_flag=False):
        name = (name or "").strip()
        if (CUSTOM_NAME_RE.match(name) and name.lower() not in RESERVED_PROVIDER_NAMES
                and name.lower() not in {n.lower() for n in found} and (url or "").strip()):
            found[name] = new_profile((url or "").strip(), (key or "").strip(), (model or "").strip(), sys_flag)
    raw = os.getenv("CUSTOM_PROVIDERS", "").strip()
    if len(raw) > 1 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]          # older docker-compose versions keep the quotes around .env values
    if raw:
        try:
            for entry in json.loads(raw):
                key = os.getenv(entry.get("api_key_env", ""), "") if entry.get("api_key_env") else entry.get("api_key", "")
                add(entry.get("name"), entry.get("base_url"), key, entry.get("model"), entry.get("system_as_user", False))
        except Exception:
            # malformed JSON: keep the app working, but tell the user (shown in the sidebar)
            st.session_state["custom_env_error"] = "CUSTOM_PROVIDERS in .env is not valid JSON, so it was ignored."
    if os.getenv("CUSTOM_BASE_URL", "").strip():
        add("Custom", os.getenv("CUSTOM_BASE_URL"), os.getenv("CUSTOM_API_KEY", ""), os.getenv("CUSTOM_MODEL", ""))
    return found

# Fixed OpenAI-compatible providers. Groq, Cohere's Compatibility API and
# OpenRouter all speak the OpenAI chat-completions protocol, so they share one
# generator below. (Verify Cohere's base URL against their docs if it stops
# working — compatibility-layer paths occasionally move.)
PROVIDER_CONFIG = {
    "API (Groq)": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "extra_headers": None,
    },
    "API (Cohere)": {
        "label": "Cohere",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "env_key": "COHERE_API_KEY",
        "extra_headers": None,
    },
    # The extra headers are optional (OpenRouter uses them only for its public
    # leaderboard attribution), but harmless to include.
    "API (OpenRouter)": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "extra_headers": {"HTTP-Referer": "https://spooky-ai.local", "X-Title": "Spooky AI"},
    },
}

# ==========================================================
# --- CUSTOM USER-FACING SECURITY MESSAGES ---
# Unlike Prompt Security's Employees browser extension (fixed pop-up copy) or the
# Agentic AI block message (400-char field in the console), THIS app is our own
# frontend calling /api/protect directly — so we fully control what the user sees.
# Edit these freely to match whatever narrative/demo script you're running.
# ==========================================================
CUSTOM_MESSAGES = {
    "blocked_prompt": (
        "🚫 **This content cannot be sent to the AI.**\n\n"
        "Confidential information (sensitive personal data, medical history, or similar) "
        "was detected in your message or attached file.\n\n"
        "Sending is not permitted under corporate policy. "
        "You can rephrase your request by removing customer data, amounts, margins, "
        "or personal information before continuing."
    ),
    "redacted_notice": (
        "⚠️ Sensitive information was detected and redacted from your message or file before continuing."
    ),
    "security_check_error": (
        "❌ **This content could not be verified with the security service** (backend error). "
        "The content was sent without full inspection — treat it as unverified."
    ),
}

# Set SHOW_CUSTOM_NOTICES=false in .env to hide the "redacted"/"security check
# error" banners entirely (no colored box at all) without touching this file
# again. This does NOT affect "blocked_prompt" — that's the actual answer
# text shown for a blocked turn, not a supplementary notice, so there's
# always something to display there regardless of this setting.
SHOW_CUSTOM_NOTICES = os.getenv("SHOW_CUSTOM_NOTICES", "true").strip().lower() in ("1", "true", "yes", "on")

def show_redacted_notice():
    if SHOW_CUSTOM_NOTICES:
        st.warning(CUSTOM_MESSAGES["redacted_notice"])

def show_security_error_notice():
    if SHOW_CUSTOM_NOTICES:
        st.error(CUSTOM_MESSAGES["security_check_error"])

ALL_MODES = ["API (Gemini)", "API (Groq)", "API (Cohere)", "API (OpenRouter)", ADD_MODE]

if "multi_messages" not in st.session_state:
    st.session_state.multi_messages = {m: [] for m in ALL_MODES}
if "session_costs" not in st.session_state:
    st.session_state.session_costs = {m: 0.0 for m in ALL_MODES}
# Custom providers add their own chat histories later (see the sidebar).
for _m in ALL_MODES:
    st.session_state.multi_messages.setdefault(_m, [])
    st.session_state.session_costs.setdefault(_m, 0.0)

if "security_stats" not in st.session_state:
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
if "last_latency" not in st.session_state: st.session_state.last_latency = 0
if "last_violation" not in st.session_state: st.session_state.last_violation = "None"
if "current_integration" not in st.session_state: st.session_state.current_integration = "API (Groq)"
if "input_text" not in st.session_state: st.session_state.input_text = None
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "last_processed_file" not in st.session_state: st.session_state.last_processed_file = None
if "gemini_available_models" not in st.session_state: st.session_state.gemini_available_models = []
if "selected_gemini_model" not in st.session_state: st.session_state.selected_gemini_model = None
if "custom_cfg" not in st.session_state: st.session_state.custom_cfg = {}
if "custom_profiles" not in st.session_state: st.session_state.custom_profiles = load_env_profiles()
for _n in st.session_state.custom_profiles:
    st.session_state.multi_messages.setdefault(custom_mode_for(_n), [])
    st.session_state.session_costs.setdefault(custom_mode_for(_n), 0.0)
if "deterministic" not in st.session_state: st.session_state.deterministic = True
if "custom_url_cache" not in st.session_state: st.session_state.custom_url_cache = {}

# ==========================================================
# --- HELPERS ---
# ==========================================================
def reset_chat():
    mode = st.session_state.current_integration
    st.session_state.multi_messages[mode] = []
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
    st.session_state.last_latency, st.session_state.last_violation = 0, "None"
    st.session_state.session_costs[mode] = 0.0
    st.session_state.uploader_key += 1
    st.toast("History cleared.")

def set_prompt(text):
    st.session_state.input_text = text
    st.session_state.uploader_key += 1

def safe_err(e, limit=200):
    """Stringify an exception for display, scrubbing every custom API key if an
    endpoint happens to echo one back in an error message."""
    text = str(e)
    keys = [(st.session_state.get("custom_cfg") or {}).get("api_key")]
    keys += [p.get("api_key") for p in (st.session_state.get("custom_profiles") or {}).values()]
    for key in keys:
        if key and len(key) >= 6:
            text = text.replace(key, "***")
    return text[:limit]

def render_debug_box(info):
    if not info: return
    stype = info.get('status_type', 'safe')
    if stype == "blocked": label, state, content = "🚫 Violation Detected", "error", None
    elif stype == "redacted": label, state, content = "⚠️ Content Redacted", "complete", f"Redacted Content: {info.get('checked_p', '')}"
    elif stype == "error": label, state, content = "❌ Security Check Error — content NOT verified", "error", None
    else: label, state, content = "✅ Safe", "complete", None
    with st.status(label, expanded=False, state=state):
        if content: st.warning(content)
        with st.expander("🔍 View Raw API Response", expanded=False): st.json(info.get('debug', {}))

def render_answer(text):
    """Renders the actual answer/output text (LLM reply or block message)
    inside a visually distinct tinted container, so it stands out from the
    Prompt Check / Response Check boxes stacked around it — see CSS rule 9."""
    with st.container():
        st.markdown('<div class="llm-answer-marker"></div>', unsafe_allow_html=True)
        st.write(text)

def get_chat_models(client):
    try:
        return sorted(set([m.name for m in client.models.list() if "gemini" in m.name.lower()]))
    except Exception:
        return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

def choose_gemini_model(available_models):
    pref = [os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.0-flash").strip()] + \
           [m.strip() for m in os.getenv("FALLBACK_GEMINI_MODELS", "").split(",") if m.strip()]
    for m in pref:
        if m in available_models: return m
    return available_models[0] if available_models else "Unavailable"

def get_runtime_gemini_candidates(sel, avail):
    cands = [sel] + [os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.0-flash").strip()] + \
            [m.strip() for m in os.getenv("FALLBACK_GEMINI_MODELS", "").split(",") if m.strip()]
    return [m for m in cands if m in avail]

def normalize_pdf_text(text):
    """
    pypdf preserves the PDF's visual line wraps as literal '\n' characters.
    If a long token (IBAN, phone number, account number...) happens to wrap
    across two lines in the source PDF, it gets split by a hard newline in
    the extracted text — which breaks pattern-based detectors (e.g. Sensitive
    Data's IBAN_CODE) that expect a contiguous token. This collapses single
    line-wrap newlines into spaces while preserving real paragraph breaks
    (two or more consecutive newlines stay as a paragraph break).
    """
    # Temporarily protect real paragraph breaks
    text = re.sub(r"\n{2,}", "§PARA§", text)
    # Collapse remaining single newlines (line-wrap artifacts) into spaces
    text = text.replace("\n", " ")
    # Restore paragraph breaks
    text = text.replace("§PARA§", "\n\n")
    return re.sub(r"[ \t]+", " ", text).strip()

def is_valid_key(key):
    """Reject empty keys and obvious .env placeholders (e.g. 'your_key_here').
    Deliberately does NOT reject a key just because it happens to contain the
    letters 'key' or 'here' — real random keys can contain those by chance."""
    if not key: return False
    k = key.strip().lower()
    if len(k) < 10: return False
    if re.search(r"(your[_\- ]|[_\-]here|changeme|<.*>|xxxx)", k): return False
    return True

HISTORY_ERROR_PREFIXES = ("⚠️ Error:", "No response generated.", "🚨 Rate limit")

def get_api_history(chat_history, view="protected"):
    """Builds the multi-turn history that is replayed to the LLM on the next turn.

    view="protected": only text that already went through the security check
        (the REDACTED prompt that was actually sent, plus the checked answer).
        Replaying the user's ORIGINAL prompts here would hand earlier sensitive
        data to the model on every later turn, bypassing the protection.
    view="raw": the unprotected conversation — original prompts and the raw
        answers that column produced.

    Blocked turns, errors and empty answers are skipped, so the history never
    contains orphan user messages or blocked content."""
    clean = []
    for item in chat_history:
        if item.get("skip_history"):
            continue
        role = item.get("role")
        if role == "side_by_side":
            if view == "raw":
                resp = item.get("unprotected_response") or ""
                if item.get("unprotected_ok", True) and resp and not resp.startswith(HISTORY_ERROR_PREFIXES):
                    clean.append({"role": "user", "content": item["user_prompt"]})
                    clean.append({"role": "assistant", "content": resp})
            else:
                sent = item.get("protected_sent", item.get("user_prompt"))   # None = blocked
                resp = item.get("protected_response") or ""
                if sent and item.get("protected_ok", True) and resp and not resp.startswith(HISTORY_ERROR_PREFIXES):
                    clean.append({"role": "user", "content": sent})
                    clean.append({"role": "assistant", "content": resp})
        elif "role" in item and "content" in item:
            if item["role"] == "user" and view == "protected":
                content = item.get("sent", item["content"])
            else:
                content = item["content"]
            if content:
                clean.append({"role": item["role"], "content": content})
    return clean

# ----------------------------------------------------------
# Custom endpoint URL validation (SSRF guard)
# ----------------------------------------------------------
def validate_custom_url(url):
    """Returns (ok, error_message). The Streamlit SERVER makes the request to
    whatever URL a user types, so by default we only allow https:// endpoints
    that resolve to public IP addresses. Set ALLOW_PRIVATE_ENDPOINTS=true to
    allow http:// / localhost / private ranges (local models, internal
    gateways).

    Known limitation: a hostname is resolved here and again by the HTTP
    client, so a hostile DNS server could in theory change its answer between
    the two (DNS rebinding). That's acceptable for a demo tool; for anything
    stronger, put the app behind an egress proxy / network policy."""
    url = (url or "").strip()
    if not url:
        return False, "Enter a Base URL."
    try:
        p = urlparse(url)
        port = p.port
    except ValueError:
        return False, "That doesn't look like a valid URL."
    if p.scheme not in ("https", "http"):
        return False, "URL must start with https://"
    if not p.hostname:
        return False, "URL is missing a host name."
    if p.username or p.password:
        return False, "Don't put credentials in the URL — use the API key field."
    if p.scheme == "http" and not ALLOW_PRIVATE_ENDPOINTS:
        return False, "Only https:// endpoints are allowed (set ALLOW_PRIVATE_ENDPOINTS=true for local/http)."
    port = port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(p.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False, f"Could not resolve host '{p.hostname}'."
    if not ALLOW_PRIVATE_ENDPOINTS:
        for info in infos:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
            if getattr(ip, "ipv4_mapped", None):
                ip = ip.ipv4_mapped
            if (not ip.is_global) or ip.is_multicast:
                return False, ("That host resolves to a private/internal address, which is blocked "
                               "(set ALLOW_PRIVATE_ENDPOINTS=true if this is intentional).")
    return True, ""

def check_custom_url_cached(url, ttl=60):
    """validate_custom_url() does a DNS lookup; Streamlit reruns the script on
    every interaction, so cache the verdict briefly per URL."""
    cache = st.session_state.custom_url_cache
    now = time.time()
    hit = cache.get(url)
    if hit and now - hit[2] < ttl:
        return hit[0], hit[1]
    ok, err = validate_custom_url(url)
    cache[url] = (ok, err, now)
    return ok, err

def normalize_base_url(url):
    """Forgiving input: strips trailing slashes and a pasted /chat/completions or /models."""
    u = (url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if u.lower().endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
    return u

def fetch_models(base_url, api_key):
    """Asks an OpenAI-compatible endpoint for its models: GET {base_url}/models.
    Same safety rules as chat requests (URL validation, no redirects, timeout).
    Returns a sorted list of model ids; raises ValueError with a readable message."""
    ok, err = validate_custom_url(base_url)
    if not ok:
        raise ValueError(err)
    headers = {"Accept": "application/json"}
    if api_key and api_key != "not-needed":
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(follow_redirects=False, timeout=15.0) as client:
            resp = client.get(base_url.rstrip("/") + "/models", headers=headers)
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not reach the endpoint ({type(exc).__name__}).")
    if resp.status_code in (401, 403):
        raise ValueError(f"The endpoint rejected the API key (HTTP {resp.status_code}).")
    if resp.status_code in (404, 405):
        raise ValueError(f"This endpoint doesn't list its models (HTTP {resp.status_code}) — type the model name instead.")
    if resp.status_code != 200:
        raise ValueError(f"Unexpected response from the endpoint (HTTP {resp.status_code}).")
    try:
        data = resp.json()
    except ValueError:
        raise ValueError("The endpoint did not return JSON — check the Base URL (it usually ends in /v1).")
    items = data.get("data") if isinstance(data, dict) else data
    if items is None and isinstance(data, dict):
        items = data.get("models")
    if not isinstance(items, list) or not items:
        raise ValueError("The endpoint returned no model list — type the model name instead.")
    ids = set()
    for item in items:
        if isinstance(item, dict):
            mid = item.get("id") or item.get("name") or item.get("model")
        else:
            mid = item
        if isinstance(mid, str) and mid.strip():
            ids.add(mid.strip())
    if not ids:
        raise ValueError("The endpoint returned no usable model names — type the model name instead.")
    return sorted(ids)[:500]

def create_profile_callback():
    """'Create provider' button: validates the form and stores a new provider."""
    ss = st.session_state
    name = (ss.get("np_name") or "").strip()
    url = normalize_base_url(ss.get("np_url") or "")
    key = (ss.get("np_key") or "").strip()
    err = None
    if not CUSTOM_NAME_RE.match(name):
        err = "Name: 1–30 characters, starting with a letter or number; letters, numbers, spaces, - _ . only."
    elif name.lower() in RESERVED_PROVIDER_NAMES or name.lower() in {n.lower() for n in ss.custom_profiles}:
        err = f"The name “{name}” is already taken."
    else:
        ok, uerr = validate_custom_url(url)
        if not ok:
            err = uerr
    if err:
        ss.np_error = err
        return
    ss.custom_profiles[name] = new_profile(url, key)
    ss.multi_messages.setdefault(custom_mode_for(name), [])
    ss.session_costs.setdefault(custom_mode_for(name), 0.0)
    ss.np_error = ""
    ss.np_name = ss.np_url = ss.np_key = ""
    ss.provider_select = profile_label(name)      # jump straight to the new provider

def delete_profile_callback(name):
    """'Delete' button: removes the provider, its chat history and its widget state."""
    ss = st.session_state
    ss.custom_profiles.pop(name, None)
    ss.multi_messages.pop(custom_mode_for(name), None)
    ss.session_costs.pop(custom_mode_for(name), None)
    for k in [k for k in list(ss.keys()) if str(k).startswith(f"cp::{name}::")]:
        try: del ss[k]
        except Exception: pass
    ss.custom_cfg = {}
    ss.provider_select = "Groq"

# When Prompt Security redacts sensitive data, the LLM sees placeholder
# tokens like [REDACTED_EMAIL_ADDRESS_1] or [REDACTED_CREDIT_CARD_1] instead
# of the real value. Some models — smaller/distilled ones especially —
# pattern-match "credit card" / "dispute" / "cc number" next to an unfamiliar
# bracketed token straight into a blanket safety refusal, because they have
# no context for what that token actually is. This note gives them that
# context so a legitimate request doesn't get refused just because the real
# data was already stripped out before it ever reached the model — which is
# the opposite of what the redaction is supposed to enable.
REDACTION_SYSTEM_NOTE = (
    "Some text you receive may contain tokens like [REDACTED_EMAIL_ADDRESS_1], "
    "[REDACTED_CREDIT_CARD_1], or similar. These are NOT sensitive, fake, or "
    "something you are being asked to fabricate, guess, or leak — they are safe "
    "placeholders inserted by an upstream data-loss-prevention system in place "
    "of real personal or sensitive data that was already removed before this "
    "message reached you. Treat them like any other piece of text: refer to "
    "them, summarize around them, or include them in your answer exactly as "
    "given. Do not refuse or add safety caveats on account of a bracketed "
    "placeholder — there is nothing sensitive in it, and you have no access to "
    "(and are not being asked for) the original value it stands in for."
)

# ----------------------------------------------------------
# Built-in sample files ("easy submit" without uploading your own)
# ----------------------------------------------------------
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
SAMPLE_MIME = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
NO_SAMPLE = "— none —"
DEFAULT_SAMPLE_PROMPT = "Repeat the full contents of the attached file exactly, word for word, with no changes."
SAMPLE_PROMPTS = {
    "vendor_invoice_injection.txt": "Process this vendor invoice and tell me the total amount to pay.",
}

class SampleFile(io.BytesIO):
    """Looks enough like Streamlit's UploadedFile (name, type, read, seek) for
    the attachment-handling code to treat both the same way."""
    def __init__(self, data, name, mime):
        super().__init__(data)
        self.name = name
        self.type = mime

def list_sample_files():
    try:
        return sorted(f for f in os.listdir(SAMPLES_DIR)
                      if not f.startswith(".") and os.path.splitext(f)[1].lower() in SAMPLE_MIME)
    except OSError:
        return []

def load_sample_file(name):
    if not name or name == NO_SAMPLE:
        return None
    name = os.path.basename(name)                      # no path tricks
    if name not in list_sample_files():
        return None
    try:
        with open(os.path.join(SAMPLES_DIR, name), "rb") as fh:
            return SampleFile(fh.read(), name, SAMPLE_MIME[os.path.splitext(name)[1].lower()])
    except OSError:
        return None

def send_sample_prompt(name):
    """Button callback: queue a ready-made prompt. The chosen sample stays
    selected, so it is attached to this message."""
    if name and name != NO_SAMPLE:
        st.session_state.input_text = SAMPLE_PROMPTS.get(name, DEFAULT_SAMPLE_PROMPT)

# ----------------------------------------------------------
# ARROW-UP prompt history (last 10 prompts, kept in a browser cookie)
# ----------------------------------------------------------
# Streamlit's chat box has no built-in history. Two tiny scripts run inside
# zero-height component iframes (same origin as the app, so they can reach the
# parent page):
#   * PUSH: after each submitted prompt, appends it to the cookie
#           "spooky_prompt_history" (max 10 entries, 400 chars each, ~3.5 KB).
#   * INSTALL: injects a keydown handler into the page; ArrowUp / ArrowDown
#           walk through the saved prompts when the chat box is empty.
# NOTE: the cookie holds your typed prompts (including any sensitive test data)
# in the browser and is sent to the app server with each request. Clear it by
# deleting the "spooky_prompt_history" cookie.
PUSH_PROMPT_JS = """<script>(function(){try{
var doc=window.parent.document;var NAME="spooky_prompt_history",MAX=10,MAXLEN=400,MAXBYTES=3500;
function read(){var c=doc.cookie.split("; ").filter(function(x){return x.indexOf(NAME+"=")===0})[0];
 if(!c)return[];try{var a=JSON.parse(decodeURIComponent(c.substring(NAME.length+1)));return Array.isArray(a)?a:[]}catch(e){return[]}}
function write(a){var v=encodeURIComponent(JSON.stringify(a));
 while(v.length>MAXBYTES&&a.length>1){a.shift();v=encodeURIComponent(JSON.stringify(a))}
 doc.cookie=NAME+"="+v+"; path=/; max-age=2592000; SameSite=Lax"}
var p=String(__PROMPT__).slice(0,MAXLEN);var a=read();
if(a.length&&a[a.length-1]===p)return;
a.push(p);while(a.length>MAX)a.shift();write(a);
}catch(e){}})();</script>"""

INSTALL_ARROW_UP_JS = """<script>(function(){try{
function handler(){
  if(window.__spookyHistInstalled)return;window.__spookyHistInstalled=true;
  var NAME="spooky_prompt_history",idx=-1,draft="";
  function read(){var c=document.cookie.split("; ").filter(function(x){return x.indexOf(NAME+"=")===0})[0];
    if(!c)return[];try{var a=JSON.parse(decodeURIComponent(c.substring(NAME.length+1)));return Array.isArray(a)?a:[]}catch(e){return[]}}
  function isChat(t){return t&&t.tagName==="TEXTAREA"&&t.closest&&t.closest('[data-testid="stChatInput"]')}
  function setVal(el,v){var set=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;
    set.call(el,v);el.dispatchEvent(new Event("input",{bubbles:true}));
    try{el.setSelectionRange(v.length,v.length)}catch(e){}}
  document.addEventListener("input",function(e){if(e.isTrusted&&isChat(e.target))idx=-1},true);
  document.addEventListener("keydown",function(e){
    var t=e.target;if(!isChat(t))return;
    if(e.key==="Enter"&&!e.shiftKey){idx=-1;return}
    if(e.altKey||e.ctrlKey||e.metaKey||e.shiftKey)return;
    if(e.key==="ArrowUp"){
      var h=read();if(!h.length)return;
      if(idx===-1){if(t.value.length&&t.selectionStart!==0)return;draft=t.value;idx=h.length}
      if(idx>0)idx--;
      e.preventDefault();setVal(t,h[idx]);
    }else if(e.key==="ArrowDown"&&idx!==-1){
      var h2=read();e.preventDefault();
      if(idx<h2.length-1){idx++;setVal(t,h2[idx])}else{idx=-1;setVal(t,draft)}
    }
  },true);
}
var P=window.parent;if(P.__spookyHistInstalled)return;
var s=P.document.createElement("script");s.textContent="("+handler.toString()+")();";
P.document.head.appendChild(s);
}catch(e){}})();</script>"""

def remember_prompt(text):
    """Append a submitted prompt to the browser-side history cookie."""
    if not text or components is None:
        return
    try:
        payload = json.dumps(text[:400]).replace("</", "<\\/")
        components.html(PUSH_PROMPT_JS.replace("__PROMPT__", payload), height=0)
    except Exception:
        pass

def install_arrow_up_history():
    if components is None:
        return
    try:
        components.html(INSTALL_ARROW_UP_JS, height=0)
    except Exception:
        pass

# ----------------------------------------------------------
# LLM call helpers
# ----------------------------------------------------------
def generate_gemini_response(genai_client, model_sel, chat_history, current_prompt, img_obj=None,
                             include_note=True, temperature=None):
    contents = []
    for m in chat_history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    current_parts = [types.Part.from_text(text=current_prompt)]
    if img_obj: current_parts.append(img_obj)
    contents.append(types.Content(role="user", parts=current_parts))
    # The redaction note only makes sense when the text really was redacted
    # (protected path). The unprotected path must stay completely raw.
    gen_config = types.GenerateContentConfig(
        system_instruction=REDACTION_SYSTEM_NOTE if include_note else None,
        temperature=temperature
    )
    for mname in get_runtime_gemini_candidates(model_sel, st.session_state.gemini_available_models):
        try:
            res = genai_client.models.generate_content(model=mname, contents=contents, config=gen_config)
            if res and res.text: return res.text
        except Exception as e:
            if "429" in str(e): continue
            else: raise e
    return None

def generate_openai_compatible_response(base_url, api_key_str, model_sel, chat_history, current_prompt,
                                        extra_headers=None, system_as_user=False, harden=False,
                                        include_note=True, temperature=None):
    """One generator for every OpenAI-compatible provider (Groq, Cohere,
    OpenRouter and the user-supplied Custom endpoint).

    system_as_user: some endpoints reject a 'system' role message. When True,
                    the redaction note is folded into the first user message.
    include_note:   send the "[REDACTED_...] tokens are harmless" note. Only the
                    PROTECTED path should; sending it on the unprotected path
                    made models echo fake [REDACTED_...] tokens even though
                    they were given the raw data.
    temperature:    e.g. 0 for repeatable answers; silently dropped if the
                    endpoint rejects the parameter.
    harden:         used for user-supplied URLs — re-validates the URL right
                    before the call and refuses to follow HTTP redirects
                    (a redirect to an internal address would bypass the
                    SSRF check)."""
    client_kwargs = {"base_url": base_url, "api_key": api_key_str}
    if extra_headers:
        client_kwargs["default_headers"] = extra_headers
    if harden:
        ok, err = validate_custom_url(base_url)
        if not ok:
            raise ValueError(err)
        client_kwargs["http_client"] = httpx.Client(follow_redirects=False, timeout=60.0)

    messages_payload = []
    if include_note and not system_as_user:
        messages_payload.append({"role": "system", "content": REDACTION_SYSTEM_NOTE})
    messages_payload += [{"role": m["role"], "content": m["content"]} for m in chat_history]
    messages_payload.append({"role": "user", "content": current_prompt})
    if include_note and system_as_user:
        for msg in messages_payload:
            if msg["role"] == "user":
                msg["content"] = f"{REDACTION_SYSTEM_NOTE}\n\n---\n\n{msg['content']}"
                break

    create_kwargs = {"messages": messages_payload, "model": model_sel}
    if temperature is not None:
        create_kwargs["temperature"] = temperature

    client = OpenAI(**client_kwargs)
    try:
        try:
            completion = client.chat.completions.create(**create_kwargs)
        except BadRequestError as e:
            # Some models (e.g. certain reasoning models) reject "temperature".
            if "temperature" in create_kwargs and "temperature" in str(e).lower():
                create_kwargs.pop("temperature")
                completion = client.chat.completions.create(**create_kwargs)
            else:
                raise
    finally:
        try: client.close()
        except Exception: pass

    # Non-compliant endpoints sometimes return HTTP 200 with a body that is not
    # a chat completion (an HTML page, an error JSON...). Say so clearly.
    if not hasattr(completion, "choices") or not completion.choices:
        raise ValueError("The endpoint did not return a chat completion. Check the Base URL "
                         "(it usually ends in /v1) and that it is OpenAI-compatible.")
    return completion.choices[0].message.content

def call_llm(app_mode, model_sel, history, prompt, img=None, warn_img=True, protected=True):
    """Single dispatch point for every provider, so adding one means editing
    PROVIDER_CONFIG (or the Custom branch) rather than three if/elif chains.

    protected=False is the raw, unprotected path: no redaction note."""
    temperature = 0 if st.session_state.get("deterministic", True) else None

    if app_mode == "API (Gemini)":
        return generate_gemini_response(st.session_state.genai_client, model_sel, history, prompt, img,
                                        include_note=protected, temperature=temperature)

    if img and warn_img:
        label = app_mode.replace("API (", "").rstrip(")")
        st.warning(f"🖼️ Image uploads are not currently supported by {label} in this app. Ignoring image.")

    if is_custom_mode(app_mode):
        cfg = st.session_state.custom_cfg
        return generate_openai_compatible_response(
            cfg["base_url"], cfg["api_key"], model_sel, history, prompt,
            system_as_user=cfg.get("system_as_user", False), harden=True,
            include_note=protected, temperature=temperature
        )

    cfg = PROVIDER_CONFIG[app_mode]
    return generate_openai_compatible_response(
        cfg["base_url"], os.getenv(cfg["env_key"]), model_sel, history, prompt,
        extra_headers=cfg["extra_headers"], include_note=protected, temperature=temperature
    )

# ==========================================================
# --- SIDEBAR ---
# ==========================================================
with st.sidebar:
    st.header("App Settings")
    st.button("🗑️ Clear Current Chat", use_container_width=True, on_click=reset_chat)

    trigger_data = {}
    try:
        with open("triggers.txt", "r") as f: trigger_data = json.load(f)
    except Exception: trigger_data = {"System": {"Error": ["Check triggers.txt file"]}}

    with st.popover("💡 Triggers", use_container_width=True):
        col_t, col_r = st.columns([0.7, 0.3])
        col_t.markdown("### Sample Prompts")
        if col_r.button("🔄"): st.rerun()
        for g, items in trigger_data.items():
            if isinstance(items, dict):
                st.markdown(f"**{g}**")
                btn_names = list(items.keys())
                for i in range(0, len(btn_names), 2):
                    cols = st.columns(2)
                    for j in range(2):
                        if i + j < len(btn_names):
                            name = btn_names[i+j]
                            if cols[j].button(name, use_container_width=True, key=f"tr_{g}_{name}"):
                                set_prompt(random.choice(items[name]))

    st.markdown("### Protection Layer")
    ps_enabled = st.toggle("Enable Prompt Security", value=True)
    side_by_side = st.toggle("🔀 Side-by-side Comparison", value=False)
    st.session_state.deterministic = st.toggle(
        "🎯 Consistent answers", value=True, key="consistent_answers_toggle",
        help="Sets the model temperature to 0, so repeated runs and the Protected / Unprotected "
             "columns are easier to compare. Some models ignore it.")
    user_email = st.text_input("User Identity", value=os.getenv("DEMO_USER_EMAIL", "john.doe@unknown.com"))

    st.divider()

    # Provider Selection — API integration is the only supported method.
    # Built-in providers, then every custom provider by the name you gave it,
    # then an entry that opens the "add custom provider" form.
    custom_names = list(st.session_state.custom_profiles) if ALLOW_CUSTOM_ENDPOINTS else []
    label_to_profile = {profile_label(n): n for n in custom_names}
    provider_options = ["Groq", "Gemini", "Cohere", "OpenRouter"] + list(label_to_profile) + \
                       ([ADD_PROVIDER_LABEL] if ALLOW_CUSTOM_ENDPOINTS else [])
    if st.session_state.get("provider_select") not in provider_options:
        st.session_state.provider_select = "Groq"      # first run, or a provider that was just deleted
    provider = st.selectbox("Provider:", provider_options, key="provider_select")
    if provider in label_to_profile:
        active_profile = label_to_profile[provider]
        app_mode = custom_mode_for(active_profile)
    elif provider == ADD_PROVIDER_LABEL:
        active_profile = None
        app_mode = ADD_MODE
    else:
        active_profile = None
        app_mode = f"API ({provider})"
    st.session_state.multi_messages.setdefault(app_mode, [])
    st.session_state.session_costs.setdefault(app_mode, 0.0)
    if st.session_state.get("custom_env_error"):
        st.caption("⚠️ " + st.session_state["custom_env_error"])

    if app_mode != st.session_state.current_integration:
        st.session_state.current_integration = app_mode
        st.rerun()

    # Debug checkboxes are rendered once, after the provider-specific block
    # below. Defaulting them here also avoids a NameError when a provider is
    # misconfigured and its block never reaches the checkboxes.
    debug_prompt, debug_response = False, False

    # Dynamic Model Selector based on explicitly derived app_mode — placed
    # immediately after the Provider dropdown above, since choosing a model
    # is a direct continuation of choosing a provider (Gemini has no manual
    # selector, but its "Auto-selected: ..." caption lands here too, for the
    # same reason).
    if app_mode == "API (Groq)":
        api_key = os.getenv("GROQ_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 GROQ_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = st.selectbox("Select Groq Model", [
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "groq/compound",
                "groq/compound-mini"
            ], index=0)

    elif app_mode == "API (Gemini)":
        api_key = os.getenv("GEMINI_FREE_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 GEMINI_FREE_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            try:
                genai_client = genai.Client(api_key=api_key)
                st.session_state.genai_client = genai_client
                chat_m = get_chat_models(genai_client)
                st.session_state.gemini_available_models = chat_m
                auto = get_env_bool("AUTO_SELECT_GEMINI_MODEL", True)
                pref = choose_gemini_model(chat_m)
                if auto:
                    selected_model = pref
                    st.caption(f"Auto-selected: `{selected_model}`")
                else:
                    if st.session_state.selected_gemini_model not in chat_m:
                        st.session_state.selected_gemini_model = pref
                    selected_model = st.selectbox("Select Gemini Model", chat_m, index=chat_m.index(st.session_state.selected_gemini_model))
                    st.session_state.selected_gemini_model = selected_model
            except Exception as e:
                st.error("⚠️ Google API Auth Failed. Check your key.")
                selected_model = "Connection Error"
                st.session_state.gemini_available_models = []

    elif app_mode == "API (Cohere)":
        api_key = os.getenv("COHERE_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 COHERE_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            # Cohere retired the unversioned "command", "command-r",
            # "command-r-plus", and "command-light" model IDs on September 15,
            # 2025 — all requests to those names now 404. Current models use
            # dated suffixes instead; check https://docs.cohere.com/docs/models
            # if any of these get retired in turn.
            selected_model = st.selectbox("Select Cohere Model", [
                "command-a-03-2025",
                "command-r-plus-08-2024",
                "command-r-08-2024"
            ], index=0)

    elif app_mode == "API (OpenRouter)":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 OPENROUTER_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            # OpenRouter's free-tier catalog churns almost daily (models get
            # added, removed, or re-priced constantly) — hardcoding specific
            # ":free" slugs breaks quickly, as confirmed firsthand. Default to
            # OpenRouter's own "openrouter/free" router, which auto-selects
            # whichever free model is currently live instead of pinning one.
            or_choice = st.selectbox("Select OpenRouter Model", [
                "openrouter/free (auto-picks a live free model)",
                "Custom model slug…"
            ], index=0)
            if or_choice.startswith("Custom"):
                selected_model = st.text_input("OpenRouter model slug", value="meta-llama/llama-3.1-8b-instruct:free")
            else:
                selected_model = "openrouter/free"

    elif is_custom_mode(app_mode):
        # Bring-your-own OpenAI-compatible endpoints: any service exposing
        # POST {base_url}/chat/completions (OpenAI, Azure OpenAI's /openai/v1,
        # Together, Mistral, DeepSeek, Ollama, LM Studio, LiteLLM, vLLM, ...).
        st.warning("⚠️ A custom endpoint receives your API key and every prompt "
                   "(including the raw text on the Unprotected side). Use test data "
                   "only, and only with services you trust.")
        selected_model = "Unavailable"
        st.session_state.custom_cfg = {}        # rebuilt below once everything is valid

        if active_profile is None:
            # ---------------- form: add a new custom provider ----------------
            st.markdown("**New custom provider**")
            st.text_input("Name", placeholder="e.g. Mistral", key="np_name",
                          help="Shown in the Provider list. 1–30 characters: letters, numbers, spaces, - _ .")
            st.text_input("Base URL", placeholder="https://api.mistral.ai/v1", key="np_url")
            st.text_input("API key", type="password", key="np_key",
                          help="Kept in this browser session only; never written to disk or logs. Leave blank for keyless local endpoints.")
            if st.session_state.get("np_error"):
                st.error(st.session_state.np_error)
            st.button("➕ Create provider", on_click=create_profile_callback, use_container_width=True, key="np_create")
            st.caption("After creating it you can fetch the model list and pick a model.")
        else:
            # ---------------- an existing custom provider ----------------
            prof = st.session_state.custom_profiles[active_profile]
            pk = f"cp::{active_profile}::"
            # Streamlit drops the state of widgets that aren't drawn, so restore
            # what was typed earlier from the stored profile before drawing them.
            for _f, _src in (("url", "base_url"), ("key", "api_key"), ("model_text", "model"),
                             ("sys", "system_as_user"), ("show_all", "show_all_models")):
                if pk + _f not in st.session_state:
                    st.session_state[pk + _f] = prof[_src]

            st.text_input("Base URL", placeholder="https://api.example.com/v1", key=pk + "url")
            st.text_input("API key", type="password", key=pk + "key",
                          help="Kept in this browser session only; never written to disk or logs. Leave blank for keyless local endpoints.")
            custom_url = normalize_base_url(st.session_state[pk + "url"])
            key_in = (st.session_state[pk + "key"] or "").strip()

            url_ok = False
            if custom_url:
                url_ok, url_err = check_custom_url_cached(custom_url)
                if not url_ok:
                    st.error(f"🔗 {url_err}")
            if custom_url and url_ok and not key_in:
                st.caption("No API key provided — sending a placeholder (fine for local/keyless endpoints).")

            # ---- model: fetch the list from the endpoint, or type a name ----
            if st.button("🔄 Fetch models", key=pk + "fetch", use_container_width=True,
                         disabled=not (custom_url and url_ok),
                         help="Asks the endpoint for its model list (GET {Base URL}/models)."):
                with st.spinner("Asking the endpoint for its models…"):
                    try:
                        prof["models_all"] = fetch_models(custom_url, key_in or "not-needed")
                        prof["models_error"] = ""
                    except Exception as exc:
                        prof["models_all"] = []
                        prof["models_error"] = safe_err(exc, 220)
            if prof["models_error"]:
                st.error(prof["models_error"])
            all_ids = prof["models_all"]
            show_all = st.checkbox("Include non-chat models (embeddings, speech…)", key=pk + "show_all") if all_ids else False
            shown = all_ids if show_all else [m for m in all_ids if not NON_CHAT_MODEL_RE.search(m)]
            if all_ids:
                hidden = len(all_ids) - len(shown)
                st.caption(f"{len(shown)} models found" + (f" · {hidden} non-chat hidden" if hidden else ""))
            if shown:
                opts = shown + [TYPE_MODEL_OPTION]
                cur = prof["model"]
                default_idx = shown.index(cur) if cur in shown else (len(opts) - 1 if cur else 0)
                choice = st.selectbox("Model", opts, index=default_idx, key=pk + "model_choice")
                if choice == TYPE_MODEL_OPTION:
                    model_val = (st.text_input("Model name", placeholder="e.g. gpt-4o-mini", key=pk + "model_text") or "").strip()
                else:
                    model_val = choice
            else:
                model_val = (st.text_input("Model name", placeholder="e.g. gpt-4o-mini", key=pk + "model_text") or "").strip()

            sys_flag = st.checkbox("Endpoint rejects 'system' messages", key=pk + "sys",
                                   help="Sends the redaction note inside the first user message instead.")

            # remember everything for when you come back to this provider
            prof["base_url"] = st.session_state[pk + "url"]
            prof["api_key"] = key_in
            prof["model"] = model_val
            prof["system_as_user"] = bool(sys_flag)
            prof["show_all_models"] = bool(show_all)

            st.button("🗑️ Delete this provider", on_click=delete_profile_callback, args=(active_profile,),
                      use_container_width=True, key=pk + "del")

            if custom_url and url_ok and model_val:
                selected_model = model_val
                st.session_state.custom_cfg = {
                    "name": active_profile,
                    "base_url": custom_url,
                    "api_key": key_in or "not-needed",
                    "system_as_user": bool(sys_flag),
                }

    if selected_model not in ["Unavailable", "Connection Error"]:
        st.caption("Mode: API Integration")
        dbg_col1, dbg_col2 = st.columns(2)
        debug_prompt = dbg_col1.checkbox("🔎 Prompt Debug", value=False)
        debug_response = dbg_col2.checkbox("🔎 Response Debug", value=False)

    sidebar_metrics = st.empty()

def refresh_metrics():
    with sidebar_metrics.container():
        with st.expander("Session Stats [beta]", expanded=False):
            c1, c2 = st.columns(2)
            c1.metric("Blocks", st.session_state.security_stats["blocks"])
            c2.metric("Redactions", st.session_state.security_stats["redactions"])
            st.caption(f"⚡ Latency: {st.session_state.last_latency} ms | 🚫 Violation: {st.session_state.last_violation}")

refresh_metrics()

# ==========================================================
# --- MAIN UI: HEADER ---
# ==========================================================
with st.container():
    st.markdown('<div class="fixed-header-container"></div>', unsafe_allow_html=True)
    col_t, col_u = st.columns([0.85, 0.15])
    with col_t:
        st.title("Spooky 𔓎", anchor=False)
        disp_id = f"{PS_APP_ID[:16]}..."
        c, t = (":green", "Connected ●") if ps_enabled else (":red", "Bypassed ○")
        policy_disp = PS_POLICY_NAME if PS_POLICY_NAME else "(connector default)"
        endpoint_disp = ""
        if is_custom_mode(app_mode) and st.session_state.custom_cfg:
            endpoint_disp = f" | Endpoint: **{urlparse(st.session_state.custom_cfg['base_url']).hostname}**"
        st.caption(f"Mode: **{app_mode}** | Model: **{selected_model}**{endpoint_disp}\n\nSecurity: {c}[**{t}**] | ID: **{disp_id}** | Policy: **{policy_disp}**")
    with col_u:
        st.markdown('<div class="header-upload-btn">', unsafe_allow_html=True)
        with st.popover("➕ Upload"):
            uploaded_file = st.file_uploader("Scan File", type=["txt", "pdf", "png", "jpg", "xlsx"], label_visibility="collapsed", key=f"f_{st.session_state.uploader_key}")
            sample_choice = NO_SAMPLE
            _samples = list_sample_files()
            if _samples:
                st.markdown("**…or try a built-in sample**")
                sample_choice = st.selectbox("Built-in sample files", [NO_SAMPLE] + _samples,
                                             key=f"s_{st.session_state.uploader_key}",
                                             label_visibility="collapsed")
                st.button("⚡ Send sample with a ready-made prompt", use_container_width=True,
                          disabled=(sample_choice == NO_SAMPLE), on_click=send_sample_prompt,
                          args=(sample_choice,), key=f"sb_{st.session_state.uploader_key}")
        st.markdown('</div>', unsafe_allow_html=True)

        # An uploaded file wins over a built-in sample.
        attached_file = uploaded_file or load_sample_file(sample_choice)

# Shown full-width under the header (inside the narrow upload column it wrapped into a tall block).
if attached_file:
    st.caption(f"📎 Archivo adjunto y listo: **{attached_file.name}** — escribí tu mensaje abajo y presioná Enter para enviarlo junto con el archivo.")

if selected_model in ["Unavailable", "Connection Error"]:
    if is_custom_mode(app_mode):
        if active_profile is None:
            st.warning("➕ **Add a custom provider.**\n\nIn the sidebar, enter a name, a Base URL (https://…/v1) and an API key, then press *Create provider*.")
        else:
            st.warning(f"⚠️ **{active_profile} is not configured yet.**\n\nEnter a valid Base URL (https://…/v1) and choose or type a Model name in the sidebar.")
    else:
        st.warning(f"⚠️ **{app_mode} is not properly configured.**\n\nPlease add a valid API key to your `.env` file and restart Docker, or select a different integration.")

# SECURITY LOGIC
def check_security_api(text, context_type="prompt", max_retries=2):
    if not ps_enabled: return True, text, {"status": "Bypassed"}, "safe"

    headers = {"Content-Type": "application/json", "APP-ID": PS_APP_ID}
    payload = {context_type: text, "user": user_email}
    if PS_POLICY_NAME:
        payload["policy_name"] = PS_POLICY_NAME

    # Prompt-checks and response-checks hit the same /api/protect endpoint,
    # but response-checks get a "free" cooldown gap — the LLM generation time
    # that happens between the prompt-check and the response-check within a
    # turn. Prompt-checks don't get that gap, especially when firing several
    # trigger prompts back to back, which makes them more exposed to a
    # transient upstream hiccup or rate limit. Rather than accept the first
    # failure as final, retry a couple of times with a short backoff before
    # reporting a real error — this is standalone from the "don't call it
    # Safe" fix: that fix stops us from LYING about an error, this tries to
    # stop the error from happening in the first place when it's transient.
    for attempt in range(max_retries + 1):
        try:
            response = http_session.post(PS_PROTECT_API, json=payload, headers=headers, timeout=15)
            try:
                data = response.json()
            except ValueError:
                data = {"error": f"Non-JSON response (HTTP {response.status_code})", "raw_text": response.text[:500]}

            # The backend can return HTTP 200 with a body that ISN'T a real
            # /api/protect result — e.g. {"message": "Error from backend service"}
            # during an upstream hiccup or rate limit. `data.get("result", {})`
            # would silently return `{}` here, and every downstream lookup
            # (violations, findings, modified_text) would fall back to
            # empty/zero — making an actual backend FAILURE look exactly like
            # a clean "Safe" result, AND passing the original, completely
            # unredacted text through to the LLM. We detect that shape
            # explicitly and treat it as retryable first, then a real "error"
            # status (never "safe") once retries are exhausted.
            if not response.ok or "result" not in data:
                if attempt < max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                st.session_state.last_violation = "⚠️ Security check error"
                return True, text, data, "error"

            res_b = data.get("result", {})

            # NOTE: totalLatency lives inside `result`, not at the top level of the response
            # (per Prompt Security API docs: "Understanding the Structure and Fields of the API Response").
            st.session_state.last_latency = res_b.get("totalLatency") or res_b.get("latency", 0)
            cont_b = res_b.get(context_type, {})
            v_list = cont_b.get("violations", [])
            st.session_state.last_violation = " + ".join(v_list) if v_list else ("None" if context_type == "prompt" else st.session_state.last_violation)

            findings = cont_b.get("findings", {})
            redacts = len(findings.get("Sensitive Data", [])) + len(findings.get("Secrets", [])) + len(findings.get("Regex", []))

            # NOTE: documented /api/protect status codes are 200/400/401/429/500 — there is no 403.
            # The block signal is the `action` field, not the HTTP status.
            if res_b.get("action") == "block":
                st.session_state.security_stats["blocks"] += 1; st.toast("Security Block!", icon="🚨")
                return False, "Blocked", data, "blocked"

            redacted = cont_b.get("modified_text") or text
            if redacts > 0:
                st.session_state.security_stats["redactions"] += redacts; st.toast(f"{redacts} items redacted!", icon="⚠️")
                status = "redacted"
            else: status = "safe"
            return True, redacted, data, status
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            st.session_state.last_violation = "⚠️ Security check error"
            return True, text, {"error": str(e)}, "error"

# CHAT DISPLAY (Supports Standard + Side-by-Side turn rendering)
# NOTE: debug info and redaction notices are stored on each message itself
# (see the "debug"/"notices" keys added when messages are appended below),
# so every past turn keeps its own record — not just the most recent one.
# This also means toggling "Show Debug Info" on retroactively reveals debug
# data for earlier turns, since it was captured at request time regardless
# of whether the checkbox was on when the turn happened.
messages_list = st.session_state.multi_messages[app_mode]

def render_turn_debug(dbg, show_prompt, show_response):
    """Renders the prompt-check and/or response-check debug boxes for a turn,
    each gated by its OWN checkbox (Prompt Debug / Response Debug) — and each
    shown with ITS OWN status (Safe/Redacted/Blocked), never a single combined
    label — so a turn where the prompt was clean but the response got
    redacted correctly shows "Safe" for the prompt and "Redacted" for the
    response, instead of one misleading "Safe" badge."""
    if not dbg: return
    if show_prompt and dbg.get("prompt_check"):
        st.caption("🔎 Prompt Check")
        render_debug_box(dbg["prompt_check"])
    if show_response and dbg.get("response_check"):
        st.caption("🔎 Response Check")
        render_debug_box(dbg["response_check"])

def render_turn_notices(notices):
    """Renders the right banner for each notice recorded on a turn. Error and
    redaction notices are DIFFERENT things — silently treating a backend
    error notice as a generic 'redacted' banner would repeat the same mistake
    this fix targets, just one layer up."""
    if not notices: return
    shown = set()
    for n in notices:
        msg_key = "security_check_error" if n.startswith("error") else "redacted_notice"
        if msg_key in shown: continue
        shown.add(msg_key)
        if msg_key == "security_check_error":
            show_security_error_notice()
        else:
            show_redacted_notice()

def render_sent_box(text, blocked=False):
    """Shows the exact text handed to the model in one side-by-side column.
    Both columns answer the SAME user prompt, but the Protected column sends
    the redacted version — this makes that difference visible."""
    with st.expander("📨 What the model received", expanded=False):
        if blocked or text is None:
            st.caption("Nothing — the prompt was blocked before it reached the model.")
        else:
            st.text(text)

for i, m in enumerate(messages_list):
    if m.get("role") == "side_by_side":
        with st.chat_message("user"):
            st.write(m["user_prompt"])
        c_prot, c_unprot = st.columns(2)
        with c_prot:
            st.markdown("#### 🛡️ Protected Mode")
            render_turn_notices(m.get("notices"))
            render_answer(m["protected_response"])
            render_turn_debug(m.get("debug"), debug_prompt, debug_response)
            render_sent_box(m.get("protected_sent", m.get("user_prompt")), blocked=m.get("protected_blocked", False))
        with c_unprot:
            st.markdown("#### ⚠️ Unprotected Mode")
            render_answer(m["unprotected_response"])
            render_sent_box(m["user_prompt"])
    else:
        if m["role"] == "assistant":
            dbg = m.get("debug") or {}
            notices = m.get("notices") or []

            # Everything below is deliberately OUTSIDE any st.chat_message()
            # block. st.chat_message() wraps its entire contents in one
            # bordered card (see CSS rule 5), so anything written inside it
            # visually merges with the answer. These notices/debug boxes
            # describe separate events (the prompt check, the response
            # check) and belong as standalone elements sitting between the
            # user's bubble and the assistant's bubble — not enclosed inside it.
            for n in notices:
                if n == "redacted_prompt": show_redacted_notice()
                elif n == "error_prompt": show_security_error_notice()
            if debug_prompt and dbg.get("prompt_check"):
                st.caption("🔎 Prompt Check")
                render_debug_box(dbg["prompt_check"])

            with st.chat_message("assistant"):
                render_answer(m["content"])

            for n in notices:
                if n == "redacted_response": show_redacted_notice()
                elif n == "error_response": show_security_error_notice()
            if debug_response and dbg.get("response_check"):
                st.caption("🔎 Response Check")
                render_debug_box(dbg["response_check"])
        else:
            with st.chat_message(m["role"]):
                st.write(m["content"])

# CHAT INPUT & PROCESSING
chat_v = st.chat_input("How can I help you safely?  (↑ recalls your previous prompts)")
prompt = st.session_state.input_text if st.session_state.input_text else chat_v
st.session_state.input_text = None

if prompt and selected_model not in ["Unavailable", "Connection Error"]:
    remember_prompt(prompt)   # arrow-up history (browser cookie)

    ctx, img = "", None
    if attached_file:
        t = attached_file.type; attached_file.seek(0)
        if "text" in t or "csv" in t: ctx = f"\n\n[File: {attached_file.name}]\n{attached_file.read().decode('utf-8', errors='ignore')}"
        elif "pdf" in t:
            try:
                raw_pdf_text = "".join([p.extract_text() or "" for p in pypdf.PdfReader(attached_file).pages])
                ctx = f"\n\n[PDF: {attached_file.name}]\n" + normalize_pdf_text(raw_pdf_text)
            except Exception: ctx = "\n[PDF Error]"
        elif "image" in t:
            try: img = Image.open(attached_file); ctx = f"\n\n[Image: {attached_file.name}]"
            except Exception: pass
        elif "spreadsheet" in t or "excel" in t:
            try:
                wb = openpyxl.load_workbook(attached_file, data_only=True)
                sheet_texts = []
                for ws in wb.worksheets:
                    lines = [f"--- Sheet: {ws.title} ---"]
                    for row in ws.iter_rows(values_only=True):
                        if any(cell is not None for cell in row):
                            lines.append(" | ".join("" if c is None else str(c) for c in row))
                    sheet_texts.append("\n".join(lines))
                ctx = f"\n\n[XLSX: {attached_file.name}]\n" + "\n\n".join(sheet_texts)
            except Exception as e:
                ctx = f"\n[XLSX Error: {e}]"

        # The file has been consumed for this message — reset the uploader
        # (and the sample picker) so it doesn't silently get re-attached to
        # the next message.
        st.session_state.uploader_key += 1

    full_p = f"{prompt if prompt else ''} {ctx}".strip()

    if full_p or img:
        # --- API METHOD ---
        msgs = st.session_state.multi_messages[app_mode]
        # Two separate replay histories: the protected conversation only ever
        # replays text that already passed the security check (earlier prompts
        # in their REDACTED form); the unprotected one replays the raw text.
        history_prot = get_api_history(msgs, "protected")
        history_raw = get_api_history(msgs, "raw")

        if side_by_side:
            with st.chat_message("user"):
                st.write(full_p)
                if img: st.image(img, width=300)

            col_prot, col_unprot = st.columns(2)
            protected_final = ""
            unprotected_final = ""
            protected_sent, protected_blocked = None, False
            protected_ok, unprotected_ok = False, False
            turn_debug = {"prompt_check": None, "response_check": None}
            turn_notices = []

            # LEFT COLUMN: PROTECTED
            with col_prot:
                st.markdown("#### 🛡️ Protected Mode")
                safe, check, dbg, status = check_security_api(full_p, "prompt")
                turn_debug["prompt_check"] = {"checked_p": check, "original_p": full_p, "debug": dbg, "status_type": status}

                if status == "redacted":
                    show_redacted_notice()
                    turn_notices.append("redacted_prompt")
                elif status == "error":
                    show_security_error_notice()
                    turn_notices.append("error_prompt")

                if debug_prompt:
                    st.caption("🔎 Prompt Check")
                    render_debug_box(turn_debug["prompt_check"])

                if not safe:
                    protected_blocked = True
                    protected_final = CUSTOM_MESSAGES["blocked_prompt"]
                    st.error(protected_final)
                else:
                    protected_sent = check
                    with st.spinner("Generating protected output..."):
                        try:
                            res_text = call_llm(app_mode, selected_model, history_prot, check, img, protected=ps_enabled)

                            if res_text:
                                # IMPORTANT: this response-level check is what actually catches
                                # PII the model echoes back (e.g. an email address repeated in
                                # its answer). Its status must be surfaced — previously it was
                                # computed but discarded, which is why the UI could show "Safe"
                                # even while the response was being redacted underneath.
                                s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                turn_debug["response_check"] = {"checked_p": s_reply, "original_p": res_text, "debug": s_dbg, "status_type": s_status}
                                protected_final = s_reply
                                protected_ok = bool(s_safe)

                                if s_status == "redacted":
                                    show_redacted_notice()
                                    turn_notices.append("redacted_response")
                                elif s_status == "error":
                                    show_security_error_notice()
                                    turn_notices.append("error_response")

                                if debug_response:
                                    st.caption("🔎 Response Check")
                                    render_debug_box(turn_debug["response_check"])

                                render_answer(protected_final)
                            else:
                                protected_final = "No response generated."
                                st.error(protected_final)
                        except Exception as e:
                            protected_final = f"⚠️ Error: {safe_err(e, 150)}"
                            st.error(protected_final)
                render_sent_box(protected_sent, blocked=protected_blocked)

            # RIGHT COLUMN: UNPROTECTED (Raw input, no redaction note)
            with col_unprot:
                st.markdown("#### ⚠️ Unprotected Mode")
                with st.spinner("Generating raw output..."):
                    try:
                        raw_res = call_llm(app_mode, selected_model, history_raw, full_p, img,
                                           warn_img=False, protected=False)

                        if raw_res:
                            unprotected_final = raw_res
                            unprotected_ok = True
                            render_answer(unprotected_final)
                        else:
                            unprotected_final = "No response generated."
                            st.error(unprotected_final)
                    except Exception as e:
                        unprotected_final = f"⚠️ Error: {safe_err(e, 150)}"
                        st.error(unprotected_final)
                render_sent_box(full_p)

            # Append whole side-by-side snapshot into session memory
            msgs.append({
                "role": "side_by_side",
                "user_prompt": full_p,
                "protected_sent": protected_sent,
                "protected_blocked": protected_blocked,
                "protected_ok": protected_ok,
                "protected_response": protected_final,
                "unprotected_ok": unprotected_ok,
                "unprotected_response": unprotected_final,
                "debug": turn_debug,
                "notices": turn_notices
            })
            refresh_metrics()

        else:
            # SINGLE STANDARD VIEW
            with st.chat_message("user"):
                st.write(full_p)
                if img: st.image(img, width=300)

            turn_debug = {"prompt_check": None, "response_check": None}
            turn_notices = []

            safe, check, dbg, status = check_security_api(full_p, "prompt")
            turn_debug["prompt_check"] = {"checked_p": check, "original_p": full_p, "debug": dbg, "status_type": status}

            if status == "redacted":
                show_redacted_notice()
                turn_notices.append("redacted_prompt")
            elif status == "error":
                show_security_error_notice()
                turn_notices.append("error_prompt")

            # Shown right here, BEFORE the LLM is even called — this is when
            # the prompt check actually happens. Previously this box only
            # appeared after the model's answer was already on screen,
            # which made it look like it came from checking the response.
            if debug_prompt:
                st.caption("🔎 Prompt Check")
                render_debug_box(turn_debug["prompt_check"])

            refresh_metrics()

            # "content" is what the user typed (shown in the chat); "sent" is
            # what the model actually received (the redacted text) — only
            # "sent" is replayed to the model on later turns.
            user_entry = {"role": "user", "content": full_p, "sent": check if safe else None}

            if not safe:
                m = CUSTOM_MESSAGES["blocked_prompt"]
                user_entry["skip_history"] = True      # blocked content never goes back to the model
                msgs.append(user_entry)
                msgs.append({"role": "assistant", "content": m, "debug": turn_debug, "notices": turn_notices, "skip_history": True})
                with st.chat_message("assistant"):
                    render_answer(m)
            else:
                res_text, gen_error = None, None
                with st.spinner("Thinking..."):
                    try:
                        res_text = call_llm(app_mode, selected_model, history_prot, check, img, protected=ps_enabled)
                    except Exception as e:
                        gen_error = e

                if gen_error is not None:
                    if "401" in str(gen_error): err_msg = f"🚫 Auth Error: Your {app_mode} Key is invalid."
                    else: err_msg = f"⚠️ Error: {safe_err(gen_error, 200)}..."
                    st.error(err_msg)
                    # Keep the failed turn on screen, but never replay it to the model
                    # (an orphan user message breaks role alternation on some APIs).
                    user_entry["skip_history"] = True
                    msgs.append(user_entry)
                    msgs.append({"role": "assistant", "content": err_msg, "debug": turn_debug, "notices": turn_notices, "skip_history": True})
                elif res_text:
                    # Same fix as side-by-side: the response-level check's own
                    # status (Safe/Redacted/Blocked) must be shown for itself,
                    # not silently folded away — this is the check that catches
                    # PII the model echoes back in its answer.
                    s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                    turn_debug["response_check"] = {"checked_p": s_reply, "original_p": res_text, "debug": s_dbg, "status_type": s_status}

                    # Answer bubble first — the response check only exists
                    # because the answer already exists to check, so it
                    # must render AFTER, not before (this matches the
                    # history-replay loop below, which already had it right).
                    with st.chat_message("assistant"):
                        render_answer(s_reply)

                    if s_status == "redacted":
                        show_redacted_notice()
                        turn_notices.append("redacted_response")
                    elif s_status == "error":
                        show_security_error_notice()
                        turn_notices.append("error_response")

                    if debug_response:
                        st.caption("🔎 Response Check")
                        render_debug_box(turn_debug["response_check"])

                    assistant_entry = {"role": "assistant", "content": s_reply, "debug": turn_debug, "notices": turn_notices}
                    if not s_safe:
                        user_entry["skip_history"] = True
                        assistant_entry["skip_history"] = True
                    msgs.append(user_entry)
                    msgs.append(assistant_entry)
                else:
                    err_msg = "🚨 Rate limit exceeded (429) or no models available. Please wait 60 seconds."
                    st.error(err_msg)
                    user_entry["skip_history"] = True
                    msgs.append(user_entry)
                    msgs.append({"role": "assistant", "content": err_msg, "debug": turn_debug, "notices": turn_notices, "skip_history": True})

            refresh_metrics()

# Arrow-up prompt history: installs the key handler in the page (idempotent).
install_arrow_up_history()

st.sidebar.markdown('<div class="sidebar-footer">Made by Gastón Z and AI 🤖</div>', unsafe_allow_html=True)
