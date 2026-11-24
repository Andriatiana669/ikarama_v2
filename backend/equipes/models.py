# backend/equipes/models.py
"""
Aucune table : les équipes sont CALCULÉES à partir des fiches employés (API RH).

  Équipe = un responsable (N+1) + ses collaborateurs directs (les employés dont il est le « chef »).
  Pôle   = le pôle indiqué dans le poste de l'employé (EmployePoste.pole).

Les anciennes tables (directions, pôles, équipes, membres, historique) ont été supprimées
par la migration 0002 : tout se met à jour automatiquement avec la synchronisation RH.
"""
