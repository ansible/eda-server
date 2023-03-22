"""
Run a simple websocket server for manual tests
"""
import asyncio
import json
from pprint import pprint

import websockets.server as ws_server

port = 6666
host = "localhost"


async def msg_handler(websocket: ws_server.WebSocketServerProtocol):
    async for message in websocket:
        payload = json.loads(message)
        data = {"path": websocket.path, "payload": payload}
        if data["payload"]["type"] == "ProcessedEvent" and not data["payload"]["results"]:
            continue
        print()
        pprint(data)
        print()


async def main():
    async with ws_server.serve(msg_handler, host, port):
        await asyncio.Future()


print("starting")
asyncio.run(main())
