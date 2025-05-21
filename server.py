# server.py
import os
import asyncio
import json
import logging
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chat-server")

# Храним все подключённые WebSocket-соединения
connected_clients: set[websockets.WebSocketServerProtocol] = set()

async def handler(ws: websockets.WebSocketServerProtocol, path: str):
    # Добавляем нового клиента
    connected_clients.add(ws)
    logger.info(f"[+] Client connected: {ws.remote_address}")
    try:
        async for raw in ws:
            # Парсим JSON (если невалидный — пропускаем)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"[!] Received invalid JSON: {raw!r}")
                continue

            # Логгируем тип и room_id (если есть)
            logger.info(f"→ Received type={data.get('type')!r} room_id={data.get('room_id')!r}")

            # Рассылаем всем остальным клиентам
            # (они у себя в on_server_message() разберут JSON и обновят UI)
            await asyncio.gather(
                *(
                    client.send(raw)
                    for client in connected_clients
                    if client is not ws
                ),
                return_exceptions=True
            )

    except (ConnectionClosedOK, ConnectionClosedError) as e:
        logger.info(f"[-] Client disconnected: {ws.remote_address} ({e.code})")
    finally:
        connected_clients.remove(ws)
        logger.info(f"[.] Remaining clients: {len(connected_clients)}")

async def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Server listening on 0.0.0.0:{port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # работа до Ctrl+C

if __name__ == "__main__":
    asyncio.run(main())
