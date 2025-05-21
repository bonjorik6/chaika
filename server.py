# server.py
import asyncio, os, json
from aiohttp import web
import websockets

connected_clients = set()

# --- HTTP health-check ---
async def health(request):
    return web.Response(text="OK")

def start_http():
    app = web.Application()
    app.router.add_get('/healthz', health)
    web.run_app(app, host='0.0.0.0', port=int(os.getenv("HTTP_PORT", 8000)), print=None)

async def handler(websocket, path):
    print(f"[SERVER] Client connected: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            dead = []
            for client in connected_clients:
                if client is websocket: continue
                try: await client.send(message)
                except: dead.append(client)
            for d in dead: connected_clients.discard(d)
    finally:
        connected_clients.discard(websocket)
        print(f"[SERVER] Client disconnected: {websocket.remote_address}")

async def main_ws():
    port = int(os.getenv("PORT", 8080))
    async with websockets.serve(handler, '0.0.0.0', port):
        print(f"WebSocket-сервер запущен на порту {port}")
        await asyncio.Future()

if __name__ == "__main__":
    # Запускаем HTTP в отдельном потоке, чтобы Railway не убивал контейнер
    import threading
    threading.Thread(target=start_http, daemon=True).start()
    asyncio.run(main_ws())
