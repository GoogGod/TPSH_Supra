from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import Venue
from .serializers import VenueSerializer
from users.permissions import IsManager


class VenueListView(ListAPIView):
    """
    Список активных объектов.
    Используется в dropdown при регистрации сотрудника.
    """
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated, IsManager]
    pagination_class = None  # Объектов мало, пагинация не нужна

    @extend_schema(summary="Список объектов", tags=["venues"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Venue.objects.filter(is_active=True)