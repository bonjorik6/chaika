# server.py
import asyncio, json, os
import websockets
from typing import Dict, Set

# room_id → set of websockets
ROOMS: Dict[str, Set[websockets.WebSocketServerProtocol]] = {}

async def handler(ws, path):
    room_id = None
    try:
        async for raw in ws:
            data = json.loads(raw)
            typ = data.get("type")

            # -------------------
            # JOIN: клиент входит в комнату
            # -------------------
            if typ == "join":
                room_id = str(data["room_id"])
                ROOMS.setdefault(room_id, set()).add(ws)
                continue

            # -------------------
            # Сигналинг: отправляем всем в той же комнате
            # -------------------
            if typ in (
                "webrtc_offer", "webrtc_answer",
                "webrtc_ice",   "webrtc_end",
                "text", "audio", "media"
            ):
                if room_id is None:
                    continue
                peers = ROOMS.get(room_id, set())
                msg = json.dumps(data)
                await asyncio.gather(*[
                    peer.send(msg)
                    for peer in peers
                    if peer is not ws
                ])
                continue

            print("Неизвестный тип:", typ)

    except websockets.ConnectionClosed:
        pass

    finally:
        # при отключении — удаляем из комнаты
        if room_id and ws in ROOMS.get(room_id, set()):
            ROOMS[room_id].remove(ws)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"WebSocket signaling on :{port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
