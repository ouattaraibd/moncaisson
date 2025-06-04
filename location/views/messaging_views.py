from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from location.models.core_models import User
from location.models.messaging_models import Conversation, Message

@login_required
def send_message(request, user_id):
    recipient = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        message_content = request.POST.get('message', '').strip()
        if message_content:
            # Trouve ou crée une conversation entre les utilisateurs
            conversation = Conversation.objects.filter(
                participants=request.user
            ).filter(
                participants=recipient
            ).first()
            
            if not conversation:
                conversation = Conversation.objects.create()
                conversation.participants.add(request.user, recipient)
            
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=message_content
            )
            messages.success(request, "Message envoyé avec succès!")
            return redirect('messaging:success', recipient_id=recipient.id)
    
    return render(request, 'location/messaging/send.html', {
        'recipient': recipient,
        'active_tab': 'messaging'
    })

@login_required
def message_success(request, recipient_id):
    recipient = get_object_or_404(User, id=recipient_id)
    return render(request, 'location/messaging/success.html', {
        'recipient': recipient
    })