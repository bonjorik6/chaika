# server.py
import os
import json
import asyncio
import websockets
from websockets.exceptions import ConnectionClosed

# Хранилище: nick → websocket
clients: dict[str, websockets.WebSocketServerProtocol] = {}

async def handler(ws: websockets.WebSocketServerProtocol, path):
    """
    1) Ждём первого сообщения: {"type":"register","from": "<nick>"}.
    2) Сохраняем nick→ws.
    3) Дальше любая data с type in {"text","file","voice"} рассылается всем остальным.
    4) Печатаем в консоль каждое приходящее.
    """
    nick = None
    try:
        # 1. регистрация
        raw = await ws.recv()
        init = json.loads(raw)
        if init.get("type") != "register" or "from" not in init:
            await ws.close(1008, "Must register first")
            return

        nick = init["from"]
        clients[nick] = ws
        print(f"[+] Registered: {nick}")

        # 2. основной цикл
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                print("[!] Received non-JSON message")
                continue

            typ     = msg.get("type")
            sender  = msg.get("from")
            room_id = msg.get("room_id")
            to_user = msg.get("to", None)

            # печатаем в консоль
            print(f"⌞ {typ} from={sender!r} to={to_user!r} room={room_id!r} payload={msg}")

            # если это чат-тип — шлём всем остальным
            if typ in ("text", "file", "voice"):
                # адресно (если указан) или всем остальным онлайн
                targets = []
                if to_user and to_user in clients:
                    targets = [clients[to_user]]
                else:
                    targets = [ws2 for nick2, ws2 in clients.items() if ws2 is not ws]

                await asyncio.gather(
                    *(ws2.send(raw) for ws2 in targets),
                    return_exceptions=True
                )
            else:
                # не-чатовые типы можно добавить сюда
                print(f"[i] Ignored message type: {typ}")

    except ConnectionClosed:
        print(f"[-] Disconnected: {nick}")
    finally:
        if nick and clients.get(nick) is ws:
            del clients[nick]

async def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"🔈 Starting server on port {port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
