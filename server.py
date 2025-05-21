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
            msg = await ws.receive_text()
            disconnected = []
            for conn in active_connections:
                if conn is ws:
                    continue
                try:
                    await conn.send_text(msg)
                except Exception:
                    disconnected.append(conn)
            for dc in disconnected:
                active_connections.remove(dc)

    except WebSocketDisconnect:
        print(f"[SERVER] Client disconnected: {ws.client}")
        active_connections.remove(ws)
    except Exception as e:
        print(f"[SERVER] Error in connection {ws.client}: {e}")
        if ws in active_connections:
            active_connections.remove(ws)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
