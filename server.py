import asyncio
import websockets
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chat-server")

# просто хранит все открытые ws-соединения
connected_clients: set[websockets.WebSocketServerProtocol] = set()

async def handler(ws: websockets.WebSocketServerProtocol, path):
    connected_clients.add(ws)
    logger.info(f"Client connected: {ws.remote_address}")
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Получено невалидное JSON-сообщение")
                continue

            typ = data.get("type")
            logger.info(f"Received message type={typ} data={data}")

            # все типы, которые шлёт ваш клиент
            if typ in ("text", "file", "voice", "image",
                       "webrtc_offer", "webrtc_answer", "webrtc_ice", "webrtc_end"):
                # разослать всем остальным
                dead = []
                for client in connected_clients:
                    if client is ws:
                        continue
                    try:
                        await client.send(raw)
                    except Exception as e:
                        logger.warning(f"Не удалось отправить клиенту {client.remote_address}: {e}")
                        dead.append(client)
                # убрать умершие коннекты
                for d in dead:
                    connected_clients.discard(d)
            else:
                logger.warning(f"Неизвестный тип сообщения: {typ}")

    except websockets.ConnectionClosed:
        logger.info(f"Client disconnected: {ws.remote_address}")
    finally:
        connected_clients.discard(ws)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Server listening on port {port}")
        await asyncio.Future()  # never exit

if __name__ == "__main__":
    asyncio.run(main())
