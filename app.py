import streamlit as st
from google import genai
from google.genai import types
from openai import OpenAI
import requests
import os
import pypdf
import random
import json
import ssl
from PIL import Image
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

[data-testid="stStatusWidget"] { visibility: hidden; display: none !important; }
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================================
# --- GLOBALS & STATE ---
# ==========================================================
PS_APP_ID = os.getenv("PS_APP_ID")
PS_GATEWAY_URL = os.getenv("PS_GATEWAY_URL")
if not PS_APP_ID or not PS_GATEWAY_URL:
    st.error("🚨 Critical Error: PS_APP_ID or PS_GATEWAY_URL missing.")
    st.stop()
PS_PROTECT_API = f"{PS_GATEWAY_URL.strip('/')}/api/protect"

_MODES = ["API (Gemini)", "API (Groq)", "API (Cohere)", "API (OpenRouter)", "AI Gateway (OpenAI)", "AI Gateway (Gemini)"]

_GROQ_MODELS       = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b", "openai/gpt-oss-120b"]
_COHERE_MODELS     = ["command-r7b-12-2024", "command-r-08-2024", "command-r-plus-08-2024", "command-a-03-2025"]
_OPENROUTER_MODELS = ["deepseek/deepseek-v4-flash:free", "google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "arcee-ai/trinity-large-thinking:free", "poolside/laguna-m.1:free"]

if "multi_messages" not in st.session_state:
    st.session_state.multi_messages = {m: [] for m in _MODES}
if "session_costs" not in st.session_state:
    st.session_state.session_costs = {m: 0.0 for m in _MODES}
if "security_stats" not in st.session_state:
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
if "last_latency" not in st.session_state: st.session_state.last_latency = 0
if "last_violation" not in st.session_state: st.session_state.last_violation = "None"
if "current_integration" not in st.session_state:
    _default = os.getenv("DEFAULT_INTEGRATION", "API (Gemini)").strip()
    st.session_state.current_integration = _default if _default in _MODES else "API (Gemini)"
if "input_text" not in st.session_state: st.session_state.input_text = None
if "last_debug_info" not in st.session_state: st.session_state.last_debug_info = None
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "gemini_available_models" not in st.session_state: st.session_state.gemini_available_models = []
if "selected_gemini_model" not in st.session_state: st.session_state.selected_gemini_model = None
if "side_by_side" not in st.session_state: st.session_state.side_by_side = False
if "side_messages" not in st.session_state:
    st.session_state.side_messages = {
        "protected":   {m: [] for m in _MODES},
        "unprotected": {m: [] for m in _MODES}
    }

# Ensure new modes have entries in session state (in case session was initialized before this mode was added)
for _mode in _MODES:
    st.session_state.multi_messages.setdefault(_mode, [])
    st.session_state.session_costs.setdefault(_mode, 0.0)
    st.session_state.side_messages["protected"].setdefault(_mode, [])
    st.session_state.side_messages["unprotected"].setdefault(_mode, [])

# ==========================================================
# --- HELPERS ---
# ==========================================================
def reset_chat():
    mode = st.session_state.current_integration
    st.session_state.multi_messages[mode] = []
    st.session_state.side_messages["protected"][mode] = []
    st.session_state.side_messages["unprotected"][mode] = []
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
    st.session_state.last_latency, st.session_state.last_violation = 0, "None"
    st.session_state.session_costs[mode], st.session_state.last_debug_info = 0.0, None
    st.session_state.uploader_key += 1
    st.toast("History cleared.")

def set_prompt(text):
    st.session_state.input_text = text
    st.session_state.uploader_key += 1

def render_debug_box(info):
    if not info: return
    stype = info.get('status_type', 'safe')
    if stype == "blocked": label, state, content = "🚫 Violation Detected", "error", None
    elif stype == "redacted": label, state, content = "⚠️ Content Redacted", "complete", f"Redacted Content: {info.get('checked_p', '')}"
    else: label, state, content = "✅ Safe", "complete", None
    with st.status(label, expanded=False, state=state):
        if content: st.warning(content)
        with st.expander("🔍 View Raw API Response", expanded=False): st.json(info.get('debug', {}))

def get_env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")

def get_chat_models(client):
    try:
        return sorted(set([m.name for m in client.models.list() if "gemini" in m.name.lower()]))
    except:
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

def is_valid_key(key):
    if not key: return False
    k_lower = key.lower()
    if "your" in k_lower or "key" in k_lower or "here" in k_lower or len(key) < 10: return False
    return True

# ==========================================================
# --- GATEWAY CALL HELPERS ---
# ==========================================================

def _call_cohere(checked_prompt, history):
    """Call Cohere via its OpenAI-compatible endpoint, with automatic model fallback on rate limits."""
    client = OpenAI(base_url="https://api.cohere.com/compatibility/v1", api_key=api_key)
    messages = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]
    messages.append({"role": "user", "content": checked_prompt})
    for model in _COHERE_MODELS:
        try:
            r = client.chat.completions.create(model=model, messages=messages)
            return r.choices[0].message.content
        except Exception as e:
            if "429" in str(e):
                continue
            raise
    raise Exception("All Cohere models are rate-limited. Please wait and try again.")


def _call_openrouter(checked_prompt, history):
    """Call OpenRouter via its OpenAI-compatible endpoint, with automatic model fallback on rate limits."""
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"HTTP-Referer": "https://spooky-ai.local", "X-Title": "Spooky AI"}
    )
    messages = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]
    messages.append({"role": "user", "content": checked_prompt})
    for model in _OPENROUTER_MODELS:
        try:
            r = client.chat.completions.create(model=model, messages=messages)
            return r.choices[0].message.content
        except Exception as e:
            if "429" in str(e):
                continue
            raise
    raise Exception("All OpenRouter models are rate-limited. Please wait and try again.")


def _call_groq(checked_prompt, history):
    """Call Groq via its OpenAI-compatible endpoint, with automatic model fallback on rate limits."""
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    messages = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]
    messages.append({"role": "user", "content": checked_prompt})
    for model in _GROQ_MODELS:
        try:
            r = client.chat.completions.create(model=model, messages=messages)
            return r.choices[0].message.content
        except Exception as e:
            if "429" in str(e):
                continue
            raise
    raise Exception("All Groq models are rate-limited. Please wait and try again.")


def _call_openai_gateway(prompt_text, history, use_gateway=True):
    """
    Call OpenAI via PS AI Gateway (reverse proxy) — PS checks prompt + response inline.
    When use_gateway=False, calls OpenAI directly (used for unprotected side-by-side column).
    """
    if use_gateway:
        client = OpenAI(
            base_url=f"{PS_GATEWAY_URL.strip('/')}/v1",
            api_key=api_key,
            default_headers={
                "ps-app-id": PS_APP_ID,
                "forward-domain": "api.openai.com",
                "user": user_email
            }
        )
    else:
        client = OpenAI(api_key=api_key)
    messages = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]
    messages.append({"role": "user", "content": prompt_text})
    r = client.chat.completions.create(model=selected_model, messages=messages)
    return r.choices[0].message.content



def _call_gemini_gateway(prompt_text, history, use_gateway=True):
    """
    Call Gemini via PS AI Gateway using raw HTTP requests.
    Bypasses the deprecated genai_legacy SDK to avoid response-parsing issues.
    When use_gateway=False, calls Google AI directly.
    """
    if use_gateway:
        base = PS_GATEWAY_URL.strip('/')
        extra_headers = {
            "ps-app-id": PS_APP_ID,
            "forward-domain": "generativelanguage.googleapis.com",
            "user": user_email
        }
    else:
        base = "https://generativelanguage.googleapis.com"
        extra_headers = {}

    url = f"{base}/v1beta/models/{selected_model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key, **extra_headers}

    contents = []
    for m in history[:-1]:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    contents.append({"role": "user", "parts": [{"text": prompt_text}]})

    resp = http_session.post(url, json={"contents": contents}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ==========================================================
# --- SIDEBAR ---
# ==========================================================
with st.sidebar:
    st.header("App Settings")
    st.button("🗑️ Clear Current Chat", use_container_width=True, on_click=reset_chat)
    trigger_data = {}
    try:
        with open("triggers.txt", "r") as f: trigger_data = json.load(f)
    except: trigger_data = {"System": {"Error": ["Check triggers.txt file"]}}
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

    user_email = st.text_input("User Identity", value=os.getenv("DEMO_USER_EMAIL", "john.doe@unknown.com"))

    st.markdown("### Protection Layer")
    ps_enabled = st.toggle("Enable Prompt Security", value=True)
    side_by_side = st.toggle("🔀 Side-by-side Comparison", value=st.session_state.side_by_side)
    st.session_state.side_by_side = side_by_side
    st.divider()

    _cur = st.session_state.current_integration
    _cur_method   = "AI Gateway" if _cur.startswith("AI Gateway") else "API"
    _cur_provider = _cur.replace(f"{_cur_method} (", "").rstrip(")")

    st.markdown("**Integration Method:**")
    method = st.radio("method", ["API", "AI Gateway"],
                      index=0 if _cur_method == "API" else 1,
                      label_visibility="collapsed")

    _api_providers = ["Gemini", "Groq", "Cohere", "OpenRouter"]
    _gw_providers  = ["OpenAI", "Gemini"]

    if method == "AI Gateway":
        _prov_idx = _gw_providers.index(_cur_provider) if (_cur_method == "AI Gateway" and _cur_provider in _gw_providers) else 0
        provider = st.selectbox("Provider:", _gw_providers, index=_prov_idx)
        app_mode = f"AI Gateway ({provider})"
    else:
        _prov_idx = _api_providers.index(_cur_provider) if (_cur_method == "API" and _cur_provider in _api_providers) else 0
        provider = st.selectbox("Provider:", _api_providers, index=_prov_idx)
        app_mode = f"API ({provider})"

    if app_mode != st.session_state.current_integration:
        st.session_state.current_integration, st.session_state.last_debug_info = app_mode, None
        st.rerun()

    st.divider()

    debug_mode = False  # default; overridden below for API modes

    if app_mode == "API (Cohere)":
        api_key = os.getenv("COHERE_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 COHERE_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = _COHERE_MODELS[0]
            st.caption(f"Auto-selected: `{selected_model}`")
        st.caption("Mode: API Integration")
        if selected_model not in ["Unavailable", "Connection Error"]:
            debug_mode = st.checkbox("Show Debug Info", value=False)

    elif app_mode == "API (OpenRouter)":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 OPENROUTER_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = _OPENROUTER_MODELS[0]
            st.caption(f"Auto-selected: `{selected_model}`")
        st.caption("Mode: API Integration")
        if selected_model not in ["Unavailable", "Connection Error"]:
            debug_mode = st.checkbox("Show Debug Info", value=False)

    elif app_mode == "API (Groq)":
        api_key = os.getenv("GROQ_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 GROQ_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = _GROQ_MODELS[0]
            st.caption(f"Auto-selected: `{selected_model}`")
        st.caption("Mode: API Integration")
        debug_mode = st.checkbox("Show Debug Info", value=False)
        st.info("💡 Groq is highly recommended for users hitting Gemini rate limits.")

    elif app_mode == "AI Gateway (Gemini)":
        api_key = os.getenv("GEMINI_FREE_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 GEMINI_FREE_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = st.selectbox("Select Gemini Model", [
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
            ], index=0)
        st.caption("Mode: AI Gateway (Reverse Proxy)")
        st.info("🛡️ PS Gateway intercepts and checks both prompt and response inline before forwarding to Gemini.")

    elif app_mode == "AI Gateway (OpenAI)":
        api_key = os.getenv("OPENAI_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 OPENAI_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = st.selectbox("Select OpenAI Model", [
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-3.5-turbo",
            ], index=0)
        st.caption("Mode: AI Gateway (Reverse Proxy)")
        st.info("🛡️ PS Gateway intercepts and checks both prompt and response inline before forwarding to OpenAI.")

    else:  # API (Gemini)
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
                st.error(f"⚠️ Google API Auth Failed. Check your key.")
                selected_model = "Connection Error"
                st.session_state.gemini_available_models = []

        st.caption("Mode: API Integration")
        if selected_model not in ["Unavailable", "Connection Error"]:
            debug_mode = st.checkbox("Show Debug Info", value=False)

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
        st.title("Spooky 𔓎")
        disp_id = f"{PS_APP_ID[:16]}..."
        c, t = (":green", "Connected ●") if ps_enabled else (":red", "Bypassed ○")
        st.caption(f"Mode: **{app_mode}** | Model: **{selected_model}**\n\nSecurity: {c}[**{t}**] | ID: **{disp_id}**")
    with col_u:
        if not side_by_side:
            st.markdown('<div class="header-upload-btn">', unsafe_allow_html=True)
            with st.popover("➕ Upload"):
                uploaded_file = st.file_uploader("Scan File", type=["txt", "pdf", "png", "jpg"], label_visibility="collapsed", key=f"f_{st.session_state.uploader_key}")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            uploaded_file = None

if selected_model in ["Unavailable", "Connection Error"]:
    st.warning(f"⚠️ **{app_mode} is not properly configured.**\n\nPlease add a valid API key to your `.env` file and restart Docker, or select a different integration.")

# ==========================================================
# --- SECURITY CHECK FUNCTION ---
# ==========================================================
def check_security_api(text, context_type="prompt"):
    if not ps_enabled: return True, text, {"status": "Bypassed"}, "safe"
    try:
        headers = {"Content-Type": "application/json", "APP-ID": PS_APP_ID}
        response = http_session.post(PS_PROTECT_API, json={context_type: text, "user": user_email}, headers=headers, timeout=15)
        data = response.json()
        res_b = data.get("result", {})
        st.session_state.last_latency = data.get("totalLatency") or res_b.get("latency", 0)
        cont_b = res_b.get(context_type, {})
        v_list = cont_b.get("violations", [])
        st.session_state.last_violation = " + ".join(v_list) if v_list else ("None" if context_type == "prompt" else st.session_state.last_violation)
        findings = cont_b.get("findings", {})
        redacts = len(findings.get("Sensitive Data", [])) + len(findings.get("Secrets", [])) + len(findings.get("Regex", []))
        if response.status_code == 403 or res_b.get("action") == "block":
            st.session_state.security_stats["blocks"] += 1; st.toast("Security Block!", icon="🚨")
            return False, "Blocked", data, "blocked"
        redacted = cont_b.get("modified_text") or text
        if redacts > 0:
            st.session_state.security_stats["redactions"] += redacts; st.toast(f"{redacts} items redacted!", icon="⚠️")
            status = "redacted"
        else: status = "safe"
        return True, redacted, data, status
    except Exception as e: return True, text, {"error": str(e)}, "safe"

# ==========================================================
# --- LLM CALL HELPER (used by side-by-side mode) ---
# ==========================================================
def get_llm_response(prompt_text, history, img=None, use_ps_gateway=None):
    """Call the LLM and return (response_text, error_msg)."""
    if use_ps_gateway is None:
        use_ps_gateway = ps_enabled
    try:
        if app_mode == "AI Gateway (OpenAI)":
            return _call_openai_gateway(prompt_text, history, use_gateway=use_ps_gateway), None

        elif app_mode == "AI Gateway (Gemini)":
            return _call_gemini_gateway(prompt_text, history, use_gateway=use_ps_gateway), None

        elif app_mode == "API (Cohere)":
            return _call_cohere(prompt_text, history), None

        elif app_mode == "API (OpenRouter)":
            return _call_openrouter(prompt_text, history), None

        elif app_mode == "API (Gemini)":
            genai_client = st.session_state.get("genai_client")
            if not genai_client:
                return None, "Gemini client not initialized. Check your GEMINI_FREE_API_KEY."
            contents = []
            for m in history[:-1]:
                role = "user" if m["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
            current_parts = [types.Part.from_text(text=prompt_text)]
            if img:
                current_parts.append(img)
            contents.append(types.Content(role="user", parts=current_parts))
            res = None
            for mname in get_runtime_gemini_candidates(selected_model, st.session_state.gemini_available_models):
                try:
                    res = genai_client.models.generate_content(model=mname, contents=contents)
                    break
                except Exception as e:
                    if "429" in str(e): continue
                    else: raise e
            if res and res.text:
                return res.text, None
            return None, "Rate limit exceeded (429) or no models available. Please wait 60 seconds."

        elif app_mode == "API (Groq)":
            if img:
                return None, "Image uploads are not supported by Groq text models."
            return _call_groq(prompt_text, history), None

    except Exception as e:
        return None, str(e)[:400]

# ==========================================================
# --- MAIN CHAT AREA ---
# ==========================================================

if not st.session_state.side_by_side:
    # ----------------------------------------------------------
    # SINGLE-CHAT MODE
    # ----------------------------------------------------------
    last_idx = -1
    for i, m in enumerate(st.session_state.multi_messages[app_mode]):
        if m["role"] == "user": last_idx = i

    debug_ph = None
    for i, m in enumerate(st.session_state.multi_messages[app_mode]):
        with st.chat_message(m["role"]): st.write(m["content"])
        if i == last_idx:
            debug_ph = st.empty()
            if "API" in app_mode and debug_mode and st.session_state.last_debug_info:
                info = st.session_state.last_debug_info
                if info.get('original_p') == m["content"]:
                    with debug_ph.container(): render_debug_box(info)

    chat_v = st.chat_input("How can I help you safely?")
    prompt = st.session_state.input_text if st.session_state.input_text else chat_v
    st.session_state.input_text = None

    if (prompt or uploaded_file) and selected_model not in ["Unavailable", "Connection Error"]:
        ctx, img = "", None
        if uploaded_file:
            t = uploaded_file.type; uploaded_file.seek(0)
            if "text" in t or "csv" in t: ctx = f"\n\n[File: {uploaded_file.name}]\n{uploaded_file.read().decode('utf-8', errors='ignore')}"
            elif "pdf" in t:
                try: ctx = f"\n\n[PDF: {uploaded_file.name}]\n" + "".join([p.extract_text() or "" for p in pypdf.PdfReader(uploaded_file).pages])
                except: ctx = "\n[PDF Error]"
            elif "image" in t:
                try: img = Image.open(uploaded_file); ctx = f"\n\n[Image: {uploaded_file.name}]"
                except: pass

        full_p = f"{prompt if prompt else ''} {ctx}".strip()
        if full_p or img:
            if debug_ph: debug_ph.empty()
            st.session_state.multi_messages[app_mode].append({"role": "user", "content": full_p})
            with st.chat_message("user"):
                st.write(full_p)
                if img: st.image(img, width=300)

            # --- AI GATEWAY METHOD (pre-check via PS API for redaction, then route through PS Gateway) ---
            if app_mode in ["AI Gateway (OpenAI)", "AI Gateway (Gemini)"]:
                safe, check, dbg, status = check_security_api(full_p, "prompt")
                refresh_metrics()
                if not safe:
                    m = "Blocked due to policy violations"
                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": m})
                    with st.chat_message("assistant"): st.write(m)
                else:
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            try:
                                if app_mode == "AI Gateway (Gemini)":
                                    res_text = _call_gemini_gateway(check, st.session_state.multi_messages[app_mode], use_gateway=True)
                                else:
                                    res_text = _call_openai_gateway(check, st.session_state.multi_messages[app_mode], use_gateway=True)
                                if res_text:
                                    s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                    st.write(s_reply)
                                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": s_reply})
                            except Exception as e:
                                err_str = str(e)
                                err_low = err_str.lower()
                                if any(w in err_low for w in ["block", "violat", "policy", "forbidden"]) or "403" in err_str:
                                    st.session_state.security_stats["blocks"] += 1
                                    st.toast("Security Block!", icon="🚨")
                                    reply = "🚫 Blocked by Prompt Security Gateway"
                                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": reply})
                                    st.write(reply)
                                elif "401" in err_str or "authentication" in err_low:
                                    st.error(f"🚫 Auth Error: Check your API key for {app_mode}. Detail: {err_str[:300]}")
                                else:
                                    st.error(f"⚠️ Error ({type(e).__name__}): {err_str[:300]}")
                refresh_metrics()

            # --- API METHOD (all other integrations) ---
            else:
                safe, check, dbg, status = check_security_api(full_p, "prompt")
                st.session_state.last_debug_info = {"checked_p": check, "original_p": full_p, "debug": dbg, "status_type": status}
                if debug_mode: render_debug_box(st.session_state.last_debug_info)
                refresh_metrics()

                if not safe:
                    m = "Blocked due to policy violations"
                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": m})
                    with st.chat_message("assistant"): st.write(m)
                else:
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            try:
                                res_text = None

                                if app_mode == "API (Gemini)":
                                    genai_client = st.session_state.genai_client
                                    contents = []
                                    for m in st.session_state.multi_messages[app_mode][:-1]:
                                        role = "user" if m["role"] == "user" else "model"
                                        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
                                    current_parts = [types.Part.from_text(text=check)]
                                    if img: current_parts.append(img)
                                    contents.append(types.Content(role="user", parts=current_parts))
                                    res = None
                                    for mname in get_runtime_gemini_candidates(selected_model, st.session_state.gemini_available_models):
                                        try:
                                            res = genai_client.models.generate_content(model=mname, contents=contents)
                                            break
                                        except Exception as e:
                                            if "429" in str(e): continue
                                            else: raise e
                                    if res and res.text:
                                        res_text = res.text
                                    else:
                                        st.error("🚨 Rate limit exceeded (429) or no models available. Please wait 60 seconds.")

                                elif app_mode == "API (Groq)":
                                    if img: st.warning("🖼️ Image uploads are not currently supported by Groq text models. Ignoring image.")
                                    res_text = _call_groq(check, st.session_state.multi_messages[app_mode])

                                elif app_mode == "API (Cohere)":
                                    if img: st.warning("🖼️ Image uploads are not currently supported by Cohere. Ignoring image.")
                                    res_text = _call_cohere(check, st.session_state.multi_messages[app_mode])

                                elif app_mode == "API (OpenRouter)":
                                    if img: st.warning("🖼️ Image uploads are not supported by this OpenRouter model. Ignoring image.")
                                    res_text = _call_openrouter(check, st.session_state.multi_messages[app_mode])

                                if res_text:
                                    s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                    st.write(s_reply)
                                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": s_reply})
                                    if s_status in ["redacted", "blocked"]:
                                        st.session_state.last_debug_info = {"checked_p": s_reply, "original_p": res_text, "debug": s_dbg, "status_type": s_status}
                                        if debug_mode: render_debug_box(st.session_state.last_debug_info)

                                refresh_metrics()
                            except Exception as e:
                                if "401" in str(e): st.error(f"🚫 Auth Error: Your {app_mode} Key is invalid.")
                                else: st.error(f"⚠️ Error: {str(e)[:200]}...")

else:
    # ----------------------------------------------------------
    # SIDE-BY-SIDE COMPARISON MODE
    # ----------------------------------------------------------
    msgs_prot   = st.session_state.side_messages["protected"][app_mode]
    msgs_unprot = st.session_state.side_messages["unprotected"][app_mode]

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 🛡️ Protected")
        for m in msgs_prot:
            with st.chat_message(m["role"]): st.write(m["content"])

    with col_right:
        st.markdown("#### ⚠️ Unprotected")
        for m in msgs_unprot:
            with st.chat_message(m["role"]): st.write(m["content"])

    chat_v = st.chat_input("Send to both chats simultaneously...")
    prompt = st.session_state.input_text if st.session_state.input_text else chat_v
    st.session_state.input_text = None

    if prompt and selected_model not in ["Unavailable", "Connection Error"]:
        msgs_prot.append({"role": "user", "content": prompt})
        msgs_unprot.append({"role": "user", "content": prompt})

        with col_left:
            with st.chat_message("user"): st.write(prompt)
        with col_right:
            with st.chat_message("user"): st.write(prompt)

        # --- PROTECTED SIDE ---
        with col_left:
            if app_mode in ["AI Gateway (OpenAI)", "AI Gateway (Gemini)"]:
                # Pre-check via PS API for redaction, then route through PS Gateway
                safe, check_p, dbg, status = check_security_api(prompt, "prompt")
                if not safe:
                    reply = "🚫 Blocked by Prompt Security"
                    msgs_prot.append({"role": "assistant", "content": reply})
                    with st.chat_message("assistant"): st.write(reply)
                else:
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            res_text, err = get_llm_response(check_p, msgs_prot, use_ps_gateway=True)
                            if err: st.error(f"⚠️ {err}")
                            elif res_text:
                                s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                st.write(s_reply)
                                msgs_prot.append({"role": "assistant", "content": s_reply})
            else:
                safe, check_p, dbg, status = check_security_api(prompt, "prompt")
                if not safe:
                    reply = "🚫 Blocked by Prompt Security"
                    msgs_prot.append({"role": "assistant", "content": reply})
                    with st.chat_message("assistant"): st.write(reply)
                else:
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            res_text, err = get_llm_response(check_p, msgs_prot)
                            if err: st.error(f"⚠️ {err}")
                            elif res_text:
                                s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                st.write(s_reply)
                                msgs_prot.append({"role": "assistant", "content": s_reply})

        # --- UNPROTECTED SIDE (PS fully bypassed) ---
        with col_right:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    res_text, err = get_llm_response(prompt, msgs_unprot, use_ps_gateway=False)
                    if err: st.error(f"⚠️ {err}")
                    elif res_text:
                        st.write(res_text)
                        msgs_unprot.append({"role": "assistant", "content": res_text})

        refresh_metrics()

st.sidebar.markdown('<div class="sidebar-footer">Made by Gastón Z and AI 🤖</div>', unsafe_allow_html=True)
