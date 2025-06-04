from rest_framework import viewsets, permissions
from location.models import DeliveryOption, DeliveryRequest
from api.serializers.delivery_serializers import DeliveryOptionSerializer,DeliveryRequestSerializer

class DeliveryOptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryOption.objects.filter(is_active=True)
    serializer_class = DeliveryOptionSerializer

class DeliveryRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryRequestSerializer
    queryset = DeliveryRequest.objects.all()