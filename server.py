import asyncio
import websockets
import os
import json

connected_clients = set()

async def handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            # Декодируем, если пришло в байтах
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                if msg_type == "text" or msg_type == "audio":
                    # Отправляем всем, кроме отправителя
                    await asyncio.gather(*[
                        client.send(json.dumps(data))
                        for client in connected_clients
                        if client != websocket
                    ])
                else:
                    print(f"Неизвестный тип сообщения: {msg_type}")
            except json.JSONDecodeError:
                print("Ошибка декодирования JSON")
            except Exception as e:
                print(f"Ошибка обработки сообщения: {e}")
    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        connected_clients.remove(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port, max_size=None):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
