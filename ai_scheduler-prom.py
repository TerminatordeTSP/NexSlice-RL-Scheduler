import time
import json
import os
import subprocess
import requests # Pour parler à Prometheus
import numpy as np
from kubernetes import client, config, watch
from stable_baselines3 import PPO

# Config
config.load_kube_config()
v1 = client.CoreV1Api()
scheduler_name = "nexslice-ai"
MODEL_FILE = "scheduler_rl_brain.zip"
PROMETHEUS_URL = "http://localhost:9090" # Le tunnel qu'on vient de créer

print(f"🚀 Scheduler RL + PROMETHEUS (Temps Réel)...")

def parse_cpu(quantity):
    # (Ta fonction de parsing habituelle...)
    s = str(quantity)
    if s.endswith('n'): return int(s[:-1]) / 1_000_000
    if s.endswith('m'): return int(s[:-1])
    if s.endswith('u'): return int(s[:-1]) / 1000
    try: return float(s) * 1000
    except: return 0

def parse_mem(quantity):
    # (Ta fonction de parsing habituelle...)
    s = str(quantity)
    if s.endswith('Ki'): return int(s[:-2]) / 1024
    if s.endswith('Mi'): return int(s[:-2])
    if s.endswith('Gi'): return int(s[:-2]) * 1024
    if s.endswith('m'): return int(s[:-1]) / (1024*1024*1000)
    try: return int(s) / (1024*1024)
    except: return 0

class RLBrain:
    def __init__(self):
        if os.path.exists(MODEL_FILE):
            print(f"🧠 Chargement du modèle RL Expert ({MODEL_FILE})...")
            self.model = PPO.load(MODEL_FILE)
        else:
            print(f"❌ ERREUR: Modèle {MODEL_FILE} introuvable !")
            exit(1)

    def choose_node(self, pod, node_stats):
        req_cpu, req_mem = 0, 0
        for container in pod.spec.containers:
            requests = container.resources.requests or {}
            req_cpu += parse_cpu(requests.get('cpu', '0'))
            req_mem += parse_mem(requests.get('memory', '0'))
        
        # Estimation grossière de l'impact (sur base 2000m allocatable)
        pod_cpu_pct = (req_cpu / 2000) * 100
        pod_mem_pct = (req_mem / 4096) * 100

        sorted_nodes = sorted(node_stats.keys())
        obs_list = [pod_cpu_pct, pod_mem_pct]
        
        for name in sorted_nodes:
            metrics = node_stats[name]
            obs_list.append(metrics['cpu_pct'])
            obs_list.append(metrics['mem_pct'])
            
        obs_vector = np.array(obs_list, dtype=np.float32)
        action, _ = self.model.predict(obs_vector, deterministic=True)
        chosen_node = sorted_nodes[action]
        
        print(f"   🔥 [Prometheus] Obs: {[round(x,1) for x in obs_list]} -> Action: {chosen_node}")
        return chosen_node

# --- LA NOUVEAUTÉ : REQUÊTE PROMETHEUS ---
def get_prometheus_metrics():
    """ Interroge Prometheus pour avoir la charge CPU instantanée (fenêtre 30s) """
    node_stats = {}
    
    # 1. On récupère d'abord la capacité des noeuds via K8s (ça ça change pas vite)
    try:
        nodes = v1.list_node().items
        capacities = {n.metadata.name: parse_cpu(n.status.allocatable['cpu']) for n in nodes}
    except: return {}

    # 2. On demande l'usage CPU à Prometheus (Langage PromQL)
    # On utilise 'irate' (Instant Rate) sur 30s pour être ultra réactif
    query = 'sum(irate(container_cpu_usage_seconds_total{image!=""}[30s])) by (instance)'
    
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
        data = response.json()
        
        if data['status'] != 'success':
            print("⚠️ Erreur Prometheus")
            return {}

        for result in data['data']['result']:
            # Le nom du noeud est souvent dans 'instance' (ex: k3d-nexslice-cluster-agent-0)
            node_name = result['metric'].get('instance', 'unknown')
            
            # Nettoyage du nom si besoin (parfois Prometheus ajoute le port)
            if node_name not in capacities: 
                # On essaie de matcher le nom K8s
                for k8s_name in capacities.keys():
                    if k8s_name in node_name:
                        node_name = k8s_name
                        break
            
            if node_name in capacities:
                usage_cores = float(result['value'][1]) * 1000 # En millicores
                capacity = capacities[node_name]
                pct_cpu = (usage_cores / capacity) * 100
                
                # On stocke (On met 0% RAM car on se focus CPU pour le test)
                node_stats[node_name] = {"cpu_pct": pct_cpu, "mem_pct": 0.0}

        # Sécurité : Si un noeud ne renvoie rien (0 charge), on l'ajoute à 0
        for k8s_name in capacities.keys():
            if k8s_name not in node_stats:
                 node_stats[k8s_name] = {"cpu_pct": 0.0, "mem_pct": 0.0}
                 
    except Exception as e:
        print(f"⚠️ Erreur connexion Prometheus: {e}")
        return {}
        
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
    brain = RLBrain()
    w = watch.Watch()
    
    print("⏳ En attente de Pods (Lecture via Prometheus)...")
    for event in w.stream(v1.list_pod_for_all_namespaces):
        pod = event['object']
        if (pod.status.phase == "Pending" and pod.spec.scheduler_name == scheduler_name and pod.spec.node_name is None):
            print(f"\n🔎 Pod détecté : {pod.metadata.name}")
            
            # C'est ici que ça change : On demande à Prometheus !
            stats = get_prometheus_metrics()
            
            if not stats: 
                print("⚠️ Prometheus pas encore prêt...")
                continue
            
            best_node = brain.choose_node(pod, stats)
            if best_node:
                bind(pod, best_node)
                print(f"✅ SUCCÈS : Assigné à {best_node}")

if __name__ == '__main__':
    main()
