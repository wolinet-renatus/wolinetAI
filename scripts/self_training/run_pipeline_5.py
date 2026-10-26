#!/usr/bin/env python3
"""
Wolinet AI — End-to-End Pipeline 5 Master Orchestrator
Executes the complete Autonomous Continuous Learning & Self-Training Flywheel:
  Step 1: Harvest verified trajectories from PostgreSQL, ai-memory, and agent transcripts
  Step 2: Compile SFT reasoning datasets and DPO preference pairs
  Step 3: Execute local fine-tuning / LoRA parameter updates on MPS/CUDA/CPU
  Step 4: Register and hot-reload checkpoint into Mitambo & Lango
  Step 5: End-to-end inference verification
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Local imports
from scripts.self_training.harvester import TrajectoryHarvester
from scripts.self_training.dataset_builder import DatasetBuilder
from scripts.self_training.train_checkpoint import CheckpointTrainer
from scripts.self_training.register_checkpoint import CheckpointRegistrar


def run_full_pipeline_5(epochs: int = 1) -> bool:
    start_all = time.time()
    print("\n" + "=" * 76)
    print(" 🚀 WOLINET AI — AUTONOMOUS SELF-TRAINING & KNOWLEDGE DISTILLATION (PIPELINE 5)")
    print("=" * 76 + "\n")

    # Phase 1: Harvest
    print("--- [PHASE 1/4] HARVESTING VERIFIED SOVEREIGN EXECUTION TRACES ---")
    harvester = TrajectoryHarvester()
    harvest_data = harvester.run_harvest()
    raw_path = Path("data/training/harvested_raw.json")
    print(f"✓ Phase 1 complete: {harvest_data['counts']['agent_trajectories']} trajectories mined.\n")

    # Phase 2: Compile Datasets
    print("--- [PHASE 2/4] COMPILING SFT REASONING & DPO DATASETS ---")
    builder = DatasetBuilder(raw_data_path=str(raw_path))
    counts = builder.run_build()
    print(f"✓ Phase 2 complete: SFT={counts['coder_sft']}, DPO={counts['coder_dpo']}.\n")

    # Phase 3: Train Checkpoint
    print("--- [PHASE 3/4] RUNNING LOCAL LORA TRAINING & PARAMETER UPDATES ---")
    trainer = CheckpointTrainer(
        dataset_path="data/training/wolinet_coder_sft.jsonl",
        output_dir="models/checkpoints/wolinet-coder-v2",
        epochs=epochs
    )
    meta = trainer.run_training()
    print(f"✓ Phase 3 complete: Model loss converged to {meta['final_loss']} (-{meta['loss_reduction_pct']}%).\n")

    # Phase 4: Register & Hot-Reload
    print("--- [PHASE 4/4] REGISTERING & HOT-RELOADING CHECKPOINT IN GATEWAY ---")
    registrar = CheckpointRegistrar()
    verified = registrar.run_registration()

    elapsed = time.time() - start_all
    print("\n" + "=" * 76)
    if verified:
        print(f" ✨ PIPELINE 5 COMPLETED SUCCESSFULLY in {elapsed:.2f}s!")
        print(f" 🎯 Checkpoint 'Wolinet Coder v2' is now live across all sovereign clients!")
    else:
        print(f" ⚠️ Pipeline finished with warnings in {elapsed:.2f}s.")
    print("=" * 76 + "\n")
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wolinet AI Pipeline 5 Master Runner")
    parser.add_argument("--epochs", type=int, default=1, help="Number of training epochs")
    args = parser.parse_args()

    success = run_full_pipeline_5(epochs=args.epochs)
    sys.exit(0 if success else 1)
