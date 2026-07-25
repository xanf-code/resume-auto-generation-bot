# Phase 11 — Frontend Command Deck (React + Vite + TypeScript)

**Goal:** The command-deck UI — job rail + 3-pane detail (LaTeX editor | PDF preview | skills sidebar), a live pipeline loader, and completion alerts.

**Prereq:** Phase 10. **Blocks:** Phase 12.

## Location & tooling
New top-level `frontend/` (React does not belong under Python `src/`). Gitignore `frontend/node_modules/`, `frontend/dist/`. Vite + React + TS. Test: **Vitest + React Testing Library + jsdom**.

Libraries: CodeMirror 6 (`@codemirror/legacy-modes/mode/stex`), `react-pdf`/`pdfjs-dist`, **Zustand**, Tailwind v4 + `tokens.css`, `sonner`, native `EventSource`/`Notification`/`AudioContext`.

## Structure (key files)
- `src/api/` — `client.ts`, `jobs.ts`, `compile.ts`, `types.ts` (mirror `PanelScore`, `SkillDump`, `Stage`, `JobStatus`).
- `src/sse/` — `JobStream.ts` (one `EventSource` per running job), `StreamManager.ts` (map + `listJobs` reconciliation on drop), `events.ts` (discriminated union + guards).
- `src/store/` — `jobsSlice`, `uiSlice`, `notificationsSlice`.
- `src/lib/` — `stages.ts` (`STAGE_ORDER`), `scoring.ts` (`THRESHOLD=78`, `MAX_ITERATIONS=4`, pass color), `notify.ts`, `sound.ts`, `download.ts`.
- `src/components/` — `layout/{TopBar,AlertsBell,CommandDeck}`, `rail/{JobRail,JobRailItem,StatusDot}`, `newjob/{NewJobModal,FileOrPasteField}`, `detail/{JobDetail,ThreePane}`, `detail/editor/{LatexEditor,EditorToolbar}`, `detail/pdf/{PdfPane,PdfViewer}`, `detail/skills/{SkillsSidebar,SkillCategory,CopyButton}`, `loader/{PipelineLoader,StageStepper,IterationCounter,RecruiterPanel,PersonaCard,AggregateGauge}`, `common/{ScoreBar,Pill,ToastHost}`.

## Event → UI mapping (`store.applyEvent`)
| event | mutation | UI |
|---|---|---|
| `stage{stage,iteration?}` | `job.stage`, maybe `job.iteration` | rail label; stepper "currently at" moves, checks fill to furthest-reached |
| `iteration{n}` | `job.iteration=n` | `it n/4` tag, pips |
| `persona_score{score}` | `job.personaScores[persona]=score` | that PersonaCard's 5 bars animate |
| `aggregate{score,passed}` | `job.aggregateScore/passed` | AggregateGauge fills; mini score tint |
| `done{status,best_score}` | terminal | loader→ThreePane, seed artifacts, **alert once** |
| `failed{error}` | terminal | error banner, **alert once** |

## Live loader
`StageStepper` tracks "furthest reached" (checks) + "currently at" (pulse) so writer back-edges read as a **new iteration**, not a glitch. `IterationCounter` n/4 pips. `RecruiterPanel` = 4 `PersonaCard`s (5 animated `ScoreBar`s each). `AggregateGauge` ring turns green at ≥78.

## Completion alert
Request `Notification` permission on **first job submit** (real gesture), not page load. On terminal event, guarded by `finishedNotified`: always toast (sonner) + chime (`AudioContext`, buffer preloaded on that first gesture); browser `Notification` only if `granted` **and** `document.visibilityState==='hidden'` (`tag: job_id`, click → focus + set active). `AlertsBell` keeps an in-app log + unread badge; mute toggle.

## New Job & seeding
`NewJobModal`: label + resume(`.tex` upload-or-paste) + JD(`.txt` upload-or-paste) + "N/3 running" hint → `POST /api/jobs` → insert rail, open SSE, set active. Opening a done job fires parallel GETs: `latex`→CodeMirror (unless user already edited in-session), `skills`→sidebar, `pdf` bytes→PdfPane ("Pipeline PDF"), `report`→score summary + `true_gaps`. Compile → `POST /api/compile` → swap PdfPane to "My compile" or show error panel. Download uses the currently shown PDF.

## TDD (Vitest + RTL)
### RED
- `store.applyEvent` reducer: each event type → correct slice mutation (table above).
- `lib/scoring.ts`: pass color flips at 78; persona average = mean of 5 dims.
- `StageStepper`: given `stage` + iteration bump, renders done/current/pending correctly and treats writer back-edge as new iteration.
- `useCompletionAlert`: fires once (double `done` replay → single alert); `Notification` only when granted AND tab hidden (mock `Notification` + `visibilityState`).
- `SkillCategory` Copy: writes comma-joined skills to a mocked `navigator.clipboard`.

### GREEN
Implement modules/components to pass.

## Acceptance
`cd frontend && npm test` green; `npm run dev` renders the deck; a mocked job flows through the loader end to end.

## Files
`frontend/**` (new), root `.gitignore` (edit).
