"""Browser-level regression tests for Lockboard.

Run with:
    python -m unittest discover -s tests -v

Requires Playwright and its Chromium browser (see CONTRIBUTING.md).
Tests use an ephemeral localhost HTTP server; no external services are called.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


class LockboardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = partial(QuietHandler, directory=str(ROOT))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)

    def tearDown(self):
        self.context.close()

    def open_board(self):
        self.page.goto(self.url, wait_until="load")
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")

    def click_tool(self, name):
        self.page.locator(f'button[data-act="{name}"]').click()

    def load_candidate(self, code):
        self.page.locator("#code-input").fill(code)
        self.click_tool("submit_code")
        expect(self.page.locator("#candidate-src")).to_have_text(code)
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")

    def test_basic_tests_never_assert_proof(self):
        self.open_board()
        self.click_tool("run_tests")
        expect(self.page.locator("#evidence")).to_contain_text("sorted / trivial inputs only")
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")

    def test_seeded_search_finds_and_shrinks_counterexample(self):
        self.open_board()
        self.click_tool("find_counterexample")
        expect(self.page.locator("#status-pill")).to_have_text("FAIL")
        expect(self.page.locator("#counter")).to_contain_text("COUNTEREXAMPLE")
        expect(self.page.locator("#counter")).to_contain_text("[1,0,2]")

    def test_human_dispute_narrows_scope_without_claiming_pass(self):
        self.open_board()
        self.click_tool("find_counterexample")
        expect(self.page.locator("#status-pill")).to_have_text("FAIL")
        self.page.locator("#dispute-reason").select_option("outside_specification")
        self.page.locator("#dispute-constraint").select_option("sorted")
        self.click_tool("dispute")
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")
        expect(self.page.locator("#spec-list")).to_contain_text("already sorted")
        self.click_tool("find_counterexample")
        expect(self.page.locator("#evidence")).to_contain_text("no disagreement in 500 trials")
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")

    def test_correct_candidate_does_not_become_pass(self):
        self.open_board()
        self.load_candidate(
            "function median(a) { const s = [...a].sort((x,y)=>x-y); "
            "return s[Math.floor(s.length/2)]; }"
        )
        self.click_tool("find_counterexample")
        expect(self.page.locator("#evidence")).to_contain_text("no disagreement in 500 trials")
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")

    def test_candidate_cannot_corrupt_reference_sort(self):
        self.open_board()
        self.load_candidate(
            "Array.prototype.sort = function(){ return this; }; "
            "function median(a) { return a[Math.floor(a.length/2)]; }"
        )
        self.click_tool("find_counterexample")
        expect(self.page.locator("#status-pill")).to_have_text("FAIL")
        expect(self.page.locator("#counter")).to_contain_text("COUNTEREXAMPLE")

    def test_nonterminating_candidate_is_terminated_and_fails(self):
        self.open_board()
        self.load_candidate(
            "function median(a) { "
            "if (a.length === 3 && a[0] === -1) { while(true){} } "
            "return a[Math.floor(a.length/2)]; }"
        )
        self.click_tool("compare_reference")
        expect(self.page.locator("#status-pill")).to_have_text("FAIL")
        expect(self.page.locator("#counter")).to_contain_text("worker terminated")

    def test_agent_can_propose_but_only_human_can_lock(self):
        self.context.add_init_script("""() => {
            window.__registeredTools = new Map();
            document.modelContext = {
                registerTool: async (spec) => {
                    window.__registeredTools.set(spec.name, spec);
                }
            };
        }""")
        self.open_board()
        expect(self.page.locator("#mcp-badge")).to_have_text("WebMCP: 8 tools registered")
        result = self.page.evaluate("""async () => {
            const tool = window.__registeredTools.get('propose_lock');
            return JSON.parse((await tool.execute({note: 'please review'})).content[0].text);
        }""")
        self.assertTrue(result["proposed"])
        self.assertEqual(result["board_status"], "UNKNOWN")
        expect(self.page.locator("#status-pill")).to_have_text("UNKNOWN")
        self.assertNotIn("lock", list(self.page.evaluate(
            "() => Array.from(window.__registeredTools.keys())"
        )))
        self.click_tool("lock")
        expect(self.page.locator("#status-pill")).to_have_text("LOCKED")
        result = self.page.evaluate("""async () => {
            const tool = window.__registeredTools.get('submit_code');
            return JSON.parse((await tool.execute({code: 'function median(a){return 0}'})).content[0].text);
        }""")
        self.assertIn("human-locked", result["error"])
        expect(self.page.locator("#status-pill")).to_have_text("LOCKED")


if __name__ == "__main__":
    unittest.main()
