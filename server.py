import asyncio
import websockets
import os
import json

connected_clients = set()

async def handler(websocket):
    print("Клиент подключился")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Получено сообщение: {message}")
            try:
                # Декодирование сообщения
                if isinstance(message, bytes):
                    message = message.decode('utf-8')
                
                data = json.loads(message)

                # Проверка правильности формата
                if isinstance(data, dict) and "type" in data and "data" in data:
                    # Рассылаем всем другим клиентам
                    await asyncio.gather(*[
                        client.send(json.dumps(data))
                        for client in connected_clients
                        if client != websocket
                    ])
                else:
                    print("⚠️ Неверный формат данных!")
            except json.JSONDecodeError:
                print("⚠️ Невозможно декодировать JSON.")
            except Exception as e:
                print(f"⚠️ Ошибка обработки сообщения: {e}")
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
