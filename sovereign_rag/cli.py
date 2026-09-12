#!/usr/bin/env python3
"""
Sovereign RAG CLI Runner
========================
Usage:
  air10-sovereign-rag "transformer armature reaction" [--mode zero-llm|ollama|api] [--limit 5] [--json]
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sovereign_rag.engine import SovereignRAGMaster


def main():
    parser = argparse.ArgumentParser(description="AIR10 Sovereign 1000x RAG Engine")
    parser.add_argument("query", type=str, help="Search query or study topic")
    parser.add_argument("--mode", type=str, choices=["zero-llm", "ollama", "api"], default="zero-llm",
                        help="Serving mode (default: zero-llm)")
    parser.add_argument("--model", type=str, default=None, help="LLM model name (e.g. deepseek-r1:7b, gpt-4o-mini)")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of retrieved passages (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of markdown")

    args = parser.parse_args()

    engine = SovereignRAGMaster()
    result = engine.generate(query_text=args.query, mode=args.mode, model=args.model, top_k=args.limit)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "="*80)
        print(f"⚡ AIR10 SOVEREIGN 1000x RAG (Mode: {result.get('mode', 'unknown')} | Latency: {result.get('latency_ms', 0)}ms)")
        print("="*80)
        print(result.get("answer", "No answer."))
        print("\n" + "-"*80)
        print(f"📚 Grounded Citations ({len(result.get('citations', []))} items):")
        for idx, cite in enumerate(result.get("citations", []), 1):
            print(f"  [{idx}] {cite['source']} ({cite['type']})")
        print("="*80 + "\n")

if __name__ == "__main__":
    main()
