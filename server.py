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
logger = logging.getLogger("webrtc-server")

CALL_TYPES = {
    "call_request",
    "call_answer",
    "call_reject",
    "call_end",
}

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
        # Ожидаем первое сообщение — регистрацию пользователя
        init = await ws.recv()
        init_data = json.loads(init)
        if init_data.get("type") != "register" or "from" not in init_data:
            logger.warning("Клиент не отправил регистрацию")
            await ws.close(code=1008, reason="Must register first")
            return

        user_nick = init_data["from"]
        connected_clients[user_nick] = ws
        logger.info(f"Пользователь зарегистрировался: {user_nick}")

        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Получено не-JSON сообщение: %r", raw)
                continue

            typ     = data.get("type")
            rid     = data.get("room_id")
            frm     = data.get("from")
            to_nick = data.get("to")
            call_id = data.get("call_id")

            # Работа с БД
            if typ in CALL_TYPES:
                conn = None
                try:
                    conn = get_conn()
                    cur = conn.cursor()

                    if typ == "call_request":
                        cur.execute("""
                            INSERT INTO calls (room_id, initiator, recipient, status, created_at)
                            VALUES (%s, %s, %s, 'pending', NOW())
                            RETURNING id
                        """, (rid, frm, to_nick))
                        call_id = cur.fetchone()["id"]
                        data["call_id"] = call_id

                    elif typ == "call_answer" and call_id:
                        cur.execute("""
                            UPDATE calls SET status='in_progress', started_at=NOW()
                            WHERE id=%s
                        """, (call_id,))

                    elif typ == "call_reject" and call_id:
                        cur.execute("""
                            UPDATE calls SET status='cancelled', ended_at=NOW()
                            WHERE id=%s
                        """, (call_id,))

                    elif typ == "call_end" and call_id:
                        cur.execute("""
                            UPDATE calls
                               SET status='finished',
                                   ended_at = NOW(),
                                   duration = EXTRACT(EPOCH FROM NOW() - started_at)::INT
                             WHERE id = %s
                        """, (call_id,))

                    conn.commit()
                    cur.close()

                except Exception as e:
                    logger.exception("SQL error on %s: %s", typ, e)
                    if conn:
                        conn.rollback()
                    await ws.close(code=1011, reason="DB error")
                    return

                finally:
                    if conn:
                        conn.close()

            # Отправка сообщений адресно
            msg = json.dumps(data)
            recipient_ws = connected_clients.get(to_nick)

            if typ == "call_request":
                # Отправляем и вызываемому, и вызывающему
                await asyncio.gather(
                    *(ws_.send(msg) for user, ws_ in connected_clients.items()
                      if user in {frm, to_nick}),
                    return_exceptions=True
                )
            elif typ in {"webrtc_offer", "webrtc_answer", "webrtc_ice", "call_answer", "call_reject", "call_end"}:
                if recipient_ws:
                    await recipient_ws.send(msg)
            elif typ == "webrtc_end":
                # По желанию можно и себе отправить, и другому
                await asyncio.gather(
                    *(ws_.send(msg) for user, ws_ in connected_clients.items()
                      if user in {frm, to_nick}),
                    return_exceptions=True
                )
            else:
                logger.debug("Неизвестный тип сообщения: %s", typ)

    except ConnectionClosed:
        logger.info("Клиент %s отключился", user_nick)
    finally:
        if user_nick and connected_clients.get(user_nick) == ws:
            del connected_clients[user_nick]

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Сервер запущен на порту {port}")
        await asyncio.Future()  # Бесконечно работает

if __name__ == "__main__":
    asyncio.run(main())
