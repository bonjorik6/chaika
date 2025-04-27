import asyncio
import websockets
import os
import json

connected_clients = set()

async def handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data["type"] in ("text", "audio"):
                    # Просто пересылаем другим клиентам как есть
                    await asyncio.gather(*[client.send(message) for client in connected_clients if client != websocket])
                else:
                    print("Неизвестный тип сообщения:", data["type"])
            except json.JSONDecodeError:
                print("Ошибка декодирования JSON от клиента")
    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        connected_clients.remove(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
