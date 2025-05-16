# server.py
import asyncio
import json
import logging
import os
import signal
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

logging.basicConfig(
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("webrtc-signal-server")

# { client_id: websocket }
clients = {}

async def register(websocket, client_id):
    if client_id in clients:
        # Если клиент с таким ID уже есть — закрываем старое соединение
        old = clients[client_id]
        await old.close(code=4000, reason="Duplicate client_id")
    clients[client_id] = websocket
    logger.info(f"Registered client: {client_id}")

async def unregister(client_id):
    clients.pop(client_id, None)
    logger.info(f"Unregistered client: {client_id}")

async def route_message(data, sender_id):
    """
    Ожидаем, что data содержит:
    {
      "type": "...",
      "from": "<sender_id>",
      "to": "<recipient_id>",    # если нет — можно рассылать всем
      ... payload ...
    }
    """
    msg_type = data.get("type")
    to_id = data.get("to")

    if not msg_type or not data.get("from"):
        logger.warning("Invalid message format: missing 'type' or 'from'")
        return

    # Если указан конкретный получатель
    if to_id:
        ws = clients.get(to_id)
        if ws:
            await ws.send(json.dumps(data))
        else:
            logger.warning(f"Client '{to_id}' not found")
    else:
        # Broadcast всем, кроме отправителя
        for cid, ws in clients.items():
            if cid != sender_id:
                await ws.send(json.dumps(data))

async def handler(websocket):
    # Первый пакет от клиента должен быть регистрация с client_id
    try:
        init = await asyncio.wait_for(websocket.recv(), timeout=5)
        init_data = json.loads(init)
        client_id = init_data.get("client_id")
        if not client_id:
            raise ValueError("No client_id provided")
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        await websocket.close(code=4001, reason="Registration failed")
        return

    await register(websocket, client_id)

    # Настроим ping/pong
    websocket.ping_interval = 20
    websocket.ping_timeout = 20

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON message")
                continue

            # Перенаправляем сигнальные сообщения
            if data.get("type", "").startswith("webrtc_") or data.get("type") in ("text", "audio", "media"):
                await route_message(data, sender_id=client_id)
            else:
                logger.info(f"Ignored message type: {data.get('type')}")
    except (ConnectionClosedOK, ConnectionClosedError) as e:
        logger.info(f"Connection closed for {client_id}: {e}")
    finally:
        await unregister(client_id)

async def main():
    port = int(os.environ.get("PORT", 8080))
    server = await websockets.serve(
        handler,
        host="0.0.0.0",
        port=port,
        max_size=2**20,           # максимальный размер сообщения 1 МБ
        ping_interval=20,
        ping_timeout=20,
        close_timeout=5
    )
    logger.info(f"Server started on port {port}")

    # Гладкое завершение по SIGINT/SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.close()))

    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
