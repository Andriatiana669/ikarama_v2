# backend/notifications/services.py
"""Créer des notifications (sans doublon d'une même alerte encore non lue)."""
from .models import Notification


def notifier(destinataires, type_, titre, message='', lien='', cle=''):
    """Crée une notification pour chaque destinataire (Employe ou id), sauf s'il a déjà la même alerte non lue."""
    crees = []
    vus = set()
    for d in destinataires:
        identifiant = getattr(d, 'pk', d)
        if not identifiant or identifiant in vus:
            continue
        vus.add(identifiant)
        if cle and Notification.objects.filter(destinataire_id=identifiant, cle=cle, lu=False).exists():
            continue
        crees.append(Notification(destinataire_id=identifiant, type=type_, titre=titre[:200], message=message, lien=lien, cle=cle[:120]))
    Notification.objects.bulk_create(crees)
    from temps_reel.diffusion import nouvelle_notification   # bulk_create n'envoie pas de signal
    for n in crees:
        nouvelle_notification(n.destinataire_id)
    return len(crees)
