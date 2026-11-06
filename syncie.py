import os
import re
import json
import time
import asyncio
import threading
import webbrowser
import requests
import discord
import gradio as gr

# ==============================================================================
# CONFIGURATION
# ==============================================================================
USER_TOKEN = os.getenv(
    "USER_TOKEN",
    "MTU1MDM0MDUzNjQ4Mzg0ODI2Mw.G6cLNH.1zK-lr7vVbJPpAFg7S6dpv-ZQelIFEh4f6giQY"
)

TARGET_BOT_ID = int(os.getenv("TARGET_BOT_ID", 1499804063712411738))
TARGET_GUILD_ID = int(os.getenv("TARGET_GUILD_ID", 1491002411198714008))

WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://discord.com/api/webhooks/1557682271916400640/Ds0wsjAb-ZPzx4vqC5-hAZB9ZSEJ24tUob_o-TOk9QG57DdcVbBlVRhkUip7oQCom6fM"
)

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "drop_alerts_02")
ENABLE_NTFY = os.getenv("ENABLE_NTFY", "True").lower() in ("true", "1", "yes")
AUTO_OPEN_BROWSER = os.getenv("AUTO_OPEN_BROWSER", "True").lower() in ("true", "1", "yes")

SKIP_KEYWORDS = [
    "shared a hyperprop card",
    "shared a public trade",
]


# ==============================================================================
# LOGGING SYSTEM
# ==============================================================================
bot_status = {"status": "Starting...", "logs": []}
log_lock = threading.Lock()

def add_log(msg: str):
    with log_lock:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        log_entry = f"{timestamp} {msg}"
        print(log_entry, flush=True)
        bot_status["logs"].append(log_entry)
        if len(bot_status["logs"]) > 200:
            bot_status["logs"].pop(0)

# ==============================================================================
# NTFY ALARM DISPATCHER
# ==============================================================================
def trigger_ntfy_alarm(topic: str, title: str, message_text: str, click_url: str = None, count: int = 5, delay: float = 2.5):
    """Sends repeated urgent-priority alarm notifications via ntfy.sh."""
    if not topic:
        return

    def _send():
        clean_topic = topic.strip()
        payload = {
            "topic": clean_topic,
            "title": title,
            "message": message_text,
            "priority": 5,  # Max priority (urgent sound & screen wake)
            "tags": ["rotating_light", "warning", "loudspeaker"]
        }
        if click_url:
            payload["click"] = click_url
            payload["actions"] = [{"action": "view", "label": "🔗 Open Verification / Drop", "url": click_url}]

        for i in range(1, count + 1):
            try:
                payload["title"] = f"{title} [{i}/{count}]"
                add_log(f"🚨 [NTFY] Dispatching alarm ({i}/{count}) to topic '{clean_topic}'...")
                res = requests.post("https://ntfy.sh", json=payload, timeout=10)
                if res.status_code == 200:
                    add_log(f"🚨 [NTFY] Alarm ({i}/{count}) delivered!")
                else:
                    add_log(f"⚠️ [NTFY] Response status {res.status_code}: {res.text}")
            except Exception as e:
                add_log(f"❌ [NTFY] Error sending alarm ({i}/{count}): {e}")

            if i < count:
                time.sleep(delay)

    threading.Thread(target=_send, daemon=True).start()

# ==============================================================================
# MESSAGE & URL EXTRACTORS
# ==============================================================================
def extract_all_text(message) -> str:
    """Combines message content, embed titles, descriptions, fields, and button labels."""
    texts = [message.content or ""]
    for emb in getattr(message, "embeds", []):
        if emb.title:
            texts.append(emb.title)
        if emb.description:
            texts.append(emb.description)
        for field in getattr(emb, "fields", []):
            texts.append(f"{field.name} {field.value}")
        if getattr(emb, "footer", None) and getattr(emb.footer, "text", None):
            texts.append(emb.footer.text)
        if getattr(emb, "author", None) and getattr(emb.author, "name", None):
            texts.append(emb.author.name)

    if getattr(message, "components", None):
        for row in message.components:
            for comp in getattr(row, "children", []):
                label = getattr(comp, "label", None) or ""
                custom_id = getattr(comp, "custom_id", None) or ""
                texts.append(f"{label} {custom_id}")

    return " ".join(texts)

def extract_verification_urls(message) -> list:
    """Extracts external verification links like drop-check, antibot, or claim urls."""
    found = set()
    combined_text = extract_all_text(message)

    # Check button URL components
    if getattr(message, "components", None):
        for row in message.components:
            for comp in getattr(row, "children", []):
                btn_url = getattr(comp, "url", None)
                if btn_url:
                    found.add(btn_url)

    url_pattern = r'https?://[^\s<>"\)\]]+'
    for match in re.findall(url_pattern, combined_text):
        lower = match.lower()
        if any(kw in lower for kw in ["drop-check", "antibot", "checkantibot", "claim", "syncie"]):
            found.add(match)

    return list(found)

# Track notified events to avoid duplicates
processed_messages = set()

def handle_syncie_message(message, event_type: str = "new"):
    """Core handler for messages from Bot 1499804063712411738."""
    if message.author.id != TARGET_BOT_ID:
        return

    msg_id = getattr(message, "id", 0)
    event_key = (msg_id, message.content, len(message.embeds))
    if event_key in processed_messages:
        return
    processed_messages.add(event_key)
    if len(processed_messages) > 1000:
        processed_messages.clear()

    channel_name = getattr(message.channel, "name", "channel")
    full_text = extract_all_text(message)
    clean_text = re.sub(r'[\*\_`#]', '', full_text).lower()

    # Skip messages matching skip keywords
    for skip_kw in SKIP_KEYWORDS:
        if skip_kw in clean_text:
            add_log(f"🛡️ [Syncie Skipped] Message {msg_id} in #{channel_name} matched skip filter: '{skip_kw}'")
            return

    verify_urls = extract_verification_urls(message)
    contains_drop = "complete the browser check" in clean_text

    add_log(f"⚡ [Syncie Bot Triggered] Event: {event_type} | Channel: #{channel_name} | Contains 'complete the browser check': {contains_drop}")

    # --- 1. Forward to Discord Webhook ---
    fwd_header = f"-# 📨 Forwarded from [#{channel_name}]({message.jump_url}) · [Jump to Message]({message.jump_url})"
    alert_prefix = "@everyone 🚨 **SYNCIE DROP ALERT DETECTED!**\n" if contains_drop else "@everyone\n"
    
    content = message.content or ""
    # Extract embed text if content is empty
    embed_texts = []
    for emb in message.embeds:
        if emb.title:
            embed_texts.append(f"**{emb.title}**")
        if emb.description:
            embed_texts.append(emb.description)
        for field in emb.fields:
            embed_texts.append(f"• **{field.name}**: {field.value}")
    if embed_texts and not content:
        content = "\n".join(embed_texts)

    full_content = (alert_prefix + fwd_header + ("\n" + content if content else "")).strip()

    # Pass-through original embeds
    forwarded_embeds = []
    for emb in message.embeds:
        emb_dict = {}
        if emb.title: emb_dict["title"] = emb.title
        if emb.description: emb_dict["description"] = emb.description
        if emb.url: emb_dict["url"] = emb.url
        if emb.color: emb_dict["color"] = emb.color.value
        if emb.image and emb.image.url: emb_dict["image"] = {"url": emb.image.url}
        if emb.thumbnail and emb.thumbnail.url: emb_dict["thumbnail"] = {"url": emb.thumbnail.url}
        if emb.author:
            emb_dict["author"] = {}
            if emb.author.name: emb_dict["author"]["name"] = emb.author.name
            if emb.author.url: emb_dict["author"]["url"] = emb.author.url
            if emb.author.icon_url: emb_dict["author"]["icon_url"] = emb.author.icon_url
        if emb.footer:
            emb_dict["footer"] = {}
            if emb.footer.text: emb_dict["footer"]["text"] = emb.footer.text
            if emb.footer.icon_url: emb_dict["footer"]["icon_url"] = emb.footer.icon_url
        if emb.fields:
            emb_dict["fields"] = [{"name": f.name, "value": f.value, "inline": f.inline} for f in emb.fields]
        if emb_dict:
            forwarded_embeds.append(emb_dict)

    # Add verification embed if URL detected
    if verify_urls:
        forwarded_embeds.append({
            "title": "🛡️ Verification / Drop Link Detected",
            "description": "\n".join([f"👉 [Click to Complete Verification]({u})" for u in verify_urls]),
            "color": 0xFF2222
        })

    bot_avatar_url = None
    if message.author.avatar:
        bot_avatar_url = str(message.author.avatar.url)
    elif message.author.default_avatar:
        bot_avatar_url = str(message.author.default_avatar.url)

    webhook_payload = {
        "username": message.author.display_name or message.author.name,
        "avatar_url": bot_avatar_url,
        "content": full_content[:2000],
        "embeds": forwarded_embeds[:10],
        "allowed_mentions": {"parse": ["everyone"]},
    }

    try:
        res = requests.post(WEBHOOK_URL, json=webhook_payload, timeout=10)
        if res.status_code in (200, 204):
            add_log(f"✅ Webhook alert successfully sent to Discord!")
        else:
            add_log(f"⚠️ Webhook error: {res.status_code} - {res.text}")
    except Exception as e:
        add_log(f"❌ Webhook request failed: {e}")

    # --- 2. Send NTFY Alarm if message contains 'complete the browser check' ---
    if contains_drop and ENABLE_NTFY and NTFY_TOPIC:
        target_click_url = verify_urls[0] if verify_urls else message.jump_url
        ntfy_title = "🚨 SYNCIE BROWSER CHECK ALERT!"
        ntfy_msg = f"Bot Syncie posted a 'Complete the browser check' message in #{channel_name}!\n\n{content[:250]}"
        trigger_ntfy_alarm(NTFY_TOPIC, ntfy_title, ntfy_msg, click_url=target_click_url, count=5, delay=2.0)

        # Auto-open verification link in browser if enabled
        if AUTO_OPEN_BROWSER and verify_urls:
            try:
                add_log(f"🌐 Opening verification link in browser: {verify_urls[0]}")
                webbrowser.open(verify_urls[0])
            except Exception as e:
                add_log(f"⚠️ Could not open browser: {e}")

# ==============================================================================
# DISCORD CLIENT
# ==============================================================================
client = discord.Client()

@client.event
async def on_ready():
    add_log(f"Successfully connected as: {client.user} (ID: {client.user.id})")
    add_log(f"🎯 Target Bot: {TARGET_BOT_ID}")
    add_log(f"🔗 Target Webhook: {WEBHOOK_URL}")
    add_log(f"🔔 ntfy Topic: '{NTFY_TOPIC}' (Active: {ENABLE_NTFY})")
    bot_status["status"] = f"Online as {client.user} | Monitoring Bot {TARGET_BOT_ID}"

@client.event
async def on_message(message):
    handle_syncie_message(message, event_type="on_message")

@client.event
async def on_message_edit(before, after):
    handle_syncie_message(after, event_type="on_message_edit")

def run_discord():
    while True:
        try:
            client.run(USER_TOKEN)
        except Exception as e:
            add_log(f"Discord error: {e}. Reconnecting in 10s...")
            time.sleep(10)

# ==============================================================================
# GRADIO DASHBOARD
# ==============================================================================
def get_dashboard_logs():
    return f"Bot Status: {bot_status['status']}\n\n" + "\n".join(reversed(bot_status["logs"]))

def create_ui():
    with gr.Blocks(title="Syncie Drop Monitor") as demo:
        gr.Markdown("# 🚀 Syncie Drop Monitor (Bot 1499804063712411738)")
        gr.Markdown(
            f"**Target Bot ID:** `{TARGET_BOT_ID}`  \n"
            f"**ntfy Topic:** `{NTFY_TOPIC}`  \n"
            f"**Webhook:** `{WEBHOOK_URL}`"
        )
        status_box = gr.Textbox(label="Live Activity Logs", value=get_dashboard_logs, every=2, lines=16)
    return demo

if __name__ == "__main__":
    # Start Discord listener in background thread
    t = threading.Thread(target=run_discord, daemon=True)
    t.start()

    # Launch Gradio interface
    ui = create_ui()
    ui.launch(server_name="0.0.0.0", server_port=7861)
