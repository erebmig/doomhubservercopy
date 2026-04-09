import discord
import asyncio
import threading
import aiohttp
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
logs = ["> SYSTEM INITIALIZED... READY TO PURGE."]

def add_log(text):
    logs.append(text)
    if len(logs) > 50: logs.pop(0)

async def start_cloning_process(token, src_id, tgt_id):
    client = discord.Client()

    @client.event
    async def on_ready():
        add_log(f"> AUTHENTICATED AS: {client.user}")
        source = client.get_guild(int(src_id))
        target = client.get_guild(int(tgt_id))

        if not source or not target:
            add_log("> ERROR: GUILD ACCESS DENIED."); await client.close(); return

        add_log(f"> TARGETING: {source.name}")
        
        # Metadata & Assets
        try:
            settings = {"name": source.name, "verification_level": source.verification_level}
            async with aiohttp.ClientSession() as session:
                if source.icon:
                    async with session.get(source.icon.url) as r: settings["icon"] = await r.read()
                if source.banner:
                    async with session.get(source.banner.url) as r: settings["banner"] = await r.read()
            await target.edit(**settings)
            add_log("> ASSETS SYNCED.")
        except: pass

        # Purge
        add_log("> PURGING CHANNELS...")
        await asyncio.gather(*[ch.delete() for ch in target.channels], return_exceptions=True)

        # Roles
        add_log("> REPLICATING HIERARCHY...")
        role_map = {}
        for r in reversed(source.roles):
            if r.name == "@everyone":
                role_map[r] = target.default_role
                try: await target.default_role.edit(permissions=r.permissions)
                except: pass
            elif not r.managed:
                try:
                    nr = await target.create_role(name=r.name, permissions=r.permissions, color=r.color, hoist=r.hoist)
                    role_map[r] = nr
                except: pass

        # Full Channel & Perm Sync
        async def create_ch(ch, cat=None):
            ovs = {role_map[ro]: o for ro, o in ch.overwrites.items() if ro in role_map}
            try:
                if isinstance(ch, discord.TextChannel):
                    await target.create_text_channel(name=ch.name, category=cat, overwrites=ovs, topic=ch.topic, nsfw=ch.nsfw, slowmode_delay=ch.slowmode_delay)
                elif isinstance(ch, discord.VoiceChannel):
                    await target.create_voice_channel(name=ch.name, category=cat, overwrites=ovs, user_limit=ch.user_limit, bitrate=ch.bitrate)
            except: pass

        for category in source.categories:
            cat_ovs = {role_map[r]: o for r, o in category.overwrites.items() if r in role_map}
            try:
                new_cat = await target.create_category(name=category.name, overwrites=cat_ovs)
                for ch in category.channels: await create_ch(ch, new_cat)
            except: pass

        for ch in source.channels:
            if ch.category is None: await create_ch(ch)

        add_log("> CLONING EMOJIS...")
        for emoji in source.emojis:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(emoji.url) as r:
                        await target.create_custom_emoji(name=emoji.name, image=await r.read())
            except: pass

        add_log("> OPERATION SUCCESSFUL. SYSTEM STANDBY.")
        await client.close()

    try: await client.start(token)
    except: add_log("> TOKEN EXPIRED OR INVALID.")

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/clone', methods=['POST'])
def run_clone():
    data = request.json
    threading.Thread(target=lambda: asyncio.run(start_cloning_process(data['token'], data['source'], data['target']))).start()
    return jsonify({"status": "fired"})

@app.route('/api/logs')
def get_logs(): return jsonify({"logs": logs})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
