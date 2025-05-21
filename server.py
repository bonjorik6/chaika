# server.py
import asyncio
import os
import websockets

# Хранит активные WebSocket-подключения
connected_clients = set()

async def handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            dead = []
            # Шлём всем остальным «как есть»
            for client in connected_clients:
                if client is websocket:
                    continue
                try:
                    await client.send(message)
                except Exception:
                    dead.append(client)
            # Убираем «мертвые» соединения
            for d in dead:
                connected_clients.discard(d)

    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        # Логируем, но не даём ошибке уйти наружу
        print(f"Handler error: {e}")
    finally:
        connected_clients.discard(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"WebSocket-сервер запущен на порту {port}")
        await asyncio.Future()  # держим сервер «висеть»

if __name__ == "__main__":
    asyncio.run(main())
