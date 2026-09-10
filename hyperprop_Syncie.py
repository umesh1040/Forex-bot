import discord
import requests

# ----------------- CONFIGURATION -----------------
USER_TOKEN = "MTQyODgxNjc4NjExMDgwODA4OA.G9HpLn.628LK5VAhWFrl5-pm-3wyZbamyvvMjyeKNMWD8"

RULES = [
    {
        "name": "Bot 1499804063712411738 Monitor",
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

client = discord.Client()

@client.event
async def on_ready():
    print("=" * 60)
    print(f"✅ Successfully logged in as: {client.user}")
    for idx, rule in enumerate(RULES, 1):
        print(f"📡 Rule #{idx}: Bot {rule['bot_id']} -> Channels {rule['channel_ids']}")
    print("=" * 60)
    print("Listening for messages... (Keep this window open)")

@client.event
async def on_message(message):
    for rule in RULES:
        # Check if the message is from the rule's target bot and in one of its target channels
        if message.author.id == rule["bot_id"] and message.channel.id in rule["channel_ids"]:
            print(f"\n🚨 [MATCH FOUND] Bot {message.author.name} posted in #{getattr(message.channel, 'name', 'general')}!")

            content = message.content if message.content else "[Bot sent an Embed or Attachment]"

            # Parse embed contents if the bot uses rich embeds
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

            # Discord notification payload
            payload = {
                "content": "@everyone 🚨 **Target Bot Sent a Message!**",
                "embeds": [
                    {
                        "title": f"New Bot Message in #{getattr(message.channel, 'name', 'channel')}",
                        "description": content[:4000],  # discord character limit
                        "url": message.jump_url,
                        "color": 0x5865F2,  # Discord blurple
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
                    print(f"✅ Alert sent to webhook for Bot {rule['bot_id']}!")
                else:
                    print(f"⚠️ Webhook response: {res.status_code} - {res.text}")
            except Exception as e:
                print(f"❌ Error sending webhook: {e}")

if __name__ == "__main__":
    client.run(USER_TOKEN)
