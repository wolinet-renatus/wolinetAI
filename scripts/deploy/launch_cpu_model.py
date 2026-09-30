#!/usr/bin/env python3
"""
Helper script to launch a CPU-optimized GGUF model in Xinference safely.
Handles authentication, CLI token caching, and optimal CPU parameters (n_ctx, n_parallel)
to prevent out-of-memory (OOM) subactor crashes.
"""

import argparse
import hashlib
import os
import sys

try:
    from xinference.client import RESTfulClient
except ImportError:
    print("Error: 'xinference' package is required. Run 'pip install xinference' first.", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Safely launch a CPU GGUF model in Xinference.")
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("XINFERENCE_ENDPOINT", "http://127.0.0.1:9997"),
        help="Xinference server URL (default: http://127.0.0.1:9997)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("XINFERENCE_USERNAME", "admin"),
        help="Admin username (default: admin or $XINFERENCE_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("XINFERENCE_PASSWORD"),
        help="Admin password (or set $XINFERENCE_PASSWORD)",
    )
    parser.add_argument(
        "--model-name",
        default="deepseek-coder-instruct",
        help="Model name (default: deepseek-coder-instruct)",
    )
    parser.add_argument(
        "--size-in-billions",
        default="1_3",
        help="Model size (default: 1_3)",
    )
    parser.add_argument(
        "--quantization",
        default="Q4_K_M",
        help="Quantization (default: Q4_K_M)",
    )
    parser.add_argument(
        "--n-ctx",
        type=int,
        default=2048,
        help="Context window size to avoid RAM OOM (default: 2048)",
    )
    parser.add_argument(
        "--n-parallel",
        type=int,
        default=1,
        help="Number of parallel inference slots (default: 1)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    password = args.password
    if not password:
        password = input(f"Enter password for '{args.username}': ").strip()

    print(f"Connecting to Xinference at {args.endpoint}...")
    client = RESTfulClient(args.endpoint)

    print(f"Authenticating as '{args.username}'...")
    try:
        client.login(args.username, password)
        print("✅ Authentication successful!")
    except Exception as e:
        print(f"❌ Login failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Persist the token to authenticate future xinference CLI calls
    token = client._get_token()
    if token:
        hashed_ep = hashlib.sha256(args.endpoint.encode("utf-8")).hexdigest()
        auth_dir = os.path.expanduser("~/.xinference/auth")
        os.makedirs(auth_dir, exist_ok=True)
        with open(os.path.join(auth_dir, hashed_ep), "w") as f:
            f.write(token)
        print(f"✅ Saved CLI token to {auth_dir}/{hashed_ep}")

    print(
        f"Launching {args.model_name} (CPU, n_ctx={args.n_ctx}, n_parallel={args.n_parallel}, quantization={args.quantization})..."
    )
    try:
        model_uid = client.launch_model(
            model_name=args.model_name,
            model_engine="llama.cpp",
            model_format="ggufv2",
            model_size_in_billions=args.size_in_billions,
            quantization=args.quantization,
            n_gpu=None,
            n_gpu_layers=0,
            n_ctx=args.n_ctx,
            n_parallel=args.n_parallel,
        )
        print(f"\n🎉 SUCCESS! Model is running with UID: {model_uid}")
    except Exception as e:
        print(f"❌ Failed to launch model: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
