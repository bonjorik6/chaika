# server.py
import asyncio
import websockets
import os
import json
import logging
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chat-server")

# Набор всех подключённых WebSocket-соединений
connected_clients: set[websockets.WebSocketServerProtocol] = set()

async def handler(ws: websockets.WebSocketServerProtocol, path: str):
    # добавить в список
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
            logger.info(f"→ Received type={typ} from {ws.remote_address}")

            # перечень типов, которые шлёт ваш клиент
            if typ in (
                "text", "file", "voice", "image",
                "webrtc_offer", "webrtc_answer", "webrtc_ice", "webrtc_end"
            ):
                # переслать всем остальным
                dead = []
                for client in connected_clients:
                    if client is ws:
                        continue
                    try:
                        await client.send(raw)
                    except Exception:
                        # потерянное соединение — запомним, чтобы удалить
                        logger.warning(f"Не могу отправить {typ} to {client.remote_address}")
                        dead.append(client)
                # убрать мёртвые
                for d in dead:
                    connected_clients.discard(d)

            else:
                logger.warning(f"Неизвестный тип сообщения: {typ}")

    except websockets.ConnectionClosed:
        logger.info(f"Client disconnected: {ws.remote_address}")
    except Exception as e:
        # любая непредвиденная ошибка — залогировать стек и не давать серверу падать
        logger.error("Unhandled exception in handler:\n" + traceback.format_exc())
    finally:
        connected_clients.discard(ws)
        logger.info(f"Connection cleanup: {ws.remote_address}")

async def main():
    port = int(os.environ.get("PORT", 8080))
    # ws://0.0.0.0:PORT/
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Server listening on port {port}")
        await asyncio.Future()  # never exit

if __name__ == "__main__":
    asyncio.run(main())
