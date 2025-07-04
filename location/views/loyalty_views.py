from django.contrib.auth.decorators import login_required

@login_required
def loyalty_dashboard(request):
    profile = request.user.loyalty_profile
    return render(request, 'location/loyalty/dashboard.html', {
        'profile': profile,
        'rewards': Reward.objects.filter(is_active=True)
    })

