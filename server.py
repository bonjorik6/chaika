import asyncio, json, os
import websockets
import asyncpg
from typing import Dict, Set

# пул подключений к базе
DB_POOL: asyncpg.Pool = None

# room_id → { websocket, ... }
ROOMS: Dict[str, Set[websockets.WebSocketServerProtocol]] = {}

async def handler(ws, path):
    global DB_POOL
    room_id = None
    call_id = None

    await ws.send(json.dumps({"type":"hello"}))  # для проверки коннекта
    try:
        async for raw in ws:
            data = json.loads(raw)
            typ  = data.get("type")

            # ————————— JOIN —————————
            if typ == "join":
                room_id = str(data["room_id"])
                ROOMS.setdefault(room_id, set()).add(ws)
                print(f"[SERVER] client joined room {room_id}")
                continue

            # все сигналы только внутри комнаты
            peers = ROOMS.get(room_id, set())

            # ————————— OFFER —————————
            if typ == "webrtc_offer":
                call_id   = data["call_id"]
                initiator = data["initiator"]
                recipient = data["recipient"]

                # создаём запись звонка в БД
                await DB_POOL.execute(
                    """
                    INSERT INTO calls(room_id, initiator, recipient, status, created_at)
                    VALUES($1, $2, $3, 'calling', now())
                    """,
                    int(room_id), initiator, recipient
                )
                print(f"[SERVER] webrtc_offer in room {room_id}, call {call_id}")

                # рассылаем оффер всем кроме отправителя
                msg = json.dumps(data)
                await asyncio.gather(*[
                    p.send(msg) for p in peers if p is not ws
                ])
                continue

            # ————————— ANSWER / ICE —————————
            if typ in ("webrtc_answer", "webrtc_ice"):
                print(f"[SERVER] {typ} in room {room_id}, call {data.get('call_id')}")
                msg = json.dumps(data)
                await asyncio.gather(*[
                    p.send(msg) for p in peers if p is not ws
                ])
                continue

            # ————————— END —————————
            if typ == "webrtc_end":
                duration = float(data.get("duration", 0))
                # обновляем БД
                await DB_POOL.execute(
                    """
                    UPDATE calls
                    SET ended_at = now(), duration = $1, status = 'ended'
                    WHERE call_id = $2
                    """,
                    duration, data["call_id"]
                )
                print(f"[SERVER] call {data['call_id']} ended, duration={duration}")
                msg = json.dumps(data)
                await asyncio.gather(*[
                    p.send(msg) for p in peers if p is not ws
                ])
                continue

            # ————————— прочие (text, file…) —————————
            if typ in ("text", "file", "voice", "media"):
                msg = json.dumps(data)
                await asyncio.gather(*[
                    p.send(msg) for p in peers if p is not ws
                ])
                continue

            print(f"[SERVER] unknown type: {typ}")

    except websockets.ConnectionClosed:
        pass
    finally:
        # при дисконнекте убираем из room
        if room_id and ws in ROOMS.get(room_id, set()):
            ROOMS[room_id].remove(ws)

async def main():
    global DB_POOL
    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    port = int(os.getenv("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"[SERVER] listening on port {port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
