from rest_framework_simplejwt.views import TokenObtainPairView

from .throttles import LoginRateThrottle


class LoginView(TokenObtainPairView):
    """JWT login with dedicated throttling."""

    throttle_classes = [LoginRateThrottle]
