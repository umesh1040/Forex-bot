import os
import sys
import subprocess
import threading
import time
import asyncio
import json
import re
import urllib.request
import urllib.parse
import webbrowser
import requests
import discord
import gradio as gr
from datetime import datetime

# ----------------- CONFIGURATION -----------------
USER_TOKEN = os.getenv("USER_TOKEN", "MTU1MDM0MDUzNjQ4Mzg0ODI2Mw.G6cLNH.1zK-lr7vVbJPpAFg7S6dpv-ZQelIFEh4f6giQY")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "drop_alerts_02")
ENABLE_NTFY = os.getenv("ENABLE_NTFY", "True").lower() in ("true", "1", "yes")
AUTO_OPEN_BROWSER = os.getenv("AUTO_OPEN_BROWSER", "True").lower() in ("true", "1", "yes")

# Optional proxy for YouTube (essential on cloud platforms like Render/AWS to bypass 429)
YOUTUBE_PROXY = os.getenv("YOUTUBE_PROXY", "").strip() or None
YOUTUBE_POLL_INTERVAL = int(os.getenv("YOUTUBE_POLL_INTERVAL", "25"))

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

YOUTUBE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

YOUTUBE_COOKIES = {
    'CONSENT': 'YES+cb.20210328-17-p0.en+FX+478',
    'SOCS': 'CAESEwgDEgk2Nzc0ODUxNDMaAmVuIAEaBgiA_LyaBg',
}

# Channels to monitor for text-sending permission (alert if closed/opened)
WATCHED_CHANNELS_ACCESS = {
    1546975688534528060: {
        "guild_id": 1491002411198714008,
        "name": "Channel 1546975688534528060",
        "webhook_url": "https://discord.com/api/webhooks/1553274892760391835/-Dt6G-CGaeiTUGGyr0mCr1X1HJEcII6Qg-eQDhyTqw671p9Iq4HQpOuGCoS_aoHNhUJY",
    },
    1493168400837382196: {
        "guild_id": 1491002411198714008,
        "name": "Channel 1493168400837382196",
        "webhook_url": "https://discord.com/api/webhooks/1553274892760391835/-Dt6G-CGaeiTUGGyr0mCr1X1HJEcII6Qg-eQDhyTqw671p9Iq4HQpOuGCoS_aoHNhUJY",
    },  
    1533813510696337471: {
        "guild_id": 1533813510205866096,
        "name": "Channel 1533813510696337471",
        "webhook_url": "https://discord.com/api/webhooks/1553274892760391835/-Dt6G-CGaeiTUGGyr0mCr1X1HJEcII6Qg-eQDhyTqw671p9Iq4HQpOuGCoS_aoHNhUJY",
    },
}

RULES = [
    {
        "name": "Bot 1499804063712411738 Monitor",
        "bot_ids": [654764587991957516, 575878365261594624, 960882470029524992],
        "channel_ids": [1493168400837382196, 1541483457694400563, 1546975688534528060],
        "webhook_url": "https://discord.com/api/webhooks/1547448491213594755/Vrfgd8X0WzoiRWno3Z26P84In7r2jhY0DqPsJBv1oCqDrvBxt_-MjfcTd17wZn_yGI10",
    },
    {  # Syncie (HyperProp Drop Bot)
        "name": "Syncie Monitor",
        "bot_ids": [1499804063712411738],
        "channel_ids": [1493168400837382196, 1541483457694400563, 1546975688534528060],
        "webhook_url": "https://discord.com/api/webhooks/1553274892760391835/-Dt6G-CGaeiTUGGyr0mCr1X1HJEcII6Qg-eQDhyTqw671p9Iq4HQpOuGCoS_aoHNhUJY",
    },
    {  # E8 Markets
        "name": "E8 Markets Monitor",
        "bot_ids": [1546451237782691881],
        "channel_ids": [1463611205116625154],
        "webhook_url": "https://discord.com/api/webhooks/1547472423006507098/zq-0aHRGDIwYbwrziWFOblzQwbH4BluvpcxXxsDdK3mov9HWcw6juC9zLJ8LZUM75tYi",
        "youtube_url": "https://www.youtube.com/@E8Markets/streams",
        "yt_filter_author": "@E8Markets",
        "yt_filter_keyword": "code",
    },
    {   # Prop Firm Match
        "name": "Prop Firm Match Monitor",
        "bot_ids": [1454107099968700620],
        "channel_ids": [1493970397320712213],
        "webhook_url": "https://discord.com/api/webhooks/1547473124121911328/3n6CWzGyACF2kbOGA4n2Gxk9axi9O6G9bqqb9Si-4sYx1Mju9GcYhNByToKh8b1crhMO",
        "youtube_url": "https://www.youtube.com/@propfirmmatch/streams",
        "yt_filter_author": "@propfirmmatch",
        "yt_filter_keyword": "code",
        "yt_skip_keywords": [
            'use code "match"',
            "use code match",
            "for the best discount",
            'code "match"',
            "code match",
            "% off",
            "%off",
        ],
    },
    {   # MyFundedFutures
        "name": "MyFundedFutures Monitor",
        "bot_ids": [],
        "channel_ids": [],
        "webhook_url": "https://discord.com/api/webhooks/1550399340906807328/Q7IQWXTVYBzsvYFXCEZHkWb0KGF1xQM3-h2u0xUMmpgKeMsZJIj8CDhFOLCQuWzlN1EZ",
        "youtube_url": "https://youtube.com/@myfundedfuturespropfirm/streams",
        "mention_everyone": True,
        "include_channel_link": True,
        "ntfy_keywords": ["https://forms", "https://docs"],
        "yt_filter_author": "@MyFundedFuturesPropFirm",
        "yt_filter_substrings": ["https://", "keyword"],
        "yt_skip_urls": [
            "https://discord.gg/myfundedfutures",
            "https://myfundedperpetuals.com",
            "https://linktr.ee/",
            "https://myfundedfutures.com",
            "https://link.me/",
            "https://x.com/",
            "https://youtube.com", 
            "how to join giveaway"
        ],
    },
]
# -------------------------------------------------


bot_status = {"status": "Starting...", "logs": []}
log_lock = threading.Lock()

def add_log(msg: str):
    with log_lock:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        log_entry = f"{timestamp} {msg}"
        print(log_entry, flush=True)
        bot_status["logs"].append(log_entry)
        if len(bot_status["logs"]) > 150:
            bot_status["logs"].pop(0)

def get_rule_bot_ids(rule):
    if "bot_ids" in rule:
        return rule["bot_ids"]
    if "bot_id" in rule:
        return [rule["bot_id"]] if isinstance(rule["bot_id"], int) else list(rule["bot_id"])
    return []

def trigger_ntfy_alarm(topic: str, title: str, message_text: str, click_url: str = None, count: int = 5, delay: float = 3.0):
    """Sends an emergency/urgent priority alarm notification via ntfy.sh repeated multiple times for persistent ringing."""
    if not topic:
        return
    def _send():
        clean_topic = topic.strip()
        payload = {
            "topic": clean_topic,
            "title": title,
            "message": message_text,
            "priority": 5,  # Max priority (urgent) -> loud alarm sound & screen wake
            "tags": ["warning", "rotating_light", "loudspeaker"]
        }
        if click_url:
            payload["click"] = click_url
            payload["actions"] = [{"action": "view", "label": "🔗 Open Link", "url": click_url}]

        for i in range(1, count + 1):
            try:
                payload["title"] = f"{title} [{i}/{count}]"
                add_log(f"🚨 Dispatching ntfy loud alarm ({i}/{count}) to topic '{clean_topic}'...")
                res = requests.post("https://ntfy.sh", json=payload, timeout=10)
                if res.status_code == 200:
                    add_log(f"🚨 ntfy alarm ({i}/{count}) delivered successfully!")
                else:
                    add_log(f"⚠️ ntfy response: {res.status_code} - {res.text}")
            except Exception as e:
                add_log(f"❌ Error sending ntfy alarm ({i}/{count}): {e}")

            if i < count:
                time.sleep(delay)

    threading.Thread(target=_send, daemon=True).start()

def extract_verification_urls(message):
    """Extracts external verification links like syncie.hyperprop.com/drop-check from message text, embeds, and buttons."""
    found_urls = set()
    raw_texts = [message.content or ""]

    for emb in message.embeds:
        if emb.title:
            raw_texts.append(emb.title)
        if emb.description:
            raw_texts.append(emb.description)
        if emb.url:
            raw_texts.append(emb.url)
        for field in emb.fields:
            raw_texts.append(f"{field.name} {field.value}")
        if getattr(emb, "footer", None) and getattr(emb.footer, "text", None):
            raw_texts.append(emb.footer.text)

    # Check button URL components
    if message.components:
        for action_row in message.components:
            for component in getattr(action_row, "children", []):
                btn_url = getattr(component, "url", None)
                if btn_url:
                    raw_texts.append(btn_url)

    combined_text = " ".join(raw_texts)
    
    url_pattern = r'https?://[^\s<>"\)\]]+'
    for match in re.findall(url_pattern, combined_text):
        lower_match = match.lower()
        if any(keyword in lower_match for keyword in ["drop-check",  "antibot", "checkantibot"]):
            found_urls.add(match)

    return list(found_urls)

def extract_general_urls(text: str):
    """Extracts all HTTP/HTTPS links from any string."""
    if not text:
        return []
    url_pattern = r'https?://[^\s<>"\)\]]+'
    return list(dict.fromkeys(re.findall(url_pattern, text)))

def is_promo_or_spam(message) -> bool:
    """Skips promo/waitlist/socials messages and test/no-prize messages."""
    raw_texts = [message.content or ""]
    for emb in getattr(message, "embeds", []):
        if emb.title:
            raw_texts.append(emb.title)
        if emb.description:
            raw_texts.append(emb.description)
        for field in getattr(emb, "fields", []):
            raw_texts.append(f"{field.name} {field.value}")
        if getattr(emb, "footer", None) and getattr(emb.footer, "text", None):
            raw_texts.append(emb.footer.text)
        if getattr(emb, "author", None) and getattr(emb.author, "name", None):
            raw_texts.append(emb.author.name)

    combined_text = " ".join(raw_texts).lower()
    clean_text = re.sub(r'[\*\_`#]', '', combined_text)

    no_prize_keywords = [
        "no prize",
        "no prizes",
        "no-prize",
        "no-prizes",
        "no reward",
        "no rewards",
        "zero prize",
        "test drop",
        "drop verification test",
    ]
    if any(npk in clean_text for npk in no_prize_keywords):
        return True

    is_msg1 = (
        "want to get a hyperprop account" in clean_text
        and "myfundedfutures" in clean_text
        and "access to purchase evaluation accounts" in clean_text
    )

    is_msg2 = (
        ("don't forget to follow hyperprop on socials" in clean_text or "don’t forget to follow hyperprop on socials" in clean_text or "dont forget to follow hyperprop on socials" in clean_text)
        and "stay up to date with the latest news, drops, and announcements" in clean_text
    )

    return is_msg1 or is_msg2


client = discord.Client()

@client.event
async def on_ready():
    add_log(f"Successfully logged in as: {client.user}")
    for idx, rule in enumerate(RULES, 1):
        bot_ids = get_rule_bot_ids(rule)
        channel_ids = rule.get("channel_ids", [])
        yt = f" | YouTube: {rule['youtube_url']}" if rule.get("youtube_url") else ""
        add_log(f"Rule #{idx} ({rule.get('name', 'Rule')}) Active: Bot(s) {bot_ids} -> Channels {channel_ids}{yt}")
    bot_status["status"] = f"Online as {client.user} | YouTube Live Monitors Active"

    # Start channel send-access monitoring task
    if not getattr(client, "_channel_monitor_started", False):
        client._channel_monitor_started = True
        client.loop.create_task(channel_access_monitor_loop())

def has_enter_button(message):
    """Checks if message has any interactive or link button matching entry keywords."""
    entry_keywords = ["enter drop", "enter", "join", "claim", "race", "duck", "participate"]
    if hasattr(message, "components") and message.components:
        for action_row in message.components:
            for component in getattr(action_row, "children", []):
                btn_label = getattr(component, "label", "") or ""
                btn_custom_id = getattr(component, "custom_id", "") or ""
                btn_desc = f"{btn_label} {btn_custom_id}".lower()
                for kw in entry_keywords:
                    if kw in btn_desc:
                        return True, btn_label or btn_custom_id or kw.title()
    return False, None

notified_events = set()

def check_and_trigger_ntfy_alarms(message, content: str = "", verify_urls: list = None):
    """Triggers loud ntfy alarm ONLY for Bot 1499804063712411738 if message has 'DROP INCOMING' or an entry button."""
    if getattr(message.author, "id", None) != 1499804063712411738:
        return

    has_enter_btn, enter_btn_name = has_enter_button(message)
    has_drop_incoming = "drop incoming" in (content or "").lower()  # case-insensitive

    if not (has_drop_incoming or has_enter_btn):
        return

    if verify_urls is None:
        verify_urls = extract_verification_urls(message)

    alert_type = f"enter_{enter_btn_name}" if has_enter_btn else "drop_incoming"
    event_key = (getattr(message, "id", 0), alert_type)
    if event_key in notified_events:
        return
    notified_events.add(event_key)
    if len(notified_events) > 1000:
        notified_events.clear()

    bot_name = getattr(message.author, "name", "Bot")
    channel_name = getattr(message.channel, "name", "channel")
    target_click_url = verify_urls[0] if verify_urls else getattr(message, "jump_url", "https://discord.com")

    if has_enter_btn:
        if verify_urls:
            ntfy_title = f"🚨 URGENT: '{enter_btn_name}' BUTTON & VERIFY!"
            ntfy_msg = f"Bot {bot_name} posted '{enter_btn_name}' button in #{channel_name} with verification link!\n\nOpen and complete verification immediately."
        else:
            ntfy_title = f"🚨 '{enter_btn_name}' BUTTON DETECTED!"
            ntfy_msg = f"Bot {bot_name} posted '{enter_btn_name}' button in #{channel_name}.\n\nCheck Discord immediately."
    else:
        if verify_urls:
            ntfy_title = "🚨 URGENT: DROP INCOMING (VERIFY NOW!)"
            ntfy_msg = f"Bot {bot_name} posted DROP INCOMING in #{channel_name} with verification link!\n\nOpen and complete verification immediately."
        else:
            ntfy_title = "🚨 DROP INCOMING DETECTED!"
            ntfy_msg = f"Bot {bot_name} posted DROP INCOMING in #{channel_name}.\n\nCheck Discord immediately."

    reason = f"'{enter_btn_name}' Entry Button" if has_enter_btn else "DROP INCOMING"
    add_log(f"🔔 [NTFY ALERT TRIGGERED] Reason: {reason} | Bot: {bot_name}")

    if ENABLE_NTFY and NTFY_TOPIC:
        trigger_ntfy_alarm(NTFY_TOPIC, ntfy_title, ntfy_msg, click_url=target_click_url)

@client.event
async def on_message_edit(before, after):
    if is_promo_or_spam(after):
        return

    content = after.content if after.content else "[Bot sent an Embed or Attachment]"
    embed_parts = []
    for emb in getattr(after, "embeds", []):
        if emb.title:
            embed_parts.append(f"**{emb.title}**")
        if emb.description:
            embed_parts.append(emb.description)
        for field in emb.fields:
            embed_parts.append(f"• **{field.name}**: {field.value}")
    if embed_parts:
        content += "\n\n" + "\n".join(embed_parts)

    verify_urls = extract_verification_urls(after)
    check_and_trigger_ntfy_alarms(after, content=content, verify_urls=verify_urls)

@client.event
async def on_message(message):
    if is_promo_or_spam(message):
        add_log(f"🛡️ Skipped Bot {getattr(message.author, 'name', 'Unknown')} message {message.id}: Matched promo/waitlist/socials filter (no notification, no webhook)")
        return

    for rule in RULES:
        target_bot_ids = get_rule_bot_ids(rule)
        channel_ids = rule.get("channel_ids", [])
        if target_bot_ids and message.author.id in target_bot_ids and message.channel.id in channel_ids:
            add_log(f"Match found! Bot {message.author.name} ({message.author.id}) posted in #{getattr(message.channel, 'name', 'channel')}")

            content = message.content if message.content else ""
            # --- Extract embed text so drop content isn't missed when message.content is empty ---
            embed_text_parts = []
            for emb in message.embeds:
                if emb.title:        embed_text_parts.append(emb.title)
                if emb.description:  embed_text_parts.append(emb.description)
                for field in emb.fields:
                    embed_text_parts.append(f"**{field.name}**: {field.value}")
            if embed_text_parts:
                content = (content + "\n\n" + "\n".join(embed_text_parts)).strip()

            verify_urls = extract_verification_urls(message)

            # --- Build forwarded embeds (pass through original embeds) ---
            forwarded_embeds = []
            for emb in message.embeds:
                emb_dict = {}
                if emb.title:
                    emb_dict["title"] = emb.title
                if emb.description:
                    emb_dict["description"] = emb.description
                if emb.url:
                    emb_dict["url"] = emb.url
                if emb.color:
                    emb_dict["color"] = emb.color.value
                if emb.image and emb.image.url:
                    emb_dict["image"] = {"url": emb.image.url}
                if emb.thumbnail and emb.thumbnail.url:
                    emb_dict["thumbnail"] = {"url": emb.thumbnail.url}
                if emb.author:
                    emb_dict["author"] = {}
                    if emb.author.name:
                        emb_dict["author"]["name"] = emb.author.name
                    if emb.author.url:
                        emb_dict["author"]["url"] = emb.author.url
                    if emb.author.icon_url:
                        emb_dict["author"]["icon_url"] = emb.author.icon_url
                if emb.footer:
                    emb_dict["footer"] = {}
                    if emb.footer.text:
                        emb_dict["footer"]["text"] = emb.footer.text
                    if emb.footer.icon_url:
                        emb_dict["footer"]["icon_url"] = emb.footer.icon_url
                if emb.fields:
                    emb_dict["fields"] = [
                        {"name": f.name, "value": f.value, "inline": f.inline}
                        for f in emb.fields
                    ]
                if emb_dict:
                    forwarded_embeds.append(emb_dict)

            # --- Extra info embeds (verify link, YouTube) ---
            extra_embeds = []
            if verify_urls:
                extra_embeds.append({
                    "title": "🛡️ Antibot Verification Required",
                    "description": "\n".join([f"👉 [Click Here to Verify]({u})" for u in verify_urls]),
                    "color": 0xFF4444,
                })
            if rule.get("youtube_url"):
                extra_embeds.append({
                    "title": "📺 YouTube Live Stream",
                    "description": f"👉 [Click Here to Watch]({rule['youtube_url']})",
                    "color": 0xFF0000,
                })

            # --- Reference header (small forwarded-from line) ---
            channel_name = getattr(message.channel, 'name', 'channel')
            guild_id = getattr(getattr(message, 'guild', None), 'id', '')
            fwd_header = (
                f"-# 📨 Forwarded from [#{channel_name}]({message.jump_url}) · "
                f"[Jump to original]({message.jump_url})"
            )
            if verify_urls:
                alert_prefix = "@everyone 🛡️ **ACTION REQUIRED: Complete Verification!**\n"
            else:
                alert_prefix = "@everyone\n"

            full_content = alert_prefix + fwd_header
            if content:
                full_content += "\n" + content

            # --- Resolve original bot's avatar ---
            bot_avatar_url = None
            if message.author.avatar:
                bot_avatar_url = str(message.author.avatar.url)
            elif message.author.default_avatar:
                bot_avatar_url = str(message.author.default_avatar.url)

            all_embeds = forwarded_embeds + extra_embeds
            # Discord allows max 10 embeds per message
            all_embeds = all_embeds[:10]

            payload = {
                "username": message.author.display_name or message.author.name,
                "avatar_url": bot_avatar_url,
                "content": full_content[:2000],
                "embeds": all_embeds,
                "allowed_mentions": {"parse": ["everyone"]},
            }

            try:
                res = requests.post(rule["webhook_url"], json=payload)
                if res.status_code in [200, 204]:
                    add_log(f"Alert sent to webhook for Bot {message.author.name} ({message.author.id})!")
                else:
                    add_log(f"Webhook error: {res.status_code} - {res.text}")
            except Exception as e:
                add_log(f"Error sending webhook: {e}")

            check_and_trigger_ntfy_alarms(message, content=content, verify_urls=verify_urls)

# =============================================================================
# CHANNEL SEND-ACCESS MONITORING
# Detects when a channel is closed (cannot send text) or re-opened (can send text)
# =============================================================================

_channel_access_state = {}  # channel_id -> bool (True: can send, False: cannot send)

async def check_channel_send_permission(channel_id: int):
    """
    Checks if our account currently has permission to view and send text in the channel.
    Returns: (can_send: bool, channel_name: str, reason: str)
    """
    channel = client.get_channel(channel_id)
    if not channel and client.is_ready():
        try:
            channel = await client.fetch_channel(channel_id)
        except Exception as e:
            return False, f"Channel {channel_id}", f"Channel inaccessible ({e})"

    if not channel:
        return False, f"Channel {channel_id}", "Channel not found (inaccessible or deleted)"

    guild = getattr(channel, "guild", None)
    if not guild:
        return False, getattr(channel, "name", str(channel_id)), "Guild not found"

    me = guild.get_member(client.user.id) or getattr(guild, "me", None)
    if not me:
        try:
            me = await guild.fetch_member(client.user.id)
        except Exception:
            me = None

    if not me:
        return False, getattr(channel, "name", str(channel_id)), "User not found in guild"

    perms = channel.permissions_for(me)
    view_ok = getattr(perms, "view_channel", getattr(perms, "read_messages", False))
    send_ok = getattr(perms, "send_messages", False)

    if not view_ok:
        return False, channel.name, "No view/read permission (channel hidden or private)"
    if not send_ok:
        return False, channel.name, "No send permission (channel locked/read-only)"

    return True, channel.name, "Can send messages"

def notify_channel_access_change(channel_id: int, can_send: bool, channel_name: str = "", reason: str = ""):
    info = WATCHED_CHANNELS_ACCESS.get(channel_id, {})
    guild_id = info.get("guild_id", "")
    ch_label = f"#{channel_name}" if channel_name and not channel_name.startswith("Channel ") else info.get("name", f"Channel {channel_id}")
    webhook_url = info.get("webhook_url")
    channel_link = f"https://discord.com/channels/{guild_id}/{channel_id}"

    if not can_send:
        title = "🔒 CHANNEL CLOSED / CANNOT SEND TEXT!"
        desc = (
            f"⚠️ Channel **{ch_label}** (<#{channel_id}>) is **CLOSED** for sending text!\n\n"
            f"• **Status:** 🔒 Locked (Cannot send text)\n"
            f"• **Reason:** {reason}\n"
            f"• **Direct Link:** [Open in Discord]({channel_link})"
        )
        color = 0xFF2222
        ntfy_title = "🔒 CHANNEL CLOSED (CANNOT SEND)!"
        ntfy_msg = f"{ch_label} is CLOSED for sending text!\nReason: {reason}\n{channel_link}"
        add_log(f"🔒 [CHANNEL CLOSED] {ch_label} ({channel_id}) is closed for text! ({reason})")
    else:
        title = "🔓 CHANNEL OPENED / SEND TEXT ENABLED!"
        desc = (
            f"✅ Channel **{ch_label}** (<#{channel_id}>) is now **OPEN** for sending text!\n\n"
            f"• **Status:** 🔓 Unlocked (Can send text)\n"
            f"• **Direct Link:** [Open in Discord]({channel_link})"
        )
        color = 0x22FF55
        ntfy_title = "🔓 CHANNEL OPEN FOR TEXT!"
        ntfy_msg = f"{ch_label} is now OPEN! You can send text now.\n{channel_link}"
        add_log(f"🔓 [CHANNEL OPEN] {ch_label} ({channel_id}) is now open for text!")

    # 1. Send Discord Webhook
    if webhook_url:
        payload = {
            "content": "@everyone",
            "embeds": [{
                "title": title,
                "description": desc,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
            }],
            "allowed_mentions": {"parse": ["everyone"]},
        }
        try:
            res = requests.post(webhook_url, json=payload, timeout=10)
            if res.status_code in [200, 204]:
                add_log(f"✅ Webhook alert delivered: {title}")
            else:
                add_log(f"⚠️ Webhook response: {res.status_code} - {res.text}")
        except Exception as e:
            add_log(f"❌ Error sending channel status webhook: {e}")

    # 2. Trigger loud ntfy alarm
    if ENABLE_NTFY and NTFY_TOPIC:
        trigger_ntfy_alarm(
            NTFY_TOPIC,
            ntfy_title,
            ntfy_msg,
            click_url=channel_link,
            count=5 if not can_send else 2,
            delay=2.0
        )

async def check_channel_access_status():
    for ch_id in list(WATCHED_CHANNELS_ACCESS.keys()):
        can_send, name, reason = await check_channel_send_permission(ch_id)
        prev = _channel_access_state.get(ch_id)
        if prev is None:
            # First initialization after bot startup
            _channel_access_state[ch_id] = can_send
            status_str = "OPEN (can send text)" if can_send else f"CLOSED ({reason})"
            add_log(f"📡 [Channel Monitor] Watching #{name} ({ch_id}): Initial state is {status_str}")
            if not can_send:
                notify_channel_access_change(ch_id, can_send, name, reason)
        elif prev != can_send:
            _channel_access_state[ch_id] = can_send
            notify_channel_access_change(ch_id, can_send, name, reason)

@client.event
async def on_guild_channel_update(before, after):
    """Instantly detects channel permission/overwrite changes via Discord gateway."""
    if after.id in WATCHED_CHANNELS_ACCESS:
        await check_channel_access_status()

async def channel_access_monitor_loop():
    """Background polling loop: verifies permissions every 10 seconds."""
    await client.wait_until_ready()
    await asyncio.sleep(5)  # Wait for guild cache to populate
    while not client.is_closed():
        try:
            await check_channel_access_status()
        except Exception as e:
            add_log(f"⚠️ Error in channel access check: {e}")
        await asyncio.sleep(10)

def run_discord():
    while True:
        try:
            client.run(USER_TOKEN)
        except Exception as e:
            add_log(f"Discord error: {e}. Reconnecting in 10s...")
            time.sleep(10)

# ==============================================================================
# YouTube Live Stream & Live Chat Monitoring Engine
# ==============================================================================

def clean_channel_url(raw_url):
    if not raw_url:
        return ""
    url = raw_url.split('?')[0].rstrip('/')
    if not url.endswith('/streams') and not url.endswith('/live') and '/watch' not in url:
        url += '/streams'
    return url

class YouTubeLiveChatClient:
    def __init__(self, channel_or_video_url):
        self.target_url = clean_channel_url(channel_or_video_url) if ('youtube.com' in channel_or_video_url or 'youtu.be' in channel_or_video_url) else channel_or_video_url.strip()
        self.api_key = None
        self.client_version = "2.20260917.01.00"
        self.video_id = None
        self.is_live = False
        self.continuation = None
        self.is_replay = False

    def fetch_url(self, url, post_data=None):
        proxies = None
        if YOUTUBE_PROXY:
            proxies = {"http": YOUTUBE_PROXY, "https": YOUTUBE_PROXY}

        headers = {**YOUTUBE_HEADERS}
        if post_data is not None:
            headers['Content-Type'] = 'application/json'

        # 1. Attempt with curl_cffi for realistic browser TLS fingerprinting
        try:
            from curl_cffi import requests as c_req
            if post_data is not None:
                resp = c_req.post(
                    url,
                    json=post_data,
                    headers=headers,
                    cookies=YOUTUBE_COOKIES,
                    proxies=proxies,
                    timeout=15,
                    impersonate="chrome124"
                )
            else:
                resp = c_req.get(
                    url,
                    headers=headers,
                    cookies=YOUTUBE_COOKIES,
                    proxies=proxies,
                    timeout=15,
                    impersonate="chrome124"
                )
            if resp.status_code == 429:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", resp.headers, None)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            pass
        except urllib.error.HTTPError:
            raise
        except Exception:
            pass

        # 2. Standard requests fallback with cookies & proxy
        try:
            if post_data is not None:
                resp = requests.post(
                    url,
                    json=post_data,
                    headers=headers,
                    cookies=YOUTUBE_COOKIES,
                    proxies=proxies,
                    timeout=15
                )
            else:
                resp = requests.get(
                    url,
                    headers=headers,
                    cookies=YOUTUBE_COOKIES,
                    proxies=proxies,
                    timeout=15
                )
            if resp.status_code == 429:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", resp.headers, None)
            resp.raise_for_status()
            return resp.text
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            if "429" in str(e):
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
            raise

    def check_channel_streams(self, channel_url=None):
        raw_url = channel_url or self.target_url
        streams_url = clean_channel_url(raw_url)

        try:
            html = self.fetch_url(streams_url)
        except Exception as e:
            return {"is_live": False, "active_stream": None, "recent_streams": [], "error": str(e)}
        
        data_match = re.search(r'var ytInitialData = ({.*?});</script>', html) or re.search(r'ytInitialData = ({.*?});', html)
        if not data_match:
            return {"is_live": False, "active_stream": None, "recent_streams": []}
        
        try:
            yt_data = json.loads(data_match.group(1))
        except Exception:
            return {"is_live": False, "active_stream": None, "recent_streams": []}

        tabs = yt_data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
        streams_tab = None
        for t in tabs:
            tab_r = t.get("tabRenderer", {})
            if "live" in tab_r.get("title", "").lower() or tab_r.get("selected", False):
                streams_tab = tab_r
                break
        
        if not streams_tab and len(tabs) > 2:
            streams_tab = tabs[2].get("tabRenderer", {})

        contents = streams_tab.get("content", {}).get("richGridRenderer", {}).get("contents", []) if streams_tab else []
        active_live = None
        recent_streams = []

        for item in contents:
            lockup = item.get("richItemRenderer", {}).get("content", {}).get("lockupViewModel", {})
            if not lockup:
                v_rend = item.get("richItemRenderer", {}).get("content", {}).get("videoRenderer", {})
                if v_rend:
                    vid_id = v_rend.get("videoId")
                    title = v_rend.get("title", {}).get("runs", [{}])[0].get("text", "")
                    badges = [b.get("metadataBadgeRenderer", {}).get("label", "") for b in v_rend.get("badges", [])]
                    is_currently_live = "LIVE" in badges
                    stream_info = {"videoId": vid_id, "title": title, "is_live": is_currently_live, "badges": badges}
                    recent_streams.append(stream_info)
                    if is_currently_live and not active_live:
                        active_live = stream_info
                continue

            content_id = lockup.get("contentId")
            metadata = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
            title = metadata.get("title", {}).get("content", "")
            
            badges = []
            is_currently_live = False
            overlays = lockup.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
            for ov in overlays:
                b_list = ov.get("thumbnailBottomOverlayViewModel", {}).get("badges", [])
                for b in b_list:
                    badge_vm = b.get("thumbnailBadgeViewModel", {})
                    text = badge_vm.get("text", "")
                    style = badge_vm.get("badgeStyle", "")
                    badges.append(text)
                    if "LIVE" in str(text).upper() or "LIVE" in str(style).upper():
                        is_currently_live = True

            stream_info = {
                "videoId": content_id,
                "title": title,
                "is_live": is_currently_live,
                "badges": badges
            }
            recent_streams.append(stream_info)
            if is_currently_live and not active_live:
                active_live = stream_info

        return {
            "is_live": active_live is not None,
            "active_stream": active_live,
            "recent_streams": recent_streams
        }

    def init_video_chat(self, video_id):
        try:
            self.video_id = video_id
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            html = self.fetch_url(watch_url)

            api_key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
            if api_key_match:
                self.api_key = api_key_match.group(1)
                
            cv_match = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
            if cv_match:
                self.client_version = cv_match.group(1)

            data_match = re.search(r'var ytInitialData = ({.*?});</script>', html) or re.search(r'ytInitialData = ({.*?});', html)
            if not data_match:
                return False

            try:
                yt_data = json.loads(data_match.group(1))
            except Exception:
                return False

            is_live_status = '"isLive":true' in html or '"isLiveNow":true' in html
            self.is_live = is_live_status

            conv_bar = yt_data.get("contents", {}).get("twoColumnWatchNextResults", {}).get("conversationBar", {})
            live_chat_rend = conv_bar.get("liveChatRenderer")
            
            if not live_chat_rend:
                return False

            self.is_replay = live_chat_rend.get("isReplay", not is_live_status)

            conts = live_chat_rend.get("continuations", [])
            for c in conts:
                for k, v in c.items():
                    if "continuation" in v:
                        self.continuation = v["continuation"]
                        break

            if not self.continuation:
                sub_menu = live_chat_rend.get("header", {}).get("liveChatHeaderRenderer", {}).get("viewSelector", {}).get("sortFilterSubMenuRenderer", {})
                items = sub_menu.get("subMenuItems", [])
                for item in items:
                    cont_data = item.get("continuation", {}).get("reloadContinuationData", {})
                    if cont_data.get("continuation"):
                        self.continuation = cont_data.get("continuation")
                        break

            return self.continuation is not None
        except Exception as e:
            add_log(f"⚠️ Error initializing live chat for stream {video_id}: {e}")
            return False

    def fetch_chat_batch(self):
        if not self.continuation or not self.api_key:
            return [], None

        endpoint = "get_live_chat_replay" if self.is_replay else "get_live_chat"
        url = f"https://www.youtube.com/youtubei/v1/live_chat/{endpoint}?key={self.api_key}"

        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": self.client_version,
                    "hl": "en",
                    "gl": "US"
                }
            },
            "continuation": self.continuation
        }

        try:
            resp_str = self.fetch_url(url, post_data=payload)
            data = json.loads(resp_str)
        except Exception:
            return [], None

        continuation_contents = data.get("continuationContents", {}).get("liveChatContinuation", {})
        actions = continuation_contents.get("actions", [])
        
        conts = continuation_contents.get("continuations", [])
        next_cont = None
        time_until_next = 1000 if self.is_replay else 2000

        for c in conts:
            for k, v in c.items():
                if "continuation" in v:
                    next_cont = v["continuation"]
                if "timeoutMs" in v:
                    time_until_next = v["timeoutMs"]
                if "timeUntilLastMessageMsec" in v:
                    time_until_next = min(v["timeUntilLastMessageMsec"], 1500)
        
        self.continuation = next_cont

        parsed_messages = []
        for action in actions:
            item = action.get("replayChatItemAction", {}).get("actions", [{}])[0] if "replayChatItemAction" in action else action
            add_item = item.get("addChatItemAction", {}).get("item", {})
            
            text_renderer = add_item.get("liveChatTextMessageRenderer")
            paid_renderer = add_item.get("liveChatPaidMessageRenderer")
            membership_renderer = add_item.get("liveChatMembershipItemRenderer")
            
            renderer = text_renderer or paid_renderer or membership_renderer
            if not renderer:
                continue

            author_name = renderer.get("authorName", {}).get("simpleText", "")
            author_id = renderer.get("authorExternalChannelId", "")
            badges = [b.get("liveChatAuthorBadgeRenderer", {}).get("tooltip", "") for b in renderer.get("authorBadges", [])]
            
            runs = renderer.get("message", {}).get("runs", [])
            message_text = "".join([r.get("text", "") or r.get("emoji", {}).get("shortcuts", [""])[0] for r in runs])
            timestamp_usec = renderer.get("timestampUsec", "0")
            
            try:
                dt = datetime.fromtimestamp(int(timestamp_usec) / 1_000_000).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            purchase_amount = paid_renderer.get("purchaseAmountText", {}).get("simpleText") if paid_renderer else None

            parsed_messages.append({
                "timestamp": dt,
                "timestamp_usec": timestamp_usec,
                "author_name": author_name,
                "author_id": author_id,
                "badges": badges,
                "message": message_text,
                "purchase_amount": purchase_amount
            })

        return parsed_messages, time_until_next

    def stream_chat(self, filter_author=None, filter_text=None, callback=None, channel_label=None, stop_event=None, stream_url=None):
        seen_message_keys = set()
        filter_author_clean = filter_author.strip().lstrip('@').lower() if filter_author else None
        
        # Support string, list, or tuple of filter substrings
        if isinstance(filter_text, (list, tuple, set)):
            filter_texts_clean = [ft.strip().lower() for ft in filter_text if ft]
        elif filter_text:
            filter_texts_clean = [filter_text.strip().lower()]
        else:
            filter_texts_clean = []

        filter_display = ", ".join(filter_texts_clean) if filter_texts_clean else "*"
        add_log(f"📺 [{channel_label}] Streaming live chat | Filter: Author '{filter_author or '*'}' | Text '{filter_display}'")

        while self.continuation:
            if stop_event and stop_event.is_set():
                break

            messages, wait_ms = self.fetch_chat_batch()
            for msg in messages:
                msg_key = f"{msg['author_id']}_{msg['timestamp_usec']}_{msg['message']}"
                if msg_key in seen_message_keys:
                    continue
                seen_message_keys.add(msg_key)

                # Filter by author name/handle or tooltip badges
                match_author = True
                if filter_author_clean:
                    author_name_norm = msg['author_name'].lower().replace('@', '').strip()
                    badge_texts = " ".join(msg['badges']).lower()
                    match_author = (filter_author_clean in author_name_norm) or (filter_author_clean in badge_texts)

                # Filter by keyword or substring in message
                match_text = True
                if filter_texts_clean:
                    msg_lower = msg['message'].lower()
                    match_text = any(ft in msg_lower for ft in filter_texts_clean)

                if match_author and match_text:
                    msg['channel_label'] = channel_label or ''
                    msg['stream_url'] = stream_url or (f"https://www.youtube.com/watch?v={self.video_id}" if self.video_id else "")
                    if callback:
                        callback(msg)

            if not self.continuation:
                add_log(f"📺 [{channel_label}] End of YouTube live chat stream.")
                break

            sleep_sec = max(0.5, (wait_ms or 1500) / 1000.0)
            time.sleep(sleep_sec)

def dispatch_yt_match(rule, msg):
    """Processes matched message from YouTube Live Chat and sends only the code/message to Discord Webhook."""
    ch_label = rule.get("name") or "YouTube Live"
    message_text = msg.get("message", "").strip()
    author_name = msg.get("author_name", "Author")

    # Skip default promo messages (e.g. USE CODE "MATCH" FOR THE BEST DISCOUNT)
    skip_keywords = rule.get("yt_skip_keywords", [])
    if skip_keywords:
        msg_lower = message_text.lower()
        if any(sk.lower() in msg_lower for sk in skip_keywords):
            add_log(f"🛡️ [{ch_label}] Skipped default promo message: '{message_text}'")
            return

    # Skip messages containing any of the configured skip URLs
    skip_urls = rule.get("yt_skip_urls", [])
    if skip_urls:
        msg_lower = message_text.lower()
        if any(su.lower() in msg_lower for su in skip_urls):
            add_log(f"🛡️ [{ch_label}] Skipped message with blocked URL: '{message_text}'")
            return

    found_urls = extract_general_urls(message_text)

    add_log(f"🔥 [YT MATCH - {ch_label}] {author_name}: {message_text}")

    mention_everyone = rule.get("mention_everyone", False)
    content = f"@everyone\n{message_text}" if mention_everyone else message_text

    include_channel_link = rule.get("include_channel_link", False) or rule.get("name") == "MyFundedFutures Monitor"
    yt_channel_url = rule.get("youtube_url")
    if include_channel_link and yt_channel_url:
        content = f"{content}\n\n📺 YouTube Channel: {yt_channel_url}"

    payload = {
        "content": content
    }
    if mention_everyone:
        payload["allowed_mentions"] = {"parse": ["everyone"]}

    # Dispatch to Discord Webhook
    webhook_url = rule.get("webhook_url")
    if webhook_url:
        try:
            res = requests.post(webhook_url, json=payload, timeout=10)
            if res.status_code in [200, 204]:
                add_log(f"✅ [{ch_label}] Code delivered to Discord webhook: {content}")
            else:
                add_log(f"⚠️ [{ch_label}] Webhook response: {res.status_code} - {res.text}")
        except Exception as e:
            add_log(f"❌ [{ch_label}] Error sending webhook: {e}")

    # Auto-Open in Browser
    if AUTO_OPEN_BROWSER and found_urls:
        for u in found_urls:
            try:
                webbrowser.open(u)
                add_log(f"🌐 [{ch_label}] Auto-opened link in browser: {u}")
            except Exception as e:
                add_log(f"⚠️ [{ch_label}] Could not open browser: {e}")

    # ntfy Push Alarm for configured keyword (e.g. "https://forms", "https://docs")
    ntfy_kws = rule.get("ntfy_keywords") or ([rule["ntfy_keyword"]] if rule.get("ntfy_keyword") else [])
    if not ntfy_kws and rule.get("name") == "MyFundedFutures Monitor":
        ntfy_kws = ["https://forms", "https://docs.g"]

    if any(kw.lower() in message_text.lower() for kw in ntfy_kws):
        if ENABLE_NTFY and NTFY_TOPIC:
            form_url = next((u for u in found_urls if any(k in u.lower() for k in ["form", "doc"])), found_urls[0] if found_urls else msg.get("stream_url"))
            ntfy_title = f"🚨 {ch_label}: FORM / DOC LINK DETECTED!"
            ntfy_msg = f"{author_name} posted a form/doc link in {ch_label} stream!\n\n{message_text}"
            trigger_ntfy_alarm(
                topic=NTFY_TOPIC,
                title=ntfy_title,
                message_text=ntfy_msg,
                click_url=form_url,
                count=5,
                delay=2.0
            )
            add_log(f"🔔 [{ch_label}] Triggered ntfy alarm for form/doc link: {form_url or message_text}")

def monitor_yt_channel(rule, poll_interval=None, stop_event=None):
    """Background worker for a single YouTube channel with exponential backoff on 429."""
    if poll_interval is None:
        poll_interval = YOUTUBE_POLL_INTERVAL

    ch_url = rule.get("youtube_url")
    if not ch_url:
        return
    ch_name = rule.get("name", "Target")
    filter_author = rule.get("yt_filter_author")
    filter_text = (
        rule.get("yt_filter_substrings")
        or rule.get("yt_filter_keywords")
        or rule.get("yt_filter_keyword")
        or rule.get("yt_filter_substring")
        or rule.get("yt_filter_text")
    )

    client = YouTubeLiveChatClient(ch_url)
    add_log(f"📺 [YT Monitor Started] {ch_name} ({ch_url}) | Filter Author: {filter_author or 'Any'} | Match: '{filter_text or '*'}'")

    current_backoff = 0

    while not (stop_event and stop_event.is_set()):
        try:
            status = client.check_channel_streams(ch_url)
            err = status.get("error", "")
            if err and "429" in err:
                current_backoff = min(300, max(30, current_backoff * 2 if current_backoff else 30))
                add_log(f"⏳ [{ch_name}] YouTube rate-limited (HTTP 429). Cooling down for {current_backoff}s to avoid IP ban...")
                for _ in range(current_backoff):
                    if stop_event and stop_event.is_set():
                        break
                    time.sleep(1)
                continue

            # Reset backoff upon successful status check
            current_backoff = 0

            if status.get("is_live") and status.get("active_stream"):
                active_stream = status["active_stream"]
                video_id = active_stream["videoId"]
                stream_url = f"https://www.youtube.com/watch?v={video_id}"
                add_log(f"🔴 [YT STREAM LIVE DETECTED!] {ch_name} -> {stream_url} ('{active_stream.get('title')}')")
                
                chat_client = YouTubeLiveChatClient(stream_url)
                if chat_client.init_video_chat(video_id):
                    chat_client.stream_chat(
                        filter_author=filter_author,
                        filter_text=filter_text,
                        callback=lambda msg: dispatch_yt_match(rule, msg),
                        channel_label=ch_name,
                        stop_event=stop_event,
                        stream_url=stream_url
                    )
                else:
                    add_log(f"⚠️ [{ch_name}] Stream is live but chat is unavailable. Waiting 25s before re-checking.")
                    time.sleep(25)
        except Exception as e:
            if "429" in str(e):
                current_backoff = min(300, max(30, current_backoff * 2 if current_backoff else 30))
                add_log(f"⏳ [{ch_name}] YouTube rate-limited (HTTP 429). Cooling down for {current_backoff}s...")
                for _ in range(current_backoff):
                    if stop_event and stop_event.is_set():
                        break
                    time.sleep(1)
                continue
            add_log(f"⚠️ [{ch_name}] Error polling channel: {e}")

        for _ in range(poll_interval):
            if stop_event and stop_event.is_set():
                break
            time.sleep(1)

def start_youtube_monitors():
    """Launches background threads for all configured YouTube stream rules."""
    proxy_info = f"Proxy: {YOUTUBE_PROXY}" if YOUTUBE_PROXY else "Proxy: None (direct connection)"
    add_log(f"📺 Starting YouTube Monitors (Interval: {YOUTUBE_POLL_INTERVAL}s | {proxy_info})")
    for rule in RULES:
        if rule.get("youtube_url"):
            th = threading.Thread(target=monitor_yt_channel, args=(rule, YOUTUBE_POLL_INTERVAL), daemon=True)
            th.start()

def run_syncie_process():
    """Runs syncie.py as a background subprocess without modifying syncie.py code."""
    syncie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "syncie.py")
    if os.path.exists(syncie_path):
        add_log("🚀 Launching Syncie Monitor (syncie.py)...")
        subprocess.Popen([sys.executable, syncie_path])
    else:
        add_log("⚠️ syncie.py not found in working directory.")

# Launch Background Services
threading.Thread(target=run_discord, daemon=True).start()
start_youtube_monitors()
run_syncie_process()

# Gradio Web UI for Hugging Face Space health check & status
def get_logs():
    return f"Status: {bot_status['status']}\n\n" + "\n".join(reversed(bot_status["logs"]))

with gr.Blocks(title="Discord & YouTube Notification Bot") as demo:
    gr.Markdown("# 🤖 Discord & YouTube Notification Bot Server")
    gr.Markdown("Monitors Discord bots and YouTube live streams concurrently. Dispatches matching drop links and promo codes to respective Discord Webhooks and ntfy.sh.")
    status_output = gr.Textbox(label="Live Activity Logs & Status", value=get_logs, every=2, lines=20)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

