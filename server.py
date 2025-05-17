# server.py

import os
import json
import asyncio
import websockets
import psycopg2
from psycopg2.extras import RealDictCursor

# --- настройки подключения к БД ---
DB_HOST     = os.environ.get("PGHOST", "centerbeam.proxy.rlwy.net")
DB_PORT     = os.environ.get("PGPORT", 31825)
DB_NAME     = os.environ.get("PGDATABASE", "railway")
DB_USER     = os.environ.get("PGUSER", "postgres")
DB_PASSWORD = os.environ.get("PGPASSWORD", "XrRCKeVnqILcchiVtRiwzUbtloCFAlVy")

def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )

# --- WebSocket сервер ---
connected_clients = set()

async def handler(ws):
    connected_clients.add(ws)
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                print("Получено невалидное сообщение")
                continue

            typ  = data.get("type")
            rid  = data.get("room_id")
            frm  = data.get("from")
            to_nick = data.get("to")  # ожидаем, что клиент при звонке шлёт "to": "<ник>"

            # --- Логика calls ---
            if typ == "call_request":
                # создаём запись звонка со статусом pending
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO calls (room_id, initiator, recipient, status, created_at)
                    VALUES (%s, %s, %s, 'pending', NOW())
                    RETURNING id
                """, (rid, frm, to_nick))
                call_id = cur.fetchone()["id"]
                conn.commit()
                cur.close()
                conn.close()
                # передаём клиенту call_id, чтобы дальше ссылаться на неё
                data["call_id"] = call_id

            elif typ == "call_answer":
                # меняем статус звонка на in_progress и фиксируем старт
                call_id = data.get("call_id")
                if call_id:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE calls
                           SET status = 'in_progress',
                               started_at = NOW()
                         WHERE id = %s
                    """, (call_id,))
                    conn.commit()
                    cur.close()
                    conn.close()

            elif typ == "call_end":
                # закрываем звонок, считаем длительность
                call_id = data.get("call_id")
                if call_id:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE calls
                           SET status = 'finished',
                               ended_at = NOW(),
                               duration = EXTRACT(EPOCH FROM NOW() - started_at)::INT
                         WHERE id = %s
                    """, (call_id,))
                    conn.commit()
                    cur.close()
                    conn.close()

            # --- ретрансляция остальным ---
            # список типов, которые мы раздаём везде
            white_list = {
                "text", "audio", "media",
                "webrtc_offer", "webrtc_answer", "webrtc_ice", "webrtc_end",
                "call_request", "call_answer", "call_reject", "call_end"
            }
            if typ in white_list:
                msg = json.dumps(data)
                await asyncio.gather(*[
                    c.send(msg)
                    for c in connected_clients
                    if c != ws
                ])
            else:
                print(f"Неизвестный тип сообщения: {typ}")

    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        connected_clients.discard(ws)


async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
