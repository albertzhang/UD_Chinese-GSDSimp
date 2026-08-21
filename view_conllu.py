#!/usr/bin/env python3
"""Terminal viewer for the UD_Chinese-GSDSimp CoNLL-U files.

Renders each selected sentence as:
  * a header (sent_id / parallel_id / entity summary),
  * an inline surface line with NER spans colored by type,
  * an indented ASCII dependency tree (forms colored by NER, deprel labels).

stdlib-only; no pip / network. NER coloring honors the ner= attribute added by
merge_ner.py. Color auto-disables when stdout is not a TTY (e.g. when piped).

Examples:
  python3 view_conllu.py dev 3          # one sentence (dev-s3)
  python3 view_conllu.py dev 3 6        # range dev-s3..dev-s6
  python3 view_conllu.py dev-s9         # by sent_id
  python3 view_conllu.py dev --entities # only sentences with named entities
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent

NER_COLOR = {"PER": 91, "LOC": 94, "ORG": 92}  # bright red / blue / green
RESET = "\x1b[0m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"


def color_enabled(force_off):
    return not force_off and sys.stdout.isatty()


def c(code, s):
    return f"\x1b[{code}m{s}\x1b[0m"


def ner_of(misc):
    if misc in ("_", ""):
        return "O"
    for f in misc.split("|"):
        if f.startswith("ner="):
            return f[4:]
    return "O"


def color_form(form, ner, enabled):
    if not enabled or ner == "O":
        return form
    code = NER_COLOR.get(ner[2:])  # drop B-/I-
    return c(code, form) if code else form


def parse_conllu(path):
    sents, meta, toks = [], [], []
    sent_id = parallel_id = text = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            if toks:
                sents.append({"sent_id": sent_id, "parallel_id": parallel_id,
                              "text": text, "toks": toks})
                meta, toks = [], []
                sent_id = parallel_id = text = None
            continue
        if line.startswith("#"):
            if line.startswith("# sent_id"):
                sent_id = line.split("=", 1)[1].strip()
            elif line.startswith("# parallel_id"):
                parallel_id = line.split("=", 1)[1].strip()
            elif line.startswith("# text"):
                text = line.split("=", 1)[1].strip()
            continue
        f = line.split("\t")
        if len(f) != 10:
            continue
        tid, form, _lemma, upos, _xpos, _feats, head, deprel, _deps, misc = f
        toks.append({"id": tid, "form": form, "upos": upos,
                     "head": head, "deprel": deprel, "misc": misc,
                     "ner": ner_of(misc)})
    if toks:
        sents.append({"sent_id": sent_id, "parallel_id": parallel_id,
                      "text": text, "toks": toks})
    return sents


def build_tree(toks):
    """Return (root_id, kids, ids) keyed by integer token id."""
    ids = {}
    for t in toks:
        try:
            ids[int(t["id"])] = t
        except ValueError:
            pass
    kids = {i: [] for i in ids}
    root = None
    for i, t in ids.items():
        try:
            h = int(t["head"])
        except ValueError:
            h = -1
        if h == 0:
            root = i
        elif h in kids:
            kids[h].append(i)
    return root, kids, ids


def render_tree(root, kids, ids, enabled):
    def rec(nid, prefix, is_last):
        t = ids[nid]
        conn = "└─ " if is_last else "├─ "
        form = color_form(t["form"], t["ner"], enabled)
        print(prefix + conn + form + " " + DIM + f"({t['deprel']})" + RESET)
        child_pre = prefix + ("   " if is_last else "│  ")
        for i, cid in enumerate(kids[nid]):
            rec(cid, child_pre, i == len(kids[nid]) - 1)

    if root is None:
        print(DIM + "(no root)" + RESET)
        return
    t = ids[root]
    print(color_form(t["form"], t["ner"], enabled) + " " + DIM +
          f"(root/{t['upos']})" + RESET)
    for i, cid in enumerate(kids[root]):
        rec(cid, "", i == len(kids[root]) - 1)


def entity_summary(toks):
    labels = {t["ner"] for t in toks if t["ner"] != "O"}
    if not labels:
        return "no entities"
    return "entities: " + ", ".join(sorted({l[2:] for l in labels}))



def show(sent, enabled):
    toks = sent["toks"]
    sid = sent["sent_id"] or "?"
    pid = sent["parallel_id"] or ""
    name = (c(1, sid) + RESET) if enabled else sid
    dim = DIM if enabled else ""
    print(name + "  " + pid + "  " + dim + entity_summary(toks) + RESET * enabled)
    if sent["text"]:
        print(dim + "文本: " + RESET * enabled + sent["text"])
    print(" ".join(color_form(t["form"], t["ner"], enabled) for t in toks))
    print(dim + "依存树:" + RESET * enabled)
    root, kids, ids = build_tree(toks)
    render_tree(root, kids, ids, enabled)
    print()


def main():
    ap = argparse.ArgumentParser(
        description="Terminal CoNLL-U viewer with NER highlighting (stdlib-only).")
    ap.add_argument("split", nargs="?", default="dev",
                    help="split (train/dev/test) or sent_id (e.g. dev-s9)")
    ap.add_argument("start", nargs="?", default=None,
                    help="1-based index, or omit for first sentence")
    ap.add_argument("end", nargs="?", type=int, default=None,
                    help="optional 1-based end index (inclusive)")
    ap.add_argument("--entities", action="store_true",
                    help="show only sentences containing named entities")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--file", default=None, help="explicit CoNLL-U path")
    args = ap.parse_args()

    split = args.split or "dev"
    start = args.start
    # Allow a bare sent_id as the first argument.
    if split.startswith(("train-s", "dev-s", "test-s")):
        start, split = split, split.split("-s")[0]

    if split not in ("train", "dev", "test"):
        print(f"ERROR: unknown split {split!r} (use train/dev/test or sent_id)",
              file=sys.stderr)
        sys.exit(1)

    path = Path(args.file) if args.file else REPO / f"zh_gsdsimp-ud-{split}.conllu"
    if not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    sents = parse_conllu(path)
    enabled = color_enabled(args.no_color)

    if enabled:
        print(DIM + "NER 颜色: " + RESET + c(91, "PER") + " " + c(94, "LOC") +
              " " + c(92, "ORG") + DIM + "  (O 不着色)" + RESET, file=sys.stderr)

    if args.entities:
        sel = [s for s in sents if any(t["ner"] != "O" for t in s["toks"])]
    elif start is None:
        sel = sents[:1]
        if len(sents) > 1:
            print(DIM + f"(showing first of {len(sents)} sentences; "
                  f"pass an index/range or --entities)" + RESET, file=sys.stderr)
    else:
        if isinstance(start, str) and start.startswith(("train-s", "dev-s", "test-s")):
            want = start
            idx = next((i for i, s in enumerate(sents) if s["sent_id"] == want), None)
            if idx is None:
                print(f"ERROR: {want} not found", file=sys.stderr)
                sys.exit(1)
            sel = [sents[idx]]
        else:
            try:
                a = int(start)
            except ValueError:
                print(f"ERROR: bad start {start!r}", file=sys.stderr)
                sys.exit(1)
            b = args.end or a
            sel = sents[a - 1:b]

    if not sel:
        print("No sentences selected.")
        return
    for s in sel:
        show(s, enabled)


if __name__ == "__main__":
    main()
