from django.db import migrations

def assign_users_to_transactions(apps, schema_editor):
    Transaction = apps.get_model('location', 'Transaction')
    User = apps.get_model('location', 'User')  # Changé de 'auth' à 'location'
    
    # Trouver un admin ou le premier utilisateur comme fallback
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.first()
    
    # Mettre à jour toutes les transactions sans utilisateur
    for transaction in Transaction.objects.filter(user__isnull=True):
        if transaction.portefeuille and transaction.portefeuille.proprietaire:
            transaction.user = transaction.portefeuille.proprietaire
        else:
            transaction.user = admin_user
        transaction.save()

class Migration(migrations.Migration):
    dependencies = [
        ('location', '0002_alter_documentverification_options_and_more'),
    ]
    operations = [
        migrations.RunPython(assign_users_to_transactions),
    ]