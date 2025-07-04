from django.core.management.base import BaseCommand
from django.core.cache import cache
from moncaisson.models import BlockedIP
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Analyse les attaques et bloque les IPs malveillantes'

    def handle(self, *args, **options):
        try:
            # Analyse des logs WAF pour blocage permanent
            from pathlib import Path
            log_file = Path(__file__).resolve().parent.parent.parent.parent / 'logs' / 'waf.log'
            
            if not log_file.exists():
                logger.error("Fichier de logs WAF introuvable")
                return

            # Logique d'analyse simplifiée
            ip_counts = {}
            with open(log_file, 'r') as f:
                for line in f:
                    if 'Attaque' in line and 'IP:' in line:
                        ip = line.split('IP: ')[1].split(' |')[0].strip()
                        ip_counts[ip] = ip_counts.get(ip, 0) + 1

            # Blocage permanent des IPs trop actives
            for ip, count in ip_counts.items():
                if count > 10:  # Seuil à ajuster
                    BlockedIP.objects.get_or_create(
                        ip_address=ip,
                        defaults={'reason': f"{count} attaques détectées"}
                    )
                    logger.warning(f"IP bloquée définitivement: {ip} ({count} attaques)")

            self.stdout.write(self.style.SUCCESS('Analyse des attaques terminée'))

        except Exception as e:
            logger.error(f"Erreur dans monitor_attacks: {str(e)}")
            raise