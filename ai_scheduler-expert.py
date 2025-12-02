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
