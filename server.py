# server.py
import os
import json
import asyncio
import logging

import websockets
from websockets.exceptions import ConnectionClosed
import psycopg2
from psycopg2.extras import RealDictCursor

# --- Настройки подключения к БД ---
DB_HOST     = os.environ.get("PGHOST",     "centerbeam.proxy.rlwy.net")
DB_PORT     = os.environ.get("PGPORT",     31825)
DB_NAME     = os.environ.get("PGDATABASE", "railway")
DB_USER     = os.environ.get("PGUSER",     "postgres")
DB_PASSWORD = os.environ.get("PGPASSWORD", "XrRCKeVnqILcchiVtRiwzUbtloCFAlVy")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-server")

connected_clients = {}  # nick → websocket

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )

async def handler(ws):
    user = None
    try:
        # --- регистрация ---
        init = await ws.recv()
        data = json.loads(init)
        if data.get("type") != "register" or "from" not in data:
            await ws.close(1008, "Must register first")
            return

        user = data["from"]
        connected_clients[user] = ws
        logger.info(f"User registered: {user}")

        # --- основной цикл обработки ---
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            typ     = msg.get("type")
            room_id = msg.get("room_id")
            sender  = msg.get("from")
            to_user = msg.get("to")
            payload = json.dumps(msg)

            # 1) WebRTC-звонки (оставляю, если нужно)
            if typ in {"call_request", "webrtc_offer", "webrtc_answer", "webrtc_ice", "call_end"}:
                # адресная пересылка
                if to_user in connected_clients:
                    await connected_clients[to_user].send(payload)
                continue

            # 2) Чат-сообщения
            if typ in {"text", "file", "voice"}:
                # если указан прямой получатель — шлём только ему
                if to_user:
                    ws_target = connected_clients.get(to_user)
                    if ws_target:
                        await ws_target.send(payload)
                    continue

                # иначе — рассылка по всем участникам комнаты
                if room_id is not None:
                    try:
                        conn = get_conn()
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT nickname FROM room_members WHERE room_id = %s",
                            (room_id,)
                        )
                        members = [r["nickname"] for r in cur.fetchall()]
                    except Exception as e:
                        logger.error("DB error fetching members: %s", e)
                        members = []
                    finally:
                        cur.close()
                        conn.close()

                    # шлём всем онлайн-участникам
                    await asyncio.gather(
                        *(
                            connected_clients[nick].send(payload)
                            for nick in members
                            if nick in connected_clients
                        ),
                        return_exceptions=True
                    )
                continue

            # 3) всё прочее игнорируем
            logger.debug("Unknown message type: %s", typ)

    except ConnectionClosed:
        logger.info(f"Client disconnected: {user}")
    finally:
        if user and connected_clients.get(user) == ws:
            del connected_clients[user]

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Server listening on port {port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
