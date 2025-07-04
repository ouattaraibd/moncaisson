from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import LoginAttempt
import json
from django.utils import timezone

@csrf_exempt
def fake_login(request):
    if request.method == 'POST':
        data = {
            'username': request.POST.get('username', ''),
            'password': request.POST.get('password', ''),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'request_path': request.path,
            'timestamp': timezone.now()  # Ajout du timestamp
        }

        LoginAttempt.objects.create(**data)
        
        # Leurrage crédible
        import random
        import time
        time.sleep(random.uniform(0.5, 2.5))
        
        return JsonResponse({
            "status": "success",
            "user": {"role": "admin"},
            "token": "fake-" + "x"*32,
            "redirect": "/admin/"
        }, status=200)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)