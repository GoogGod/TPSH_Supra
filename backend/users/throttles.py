from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """Rate-limit login attempts by IP + username."""

    scope = "login"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if not ident:
            return None

        username = ""
        try:
            username = str(request.data.get("username", "")).strip().lower()
        except Exception:
            username = ""

        key = ident if not username else f"{ident}:{username}"
        return self.cache_format % {"scope": self.scope, "ident": key}
