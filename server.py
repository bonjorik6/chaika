# server.py
import asyncio
import json
import os
import websockets

connected_clients = set()

async def handler(websocket, path):
    # Добавляем нового клиента в набор
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            # Попытаться ретранслировать каждому, кроме отправителя
            dead = []
            for client in connected_clients:
                if client is websocket:
                    continue
                try:
                    await client.send(message)
                except Exception:
                    # Собираем тех, у кого отправка упала
                    dead.append(client)
            # Убираем «мертвые» подключения
            for d in dead:
                connected_clients.discard(d)

    except websockets.ConnectionClosed:
        # Клиент сам отключился
        pass
    finally:
        # Всегда удаляем клиента из набора при выходе
        connected_clients.discard(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"WebSocket-сервер запущен на порту {port}")
        await asyncio.Future()  # <- никогда не завершится

if __name__ == "__main__":
    asyncio.run(main())
