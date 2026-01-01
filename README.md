# PyGuard

[![Python Versions](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)

An async Python HTTP proxy client for intercepting, responding, and forwarding requests.

## Key Features

* Async/await support throughout
* Intercept and respond to HTTP requests
* Forward requests to other servers with optional response modification
* Lightweight and easy to extend

## Installing

Clone the repository and install dependencies:

```bash
git clone https://github.com/mrsnifo/pyguard.git
cd pyguard
python3 -m pip install -U .
```

## Respond Example

```python
from pyguard import Client, Request
from aiohttp.web import Response

client = Client()

@client.event
async def on_request(request: Request):
    print(f"Request from {request.remote}")
    # Respond immediately
    request.respond(Response(text="Access Denied", status=403))

client.run(host="localhost", port=8080)
```

## Forward Example

```python
from pyguard import Client, Request, Response

client = Client()

@client.event
async def on_request(request: Request):
    request.forward("http://localhost:8030", request)

@client.event
async def on_forward(response: Response):
    # Modify the forwarded response
    response.headers["X-Filtered-By"] = "PyGuard"
    response.respond(response)

client.run(host="localhost", port=8080)
```

More examples available in the [examples](examples) folder.
