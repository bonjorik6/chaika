import asyncio
import websockets

connected_clients = set()

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            await asyncio.gather(
                *[client.send(message) for client in connected_clients if client != websocket]
            )
    except websockets.ConnectionClosedOK:
        print("Клиент отключился")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connected_clients.remove(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8080):
        print("Сервер запущен на порту 8080")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
