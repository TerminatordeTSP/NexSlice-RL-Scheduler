#!/bin/bash

# Couleurs et Constantes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
EDGE_NODE="k3d-nexslice-cluster-agent-1" 
CLOUD_NODE="k3d-nexslice-cluster-server-0"

# Fonction Helper
deploy() {
    NAME=$1
    CPU=$2
    MEM=$3
    EXPECTED_NODE=$4
    
    echo -e "\n${CYAN}>>> Scénario : $NAME (Req: $CPU CPU)${NC}"
    
    # On laisse l'IA choisir (schedulerName: nexslice-ai)
    kubectl run $NAME --image=nginx --restart=Never --overrides='{"spec": {"schedulerName": "nexslice-ai", "containers": [{"name": "n", "image": "nginx", "resources": {"requests": {"cpu": "'$CPU'm", "memory": "'$MEM'Mi"}}}]}}' -n nexslice >/dev/null 2>&1
    
    # Attente active
    for i in {1..15}; do
        NODE=$(kubectl get pod $NAME -n nexslice -o jsonpath='{.spec.nodeName}')
        if [[ -n "$NODE" ]]; then
            echo -e "   ✅ Placé sur : ${YELLOW}$NODE${NC} (Attendu: $EXPECTED_NODE)"
            return
        fi
        sleep 1
    done
    echo -e "   ❌ Timeout: Non placé."
}

# Fonction pour forcer le remplissage (Utilise 'stress-filler' pour cleanup)
force_fill() {
    NODE=$1
    CPU=$2
    # Crée un Pod de stress avec un nom unique et le label run=stress-filler
    kubectl run stress-filler-$RANDOM --image=vish/stress --labels="run=stress-filler" --restart=Never --overrides='{"spec": {"nodeName": "'$NODE'", "containers": [{"name": "f", "image": "vish/stress", "args": ["-cpus", "10"], "resources": {"requests": {"cpu": "1000m"}}}]}}' -n nexslice >/dev/null 2>&1
}

# Fonction pour nettoyer TOUS les fillers stress
cleanup_stress() {
    # Supprime par le label run=stress-filler
    kubectl delete pod -l run=stress-filler -n nexslice --grace-period=0 --force >/dev/null 2>&1
    echo -e "   ✅ Stress Killer arrêté et nettoyé."
    sleep 5
}

# ---------------------------------------------------------
# 0. NETTOYAGE ROBUSTE ET PRÉPARATION
# ---------------------------------------------------------
echo -e "${YELLOW}[Init] Nettoyage complet (Déploiements et Pods orphelins)...${NC}"
kubectl delete deployment --all -n nexslice --grace-period=0 --force >/dev/null 2>&1
kubectl delete pods --all -n nexslice --grace-period=0 --force >/dev/null 2>&1
sleep 5
echo -e "${GREEN}Cluster prêt.${NC}"

read -p "Appuyer sur Entrée pour lancer la Phase 1 (Slicing Basique)..."

# ---------------------------------------------------------
# PHASE 1 : TESTS BASIQUES (SLICING & CONSOLIDATION)
# ---------------------------------------------------------
deploy "oai-du-critical" 200 200 "Agent"
deploy "oai-upf-urllc-slice" 150 150 "Agent"
deploy "oai-amf-control" 100 100 "Server"

read -p "Phase 1 terminée. Appuyer sur Entrée pour la Phase 2 (Compromis & Crise)..."

# ---------------------------------------------------------
# PHASE 2 : TESTS AVANCÉS (COMPROMIS ET PÉNURIE)
# ---------------------------------------------------------

# 4. CRÉATION DU STRESS EDGE (Sabotage de Agent-1 pour la pénurie)
echo -e "\n${RED}>>> 4. SABOTAGE DE L'EDGE : Agent-1 (CPU ciblée)${NC}"
force_fill "$EDGE_NODE" 800 

# --- PAUSE CRITIQUE 1 (Vérification de la charge) ---
echo -e "\n${YELLOW}⚠️  PAUSE CRITIQUE 1 : Vérification surcharge EDGE${NC}"
echo "   Objectif : Surcharge AGENT-1 (Attendez le pic 60-70% CPU dans le terminal top nodes)."
read -p "Appuyez sur Entrée UNIQUEMENT quand l'AGENT-1 est saturé..."

# 5. TEST ÉVASION EDGE : DU arrive (Critique Latence)
# Objectif : Edge est saturé (Agent-1). Il doit fuir vers l'Edge libre (Agent-0).
deploy "du-critique-survivant" 150 150 "Agent-0"

# 6. Nettoyage de l'Agent-1 avant d'attaquer le Cloud
echo -e "\n${GREEN}>>> 6. CLEANUP : Arrêt du stress Agent-1 pour l'étape suivante.${NC}"
cleanup_stress 

# 7. CRÉATION DU STRESS CLOUD (On remplit le Server pour la crise)
echo -e "\n${RED}>>> 7. SABOTAGE DU CLOUD : Server (CPU ciblée)${NC}"
force_fill "$CLOUD_NODE" 3200 

# --- PAUSE CRITIQUE 2 (Vérification de la charge) ---
echo -e "\n${YELLOW}⚠️  PAUSE CRITIQUE 2 : Vérification surcharge CLOUD${NC}"
echo "   Objectif : Surcharge SERVER-0 (Attendez le pic 50-60% CPU)."
read -p "Appuyez sur Entrée UNIQUEMENT quand le SERVER-0 est saturé..."

# 8. TEST ULTIME COMPROMIS : URLLC CRITIQUE (Gros)
# Contexte : Cloud est plein. URLLC (Critique) doit choisir entre :
# A) Crash vs B) Edge libre
deploy "upf-urllc-compromis" 100 100 "Agent" # Attendu : Agent (Il prend le risque si le Cloud est trop full)

# 9. TEST DE SURVIE : Gros Pod eMBB arrive
# Contexte : Cloud est full. Il doit trouver le petit trou libre sur l'Edge.
deploy "upf-embb-gros" 100 100 "Agent" 

# 10. TEST FINAL DE RETOUR À LA NORMALE
cleanup_stress 
deploy "amf-final-clean" 100 100 "Server" # Attendu : Server (Règle Consolidation)

echo -e "\n${GREEN}=== DÉMO ULTIME TERMINÉE ===${NC}"
