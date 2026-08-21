#!/usr/bin/env python3
"""Merge UNER_Chinese-GSD IOB2 NER labels into UD_Chinese-GSDSimp CONLLU files.

Projects NER labels positionally onto the UD tokens, appending ``ner={label}`` to
each token's MISC field, so each split becomes one self-contained multi-task
CONLLU file (UD treebank + NER layer).

Approach (see handoff/plan):
  * Sentences pair by index: UD ``# parallel_id`` == ``zhgsd/{split}{N}``.
  * Aligned sentences (equal token count): label[i] -> UD token[i], guarded by a
    per-position form-length check.
  * Divergent sentences (unequal token count): a deterministic greedy walk
    re-aligns via normalized (Traditional->Simplified) form equality, handling
    UNER merges (take first constituent's label) and UD splits (first sub-token
    inherits, rest O). Any unmatchable pair hard-errors (never a silent label).

Stdlib only. Writes in place; git preserves the pristine history.
"""
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent


def find_workspace(start: Path) -> Path:
    """Return the ancestor dir that contains UNER_Chinese-GSD (sibling of the repo)."""
    cur = start.resolve()
    for _ in range(6):
        if (cur / "UNER_Chinese-GSD").is_dir():
            return cur
        cur = cur.parent
    die(f"could not locate UNER_Chinese-GSD in any ancestor of {start}")


UNER_DIR = find_workspace(REPO) / "UNER_Chinese-GSD"
SPLITS = ("train", "dev", "test")

EXPECTED_SENTENCES = {"train": 3997, "dev": 500, "test": 500}
EXPECTED_TOKENS = {"train": 98614, "dev": 12665, "test": 12010}

# Verified label multisets (per plan; collapse merges/splits into the UD token set).
EXPECTED_LABELS = {
    "train": {"O": 86699, "B-PER": 2155, "B-LOC": 2871, "I-LOC": 2514,
              "B-ORG": 1110, "I-PER": 1479, "I-ORG": 1786},
    "dev": {"O": 11193, "B-ORG": 135, "B-LOC": 437, "B-PER": 238,
            "I-ORG": 184, "I-LOC": 313, "I-PER": 165},
    "test": {"O": 10599, "B-LOC": 434, "I-LOC": 337, "B-ORG": 127,
             "I-ORG": 182, "B-PER": 206, "I-PER": 125},
}

VALID_LABELS = {"O", "B-PER", "I-PER", "B-LOC", "I-LOC", "B-ORG", "I-ORG"}
# 塤 appears only inside the divergent test s#96 and can never be learned from
# aligned data; pin it explicitly.
SUPPLEMENT_MAP = {"塤": "埙"}


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_iob2(path: Path, split: str):
    """Return list of {'text': str, 'tokens': [(form, label), ...]}."""
    if not path.is_file():
        die(f"UNER input missing: {path}")
    sentences = []
    cur_text = ""
    cur_tokens = []
    lineno = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        lineno += 1
        if not line:
            if cur_tokens:
                sentences.append({"text": cur_text, "tokens": cur_tokens})
                cur_text, cur_tokens = "", []
            continue
        if line.startswith("#"):
            if line.startswith("# text"):
                cur_text = line.split("=", 1)[1].strip()
            continue
        fields = line.split("\t")
        if len(fields) != 5:
            die(f"{path}:{lineno}: malformed IOB2 row ({len(fields)} fields): {line!r}")
        try:
            n = int(fields[0])
        except ValueError:
            die(f"{path}:{lineno}: non-integer id {fields[0]!r}")
        if n != len(cur_tokens) + 1:
            die(f"{path}:{lineno}: id sequence broken: expected {len(cur_tokens) + 1}, got {n}")
        cur_tokens.append((fields[1], fields[2]))
    if cur_tokens:
        sentences.append({"text": cur_text, "tokens": cur_tokens})
    return sentences


def parse_conllu(path: Path, split: str):
    """Return list of sentence dicts. Hard-errors if MISC already has ner=."""
    sentences = []
    cur_meta = []
    cur_rows = []
    cur_forms = []
    cur_sent_id = None
    cur_parallel_id = None
    lineno = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        lineno += 1
        if not line:
            if cur_rows or cur_meta:
                if cur_sent_id is None:
                    die(f"{path}:{lineno}: sentence block without # sent_id")
                sentences.append({
                    "meta": cur_meta,
                    "rows": cur_rows,
                    "forms": cur_forms,
                    "sent_id": cur_sent_id,
                    "parallel_id": cur_parallel_id,
                    "labels": [None] * len(cur_rows),
                })
                cur_meta, cur_rows, cur_forms = [], [], []
                cur_sent_id = cur_parallel_id = None
            continue
        if line.startswith("#"):
            cur_meta.append(line)
            if line.startswith("# sent_id"):
                cur_sent_id = line.split("=", 1)[1].strip()
            elif line.startswith("# parallel_id"):
                cur_parallel_id = line.split("=", 1)[1].strip()
            continue
        fields = line.split("\t")
        if len(fields) != 10:
            die(f"{path}:{lineno}: malformed CONLLU row ({len(fields)} fields): {line!r}")
        if "ner=" in fields[9]:
            die(f"{path}:{lineno}: MISC already contains ner= (re-run guard): {fields[9]!r}")
        cur_rows.append(line)
        cur_forms.append(fields[1])
    if cur_rows or cur_meta:
        if cur_sent_id is None:
            die(f"{path}:{lineno}: trailing block without # sent_id")
        sentences.append({
            "meta": cur_meta,
            "rows": cur_rows,
            "forms": cur_forms,
            "sent_id": cur_sent_id,
            "parallel_id": cur_parallel_id,
            "labels": [None] * len(cur_rows),
        })
    return sentences


# --------------------------------------------------------------------------- #
# TC -> SC char map (learned from aligned sentences only)
# --------------------------------------------------------------------------- #
def learn_tc_sc_map(uner_all, ud_all):
    obs = {}  # tc_char -> set(sc_char)
    for split in SPLITS:
        usents = uner_all[split]
        vsents = ud_all[split]
        for us, vs in zip(usents, vsents):
            if len(us["tokens"]) != len(vs["forms"]):
                continue  # divergent; skip
            for (uf, _), vf in zip(us["tokens"], vs["forms"]):
                if len(uf) == 1 and len(vf) == 1:
                    obs.setdefault(uf, set()).add(vf)
                elif len(uf) == len(vf) > 1:
                    for c1, c2 in zip(uf, vf):
                        obs.setdefault(c1, set()).add(c2)
    cmap = {}
    for tc, vals in obs.items():
        if len(vals) == 1:
            v = next(iter(vals))
            if v != tc:
                cmap[tc] = v
    cmap.update(SUPPLEMENT_MAP)
    return cmap


# --------------------------------------------------------------------------- #
# Projection
# --------------------------------------------------------------------------- #
def project(uner_sent, ud_sent, cmap, split):
    """Fill ud_sent['labels']; return list of event strings for merge.log."""
    utoks = uner_sent["tokens"]
    uforms = ud_sent["forms"]
    labels = ud_sent["labels"]
    events = []

    if len(utoks) == len(uforms):
        # Aligned path: position is the anchor.
        for i, ((uf, ul), vf) in enumerate(zip(utoks, uforms)):
            if len(uf) != len(vf):
                die(f"{split} {ud_sent['parallel_id']}: length mismatch at pos {i}: "
                    f"{uf!r} vs {vf!r}")
            labels[i] = ul
        return events

    # Divergent path: deterministic greedy walk on normalized forms.
    def norm(s):
        return "".join(cmap.get(c, c) for c in s)

    pid = ud_sent["parallel_id"]
    i = j = 0
    nu = len(utoks)
    nv = len(uforms)
    while i < nu and j < nv:
        uf, ul = utoks[i]
        vf = uforms[j]
        if norm(uf) == norm(vf):
            labels[j] = ul
            i += 1
            j += 1
            continue
        # UNER merge: concat(UNER[i..i+k]) == UD[j]
        matched = False
        for k in range(2, 5):
            if i + k <= nu:
                parts = [t[0] for t in utoks[i:i + k]]
                if norm("".join(parts)) == norm(vf):
                    first_label = utoks[i][1]
                    labels[j] = first_label
                    events.append(
                        f"merge UNER[{i}..{i + k - 1}] ({','.join(parts)}) "
                        f"-> UD[{j}] ({vf}) label={first_label}"
                    )
                    i += k
                    j += 1
                    matched = True
                    break
        if matched:
            continue
        # UD split: UNER[i] == concat(UD[j..j+k])
        for k in range(2, 5):
            if j + k <= nv:
                parts = uforms[j:j + k]
                if norm(uf) == norm("".join(parts)):
                    assigned = [ul] + ["O"] * (k - 1)
                    labels[j] = ul
                    for m in range(1, k):
                        labels[j + m] = "O"
                    events.append(
                        f"split UNER[{i}] ({uf}) -> UD[{j}..{j + k - 1}] "
                        f"({','.join(parts)}) label={','.join(assigned)}"
                    )
                    i += 1
                    j += k
                    matched = True
                    break
        if matched:
            continue
        die(f"{split} {pid}: cannot align UNER[{i}] ({uf!r}, {ul}) with UD[{j}] ({vf!r})")
    if i != nu or j != nv:
        die(f"{split} {pid}: leftover UNER tail from token {i}/{nu}, "
            f"UD tail from token {j}/{nv}")
    return events


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def emit_conllu(sentences, path: Path):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for sent in sentences:
            for line in sent["meta"]:
                fh.write(line + "\n")
            for row, label in zip(sent["rows"], sent["labels"]):
                fields = row.split("\t")
                misc = fields[9]
                fields[9] = f"ner={label}" if misc in ("_", "") else f"{misc}|ner={label}"
                fh.write("\t".join(fields) + "\n")
            fh.write("\n")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# Built-in verification
# --------------------------------------------------------------------------- #
def verify_output(path: Path, split: str):
    counts = Counter()
    n_sent = 0
    n_tok = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 10:
            die(f"{path}: malformed output row ({len(fields)} fields)")
        misc = fields[9]
        ner_fields = [f for f in misc.split("|") if f.startswith("ner=")]
        if len(ner_fields) != 1:
            die(f"{path}: token missing/ambiguous ner= in MISC: {misc!r}")
        label = ner_fields[0][4:]
        if label not in VALID_LABELS:
            die(f"{path}: invalid NER label {label!r} in MISC {misc!r}")
        counts[label] += 1
        n_tok += 1
        if fields[0].startswith("1\t"):  # crude sentence-counter via ids
            pass
    return counts, n_tok


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    if not UNER_DIR.is_dir():
        die(f"UNER_Chinese-GSD not found at {UNER_DIR}")

    uner_all = {}
    ud_all = {}
    for split in SPLITS:
        uner_all[split] = parse_iob2(UNER_DIR / f"zh_gsd-ud-{split}.iob2", split)
        ud_all[split] = parse_conllu(REPO / f"zh_gsdsimp-ud-{split}.conllu", split)

    # Pairing assertions.
    for split in SPLITS:
        n = EXPECTED_SENTENCES[split]
        if len(uner_all[split]) != n or len(ud_all[split]) != n:
            die(f"{split}: sentence count mismatch "
                f"UNER={len(uner_all[split])} UD={len(ud_all[split])} expected {n}")
        for idx in range(n):
            want = f"zhgsd/{split}{idx + 1}"
            got = ud_all[split][idx]["parallel_id"]
            if got != want:
                die(f"{split} s#{idx + 1}: parallel_id {got!r} != expected {want!r}")

    cmap = learn_tc_sc_map(uner_all, ud_all)

    divergence = {split: [] for split in SPLITS}
    for split in SPLITS:
        for us, vs in zip(uner_all[split], ud_all[split]):
            events = project(us, vs, cmap, split)
            if events:
                divergence[split].append((vs["sent_id"], vs["parallel_id"],
                                          us["text"], _ud_text(vs), events))

    # Write outputs.
    for split in SPLITS:
        emit_conllu(ud_all[split], REPO / f"zh_gsdsimp-ud-{split}.conllu")

    # Write merge.log.
    write_merge_log(divergence)

    # Built-in verification.
    for split in SPLITS:
        path = REPO / f"zh_gsdsimp-ud-{split}.conllu"
        counts, n_tok = verify_output(path, split)
        if n_tok != EXPECTED_TOKENS[split]:
            die(f"{split}: token count {n_tok} != expected {EXPECTED_TOKENS[split]}")
        if counts != EXPECTED_LABELS[split]:
            die(f"{split}: label multiset mismatch:\n"
                f"  got {dict(sorted(counts.items()))}\n"
                f"  exp {EXPECTED_LABELS[split]}")
        n_sent = len(ud_all[split])
        non_o = sum(v for k, v in counts.items() if k != "O")
        nd = len(divergence[split])
        print(f"{split}: {n_sent} sentences, {n_tok} tokens, "
              f"{non_o} non-O labels, {nd} divergent re-aligned")

    print("OK: all splits merged and verified.")


def _ud_text(vs):
    for m in vs["meta"]:
        if m.startswith("# text"):
            return m.split("=", 1)[1].strip()
    return ""


def write_merge_log(divergence):
    lines = [
        "# NER merge log — UNER_Chinese-GSD IOB2 -> UD_Chinese-GSDSimp CONLLU MISC",
        f"# date: {datetime.now().isoformat(timespec='seconds')}",
        "# command: python3 merge_ner.py",
        f"# learned TC->SC map entries: {len(SUPPLEMENT_MAP)} supplement "
        f"+ corpus-derived (see SUPPLEMENT_MAP + aligned-sentence learning)",
        "",
    ]
    total = 0
    for split in SPLITS:
        for sent_id, pid, uner_text, ud_text, events in divergence[split]:
            total += 1
            lines.append(f"## {split} {pid} (sent_id: {sent_id})")
            lines.append(f"# UNER text: {uner_text}")
            lines.append(f"# UD   text: {ud_text}")
            for ev in events:
                lines.append(ev)
            lines.append("")
    with open(REPO / "merge.log", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
