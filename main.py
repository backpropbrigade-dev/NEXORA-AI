import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pyttsx3
import speech_recognition as sr
from dotenv import load_dotenv
from groq import Groq
from services.local_actions import classify_local_action


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

load_dotenv(APP_DIR / ".env")

groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = (
    Groq(api_key=groq_api_key, timeout=20, max_retries=0)
    if groq_api_key
    else None
)

PREFERRED_MODELS = (
    "openai/gpt-oss-20b",
    "groq/compound-mini",
    "groq/compound",
    "llama-3.1-8b-instant",
)


def select_available_model(excluded_models=None, fallback=None):
    """Choose the first preferred model available to this API key."""
    excluded_models = excluded_models or set()
    if groq_client is not None:
        try:
            available_models = {
                model.id for model in groq_client.models.list().data
            }
            for model_id in PREFERRED_MODELS:
                if model_id in available_models and model_id not in excluded_models:
                    return model_id
        except Exception:
            pass
    return fallback


selected_model = select_available_model(fallback="openai/gpt-oss-20b")
if groq_client is not None:
    print(f"Groq model ready: {selected_model}")

SYSTEM_MESSAGE = "You are NEXORA AI, a helpful personal voice assistant."
SYSTEM_MESSAGE += (
    " Answer the user's question directly and accurately. Use clear conversational "
    "English. Since your response will be spoken aloud, avoid Markdown tables, "
    "excessive formatting, emojis, and unnecessarily long answers. Give concise "
    "answers by default, usually two to five sentences. Give step-by-step "
    "explanations when the user requests them. Never claim that you were personally "
    "trained by the user. If information is uncertain or requires live data that "
    "you do not have, say so honestly instead of fabricating it."
)
SYSTEM_MESSAGE += (
    " You are NEXORA AI, a voice-enabled personal assistant. Your responses are "
    "converted to audible speech using text-to-speech. Never claim that you are "
    "unable to speak or that you are only text-based. Respond naturally as a voice "
    "assistant. Keep ordinary answers concise and conversational unless the user "
    "requests a detailed explanation."
)
conversation_history = [{"role": "system", "content": SYSTEM_MESSAGE}]


# Shared speech-recognition settings.
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.pause_threshold = 1.8
recognizer.non_speaking_duration = 0.8
recognizer.phrase_threshold = 0.2

speech_rate = 165
speech_volume = 1.0
speech_lock = threading.Lock()


def clean_for_speech(text):
    """Remove formatting that sounds unnatural when read aloud."""
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub("[*_" + chr(96) + "]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def speak(text):
    """Speak text with a fresh engine so repeated responses remain audible."""
    cleaned_text = clean_for_speech(text)
    if not cleaned_text:
        return False

    with speech_lock:
        engine = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", speech_rate)
            engine.setProperty("volume", speech_volume)

            try:
                voices = engine.getProperty("voices")
                english_voice = next(
                    (
                        voice
                        for voice in voices
                        if "english" in (
                            f"{voice.name} {voice.id} "
                            f"{getattr(voice, 'languages', '')}"
                        ).lower()
                        or "en-" in str(getattr(voice, "languages", "")).lower()
                        or "en_" in str(getattr(voice, "languages", "")).lower()
                    ),
                    None,
                )
                if english_voice:
                    engine.setProperty("voice", english_voice.id)
            except Exception:
                pass

            engine.say(cleaned_text)
            engine.runAndWait()
            engine.stop()
            return True
        except Exception as error:
            print(f"Speech error ({type(error).__name__}): {error}")
            return False
        finally:
            if engine is not None:
                del engine


def respond(text):
    """Print one complete response and speak its cleaned form once."""
    print(f"NEXORA AI: {text}")
    speak(text)


def trim_conversation_history():
    """Keep the system prompt and approximately ten recent exchanges."""
    global conversation_history
    recent_messages = conversation_history[1:][-20:]
    conversation_history = [conversation_history[0]] + recent_messages


def is_model_not_found_error(error):
    """Return whether a Groq exception reports an unavailable model."""
    error_text = str(error).lower()
    error_code = str(getattr(error, "code", "")).lower()
    return (
        getattr(error, "status_code", None) == 404
        and (
            "model_not_found" in error_text
            or error_code == "model_not_found"
        )
    )


def ask_ai(question):
    """Send a conversational question to Groq and retain recent context."""
    global selected_model

    if groq_client is None:
        return "My AI service is not configured yet."

    conversation_history.append({"role": "user", "content": question})
    trim_conversation_history()

    for attempt in range(2):
        try:
            completion = groq_client.chat.completions.create(
                model=selected_model,
                messages=conversation_history,
                temperature=0.4,
                max_tokens=500,
            )
            answer = (completion.choices[0].message.content or "").strip()
            if answer:
                conversation_history.append(
                    {"role": "assistant", "content": answer}
                )
                trim_conversation_history()
                return answer
            break
        except Exception as error:
            if attempt == 0 and is_model_not_found_error(error):
                replacement_model = select_available_model(
                    excluded_models={selected_model}
                )
                if replacement_model:
                    selected_model = replacement_model
                    print(f"Groq model ready: {selected_model}")
                    continue

            error_message = str(error)
            if groq_api_key:
                error_message = error_message.replace(groq_api_key, "<redacted>")
            print(f"Groq error ({type(error).__name__}): {error_message}")
            break

    return (
        "I could not reach my AI service right now. Please check the internet "
        "connection and API configuration."
    )


def prepare_microphone():
    """Calibrate ambient noise once when NEXORA AI starts."""
    print("Preparing microphone...")
    device_index = os.getenv("MICROPHONE_DEVICE_INDEX", "").strip()
    microphone = sr.Microphone(
        device_index=int(device_index) if device_index else None
    )
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
    print("Microphone ready.")


def transcribe_audio(audio):
    """Transcribe microphone audio with Groq Whisper, then Google once."""
    temporary_path = None
    try:
        if groq_client is None:
            raise RuntimeError("Groq is not configured")

        wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
            wav_file.write(wav_bytes)
            temporary_path = Path(wav_file.name)

        with temporary_path.open("rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                language="en",
                temperature=0.0,
                response_format="json",
                prompt=(
                    "JARVIS, Google, YouTube, GitHub, Gmail, Python, machine "
                    "learning, Windows commands"
                ),
            )

        text = (transcription.text or "").strip()
        if text:
            return text
        raise ValueError("Groq Whisper returned empty text")
    except Exception as error:
        error_message = str(error)
        if groq_api_key:
            error_message = error_message.replace(groq_api_key, "<redacted>")
        print(f"Groq transcription error ({type(error).__name__}): {error_message}")
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as error:
                print(f"Audio cleanup error ({type(error).__name__}): {error}")

    try:
        return recognizer.recognize_google(audio, language="en-IN").strip()
    except Exception as error:
        print(f"Transcription failed ({type(error).__name__}): {error}")
        return ""


def listen():
    """Listen once and return recognized speech."""
    try:
        with sr.Microphone() as source:
            print("Listening...")
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)

        text = transcribe_audio(audio)
        if text:
            print(f"YOU: {text}")
        return text
    except sr.WaitTimeoutError:
        return ""
    except Exception as error:
        print(f"Microphone error ({type(error).__name__}): {error}")
        return ""


LOCAL_APPLICATIONS = {
    "open notepad": "notepad.exe",
    "open calculator": "calc.exe",
    "open paint": "mspaint.exe",
    "open command prompt": "cmd.exe",
    "open file explorer": "explorer.exe",
}

WEBSITES = {
    "open google": ("https://www.google.com", "Opening Google now."),
    "open youtube": ("https://www.youtube.com", "Opening YouTube now."),
    "open gmail": ("https://mail.google.com", "Opening Gmail now."),
    "open github": ("https://github.com", "Opening GitHub now."),
    "open chatgpt": ("https://chatgpt.com", "Opening ChatGPT now."),
    "open wikipedia": ("https://www.wikipedia.org", "Opening Wikipedia now."),
    "open stack overflow": (
        "https://stackoverflow.com",
        "Opening Stack Overflow now.",
    ),
    "open geeksforgeeks": (
        "https://www.geeksforgeeks.org",
        "Opening GeeksforGeeks now.",
    ),
    "open python documentation": (
        "https://docs.python.org/3/",
        "Opening the Python documentation.",
    ),
}

GREETINGS = {
    "hello",
    "hello jarvis",
    "hi",
    "hi jarvis",
    "hey jarvis",
    "good morning",
    "good afternoon",
    "good evening",
}

MICROPHONE_CHECKS = {
    "can you hear me",
    "are you able to hear me",
}

WELLBEING_QUESTIONS = {
    "how are you",
    "how are you doing",
    "are you fine",
    "how do you feel",
}


class BrowserController:
    """Control a JARVIS-managed browser when Playwright is available."""

    def __init__(self):
        self._playwright = None
        self._context = None
        self._page = None

    def _ensure_page(self):
        if self._page and not self._page.is_closed():
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Playwright is not installed; direct browser controls are unavailable"
            ) from error

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        launch_errors = []
        for launch_options in (
            {"channel": "chrome"},
            {"channel": "msedge"},
            {},
        ):
            try:
                self._context = (
                    self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(APP_DIR / ".browser-profile"),
                        headless=False,
                        **launch_options,
                    )
                )
                break
            except Exception as error:
                launch_errors.append(f"{type(error).__name__}: {error}")

        if self._context is None:
            raise RuntimeError(
                "No Playwright browser could be launched: "
                + " | ".join(launch_errors)
            )

        self._page = (
            self._context.pages[0]
            if self._context.pages
            else self._context.new_page()
        )
        return self._page

    def navigate(self, url):
        page = self._ensure_page()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return True

    def new_tab(self):
        self._page = self._ensure_page().context.new_page()
        return True

    def go_back(self):
        self._ensure_page().go_back(wait_until="domcontentloaded", timeout=15000)
        return True

    def go_forward(self):
        self._ensure_page().go_forward(
            wait_until="domcontentloaded", timeout=15000
        )
        return True

    def refresh(self):
        self._ensure_page().reload(wait_until="domcontentloaded", timeout=15000)
        return True

    def close_tab(self):
        page = self._ensure_page()
        page.close()
        self._page = None
        return True

    def scroll(self, direction):
        page = self._ensure_page()
        if direction == "top":
            page.evaluate("window.scrollTo(0, 0)")
        elif direction == "bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            distance = "window.innerHeight" if direction == "down" else "-window.innerHeight"
            page.evaluate(f"window.scrollBy(0, {distance})")
        return True

    def close_browser(self):
        if self._context is not None:
            self._context.close()
            self._context = None
            self._page = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        return True


browser_controller = BrowserController()


def open_url(url, success_message):
    """Open a validated URL with the user's browser and safe fallbacks."""
    parsed_url = urlparse(url) if isinstance(url, str) else None
    if (
        parsed_url is None
        or parsed_url.scheme not in {"https", "http"}
        or not parsed_url.netloc
    ):
        print("Browser error (ValueError): URL must use http:// or https://")
        respond(
            "I could not open the browser. Please check your default browser "
            "settings."
        )
        return False

    if os.name == "nt":
        try:
            os.startfile(url)
            respond(success_message)
            return True
        except OSError as error:
            print(f"Default browser error ({type(error).__name__}): {error}")

    try:
        browser_controller.navigate(url)
        respond(success_message)
        return True
    except Exception as error:
        print(f"Managed browser error ({type(error).__name__}): {error}")

    try:
        if webbrowser.open_new_tab(url):
            respond(success_message)
            return True
        fallback_error = "open_new_tab returned False"
    except Exception as error:
        fallback_error = f"{type(error).__name__}: {error}"

    print(f"Browser fallback error: {fallback_error}")
    respond(
        "I could not open the browser. Please check your default browser settings."
    )
    return False


def open_chrome():
    """Launch an installed Chrome executable without accepting arbitrary commands."""
    candidates = [
        shutil.which("chrome.exe"),
        os.environ.get("ProgramFiles", "") + r"\Google\Chrome\Application\chrome.exe",
        os.environ.get("ProgramFiles(x86)", "")
        + r"\Google\Chrome\Application\chrome.exe",
        os.environ.get("LOCALAPPDATA", "")
        + r"\Google\Chrome\Application\chrome.exe",
    ]
    chrome_path = next(
        (candidate for candidate in candidates if candidate and Path(candidate).is_file()),
        None,
    )
    if not chrome_path:
        print("Browser error: Chrome executable was not found.")
        respond("I could not find Google Chrome installed on this computer.")
        return True

    try:
        subprocess.Popen([chrome_path])
        respond("Opening Google Chrome.")
    except OSError as error:
        print(f"Chrome start error ({type(error).__name__}): {error}")
        respond("I could not launch Google Chrome.")
    return True


def browser_action(action, message, *args):
    """Run a managed-browser action and report failures instead of faking success."""
    try:
        getattr(browser_controller, action)(*args)
        respond(message)
    except Exception as error:
        print(f"Browser action error ({type(error).__name__}): {error}")
        respond(
            "I could not control the managed browser. Install Playwright and "
            "its browser, then try again."
        )
    return True


def execute_command(command):
    """Route allow-listed local commands before using Groq as fallback."""
    local_action = classify_local_action(command)
    if local_action:
        command = local_action["command"]
    raw_command = re.sub(r"\bjarvis\b", " ", command.lower()).strip()
    normalized = re.sub(r"[^\w\s]", " ", command.lower())
    normalized = re.sub(r"\bjarvis\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Exit commands have highest priority.
    if normalized in {"stop", "exit", "quit", "goodbye", "shutdown"}:
        respond("Goodbye. Have a great day.")
        return False

    # Browser controls are explicit and take priority over conversation.
    if normalized in {"open chrome", "launch chrome"}:
        return open_chrome()
    if normalized in {"open browser", "open my browser", "launch the browser"}:
        return open_url("https://www.google.com", "Opening your browser.")
    if normalized in {"open a new tab", "new tab", "open new tab"}:
        return browser_action("new_tab", "Opening a new browser tab.")
    if normalized in {"go back", "browser back"}:
        return browser_action("go_back", "Going back in the browser.")
    if normalized in {"go forward", "browser forward"}:
        return browser_action("go_forward", "Going forward in the browser.")
    if normalized in {"refresh the page", "refresh page", "reload the page"}:
        return browser_action("refresh", "Refreshing the page.")
    if normalized in {"close the current tab", "close current tab"}:
        return browser_action("close_tab", "Closing the current tab.")
    if normalized in {"close the browser", "exit browser"}:
        return browser_action("close_browser", "Closing the managed browser.")
    if normalized in {"scroll up", "scroll down", "scroll to the top", "scroll to the bottom"}:
        direction = (
            "top" if "top" in normalized
            else "bottom" if "bottom" in normalized
            else "up" if "up" in normalized
            else "down"
        )
        return browser_action("scroll", f"Scrolling {direction}.", direction)

    # Website searches, websites, and applications take priority over conversation.
    search_match = None
    if not normalized.startswith(("search youtube", "search on youtube", "open youtube and search")):
        search_match = re.match(
            r"^(?:please\s+)?(?:search google|google|search the web|search for|find)\s+(?:for\s+)?(.+)",
            normalized,
        )
    if search_match:
        query = search_match.group(1).strip()
        if query:
            encoded_query = quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            open_url(search_url, f"Searching Google for {query}.")
        else:
            respond("What would you like me to search for?")
        return True

    youtube_match = re.match(
        r"^(?:search youtube for|search on youtube for|"
        r"open youtube and search for)\s+(.+)",
        normalized,
    )
    if not youtube_match and "youtube" in normalized and normalized.startswith(
        ("find", "play")
    ):
        youtube_match = re.search(
            r"(?:find|play)\s+(?:a\s+)?(?:video\s+)?(?:about\s+)?"
            r"(.+?)(?:\s+on youtube)?$",
            normalized,
        )
    if youtube_match:
        query = re.sub(
            r"\s+and\s+open the first video$|\s+and\s+open a video$",
            "",
            youtube_match.group(1).strip(),
        ).strip()
        if query:
            search_url = (
                "https://www.youtube.com/results?search_query="
                + quote_plus(query)
            )
            open_url(search_url, f"Searching YouTube for {query}.")
        else:
            respond("What would you like me to search for on YouTube?")
        return True

    navigation_match = re.fullmatch(
        r"(?:navigate to|go to|open)\s+((?:https?://)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?)",
        raw_command,
    )
    if navigation_match:
        destination = navigation_match.group(1)
        if not destination.startswith(("http://", "https://")):
            destination = "https://" + destination
        open_url(destination, f"Opening {destination}.")
        return True

    website_command = next(
        (website for website in WEBSITES if website == normalized),
        None,
    )
    if website_command:
        url, success_message = WEBSITES[website_command]
        open_url(url, success_message)
        if local_action and local_action["question"]:
            answer = ask_ai(local_action["question"])
            if answer:
                respond(answer)
        return True

    application_command = next(
        (application for application in LOCAL_APPLICATIONS if application == normalized),
        None,
    )
    if application_command:
        application_name = application_command.removeprefix("open ")
        try:
            subprocess.Popen([LOCAL_APPLICATIONS[application_command]])
            respond(f"Opening {application_name}.")
        except OSError:
            respond(f"I could not open {application_name}.")
        return True

    # Date and time are handled locally.
    if normalized in {"time", "what time is it", "tell me the time"}:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        respond(f"The current time is {current_time}.")
        return True

    if normalized in {"date", "what is the date", "tell me today's date"}:
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        respond(f"Today's date is {today}.")
        return True

    if normalized in MICROPHONE_CHECKS:
        respond("Yes, I can hear you clearly. How can I help you?")
        return True

    if normalized in WELLBEING_QUESTIONS:
        respond("I am doing well and ready to help you. How are you?")
        return True

    if normalized in GREETINGS:
        respond("Hello! How can I help you?")
        return True

    if normalized == "who are you":
        respond("I am Jarvis, your Python personal assistant.")
        return True

    answer = ask_ai(command)
    if answer:
        respond(answer)
    return True


def main():
    """Run the conversational NEXORA AI loop."""
    if not groq_api_key:
        print("GROQ_API_KEY is missing from the .env file.")
        respond("My AI service is not configured yet.")

    try:
        prepare_microphone()
        respond("Jarvis is online. How can I help you?")

        while True:
            command = listen()
            if command and not execute_command(command):
                break
    except KeyboardInterrupt:
        print()
        respond("Goodbye. Have a great day.")


if __name__ == "__main__":
    if "--test-speaker" in sys.argv[1:]:
        respond("Speaker test one.")
        respond("Speaker test two.")
        respond("Speaker test three. All responses can be spoken.")
    else:
        main()
