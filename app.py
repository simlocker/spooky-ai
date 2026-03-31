import streamlit as st
import google.generativeai as genai
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
        # Requires TLS 1.2 minimum
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
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header { background: none !important; border: none !important; }
[data-testid="stHeader"] { background: none !important; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 1.5rem !important; }

[data-testid="stSidebar"] {
    background-color: #614869 !important;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 2rem !important;
    gap: 0.5rem !important;
}

.sidebar-footer {
    position: fixed; bottom: 10px; left: 10px; width: 310px;
    color: #A5B5D1; font-size: 15px; pointer-events: none;
}

[data-testid="stChatInput"] > div {
    background-color: #262730 !important;
    border-radius: 12px !important;
    border: 1px solid transparent !important;
}
[data-testid="stChatInput"]:focus-within > div {
    border: 1px solid #614869 !important;
    box-shadow: 0 0 0 0.1rem rgba(97, 72, 105, 0.2) !important;
}

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

div[data-testid="stChatMessageAvatarBackground"] {
    border-radius: 8px !important;
}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageAvatarBackground"] {
    background-color: #4B0082 !important;
}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageAvatarBackground"] {
    background-color: #614869 !important;
}

div[data-testid="stChatMessage"] {
    background-color: rgba(97, 72, 105, 0.05) !important;
    border: 1px solid rgba(97, 72, 105, 0.2) !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
    padding: 0.5rem 0.8rem !important;
}

div[data-testid="stToastContainer"] {
    bottom: 30px !important;
    right: 30px !important;
    z-index: 9999999 !important;
}

[data-testid="stCheckbox"] label p, [data-testid="stWidgetLabel"] p {
    font-size: 14px !important;
    color: rgb(250, 250, 250) !important;
}

[data-testid="stVerticalBlock"] > div:has(div.fixed-header-container) {
    position: sticky !important;
    top: 0;
    background-color: #0e1117;
    z-index: 1000;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(250, 250, 250, 0.1);
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
    st.session_state.multi_messages = {"AI Gateway (OpenAI)": [], "API (Gemini)": []}
if "session_costs" not in st.session_state:
    st.session_state.session_costs = {"AI Gateway (OpenAI)": 0.0, "API (Gemini)": 0.0}
if "security_stats" not in st.session_state:
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
if "last_latency" not in st.session_state: st.session_state.last_latency = 0
if "last_violation" not in st.session_state: st.session_state.last_violation = "None"
if "current_integration" not in st.session_state: st.session_state.current_integration = "API (Gemini)"
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

def get_chat_models():
    return sorted(set([m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]))

def choose_gemini_model(available_models):
    pref = [os.getenv("DEFAULT_GEMINI_MODEL", "models/gemini-2.0-flash").strip()] + \
           [m.strip() for m in os.getenv("FALLBACK_GEMINI_MODELS", "").split(",") if m.strip()]
    for m in pref:
        if m in available_models: return m
    return available_models[0] if available_models else "Unavailable"

def get_runtime_gemini_candidates(sel, avail):
    cands = [sel] + [os.getenv("DEFAULT_GEMINI_MODEL", "models/gemini-2.0-flash").strip()] + \
            [m.strip() for m in os.getenv("FALLBACK_GEMINI_MODELS", "").split(",") if m.strip()]
    return [m for m in cands if m in avail]

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
    st.divider()
    app_mode = st.radio("Select Prompt Security Integration:", ["API (Gemini)", "AI Gateway (OpenAI)"],
                        index=0 if st.session_state.current_integration == "API (Gemini)" else 1)
    if app_mode != st.session_state.current_integration:
        st.session_state.current_integration, st.session_state.last_debug_info = app_mode, None
        st.rerun()
    user_email = st.text_input("User Identity", value=os.getenv("DEMO_USER_EMAIL", "john.doe@unknown.com"))
    st.divider()

    if app_mode == "AI Gateway (OpenAI)":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key: st.error("🔑 OPENAI_API_KEY missing.")
        else: selected_model = st.selectbox("Select OpenAI Model", ["gpt-4o-mini", "gpt-4o"], index=0)
        st.caption("Mode: AI Gateway (Reverse Proxy)")
        if st.button("💰"): st.session_state.show_cost = not st.session_state.show_cost
    else:
        api_key = os.getenv("GEMINI_FREE_API_KEY")
        if not api_key: st.error("🔑 GEMINI_FREE_API_KEY missing.")
        else:
            try:
                genai.configure(api_key=api_key)
                chat_m = get_chat_models()
                st.session_state.gemini_available_models = chat_m
                auto = get_env_bool("AUTO_SELECT_GEMINI_MODEL", True)
                pref = choose_gemini_model(chat_m)
                if auto: selected_model = pref; st.caption(f"Auto-selected: `{selected_model}`")
                else: 
                    if st.session_state.selected_gemini_model not in chat_m: st.session_state.selected_gemini_model = pref
                    selected_model = st.selectbox("Select Gemini Model", chat_m, index=chat_m.index(st.session_state.selected_gemini_model))
                    st.session_state.selected_gemini_model = selected_model
            except Exception as e: st.error(str(e))
        st.caption("Mode: API Integration")
        debug_mode = st.checkbox("Show Debug Info", value=False)
    
    sidebar_metrics = st.empty()

def refresh_metrics():
    with sidebar_metrics.container():
        if app_mode == "AI Gateway (OpenAI)":
            if st.session_state.show_cost: st.info(f"**Total Spend:** ${st.session_state.session_costs['AI Gateway (OpenAI)']:,.6f}")
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

# SECURITY LOGIC (FIXED WITH SESSION ADAPTER)
def check_security_api(text, context_type="prompt"):
    if not ps_enabled: return True, text, {"status": "Bypassed"}, "safe"
    try:
        headers = {"Content-Type": "application/json", "APP-ID": PS_APP_ID}
        # FIX: Using persistent session with TLS Adapter
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

# CHAT DISPLAY
last_idx = -1
for i, m in enumerate(st.session_state.multi_messages[app_mode]):
    if m["role"] == "user": last_idx = i

debug_ph = None
for i, m in enumerate(st.session_state.multi_messages[app_mode]):
    with st.chat_message(m["role"]): st.write(m["content"])
    if i == last_idx:
        debug_ph = st.empty()
        if app_mode == "API (Gemini)" and debug_mode and st.session_state.last_debug_info:
            info = st.session_state.last_debug_info
            if info.get('original_p') == m["content"]:
                with debug_ph.container(): render_debug_box(info)

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
        st.session_state.multi_messages[app_mode].append({"role": "user", "content": full_p})
        with st.chat_message("user"):
            st.write(full_p); 
            if img: st.image(img, width=300)
        
        if app_mode == "AI Gateway (OpenAI)":
            base = f"{PS_GATEWAY_URL.strip('/')}/v1" if ps_enabled else "https://api.openai.com/v1"
            client = OpenAI(base_url=base, api_key=api_key, default_headers={"ps-app-id": PS_APP_ID, "forward-domain": "api.openai.com", "user": user_email} if ps_enabled else {})
            with st.chat_message("assistant"):
                try:
                    r = client.chat.completions.create(model=selected_model, messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.multi_messages[app_mode]])
                    u = r.usage
                    if u:
                        rate = 0.15 if "mini" in selected_model else 2.50
                        st.session_state.session_costs["AI Gateway (OpenAI)"] += (u.prompt_tokens * rate / 10**6) + (u.completion_tokens * rate*4 / 10**6)
                    reply = r.choices[0].message.content; st.write(reply)
                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": reply}); refresh_metrics()
                except Exception as e: st.error(str(e))
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
                            cont = [check]; 
                            if img: cont.append(img)
                            hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in st.session_state.multi_messages[app_mode][:-1]]
                            res = None
                            for mname in get_runtime_gemini_candidates(selected_model, st.session_state.gemini_available_models):
                                try: res = genai.GenerativeModel(mname).start_chat(history=hist).send_message(cont); break
                                except: continue
                            s_safe, s_reply, s_dbg, s_status = check_security_api(res.text, "response")
                            st.write(s_reply); st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": s_reply})
                            if s_status in ["redacted", "blocked"]:
                                st.session_state.last_debug_info = {"checked_p": s_reply, "original_p": res.text, "debug": s_dbg, "status_type": s_status}
                                if debug_mode: render_debug_box(st.session_state.last_debug_info)
                            refresh_metrics()
                        except Exception as e: st.error(str(e))

st.sidebar.markdown('<div class="sidebar-footer">Made by Gastón Z and AI 🤖</div>', unsafe_allow_html=True)
