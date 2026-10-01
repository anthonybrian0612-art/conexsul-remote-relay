import os,hmac,struct,json,time
from aiohttp import web,WSMsgType

TOKEN=os.environ.get('RELAY_TOKEN','')
MAX_MSG=20*1024*1024

collectors={}
collector_hello={}
central=None

stats={
 'h264_received':0,
 'h264_forwarded':0,
 'h264_bytes_received':0,
 'h264_bytes_forwarded':0,
 'forward_errors':0,
 'last_h264_device':None,
 'last_h264_at':None,
 'last_error':None
}

def ok(req):
 return bool(TOKEN) and hmac.compare_digest(req.query.get('token',''),TOKEN)

def wrap(did,data):
 ident=did.encode('utf-8')
 return struct.pack('>H',len(ident))+ident+data

async def health(req):
 devices={}
 for did,ws in list(collectors.items()):
  devices[did]={'connected':ws is not None and not ws.closed}
 return web.json_response({
  'ok':True,
  'service':'Conexsul Remote Relay V4.3 HUB DIAG',
  'devices':len(collectors),
  'device_names':list(collectors.keys()),
  'central':central is not None and not central.closed,
  'h264_received':stats['h264_received'],
  'h264_forwarded':stats['h264_forwarded'],
  'h264_bytes_received':stats['h264_bytes_received'],
  'h264_bytes_forwarded':stats['h264_bytes_forwarded'],
  'forward_errors':stats['forward_errors'],
  'last_h264_device':stats['last_h264_device'],
  'last_h264_at':stats['last_h264_at'],
  'last_error':stats['last_error']
 })

async def ws_handler(req):
 global central
 if not ok(req):
  return web.Response(status=401,text='Unauthorized')

 role=req.query.get('role')
 did=req.query.get('device_id','').strip()

 ws=web.WebSocketResponse(
  heartbeat=25,
  max_msg_size=MAX_MSG,
  compress=False,
  autoclose=True,
  autoping=True
 )
 await ws.prepare(req)

 if role=='central':
  if central and not central.closed:
   await central.close(code=4001,message=b'replaced')
  central=ws

  # Reenvia HELLO dos coletores que já estavam conectados.
  for cid,hello in list(collector_hello.items()):
   peer=collectors.get(cid)
   if peer is not None and not peer.closed:
    try:
     await ws.send_bytes(wrap(cid,hello))
    except Exception as e:
     stats['forward_errors']+=1
     stats['last_error']='HELLO '+type(e).__name__+': '+str(e)

 elif role=='collector' and did:
  old=collectors.get(did)
  if old and not old.closed:
   await old.close(code=4001,message=b'replaced')
  collectors[did]=ws
 else:
  await ws.close(code=4000,message=b'bad role')
  return ws

 try:
  async for msg in ws:
   if role=='collector' and msg.type==WSMsgType.BINARY:
    data=bytes(msg.data)
    if not data:
     continue

    kind=data[0]

    if kind==1:
     collector_hello[did]=data

    if kind==3:
     payload_len=max(0,len(data)-1)
     stats['h264_received']+=1
     stats['h264_bytes_received']+=payload_len
     stats['last_h264_device']=did
     stats['last_h264_at']=time.strftime('%Y-%m-%d %H:%M:%S')

    if central and not central.closed:
     try:
      packet=wrap(did,data)
      await central.send_bytes(packet)
      if kind==3:
       stats['h264_forwarded']+=1
       stats['h264_bytes_forwarded']+=max(0,len(data)-1)
     except Exception as e:
      stats['forward_errors']+=1
      stats['last_error']=type(e).__name__+': '+str(e)

   elif role=='central' and msg.type==WSMsgType.TEXT:
    try:
     o=json.loads(msg.data)
     target=o.pop('device_id','')
     peer=collectors.get(target)
    except Exception:
     continue
    if peer and not peer.closed:
     await peer.send_str(json.dumps(o,separators=(',',':')))

   elif msg.type==WSMsgType.ERROR:
    stats['last_error']='WS '+str(ws.exception())

 finally:
  if role=='central' and central is ws:
   central=None
  if role=='collector' and collectors.get(did) is ws:
   collectors.pop(did,None)
   collector_hello.pop(did,None)

 return ws

app=web.Application(client_max_size=MAX_MSG)
app.router.add_get('/',health)
app.router.add_get('/ws',ws_handler)

if __name__=='__main__':
 web.run_app(app,host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
