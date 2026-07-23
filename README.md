# Cooperative Driving with Language Agents — A Method Survey

A curated comparison of recent methods for **cooperative autonomous driving**, spanning LLM-based negotiation agents and end-to-end V2X driving stacks. For each method we track the primary mechanism, evaluation setting, whether evaluation is closed- or open-loop, and the reported metrics.

🌐 **Webpage:** [Bhargavhs.github.io/cooperative-driving-survey](https://Bhargavhs.github.io/cooperative-driving-survey/) (served via GitHub Pages from `main` / root).

## Language and Negotiation Agents

| Method | Primary Mechanism | Evaluation Setting | Closed/Open Loop | Metric |
|---|---|---|---|---|
| **AgentsCoDriver** (IEEE T-ITS, 2024) | LLM social reasoning | HighwayEnv | Closed | Success rate, collision rate, communication/token cost |
| **CoLMDriver** (ICCV, 2025) | LLM negotiation and waypoints | InterDrive/CARLA (MDrive) | Closed | Driving Score (DS), Success Rate (SR) |
| **CoopReflect** (AAMAS, 2026) | V2V message refinement | TalkingVehiclesGym | Closed | Task success / collision avoidance rate, traffic efficiency (speed/completion) |
| **CoMAL** (SDM, 2025) | Role memory and reasoning | Flow/SUMO | Closed | Traffic-flow efficiency (avg. velocity/throughput vs. RL baselines) |
| **KoMA** (IEEE T-IV, 2024) | Knowledge-driven LLM planning | HighwayEnv | Closed | Success rate, efficiency (avg. speed) |
| **AgentsCoMerge** (IEEE Journal, 2024) | LLM cooperative merging | SUMO/LimSim++, nuScenes, HighD | Closed | Merging success, travel time / avg. speed, collision/safety |
| **V2V-LLM** (ICRA, 2026) | Centralized MLLM fuses shared CAV perception features | V2V-QA benchmark | Open | Planning: L2 error, collision rate; grounding/notable-object: F1-type accuracy |
| **V2V-GoT** (ICRA, 2026) | Graph-of-thoughts over occlusion-aware perception QAs + planning-aware prediction QAs | V2V-QA-style benchmark extending V2V-LLM | Open | L2 error, collision rate |
| **SwarmDrive** (2026, not yet published) | Decentralized edge SLMs exchange post-inference intent distributions | Single occluded-intersection executable study | Closed | Success rate, end-to-end latency |

## End-to-End Cooperative Driving

| Method | Primary Mechanism | Evaluation Setting | Closed/Open Loop | Metric |
|---|---|---|---|---|
| **UniV2X** (AAAI, 2025) | Sparse-dense V2X E2E | DAIR-V2X, V2X-Sim | Open | Planning: L2 error, collision rate; stage-wise perception (detection mAP, tracking), occupancy IoU, transmission cost (BPS) |
| **COOPERNAUT** (CVPR, 2022) | V2V latent sharing | AutoCastSim/CARLA | Closed | Success rate, collision rate on 3 accident-prone scenario types |
| **CoDriving** (IEEE TPAMI, 2025) | Driving-request V2X E2E | V2Xverse | Closed | Driving Score (DS), Success Rate (SR), route completion, infraction score; plus modular perception metrics |
| **V2X-VLM** (TR Part C, 2025) | VLM-based V2X planning | DAIR-V2X | Open | L2 error, collision rate |
| **CoGoal3D** (ECCV, 2026) | Two-stage V2X 3D fusion: multiscale 3D-aware global fusion to handle spatial misalignment from differing collaborator height/attitude, then proposal refinement with an auxiliary 3D point reconstruction task | DAIR-V2X, V2V4Real, V2X-Real | Open | — |

## Notes

- **Closed-loop** = the policy's actions feed back into the simulator (CARLA, SUMO, HighwayEnv, etc.); **open-loop** = evaluation against logged data / QA benchmarks without action feedback.
- Contributions welcome — open a PR adding a row with method, venue, mechanism, eval setting, loop type, and metrics.

## Citation

If you find this comparison useful, please star the repo and cite the original papers.
