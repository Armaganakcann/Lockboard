# Lockboard development roadmap

This is a plan, not a claim that proposed features are implemented or funded.

## Near term

- [x] Establish human-only locking and agent-readable verification evidence (existing demo).
- [ ] Keep a browser-level regression suite green across supported Chromium environments.
- [ ] Add adversarial tests for forged Worker messages, CSP restrictions, and malformed code; document gaps.
- [ ] Improve contributor onboarding and reproducible local demos.
- [ ] Collect independent maintainer and external-user feedback.

## Research directions

- [ ] Generalize the currently hard-coded \`median(a)\` reference to explicitly specified additional problems.
- [ ] Evaluate whether shrinking preserves constraints and genuinely minimizes counterexamples under each added problem.
- [ ] Measure test-search cost and sensitivity across seeds and defect classes.
- [ ] Investigate browser compatibility, accessibility, and failure modes without overstating security guarantees.

## Non-goals

The system does not provide formal proof of program correctness or a secure execution environment for intentionally malicious code. Automated verification must not substitute for human specification decisions.
