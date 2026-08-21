# Summary

Simplified Chinese Universal Dependencies dataset converted from the GSD (traditional) dataset with manual corrections.

# Introduction

This is a simplified Chinese version of the UD Chinese GSD treebank. It is initially automatically converted into simplified Chinese with the OpenCC tool with patterns for mapping punctuation, then corrected with manual fixes.


# Named Entity Recognition (NER) layer

Each split's CoNLL-U file now carries an IOB2 named-entity layer in the MISC
column as `ner=<LABEL>`, where `<LABEL>` is one of `O`, `B-PER`, `I-PER`,
`B-LOC`, `I-LOC`, `B-ORG`, `I-ORG`. The labels are projected from
UNER_Chinese-GSD (Traditional Chinese IOB2 NER annotations) onto the 4997 shared
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

# Changelog

* 2026-08-21
  * Added a Named Entity Recognition (NER) layer (`ner=` in MISC; IOB2 labels
    B/I-PER, B/I-LOC, B/I-ORG, O) projected from UNER_Chinese-GSD onto the 4997
    GSD sentences. See `merge_ner.py` and `merge.log`.

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
