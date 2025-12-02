import time
import json
import os
import subprocess
import requests
import numpy as np
from kubernetes import client, config, watch
from stable_baselines3 import PPO

# --- CONFIG ---
config.load_kube_config()
v1 = client.CoreV1Api()
scheduler_name = "nexslice-ai"
MODEL_FILE = "scheduler_rl_brain.zip"
PROMETHEUS_URL = "http://localhost:9090"

# Topologie K3d (Hardcodée pour correspondre au simulateur)
NODE_MAP = {
    "k3d-nexslice-cluster-server-0": {"id": 0, "latency": 50.0}, # CLOUD
    "k3d-nexslice-cluster-agent-0":  {"id": 1, "latency": 2.0},  # EDGE
    "k3d-nexslice-cluster-agent-1":  {"id": 2, "latency": 2.0}   # EDGE
}

print(f"📡 Scheduler 5G 'NexSlice' démarré...")

def parse_cpu(quantity):
    s = str(quantity)
    if s.endswith('m'): return int(s[:-1])
    try: return float(s) * 1000
    except: return 0

def parse_mem(quantity):
    s = str(quantity)
    if s.endswith('Mi'): return int(s[:-2])
    if s.endswith('Gi'): return int(s[:-2]) * 1024
    try: return int(s) / (1024*1024)
    except: return 0

class NexSliceBrain:
    def __init__(self):
        if os.path.exists(MODEL_FILE):
            print(f"🧠 Modèle chargé: {MODEL_FILE}")
            self.model = PPO.load(MODEL_FILE)
        else:
            print(f"❌ Pas de modèle {MODEL_FILE} !")
            exit(1)

    def pod_to_vector(self, pod):
        """ Traduit un vrai Pod K8s en vecteur numérique pour l'IA """
        name = pod.metadata.name.lower()
        
        # 1. Identification du Profil (Doit matcher sim_env.py)
        # IDs: 0-3=CP, 4=UP-eMBB, 5=UP-URLLC, 6=CU, 7=DU, 8=SIM
        pod_id = 2.0 # Défaut
        profile_id = 0.0
        
        if "du" in name:          # OAI-DU (Distributed Unit)
            pod_id, profile_id = 7.0, 4.0 # RAN_DU (Edge Critical)
            print(f"   ⚡️ TYPE: RAN Distributed Unit (Latence Critique)")
            
        elif "cu" in name:        # OAI-CU
            pod_id, profile_id = 6.0, 3.0 # RAN_CU (Cloud OK)
            
        elif "upf" in name:       # User Plane
            if "urllc" in name:
                pod_id, profile_id = 5.0, 2.0 # UP-URLLC
                print(f"   ⚡️ TYPE: UPF URLLC (Latence Critique)")
            else:
                pod_id, profile_id = 4.0, 2.0 # UP-eMBB
                
        elif any(x in name for x in ["amf", "smf", "nrf", "udm", "ausf"]):
            pod_id, profile_id = 0.0, 1.0 # Control Plane
            
        # 2. Ressources
        req_cpu, req_mem = 0, 0
        for c in pod.spec.containers:
            r = c.resources.requests or {}
            req_cpu += parse_cpu(r.get('cpu', '0'))
            req_mem += parse_mem(r.get('memory', '0'))
            
        # Normalisation comme dans le simulateur
        # (On divise par des valeurs arbitraires "Max" pour avoir des petits chiffres)
        vec_cpu = req_cpu # On garde l'échelle millicores pour le simu
        vec_mem = req_mem 
        
        return [pod_id, vec_cpu, vec_mem, profile_id]

    def choose_node(self, pod, node_stats):
        # A. Vecteur Pod (4 valeurs)
        pod_vec = self.pod_to_vector(pod)
        
        # B. Vecteur Noeuds (9 valeurs : CPU, MEM, Latence pour chaque noeud)
        # L'ordre DOIT être : Server, Agent0, Agent1
        node_vec = []
        ordered_names = ["k3d-nexslice-cluster-server-0", "k3d-nexslice-cluster-agent-0", "k3d-nexslice-cluster-agent-1"]
        
        for name in ordered_names:
            stats = node_stats.get(name, {'cpu': 0, 'mem': 0})
            node_vec.append(stats['cpu']) # CPU Used
            node_vec.append(stats['mem']) # MEM Used
            node_vec.append(NODE_MAP[name]['latency']) # Latence fixe
            
        # C. Fusion
        obs = np.array(pod_vec + node_vec, dtype=np.float32)
        
        # D. Décision
        action, _ = self.model.predict(obs, deterministic=True)
        chosen_node = ordered_names[action]
        
        print(f"   🤖 Décision IA: {chosen_node}")
        return chosen_node

# --- PROMETHEUS ---
def get_metrics():
    # Simulation légère si Prometheus plante encore, pour que tu puisses tester le code Python
    # Si Prometheus marche, décommenter la requête requests.get(...)
    # Pour l'instant on renvoie des valeurs fictives pour tester la logique de nommage
    return {
        "k3d-nexslice-cluster-server-0": {'cpu': 10, 'mem': 10},
        "k3d-nexslice-cluster-agent-0":  {'cpu': 5,  'mem': 5},
        "k3d-nexslice-cluster-agent-1":  {'cpu': 5,  'mem': 5}
    }

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
    brain = NexSliceBrain()
    w = watch.Watch()
    print("⏳ Scheduler NexSlice en attente de pods...")
    
    for event in w.stream(v1.list_pod_for_all_namespaces):
        pod = event['object']
        if pod.status.phase == "Pending" and pod.spec.scheduler_name == scheduler_name and pod.spec.node_name is None:
            print(f"\n🔎 Pod détecté: {pod.metadata.name}")
            best_node = brain.choose_node(pod, get_metrics())
            if best_node:
                bind(pod, best_node)
                print(f"✅ Assigné à {best_node}")

if __name__ == '__main__':
    main()
