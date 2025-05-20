import os
import json
import asyncio
import logging

import websockets
import psycopg2
from psycopg2.extras import RealDictCursor

# --- настройки подключения к БД ---
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

def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )

connected_clients = set()

async def handler(ws):
    connected_clients.add(ws)
    try:
        async for raw in ws:
            # 1) Парсим JSON
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

            # 2) Если это one of CALL_TYPES — работаем с БД
            if typ in CALL_TYPES:
                conn = None
                try:
                    conn = get_conn()
                    cur  = conn.cursor()

                    if typ == "call_request":
                        cur.execute(
                            """
                            INSERT INTO calls (
                                room_id, initiator, recipient, status, created_at
                            ) VALUES (%s, %s, %s, 'pending', NOW())
                            RETURNING id
                            """,
                            (rid, frm, to_nick)
                        )
                        call_id = cur.fetchone()["id"]
                        data["call_id"] = call_id

                    elif typ == "call_answer" and call_id:
                        cur.execute(
                            "UPDATE calls SET status='in_progress', started_at=NOW() WHERE id=%s",
                            (call_id,)
                        )

                    elif typ == "call_reject" and call_id:
                        cur.execute(
                            "UPDATE calls SET status='cancelled', ended_at=NOW() WHERE id=%s",
                            (call_id,)
                        )

                    elif typ == "call_end" and call_id:
                        cur.execute(
                            """
                            UPDATE calls
                               SET status='finished',
                                   ended_at = NOW(),
                                   duration = EXTRACT(EPOCH FROM NOW() - started_at)::INT
                             WHERE id = %s
                            """,
                            (call_id,)
                        )

                    conn.commit()
                    cur.close()

                except Exception as e:
                    logger.exception("SQL error on %s: %s", typ, e)
                    await ws.close(code=1011, reason="DB error")
                    return

                finally:
                    if conn:
                        conn.close()

            # 3) Ретранслируем сигнализацию и медиа‑команды
            white_list = {
                "text", "audio", "media",
                "webrtc_offer", "webrtc_answer", "webrtc_ice", "webrtc_end",
                *CALL_TYPES
            }

            msg = json.dumps(data)
            if typ == "call_request":
                # всем, включая отправителя (для получения call_id)
                await asyncio.gather(
                    *[c.send(msg) for c in connected_clients],
                    return_exceptions=True
                )
            elif typ in white_list:
                await asyncio.gather(
                    *[c.send(msg) for c in connected_clients if c != ws],
                    return_exceptions=True
                )
            else:
                logger.debug("Игнорирую неизвестный тип сообщения: %s", typ)

    except websockets.ConnectionClosed:
        logger.info("Клиент отключился")
    finally:
        connected_clients.discard(ws)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Сервер запущен на порту {port}") 
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
