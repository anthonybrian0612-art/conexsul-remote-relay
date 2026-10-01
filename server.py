import os,hmac,struct,json
from aiohttp import web,WSMsgType
TOKEN=os.environ.get('RELAY_TOKEN','');MAX_MSG=8*1024*1024
collectors={};collector_hello={};central=None

def ok(req):
 return bool(TOKEN) and hmac.compare_digest(req.query.get('token',''),TOKEN)

def wrap(did,data):
 ident=did.encode('utf-8');return struct.pack('>H',len(ident))+ident+data

async def health(req):
 return web.json_response({'ok':True,'service':'Conexsul Remote Relay V4.2 HUB','devices':len(collectors),'central':central is not None and not central.closed})

async def ws_handler(req):
 global central
 if not ok(req):return web.Response(status=401,text='Unauthorized')
 role=req.query.get('role');did=req.query.get('device_id','').strip()
 ws=web.WebSocketResponse(heartbeat=25,max_msg_size=MAX_MSG,compress=False);await ws.prepare(req)
 if role=='central':
  if central and not central.closed:await central.close(code=4001,message=b'replaced')
  central=ws
  # Reenvia imediatamente a identificação de todos os coletores que já estavam online.
  for cid,hello in list(collector_hello.items()):
   peer=collectors.get(cid)
   if peer is not None and not peer.closed:
    try:await ws.send_bytes(wrap(cid,hello))
    except Exception:pass
 elif role=='collector' and did:
  old=collectors.get(did)
  if old and not old.closed:await old.close(code=4001,message=b'replaced')
  collectors[did]=ws
 else:
  await ws.close(code=4000,message=b'bad role');return ws
 try:
  async for msg in ws:
   if role=='collector' and msg.type==WSMsgType.BINARY:
    data=bytes(msg.data)
    # kind 1 = HELLO/metadados. Mantém em cache para uma Central que conectar depois.
    if data and data[0]==1:collector_hello[did]=data
    if central and not central.closed:await central.send_bytes(wrap(did,data))
   elif role=='central' and msg.type==WSMsgType.TEXT:
    try:
     o=json.loads(msg.data);target=o.pop('device_id','');peer=collectors.get(target)
    except Exception:continue
    if peer and not peer.closed:await peer.send_str(json.dumps(o,separators=(',',':')))
 finally:
  if role=='central' and central is ws:central=None
  if role=='collector' and collectors.get(did) is ws:
   collectors.pop(did,None);collector_hello.pop(did,None)
 return ws

app=web.Application(client_max_size=MAX_MSG);app.router.add_get('/',health);app.router.add_get('/ws',ws_handler)
if __name__=='__main__':web.run_app(app,host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
