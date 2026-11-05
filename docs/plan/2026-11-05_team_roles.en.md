> Superseded by task 08 (2026-11-05); see `docs/plan/2026-11-05_workload_v2.zh.md` (Chinese only).

# Suggested roles for the five of us (for discussion at the 2026-11-05 team meeting)

All of this is a **suggestion**, to be settled after discussion at the meeting. Task IDs are in section 3 of `2026-11-05_status_and_plan.en.md`. Person-hours are computed by `scratch/plan/team_load.py` from the allocation ratios below; the ratios can be changed and the numbers recomputed. Chinese version: `2026-11-05_team_roles.zh.md`.

## Read this screen first

- **How it is split**: Workstreams are assigned by each person's strengths. Zizhang owns design and scope; Ron owns the core code and connecting the model; Yingxia owns rules, mock data, labelling and evaluation; Kylie owns the project schedule, communication with Jake, and presentations; Zhaohan starts with tasks that don't depend on specific skills (review tool trial, distance, docs, labelling), to be adjusted once their background is known (**to be confirmed by Zhaohan**).
- **Workload** (person-hours, ranges): Zizhang 57–90, Ron 89–137, Kylie 45–70, Yingxia 68–104, Zhaohan 42–66; total 300–466.
- **Bottleneck**: **Ron**. Most of the coding tasks on the critical path (data read-in, blind parse, connecting the model, controlled experiments) can only be done by Ron, who has about 48 to 73 hours on the critical path. Under the team contract Ron has the most time available, so the higher workload is intentional; the responses are in section 4.
- **All three commitments in the contract are met**: everyone owns at least one workstream; everyone shares the human labelling (H2, about 6 to 8 hours each); everyone presents the part they own at the midterm and at the final.

## 1. Owner and helpers for each workstream

| Workstream | Tasks | Owner | Helpers | Notes |
|---|---|---|---|---|
| Design and scope | S1, P1, T3 | Zizhang | Yingxia | Gatekeeper of the decision record: Zizhang checks whether any change crosses the boundary (for example, "should it be paid" showing up) |
| Schema implementation and data read-in | S2, S3 | Ron | Zizhang | Zizhang checks the YAML against the table-creation statements, and the read-in results against the task 06 numbers |
| Prototype rework per the decisions | P2, P5, T2 | Zizhang | Ron | Removing old paths, layering the output, versioning tax and currency: these changes are small in scope and suit AI-assisted coding |
| Prototype rework per the decisions (core) | P3, P4 | Ron | Zizhang, Yingxia | Yingxia checks the P4 checklist item by item against the decision record |
| Rules and multi-level duplicate check | R1, R2, R3 | Yingxia (R1), Zizhang (R2), Kylie (R3) | Zizhang, Kylie, Yingxia | Kylie reviews the R2 plain-language explanation from the perspective of a "PPG reader" |
| mock data | M1, M2 | Yingxia (M1), Kylie (M2) | Zhaohan, Zizhang | M2: Kylie keeps the holdout batch, which is used only once, in the final test |
| Model connection | L1, L2 | Ron (L1), Zizhang (L2) | Zizhang, Ron | The L2 docstrings and examples must be written for the model to read; Zizhang writes them and Ron wires them into the code |
| Human checking | H1, H2, H3 | Yingxia | Everyone (H2), Kylie, Zhaohan | H2: each person takes about 40 items, 20% double-labelled |
| Evaluation and controlled experiments | V1, V2, V3, V4 | Yingxia (V1, V2, V4), Ron (V3) | Ron, Yingxia | The with/without guardrails comparison in V3 is a course requirement and must be done |
| Review UI | U1, U2, U3 | Kylie (U1, U3), U2 see notes | Zhaohan, Ron | U2: if U1 concludes we should use an open-source tool, Zhaohan configures it (to be confirmed by Zhaohan); any part we build ourselves is Ron's |
| Distance | G1 | Zhaohan | Yingxia | Scheduled after the framework; addresses are not sent to external services |
| skill folder and docs | K1 | Zhaohan | Kylie | |
| Communication with Jake | J01 | Kylie | Zizhang | Zizhang writes the content of the questions; Kylie sends them, follows up and backfills the answers; Zizhang is not mainly the client contact |
| Midterm and final presentations | D1, D2 | Kylie | Everyone | Each person presents their own workstream |
| Task 05 wrap-up check | T1 | Yingxia | | |

## 2. Expected workload per person

| Person | Tasks owned | Person-hours (low–high) | Main skills |
|---|---|---|---|
| Zizhang | S1, P1, P2, P5, R2, L2, T2, T3 | 57–90 | Strategy, business judgement, AI-assisted coding |
| Ron | S2, S3, P3, P4, L1, V3 (the self-built part of U2) | 89–137 | Coding |
| Kylie | J01, M2, U1, U3, R3, D1, D2 | 45–70 | Organizing, communication, presenting |
| Yingxia | R1, M1, H1, H3, V1, V2, V4, T1 | 68–104 | Business and data analysis |
| Zhaohan | G1, K1, U2 (open-source configuration); a lot of helping | 42–66 | To be confirmed by Zhaohan |

On average 60 to 93 hours per person over about 4 weeks, or 15 to 23 hours per week (lighter in Thanksgiving week).

## 3. What each person does in the first week (2026-11-05 to 2026-11-11)

| Person | First week |
|---|---|
| Zizhang | Lead S1: go through schema v0 with the team and settle "how to order the first copy" and "how many retries"; start P1: revise the expectations of Codex's 88 edge cases one by one per the decision record; at the midterm update, present "project positioning and what changed this time" |
| Ron | Read the task 06 report and `06_schema_v0.yaml`; once S1 is finalized, start S2 (create the tables, read in the dev set, check the ID-relationship numbers); look over the old paths to be removed from the prototype and estimate the effort for P3 and P4 |
| Kylie | Put the 14 questions for Jake into an email and send it (J01), and set up a "question–answer–where it was backfilled" tracking sheet; set the custody rules for the M2 holdout batch; start U1: install Label Studio and Argilla and tick them off against section 6 of the decision record; lead the preparation of the midterm update |
| Yingxia | Start H1: labelling guide and sampling method; read task 06 B3 and list the positive and negative mock cases M1 needs to add; prepare the metric definitions for V1 |
| Zhaohan | Try out the open-source review tools with Kylie (U1); read the decision record and the pipeline diagram, and confirm their background and the direction they want to own (**to be confirmed by Zhaohan**); get ready to take part in the H2 labelling |

## 4. Bottlenecks and responses

- **Ron is the coding bottleneck.** S2, P3, P4 and L1 are all on the critical path, and only Ron can do them quickly. Responses:
  1. Code changes that are small in scope (P2, P5, R2, T2) go to Zizhang, written with AI assistance;
  2. The metric scripts and the Baseline (V1, V2) go to Yingxia;
  3. Prefer open-source tools for the review UI to reduce what we build ourselves (U1 reaches its conclusion first);
  4. Split P3 and P4 into two tracks; Yingxia prepares the P4 checklist and test cases, and Ron only writes the implementation.
- **Zhaohan's background is unknown.** For now, give them only tasks that don't depend on specific skills; if Zhaohan can code, they can take over S3 (moving into `src/`) or the self-built part of U2, directly reducing Ron's load.
- **Kylie is the only channel for communication with Jake.** Zizhang vets the content of the questions, and the answers are backfilled into the decision record and the cards, so that the same question isn't asked twice.

## 5. To decide at the meeting

1. Whether this split is accepted; Zhaohan's background and preferences.
2. The date of the midterm update (2026-11-12 for now) and of the final presentation (2026-12-03 for now).
3. The time and format of the weekly meeting; who updates the board (suggestion: Kylie compiles it, and each owner provides test reports).
4. Whether to add 4 new cards to the board: schema implementation, mock data, human checking, review UI.
