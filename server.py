# server.py
import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI()
active_connections: list[WebSocket] = []

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_connections.append(ws)
    print(f"[SERVER] Client connected: {ws.client}")

    try:
        while True:
            # ждём текстового сообщения (JSON-строки)
            msg = await ws.receive_text()
            # ретранслируем «как есть» всем остальным
            disconnected = []
            for conn in active_connections:
                if conn is ws:
                    continue
                try:
                    await conn.send_text(msg)
                except Exception:
                    disconnected.append(conn)
            # убираем отвалившиеся
            for dc in disconnected:
                active_connections.remove(dc)

    except WebSocketDisconnect:
        print(f"[SERVER] Client disconnected: {ws.client}")
        active_connections.remove(ws)
    except Exception as e:
        # чтобы не убирать по 1011 сразу
        print(f"[SERVER] Error in connection {ws.client}: {e}")
        if ws in active_connections:
            active_connections.remove(ws)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, log_level="info")
