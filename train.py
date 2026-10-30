# train.py
import random
from agents import run_multi_agent_system

print("Starting training with synthetic data...\n")

# We will create 20 fake scenarios
for i in range(1, 21):
    print(f"\n========= Scenario {i} =========")

    # Create fake timeline
    timeline = [
        {
            "event_id": f"E{i}_1",
            "event_type": "TEMPERATURE_READING",
            "trust_score": round(random.uniform(0.1, 0.9), 2),
            "source": "SENSOR_14"
        },
        {
            "event_id": f"E{i}_2",
            "event_type": "COOLING_STATUS",
            "trust_score": round(random.uniform(0.3, 0.95), 2),
            "source": "MAINTENANCE_AGENT"
        },
        {
            "event_id": f"E{i}_3",
            "event_type": "NETWORK_ALERT",
            "trust_score": round(random.uniform(0.2, 0.85), 2),
            "source": "SECURITY_SENSOR"
        }
    ]

    # Create fake current state
    current_state = {
        "estimated_catastrophe_probability": round(random.uniform(0.4, 0.9), 2),
        "temperature": round(random.uniform(75, 110), 1),
        "backup_cooling_available": random.choice([True, False]),
        "shutdown_permission": random.choice([True, False])
    }

    # Run the multi-agent system
    result = run_multi_agent_system(timeline, current_state)

    print(f"Final Decision: {result['final_decision']}")
    print(f"Reason        : {result['reason']}")