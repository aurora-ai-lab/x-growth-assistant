"""Smoke and behaviour tests. Run from the repo root:

    python3 -m unittest discover -s tests -v

Starts the real HTTP server on a free local port and calls it over HTTP.
"""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "web", "backend"))
os.environ["QUIET"] = "1"
for var in ("X_API_BEARER_TOKEN", "X_API_CLIENT_ID", "X_API_CLIENT_SECRET"):
    os.environ.pop(var, None)

import server  # noqa: E402
import xapi  # noqa: E402

REQUIRED_KEYS = {"status", "signals", "checked_at", "confidence"}
STATUSES = {"normal", "suspected", "limited", "unknown"}


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:{}".format(cls.httpd.server_address[1])
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def call(self, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, res.headers.get("Content-Type"), res.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers.get("Content-Type"), err.read()

    def json_call(self, path, body=None, raw=None):
        status, ctype, payload = self.call(path, body, raw)
        self.assertIn("application/json", ctype)
        return status, json.loads(payload)

    def assert_limit_shape(self, data):
        self.assertTrue(REQUIRED_KEYS <= set(data), data.keys())
        self.assertIn(data["status"], STATUSES)
        self.assertIsInstance(data["signals"], list)
        self.assertIsInstance(data["confidence"], float)
        self.assertTrue(0 <= data["confidence"] <= 1)
        self.assertRegex(data["checked_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        for sig in data["signals"]:
            self.assertTrue({"id", "label", "source", "observed", "weight", "detail"} <= set(sig))

    # --- required cases ---------------------------------------------------
    def test_normal_handle_without_evidence_is_unknown(self):
        status, data = self.json_call("/api/limit-check?handle=jack")
        self.assertEqual(status, 200)
        self.assert_limit_shape(data)
        self.assertEqual(data["status"], "unknown")
        self.assertLessEqual(data["confidence"], 0.1)
        self.assertEqual(data["x_api"]["state"], "not_configured")
        self.assertGreaterEqual(len(data["manual_checks"]), 5)

    def test_nonexistent_handle_is_unknown_not_error(self):
        status, data = self.json_call("/api/limit-check?handle=zz_nosuchuser99")
        self.assertEqual(status, 200)
        self.assert_limit_shape(data)
        self.assertEqual(data["status"], "unknown")
        ids = [s["id"] for s in data["signals"]]
        self.assertIn("handle_existence_unverified", ids)

    def test_missing_handle_is_400(self):
        status, data = self.json_call("/api/limit-check")
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "missing_handle")

    # --- validation -------------------------------------------------------
    def test_invalid_handle_is_400(self):
        for bad in ("this_handle_is_way_too_long", "bad-handle", "%40%40"):
            status, data = self.json_call("/api/limit-check?handle=" + bad)
            self.assertEqual(status, 400, bad)
            self.assertIn(data["error"]["code"], ("invalid_handle", "missing_handle"))

    def test_handle_normalisation(self):
        _, data = self.json_call("/api/limit-check", {"handle": "https://x.com/Jack_01/status/1"})
        self.assertEqual(data["handle"], "Jack_01")
        _, data = self.json_call("/api/limit-check", {"handle": "@jack"})
        self.assertEqual(data["handle"], "jack")

    def test_invalid_json_and_types(self):
        status, data = self.json_call("/api/limit-check", raw=b"{not json")
        self.assertEqual((status, data["error"]["code"]), (400, "invalid_json"))
        status, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {"followers": -3}})
        self.assertEqual((status, data["error"]["code"]), (400, "invalid_evidence"))
        status, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {"button_errors": "yes"}})
        self.assertEqual(status, 400)

    # --- evidence logic ---------------------------------------------------
    def test_official_notice_gives_limited_with_capped_confidence(self):
        _, data = self.json_call("/api/limit-check", {
            "handle": "jack", "evidence": {"action_blocked_notice": True}})
        self.assert_limit_shape(data)
        self.assertEqual(data["status"], "limited")
        self.assertLessEqual(data["confidence"], 0.6)
        self.assertEqual(data["recheck_interval_hours"], 48)

    def test_description_text_is_parsed(self):
        _, data = self.json_call("/api/limit-check", {
            "handle": "jack",
            "description": "Banner says: Some of your account features are temporarily limited."})
        self.assertEqual(data["status"], "limited")
        sig = [s for s in data["signals"] if s["id"] == "action_blocked_notice"][0]
        self.assertEqual(sig["source"], "user_text")
        self.assertEqual(data["evidence_source"], "user_text")
        _, data = self.json_call("/api/limit-check", {
            "handle": "jack", "description": "the follow button also reverts"})
        self.assertIn("button_errors", [s["id"] for s in data["signals"]])

    def test_text_conflicting_with_form_warns(self):
        _, data = self.json_call("/api/limit-check", {
            "handle": "jack", "evidence": {"action_blocked_notice": False},
            "description": "X showed: Some of your account features are temporarily limited"})
        self.assertEqual(data["status"], "unknown")
        self.assertTrue(any("action_blocked_notice" in w for w in data["warnings"]))

    def test_moderate_signals_give_suspected(self):
        _, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {
            "followers_only_visibility": True, "search_visible_logged_out": False}})
        self.assertEqual(data["status"], "suspected")
        self.assertEqual(data["confidence"], 0.5)

    def test_all_clear_gives_normal(self):
        _, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {
            "followers_only_visibility": False, "search_visible_logged_out": True,
            "action_blocked_notice": False, "replies_hidden_behind_show_more": False}})
        self.assertEqual(data["status"], "normal")
        self.assertLessEqual(data["confidence"], 0.6)

    def test_partial_negative_checks_stay_unknown(self):
        _, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {
            "action_blocked_notice": False}})
        self.assertEqual(data["status"], "unknown")

    def test_no_posts_is_not_a_limit(self):
        _, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {
            "impressions_last_7d": 0, "posts_last_7d": 0}})
        self.assertEqual(data["status"], "unknown")
        self.assertIn("no_recent_posts", [s["id"] for s in data["signals"]])

    def test_impression_drop_vs_baseline(self):
        _, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {
            "impressions_last_7d": 20, "avg_weekly_impressions_prev_4w": 5000, "posts_last_7d": 10}})
        self.assertEqual(data["status"], "suspected")

    def test_unknown_field_warns(self):
        _, data = self.json_call("/api/limit-check", {"handle": "jack", "evidence": {"foo": 1}})
        self.assertTrue(data["warnings"])

    def test_key_present_still_unknown(self):
        os.environ["X_API_BEARER_TOKEN"] = "dummy-for-test"
        try:
            _, data = self.json_call("/api/limit-check?handle=jack")
            self.assertEqual(data["status"], "unknown")
            self.assertEqual(data["x_api"]["state"], "not_implemented")
        finally:
            os.environ.pop("X_API_BEARER_TOKEN")

    def test_xapi_stub_has_no_network_code(self):
        with open(xapi.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for mod in ("import urllib", "import http", "import socket", "import requests"):
            self.assertNotIn(mod, src)

    # --- other endpoints --------------------------------------------------
    def test_health_and_schema(self):
        status, data = self.json_call("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        _, schema = self.json_call("/api/limit-check/schema")
        self.assertEqual(set(schema["statuses"]), STATUSES)

    def test_post_review(self):
        _, ok = self.json_call("/api/post-review", {"text": "Shipped a small CLI that formats CSVs. Feedback welcome."})
        self.assertEqual(ok["verdict"], "allowed")
        _, bad = self.json_call("/api/post-review", {"text": "Guaranteed returns! Send 1 ETH and get 2 back"})
        self.assertEqual((bad["verdict"], bad["risk"]), ("do_not_post", "high"))
        _, grey = self.json_call("/api/post-review", {"text": "Huge GIVEAWAY: RT to win a keyboard"})
        self.assertEqual(grey["verdict"], "revise")
        _, ad = self.json_call("/api/post-review", {"text": "Use code SAVE10 for 10% off our planner"})
        self.assertEqual(ad["verdict"], "allowed")
        self.assertFalse(ad["stats"]["paid_partnership_disclosed"])
        status, err = self.json_call("/api/post-review", {"text": ""})
        self.assertEqual(status, 400)

    def test_disclosure_and_superlatives(self):
        _, data = self.json_call("/api/post-review", {"text": "Use code X for 20% off. #ad-free app"})
        self.assertFalse(data["stats"]["paid_partnership_disclosed"])
        _, data = self.json_call("/api/post-review", {"text": "Use code X for 20% off. #ad"})
        self.assertTrue(data["stats"]["paid_partnership_disclosed"])
        _, data = self.json_call("/api/post-review", {"text": "The best tool on the market, 10x your output"})
        self.assertEqual(data["verdict"], "revise")
        self.assertIn("superlative", [m["category"] for m in data["matched"]])

    def test_dates_are_not_phone_numbers(self):
        _, data = self.json_call("/api/post-review", {"text": "Launch on 2026-10-24, 10:00 to 12:00."})
        self.assertEqual(data["verdict"], "allowed")
        _, data = self.json_call("/api/post-review", {"text": "Call her: 415-555-0134"})
        self.assertEqual(data["verdict"], "do_not_post")

    def test_chat(self):
        _, data = self.json_call("/api/chat", {"message": "where can I buy followers cheap"})
        self.assertEqual(data["intent"], "refused")
        _, data = self.json_call("/api/chat", {"message": "my password: hunter2"})
        self.assertEqual(data["intent"], "password_warning")
        _, data = self.json_call("/api/chat", {"message": "review: New thread on pricing lessons"})
        self.assertEqual(data["intent"], "post_review")
        _, data = self.json_call("/api/chat", {"message": "am I shadowbanned? @jack"})
        self.assertEqual(data["intent"], "limit_check")
        self.assertEqual(data["data"]["status"], "unknown")
        _, data = self.json_call("/api/chat", {"message": "how do I grow my traffic"})
        self.assertEqual(data["intent"], "growth")

    def test_static_and_traversal(self):
        status, ctype, body = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"X Growth Assistant", body)
        status, _, _ = self.call("/../../web/backend/server.py")
        self.assertEqual(status, 404)
        status, _, _ = self.call("/%2e%2e/%2e%2e/LICENSE")
        self.assertEqual(status, 404)
        status, data = self.json_call("/api/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()

