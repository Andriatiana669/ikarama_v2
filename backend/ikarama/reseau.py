# backend/ikarama/reseau.py
"""
Outils communs pour les appels HTTP sortants (Keycloak, API RH).
"""
import requests


def decrire_erreur_reseau(exc: requests.RequestException) -> str:
    """Explication courte et utile d'un échec réseau, pour le journal du serveur."""
    if isinstance(exc, requests.exceptions.SSLError):
        return (f"certificat HTTPS refusé ({exc.__class__.__name__}). "
                "Renseigner CA_BUNDLE (fichier .pem) ou CA_BUNDLE=systeme dans le .env.")
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return "délai de connexion dépassé (réseau, pare-feu ou proxy)."
    if isinstance(exc, requests.exceptions.ConnectionError):
        return f"connexion impossible ({exc.__class__.__name__}) : adresse, port ou pare-feu."
    if isinstance(exc, requests.exceptions.Timeout):
        return "le service a mis trop de temps à répondre."
    return f"{exc.__class__.__name__}."
