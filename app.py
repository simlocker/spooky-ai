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

if "multi_messages" not in st.session_state:
    st.session_state.multi_messages = {"AI Gateway (OpenAI)": [], "API (Gemini)": [], "API (Groq)": []}
if "session_costs" not in st.session_state:
    st.session_state.session_costs = {"AI Gateway (OpenAI)": 0.0, "API (Gemini)": 0.0, "API (Groq)": 0.0}
if "security_stats" not in st.session_state:
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
if "last_latency" not in st.session_state: st.session_state.last_latency = 0
if "last_violation" not in st.session_state: st.session_state.last_violation = "None"
if "current_integration" not in st.session_state: st.session_state.current_integration = "API (Groq)"
if "show_cost" not in st.session_state: st.session_state.show_cost = False
if "input_text" not in st.session_state: st.session_state.input_text = None
if "last_debug_info" not in st.session_state: st.session_state.last_debug_info = None
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

# Helper generator functions for LLM API calls
def generate_gemini_response(genai_client, model_sel, chat_history, current_prompt, img_obj=None):
    contents = []
    for m in chat_history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    
    current_parts = [types.Part.from_text(text=current_prompt)]
    if img_obj: current_parts.append(img_obj)
    contents.append(types.Content(role="user", parts=current_parts))

    for mname in get_runtime_gemini_candidates(model_sel, st.session_state.gemini_available_models):
        try:
            res = genai_client.models.generate_content(model=mname, contents=contents)
            if res and res.text: return res.text
        except Exception as e:
            if "429" in str(e): continue
            else: raise e
    return None

def generate_groq_response(api_key_str, model_sel, chat_history, current_prompt):
    groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key_str)
    messages_payload = [{"role": m["role"], "content": m["content"]} for m in chat_history]
    messages_payload.append({"role": "user", "content": current_prompt})

    chat_completion = groq_client.chat.completions.create(
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

    # Integration Method Selection
    integration_method = st.radio("Integration Method:", ["API", "AI Gateway"], index=0)

    if integration_method == "AI Gateway":
        app_mode = "AI Gateway (OpenAI)"
    else:
        provider = st.selectbox("Provider:", ["Groq", "Gemini"], index=0)
        app_mode = f"API ({provider})"

    if app_mode != st.session_state.current_integration:
        st.session_state.current_integration, st.session_state.last_debug_info = app_mode, None
        st.rerun()

    user_email = st.text_input("User Identity", value=os.getenv("DEMO_USER_EMAIL", "john.doe@unknown.com"))
    st.divider()

    # Dynamic Model Selector based on explicitly derived app_mode
    if app_mode == "AI Gateway (OpenAI)":
        api_key = os.getenv("OPENAI_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 OPENAI_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
        else:
            selected_model = st.selectbox("Select OpenAI Model", ["gpt-4o-mini", "gpt-4o"], index=0)
        st.caption("Mode: AI Gateway (Reverse Proxy)")
        if st.button("💰"): st.session_state.show_cost = not st.session_state.show_cost

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
        debug_mode = st.checkbox("Show Debug Info", value=False)
        #st.info("💡 Groq is highly recommended for users hitting Gemini rate limits.")

    elif app_mode == "API (Gemini)":
        api_key = os.getenv("GEMINI_FREE_API_KEY")
        if not is_valid_key(api_key):
            st.error("🔑 GEMINI_FREE_API_KEY is missing or a placeholder.")
            selected_model = "Unavailable"
            debug_mode = False
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
        st.caption(f"Mode: **{app_mode}** | Model: **{selected_model}**\n\nSecurity: {c}[**{t}**] | ID: **{disp_id}**")
    with col_u:
        st.markdown('<div class="header-upload-btn">', unsafe_allow_html=True)
        with st.popover("➕ Upload"):
            uploaded_file = st.file_uploader("Scan File", type=["txt", "pdf", "png", "jpg"], label_visibility="collapsed", key=f"f_{st.session_state.uploader_key}")
        st.markdown('</div>', unsafe_allow_html=True)

if selected_model in ["Unavailable", "Connection Error"]:
    st.warning(f"⚠️ **{app_mode} is not properly configured.**\n\nPlease add a valid API key to your `.env` file and restart Docker, or select a different integration.")

# SECURITY LOGIC
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

# CHAT DISPLAY (Supports Standard + Side-by-Side turn rendering)
debug_ph = None
messages_list = st.session_state.multi_messages[app_mode]

for i, m in enumerate(messages_list):
    if m.get("role") == "side_by_side":
        with st.chat_message("user"):
            st.write(m["user_prompt"])
        c_prot, c_unprot = st.columns(2)
        with c_prot:
            st.markdown("#### 🛡️ Protected Mode")
            st.write(m["protected_response"])
        with c_unprot:
            st.markdown("#### ⚠️ Unprotected Mode")
            st.write(m["unprotected_response"])
    else:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if i == len(messages_list) - 1 and "API" in app_mode and debug_mode and st.session_state.last_debug_info:
        debug_ph = st.empty()
        with debug_ph.container():
            render_debug_box(st.session_state.last_debug_info)

# CHAT INPUT & PROCESSING
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
                    reply = r.choices[0].message.content; st.write(reply)
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

                # LEFT COLUMN: PROTECTED
                with col_prot:
                    st.markdown("#### 🛡️ Protected Mode")
                    safe, check, dbg, status = check_security_api(full_p, "prompt")
                    st.session_state.last_debug_info = {"checked_p": check, "original_p": full_p, "debug": dbg, "status_type": status}
                    if debug_mode: render_debug_box(st.session_state.last_debug_info)

                    if not safe:
                        protected_final = "🚫 Prompt Blocked by Policy"
                        st.error(protected_final)
                    else:
                        with st.spinner("Generating protected output..."):
                            try:
                                if app_mode == "API (Gemini)":
                                    res_text = generate_gemini_response(st.session_state.genai_client, selected_model, history, check, img)
                                elif app_mode == "API (Groq)":
                                    if img: st.warning("🖼️ Image uploads are not supported by Groq.")
                                    res_text = generate_groq_response(api_key, selected_model, history, check)
                                
                                if res_text:
                                    s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                    protected_final = s_reply
                                    st.write(protected_final)
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
                            
                            if raw_res:
                                unprotected_final = raw_res
                                st.write(unprotected_final)
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
                    "unprotected_response": unprotected_final
                })
                refresh_metrics()

            else:
                # SINGLE STANDARD VIEW
                st.session_state.multi_messages[app_mode].append({"role": "user", "content": full_p})
                with st.chat_message("user"):
                    st.write(full_p)
                    if img: st.image(img, width=300)

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
                                    res_text = generate_gemini_response(st.session_state.genai_client, selected_model, history, check, img)
                                elif app_mode == "API (Groq)":
                                    if img: st.warning("🖼️ Image uploads are not currently supported by Groq text models. Ignoring image.")
                                    res_text = generate_groq_response(api_key, selected_model, history, check)

                                if res_text:
                                    s_safe, s_reply, s_dbg, s_status = check_security_api(res_text, "response")
                                    st.write(s_reply)
                                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": s_reply})
                                    if s_status in ["redacted", "blocked"]:
                                        st.session_state.last_debug_info = {"checked_p": s_reply, "original_p": res_text, "debug": s_dbg, "status_type": s_status}
                                        if debug_mode: render_debug_box(st.session_state.last_debug_info)
                                else:
                                    st.error("🚨 Rate limit exceeded (429) or no models available. Please wait 60 seconds.")

                                refresh_metrics()
                            except Exception as e:
                                if "401" in str(e): st.error(f"🚫 Auth Error: Your {app_mode} Key is invalid.")
                                else: st.error(f"⚠️ Error: {str(e)[:200]}...")

st.sidebar.markdown('<div class="sidebar-footer">Made by Gastón Z and AI 🤖</div>', unsafe_allow_html=True)
