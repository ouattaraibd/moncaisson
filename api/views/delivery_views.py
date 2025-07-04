from rest_framework import viewsets, permissions
from location.models import DeliveryOption, DeliveryRequest
from api.serializers.delivery_serializers import DeliveryOptionSerializer,DeliveryRequestSerializer
from django_ratelimit.decorators import ratelimit
from rest_framework.decorators import api_view
from rest_framework.response import Response

@ratelimit(key='ip', rate='10/m')
@api_view(['POST'])
def create_delivery(request):
    return Response({"message": "Delivery created"})

class DeliveryOptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryOption.objects.filter(is_active=True)
    serializer_class = DeliveryOptionSerializer

class DeliveryRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryRequestSerializer
    queryset = DeliveryRequest.objects.all()

