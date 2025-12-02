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
