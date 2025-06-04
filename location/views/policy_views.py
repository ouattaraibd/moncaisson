from django.shortcuts import redirect
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django import forms
from django.conf import settings

try:
    from location.models import Policy, PolicyAcceptance
except ImportError:
    Policy = None
    PolicyAcceptance = None
    import warnings
    warnings.warn("Policy models not available - running in compatibility mode")

class PolicyAcceptanceForm(forms.Form):
    accept = forms.BooleanField(
        required=True,
        label="J'accepte les termes et conditions",
        widget=forms.CheckboxInput(attrs={'required': 'required'})
    )

class PolicyAcceptanceView(LoginRequiredMixin, FormView):
    template_name = 'location/policy/acceptance.html'
    form_class = PolicyAcceptanceForm

    def dispatch(self, request, *args, **kwargs):
        if Policy is None or PolicyAcceptance is None:
            messages.warning(request, "La fonctionnalité de politique n'est pas disponible actuellement")
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            policy_type = self.kwargs['policy_type'].upper()
            context['policy'] = Policy.objects.get(
                policy_type=policy_type,
                is_active=True
            )
            context['next_url'] = self.request.GET.get('next', '/')
        except Policy.DoesNotExist:
            messages.error(self.request, "La politique demandée n'existe pas")
        except Exception as e:
            messages.error(self.request, f"Une erreur est survenue: {str(e)}")
        return context

    def form_valid(self, form):
        try:
            policy_type = self.kwargs['policy_type'].upper()
            policy = Policy.objects.get(
                policy_type=policy_type,
                is_active=True
            )
            
            PolicyAcceptance.objects.create(
                user=self.request.user,
                policy=policy,
                ip_address=self._get_client_ip()
            )
            messages.success(self.request, "Politique acceptée avec succès")
        except Policy.DoesNotExist:
            messages.error(self.request, "La politique demandée n'existe pas")
        except Exception as e:
            messages.error(self.request, f"Erreur lors de l'acceptation: {str(e)}")
        
        return redirect(self.get_success_url())

    def get_success_url(self):
        return self.request.GET.get('next', '/')

    def _get_client_ip(self):
        """
        Méthode pour récupérer l'adresse IP réelle du client
        """
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip