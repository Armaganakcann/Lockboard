/* Lockboard: agent proposes, tools verify, human defines what counts.

   Trust boundary: the candidate runs in a Worker and is asked exactly one thing —
   "what do you return for this input?". The reference, the search, the shrinking and
   every verdict live on this thread, where submitted code cannot reach them. An earlier
   build ran the reference inside the same Worker; a candidate that reassigned
   Array.prototype.sort could make itself look clean. */
(() => {
  const DEFAULT_CANDIDATE = `function median(a) {
  return a[Math.floor(a.length / 2)];
}`;

  const DEFAULT_CLAIM =
    "This implementation correctly computes the median for every nonempty numeric array.";
  const DEFAULT_SEED = 2026;
  const MAX_CODE_CHARS = 20000;
  const MAX_TRIALS = 500;
  const PER_INPUT_MS = 1000;
  const SMOKE_MS = 1500;
  const SCALING_MS = 20000;

  const BASIC = [
    { input: [1, 2, 3], expected: 2 },
    { input: [3, 3, 3], expected: 3 },
    { input: [0], expected: 0 },
  ];
  const BOUNDARIES = [[0], [1, 1, 1], [1, 2, 3], [3, 2, 1], [-1, 0, 1]];

  /* What the human is allowed to narrow the problem to. Each one changes what the
     generator produces, so narrowing the spec changes what the verifier can find. */
  const CONSTRAINTS = {
    sorted: {
      label: "input is already sorted ascending",
      holds: (a) => a.every((v, i) => i === 0 || a[i - 1] <= v),
      apply: (a) => [...a].sort((x, y) => x - y),
    },
    nonneg: {
      label: "all values are non-negative",
      holds: (a) => a.every((v) => v >= 0),
      apply: (a) => a.map((v) => Math.abs(v)),
    },
    minlen3: {
      label: "length is at least 3",
      holds: (a) => a.length >= 3,
      apply: (a) => (a.length >= 3 ? a : [...a, ...a, ...a].slice(0, 3)),
    },
  };

  const REASONS = {
    outside_specification: "outside specification",
    invalid_input_domain: "invalid input domain",
    expected_behavior_changed: "expected behaviour changed",
  };

  const state = {
    candidateSrc: DEFAULT_CANDIDATE,
    claim: DEFAULT_CLAIM,
    spec: [],
    disputes: [],
    status: "UNKNOWN",
    locked: false,
    lockProposal: null,
    evidence: [],
    counter: null,
    busy: false,
  };

  const $ = (id) => document.getElementById(id);

  /* ---------- verifier: this thread only ---------- */

  function referenceMedian(a) {
    const s = Array.prototype.slice.call(a).sort((x, y) => x - y);
    return s[Math.floor((s.length - 1) / 2)];
  }

  function mulberry32(seed) {
    let s = seed | 0;
    return function () {
      s = (s + 0x6d2b79f5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const inSpec = (a) => state.spec.every((k) => CONSTRAINTS[k].holds(a));

  /* Constraints are applied constructively, not by rejection sampling: filtering random
     arrays for "already sorted" would almost never draw one. */
  function normalize(a) {
    return state.spec.reduce((acc, k) => CONSTRAINTS[k].apply(acc), a);
  }

  function generateInput(rand, i) {
    const raw =
      i < BOUNDARIES.length
        ? BOUNDARIES[i]
        : (() => {
            const len = 1 + 2 * (1 + Math.floor(rand() * 4)); // odd, 3..9
            const span = [10, 100, 1000][Math.floor(rand() * 3)];
            return Array.from({ length: len }, () => Math.floor(rand() * span * 2) - span);
          })();
    const a = normalize(raw);
    return inSpec(a) ? a : null;
  }

  /* Replace each value by its rank so a minimal case reads as distinct small ints. */
  function toRanks(a) {
    const order = [...a.keys()].sort((i, j) => a[i] - a[j]);
    const out = new Array(a.length);
    order.forEach((idx, rank) => {
      out[idx] = rank;
    });
    return out;
  }

  /* ---------- sandbox ---------- */

  /* Walks the prototype chain: shadowing `self` alone leaves
     Object.getPrototypeOf(self).fetch reachable. */
  const HARDENING = `
    const strip = (name) => {
      let o = self;
      while (o) {
        try { if (Object.getOwnPropertyDescriptor(o, name)) delete o[name]; } catch (e) {}
        o = Object.getPrototypeOf(o);
      }
      try {
        Object.defineProperty(self, name, {
          value: undefined, writable: false, configurable: false, enumerable: false,
        });
      } catch (e) {}
    };
    [
      "fetch", "XMLHttpRequest", "WebSocket", "EventSource", "importScripts",
      "Worker", "SharedWorker", "indexedDB", "caches", "BroadcastChannel",
      "RTCPeerConnection", "postMessage", "close",
    ].forEach(strip);
    try { self.navigator.sendBeacon = undefined; } catch (e) {}
  `;

  /* Runs BEFORE the candidate, so `post` is captured in a closure the candidate
     cannot reach — the global postMessage is gone by the time its code is parsed.
     It answers one question per message and computes nothing. */
  function SANDBOX_HARNESS(post, nonce) {
    self.onmessage = (ev) => {
      const m = ev.data || {};
      if (m.n !== nonce) return;
      if (m.cmd === "eval") {
        if (typeof median !== "function") {
          post({ n: nonce, id: m.id, ok: false, error: "no function named median is defined" });
          return;
        }
        try {
          post({ n: nonce, id: m.id, ok: true, value: median(m.input) });
        } catch (err) {
          post({ n: nonce, id: m.id, ok: false, error: String((err && err.message) || err) });
        }
        return;
      }
      if (m.cmd === "scaling") {
        /* Stays here because it needs many calls. It compares the candidate only
           against itself and the board refuses to draw a verdict from it. */
        try {
          if (typeof median !== "function") throw new Error("no median function");
          const SIZES = [200, 2000, 8000];
          const TARGET_MS = 30;
          const MAX_REPS = 500000;
          let sink = 0;
          const arrays = SIZES.map((n) => Array.from({ length: n }, (_, i) => n - i));

          /* A fixed repetition count was tuned for an O(1) candidate. Anything that
             actually sorts blew the time budget, so the count is calibrated against the
             largest input instead: one sample lands near TARGET_MS whatever the candidate
             costs, and the same count is reused for every size to keep sizes comparable. */
          const calibrate = (a) => {
            let n = 1;
            for (;;) {
              const t0 = performance.now();
              for (let i = 0; i < n; i++) sink += median(a);
              const ms = performance.now() - t0;
              if (ms >= 5) return Math.min(MAX_REPS, Math.max(1, Math.round((n / ms) * TARGET_MS)));
              if (n >= MAX_REPS) return MAX_REPS;
              n *= 4;
            }
          };
          const REPS = calibrate(arrays[arrays.length - 1]);

          const once = (a) => {
            const t0 = performance.now();
            for (let i = 0; i < REPS; i++) sink += median(a);
            return ((performance.now() - t0) * 1e6) / REPS;
          };
          for (const a of arrays) once(a); // warm every size first
          const times = arrays.map((a, k) => {
            const s = [];
            for (let r = 0; r < 7; r++) s.push(once(a));
            s.sort((x, y) => x - y);
            return {
              n: SIZES[k],
              ns_per_call: Number(s[0].toFixed(2)),
              run_to_run_spread_ns: Number((s[s.length - 1] - s[0]).toFixed(2)),
            };
          });
          post({ n: nonce, id: m.id, ok: true, value: { times, reps_per_n: REPS, sink_ignore: sink === Infinity ? 1 : 0 } });
        } catch (err) {
          post({ n: nonce, id: m.id, ok: false, error: String((err && err.message) || err) });
        }
      }
    };
  }

  /* `post` is captured before hardening removes the global, and lives in a closure the
     candidate has no name for. The candidate is appended last: it can define median and
     it can even clobber self.onmessage — but it cannot emit a message we would accept. */
  function buildWorkerSource(candidateSrc, nonce) {
    return [
      "(() => {",
      "  const post = self.postMessage.bind(self);",
      HARDENING,
      `  (${SANDBOX_HARNESS.toString()})(post, ${JSON.stringify(nonce)});`,
      "})();",
      candidateSrc,
    ].join("\n");
  }

  function createSandbox(candidateSrc) {
    const nonce = `${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
    let url;
    let w;
    try {
      url = URL.createObjectURL(
        new Blob([buildWorkerSource(candidateSrc, nonce)], { type: "text/javascript" }),
      );
      w = new Worker(url);
    } catch (err) {
      if (url) URL.revokeObjectURL(url);
      return { fatal: `sandbox unavailable: ${(err && err.message) || err}` };
    }
    const pending = new Map();
    let dead = false;
    let fatal = null;
    let seq = 0;

    const kill = () => {
      if (dead) return;
      dead = true;
      w.terminate();
      URL.revokeObjectURL(url);
    };

    w.onmessage = (ev) => {
      const m = ev.data || {};
      if (m.n !== nonce) return; // ignore anything the candidate managed to emit
      const p = pending.get(m.id);
      if (!p) return;
      pending.delete(m.id);
      p(m);
    };
    w.onerror = (ev) => {
      if (ev.preventDefault) ev.preventDefault();
      fatal = `submitted code failed to load: ${ev.message || "syntax error"}`;
      for (const p of pending.values()) p({ fatal });
      pending.clear();
      kill();
    };

    function ask(cmd, payload, timeoutMs) {
      if (fatal) return Promise.resolve({ fatal });
      if (dead) return Promise.resolve({ fatal: "sandbox already terminated" });
      const id = ++seq;
      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          kill();
          resolve({ timeout: true, timeout_ms: timeoutMs, input: payload.input });
        }, timeoutMs);
        pending.set(id, (m) => {
          clearTimeout(timer);
          resolve(m);
        });
        w.postMessage({ n: nonce, id, cmd, ...payload });
      });
    }

    return {
      evalInput: (input, ms) => ask("eval", { input }, ms || PER_INPUT_MS),
      scaling: () => ask("scaling", {}, SCALING_MS),
      dispose: kill,
      get dead() {
        return dead;
      },
    };
  }

  /* One verdict per input, decided here. */
  async function probe(sb, input) {
    const r = await sb.evalInput(input);
    if (r.timeout) return { hang: true, input, timeout_ms: r.timeout_ms };
    if (r.fatal) return { fatal: r.fatal };
    const expected = referenceMedian(input);
    const actual = r.ok ? r.value : `throws ${r.error}`;
    return { input, expected, actual, ok: r.ok && Object.is(r.value, expected) };
  }

  async function shrink(sb, a) {
    let best = a;
    let improved = true;
    while (improved) {
      improved = false;
      if (best.length >= 3) {
        outer: for (let i = 0; i < best.length; i++) {
          for (let j = i + 1; j < best.length; j++) {
            const c = best.filter((_, k) => k !== i && k !== j);
            if (!inSpec(c)) continue;
            const p = await probe(sb, c);
            if (p.fatal || p.hang) break outer;
            if (!p.ok) {
              best = c;
              improved = true;
              break outer;
            }
          }
        }
      }
    }
    const ranked = toRanks(best);
    if (!inSpec(ranked)) return best;
    const p = await probe(sb, ranked);
    return !p.fatal && !p.hang && !p.ok ? ranked : best;
  }

  /* ---------- board ---------- */

  function setStatus(next) {
    if (state.locked && next !== "LOCKED") return;
    state.status = next;
    render();
  }

  function addEvidence(row) {
    const i = state.evidence.findIndex((e) => e.id === row.id);
    if (i >= 0) state.evidence[i] = row;
    else state.evidence.push(row);
    render();
  }

  const textResult = (obj) => ({ content: [{ type: "text", text: JSON.stringify(obj, null, 2) }] });

  /* No tool and no button picks a verdict. FAIL means a counterexample currently stands;
     otherwise UNKNOWN. LOCKED is the one exception, and only a human hand sets it. */
  const derivedStatus = () => (state.counter ? "FAIL" : "UNKNOWN");

  /* A candidate that does not halt is a failing candidate, not a tool error. */
  function reportHang(id, label, p) {
    state.counter = {
      input: p.input,
      expected: "(any value within the time limit)",
      actual: `no result after ${p.timeout_ms} ms — worker terminated`,
    };
    addEvidence({
      id,
      label,
      ok: false,
      detail: `did not return within ${p.timeout_ms} ms on ${JSON.stringify(p.input)}`,
    });
    setStatus("FAIL");
    return textResult({
      halted: false,
      timeout_ms: p.timeout_ms,
      hung_on: p.input,
      note: "The Worker was terminated. A candidate that does not halt is a failing candidate.",
      board_status: state.status,
    });
  }

  async function withSandbox(fn) {
    const sb = createSandbox(state.candidateSrc);
    if (sb.fatal) return textResult({ error: sb.fatal });
    try {
      return await fn(sb);
    } finally {
      sb.dispose();
    }
  }

  const tools = {
    async submit_code({ code } = {}) {
      if (state.locked) return textResult({ error: "board is human-locked" });
      if (typeof code !== "string" || !code.trim()) {
        return textResult({ error: "code must be a non-empty string defining function median(a)" });
      }
      if (code.length > MAX_CODE_CHARS) {
        return textResult({ error: `code exceeds ${MAX_CODE_CHARS} characters` });
      }
      const sb = createSandbox(code);
      if (sb.fatal) return textResult({ accepted: false, error: sb.fatal });
      const r = await sb.evalInput([1, 2, 3], SMOKE_MS);
      sb.dispose();
      if (r.fatal || r.timeout || !r.ok) {
        return textResult({
          accepted: false,
          error:
            r.fatal ||
            (r.timeout ? `candidate did not respond within ${r.timeout_ms} ms` : r.error),
          note: "Candidate rejected; the previous one is still on the board.",
        });
      }
      state.candidateSrc = code;
      state.claim = DEFAULT_CLAIM;
      state.status = "UNKNOWN";
      state.evidence = [];
      state.counter = null;
      state.lockProposal = null;
      render();
      return textResult({
        accepted: true,
        probe: { input: [1, 2, 3], expected: referenceMedian([1, 2, 3]), actual: r.value },
        note: "Loaded. Board reset to UNKNOWN — nothing is verified yet.",
        board_status: state.status,
      });
    },

    run_tests: () =>
      withSandbox(async (sb) => {
        const rows = [];
        for (const c of BASIC) {
          const p = await probe(sb, c.input);
          if (p.fatal) return textResult({ error: p.fatal });
          if (p.hang) return reportHang("basic", "basic tests", p);
          rows.push({ input: c.input, expected: c.expected, actual: p.actual, ok: Object.is(p.actual, c.expected) });
        }
        const fail = rows.find((r) => !r.ok) || null;
        const passed = !fail;
        addEvidence({
          id: "basic",
          label: `${rows.length} basic tests`,
          ok: passed,
          detail: passed ? "sorted / trivial inputs only" : "failed a basic case",
        });
        if (fail) {
          state.counter = { input: fail.input, expected: fail.expected, actual: fail.actual };
          setStatus("FAIL");
        }
        return textResult({
          tool: "run_tests",
          passed,
          rows,
          note: "Basic tests passing does not prove the claim. Status stays UNKNOWN unless a counterexample exists.",
          board_status: state.status,
        });
      }),

    find_counterexample: ({ seed } = {}) =>
      withSandbox(async (sb) => {
        const usedSeed = Number.isFinite(seed) ? Math.trunc(seed) : DEFAULT_SEED;
        const rand = mulberry32(usedSeed);
        let raw = null;
        let trials = 0;
        for (; trials < MAX_TRIALS; trials++) {
          const input = generateInput(rand, trials);
          if (!input) continue; // spec rules this draw out
          const p = await probe(sb, input);
          if (p.fatal) return textResult({ error: p.fatal });
          if (p.hang) return reportHang("adv", "adversarial search", p);
          if (!p.ok) {
            raw = input;
            break;
          }
        }
        if (!raw) {
          addEvidence({
            id: "adv",
            label: "adversarial search",
            ok: null,
            detail: `no disagreement in ${MAX_TRIALS} trials (seed ${usedSeed})`,
          });
          return textResult({
            tool: "find_counterexample",
            found: false,
            seed: usedSeed,
            trials_run: MAX_TRIALS,
            note: "Search exhausted without disagreement. That is not proof of correctness; status stays UNKNOWN.",
            board_status: state.status,
          });
        }
        const minimal = await shrink(sb, raw);
        const p = await probe(sb, minimal);
        state.counter = {
          input: minimal,
          expected: p.expected,
          actual: p.actual,
          raw,
          seed: usedSeed,
          trials: trials + 1,
        };
        addEvidence({
          id: "adv",
          label: "adversarial search",
          ok: false,
          detail: `disagreement at trial ${trials + 1} (seed ${usedSeed}), shrunk to ${JSON.stringify(minimal)}`,
        });
        setStatus("FAIL");
        return textResult({
          tool: "find_counterexample",
          found: true,
          seed: usedSeed,
          trials_run: trials + 1,
          raw_input: raw,
          minimal_input: minimal,
          expected: p.expected,
          actual: p.actual,
          note: "Inputs generated and shrunk on the page thread; the sandbox only reports what the candidate returned.",
          board_status: state.status,
        });
      }),

    compare_reference: () =>
      withSandbox(async (sb) => {
        const cases = [...BASIC.map((c) => c.input), ...BOUNDARIES].filter(inSpec);
        if (state.counter && Array.isArray(state.counter.input) && inSpec(state.counter.input)) {
          cases.push(state.counter.input);
        }
        if (!cases.length) {
          return textResult({
            tool: "compare_reference",
            passed: null,
            note: "Every built-in case is outside the current specification. Nothing to compare.",
            specification: state.spec.map((k) => CONSTRAINTS[k].label),
            board_status: state.status,
          });
        }
        const rows = [];
        for (const input of cases) {
          const p = await probe(sb, input);
          if (p.fatal) return textResult({ error: p.fatal });
          if (p.hang) return reportHang("ref", "reference comparison", p);
          rows.push(p);
        }
        const fail = rows.find((r) => !r.ok) || null;
        addEvidence({
          id: "ref",
          label: "reference comparison",
          ok: !fail,
          detail: fail ? "diverges from reference" : "matches reference on current case set",
        });
        if (fail) {
          state.counter = { input: fail.input, expected: fail.expected, actual: fail.actual };
          setStatus("FAIL");
        }
        return textResult({
          tool: "compare_reference",
          passed: !fail,
          fail,
          note: "The reference runs on the page thread, out of reach of submitted code.",
          board_status: state.status,
        });
      }),

    measure_scaling: () =>
      withSandbox(async (sb) => {
        const r = await sb.scaling();
        if (r.fatal) return textResult({ error: r.fatal });
        /* A benchmark that ran out of time says nothing about whether the candidate is
           correct or whether it halts — it halted on every input the search gave it. So
           this records a note and leaves the status exactly where it was. */
        if (r.timeout) {
          addEvidence({
            id: "scale",
            label: "scaling measurement",
            ok: null,
            detail: `aborted — did not complete within ${r.timeout_ms} ms`,
          });
          return textResult({
            tool: "measure_scaling",
            verdict: "ABORTED",
            timeout_ms: r.timeout_ms,
            note: "The benchmark did not finish in time. That is a fact about the measurement, not about the candidate, so the board status is unchanged.",
            board_status: state.status,
          });
        }
        if (!r.ok) return textResult({ error: r.error });
        const times = r.value.times;
        const noise = Math.max(...times.map((t) => t.run_to_run_spread_ns));
        const signal =
          Math.max(...times.map((t) => t.ns_per_call)) - Math.min(...times.map((t) => t.ns_per_call));
        const resolved = signal > 2 * noise;
        addEvidence({
          id: "scale",
          label: "scaling measurement",
          ok: null,
          /* The row already carries the UNKNOWN mark; repeating it here read as
             "UNKNOWN — UNKNOWN — ...". The INCONCLUSIVE verdict still goes to the agent
             in the tool result. */
          detail: resolved
            ? "timings differ across sizes, but timing is not proof of O(·)"
            : "below timing resolution; no complexity claim supported",
        });
        return textResult({
          tool: "measure_scaling",
          reps_per_n: r.value.reps_per_n,
          times,
          noise_floor_ns: Number(noise.toFixed(2)),
          across_size_signal_ns: Number(signal.toFixed(2)),
          verdict: resolved ? "UNKNOWN" : "INCONCLUSIVE",
          note: resolved
            ? "Timing is evidence about this machine, not a proof of asymptotic complexity."
            : `The spread across sizes (${signal.toFixed(2)}ns) does not exceed run-to-run noise (${noise.toFixed(2)}ns). No complexity statement is supported either way.`,
          board_status: state.status,
        });
      }),

    /* A new claim is a claim about something else, so the evidence gathered against the old
       one no longer stands. Clearing it is what returns the board to UNKNOWN — the status is
       never set directly, or this would be a back door for erasing a FAIL that still holds. */
    add_claim({ text } = {}) {
      if (state.locked) return textResult({ error: "board is human-locked" });
      if (!text) return textResult({ error: "text is required" });
      state.claim = String(text);
      state.counter = null;
      state.evidence = state.evidence.filter((e) => e.id.startsWith("dispute-"));
      state.lockProposal = null;
      setStatus(derivedStatus());
      return textResult({
        tool: "add_claim",
        claim: state.claim,
        note: "Evidence about the previous claim was cleared. The specification and any human disputes stand.",
        board_status: state.status,
      });
    },

    /* Agent-callable. Does NOT close the board — it asks a human to. */
    propose_lock({ note } = {}) {
      if (state.locked) return textResult({ error: "board is already human-locked" });
      state.lockProposal = { note: note ? String(note) : "(no rationale given)" };
      render();
      return textResult({
        tool: "propose_lock",
        proposed: true,
        note: state.lockProposal.note,
        board_status: state.status,
        awaiting: "A human must press Lock on the page. No tool can close this board.",
      });
    },

    list_board: () =>
      textResult({
        tool: "list_board",
        candidate: state.candidateSrc,
        claim: state.claim,
        specification: state.spec.map((k) => ({ id: k, requires: CONSTRAINTS[k].label })),
        disputes: state.disputes,
        status: state.status,
        locked: state.locked,
        lock_proposal: state.lockProposal,
        evidence: state.evidence,
        counterexample: state.counter,
      }),
  };

  /* Human-only. Never registered as a tool. The agent can find a counterexample; only a
     person can rule that it does not count, and doing so narrows what the search may draw. */
  function humanDispute(reasonKey, constraintKey) {
    if (state.locked || !state.counter) return;
    if (!REASONS[reasonKey] || !CONSTRAINTS[constraintKey]) return;
    state.disputes.push({
      input: state.counter.input,
      reason: REASONS[reasonKey],
      now_requires: CONSTRAINTS[constraintKey].label,
    });
    if (!state.spec.includes(constraintKey)) state.spec.push(constraintKey);
    addEvidence({
      id: `dispute-${state.disputes.length}`,
      label: "human dispute",
      ok: null,
      detail: `${REASONS[reasonKey]} — spec now requires: ${CONSTRAINTS[constraintKey].label}`,
    });
    state.counter = null;
    state.lockProposal = null;
    state.evidence = state.evidence.filter((e) => e.id !== "adv" && e.id !== "ref");
    state.status = derivedStatus();
    render();
  }

  /* Human-only. Never registered as a tool. */
  function humanLock() {
    state.locked = true;
    state.lockProposal = null;
    state.status = "LOCKED";
    render();
  }

  /* ---------- render ---------- */

  function render() {
    $("candidate-src").textContent = state.candidateSrc;
    $("claim-text").textContent = state.claim;

    const pill = $("status-pill");
    pill.textContent = state.status;
    pill.className = "pill " + String(state.status).toLowerCase();

    const list = $("evidence");
    list.textContent = "";
    const rows = state.evidence.length
      ? state.evidence
      : [{ label: "empty", detail: "run a verifier tool", empty: true }];
    for (const e of rows) {
      const li = document.createElement("li");
      const a = document.createElement("span");
      a.textContent = e.label;
      const b = document.createElement("span");
      if (e.empty) {
        b.textContent = e.detail;
      } else {
        b.className = e.ok === true ? "ok" : e.ok === false ? "bad" : "";
        b.textContent = `${e.ok === true ? "PASS" : e.ok === false ? "FAIL" : "UNKNOWN"} — ${e.detail}`;
      }
      li.append(a, b);
      list.append(li);
    }

    const counter = $("counter");
    if (state.counter) {
      counter.classList.remove("empty");
      const c = state.counter;
      const lines = [
        "COUNTEREXAMPLE",
        `input     ${JSON.stringify(c.input)}`,
        `expected  ${c.expected}`,
        `actual    ${c.actual}`,
      ];
      if (c.raw && JSON.stringify(c.raw) !== JSON.stringify(c.input)) {
        lines.push(`found as  ${JSON.stringify(c.raw)} (seed ${c.seed}, trial ${c.trials})`);
      }
      counter.textContent = lines.join("\n");
    } else {
      counter.classList.add("empty");
      counter.textContent = "No counterexample yet.";
    }

    const spec = $("spec-list");
    spec.textContent = "";
    if (!state.spec.length) {
      const li = document.createElement("li");
      li.textContent = "any nonempty numeric array, odd length";
      li.className = "muted";
      spec.append(li);
    } else {
      for (const k of state.spec) {
        const li = document.createElement("li");
        li.textContent = CONSTRAINTS[k].label;
        spec.append(li);
      }
    }

    $("dispute-panel").hidden = !state.counter || state.locked;

    const banner = $("lock-proposal");
    if (state.lockProposal && !state.locked) {
      banner.hidden = false;
      banner.textContent = `Agent proposed a lock — a human must confirm. Rationale: ${state.lockProposal.note}`;
    } else {
      banner.hidden = true;
      banner.textContent = "";
    }

    document.querySelectorAll("button[data-act]").forEach((b) => {
      const act = b.getAttribute("data-act");
      if (act === "reset") return;
      b.disabled = state.busy || (state.locked && act !== "reject" && act !== "lock");
    });
  }

  /* ---------- human input ---------- */

  async function withBusy(fn) {
    state.busy = true;
    render();
    try {
      return await fn();
    } finally {
      state.busy = false;
      render();
    }
  }

  document.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-act]");
    if (!btn || btn.disabled) return;
    const act = btn.getAttribute("data-act");

    if (act === "reset") {
      Object.assign(state, {
        candidateSrc: DEFAULT_CANDIDATE,
        claim: DEFAULT_CLAIM,
        spec: [],
        disputes: [],
        status: "UNKNOWN",
        locked: false,
        lockProposal: null,
        evidence: [],
        counter: null,
        busy: false,
      });
      $("code-input").value = "";
      render();
      return;
    }
    if (act === "reject") {
      state.locked = false;
      state.lockProposal = null;
      setStatus(derivedStatus());
      return;
    }
    if (act === "dispute") {
      humanDispute($("dispute-reason").value, $("dispute-constraint").value);
      return;
    }
    if (act === "lock") {
      humanLock();
      return;
    }
    if (act === "submit_code") {
      const code = $("code-input").value.trim();
      if (code) await withBusy(() => tools.submit_code({ code }));
      return;
    }
    if (typeof tools[act] === "function") await withBusy(() => tools[act]({}));
  });

  /* ---------- WebMCP ---------- */

  function mcpHost() {
    if (document.modelContext && typeof document.modelContext.registerTool === "function") {
      return document.modelContext;
    }
    if (navigator.modelContext && typeof navigator.modelContext.registerTool === "function") {
      return navigator.modelContext;
    }
    return null;
  }

  const SPECS = [
    {
      name: "submit_code",
      description:
        "Load a candidate implementation onto the board. It must define function median(a). The code runs only inside a terminable Worker with no network access, and is asked only what it returns for a given input. Resets the board to UNKNOWN.",
      schema: {
        type: "object",
        properties: { code: { type: "string", description: "JavaScript defining function median(a)" } },
        required: ["code"],
      },
    },
    {
      name: "run_tests",
      description:
        "Run the built-in basic test suite against the loaded candidate. Passing does not prove the claim.",
    },
    {
      name: "find_counterexample",
      description:
        "Search for an input where the candidate disagrees with the page's reference median, then shrink it to a minimal case. Seeded, so a run replays exactly.",
      schema: {
        type: "object",
        properties: { seed: { type: "integer", description: `PRNG seed. Defaults to ${DEFAULT_SEED}.` } },
      },
    },
    { name: "compare_reference", description: "Compare candidate outputs to the page's independent reference median." },
    {
      name: "measure_scaling",
      description:
        "Time the candidate on growing arrays. Reports its own noise floor and returns INCONCLUSIVE when it cannot resolve a trend.",
    },
    {
      name: "add_claim",
      description: "Replace the text of the current claim. Resets status to UNKNOWN unless locked.",
      schema: {
        type: "object",
        properties: { text: { type: "string", description: "Claim sentence" } },
        required: ["text"],
      },
    },
    {
      name: "propose_lock",
      description:
        "Ask the human to close the board. This does not lock anything — only a human hand on the page can.",
      schema: {
        type: "object",
        properties: { note: { type: "string", description: "Why the board should be closed" } },
      },
    },
    { name: "list_board", description: "Read candidate, claim, status, evidence, lock proposal, and counterexample." },
  ];

  async function registerWebMCP() {
    const host = mcpHost();
    const badge = $("mcp-badge");
    if (!host) {
      badge.textContent = "WebMCP: not in this browser — human controls still work";
      badge.className = "badge miss";
      return;
    }
    let ok = 0;
    for (const spec of SPECS) {
      try {
        await host.registerTool({
          name: spec.name,
          description: spec.description,
          inputSchema: spec.schema || { type: "object", properties: {} },
          annotations: { readOnlyHint: spec.name === "list_board" },
          execute: async (args) => tools[spec.name](args || {}),
        });
        ok++;
      } catch (err) {
        console.warn("registerTool failed", spec.name, err);
      }
    }
    const all = ok === SPECS.length;
    badge.textContent = all ? `WebMCP: ${ok} tools registered` : `WebMCP: ${ok}/${SPECS.length} registered — see console`;
    badge.className = "badge " + (all ? "ok" : "miss");
  }

  render();
  registerWebMCP();
})();
