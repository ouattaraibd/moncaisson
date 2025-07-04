from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from location.models.policy_models import Policy, PolicyAcceptance

class PolicyAcceptanceMiddleware(MiddlewareMixin):
    EXEMPT_PATHS = ['/policy/', '/logout/', '/admin/']
    
    def process_request(self, request):
        if (request.path_info in self.EXEMPT_PATHS or 
            not request.user.is_authenticated):
            return
            
        required_policies = Policy.objects.filter(
            is_active=True,
            effective_date__lte=timezone.now(),
            expiration_date__gte=timezone.now()
        ).filter(
            Q(policy_type='GENERAL') |
            Q(policy_type=request.user.user_type)
        )

        for policy in required_policies:
            if not PolicyAcceptance.objects.filter(
                user=request.user,
                policy=policy,
                accepted=True
            ).exists():
                logger.warning(f"Policy {policy} non acceptée par {request.user}")
                return redirect('policy_acceptance', 
                    policy_id=policy.id,
                    next=request.path_info)

