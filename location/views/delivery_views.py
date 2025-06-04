import os
from django.views.generic import ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from xhtml2pdf import pisa
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template, render_to_string
from location.models import DeliveryRequest

# Import DRF components
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from api.serializers.delivery_serializers import DeliveryRequestSerializer
from ..permissions import IsOwnerOrAdmin

class DeliveryListView(LoginRequiredMixin, ListView):
    model = DeliveryRequest
    template_name = 'location/delivery/list.html'
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return DeliveryRequest.objects.all()
        return DeliveryRequest.objects.filter(reservation__client=self.request.user)

class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    model = DeliveryRequest
    fields = ['status', 'tracking_number', 'driver']
    template_name = 'location/delivery/update.html'
    success_url = '/delivery/'
    
class DeliveryRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    filterset_fields = ['status', 'option']
    search_fields = ['delivery_address']

    def get_queryset(self):
        queryset = DeliveryRequest.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(reservation__client=self.request.user)
        return queryset

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        delivery = self.get_object()
        if delivery.status not in ['PENDING', 'SCHEDULED']:
            return Response({'error': 'Annulation impossible'}, status=400)
        delivery.status = 'CANCELLED'
        delivery.save()
        return Response({'status': 'annulé'})

class DeliveryPDFView(LoginRequiredMixin, ListView):
    model = DeliveryRequest
    template_name = 'location/delivery/pdf_report.html'
    
    def get(self, request, *args, **kwargs):
        deliveries = self.get_queryset()
        
        # Utilisez render_to_string avec un contexte minimal
        html = render_to_string(self.template_name, {
            'object_list': deliveries,
            'base_dir': settings.BASE_DIR
        })
        
        result = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")),
            dest=result,
            encoding='UTF-8',
            link_callback=self.link_callback
        )
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'filename="livraisons.pdf"'
            return response
        return HttpResponse('Erreur lors de la génération du PDF: %s' % pdf.err, status=400)
    
    def link_callback(self, uri, rel):
        """
        Convertit les URIs HTML en chemins système pour les ressources
        """
        # Ignore les URLs externes et les données URI
        if uri.startswith('http') or uri.startswith('data:'):
            return None
            
        # Gère les chemins absolus
        if uri.startswith('/'):
            path = os.path.join(settings.STATIC_ROOT, uri.lstrip('/'))
        else:
            path = os.path.join(settings.BASE_DIR, uri)
            
        # Vérifie que le fichier existe
        if not os.path.isfile(path):
            raise Exception('Fichier non trouvé: %s' % path)
            
        return path