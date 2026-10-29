# Pipeline 09 approved implementation plan

Implement nearest-continuity independently on feature/possession-inference.
No commits, pushes, baseline/scorer changes, frontend changes or E2–E4.

1. Add synthetic policy and integration tests; observe failure before implementation.
2. Add package entry point, strategy.py (evidence and bounded same-team gaps),
   pipeline.py (ATD/XML loading and staged CSV/JSON publication).
3. Use published inclusive halves 11185–90651 and 110808–190197, 199319 rows.
   Default gap limit 25 frames, unknown X, no D inference. No smoothing of
   observed evidence. Metadata includes inputs, settings, execution and occupancy.
4. Document contracts and reproduction. Run relevant pytest and Black.
5. Generate and score only if licensed tracking and public truth are available;
   report missing assets honestly. Never tune on public truth.

Ruling: retain the explicitly requested current feature branch. Reproduce the
small nearest-player calculation locally and parity-test it because Pipeline 05
must stay unchanged. Reuse existing readers, logging and staged publication.

Verification: 29 relevant tests passed, including official validation of a
synthetic 199319-row submission and all four published half edges. Black checks
passed for each changed Python file; git diff --check passed. Independent review
found no blockers. Broader pipeline/utility collection requires missing cv2.
Full-match generation, occupancy and public scoring remain blocked: data/ and
output/ contain no match assets and MTAH_DATA_DIR is unset. No tuning performed.
