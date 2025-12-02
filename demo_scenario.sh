#!/bin/bash

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== DÉMO FINALE V2 : AI SCHEDULER 5G ===${NC}"

# Fonction d'attente intelligente
wait_for_pod() {
    POD_NAME=$1
    EXPECTED=$2 # "agent" ou "server"
    
    printf "   ⏳ Placement de $POD_NAME en cours..."
    
    # On boucle tant que le noeud est vide ou Pending (Max 20s)
    for i in {1..20}; do
        NODE=$(kubectl get pod $POD_NAME -n nexslice -o jsonpath='{.spec.nodeName}')
        if [[ -n "$NODE" && "$NODE" != "null" ]]; then
            echo ""
            if [[ "$NODE" == *"$EXPECTED"* ]]; then
                echo -e "   ✅ $POD_NAME -> ${GREEN}$NODE${NC} (Match $EXPECTED)"
            else
                # Si c'est un AMF sur un Agent, ce n'est pas "grave", c'est juste "luxueux"
                echo -e "   ⚠️ $POD_NAME -> ${YELLOW}$NODE${NC} (Préférence IA)"
            fi
            return
        fi
        sleep 1
        printf "."
    done
    echo -e "\n   ❌ Timeout : Le pod n'a pas été assigné (Vérifie le script Python)"
}

# Nettoyage
echo -e "\n${YELLOW}[Init] Reset Cluster...${NC}"
kubectl delete pods --all -n nexslice --grace-period=0 --force >/dev/null 2>&1
sleep 3

# 1. CORE
echo -e "\n${BLUE}--- 1. CORE NETWORK (AMF) ---${NC}"
kubectl run amf-core --image=nginx --restart=Never --overrides='{"spec": {"schedulerName": "nexslice-ai", "containers": [{"name": "n", "image": "nginx", "resources": {"requests": {"cpu": "100m"}}}]}}' -n nexslice >/dev/null 2>&1
wait_for_pod "amf-core" "server"

# 2. RAN DU
echo -e "\n${BLUE}--- 2. RAN DISTRIBUTED UNIT (Critique) ---${NC}"
kubectl run du-radio --image=nginx --restart=Never --overrides='{"spec": {"schedulerName": "nexslice-ai", "containers": [{"name": "n", "image": "nginx", "resources": {"requests": {"cpu": "100m"}}}]}}' -n nexslice >/dev/null 2>&1
wait_for_pod "du-radio" "agent"

# 3. URLLC
echo -e "\n${BLUE}--- 3. SLICE URLLC (Critique) ---${NC}"
kubectl run upf-urllc --image=nginx --restart=Never --overrides='{"spec": {"schedulerName": "nexslice-ai", "containers": [{"name": "n", "image": "nginx", "resources": {"requests": {"cpu": "100m"}}}]}}' -n nexslice >/dev/null 2>&1
wait_for_pod "upf-urllc" "agent"

# 4. STRESS
echo -e "\n${RED}--- 4. STRESS TEST (Surcharge) ---${NC}"
echo "🔥 Lancement du stress (12 CPU)..."
kubectl apply -f stress-test.yaml >/dev/null 2>&1
echo "⏳ Attente détection Prometheus (10s)..."
sleep 10

# 5. REACTION
echo -e "\n${BLUE}--- 5. RÉACTION SOUS LE FEU ---${NC}"
echo "Lancement de 3 utilisateurs pendant la surcharge..."
for i in 1 2 3; do
    kubectl run user-$i --image=nginx --restart=Never --overrides='{"spec": {"schedulerName": "nexslice-ai", "containers": [{"name": "n", "image": "nginx", "resources": {"requests": {"cpu": "10m"}}}]}}' -n nexslice >/dev/null 2>&1
done

sleep 5
echo "📊 Répartition finale :"
kubectl get pods -n nexslice -l run!=stress-cpu -o custom-columns=POD:.metadata.name,NODE:.spec.nodeName
