from collections import defaultdict
from pyguard import Client, http
from aiohttp.web import Response
import time

app = Client()

RATE_LIMIT = 3
TIME_WINDOW = 5
clients = defaultdict(list)

@app.event
async def on_request(request: http.Request):
    now = time.time()
    ip = request.remote
    clients[ip] = [t for t in clients[ip] if now - t < TIME_WINDOW]
    if len(clients[ip]) >= RATE_LIMIT:
        request.respond(Response(text='Rate limit exceeded', status=429))

    clients[ip].append(now)
    request.forward("http://localhost:8030", request)

app.run(host="localhost", port=8080)
