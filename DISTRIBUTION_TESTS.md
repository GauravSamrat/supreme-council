# Windows distribution verification

Verification date: 25 November 2026 (Asia/Kolkata).

| Check | Actual result |
| --- | --- |
| Existing Windows automated suite | 21 of 21 passed before packaging changes. |
| Clean Windows setup | Passed with Python 3.11 in a new directory with spaces. The installer created a virtual environment, installed dependencies and copied the template to an empty local `.env`. |
| Clean-install automated suite | 22 of 22 passed. HTTP inference requests were mocked. |
| Dependency consistency | `pip check` passed in the clean environment. |
| Tkinter desktop acceptance | The window initialized. Auto was selected, dark appearance applied, and invoking Run in Confidential mode surfaced the real CLI subprocess message in the progress panel and restored the controls. |
| Model selection and fallback | Automated checks passed for reliability scoring and decay, family diversity, replacing a failed free model, paid and unknown-price rejection, and synthesis failure with report preservation. |
| Quotas and cooldowns | Automated checks passed for concurrent reservations, request and token caps, evaluation caps, interrupted reservations, model and provider cooldowns, and the half-open probe lease. |
| Secret and private-file review | Checked local Git refs and reflogs, unique historical blobs, commit messages and tracked working-tree files against common secret patterns, known local credential values and private-data path patterns. The scan did not print values. No matches remained after review. This signature-based scan cannot establish that every possible secret format is absent. |

Live credentialed provider requests and billing checks were outside this distribution acceptance run. Account tier, catalog behavior and retention terms still need independent verification before use. Desktop cancellation, export and report navigation were not exercised by the Tkinter acceptance script. No dependency vulnerability scan or Windows executable code signing was performed.

The distribution is a source ZIP requiring a separate Python installation. The repository currently has no explicit redistribution license. Public download does not grant reuse or redistribution rights by itself.
