import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import requests
import os
import pypdf
import random
import json
from PIL import Image

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

/* 3. Chat Input Cleanup */
[data-testid="stChatInput"] > div {
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
div.header-upload-btn button:hover {
    background-color: #4B0082 !important;
    border-color: #9370DB !important;
}

/* 5. CHAT BUBBLES (Purple Theme - Compact Version) */
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

div[data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {
    gap: 0rem !important;
}

/* 6. TOAST NOTIFICATIONS */
div[data-testid="stToastContainer"] {
    visibility: visible !important;
    width: auto !important;
    height: auto !important;
    position: fixed !important;
    top: unset !important;
    bottom: 30px !important;
    right: 30px !important;
    left: unset !important;
    z-index: 9999999 !important;
}

/* 7. CUSTOMIZE CHECKBOX */
[data-testid="stCheckbox"] label p {
    font-size: 14px !important;
    color: rgb(250, 250, 250) !important;
    font-weight: 400 !important;
}

/* 8. MAIN TITLE STYLING */
h1 {
    font-size: 2.5rem !important;
    padding-top: 0rem !important;
}

/* 9. PINNED HEADER LOGIC */
[data-testid="stVerticalBlock"] > div:has(div.fixed-header-container) {
    position: sticky !important;
    top: 0;
    background-color: #0e1117;
    z-index: 1000;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(250, 250, 250, 0.1);
}

/* 10. HIDE STREAMLIT BRANDING */
[data-testid="stStatusWidget"] {
    visibility: hidden;
    display: none !important;
}
#stAppViewContainer > section:nth-child(2) > div:nth-child(1) {
    display: none !important;
}
footer {
    display: none !important;
}
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================================
# --- PROMPT SECURITY GLOBALS ---
# ==========================================================
PS_APP_ID = os.getenv("PS_APP_ID")
# User now provides the base Gateway URL in .env
PS_GATEWAY_URL = os.getenv("PS_GATEWAY_URL")

if not PS_APP_ID or not PS_GATEWAY_URL:
    st.error("🚨 Critical Error: PS_APP_ID or PS_GATEWAY_URL is missing. Please check your .env file.")
    st.stop()

# Dynamically construct the Protect API endpoint
# .strip("/") ensures we don't end up with double slashes if the user includes one
PS_PROTECT_API = f"{PS_GATEWAY_URL.strip('/')}/api/protect"

# ==========================================================
# --- INITIALIZE SESSION STATES ---
# ==========================================================
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

# ==========================================================
# --- HELPERS ---
# ==========================================================
def reset_chat():
    mode = st.session_state.current_integration
    st.session_state.multi_messages[mode] = []
    st.session_state.security_stats = {"blocks": 0, "redactions": 0}
    st.session_state.last_latency = 0
    st.session_state.last_violation = "None"
    st.session_state.session_costs[mode] = 0.0
    st.session_state.last_debug_info = None
    st.session_state.uploader_key += 1
    st.session_state.last_processed_file = None
    st.toast("History cleared.")

def set_prompt(text):
    st.session_state.input_text = text

def render_debug_box(info):
    if not info: return
    status_type = info.get('status_type', 'safe')
    checked_p = info.get('checked_p', '')
    debug_data = info.get('debug', {})
    
    # Label Logic
    if status_type == "blocked":
        label, state = "🚫 Violation Detected", "error"
        content = None
    elif status_type == "redacted":
        # Force the label to show Redacted if status_type indicates it
        label, state = "⚠️ Content Redacted", "complete" 
        content = f"Redacted Content: {checked_p}"
    else:
        label, state = "✅ Safe", "complete"
        content = None

    with st.status(label, expanded=False, state=state):
        if content: st.warning(content)
        with st.expander("🔍 View Raw API Response", expanded=False):
            st.json(debug_data)

# ==========================================================
# --- SIDEBAR ---
# ==========================================================
with st.sidebar:
    st.header("App Settings")
    st.button("🗑️ Clear Current Chat", use_container_width=True, on_click=reset_chat)

    # 1. Load triggers dynamically
    trigger_data = {}
    try:
        with open("triggers.txt", "r") as f:
            trigger_data = json.load(f)
    except Exception as e:
        st.sidebar.warning("⚠️ triggers.txt issue. Rebuild Docker or check JSON format.")
        # Fallback structure to prevent crash if file is broken
        trigger_data = {"System": {"Error": ["Check triggers.txt file"]}}

    # 2. Dynamic Popover Generation
    with st.popover("💡 Triggers", use_container_width=True):
        col_t, col_r = st.columns([0.7, 0.3])
        col_t.markdown("### Sample Prompts")
        if col_r.button("🔄", help="Reload triggers.txt"):
            st.rerun()

        # Iterate over Top-Level Groups (e.g., "Sensitive Data", "Secrets")
        for group_name, sub_items in trigger_data.items():
            # Check if this entry contains sub-items (buttons) or is just a flat list
            if isinstance(sub_items, dict):
                st.markdown(f"**{group_name}**")
                
                # Get all button names in this group
                btn_names = list(sub_items.keys())
                
                # Create rows with 2 columns each
                for i in range(0, len(btn_names), 2):
                    cols = st.columns(2)
                    # Loop for the 2 columns (left and right)
                    for j in range(2):
                        if i + j < len(btn_names):
                            btn_label = btn_names[i+j]
                            prompt_list = sub_items[btn_label]
                            
                            # Render the button
                            with cols[j]:
                                if st.button(
                                    btn_label, 
                                    use_container_width=True, 
                                    # Unique key is essential for buttons generated in loops
                                    key=f"trig_{group_name}_{btn_label}"
                                ):
                                    set_prompt(random.choice(prompt_list))
            
            elif isinstance(sub_items, list):
                # Handle legacy flat lists if any exist (e.g. if you didn't nest them)
                if st.button(group_name, use_container_width=True, key=f"trig_flat_{group_name}"):
                    set_prompt(random.choice(sub_items))

    st.divider()
    app_mode = st.radio("Select Prompt Security Integration:", ["API (Gemini)", "AI Gateway (OpenAI)"],
                        index=0 if st.session_state.current_integration == "API (Gemini)" else 1)

    if app_mode != st.session_state.current_integration:
        st.session_state.current_integration = app_mode
        st.session_state.last_debug_info = None
        st.rerun()

    user_email = st.text_input("User Identity", value=os.getenv("DEMO_USER_EMAIL", "john.doe@unknown.com"))
    st.divider()

    if app_mode == "AI Gateway (OpenAI)":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("🔑 OPENAI_API_KEY is missing in .env")
            selected_model = "Unavailable"
        else:
            selected_model = st.selectbox("Select OpenAI Model", ["gpt-4o-mini", "gpt-4o"], index=0)
        st.caption("Mode: AI Gateway (Reverse Proxy)")
        if st.button("💰"): st.session_state.show_cost = not st.session_state.show_cost
        sidebar_metrics_container = st.empty()
    else:
        api_key = os.getenv("GEMINI_FREE_API_KEY")
        if not api_key:
            st.error("🔑 GEMINI_FREE_API_KEY is missing in .env")
            selected_model = "Unavailable"
            debug_mode = False
        else:
            try:
                genai.configure(api_key=api_key)
                chat_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
                default_ix = next((i for i, name in enumerate(chat_models) if "gemini-2.0-flash" in name), 0)
                selected_model = st.selectbox("Select Gemini Model (Free Tier)", chat_models, index=default_ix)
            except Exception as e:
                st.error(f"⚠️ Gemini Connection Failed: {str(e)}")
                selected_model = "Connection Error"
        st.caption("Mode: API Integration")
        debug_mode = st.checkbox("Show Debug Info", value=False)
        st.divider()
        sidebar_metrics_container = st.empty()

def refresh_metrics():
    with sidebar_metrics_container.container():
        if app_mode == "AI Gateway (OpenAI)":
            if st.session_state.show_cost:
                cost = st.session_state.session_costs["AI Gateway (OpenAI)"]
                st.info(f"**Total Approximate Spend:** ${cost:,.6f}")
        else:
            with st.expander("Session Stats [beta]", expanded=False):
                c1, c2 = st.columns(2)
                c1.metric("Blocks", st.session_state.security_stats["blocks"])
                c2.metric("Redactions", st.session_state.security_stats["redactions"])
                st.caption(f"⚡ Latency: {st.session_state.last_latency} ms")
                st.caption(f"🚫 Violation: {st.session_state.last_violation}")

refresh_metrics()

# ==========================================================
# --- MAIN UI: HEADER ---
# ==========================================================
with st.container():
    st.markdown('<div class="fixed-header-container"></div>', unsafe_allow_html=True)
    col_title, col_upload = st.columns([0.85, 0.15])
    with col_title:
        st.title("Spooky 𔓎")
        display_id = f"{PS_APP_ID[:16]}..." if len(PS_APP_ID) > 16 else PS_APP_ID
        st.caption(f"Active Mode: **{app_mode}** | Model: **{selected_model}**\n\n"
                   f"Prompt Security: :green[**Connected ●**] | App-ID: **{display_id}**")

    with col_upload:
        st.markdown('<div class="header-upload-btn">', unsafe_allow_html=True)
        with st.popover("➕ Upload"):
            st.markdown("### 📎 Scan File")
            uploaded_file = st.file_uploader("Select file", type=["txt", "pdf", "png", "jpg"],
                                           label_visibility="collapsed",
                                           key=f"file_up_{st.session_state.uploader_key}")
        st.markdown('</div>', unsafe_allow_html=True)

# SECURITY LOGIC
def check_security_api(text, context_type="prompt"):
    try:
        payload = {context_type: text, "user": user_email}
        headers = {"Content-Type": "application/json", "APP-ID": PS_APP_ID}
        response = requests.post(PS_PROTECT_API, json=payload, headers=headers, timeout=10)
        data = response.json()
        result_block = data.get("result", {})

        st.session_state.last_latency = data.get("totalLatency") or result_block.get("latency", 0)
        content_block = result_block.get(context_type, {}) or {}

        # --- PERSISTENT VIOLATION LOGIC ---
        violations_list = content_block.get("violations", [])
        if violations_list:
            st.session_state.last_violation = " + ".join(violations_list)
        elif context_type == "prompt":
            st.session_state.last_violation = "None"

        action = result_block.get("action", "none")
        
        # Check findings explicitly to catch "log" actions that still found data
        findings = content_block.get("findings", {})
        sensitive_count = len(findings.get("Sensitive Data", []))
        secrets_count = len(findings.get("Secrets", []))
        regex_count = len(findings.get("Regex", []))
        turn_redactions = sensitive_count + secrets_count + regex_count

        if response.status_code == 403 or action == "block":
            st.session_state.security_stats["blocks"] += 1
            st.toast("Security Block Triggered!", icon="🚨")
            return False, "Blocked due to policy violations", data, "blocked"

        redacted_text = content_block.get("modified_text") or text
        
        # Determine status_type based on actual findings
        if turn_redactions > 0:
            st.session_state.security_stats["redactions"] += turn_redactions
            st.toast(f"{turn_redactions} item(s) redacted!", icon="⚠️")
            status_type = "redacted"
        else:
            status_type = "safe"

        return True, redacted_text, data, status_type
    except Exception as e:
        return True, text, {"error": str(e)}, "safe"

# CHAT DISPLAY
last_user_index = -1
for i, msg in enumerate(st.session_state.multi_messages[app_mode]):
    if msg["role"] == "user": last_user_index = i

debug_box_placeholder = None
for i, msg in enumerate(st.session_state.multi_messages[app_mode]):
    with st.chat_message(msg["role"]): st.write(msg["content"])
    if (i == last_user_index):
        debug_box_placeholder = st.empty()
        # If this is a historical message (re-run), show the stored debug info
        if (app_mode == "API (Gemini)" and debug_mode and st.session_state.last_debug_info):
            info = st.session_state.last_debug_info
            # We loosely associate the last debug info with the last user message
            # Ideally we'd store debug info per message in history, but for this demo simple state is sufficient
            with debug_box_placeholder.container(): render_debug_box(info)


# ==========================================================
# --- CHAT INPUT & PROCESSING ---
# ==========================================================
chat_val = st.chat_input("How can I help you safely?")
prompt = st.session_state.input_text if st.session_state.input_text else chat_val
st.session_state.input_text = None

is_new_interaction = chat_val is not None or prompt is not None
if uploaded_file and not is_new_interaction:
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.last_processed_file != file_id:
        is_new_interaction = True

if is_new_interaction and selected_model not in ["Unavailable", "Connection Error"]:
    file_text_context = ""
    image_content = None
    if uploaded_file:
        st.session_state.last_processed_file = f"{uploaded_file.name}_{uploaded_file.size}"
        file_type = uploaded_file.type
        uploaded_file.seek(0)
        if "text" in file_type or "csv" in file_type:
            try:
                decoded_text = uploaded_file.read().decode('utf-8', errors='ignore')
                file_text_context = f"\n\n[File: {uploaded_file.name}]\n{decoded_text}"
            except Exception as e: file_text_context = f"\n[Error: {str(e)}]"
        elif "pdf" in file_type:
            try:
                pdf_reader = pypdf.PdfReader(uploaded_file)
                pdf_text = "".join([page.extract_text() or "" for page in pdf_reader.pages])
                file_text_context = f"\n\n[PDF: {uploaded_file.name}]\n{pdf_text}"
            except: file_text_context = f"\n[Error reading PDF]"
        elif "image" in file_type:
            try:
                image_content = Image.open(uploaded_file)
                file_text_context = f"\n\n[Image attached: {uploaded_file.name}]"
            except: pass

    combined_prompt_text = f"{prompt if prompt else ''} {file_text_context}".strip()

    if combined_prompt_text or image_content:
        # 1. Clear previous placeholder if it exists to prepare for new content
        if debug_box_placeholder: debug_box_placeholder.empty()

        # 2. Append User Message
        st.session_state.multi_messages[app_mode].append({"role": "user", "content": combined_prompt_text})
        with st.chat_message("user"):
            st.write(combined_prompt_text)
            if image_content: st.image(image_content, width=300)

        # 3. Create a fresh placeholder for the Active Turn Debug Info
        active_debug_placeholder = st.empty()

        if app_mode == "AI Gateway (OpenAI)":
            # FIX: The OpenAI client specifically requires the /v1 suffix for the Gateway proxy
            openai_base_url = f"{PS_GATEWAY_URL.strip('/')}/v1"
            
            client = OpenAI(
                base_url=openai_base_url, 
                api_key=api_key,
                default_headers={
                    "ps-app-id": PS_APP_ID, 
                    "forward-domain": "api.openai.com", 
                    "user": user_email
                }
            )
            
            with st.chat_message("assistant"):
                try:
                    response = client.chat.completions.create(
                        model=selected_model,
                        messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.multi_messages[app_mode]]
                    )
                    u = response.usage
                    if u:
                        rate = 0.15 if "mini" in selected_model else 2.50
                        st.session_state.session_costs["AI Gateway (OpenAI)"] += (u.prompt_tokens * rate / 10**6) + (u.completion_tokens * rate*4 / 10**6)
                    reply = response.choices[0].message.content
                    st.write(reply)
                    st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": reply})
                    refresh_metrics()
                except Exception as e: st.error(str(e))
        else:
            # A. CHECK PROMPT SECURITY
            is_safe, checked_p, debug, status_type = check_security_api(combined_prompt_text, "prompt")

            # Store initial state (likely "Safe")
            st.session_state.last_debug_info = {"is_safe": is_safe, "checked_p": checked_p, "original_p": combined_prompt_text, "debug": debug, "status_type": status_type}

            # Render "Safe" initially
            if debug_mode:
                with active_debug_placeholder.container():
                    render_debug_box(st.session_state.last_debug_info)

            refresh_metrics()

            if not is_safe:
                msg = "Blocked due to policy violations"
                st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": msg})
                with st.chat_message("assistant"): st.write(msg)
            else:
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            # B. GENERATE RESPONSE
                            gem_model = genai.GenerativeModel(selected_model)
                            gemini_content = [checked_p]
                            if image_content: gemini_content.append(image_content)
                            history_payload = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in st.session_state.multi_messages[app_mode][:-1]]
                            chat = gem_model.start_chat(history=history_payload)
                            res = chat.send_message(gemini_content)

                            # C. CHECK RESPONSE SECURITY
                            is_res_safe, safe_res, res_debug, res_status_type = check_security_api(res.text, "response")

                            st.write(safe_res)
                            st.session_state.multi_messages[app_mode].append({"role": "assistant", "content": safe_res})

                            # D. UPGRADE DEBUG BOX IF NEEDED
                            if res_status_type in ["redacted", "blocked"]:
                                st.session_state.last_debug_info = {
                                    "is_safe": is_res_safe,
                                    "checked_p": safe_res,
                                    "original_p": res.text,
                                    "debug": res_debug,
                                    "status_type": res_status_type
                                }
                                if debug_mode:
                                    with active_debug_placeholder.container():
                                        render_debug_box(st.session_state.last_debug_info)

                            refresh_metrics()
                        except Exception as e: st.error(str(e))
elif (chat_val or uploaded_file) and selected_model in ["Unavailable", "Connection Error"]:
    st.warning("⚠️ Integration with LLM is not configured. Please check your .env settings.")

st.sidebar.markdown('<div class="sidebar-footer">Made by Gastón Z and AI 🤖</div>', unsafe_allow_html=True)
