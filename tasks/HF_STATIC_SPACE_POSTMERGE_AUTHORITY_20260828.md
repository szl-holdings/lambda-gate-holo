# Post-merge static Space authority repair

## Live failure

Protected-main release run `33184785729`, attempt 3, fails in `authorize-exact-governed-merge` at `scripts/hf_static_space.py guard` with:

`ContractError: exact main revision is not one unambiguous merged PR`

The immutable push tuple is exact:

- repository: `szl-holdings/lambda-gate-holo`
- push before / squash parent: `c17550f9c61dd2c25ac928218ec34ee47048e67c`
- push after / protected main: `11ceb3cc9b054a75813175ed831ae93e1e1dad3a`
- merged PR: `#5`
- PR head: `6e8f50dbec5ff3e6a6b9c82181e233c0198e12cd`
- base: `main@c17550f9c61dd2c25ac928218ec34ee47048e67c`
- merge commit: `11ceb3cc9b054a75813175ed831ae93e1e1dad3a`

The DCO job independently confirms the exact base-to-head push range. The live PR readback is closed, merged, repository-bound, and exact. The fragile component is the merge-commit `/commits/{source_sha}/pulls` association under the workflow-scoped token.

## Required permanent fix

Replace the initial merge-commit association dependency with a bounded, complete closed-pull-request inventory that proves exactly one pull request satisfies all of the following:

1. closed and merged;
2. `merge_commit_sha == source_sha`;
3. `base.ref == main`;
4. `base.sha == push.before`;
5. base and head repositories match the exact governed repository name and numeric ID;
6. head ref and immutable head SHA are present;
7. merged-by identity and merged-at timestamp are present;
8. the exact PR body evidence binds the PR head;
9. a second canonical inventory/readback remains byte-equivalent before credentials or publication.

Keep the independent `/commits/{PR_HEAD_SHA}/pulls` singleton binding for the exact PR head and keep every exact workflow/check-suite/job/readback gate. Do not accept commit-message parsing, PR-number guessing, an unbounded search, a first-match policy, or a fallback that weakens ambiguity rejection.

Use a deterministic API such as complete pagination of `pulls?state=closed&base=main&sort=updated&direction=desc`, with a governed upper bound and explicit pagination/incomplete-inventory failure. The selected PR must still be fetched by number and revalidated through `_exact_merged_pull_projection`.

## Tests

Add hostile tests for:

- two matching closed PR rows;
- unrelated closed PRs before/after the exact row;
- wrong merge SHA, base SHA/ref, repository name/ID, missing head repository, missing merge identity/time;
- truncated/incomplete/pagination overflow inventory;
- inventory drift between first and final reads;
- exact singleton positive control where merge-commit association is empty or unavailable;
- preservation of exact head-association, workflow-run, check-suite, DCO, and body-evidence gates.

Remove this task file in the implementation commit. Run the complete exact Python 3.12.13 suite, build/validate, DCO, protected external release boundary, and fresh review. After protected squash merge, the push-triggered workflow must publish and independently measure the exact Hugging Face Space revision before any success claim.