// src/api/index.ts
// Point d'import unique :  import { equipesApi, utilisateursApi } from '@/api'
export { apiClient, ApiErreur, messageErreur } from './client'
export { creerRessource } from './ressource'
export { authApi } from './auth'
export { utilisateursApi } from './utilisateurs'
export { equipesApi } from './equipes'
export { reglesAccesApi, accesApi, rolesApi } from './autorisations'
export { affairesApi, prestationsApi, projetsApi, tachesApi, statutsApi, descriptionsApi } from './marches'
export { feuillesApi, lignesFeuilleApi, historiqueFeuilleApi } from './gsheets'
export { ancienneDonneeApi, equipeFeuilleApi, monResumeApi, statutsFeuilleApi, tempsEstimatifApi } from './gsheets'
export {
  analyseEmployesApi,
  analyseRendementApi,
  evaluationRendementApi,
  evolutionRendementApi,
  globaleRendementApi,
  parametresGraphiquesApi,
  parametresRendementApi,
  reelObjectifApi,
} from './rendements'
export { everwinApi, pointagesApi, suiviPointagesApi, verificationApi } from './pointages'
export { accueilApi, controlesApi, notificationsApi } from './notifications'
export { planningApi } from './planning'
export { dureeEstimativeApi } from './marches'
export { configurationsResponsablesApi } from './marches'
