from django.urls import path, include
from rest_framework import routers
from .views.delivery_views import DeliveryOptionViewSet, DeliveryRequestViewSet

router = routers.DefaultRouter()
router.register(r'options', DeliveryOptionViewSet)
router.register(r'requests', DeliveryRequestViewSet)

urlpatterns = [
    path('delivery/', include(router.urls)),
]

