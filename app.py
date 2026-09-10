import os
import threading
import time
import gradio as gr
import discord
import requests

# ----------------- CONFIGURATION -----------------
USER_TOKEN = os.getenv("USER_TOKEN", "MTQyODgxNjc4NjExMDgwODA4OA.G9HpLn.628LK5VAhWFrl5-pm-3wyZbamyvvMjyeKNMWD8")

RULES = [
    {
        "name": "Bot 274561010600509450 Monitor",
        "bot_id": 274561010600509450,
        "channel_ids": [1493168400837382196, 1541483457694400563],
        "webhook_url": "https://discord.com/api/webhooks/1547448491213594755/Vrfgd8X0WzoiRWno3Z26P84In7r2jhY0DqPsJBv1oCqDrvBxt_-MjfcTd17wZn_yGI10",
    },
    {
        "name": "Bot 1219234102302212166 Monitor",
        "bot_id": 1219234102302212166,
        "channel_ids": [1463611205116625154],
        "webhook_url": "https://discord.com/api/webhooks/1547472423006507098/zq-0aHRGDIwYbwrziWFOblzQwbH4BluvpcxXxsDdK3mov9HWcw6juC9zLJ8LZUM75tYi",
    },
    {
        "name": "Bot 1454107099968700620 Monitor",
        "bot_id": 1454107099968700620,
        "channel_ids": [1493970397320712213],
        "webhook_url": "https://discord.com/api/webhooks/1547473124121911328/3n6CWzGyACF2kbOGA4n2Gxk9axi9O6G9bqqb9Si-4sYx1Mju9GcYhNByToKh8b1crhMO",
    },
]
# -------------------------------------------------

bot_status = {"status": "Starting...", "logs": []}

def add_log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    log_entry = f"{timestamp} {msg}"
    print(log_entry)
    bot_status["logs"].append(log_entry)
    if len(bot_status["logs"]) > 100:
        bot_status["logs"].pop(0)

client = discord.Client()

@client.event
async def on_ready():
    add_log(f"Successfully logged in as: {client.user}")
    for idx, rule in enumerate(RULES, 1):
        add_log(f"Rule #{idx} Active: Bot {rule['bot_id']} -> Channels {rule['channel_ids']}")
    bot_status["status"] = f"Online as {client.user}"

@client.event
async def on_message(message):
    for rule in RULES:
        if message.author.id == rule["bot_id"] and message.channel.id in rule["channel_ids"]:
            add_log(f"Match found! Bot {message.author.name} posted in #{getattr(message.channel, 'name', 'channel')}")

            content = message.content if message.content else "[Bot sent an Embed or Attachment]"

            embed_parts = []
            for emb in message.embeds:
                if emb.title:
                    embed_parts.append(f"**{emb.title}**")
                if emb.description:
                    embed_parts.append(emb.description)
                for field in emb.fields:
                    embed_parts.append(f"• **{field.name}**: {field.value}")

            if embed_parts:
                content += "\n\n" + "\n".join(embed_parts)

            payload = {
                "content": "@everyone 🚨 **Target Bot Sent a Message!**",
                "embeds": [
                    {
                        "title": f"New Bot Message in #{getattr(message.channel, 'name', 'channel')}",
                        "description": content[:4000],
                        "url": message.jump_url,
                        "color": 0x5865F2,
                        "fields": [
                            {
                                "name": "Jump to Message",
                                "value": f"[Click here to view in Discord]({message.jump_url})",
                                "inline": False
                            }
                        ],
                        "footer": {
                            "text": f"Bot: {message.author.name} ({message.author.id})"
                        }
                    }
                ]
            }

            try:
                res = requests.post(rule["webhook_url"], json=payload)
                if res.status_code in [200, 204]:
                    add_log(f"Alert sent to webhook for Bot {rule['bot_id']}!")
                else:
                    add_log(f"Webhook error: {res.status_code} - {res.text}")
            except Exception as e:
                add_log(f"Error sending webhook: {e}")

def run_discord():
    while True:
        try:
            client.run(USER_TOKEN)
        except Exception as e:
            add_log(f"Discord error: {e}. Reconnecting in 10s...")
            time.sleep(10)

# Start Discord listener thread
threading.Thread(target=run_discord, daemon=True).start()

# Gradio Web UI for Hugging Face Space health check & status
def get_logs():
    return f"Status: {bot_status['status']}\n\n" + "\n".join(reversed(bot_status["logs"]))

with gr.Blocks(title="Discord Notification Bot") as demo:
    gr.Markdown("# 🤖 Discord Notification Bot Server")
    status_output = gr.Textbox(label="Live Logs & Status", value=get_logs, every=3, lines=15)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
