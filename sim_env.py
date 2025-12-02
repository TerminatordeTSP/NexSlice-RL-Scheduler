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
