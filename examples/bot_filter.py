from collections import defaultdict, deque
from aiohttp.web import Response
from pyguard import Client
import time

client = Client()

WINDOW = 15
MAX_REQUESTS = 40
BURST_REQUESTS = 15
BURST_WINDOW = 2

BLOCK_TIME = 60

SUSPICIOUS_PATHS = {
    "/admin",
    "/wp-login",
    "/wp-admin",
    "/.env",
    "/config",
    "/phpmyadmin",
}

REQUIRED_HEADERS = {
    "user-agent",
    "accept",
}

BROWSER_HEADERS = {
    "accept-language",
    "accept-encoding",
}

BAD_UA_KEYWORDS = {
    "curl", "wget", "python", "aiohttp",
    "httpclient", "scrapy", "bot", "spider",
    "crawler", "scanner", "nmap", "nikto",
}

requests = defaultdict(deque)
blocked_until = {}

def now() -> float:
    return time.time()


def is_blocked(ip: str) -> bool:
    return blocked_until.get(ip, 0) > now()


def block(ip: str, seconds: int = BLOCK_TIME) -> None:
    blocked_until[ip] = now() + seconds


def record_request(ip: str) -> None:
    timestamps = requests[ip]
    timestamps.append(now())

    while timestamps and now() - timestamps[0] > WINDOW:
        timestamps.popleft()


def too_many_requests(ip: str) -> bool:
    return len(requests[ip]) > MAX_REQUESTS


def burst_detected(ip: str) -> bool:
    timestamps = requests[ip]
    recent = [t for t in timestamps if now() - t <= BURST_WINDOW]
    return len(recent) >= BURST_REQUESTS


def suspicious_user_agent(ua: str) -> bool:
    if not ua or len(ua) < 10:
        return True

    ua_l = ua.lower()
    return any(bad in ua_l for bad in BAD_UA_KEYWORDS)


def missing_required_headers(headers) -> bool:
    lower = {k.lower() for k in headers.keys()}
    return not REQUIRED_HEADERS.issubset(lower)


def looks_non_browser(headers) -> bool:
    lower = {k.lower() for k in headers.keys()}
    return not BROWSER_HEADERS.intersection(lower)


def probing_path(path: str) -> bool:
    for bad in SUSPICIOUS_PATHS:
        if path.startswith(bad):
            return True
    return False

@client.event
async def on_request(request):
    ip = request.remote or "unknown"

    if is_blocked(ip):
        request.respond(Response(status=403, text="Blocked"))

    record_request(ip)

    ua = request.headers.get("User-Agent", "")
    headers = request.headers
    path = request.path

    score = 0

    if suspicious_user_agent(ua):
        score += 3

    if missing_required_headers(headers):
        score += 2

    if looks_non_browser(headers):
        score += 1

    if probing_path(path):
        score += 3

    if burst_detected(ip):
        score += 3

    if too_many_requests(ip):
        score += 2

    if score >= 5:
        block(ip)
        request.respond(
            Response(
                status=403,
                text="Access denied",
            )
        )

    request.forward("http://localhost:8030", request)


@client.event
async def on_forward(response):
    response.headers["X-Filtered-By"] = "PyGuard"
    response.respond(response)


client.run()
