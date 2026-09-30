import asyncio
import json
import os
from aiohttp import web, WSMsgType

TOKEN = os.environ.get("RELAY_TOKEN", "")
MAX_MSG = 8 * 1024 * 1024

# device_id -> {"collector": ws, "central": ws}
sessions = {}

def authorized(request):
    token = request.query.get("token", "")
    return bool(TOKEN) and secrets_compare(token, TOKEN)

def secrets_compare(a, b):
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())

async def health(request):
    return web.json_response({
        "ok": True,
        "service": "Conexsul Remote Relay V4.1",
        "devices": len(sessions)
    })

async def websocket_handler(request):
    if not authorized(request):
        return web.Response(status=401, text="Unauthorized")

    role = request.query.get("role")
    device_id = request.query.get("device_id", "").strip()

    if role not in ("collector", "central") or not device_id:
        return web.Response(status=400, text="role and device_id required")

    ws = web.WebSocketResponse(
        heartbeat=25,
        max_msg_size=MAX_MSG,
        compress=False
    )
    await ws.prepare(request)

    entry = sessions.setdefault(device_id, {"collector": None, "central": None})

    old = entry.get(role)
    if old is not None and not old.closed:
        await old.close(code=4001, message=b"replaced")

    entry[role] = ws

    peer_role = "central" if role == "collector" else "collector"

    try:
        async for msg in ws:
            peer = sessions.get(device_id, {}).get(peer_role)
            if peer is None or peer.closed:
                continue

            if msg.type == WSMsgType.BINARY:
                await peer.send_bytes(msg.data)
            elif msg.type == WSMsgType.TEXT:
                await peer.send_str(msg.data)
            elif msg.type == WSMsgType.ERROR:
                break
    finally:
        current = sessions.get(device_id)
        if current and current.get(role) is ws:
            current[role] = None
        current = sessions.get(device_id)
        if current and current["collector"] is None and current["central"] is None:
            sessions.pop(device_id, None)

    return ws

app = web.Application(client_max_size=MAX_MSG)
app.router.add_get("/", health)
app.router.add_get("/ws", websocket_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)
