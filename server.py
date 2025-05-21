# server.py
import os, asyncio, json, logging, websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chat-server")

connected_clients = set()

async def handler(ws, path):
    connected_clients.add(ws)
    logger.info(f"[+] Client connected: {ws.remote_address}")
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            logger.info(f"→ Received type={data.get('type')} room_id={data.get('room_id')}")
            await asyncio.gather(
                *(client.send(raw) for client in connected_clients if client is not ws),
                return_exceptions=True
            )
    except (ConnectionClosedOK, ConnectionClosedError) as e:
        logger.info(f"[-] Client disconnected: {ws.remote_address} ({e.code})")
    finally:
        connected_clients.remove(ws)
        logger.info(f"[.] Remaining clients: {len(connected_clients)}")

async def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Server listening on 0.0.0.0:{port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
