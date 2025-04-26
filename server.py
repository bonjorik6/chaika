import asyncio
import websockets

# Храним всех подключенных клиентов
connected_clients = set()

async def handler(websocket, path):
    # При подключении добавляем клиента
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            # Рассылаем сообщение всем клиентам
            await asyncio.gather(*[client.send(message) for client in connected_clients if client != websocket])
    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        # При отключении удаляем клиента
        connected_clients.remove(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8080):
        print("Сервер запущен на порту 8080")
        await asyncio.Future()  # бесконечное ожидание

if __name__ == "__main__":
    asyncio.run(main())
