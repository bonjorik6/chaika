import os
import json
import asyncio
import logging
import websockets
from websockets.exceptions import ConnectionClosed
import psycopg2
from psycopg2.extras import RealDictCursor

# --- Настройки подключения к БД ---
DB_HOST     = os.environ.get("PGHOST", "centerbeam.proxy.rlwy.net")
DB_PORT     = os.environ.get("PGPORT", 31825)
DB_NAME     = os.environ.get("PGDATABASE", "railway")
DB_USER     = os.environ.get("PGUSER", "postgres")
DB_PASSWORD = os.environ.get("PGPASSWORD", "XrRCKeVnqILcchiVtRiwzUbtloCFAlVy")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-server")

# Ключ: ник, значение: WebSocket-соединение
connected_clients = {}

def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )

async def handler(ws):
    user_nick = None
    try:
        # Ждём регистрации
        init = await ws.recv()
        init_data = json.loads(init)
        if init_data.get("type") != "register" or "from" not in init_data:
            await ws.close(code=1008, reason="Must register first")
            return

        user_nick = init_data["from"]
        connected_clients[user_nick] = ws
        logger.info(f"User registered: {user_nick}")

        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            sender   = data.get("from")
            target   = data.get("to")
            payload  = json.dumps(data)

            # Рассылка: всем в комнате или адресно
            if msg_type == "message":
                # текстовые сообщения: отослать получателю
                if target and target in connected_clients:
                    await connected_clients[target].send(payload)
                else:
                    # широковещательно всем
                    await asyncio.gather(
                        *[ws_.send(payload) for ws_ in connected_clients.values()],
                        return_exceptions=True
                    )

            elif msg_type in {"photo", "voice"}:
                # медиа: пересылаем адресно или всем
                if target and target in connected_clients:
                    await connected_clients[target].send(payload)
                else:
                    await asyncio.gather(
                        *[ws_.send(payload) for ws_ in connected_clients.values()],
                        return_exceptions=True
                    )
            else:
                logger.debug(f"Unknown message type: {msg_type}")

    except ConnectionClosed:
        logger.info(f"Client disconnected: {user_nick}")
    finally:
        if user_nick and connected_clients.get(user_nick) == ws:
            del connected_clients[user_nick]

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Server listening on port {port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
