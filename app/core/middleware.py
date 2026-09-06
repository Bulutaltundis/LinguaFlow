from urllib.parse import urlparse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.rate_limit import allowed

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        limited = ("login", 5, 300) if path in {"/auth/login", "/api/auth/login"} else ("register", 8, 3600) if path in {"/auth/register", "/api/auth/register"} else ("answer", 60, 60) if path.endswith("/answer") else ("shop", 20, 60) if (path.startswith("/shop/buy/") or path.startswith("/api/shop/buy/")) else ("join", 10, 300) if path in {"/classes/join", "/api/classes/join"} else None
        if limited:
            name, limit, window = limited
            address = request.client.host if request.client else "unknown"
            if not allowed(f"{name}:{address}", limit, window):
                return JSONResponse({"detail": "Çok fazla istek. Lütfen biraz bekle."}, status_code=429)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.url.path.startswith(("/auth/login", "/auth/register", "/api/", "/billing/webhook", "/billing/apple/notifications", "/billing/apple/transaction")):
            origin = request.headers.get("origin") or request.headers.get("referer")
            if not origin or urlparse(origin).netloc != request.url.netloc:
                return JSONResponse({"detail": "CSRF doğrulaması başarısız."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
