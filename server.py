import os,hmac,struct
from aiohttp import web,WSMsgType
TOKEN=os.environ.get('RELAY_TOKEN','');MAX_MSG=8*1024*1024;collectors={};central=None
def ok(req):return bool(TOKEN) and hmac.compare_digest(req.query.get('token',''),TOKEN)
async def health(req):return web.json_response({'ok':True,'service':'Conexsul Remote Relay V4.1 HUB','devices':len(collectors),'central':central is not None and not central.closed})
async def ws_handler(req):
 global central
 if not ok(req):return web.Response(status=401,text='Unauthorized')
 role=req.query.get('role');did=req.query.get('device_id','').strip();ws=web.WebSocketResponse(heartbeat=25,max_msg_size=MAX_MSG,compress=False);await ws.prepare(req)
 if role=='central':
  if central and not central.closed:await central.close(code=4001,message=b'replaced')
  central=ws
 elif role=='collector' and did:
  old=collectors.get(did)
  if old and not old.closed:await old.close(code=4001,message=b'replaced')
  collectors[did]=ws
 else:await ws.close(code=4000,message=b'bad role');return ws
 try:
  async for msg in ws:
   if role=='collector' and msg.type==WSMsgType.BINARY and central and not central.closed:
    ident=did.encode();await central.send_bytes(struct.pack('>H',len(ident))+ident+msg.data)
   elif role=='central' and msg.type==WSMsgType.TEXT:
    import json
    try:o=json.loads(msg.data);target=o.pop('device_id','');peer=collectors.get(target); 
    except Exception:continue
    if peer and not peer.closed:await peer.send_str(json.dumps(o,separators=(',',':')))
 finally:
  if role=='central' and central is ws:central=None
  if role=='collector' and collectors.get(did) is ws:collectors.pop(did,None)
 return ws
app=web.Application(client_max_size=MAX_MSG);app.router.add_get('/',health);app.router.add_get('/ws',ws_handler)
if __name__=='__main__':web.run_app(app,host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
