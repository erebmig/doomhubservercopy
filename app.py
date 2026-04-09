import discord
import asyncio
import threading
import aiohttp
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
logs = ["> DOOMHUB SYSTEM ONLINE...", "> PURPLE PROTOCOL ACTIVATED."]

def add_log(text):
    logs.append(text)
    if len(logs) > 30: logs.pop(0)

async def check_token_validity(token):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/v9/users/@me", headers={"Authorization": token}) as resp:
            return resp.status == 200

async def start_cloning_process(token, src_id, tgt_id):
    client = discord.Client()

    @client.event
    async def on_ready():
        add_log(f"> AUTH SUCCESS: {client.user}")
        source = client.get_guild(int(src_id))
        target = client.get_guild(int(tgt_id))

        if not source or not target:
            add_log("> ERROR: INVALID GUILD IDS.")
            await client.close()
            return

        add_log(f"> CLONING: {source.name} -> {target.name}")

        # Wipe
        for ch in target.channels:
            try: await ch.delete(); await asyncio.sleep(0.05)
            except: pass
        
        # Roles
        role_map = {}
        for r in reversed(source.roles):
            if r.name == "@everyone" or r.managed: continue
            try:
                nr = await target.create_role(name=r.name, permissions=r.permissions, color=r.color, hoist=r.hoist)
                role_map[r] = nr
                await asyncio.sleep(0.1)
            except: pass

        # Channels
        for cat in source.categories:
            try:
                new_cat = await target.create_category(cat.name)
                for ch in cat.channels:
                    ovs = {role_map[r]: o for r, o in ch.overwrites.items() if r in role_map}
                    if isinstance(ch, discord.TextChannel):
                        await target.create_text_channel(ch.name, category=new_cat, overwrites=ovs)
                    elif isinstance(ch, discord.VoiceChannel):
                        await target.create_voice_channel(ch.name, category=new_cat, overwrites=ovs)
                    await asyncio.sleep(0.2)
            except: pass

        add_log("> OPERATION COMPLETE.")
        await client.close()

    try:
        await client.start(token)
    except:
        add_log("> FATAL: CONNECTION LOST.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check', methods=['POST'])
def check_token():
    token = request.json.get('token')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    is_valid = loop.run_until_complete(check_token_validity(token))
    return jsonify({"valid": is_valid})

@app.route('/api/clone', methods=['POST'])
def run_clone():
    data = request.json
    token, src, tgt = data.get('token'), data.get('source'), data.get('target')
    
    def run_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_cloning_process(token, src, tgt))
        
    threading.Thread(target=run_thread).start()
    return jsonify({"status": "started"})

@app.route('/api/logs')
def get_logs():
    return jsonify({"logs": logs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
