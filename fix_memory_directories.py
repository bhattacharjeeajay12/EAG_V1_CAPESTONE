# Run this script once to ensure the Memory directories exist
import os

def create_memory_dirs():
    # Create main Memory directory
    memory_dir = "Memory"
    os.makedirs(memory_dir, exist_ok=True)
    print(f"Created main Memory directory at: {memory_dir}")

    # Create subdirectories for each agent
    agent_dirs = ["buy", "return", "order"]
    for agent in agent_dirs:
        agent_dir = os.path.join(memory_dir, agent)
        os.makedirs(agent_dir, exist_ok=True)
        print(f"Created memory directory for {agent} agent at: {agent_dir}")

if __name__ == "__main__":
    create_memory_dirs()
    print("Memory directories created successfully!")
