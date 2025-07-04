from django.db import models
from django.utils import timezone

class IPScore(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    score = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    is_blocked = models.BooleanField(default=False)

    @classmethod
    def increment_score(cls, ip_address):
        ip_score, created = cls.objects.get_or_create(
            ip_address=ip_address,
            defaults={'score': 1}
        )
        if not created:
            ip_score.score += 1
            ip_score.save()
        return ip_score