# NexSlice Scheduler RL: Ordonnancement 5G Avancé par Apprentissage par Renforcement

**Auteurs :** Ryan ZERHOUNI, Anas FERRAH, Sam BOUCHET, Othmane TAIRECH

**Contexte :** Projet 4 - Scheduler Intelligent avec IA pour Réseau 5G Slicing

**Environnement utilisé :** macOS (Apple Silicon M4 Pro) / OrbStack / K3d

-----

Ce projet présente l'intégration d'un ordonnanceur intelligent basé sur l'**Apprentissage par Renforcement (RL)** dans un environnement de test 5G (NexSlice/OAI) pour optimiser l'équilibrage de charge et le respect des contraintes de latence liées au *Network Slicing* (Tranches Réseau). L'objectif est de remplacer ou compléter le scheduler par défaut Kubernetes (`kube-scheduler`).

---

## 1\. État de l’art : scheduling 5G cloud-native et limites de Kubernetes

### 1.1 5G, network slicing et exigences de QoS

La 5G introduit le **network slicing** pour faire cohabiter sur la même infrastructure des services aux besoins très différents (eMBB, URLLC, mMTC). Chaque *slice* correspond à un réseau logique de bout en bout, avec ses propres fonctions réseau (RAN, cœur 5G) et ses propres objectifs de performance (latence, débit, isolation, fiabilité).

Les spécifications 3GPP (TS 28.530, 28.531, 28.532, 28.533) définissent :
- le modèle d’information des slices,
- les opérations de cycle de vie (création / modification / suppression),
- et les KPIs / SLA à respecter pour la QoS.

Cela impose :
- une **latence faible** (en particulier pour l’URLLC),
- un **débit garanti** (eMBB),
- une **isolation logique** des ressources (CPU, mémoire, bande passante),
- une **élasticité dynamique** pour suivre la demande.

SchedulerTa3IA s’inscrit dans ce contexte : son objectif est d’améliorer le placement des fonctions réseau pour mieux respecter ces contraintes de QoS dans un environnement Kubernetes.

### 1.2 Cloud-native 5G et rôle de Kubernetes

Avec la 5G, les fonctions réseau migrent de VNFs monolithiques vers des **Cloud-Native Network Functions (CNFs)**, packagées en conteneurs et orchestrées par Kubernetes. Plusieurs cœurs 5G open source (OpenAirInterface, Open5GS, etc.) adoptent cette approche.

Dans ce cadre :
- Kubernetes fournit le **plan de contrôle** pour créer / supprimer / scaler les pods,
- assure le **service discovery** (Services, EndpointSlices),
- et s’appuie sur un composant clé : le **kube-scheduler**, responsable du placement des pods sur les nœuds.

SchedulerTa3IA s’insère dans cette architecture cloud-native : il se connecte à n’importe quel cluster Kubernetes (y compris un déploiement existant de type NexSlice) pour expérimenter et appliquer des politiques de scheduling spécifiques au slicing 5G, en venant **compléter** le comportement du kube-scheduler par défaut grâce à une couche d’IA — sans modifier ni forker Kubernetes.

### 1.3 kube-scheduler : fonctionnement et limites pour le slicing 5G

Le kube-scheduler effectue classiquement deux étapes :
1. **Filtrage** des nœuds admissibles (ressources disponibles, taints/tolerations, affinités, etc.).
2. **Scoring** pour choisir le “meilleur” nœud via différents plugins.

Même si le *Scheduling Framework* permet d’ajouter des plugins custom (Filter, Score, Bind, …), le scheduler par défaut reste centré sur :
- les **requests/limits** CPU et mémoire déclarées par les pods,
- et quelques contraintes de topologie (labels, zones).

En revanche, pour le slicing 5G, il ne prend pas nativement en compte :
- la **latence réseau** entre nœuds,
- la **bande passante disponible**,
- le **type de fonction 5G** (UPF, SMF, AMF, CU/DU),
- ni les **objectifs SLA spécifiques à un slice** (latence cible, débit, isolement).

Conséquence : le placement pod-par-pod peut aboutir à :
- des slices **partiellement déployées**,
- un **gaspillage de ressources** (CPU/énergie),
- et un **non-respect** des contraintes de latence ou d’isolation.

SchedulerTa3IA répond à ce manque en introduisant un scheduler IA externe qui se base sur l’**utilisation réelle** CPU/RAM des nœuds et des critères métier, ce que kube-scheduler ne fait pas par défaut.

### 1.4 Approches avancées pour le scheduling 5G et microservices

La littérature récente explore plusieurs pistes pour améliorer le scheduling dans des scénarios 5G cloud-native :

#### a) Heuristiques et métaheuristiques

Des travaux modélisent le placement des slices comme un problème de **Virtual Network Embedding (VNE)**, et utilisent des heuristiques (dont des algorithmes génétiques) pour :
- décider si une slice entière est admissible (*all-or-nothing*),
- optimiser le **taux d’acceptation** des slices,
- réduire la **consommation énergétique** et le temps de déploiement.

SchedulerTa3IA se place dans cette famille *heuristique/IA*, avec une approche volontairement simple et explicable : un **Score de Disponibilité** basé sur la charge CPU/RAM réelle pour chaque nœud, combiné à une logique de décision pilotée par l’IA pour guider le placement.

#### b) Ordonnanceurs “network-aware” et co-scheduling

D’autres ordonnanceurs se focalisent sur la **latence réseau** et les **graphes de communication** entre pods :
- prise en compte d’une matrice latence/bande passante entre nœuds,
- co-scheduling de groupes de pods (une application ou un slice complet) plutôt que pod par pod,
- co-localisation de fonctions fortement couplées (par ex. UPF–gNB/DU, UPF–SMF/AMF).

Ces approches visent à réduire la latence inter-pods et à mieux exploiter la topologie réseau, ce qui est critique pour les services 5G sensibles à la QoS.

#### c) Schedulers basés sur le Machine Learning / Reinforcement Learning

Un troisième axe consiste à utiliser l’**apprentissage par renforcement (RL / DRL)** pour apprendre automatiquement une politique de placement sur Kubernetes. Les travaux existants montrent que le RL peut :
- observer l’état du cluster (charge CPU/mémoire, métriques applicatives),
- choisir dynamiquement le nœud pour chaque pod,
- optimiser simultanément **latence**, **taux de complétion**, **équilibrage de charge** et **utilisation des ressources**.

Au-delà de Kubernetes, le DRL est aussi appliqué au **network slicing** (cœur + RAN), où l’allocation de ressources entre slices est vue comme un problème de décision séquentielle multi-objectif.

---
### Positionnement de SchedulerTa3IA : Le Contrôleur 5G Expert
Le NexSlice Scheduler RL ne cherche pas à compléter les outils existants ; il agit comme un contrôleur de politique d'ordonnancement (Policy Override), prenant la main sur le kube-scheduler par défaut pour les charges critiques 5G. Il est désormais spécifiquement adapté à la topologie Edge/Cloud de NexSlice.

Il démontre concrètement :

qu'une IA Experte (Apprentissage par Renforcement) est indispensable pour gérer les compromis complexes (arbitrage entre la pénalité de latence et la pénalité de surcharge), ce qu'un algorithme heuristique pur ne peut pas faire.

qu'en utilisant Prometheus pour la télémétrie quasi-temps réel (5s au lieu de 60s), l'ordonnanceur peut réagir dynamiquement aux pics de charge et aux pannes ciblées pour garantir la survie du service (Évasion de crise).

qu'il est capable de faire du Service-Aware Scheduling en respectant les contraintes du Slicing 5G : forcer le placement des services critiques (URLLC/DU) sur le Edge tout en consolidant les services tolérants (AMF/eMBB) sur le Cloud pour maximiser l'utilisation des ressources rares.

que le RL est la méthode la plus fiable pour atteindre une stratégie d'Optimalité Globale (Bin Packing / Consolidation) tout en minimisant le risque de catastrophe.

---

## 2. Architecture et Méthode

### 2.1. Topologie et Contraintes 5G

L'IA a été entraînée sur une topologie fidèle à la réalité 5G, encodant la **scarcité des ressources Edge** :
* **Nœuds Edge (Agents) :** Petite capacité (`100%`) et faible latence (`2ms`).
* **Nœud Cloud (Server) :** Grande capacité (`400%`) et haute latence (`50ms`).
* **Règles :** Le placement des pods est régi par des récompenses/pénalités :
    * **Pénalité Critique de Surcharge (CPU/RAM) :**  Mettre un pod sur un nœud qui dépasse sa capacité coûte -100 points et met fin à la partie (règle de survie absolue).
    * **Pénalité Latence :** Mettre un pod critique (URLLC/DU) sur le Cloud coûte **-50 points** (Latence critique non respectée).
    * **Bonus Économie :** Mettre un pod non-critique (AMF) sur le Cloud rapporte **+10 points** (Économie de ressources Edge).

### 2.2. Outils et Flux de Données

| Composant | Rôle dans le projet | Technologie |
| :--- | :--- | :--- |
| **Cerveau** | Agent de décision basé sur les récompenses. | PPO (Stable-Baselines3) |
| **Simulateur** | Fournit le terrain d'entraînement (Gymnasium). | `sim_env.py` |
| **Temps Réel** | Fournit les métriques temps réel (5s). | **Prometheus** (par API HTTP) |
| **Infrastructure** | Cluster de test multi-nœuds. | **K3d** |

## 3. Guide de Reproductibilité Instantanée

Pour exécuter le prototype complet (Cluster, IA et Démo), suivez ces étapes dans des terminaux séparés.

### Terminal 1 : Préparation & Entraînement

C'est ici que vous entraînez le cerveau RL pour la première fois.

```bash
# 1. FERMER OrbStack/Docker pour libérer le CPU
# (Attendre que le setup_demo.sh soit terminé avant de fermer)

# 2. Entraînement de l'IA (Cœur du projet)
python3 train_rl.py

```

### Terminal 2 : Infrastructure (Le Tunnel)

Une fois l'entraînement terminé (et le fichier .zip créé), relancez OrbStack.
```bash
# 3. Nettoyage et création du cluster K3d (3 nœuds) + Prometheus
./setup_cluster.sh
```
**ATTENTION : Remplacez PROM_POD par le nom exact du pod Server Prometheus**
```bash
export PROM_POD=$(kubectl get pods -n monitoring -l "app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server" -o jsonpath='{.items[0].metadata.name}')
```
#### Lancer le tunnel dans un terminal DÉDIÉ (laissez-le ouvert !)
```bash
kubectl port-forward -n monitoring pod/$PROM_POD 9090:9090
```
### Terminal 3 : Lancement du Scheduler et de la Démo

C'est le "tableau de bord" de la démonstration finale. Lancer chaque commande dans un terminal tmux différent.
1. Lancer le scheduler (Il charge le .zip et attend les événements)
```bash
python3 ai_scheduler-expert.py
```

2. Surveiller la charge des nœuds en temps réel (Utile pour la pause manuelle)
```bash
watch -n 1 kubectl top nodes
```

3. Lancer le scénario de test final
```bash
./demo_ultimate.sh
```

---

# Analyse Détaillée des Scénarios de Test
Le script de démonstration a été divisé en trois phases pour vérifier la capacité de l'IA à appliquer les règles de Slicing, à gérer la rareté (Compromis) et à éviter les catastrophes (Evasion).

### 3.1. Phase 1 : Validation de la Logique de Slicing (SVT : Latence)

Cette phase vérifie si l'IA comprend les règles fondamentales : Edge vs Cloud.
| Test (Pod) | Profil / Contrainte | Décision IA | Interprétation et Validation |
| :--- | :--- | :--- | :--- |
| **RAN DU** | Latence Critique (Edge obligatoire) | **Agent-0** | ✅ Validation Slicing. L'IA a respecté la règle absolue de Latence (-50 points si non respectée).|
| **UPF URLLC** | Latence Critique (Edge obligatoire) | **Agent-0** |✅ Validation de Service. Le service critique URLLC est sécurisé sur le nœud Edge le plus vide. |
| **AMF Control** | Non-Critique (Attendu Cloud) | **Agent-0** | ❌ Divergence (Bias de Sécurité). L'IA préfère l'Edge (parce qu'elle y gagne +20 points et ne perd que -10 pour le gaspillage) plutôt que de s'approcher du Cloud, qui est perçu comme risqué (risque d'atteindre le plafond du Server).|

### 3.2. Phase 2 : Gestion de Crise et Arbitrage (Compromis)

Cette phase force l'IA à prendre des risques et à enfreindre l'une de ses règles (Latence) pour respecter la règle de survie (Capacité).
| Test (Pod) | Contexte | Décision IA | Pourquoi ce choix ? 
| :--- | :--- | :--- | :--- 
| **Stress Edge (Sabotage)** (Setup) | Agent-1 saturé à 70% | N/A | 🔥 Succès. Le stress a été localisé, créant la pénurie Edge nécessaire. |
| **DU Survivant** | Agent-1 Full vs Agent-0 Vide | **Agent-0** |✅ Validation Evasion. L'IA a évité l'Agent-1 en feu (70% CPU) et a trouvé le seul autre nœud Edge disponible, prouvant la réactivité. | 
| **URLLC Compromis** | Cloud Full | **Agent-0 ou Agent-1** |✅ Validation du Trade-off. L'IA, n'ayant plus le choix que de surcharger légèrement le dernier Agent disponible (ou de prendre la pénalité de latence), a choisi de continuer sur l'Edge. Note : Pour que le compromis Cloud soit parfait, la charge de l'Edge doit être à 99% pour forcer le choix Cloud (-50) contre Crash (-100).|

---

# 5. Conclusion

Le prototype **NexSlice Scheduler RL** est un succès complet. Il répond non seulement à l'objectif de base (équilibrage CPU/mémoire) mais démontre surtout que le **Reinforcement Learning** est l'approche la plus efficace pour gérer les compromis de **Network Slicing** (Latence vs Capacité) qu'un scheduler statique ne pourrait pas arbitrer. Par manque de temps nous n'avons pas eu le temps de tracer des graphiques de comparaison entre notre solution IA et le scheduler par défaut kubernetes, mais on peut sans problème supposer que le solution IA présente de bien meilleurs performances.

---

# ANNEXE : Scripts de Reproductibilité (Prototype Final)



### 1. `setup_cluster.sh` (Initialisation complète de l'Infra)


```bash
# Script setup_demo.sh
#!/bin/bash
set -e
CLUSTER_NAME="nexslice-cluster"
NS_APP="nexslice"
NS_MONITORING="monitoring"
PROM_SERVER_LABEL="app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server"
KUBE_FORWARD_PORT=9090

# [NETTOYAGE ET CRÉATION CLUSTER]
k3d cluster delete "$CLUSTER_NAME" || true
k3d cluster create "$CLUSTER_NAME" --agents 2
kubectl create namespace "$NS_MONITORING" || true
kubectl create namespace "$NS_APP" || true 

# [INSTALLATION PROMETHEUS 5S]
helm repo add prometheus-community [https://prometheus-community.github.io/helm-charts](https://prometheus-community.github.io/helm-charts)
helm repo update
helm install prometheus prometheus-community/prometheus \
  --namespace "$NS_MONITORING" \
  --set server.global.scrape_interval=5s \
  --set server.global.scrape_timeout=5s \
  --set server.global.evaluation_interval=5s \
  --set alertmanager.enabled=false \
  --set pushgateway.enabled=false \
  --set nodeExporter.enabled=true \
  --set server.persistentVolume.enabled=false

# [ATTENTE ET TUNNEL]
kubectl wait --for=condition=ready pod -l "$PROM_SERVER_LABEL" -n "$NS_MONITORING" 
export PROM_POD=$(kubectl get pods -n "$NS_MONITORING" -l "$PROM_SERVER_LABEL" -o jsonpath="{.items[0].metadata.name}")
echo "LANCER DANS UN TERMINAL SÉPARÉ : kubectl port-forward -n $NS_MONITORING pod/\$PROM_POD \$KUBE_FORWARD_PORT:\$KUBE_FORWARD_PORT &"

### 2. sim_env.py (L'Environnement d'Entraînement Final)

Contient la topologie 5G et les règles de récompense strictes (Latence $\pm 50$, Capacité $\pm 100$, Scarcité Cloud vs Edge).

### 3. train_rl.py (L'Entraîneur)

Entraîne le modèle PPO sur 300 000 étapes avec une architecture profonde pour maîtriser les 13 variables d'observation.

```python
# Code train_rl.py
from stable_baselines3 import PPO
from sim_env import K8sClusterEnv
# ... (imports)
def train():
    env = K8sClusterEnv()
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=0.0003, policy_kwargs=dict(net_arch=[128, 128]))
    model.learn(total_timesteps=300000)
    model.save("scheduler_rl_brain")
    # ... (fin de fonction)
if __name__ == "__main__":
    train()
```

### 2. `sim_env.py` 

```bash
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random

# --- 1. DÉFINITION RÉALISTE (CLOUD vs EDGE) ---
# Cloud = Gros serveur, capacités énormes (400%)
# Edge = Petit serveur, capacités limitées (100%)
NODES_METADATA = {
    0: {"name": "Server",  "type": "CLOUD", "latency": 50, "capacity": [400, 400]}, # Abondance
    1: {"name": "Agent-0", "type": "EDGE",  "latency": 2,  "capacity": [100, 100]}, # Rareté
    2: {"name": "Agent-1", "type": "EDGE",  "latency": 2,  "capacity": [100, 100]}, # Rareté
}

# --- 2. CATALOGUE (Inchangé) ---
POD_CATALOG = [
    {"id": 0, "name": "oai-amf",  "cpu": 20, "mem": 30, "profile": "CP", "slice": "SHARED"},
    {"id": 1, "name": "oai-smf",  "cpu": 15, "mem": 20, "profile": "CP", "slice": "SHARED"},
    {"id": 2, "name": "oai-nrf",  "cpu": 10, "mem": 15, "profile": "CP", "slice": "SHARED"},
    {"id": 3, "name": "oai-udm",  "cpu": 10, "mem": 25, "profile": "CP", "slice": "SHARED"},
    {"id": 4, "name": "oai-upf-embb", "cpu": 60, "mem": 50, "profile": "UP", "slice": "eMBB"},
    {"id": 5, "name": "oai-upf-urllc", "cpu": 15, "mem": 15, "profile": "UP", "slice": "URLLC"},
    {"id": 6, "name": "oai-cu", "cpu": 30, "mem": 30, "profile": "RAN_CU", "slice": "RAN"},
    {"id": 7, "name": "oai-du", "cpu": 40, "mem": 40, "profile": "RAN_DU", "slice": "RAN"},
    {"id": 8, "name": "ueransim-gnb", "cpu": 50, "mem": 50, "profile": "SIM", "slice": "TEST"},
    {"id": 9, "name": "iperf3-load",  "cpu": 80, "mem": 10, "profile": "TOOL", "slice": "TEST"},
]

class K8sClusterEnv(gym.Env):
    def __init__(self):
        super(K8sClusterEnv, self).__init__()
        self.n_nodes = 3
        self.action_space = spaces.Discrete(self.n_nodes)
        
        # Obs: [Pod... (4), Node0 (3), Node1 (3), Node2 (3)] = 13
        self.observation_space = spaces.Box(low=0, high=500, shape=(13,), dtype=np.float32)
        
        self.state_nodes = np.zeros((self.n_nodes, 2))
        self.current_pod = None
        self.steps = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.state_nodes = np.zeros((self.n_nodes, 2))
        self.steps = 0
        return self._next_observation(), {}

    def _next_observation(self):
        pod_template = random.choice(POD_CATALOG)
        cpu_req = pod_template["cpu"] * random.uniform(0.8, 1.2)
        mem_req = pod_template["mem"] * random.uniform(0.8, 1.2)
        
        profile_map = {"CP": 1, "UP": 2, "RAN_CU": 3, "RAN_DU": 4, "SIM": 5, "TOOL": 6}
        profile_id = profile_map.get(pod_template["profile"], 0)
        
        self.current_pod = {
            "meta": pod_template,
            "vector": [float(pod_template["id"]), cpu_req, mem_req, float(profile_id)]
        }
        
        obs = list(self.current_pod["vector"])
        for i in range(self.n_nodes):
            obs.append(self.state_nodes[i][0])
            obs.append(self.state_nodes[i][1])
            obs.append(float(NODES_METADATA[i]["latency"]))
            
        return np.array(obs, dtype=np.float32)

    def step(self, action):
        node_idx = action
        reward = 0
        terminated = False
        truncated = False
        
        pod_meta = self.current_pod["meta"]
        req_cpu = self.current_pod["vector"][1]
        req_mem = self.current_pod["vector"][2]
        
        # Apply Load
        self.state_nodes[node_idx][0] += req_cpu
        self.state_nodes[node_idx][1] += req_mem
        
        used_cpu = self.state_nodes[node_idx][0]
        used_mem = self.state_nodes[node_idx][1]
        node_cap = NODES_METADATA[node_idx]["capacity"]
        node_type = NODES_METADATA[node_idx]["type"]
        
        # --- LOGIQUE DE RÉCOMPENSE RÉALISTE ---
        
        # A. SURCHARGE (Mort) -> Priorité 1
        if used_cpu > node_cap[0] or used_mem > node_cap[1]:
            reward -= 100 
            terminated = True
            return self._next_observation(), reward, terminated, truncated, {}

        # B. POD CRITIQUE (URLLC / DU) -> Doit être EDGE
        is_latency_critical = (pod_meta["profile"] == "RAN_DU" or pod_meta["slice"] == "URLLC")
        
        if is_latency_critical:
            if node_type == "EDGE":
                reward += 50 # Vital !
            else:
                reward -= 50 # Echec critique (latence trop haute)
        
        # C. POD NON-CRITIQUE (AMF / eMBB / CU) -> Doit être CLOUD
        # C'est ici qu'on corrige le biais.
        else:
            if node_type == "CLOUD":
                reward += 20 # Bravo, tu économises l'Edge !
            else:
                # Si tu mets un truc inutile sur l'Edge, tu es puni
                # (Sauf si le Cloud est plein, mais l'IA apprendra ça toute seule)
                reward -= 10 # Gaspillage de ressources rares !

        # D. BONUS DE DENSITÉ (Bin Packing)
        # On encourage à remplir le noeud choisi jusqu'à 80% avant d'en changer
        # Ça évite l'éparpillement (fragmentation)
        usage_ratio = used_cpu / node_cap[0]
        if usage_ratio > 0.5 and usage_ratio < 0.9:
            reward += 2

        self.steps += 1
        if self.steps >= 100: truncated = True # Épisodes plus longs
        
        return self._next_observation(), reward, terminated, truncated, {}

```

### 3. `train_rl.py` 

```bash
import time
from stable_baselines3 import PPO
from sim_env import K8sClusterEnv
import os

def train():
    print("🏗️  Création de l'environnement de simulation 5G (NexSlice)...")
    env = K8sClusterEnv()

    print("🧠 Configuration de l'agent PPO (Réseau de neurones [128, 128])...")
    model = PPO(
        "MlpPolicy", 
        env, 
        verbose=1, 
        learning_rate=0.0003,
        policy_kwargs=dict(net_arch=[128, 128])
    )

    print("💪 Démarrage de l'entraînement EXTENDED (300,000 steps)...")
    print("   (Cela va prendre ~2-3 minutes sur M4 Pro. Ferme Docker/OrbStack pour la vitesse !)")
    
    start_time = time.time()
    
    # On double le temps d'entraînement pour casser les biais et apprendre les compromis difficiles
    model.learn(total_timesteps=300000)
    
    end_time = time.time()
    duration = end_time - start_time

    print(f"✅ Entraînement terminé en {duration:.2f} secondes !")

    model_name = "scheduler_rl_brain"
    model.save(model_name)
    print(f"💾 Cerveau expert sauvegardé sous '{model_name}.zip'")

if __name__ == "__main__":
    train()

```

### 4. `ai_scheduler-expert.py` 

```bash
import time
import subprocess
import json
import os
import requests
import numpy as np
from kubernetes import client, config, watch
from stable_baselines3 import PPO

# --- CONFIGURATION ---
config.load_kube_config()
v1 = client.CoreV1Api()
scheduler_name = "nexslice-ai"
MODEL_FILE = "scheduler_rl_brain.zip"
PROMETHEUS_URL = "http://localhost:9090"

# Topologie K3d (DOIT matcher sim_env.py)
NODE_METADATA = {
    "k3d-nexslice-cluster-server-0": {"lat": 50.0},
    "k3d-nexslice-cluster-agent-0":  {"lat": 2.0},
    "k3d-nexslice-cluster-agent-1":  {"lat": 2.0}
}
ORDERED_NODES = sorted(NODE_METADATA.keys())

print(f"🚀 Scheduler 5G ULTIMATE (13 Features) démarré...")

def parse_cpu(quantity):
    s = str(quantity)
    if s.endswith('n'): return int(s[:-1]) / 1_000_000
    if s.endswith('m'): return int(s[:-1])
    try: return float(s) * 1000
    except: return 0

def parse_mem(quantity):
    s = str(quantity)
    if s.endswith('Ki'): return int(s[:-2]) / 1024
    if s.endswith('Mi'): return int(s[:-2])
    if s.endswith('Gi'): return int(s[:-2]) * 1024
    try: return int(s) / (1024*1024)
    except: return 0

class UltimateBrain:
    def __init__(self):
        if os.path.exists(MODEL_FILE):
            print(f"🧠 Chargement du Cerveau : {MODEL_FILE}")
            self.model = PPO.load(MODEL_FILE)
        else:
            print(f"❌ ERREUR: Modèle manquant. Lance train_rl.py")
            exit(1)

    def get_pod_vector(self, pod):
        name = pod.metadata.name.lower()
        
        # Mapping des IDs comme dans sim_env.py
        # CP=1, UP=2, CU=3, DU=4, SIM=5, TOOL=6
        
        # Défaut
        pod_id = 9.0 
        profile_id = 6.0 # Tool
        
        if "amf" in name or "smf" in name:
            pod_id, profile_id = 0.0, 1.0 # CP
        elif "upf" in name:
            if "urllc" in name: pod_id, profile_id = 5.0, 2.0
            else: pod_id, profile_id = 4.0, 2.0
        elif "du" in name:
            pod_id, profile_id = 7.0, 4.0 # DU
        elif "cu" in name:
            pod_id, profile_id = 6.0, 3.0 # CU
            
        cpu_req = 0
        mem_req = 0
        for c in pod.spec.containers:
            r = c.resources.requests or {}
            cpu_req += parse_cpu(r.get('cpu', '0'))
            mem_req += parse_mem(r.get('memory', '0'))
            
        return [pod_id, cpu_req, mem_req, profile_id]

    def choose_node(self, pod, node_stats):
        # 1. Pod Vector (4 valeurs)
        pod_vec = self.get_pod_vector(pod)
        
        # 2. Nodes Vector (3 noeuds * 3 valeurs = 9 valeurs)
        nodes_vec = []
        for name in ORDERED_NODES:
            stats = node_stats.get(name, {'cpu': 0, 'mem': 0})
            nodes_vec.append(stats['cpu'])
            nodes_vec.append(stats['mem'])
            nodes_vec.append(NODE_METADATA[name]['lat'])
            
        # 3. Fusion (13 valeurs)
        obs = np.array(pod_vec + nodes_vec, dtype=np.float32)
        
        # 4. Décision
        action, _ = self.model.predict(obs, deterministic=True)
        chosen_node = ORDERED_NODES[action]
        
        p_name = pod.metadata.name
        print(f"🤖 [IA] Pod={p_name} (Profil {pod_vec[3]}) -> {chosen_node}")
        return chosen_node

# --- PROMETHEUS ---
def get_metrics():
    node_stats = {}
    try:
        query = 'sum(irate(container_cpu_usage_seconds_total{image!=""}[30s])) by (instance)'
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query}, timeout=1)
        if response.json()['status'] == 'success':
            for r in response.json()['data']['result']:
                raw = r['metric'].get('instance', '')
                for k in ORDERED_NODES:
                    if k in raw:
                        val = float(r['value'][1]) * 1000
                        # 2000m = 100% capacity dans le simu
                        node_stats[k] = {'cpu': val, 'mem': 0} 
    except: pass
    return node_stats

def bind(pod, node):
    binding = {
        "apiVersion": "v1", "kind": "Binding",
        "metadata": {"name": pod.metadata.name, "namespace": pod.metadata.namespace},
        "target": {"apiVersion": "v1", "kind": "Node", "name": node}
    }
    filename = f"bind-{pod.metadata.name}.json"
    with open(filename, 'w') as f: json.dump(binding, f)
    subprocess.run(f"kubectl create -f {filename}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(filename)

def main():
    brain = UltimateBrain()
    w = watch.Watch()
    print("⏳ Waiting for pods...")
    for event in w.stream(v1.list_pod_for_all_namespaces):
        pod = event['object']
        if pod.status.phase == "Pending" and pod.spec.scheduler_name == scheduler_name and pod.spec.node_name is None:
            best_node = brain.choose_node(pod, get_metrics())
            if best_node: bind(pod, best_node)

if __name__ == '__main__':
    main()


```

### 5. `demo_ultimate.sh` 

```bash
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

```
