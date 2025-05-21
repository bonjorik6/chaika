import asyncio
import json
import logging
import os
import signal
from collections import defaultdict

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import websockets

# --- Configuration from env ---
DB_HOST = os.getenv('DB_HOST', 'centerbeam.proxy.rlwy.net')
DB_PORT = int(os.getenv('DB_PORT', 31825))
DB_NAME = os.getenv('DB_NAME', 'railway')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'XrRCKeVnqILcchiVtRiwzUbtloCFAlVy')

WS_HOST = os.getenv('WS_HOST', '0.0.0.0')
WS_PORT = int(os.getenv('PORT', os.getenv('WS_PORT', '6789')))

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('server')

# Initialize DB connection pool (for future use)
DB_POOL = ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)
logger.info('Database connection pool initialized')

# Track which clients are in which rooms
room_clients = defaultdict(set)
# Allowed message types
ALLOWED_TYPES = {'text', 'file', 'voice', 'image'}

async def register_client(ws, room_id):
    if ws not in room_clients[room_id]:
        room_clients[room_id].add(ws)
        logger.debug(f'Client {id(ws)} joined room {room_id}')

async def unregister_client(ws):
    for room_id, clients in list(room_clients.items()):
        if ws in clients:
            clients.remove(ws)
            logger.debug(f'Client {id(ws)} left room {room_id}')
            if not clients:
                del room_clients[room_id]

async def handler(ws, path):
    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                logger.warning('Invalid JSON: %s', msg)
                continue

            room_id = data.get('room_id')
            msg_type = data.get('type')
            if room_id is None or msg_type not in ALLOWED_TYPES:
                logger.warning('Skipping message without room_id or unallowed type: %s', data)
                continue

            # Add this client to the room
            await register_client(ws, room_id)

            # Broadcast to peers in same room
            for peer in room_clients[room_id]:
                if peer is not ws:
                    try:
                        await peer.send(msg)
                    except Exception as e:
                        logger.error('Error broadcasting to client %s: %s', id(peer), e)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister_client(ws)

async def main():
    server = await websockets.serve(handler, WS_HOST, WS_PORT)
    logger.info(f'WebSocket server listening on {WS_HOST}:{WS_PORT}')

    loop = asyncio.get_event_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    await stop
    logger.info('Shutdown signal received')
    server.close()
    await server.wait_closed()
    logger.info('WebSocket server closed')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        DB_POOL.closeall()
        logger.info('Database pool closed')
