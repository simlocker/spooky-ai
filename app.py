import streamlit as st
from google import genai
from google.genai import types
from openai import OpenAI
import requests
import os
import pypdf
import openpyxl
import random
import json
import ssl
import re
import time
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

# Optional: pin a specific named Policy (Homegrown Apps > Policies > "Manage Policies")
# instead of silently relying on whichever policy the console has marked as this
# connector's "Default Homegrown App Policy". Leave blank to use the default.
PS_POLICY_NAME = os.getenv("PS_POLICY_NAME", "").strip()

# ==========================================================
# --- CUSTOM USER-FACING SECURITY MESSAGES ---
# Unlike Prompt Security's Employees browser extension (fixed pop-up copy) or the
# Agentic AI block message (400-char field in the console), THIS app is our own
# frontend calling /api/protect directly — so we fully control what the user sees.
# Edit these freely to match whatever narrative/demo script you're running.
# ==========================================================
CUSTOM_MESSAGES = {
    "blocked_prompt": (
        "🚫 **Este contenido no puede enviarse a la IA.**\n\n"
        "Se detectó información confidencial (datos personales sensibles, historial médico, o afines) "
        "en tu mensaje o archivo adjunto.\n\n"
        "El envío no está permitido según la política corporativa. "
        "Puede reformular la consulta eliminando datos de cliente, importes, márgenes "
        "o información personal antes de continuar."
    ),
    "redacted_notice": (
        "⚠️ Se detectó y redactó información sensible en tu mensaje o archivo antes de continuar."
    ),
    "security_check_error": (
        "❌ **No se pudo verificar este contenido con el servicio de seguridad** (error del backend). "
        "El contenido se envió sin inspección completa — trátalo como no verificado."
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

if "multi_messages" not in st.session_state:
    st.session_state.multi_messages = {"AI Gateway (OpenAI)": [], "API (Gemini)": [], "API (Groq)": [], "API (Cohere)": [], "API (OpenRouter)": []}
if "session_costs" not in st.session_state:
    st.session_state.session_costs = {"AI Gateway (OpenAI)": 0.0, "API (Gemini)": 0.0, "API (Groq)": 0.0, "API (Cohere)": 0.0, "API (OpenRouter)": 0.0}
if "security_stats" not in st.session_state:
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
if "last_latency" not in st.session_state: st.session_state.last_latency = 0
if "last_violation" not in st.session_state: st.session_state.last_violation = "None"
if "current_integration" not in st.session_state: st.session_state.current_integration = "API (Groq)"
if "show_cost" not in st.session_state: st.session_state.show_cost = False
if "input_text" not in st.session_state: st.session_state.input_text = None
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "last_processed_file" not in st.session_state: st.session_state.last_processed_file = None
if "gemini_available_models" not in st.session_state: st.session_state.gemini_available_models = []
if "selected_gemini_model" not in st.session_state: st.session_state.selected_gemini_model = None

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
    if not key: return False
    k_lower = key.lower()
    if "your" in k_lower or "key" in k_lower or "here" in k_lower or len(key) < 10: return False
    return True

def get_api_history(chat_history):
    """Converts mixed chat session history into OpenAI/Gemini compliant multi-turn history."""
    clean_history = []
    for item in chat_history:
        if item.get("role") == "side_by_side":
            clean_history.append({"role": "user", "content": item["user_prompt"]})
            clean_history.append({"role": "assistant", "content": item["protected_response"]})
        elif "role" in item and "content" in item:
            clean_history.append({"role": item["role"], "content": item["content"]})
    return clean_history

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

# Helper generator functions for LLM API calls
def generate_gemini_response(genai_client, model_sel, chat_history, current_prompt, img_obj=None):
    contents = []
    for m in chat_history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    
    current_parts = [types.Part.from_text(text=current_prompt)]
    if img_obj: current_parts.append(img_obj)
    contents.append(types.Content(role="user", parts=current_parts))

    gen_config = types.GenerateContentConfig(system_instruction=REDACTION_SYSTEM_NOTE)
    for mname in get_runtime_gemini_candidates(model_sel, st.session_state.gemini_available_models):
        try:
            res = genai_client.models.generate_content(model=mname, contents=contents, config=gen_config)
            if res and res.text: return res.text
        except Exception as e:
            if "429" in str(e): continue
            else: raise e
    return None

def generate_groq_response(api_key_str, model_sel, chat_history, current_prompt):
    groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key_str)
    messages_payload = [{"role": "system", "content": REDACTION_SYSTEM_NOTE}]
    messages_payload += [{"role": m["role"], "content": m["content"]} for m in chat_history]
    messages_payload.append({"role": "user", "content": current_prompt})

    chat_completion = groq_client.chat.completions.create(
        messages=messages_payload,
        model=model_sel
    )
    return chat_completion.choices[0].message.content

# Cohere publishes an OpenAI-SDK-compatible endpoint (the "Compatibility API"),
# so — like Groq above — this reuses the openai package instead of adding the
# separate `cohere` dependency. Verify this base URL against Cohere's current
# docs if it stops working; compatibility-layer paths occasionally move.
def generate_cohere_response(api_key_str, model_sel, chat_history, current_prompt):
    cohere_client = OpenAI(base_url="https://api.cohere.ai/compatibility/v1", api_key=api_key_str)
    messages_payload = [{"role": "system", "content": REDACTION_SYSTEM_NOTE}]
    messages_payload += [{"role": m["role"], "content": m["content"]} for m in chat_history]
    messages_payload.append({"role": "user", "content": current_prompt})

    chat_completion = cohere_client.chat.completions.create(
        messages=messages_payload,
        model=model_sel
    )
    return chat_completion.choices[0].message.content

# OpenRouter's native API is OpenAI-SDK compatible too. The extra headers are
# optional (OpenRouter uses them only for its public leaderboard attribution),
# but harmless to include.
def generate_openrouter_response(api_key_str, model_sel, chat_history, current_prompt):
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key_str,
        default_headers={"HTTP-Referer": "https://spooky-ai.local", "X-Title": "Spooky AI"}
    )
    messages_payload = [{"role": "system", "content": REDACTION_SYSTEM_NOTE}]
    messages_payload += [{"role": m["role"], "content": m["content"]} for m in chat_history]
    messages_payload.append({"role": "user", "content": current_prompt})

    chat_completion = openrouter_client.chat.completions.create(
        messages=messages_payload,
        model=model_sel
    )
    return chat_completion.choices[0].message.content

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

    st.markdown("### Protection Layer")
    ps_enabled = st.toggle("Enable Prompt Security", value=True)
    side_by_side = st.toggle("🔀 Side-by-side Comparison", value=False)
    st.divider()

    user_email = st.text_input("User Identity", value=os.getenv("DEMO_USER_EMAIL", "john.doe@unknown.com"))
    st.divider()

    # Integration Method Selection
    integration_method = st.radio("Integration Method:", ["API", "AI Gateway"], index=0)

    if integration_method == "AI Gateway":
        app_mode = "AI Gateway (OpenAI)"
    else:
        provider = st.selectbox("Provider:", ["Groq", "Gemini", "Cohere", "OpenRouter"], index=0)
        app_mode = f"API ({provider})"

    if app_mode != st.session_state.current_integration:
        st.session_state.current_integration = app_mode
        st.rerun()

    # Dynamic Model Selector based on explicitly derived app_mode — placed
    # immediately after the Provider dropdown above, since choosing a model
    # is a direct continuation of choosing a provider (Gemini has no manual
    # selector, but its "Auto-selected: ..." caption lands here too, for the
    # same reason).
    if app_mode == "AI Gateway (OpenAI)":
        api_key = os.getenv("OPENAI_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 OPENAI_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = st.selectbox("Select OpenAI Model", ["gpt-4o-mini", "gpt-4o"], index=0)
        st.caption("Mode: AI Gateway (Reverse Proxy)")
        if st.button("💰"): st.session_state.show_cost = not st.session_state.show_cost
        # Gateway mode protects traffic transparently via the reverse proxy —
        # there's no local prompt/response check to show debug info for, but
        # both flags must still exist so the shared history-replay loop below
        # doesn't hit a NameError when it checks them for this mode's messages.
        debug_prompt, debug_response = False, False

    elif app_mode == "API (Groq)":
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
        st.caption("Mode: API Integration")
        dbg_col1, dbg_col2 = st.columns(2)
        debug_prompt = dbg_col1.checkbox("🔎 Prompt Debug", value=False)
        debug_response = dbg_col2.checkbox("🔎 Response Debug", value=False)
        #st.info("💡 Groq is highly recommended for users hitting Gemini rate limits.")

    elif app_mode == "API (Gemini)":
        api_key = os.getenv("GEMINI_FREE_API_KEY")
        # Default both to False up front — this also fixes a pre-existing gap
        # where a Gemini auth failure ("Connection Error") left debug_mode
        # completely undefined (only the invalid-key path set it), which
        # would have raised a NameError as soon as the history loop below
        # tried to check it.
        debug_prompt, debug_response = False, False
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
            dbg_col1, dbg_col2 = st.columns(2)
            debug_prompt = dbg_col1.checkbox("🔎 Prompt Debug", value=False)
            debug_response = dbg_col2.checkbox("🔎 Response Debug", value=False)

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
        st.caption("Mode: API Integration")
        dbg_col1, dbg_col2 = st.columns(2)
        debug_prompt = dbg_col1.checkbox("🔎 Prompt Debug", value=False)
        debug_response = dbg_col2.checkbox("🔎 Response Debug", value=False)

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
        st.caption("Mode: API Integration")
        dbg_col1, dbg_col2 = st.columns(2)
        debug_prompt = dbg_col1.checkbox("🔎 Prompt Debug", value=False)
        debug_response = dbg_col2.checkbox("🔎 Response Debug", value=False)

    sidebar_metrics = st.empty()

def refresh_metrics():
    with sidebar_metrics.container():
        if "AI Gateway" in app_mode:
            if st.session_state.show_cost: st.info(f"**Total Spend:** ${st.session_state.session_costs[app_mode]:,.6f}")
        else:
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
        policy_disp = PS_POLICY_NAME if PS_POLICY_NAME else "(connector default)"
        st.caption(f"Mode: **{app_mode}** | Model: **{selected_model}**\n\nSecurity: {c}[**{t}**] | ID: **{disp_id}** | Policy: **{policy_disp}**")
    with col_u:
        st.markdown('<div class="header-upload-btn">', unsafe_allow_html=True)
        with st.popover("➕ Upload"):
            uploaded_file = st.file_uploader("Scan File", type=["txt", "pdf", "png", "jpg", "xlsx"], label_visibility="collapsed", key=f"f_{st.session_state.uploader_key}")
        st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    st.caption(f"📎 Archivo adjunto y listo: **{uploaded_file.name}** — escribí tu mensaje abajo y presioná Enter para enviarlo junto con el archivo.")

if selected_model in ["Unavailable", "Connection Error"]:
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
        with c_unprot:
            st.markdown("#### ⚠️ Unprotected Mode")
            render_answer(m["unprotected_response"])
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
chat_v = st.chat_input("How can I help you safely?")
prompt = st.session_state.input_text if st.session_state.input_text else chat_v
st.session_state.input_text = None

if prompt and selected_model not in ["Unavailable", "Connection Error"]:
    ctx, img = "", None
    if uploaded_file:
        t = uploaded_file.type; uploaded_file.seek(0)
        if "text" in t or "csv" in t: ctx = f"\n\n[File: {uploaded_file.name}]\n{uploaded_file.read().decode('utf-8', errors='ignore')}"
        elif "pdf" in t:
            try:
                raw_pdf_text = "".join([p.extract_text() or "" for p in pypdf.PdfReader(uploaded_file).pages])
                ctx = f"\n\n[PDF: {uploaded_file.name}]\n" + normalize_pdf_text(raw_pdf_text)
            except: ctx = "\n[PDF Error]"
        elif "image" in t:
            try: img = Image.open(uploaded_file); ctx = f"\n\n[Image: {uploaded_file.name}]"
            except: pass
        elif "spreadsheet" in t or "excel" in t:
            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                sheet_texts = []
                for ws in wb.worksheets:
                    lines = [f"--- Sheet: {ws.title} ---"]
                    for row in ws.iter_rows(values_only=True):
                        if any(cell is not None for cell in row):
                            lines.append(" | ".join("" if c is None else str(c) for c in row))
                    sheet_texts.append("\n".join(lines))
                ctx = f"\n\n[XLSX: {uploaded_file.name}]\n" + "\n\n".join(sheet_texts)
            except Exception as e:
                ctx = f"\n[XLSX Error: {e}]"
        # The file has been consumed for this message — reset the uploader
        # widget so it doesn't silently get re-attached to the next message.
        st.session_state.uploader_key += 1

    full_p = f"{prompt if prompt else ''} {ctx}".strip()
    if full_p or img:
        # --- OPENAI GATEWAY METHOD ---
        if app_mode == "AI Gateway (OpenAI)":
            st.session_state.multi_messages[app_mode].append({"role": "user", "content": full_p})
            with st.chat_message("user"):
                st.write(full_p)
                if img: st.image(img, width=300)

            base_url = f"{PS_GATEWAY_URL.strip('/')}/v1" if ps_enabled else "https://api.openai.com/v1"
            client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                default_headers={"ps-app-id": PS_APP_ID, "forward-domain": "api.openai.com", "user": user_email} if ps_enabled else {}
            )
            with st.chat_message("assistant"):
                try:
                    r = client.chat.completions.create(
                        model=selected_model, 
                        messages=get_api_history(st.session_state.multi_messages[app_mode])
                    )
                    u = r.usage
                    if u:
                        rate = 0.15 if "mini" in selected_model else 2.50
                        st.session_state.session_costs["AI Gateway (OpenAI)"] += (u.prompt_tokens * rate / 10**6) + (u.completion_tokens * rate*4 / 10**6)
                    reply = r.choices[0].message.content; render_answer(reply)
                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": reply}); refresh_metrics()
                except Exception as e:
                    if "401" in str(e): st.error(f"🚫 Auth Error: Your {app_mode} Key is invalid or you forgot to restart Docker after editing .env.")
                    else: st.error(f"⚠️ Error: {str(e)[:200]}...")

        # --- API METHOD (GEMINI & GROQ) ---
        else:
            history = get_api_history(st.session_state.multi_messages[app_mode])

            if side_by_side:
                with st.chat_message("user"):
                    st.write(full_p)
                    if img: st.image(img, width=300)

                col_prot, col_unprot = st.columns(2)
                protected_final = ""
                unprotected_final = ""
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
                        protected_final = CUSTOM_MESSAGES["blocked_prompt"]
                        st.error(protected_final)
                    else:
                        with st.spinner("Generating protected output..."):
                            try:
                                if app_mode == "API (Gemini)":
                                    res_text = generate_gemini_response(st.session_state.genai_client, selected_model, history, check, img)
                                elif app_mode == "API (Groq)":
                                    if img: st.warning("🖼️ Image uploads are not supported by Groq.")
                                    res_text = generate_groq_response(api_key, selected_model, history, check)
                                elif app_mode == "API (Cohere)":
                                    if img: st.warning("🖼️ Image uploads are not supported by Cohere in this app.")
                                    res_text = generate_cohere_response(api_key, selected_model, history, check)
                                elif app_mode == "API (OpenRouter)":
                                    if img: st.warning("🖼️ Image uploads are not supported by OpenRouter in this app.")
                                    res_text = generate_openrouter_response(api_key, selected_model, history, check)
                                
                                if res_text:
                                    # IMPORTANT: this response-level check is what actually catches
                                    # PII the model echoes back (e.g. an email address repeated in
                                    # its answer). Its status must be surfaced — previously it was
                                    # computed but discarded, which is why the UI could show "Safe"
                                    # even while the response was being redacted underneath.
                                    s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                    turn_debug["response_check"] = {"checked_p": s_reply, "original_p": res_text, "debug": s_dbg, "status_type": s_status}
                                    protected_final = s_reply
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
                                protected_final = f"⚠️ Error: {str(e)[:150]}"
                                st.error(protected_final)

                # RIGHT COLUMN: UNPROTECTED (Raw input)
                with col_unprot:
                    st.markdown("#### ⚠️ Unprotected Mode")
                    with st.spinner("Generating raw output..."):
                        try:
                            if app_mode == "API (Gemini)":
                                raw_res = generate_gemini_response(st.session_state.genai_client, selected_model, history, full_p, img)
                            elif app_mode == "API (Groq)":
                                raw_res = generate_groq_response(api_key, selected_model, history, full_p)
                            elif app_mode == "API (Cohere)":
                                raw_res = generate_cohere_response(api_key, selected_model, history, full_p)
                            elif app_mode == "API (OpenRouter)":
                                raw_res = generate_openrouter_response(api_key, selected_model, history, full_p)
                            
                            if raw_res:
                                unprotected_final = raw_res
                                render_answer(unprotected_final)
                            else:
                                unprotected_final = "No response generated."
                                st.error(unprotected_final)
                        except Exception as e:
                            unprotected_final = f"⚠️ Error: {str(e)[:150]}"
                            st.error(unprotected_final)

                # Append whole side-by-side snapshot into session memory
                st.session_state.multi_messages[app_mode].append({
                    "role": "side_by_side",
                    "user_prompt": full_p,
                    "protected_response": protected_final,
                    "unprotected_response": unprotected_final,
                    "debug": turn_debug,
                    "notices": turn_notices
                })
                refresh_metrics()

            else:
                # SINGLE STANDARD VIEW
                st.session_state.multi_messages[app_mode].append({"role": "user", "content": full_p})
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

                if not safe:
                    m = CUSTOM_MESSAGES["blocked_prompt"]
                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": m, "debug": turn_debug, "notices": turn_notices})
                    with st.chat_message("assistant"):
                        render_answer(m)
                else:
                    res_text, gen_error = None, None
                    with st.spinner("Thinking..."):
                        try:
                            if app_mode == "API (Gemini)":
                                res_text = generate_gemini_response(st.session_state.genai_client, selected_model, history, check, img)
                            elif app_mode == "API (Groq)":
                                if img: st.warning("🖼️ Image uploads are not currently supported by Groq text models. Ignoring image.")
                                res_text = generate_groq_response(api_key, selected_model, history, check)
                            elif app_mode == "API (Cohere)":
                                if img: st.warning("🖼️ Image uploads are not currently supported by Cohere in this app. Ignoring image.")
                                res_text = generate_cohere_response(api_key, selected_model, history, check)
                            elif app_mode == "API (OpenRouter)":
                                if img: st.warning("🖼️ Image uploads are not currently supported by OpenRouter in this app. Ignoring image.")
                                res_text = generate_openrouter_response(api_key, selected_model, history, check)
                        except Exception as e:
                            gen_error = e

                    if gen_error is not None:
                        if "401" in str(gen_error): st.error(f"🚫 Auth Error: Your {app_mode} Key is invalid.")
                        else: st.error(f"⚠️ Error: {str(gen_error)[:200]}...")
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

                        st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": s_reply, "debug": turn_debug, "notices": turn_notices})
                    else:
                        st.error("🚨 Rate limit exceeded (429) or no models available. Please wait 60 seconds.")

                    refresh_metrics()

st.sidebar.markdown('<div class="sidebar-footer">Made by Gastón Z and AI 🤖</div>', unsafe_allow_html=True)
