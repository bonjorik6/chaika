# server.py
import os
import asyncio
import json
import logging
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chat-server")

# Все подключенные WebSocket-сессии
connected_clients = set()

async def handler(ws, path):
    # При подключении
    connected_clients.add(ws)
    logger.info(f"[+] Client connected: {ws.remote_address}")
    try:
        async for raw in ws:
            # Пытаемся распарсить JSON
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("← Получено не-JSON сообщение, игнорируем")
                continue

            # Логируем тип и комнату (если есть)
            logger.info(f"← From {ws.remote_address}: type={data.get('type')} room_id={data.get('room_id')}")

            # Рассылаем всем остальным
            await asyncio.gather(
                *[client.send(raw) for client in connected_clients if client is not ws],
                return_exceptions=True
            )

    except (ConnectionClosedOK, ConnectionClosedError) as e:
        logger.info(f"[-] Client disconnected: {ws.remote_address} code={e.code}")
    finally:
        connected_clients.remove(ws)
        logger.info(f"[.] Сейчас подключено: {len(connected_clients)} клиентов")

async def main():
    port = int(os.environ.get("PORT", 8080))
    # Обратите внимание: handler принимает два аргумента (ws, path)
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Server listening on 0.0.0.0:{port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
