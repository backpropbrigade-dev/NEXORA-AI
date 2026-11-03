import unittest

from services.local_actions import classify_local_action


class LocalActionIntentTests(unittest.TestCase):
    def test_open_youtube_has_allowlisted_command(self):
        self.assertEqual(classify_local_action("Open YouTube")["command"], "open youtube")

    def test_natural_variants_route_to_same_action(self):
        for phrase in ("Launch YouTube", "Go to YouTube", "Open YouTube for me"):
            with self.subTest(phrase=phrase):
                self.assertEqual(classify_local_action(phrase)["command"], "open youtube")

    def test_how_to_question_is_not_an_action(self):
        self.assertIsNone(classify_local_action("How do I open YouTube?"))

    def test_general_question_is_not_an_action(self):
        self.assertIsNone(classify_local_action("What is machine learning?"))

    def test_unsupported_shell_request_is_rejected(self):
        self.assertIsNone(classify_local_action("run powershell and delete files"))

    def test_mixed_request_retains_follow_up_question(self):
        action = classify_local_action("Open YouTube and tell me what YouTube is")
        self.assertEqual(action["command"], "open youtube")
        self.assertEqual(action["question"], "What is YouTube?")


if __name__ == "__main__":
    unittest.main()
