# Summary

Simplified Chinese Universal Dependencies dataset converted from the GSD (traditional) dataset with manual corrections.

# Introduction

This is a simplified Chinese version of the UD Chinese GSD treebank. It is initially automatically converted into simplified Chinese with the OpenCC tool with patterns for mapping punctuation, then corrected with manual fixes.


# Named Entity Recognition (NER) layer

Each split's CoNLL-U file now carries an IOB2 named-entity layer in the MISC
column as `ner=<LABEL>`, where `<LABEL>` is one of `O`, `B-PER`, `I-PER`,
`B-LOC`, `I-LOC`, `B-ORG`, `I-ORG`. The labels are projected from the
[UNER_Chinese-GSD](https://github.com/UniversalNER/UNER_Chinese-GSD) dataset
(Traditional Chinese IOB2 NER annotations, part of
[Universal NER](https://www.universalner.org/)) onto the 4997 shared
GSD sentences (train/dev/test = 3997/500/500). Alignment is by sentence index
(`# parallel_id` = `zhgsd/{split}{N}`); for the 4992 sentences with identical
tokenization the label transfers position-by-position. The 5 sentences whose
tokenization diverges are re-aligned by a deterministic greedy walk over
normalized (Traditional→Simplified) forms and recorded in `merge.log`.

* `merge_ner.py` — stdlib-only, regenerable pipeline: parse UNER IOB2 and UD
  CoNLL-U, project labels, append `ner=` to MISC, and self-verify. Run with
  `python3 merge_ner.py`.
* `merge.log` — the 5 divergence blocks (sentence id, UNER/UD surface text, and
  the merge/split events).

## Using the NER layer

The `ner=` attribute uses the **IOB2** scheme and is present on every token's
MISC column:

* `O` — token is outside any named entity.
* `B-<TYPE>` — token begins an entity of `<TYPE>` (`PER` person, `LOC` location,
  `ORG` organization).
* `I-<TYPE>` — token continues the entity opened by the preceding `B-<TYPE>` /
  `I-<TYPE>` token of the same `<TYPE>`.

An entity span is the maximal run `B-TYPE I-TYPE*`. For example `火星 B-LOC` is
a one-token LOC entity, while `迦陵 B-LOC` + `舍利塔 I-LOC` form one LOC entity
across two tokens.

```python
def extract_entities(path):
    """Return a list of (entity_type, [token_forms]) spans from a CoNLL-U file."""
    def ner(misc):
        if misc == "_":
            return "O"
        for f in misc.split("|"):
            if f.startswith("ner="):
                return f[4:]
        return "O"

    spans, cur_type, cur = [], None, []
    def flush():
        nonlocal cur_type, cur
        if cur_type:
            spans.append((cur_type, cur))
        cur_type, cur = None, []

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                flush(); continue
            cols = line.split("\t")
            if len(cols) != 10:
                continue
            form, label = cols[1], ner(cols[9])
            if label == "O":
                flush()
            elif label.startswith("B-"):
                flush(); cur_type, cur = label[2:], [form]
            elif label.startswith("I-"):
                if cur_type == label[2:]:
                    cur.append(form)
                else:
                    flush(); cur_type, cur = label[2:], [form]
        flush()
    return spans
```

Notes:

* Entity boundaries follow the **UD tokenization**, not the original UNER
  tokenization. On the 5 divergent sentences the alignment walk merges or splits
  tokens, so an entity may span a single merged UD token (label = first UNER
  constituent's label) or several split UD tokens (first inherits the label, the
  rest are `O`). See `merge.log` for the exact events.
* The layer is orthogonal to the syntactic annotation — consume `ner=` on its
  own, or join it with `parallel_id` / the dependency parse as your task needs.
* The per-split token counts and label distribution are asserted by
  `merge_ner.py` (`EXPECTED_LABELS`) and summarized in `merge.log`; if you use
  this layer, cite Universal NER (BibTeX above).

### NER label distribution

Token counts per IOB2 label, per split. These are the **output** counts (after the
5 divergent sentences are merged/split) and are asserted by `merge_ner.py` on
every run against `EXPECTED_LABELS`:

| Label  |   train |   dev |  test |   total |
|--------|--------:|------:|------:|--------:|
| O      |   86699 | 11193 | 10599 |  108491 |
| B-PER  |    2155 |   238 |   206 |    2599 |
| I-PER  |    1479 |   165 |   125 |    1769 |
| B-LOC  |    2871 |   437 |   434 |    3742 |
| I-LOC  |    2514 |   313 |   337 |    3164 |
| B-ORG  |    1110 |   135 |   127 |    1372 |
| I-ORG  |    1786 |   184 |   182 |    2152 |
| tokens |   98614 | 12665 | 12010 |  123289 |

The only difference from the raw UNER counts is the collapse of the 5 divergent
sentences (a merged UD token keeps the first constituent's label); see `merge.log`.

The NER labels are redistributed from the
[UNER_Chinese-GSD](https://github.com/UniversalNER/UNER_Chinese-GSD) dataset
([Universal NER](https://www.universalner.org/); based on
[UD_Chinese-GSD](https://github.com/UniversalDependencies/UD_Chinese-GSD)). The
labels are licensed under
[CC BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/), the same license
as this treebank.

If you use this NER layer, please cite:

```bibtex
@inproceedings{mayhew2024universal,
  title={Universal NER: A Gold-Standard Multilingual Named Entity Recognition Benchmark},
  author={Stephen Mayhew and Terra Blevins and Shuheng Liu and Marek Šuppa and Hila Gonen and Joseph Marvin Imperial and Börje F. Karlsson and Peiqin Lin and Nikola Ljubešić and LJ Miranda and Barbara Plank and Arij Riab and Yuval Pinter},
  booktitle={Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics (NAACL)},
  year={2024},
  url={https://aclanthology.org/2024.naacl-long.243/}
}
```

# Changelog

* 2026-08-21
  * Added a Named Entity Recognition (NER) layer (`ner=` in MISC; IOB2 labels
    B/I-PER, B/I-LOC, B/I-ORG, O) projected from UNER_Chinese-GSD (Universal NER) onto the 4997
    GSD sentences. See `merge_ner.py` and `merge.log`.
  * Added "Using the NER layer" usage notes (IOB2 decoding, span reconstruction,
    Python example, divergent-sentence caveat) to README.
  * Added an NER label-distribution table (per-split IOB2 counts) to README.

* 2025-09-12 v2.16
  * add parallel corpus information to machine-readable metadata
  * add parallel data support with parallel_id metadata
* 2025-11-15 v2.17
  * Fixed attachment clf+det according to the guidelines.
* 2023-11-15 v2.13
  * Some PART/ADV should be SCONJ (see https://github.com/UniversalDependencies/docs/issues/460 and https://github.com/slavpetrov/parallel-treebanks/issues/30).
  * Fixed attachment clf+nummod according to the guidelines.
* 2023-05-15 v2.12
  * Fixed: PUNCT nodes must be attached via punct relations.
  * Fixed: Only some UPOS categories are compatible with mark.
  * Fixed: Only some UPOS categories are compatible with det.
  * Fixed: ADJ cannot be copula.
  * Fixed: Auxiliary must be tagged AUX.
  * Fixed: Nominal cannot be advmod.
  * Fixed: Verb cannot be advmod.
  * Added pinyin transcription.
  * Scaled down the set of copulas and other auxiliaries.
  * Fixed: function words must be leaves.
  * Fixed: case marker adpositions mislabled as acl.
* 2021-05-15 v2.8
  * Changed mark:relcl to mark:rel (as in the other Chinese treebanks).
  * Removed the relation case:dec (for 的 between two nouns; the other treebanks use just `case` here).
  * Removed the relation aux:aspect (the aspect particles 了 (le), 过 (guo), 着 (zhe) use just `aux` in the other treebanks).
  * Question particles changed from Mood=Inter to PartType=Int, and from discourse to discourse:sp.
  * Undocumented relation subtypes case:pref and case:suff changed to case.
  * Extent constructions converted from cop + mark:comp to compound:ext.
  * Changed mark:advb to mark:adv (as in the other Chinese treebanks).
* 2020-11-15 v2.7
  * Aspect markers relations are corrected from `case:aspect` to `aux:aspect`.
* 2019-11-15 v2.5
  * Initial release in Universal Dependencies, converted from UD_Chinese-GSD.
  * Google gave permission to drop the "NC" restriction from the license.
    This applies to the UD annotations (not the underlying content, of which Google claims no ownership or copyright).
  * Fixed punctuation (use East Asian punctuation where appropriate)
  * Fixed various parses and features (e.g., added Case=Ord)
  * Some manual fixes in tokenization



<pre>
=== Machine-readable metadata (DO NOT REMOVE!) ================================
Data available since: UD v2.5
License: CC BY-SA 4.0
Includes text: yes
Parallel: zhgsd
Genre: wiki
Lemmas: automatic with corrections
UPOS: converted with corrections
XPOS: manual native
Features: automatic with corrections
Relations: converted from manual
Contributors: Qi, Peng; Yasuoka, Koichi
Contributing: here
Contact: pengqi@cs.stanford.edu
===============================================================================
</pre>
