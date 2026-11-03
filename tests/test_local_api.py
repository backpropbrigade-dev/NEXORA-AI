import tempfile
import unittest
import os
import threading
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_groq_key = os.environ.get("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = ""  # Keep module import from making a live Groq model-list call.
from api import server as local_api
if _groq_key is None:
    os.environ.pop("GROQ_API_KEY", None)
else:
    os.environ["GROQ_API_KEY"] = _groq_key
from services.conversation_store import ConversationStore


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ConversationStore(Path(self.temp_dir.name) / "test.sqlite3")
        self.store_patch = patch.object(local_api, "store", self.store)
        self.store_patch.start()
        local_api.state.update({"status": "idle", "voice_running": False, "voice_processing": False, "voice_conversation_id": None, "microphone": "not_checked"})
        local_api.voice_session_id = None
        local_api.voice_stopper = None
        local_api.voice_microphone = None
        local_api.voice_capture_active = False
        self.client = TestClient(local_api.app)

    def tearDown(self):
        self.client.close()
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_local_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_worker_events_are_delivered_to_websocket_loop(self):
        with self.client.websocket_connect("/api/events") as websocket:
            local_api.emit("diagnostic", message="Local voice events are connected.")
            event = websocket.receive_json()

        self.assertEqual(event["type"], "diagnostic")
        self.assertEqual(event["message"], "Local voice events are connected.")

    def test_open_youtube_calls_allowlisted_executor(self):
        calls = []

        def fake_open(url, message):
            calls.append(url)
            local_api.main.respond(message)
            return True

        with patch.object(local_api.main, "open_url", side_effect=fake_open), patch.object(local_api.main, "speak", return_value=True):
            response = self.client.post("/api/actions/execute", json={"command": "Open YouTube"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(calls, ["https://www.youtube.com"])
        self.assertEqual(response.json()["message"], "Opening YouTube now.")

    def test_open_url_prefers_windows_default_browser_for_websites(self):
        responses = []
        with (
            patch.object(local_api.main.os, "startfile") as startfile,
            patch.object(local_api.main, "respond", side_effect=responses.append),
            patch.object(local_api.main.browser_controller, "navigate") as navigate,
        ):
            opened = local_api.main.open_url(
                "https://www.youtube.com", "Opening YouTube now."
            )

        if os.name == "nt":
            self.assertTrue(opened)
            startfile.assert_called_once_with("https://www.youtube.com")
            navigate.assert_not_called()
            self.assertEqual(responses, ["Opening YouTube now."])
        else:
            startfile.assert_not_called()

    def test_unsupported_command_never_reaches_executor(self):
        with patch.object(local_api, "run_command") as execute:
            response = self.client.post("/api/actions/execute", json={"command": "run arbitrary shell code"})
        self.assertEqual(response.status_code, 422)
        execute.assert_not_called()

    def test_how_to_open_youtube_is_answered_instead_of_executed(self):
        with patch.object(local_api.main, "open_url") as open_url, patch.object(local_api.main, "ask_ai", return_value="Use a web browser to visit YouTube.") as ask_ai, patch.object(local_api.main, "respond"):
            local_api.main.execute_command("How do I open YouTube?")
        open_url.assert_not_called()
        ask_ai.assert_called_once_with("How do I open YouTube?")

    def test_voice_start_stop_use_local_microphone_service(self):
        calls = []

        class FakeMicrophone:
            def __init__(self, ready_event, closed_event, device_index=None):
                self.stream_available = True
                self.closed_event = closed_event
                self.error = None
                ready_event.set()

        def start_listener(*args, **kwargs):
            calls.append("start")
            def stop(**options):
                calls.append("stop")
                local_api.voice_capture_active = False
                args[0].closed_event.set()
            return stop

        with patch.object(local_api, "TrackedMicrophone", FakeMicrophone), patch.object(local_api.main.recognizer, "listen_in_background", side_effect=start_listener):
            started = self.client.post("/api/voice/start", json={})
            stopped = self.client.post("/api/voice/stop")

        self.assertEqual(started.status_code, 200)
        self.assertTrue(started.json()["ok"])
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(calls, ["start", "stop"])

    def test_microphone_device_index_is_configurable(self):
        captured = []

        class FakeMicrophone:
            def __init__(self, ready_event, closed_event, device_index=None):
                captured.append(device_index)
                self.stream_available = True
                self.closed_event = closed_event
                self.error = None
                ready_event.set()

        def start_listener(*args, **kwargs):
            def stop(**options):
                args[0].closed_event.set()
                local_api.voice_capture_active = False
            return stop

        with (
            patch.dict(os.environ, {"MICROPHONE_DEVICE_INDEX": "2"}),
            patch.object(local_api, "TrackedMicrophone", FakeMicrophone),
            patch.object(local_api.main.recognizer, "listen_in_background", side_effect=start_listener),
        ):
            response = self.client.post("/api/voice/start", json={})
            self.client.post("/api/voice/stop")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured, [2])

    def test_invalid_microphone_device_index_returns_actionable_error(self):
        with patch.dict(os.environ, {"MICROPHONE_DEVICE_INDEX": "not-a-number"}):
            response = self.client.post("/api/voice/start", json={})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertIn("microphone", response.json()["message"].lower())
        self.assertFalse(local_api.state["voice_running"])

    def test_microphone_open_failure_returns_actionable_diagnostic(self):
        with patch.object(local_api.main.recognizer, "listen_in_background", side_effect=OSError("No Default Input Device Available")):
            response = self.client.post("/api/voice/start", json={})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(response.json()["microphone"], "device_unavailable")
        self.assertIn("recording device", response.json()["message"])
        self.assertFalse(local_api.state["voice_running"])
        self.assertFalse(local_api.voice_capture_active)

    def test_recognized_transcript_is_emitted_for_cloud_chat_handler(self):
        events = []
        completed = threading.Event()
        local_api.state.update({"status": "processing", "voice_running": True, "voice_processing": False, "voice_conversation_id": "local-id"})
        local_api.voice_session_id = "session-id"
        def record_event(name, **data):
            events.append((name, data))
            if name == "listening_finished":
                completed.set()
        with patch.object(local_api.main, "transcribe_audio", return_value="What is machine learning?"), patch.object(local_api, "emit", side_effect=record_event), patch.object(local_api, "run_command") as local_chat:
            local_api.voice_callback("session-id", local_api.main.recognizer, object())
            self.assertTrue(completed.wait(timeout=2))
        local_chat.assert_not_called()
        transcript = next(data for name, data in events if name == "transcript_received")
        self.assertEqual(transcript["transcript"], "What is machine learning?")
        local_api.state.update({"status": "idle", "voice_running": False, "voice_conversation_id": None})
        local_api.voice_session_id = None


if __name__ == "__main__":
    unittest.main()
