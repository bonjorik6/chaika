import os
import json
import asyncio
import logging
import signal
from collections import defaultdict

import websockets

# --- Logging configuration ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('server')

# Map room_id to active WebSocket connections
room_clients = defaultdict(set)

# Allowed message types
ALLOWED_TYPES = {'text', 'file', 'voice', 'image'}

async def register(ws, room_id):
    if ws not in room_clients[room_id]:
        room_clients[room_id].add(ws)
        logger.debug(f'Client {id(ws)} joined room {room_id}')

async def unregister(ws):
    for room_id, conns in list(room_clients.items()):
        if ws in conns:
            conns.remove(ws)
            logger.debug(f'Client {id(ws)} left room {room_id}')
            if not conns:
                del room_clients[room_id]

async def handler(ws, path):
    try:
        async for raw in ws:
            # Parse incoming JSON
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning('Invalid JSON received: %s', raw)
                continue

            room_id = data.get('room_id')
            msg_type = data.get('type')

            # Validate message
            if room_id is None or msg_type not in ALLOWED_TYPES:
                logger.warning('Skipping unsupported message: %s', data)
                continue

            # Ensure this ws is in the room
            await register(ws, room_id)

            # Broadcast to **other** clients in the same room
            for peer in room_clients[room_id]:
                if peer is not ws:
                    try:
                        await peer.send(raw)
                    except Exception as e:
                        logger.error('Error sending to client %s: %s', id(peer), e)
    except websockets.exceptions.ConnectionClosed:
        logger.info('Client disconnected: %s', id(ws))
    finally:
        await unregister(ws)

async def main():
    # On Railway, PORT is provided via env
    port = int(os.environ.get('PORT', '6789'))
    server = await websockets.serve(handler, '0.0.0.0', port)
    logger.info(f'WebSocket server listening on 0.0.0.0:{port}')

    # Graceful shutdown on SIGINT/SIGTERM
    loop = asyncio.get_event_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)
    await stop

    logger.info('Shutdown signal received, closing server')
    server.close()
    await server.wait_closed()
    logger.info('Server closed')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception('Server error: %s', e)
