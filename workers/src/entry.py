"""
VANTA — Cloudflare Workers 權威遊戲伺服器（WebSocket + Durable Object）
========================================================================
架構：

  Godot / 瀏覽器客戶端 (WebSocket, binary frames)
      │  /ws?match=<name>&ai=1&seed=42
      ▼
  Default (WorkerEntrypoint)  ── getByName(match) ──►  MatchDO（每場比賽一個實例）
                                                         │
                                                         ▼
                                          MatchHost（確定性模擬核心，見 match_host.py）

協定與本地 UDP 版完全相容：封包格式沿用 server/netcode/protocol.py，
只是改走 WebSocket binary frames。反作弊 / Rollback / 去重 / 快照廣播
全部由 GameServer 原樣處理。

部署：bash scripts/build.sh  （複製 server/ → src/server 後 pywrangler deploy）
"""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from js import Object, WebSocketPair
from pyodide.ffi import to_js
from workers import DurableObject, Response, WorkerEntrypoint

from match_host import MatchHost

ALARM_INTERVAL_MS = 1000          # 閒置時的補步喚醒間隔（沒人輸入也要推進模擬）

INDEX_HTML = """<!doctype html>
<html lang="zh-Hant"><meta charset="utf-8"><title>VANTA — 伺服器測試台</title>
<body style="font-family:monospace;background:#111;color:#0f0;padding:16px">
<h2>VANTA Workers 權威伺服器</h2>
<label>match: <input id="m" value="demo"></label>
<label>AI: <input id="ai" type="checkbox" checked></label>
<button onclick="go()">連線</button>
<div id="log"></div>
<script>
const MAGIC=0x56, T_INPUT=0x01, T_SNAPSHOT=0x02, T_WELCOME=0x03;
const SNAP_HDR=10, ENT=26;
function log(s){const d=document.createElement('div');d.textContent=s;document.getElementById('log').prepend(d);}
function inputPkt(netId,seq,forward,strafe,flags){
  const b=new Uint8Array(15);const v=new DataView(b.buffer);
  b[0]=MAGIC;b[1]=T_INPUT;v.setUint16(2,netId,true);v.setUint32(4,seq,true);
  v.setUint32(8,Date.now()&0xffffffff,true);
  v.setInt8(12,Math.round(Math.max(-1,Math.min(1,forward))*127));
  v.setInt8(13,Math.round(Math.max(-1,Math.min(1,strafe))*127));b[14]=flags;return b;}
function parseSnap(buf){
  const v=new DataView(buf.buffer,buf.byteOffset,buf.byteLength);
  const tick=v.getUint32(2,true);const out=[];
  for(let s=0;s<10;s++){const o=SNAP_HDR+s*ENT;const flags=buf[o+1];
    if(!(flags&8))continue;
    out.push({slot:buf[o],x:v.getInt16(o+2,true)/100,y:v.getInt16(o+4,true)/100,z:v.getInt16(o+6,true)/100,
      hp:buf[o+22],mag:buf[o+23]});}
  return {tick,players:out};}
function go(){
  const name=document.getElementById('m').value||'demo';
  const ai=document.getElementById('ai').checked?1:0;
  const proto=location.protocol==='https:'?'wss':'ws';
  const ws=new WebSocket(`${proto}://${location.host}/ws?match=${encodeURIComponent(name)}&ai=${ai}`);
  ws.binaryType='arraybuffer';
  let seq=0,last=-1;
  ws.onopen=()=>{log('已連線');setInterval(()=>{try{ws.send(inputPkt(0,seq++,0,0,0));}catch(e){}},8);};
  ws.onmessage=(ev)=>{
    const buf=new Uint8Array(ev.data);
    if(buf[1]===T_WELCOME){log(`WELCOME net_id=${buf[2]|(buf[3]<<8)} slot=${buf[4]}`);return;}
    if(buf[1]===T_SNAPSHOT){
      const s=parseSnap(buf);
      if(s.tick!==last){last=s.tick;
        log(`tick=${s.tick} players=${s.players.map(p=>p.slot+':('+p.x.toFixed(1)+','+p.z.toFixed(1)+')hp'+p.hp).join(' ')}`);}}
    else if(buf[1]===5){log(`EVENT type=${buf[2]|(buf[3]<<8)}`);}};
  ws.onclose=e=>log(`關閉 code=${e.code}`);}
</script>"""


def _to_bytes(message):
    """Workers binary WS message（ArrayBuffer / Uint8Array）→ Python bytes。"""
    if isinstance(message, (bytes, bytearray, memoryview)):
        return bytes(message)
    try:
        return bytes(message.to_py())
    except Exception:
        return bytes(bytearray(message))


class MatchDO(DurableObject):
    """一場比賽 = 一個 DO 實例（getByName(match) 確保同 match 名同一場）。"""

    def __init__(self, state, env):
        super().__init__(state, env)
        self.state = state
        self.env = env
        self._host: MatchHost | None = None
        # 連線對照：這個 runtime 每次回呼都會產生「全新」的 ws proxy
        # （is/==/id 全不可靠），唯一可靠的是 JS 端身分比較 Object.is()。
        self._conns: list = []                   # [(ws proxy, ws_id), ...]
        self._by_id: dict[int, object] = {}      # ws_id -> ws proxy

    # ------------------------------------------------------------------ #
    def _host_for(self, query: dict | None = None) -> MatchHost:
        # 若查詢帶 ?reset=1 或比賽已結束 → 重建 DO（避免舊 DO 狀態殘留）
        need_reset = self._host is not None and query and query.get("reset")
        finished = (self._host is not None
                    and self._host.world.match is not None
                    and self._host.world.match.phase.value == "finished")
        # 晚加入防呆：無人連線 → 一律重開新比賽。
        # （DO 常駐會把 AI 對戰打到屍橫遍野，晚加入的人只會看到
        #   「players 1」的空場；首位連線者永遠拿到全新的第 1 回合）
        stale = self._host is not None and self._host.session_count() == 0
        if self._host is None or need_reset or finished or stale:
            seed = 42
            ai = False
            mode = "competitive"
            if query:
                try:
                    seed = int((query.get("seed") or ["42"])[0])
                except (TypeError, ValueError):
                    seed = 42
                ai = (query.get("ai") or ["0"])[0] in ("1", "true", "yes")
                mode = (query.get("mode") or ["competitive"])[0]
            self._host = MatchHost(seed=seed, ai_mode=ai, mode=mode, on_send=self._send)
            self._conns.clear()
            self._by_id.clear()
        return self._host

    def _send(self, ws_id: int, data: bytes) -> None:
        ws = self._by_id.get(ws_id)
        if ws is not None:
            try:
                ws.send(to_js(data))             # bytes → Uint8Array binary frame
            except Exception as e:
                print(f"send err: {e}")

    def _schedule_alarm(self) -> None:
        host = self._host
        # 比賽結束且無連線 → 停止 alarm，讓閒置 DO 可被回收（省 CPU 成本）
        if host is not None and host.world.match is not None:
            finished = host.world.match.phase.value == "finished"
            if finished and host.session_count() == 0:
                try:
                    self.state.storage.deleteAlarm()
                except Exception:
                    pass
                return
        try:
            self.state.storage.setAlarm(int(time.time() * 1000) + ALARM_INTERVAL_MS)
        except Exception as e:
            print(f"alarm err: {e}")

    # ------------------------------------------------------------------ #
    async def fetch(self, request):
        if (request.headers.get("Upgrade") or "").lower() != "websocket":
            return Response(
                "VANTA match server — connect via WebSocket to /ws?match=<id>&ai=1",
                status=400)
        host = self._host_for(parse_qs(urlparse(request.url).query))
        client, server = WebSocketPair.new().object_values()
        self.state.acceptWebSocket(server)
        ws_id = host.connect()
        self._conns.append((server, ws_id))
        self._by_id[ws_id] = server
        self._schedule_alarm()
        return Response(None, status=101, web_socket=client)

    def _ws_id_for(self, ws):
        js_is = getattr(Object, "is")   # Object.is（.is 是關鍵字，Pyodide 不接受點語法）
        for stored, ws_id in self._conns:
            try:
                if js_is(stored, ws):
                    return ws_id
            except Exception:
                continue
        return None

    async def webSocketMessage(self, ws, message):
        data = _to_bytes(message)
        ws_id = self._ws_id_for(ws)
        if ws_id is None:
            return
        self._host_for().on_message(ws_id, data)
        self._schedule_alarm()

    async def webSocketClose(self, ws, code, reason, wasClean):
        ws_id = self._ws_id_for(ws)
        if ws_id is not None:
            self._conns = [(s, i) for s, i in self._conns if i != ws_id]
            self._by_id.pop(ws_id, None)
            self._host_for().on_close(ws_id)

    async def webSocketError(self, ws, error):
        try:
            ws.close(1011, "WebSocket error")
        except Exception:
            pass

    async def alarm(self, info):
        self._host_for().advance()
        self._schedule_alarm()


class Default(WorkerEntrypoint):
    """路由：/ws → 對應 match 的 MatchDO；/ → 測試台頁面。"""

    async def fetch(self, request):
        url = urlparse(request.url)
        if url.path == "/":
            return Response(INDEX_HTML, headers={"Content-Type": "text/html; charset=utf-8"})
        if url.path == "/ws":
            q = parse_qs(url.query)
            match = (q.get("match") or ["default"])[0] or "default"
            stub = self.env.MATCH.getByName(match)
            return await stub.fetch(request)
        return Response("Not Found", status=404)
