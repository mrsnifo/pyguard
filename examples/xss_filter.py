from aiohttp.web import Response
from pyguard import Client, http
import re

client = Client()

XSS_PATTERNS = [
    r"<script\b",
    r"</script>",
    r"javascript:",
    r"onerror\s*=",
    r"onload\s*=",
    r"alert\s*\(",
    r"document\.cookie",
    r"document\.location",
]

XSS_REGEX = re.compile("|".join(XSS_PATTERNS), re.IGNORECASE)

def contains_xss(value: str) -> bool:
    return bool(XSS_REGEX.search(value))


@client.event
async def on_request(request: http.Request):
    for key, value in request.query.items():
        if contains_xss(value):
            request.respond(
                Response(
                    text="Blocked: XSS detected in query parameters",
                    status=400,
                )
            )

    for key, value in request.headers.items():
        if contains_xss(value):
            request.respond(
                Response(
                    text="Blocked: XSS detected in headers",
                    status=400,
                )
            )

    if request.can_read_body:
        body = await request.text()
        if contains_xss(body):
            request.respond(
                Response(
                    text="Blocked: XSS detected in request body",
                    status=400,
                )
            )
    request.forward("http://localhost:8030", request)


client.run(port=8080)
