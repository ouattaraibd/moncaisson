from rest_framework import serializers
from location.models import DeliveryOption, DeliveryRequest

class DeliveryOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryOption
        fields = ['id', 'name', 'description', 'price']

class DeliveryRequestSerializer(serializers.ModelSerializer):
    option_details = DeliveryOptionSerializer(source='option', read_only=True)
    reservation_details = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryRequest
        fields = ['id', 'reservation', 'option', 'option_details', 'delivery_address', 
                'status', 'created_at', 'updated_at', 'reservation_details']
        extra_kwargs = {
            'status': {'read_only': True}
        }

    def get_reservation_details(self, obj):
        from api.serializers import ReservationSerializer  # Import circulaire évité
        return ReservationSerializer(obj.reservation).data

    def validate(self, data):
        if data['option'].is_active is False:
            raise serializers.ValidationError("Cette option de livraison n'est plus disponible")
        return data

