from location.models.security import IPScore 

class IPScoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if response.status_code == 403:  # Si le WAF a bloqué
            ip = request.META.get('REMOTE_ADDR')
            IPScore.increment_score(ip)
            
        return response