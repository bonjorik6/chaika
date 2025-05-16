# server/server.py
import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI()
connected = set()

@app.websocket("/")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected.add(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            # ретранслируем всем, кроме отправителя
            for other in list(connected):
                if other is not ws:
                    await other.send_text(raw)
    except WebSocketDisconnect:
        connected.remove(ws)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
