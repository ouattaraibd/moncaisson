from django_ratelimit.exceptions import Ratelimited
from django.http import JsonResponse

def handle_ratelimit_error(request, exception):
    if isinstance(exception, Ratelimited):
        return JsonResponse({
            "error": "too_many_requests",
            "message": "Vous avez dépassé la limite de requêtes"
        }, status=429)
    return None

