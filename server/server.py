import asyncio
import websockets
import os
import json

connected_clients = set()

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                # поддерживаем текст, медиа и WebRTC сигналинг
                if data.get("type") in ("text", "audio", "media", "offer", "answer", "candidate"):
                    # ретранслируем всем остальным клиентам
                    await asyncio.gather(*[
                        client.send(json.dumps(data))
                        for client in connected_clients
                        if client != websocket
                    ])
                else:
                    print(f"Ignored unknown message type: {data.get('type')}")
            except json.JSONDecodeError:
                print("Получено невалидное JSON-сообщение")
    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        connected_clients.remove(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())