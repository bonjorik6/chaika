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
                msg_type = data.get("type")
                if msg_type in (
                    "text", "file", "voice", "audio", "media",
                    "group_created", "group_renamed", "group_updated", 
                    "room_deleted", "history_cleared"
                ):
                    broadcast = json.dumps(data)
                    # Вместо asyncio.gather: отправляем по одному и отлавливаем исключения
                    for client in set(connected_clients):
                        if client is websocket:
                            continue
                        try:
                            await client.send(broadcast)
                        except Exception as e:
                            print(f"Ошибка при отправке клиенту {client.remote_address}: {e}")
                else:
                    print(f"Неизвестный тип сообщения: {msg_type}")
            except json.JSONDecodeError:
                print("Получено невалидное сообщение")
    except websockets.ConnectionClosed:
        print("Клиент отключился")
    finally:
        connected_clients.remove(websocket)

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()  # чтобы сервер не завершился

if __name__ == "__main__":
    asyncio.run(main())
