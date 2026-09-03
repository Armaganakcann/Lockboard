# Lockboard

**Agent proposes. Tools verify. Human defines what counts.**

A claim board for generated code. The verifier and the code under test do not share a scope. The agent can write code, run it, and argue about it —
it cannot grade itself and it cannot close the board.

## The three invariants

1. **PASS is never written.** `run_tests` passing leaves the status at `UNKNOWN`, and an
   exhausted 500-trial search also leaves it at `UNKNOWN`. Absence of a counterexample is
   not proof, so the board has no way to say so.
2. **Status is not agent-controlled.** No agent or tool can arbitrarily choose a verdict, and
   there is no `set_status` tool. `FAIL` is derived from a standing verifier-detected
   counterexample or non-termination; otherwise the board remains `UNKNOWN`. `LOCKED` can only
   be set by a human. Tools change the *evidence*; the status follows from it.
3. **Only a human decides what counts.** An agent can find a counterexample; it cannot rule
   that one does not apply. A person disputes it with a reason, which narrows the
   specification — and narrowing the specification changes what the search is allowed to
   generate next.

## The problem

`median(a)` for a nonempty odd-length numeric array. The board opens with a candidate that
passes every sorted and trivial input, which is exactly why basic tests are not enough:

```js
function median(a) {
  return a[Math.floor(a.length / 2)];
}
```

Replace it at any time — paste into the box, or have the agent call `submit_code`.

## Tools

| tool | writes | notes |
|---|---|---|
| `submit_code` | resets to `UNKNOWN` | loads a candidate. The smoke probe only confirms a loadable, callable `median(a)` that returns within its budget — it deliberately does not check correctness, or a wrong candidate could never get onto the board |
| `run_tests` | records a pass or a failing case; a failing case derives `FAIL` | basic suite; passing proves nothing and never upgrades the status |
| `find_counterexample` | records a counterexample; board derives `FAIL` | seeded search + shrinking, nothing hardcoded |
| `compare_reference` | records a disagreement; board derives `FAIL` | candidate vs. the page's independent reference |
| `measure_scaling` | records a timing note only, in every outcome | calibrates its repetition count against the candidate, reports its own noise floor, and returns `INCONCLUSIVE` when it cannot resolve a trend. If the benchmark itself runs out of time it reports `ABORTED` and leaves the status alone — a slow measurement is a fact about the measurement, not about the code |
| `add_claim` | clears evidence about the old claim, so the board falls back to `UNKNOWN` | a new claim is a claim about something else; the specification and human disputes stand |
| `propose_lock` | nothing | asks a human to close the board |
| `list_board` | read-only | candidate, claim, specification, disputes, status, evidence, counterexample |

Eight tools. None of them chooses a verdict — they add or remove evidence, and the board
reads the status off that evidence. Disputing a counterexample and locking the board are page
controls with no tool behind them.

Registered on `document.modelContext`, falling back to `navigator.modelContext`. Every
control on the page calls the same function the tool calls — there is no DOM-scraping path.

### `find_counterexample` is a search, not a memory

It generates inputs from a seeded PRNG, compares each against the reference, then shrinks the
first disagreement — dropping element pairs, then rank-normalizing to distinct small integers
so the minimal case is readable. Seeded, so a recorded demo replays exactly:

```
seed 2026 -> disagreement at trial 6
  found as  [3,2,-7,-6,3]
  minimal   [1,0,2]   expected 1   actual 0
```

A different `seed` finds a different route to the same defect.

## The dispute loop

A counterexample is a fact about the code. Whether it *counts* is a judgement about the
problem, and the board gives that judgement only to a person.

When a counterexample stands, the page offers a reason — *outside specification*, *invalid
input domain*, *expected behaviour changed* — and a constraint to add. Disputing does not
delete the finding; it narrows the specification, and the generator honours the narrowed
spec from then on. Constraints are applied constructively rather than by rejection sampling,
because filtering random arrays for "already sorted" would almost never draw one.

The agent reads the current specification through `list_board` and re-verifies against it.
So the same code can move from `FAIL` to *no counterexample found* without anyone touching
the code — and still not reach `PASS`:

```
agent   find_counterexample   -> [1,0,2] expected 1, actual 0     FAIL
human   dispute               -> outside specification
                                 spec now requires sorted input
agent   find_counterexample   -> 500 trials, no disagreement      UNKNOWN
human   Lock                                                      LOCKED
```

That is the whole product in four lines. The agent proposed, the tools verified, and the
person decided what the problem actually was.

Note the division of labour between the two ways a board can change. Changing the *scope* of
an existing claim is handled through human dispute and specification updates; `add_claim`
starts a *new* claim and clears the evidence tied to the previous one. Rewriting the claim
text is therefore not a repair path — an agent cannot edit its way out of a counterexample
that still applies to the question actually being asked.

## Execution model

Submitted code never runs on the page thread. Each tool call builds a fresh Worker from a
Blob — hardening, harness and candidate as one script, so there is no `eval` and the CSP
needs no `'unsafe-eval'` — and terminates it when the call is done.

This is **browser-isolated execution with explicit network/API hardening and host-enforced
termination**. It is not a security sandbox in the sense that it would contain deliberately
hostile code, and nothing here should be read as that claim.

### The trust boundary is the point

The candidate is asked exactly one question — *what do you return for this input?* The
reference implementation, the input generator, the shrinker and every verdict live on the
page thread, where submitted code has no reach.

An earlier build ran the reference inside the same Worker. Two attacks broke it, and both
are now regression tests:

- **Corrupting the reference.** A candidate beginning `Array.prototype.sort = function(){ return this; }`
  made the in-worker reference agree with it. The same buggy median that failed at trial 6
  came back clean after 500 trials.
- **Forging a verdict.** A candidate calling `postMessage({type:'done', result:{found:false}})`
  at load time raced ahead of the real search, and the board reported the forgery.

Both are closed by construction rather than by filtering: the reference moved out of reach,
and the harness captures `postMessage` into a closure before hardening deletes the global,
so a candidate has no way to emit a message the page would accept. A candidate that
overwrites `self.onmessage` can stop answering — it cannot answer falsely, and silence is
reported as a failure.

### What the sandbox actually enforces

Each property was checked in Chromium rather than assumed:

- **No network.** The page ships `connect-src 'none'`, and a blob Worker inherits the
  document policy. An unhardened worker fetching a same-origin URL is refused with
  *"Refused to connect … because it violates the following Content Security Policy directive:
  `connect-src 'none'`"*. WebSocket does not throw under this policy — it constructs and
  lands in `CLOSED` — so `WebSocket` is stripped inside the worker as well.
- **No `eval`.** `script-src 'self'` carries no `'unsafe-eval'`, and it reaches the worker:
  a candidate calling `eval` gets an `EvalError`.
- **No reachable escape hatches.** `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`,
  `importScripts`, `Worker`, `SharedWorker`, `indexedDB`, `caches`, `BroadcastChannel`,
  `RTCPeerConnection`, `postMessage` and `close` are deleted along the whole prototype chain
  — shadowing `self` alone leaves `Object.getPrototypeOf(self).fetch` reachable — and
  `navigator.sendBeacon` is cleared. A probe candidate reports `own: · proto: none`. There is
  no DOM in a worker.
- **Timeouts are real.** Each input carries a 1 s budget; a candidate that does not halt is
  killed with `terminate()`, which a same-thread `new Function` could never do. Because the
  page drives one input at a time, it knows exactly which one hung:

```
did not return within 1000 ms on [-1,0,1]
```

That is recorded as a counterexample, not a tool error — a candidate that does not halt is a
failing candidate. The page stays responsive throughout.

A candidate can still burn CPU or allocate memory until it is terminated. That is the
accepted cost, and the timeout is the answer to it.

## Run it

WebMCP is a secure-context API, so serve over `localhost` rather than opening `file://`:

```
npx http-server . -p 8099
```

In a browser without WebMCP the badge says so and every control still works — the page is
fully usable by a human alone.

## Demo (2 min)

1. Open the page. Status `UNKNOWN`.
2. Agent: `run_tests` → all basic tests pass, status **stays** `UNKNOWN`.
3. Agent: `find_counterexample` → `FAIL`, minimal case `[1,0,2]`, expected 1, actual 0.
4. Human: dispute it — *outside specification*, spec now requires sorted input.
5. Agent: `find_counterexample` again → 500 trials, nothing. Status back to `UNKNOWN`,
   never `PASS`.
6. Agent: `propose_lock` → banner appears, board stays open.
7. Human presses **Lock**.

## Non-goals

No accounts, no persistence, no backend. One problem, one board, one browser tab.

## Licence

MIT — see `LICENSE`.
