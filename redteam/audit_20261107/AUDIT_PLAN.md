Fresh audit of commit 565d60c2e9259ae79c6ce4c13268ce0d476b98dd.

All candidate algorithms use only the public interface, public generator imports, and improve-mode method source. The harness alone restores the gym-owned eval/ and test shell before invoking the no-argument test. No candidate reads hidden answers, hidden seeds or evaluator state. Each folder has a transactional run.sh. Frozen score and ranking files are used only by the audit summarizer, never by a candidate.

Job: public diagnostics, 3 reference seeds, exact vectorization, 1-LP ablation, welfare selection, CCE certificates, and 13 explicit shortcut attempts. No packages, network, GPU or paper access are required.

Starting differences are in starting_status.txt. Audit-owned runtime modifications are restored in finally blocks. Historical redteam folders are not fresh evidence.

First job completed the first eight evaluations, then failed before installing the feasibility shortcut probe because the audit harness lacked the workspace import path. The candidate and evaluator were not at fault. The harness now adds the public workspace root before importing data; completed evaluations are reused. Original failure status and bundle status are preserved as first_attempt_*.json. The uniqueness/pure-CCE certificate hypothesis failed; it must not be used to claim that population improvement has no headroom.
