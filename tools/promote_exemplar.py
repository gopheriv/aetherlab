"""Review and promote high-scoring tournament winners into the curated exemplars.

The Quality Flywheel's "winners teach" channel (Phase 3) stashes critic-approved,
high-scoring tournament winners in ``<data_dir>/exemplar_candidates.json``. This
tool lets a MAINTAINER review them and emit a paste-ready snippet for
``aetherlab/services/scene_exemplars.py``.

Promotion is deliberately a human-reviewed code change: this script NEVER edits
`scene_exemplars.py` itself, because feeding LLM-written code straight back into
every future generation prompt is a supply-chain risk. Review the code (and,
ideally, run it through strict visual regression) before pasting it in.

    python tools/promote_exemplar.py --list
    python tools/promote_exemplar.py --show 0        # print full code for review
    python tools/promote_exemplar.py --emit 0        # paste-ready EXEMPLARS snippet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _store():
    from aetherlab.core.settings import load_settings
    from aetherlab.services.scene_exemplars import ExemplarCandidateStore

    settings = load_settings()
    return ExemplarCandidateStore(settings.data_dir / "exemplar_candidates.json")


def main(argv: list[str] | None = None) -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="list exemplar candidates")
    group.add_argument("--show", type=int, metavar="N", help="print candidate N's full code")
    group.add_argument("--emit", type=int, metavar="N", help="print a paste-ready EXEMPLARS snippet for N")
    args = parser.parse_args(argv)

    candidates = _store().list()
    if not candidates:
        print("No exemplar candidates yet. Run tournaments with a vision critic configured.")
        return 0

    if args.show is not None or args.emit is not None:
        idx = args.show if args.show is not None else args.emit
        if not (0 <= idx < len(candidates)):
            print(f"Index {idx} out of range (0..{len(candidates) - 1}).")
            return 2
        cand = candidates[idx]
        if args.emit is not None:
            print("# Promote into aetherlab/services/scene_exemplars.py after review:")
            print(f'_{cand["domain"].upper()}_PROMOTED = """{cand["code"]}"""')
            print(f'# EXEMPLARS["{cand["domain"]}"] = _{cand["domain"].upper()}_PROMOTED')
        else:
            print(f"# candidate {idx}: domain={cand['domain']} score={cand['score']} "
                  f"verdict={cand['verdict']} created={cand.get('created_at', '')}")
            print(cand["code"])
        return 0

    # default / --list
    print(f"{len(candidates)} exemplar candidate(s):")
    for i, cand in enumerate(candidates):
        print(f"  [{i}] domain={cand['domain']:<10} score={cand['score']:<5} "
              f"verdict={cand['verdict']:<6} lines={len(cand['code'].splitlines()):<4} "
              f"created={cand.get('created_at', '')}")
    print("\nReview with --show N; get a paste-ready snippet with --emit N. "
          "Promotion is a manual, reviewed edit to scene_exemplars.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
