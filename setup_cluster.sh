#!/bin/bash
set -e # Arrête le script si une commande échoue

# --- COULEURS ET VARIABLES ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

CLUSTER_NAME="nexslice-cluster"
NS_APP="nexslice"
NS_MONITORING="monitoring"
PROM_SERVER_LABEL="app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server"
KUBE_FORWARD_PORT=9090

# --- FONCTIONS UTILES ---

wait_for_pod_ready() {
    local label=$1
    local ns=$2
    echo -e "${BLUE}>>> Attente illimitée de $label dans $ns... (Peut prendre plusieurs minutes)${NC}"
    # Le timeout a été retiré pour s'adapter à la vitesse du réseau
    kubectl wait --for=condition=ready pod -l "$label" -n "$ns" 
    echo -e "${GREEN}✅ $label est prêt.${NC}"
}

# --- ÉTAPE 1 : NETTOYAGE ET CRÉATION DU CLUSTER ---
echo -e "\n${RED}=============================================================${NC}"
echo -e "${RED}                 1. NETTOYAGE ET CRÉATION CLUSTER              ${NC}"
echo -e "${RED}=============================================================${NC}"

echo -e "${YELLOW}🧹 Nettoyage de l'ancien cluster K3d...${NC}"
k3d cluster delete "$CLUSTER_NAME" || true

echo -e "${YELLOW}🛠️ Création du cluster $CLUSTER_NAME (1 Server + 2 Agents)...${NC}"
k3d cluster create "$CLUSTER_NAME" --agents 2

echo -e "${GREEN}✅ Cluster créé. Nœuds actifs :${NC}"
kubectl get nodes

# --- ÉTAPE 2 : INSTALLATION DE PROMETHEUS (5s SCRAPE) ---
echo -e "\n${BLUE}=============================================================${NC}"
echo -e "${BLUE}           2. INSTALLATION PROMETHEUS (TEMPS RÉEL)           ${NC}"
echo -e "${BLUE}=============================================================${NC}"

echo -e "${YELLOW}📦 Ajout du repo Helm et création du Namespace $NS_MONITORING...${NC}"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace "$NS_MONITORING" || true
kubectl create namespace "$NS_APP" || true 

echo -e "${YELLOW}🚀 Déploiement de Prometheus (Mode RAM, 5s Scrape)...${NC}"
helm install prometheus prometheus-community/prometheus \
  --namespace "$NS_MONITORING" \
  --set server.global.scrape_interval=5s \
  --set server.global.scrape_timeout=5s \
  --set server.global.evaluation_interval=5s \
  --set alertmanager.enabled=false \
  --set pushgateway.enabled=false \
  --set nodeExporter.enabled=true \
  --set server.persistentVolume.enabled=false

# 4. Attendre que le serveur Prometheus soit prêt
wait_for_pod_ready "$PROM_SERVER_LABEL" "$NS_MONITORING"

# --- ÉTAPE 4 : CRÉATION DU TUNNEL ET PRÉPARATION DE L'IA ---
echo -e "\n${BLUE}=============================================================${NC}"
echo -e "${BLUE}           4. OUVERTURE DU TUNNEL ET PRÉPARATION             ${NC}"
echo -e "${BLUE}=============================================================${NC}"

# On trouve le nom du pod Server Prometheus
export PROM_POD=$(kubectl get pods -n "$NS_MONITORING" -l "$PROM_SERVER_LABEL" -o jsonpath="{.items[0].metadata.name}")

echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "${CYAN} ACTION REQUISE : Lancez cette commande dans un terminal SÉPARÉ et laissez-le ouvert !${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "${GREEN}COMMANDE DU TUNNEL :${NC}"
echo -e "kubectl port-forward -n $NS_MONITORING pod/$PROM_POD $KUBE_FORWARD_PORT:$KUBE_FORWARD_PORT &"
echo -e "${CYAN}------------------------------------------------------------${NC}"

echo -e "\n${YELLOW}INFRASTRUCTURE PRÊTE ! ${NC}"
echo "1. Lancez le tunnel ci-dessus."
echo "2. Lancez le scheduler RL : ${GREEN}python3 ai_scheduler-expert.py${NC} (dans un autre terminal)."
echo "3. Lancez le script de démo : ${GREEN}./demo_ultimate_final.sh${NC}"
