import os, json, asyncio
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncpg
import uvicorn

DATABASE_URL = os.getenv("DATABASE_URL")  # обязательно настроить в Railway
PORT         = int(os.getenv("PORT", 8000))

app = FastAPI()
DB_POOL: asyncpg.Pool = None
ROOMS: Dict[str, Set[WebSocket]] = {}

@app.on_event("startup")
async def on_startup():
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    room_id = None
    call_id = None
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            t = data.get("type")

            if t == "join":
                room_id = str(data["room_id"])
                ROOMS.setdefault(room_id, set()).add(ws)
                continue

            peers = ROOMS.get(room_id, set())

            if t == "webrtc_offer":
                call_id   = data["call_id"]
                initiator = data["initiator"]
                recipient = data["recipient"]
                # пишем в БД
                await DB_POOL.execute(
                    "INSERT INTO calls(room_id, initiator, recipient, status, created_at) "
                    "VALUES($1,$2,$3,'calling',now())",
                    int(room_id), initiator, recipient
                )
                # ретранслируем
                msg = json.dumps(data)
                await asyncio.gather(*[p.send_text(msg) for p in peers if p is not ws])
                continue

            if t in ("webrtc_answer", "webrtc_ice"):
                msg = json.dumps(data)
                await asyncio.gather(*[p.send_text(msg) for p in peers if p is not ws])
                continue

            if t == "webrtc_end":
                duration = float(data.get("duration", 0))
                await DB_POOL.execute(
                    "UPDATE calls SET ended_at=now(), duration=$1, status='ended' WHERE call_id=$2",
                    duration, data["call_id"]
                )
                msg = json.dumps(data)
                await asyncio.gather(*[p.send_text(msg) for p in peers if p is not ws])
                continue

            # прочие (text, file, voice, media)
            if t in ("text", "file", "voice", "media"):
                msg = json.dumps(data)
                await asyncio.gather(*[p.send_text(msg) for p in peers if p is not ws])
                continue

    except WebSocketDisconnect:
        pass
    finally:
        if room_id and ws in ROOMS.get(room_id, set()):
            ROOMS[room_id].remove(ws)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=PORT)
