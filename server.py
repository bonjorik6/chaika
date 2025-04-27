import asyncio
import websockets
import os

connected_clients = set()

async def handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            # Рассылаем сообщение только активным клиентам
            disconnected = []
            for client in connected_clients:
                try:
                    await client.send(message)
                except websockets.ConnectionClosed:
                    disconnected.append(client)
            # Удаляем отключившихся клиентов
            for client in disconnected:
                connected_clients.remove(client)
    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
