# Contributing to Lockboard

Thanks for helping improve reproducible verification of AI-generated code.

## Scope

Lockboard is a small, browser-based experiment; its current reference problem is \`median(a)\`. The board is not a general-purpose hostile-code sandbox or a correctness prover. Keep these limits explicit.

## Local setup

1. Fork and clone the repository.
2. Install Python 3.12+ and Node.js (for the syntax check).
3. From the repository root, run:

   \`\`\`bash
   python -m pip install -r requirements-test.txt
   python -m playwright install chromium
   python -m unittest discover -s tests -v
   node --check app.js
   \`\`\`

4. To use the browser UI manually, start a localhost server (for example \`python -m http.server 8099\`) and open \`http://localhost:8099\`. Opening \`file://\` is not supported for WebMCP.

Linux CI uses \`python -m playwright install --with-deps chromium\` to install OS-level browser dependencies. Browser integration tests run against a temporary localhost server; they do not call external model APIs.

## Before opening a pull request

- Explain the behavior being changed and why.
- Add or update a reproducible regression test for behavior changes.
- Run the full browser regression suite and \`node --check app.js\`.
- Preserve the verification boundary: the candidate may execute only inside a bounded Worker; reference, input generation, and verdicts remain outside candidate reach.
- Never allow an agent tool to set a passing verdict or human lock.
- Document known limitations and avoid claiming that an exhausted search proves correctness.
- Don't commit secrets, private model access, or unpublished research data.

Open a GitHub issue for larger design changes before implementing them. External contributions and feedback are welcome.

## Reporting security issues

Please follow [SECURITY.md](SECURITY.md) and avoid posting exploit details in public issues.
