# ✦ NEXORA AI — Your Intelligent Companion

NEXORA AI is the user-facing brand for this project. Existing Python module,
database, and executable names remain compatible with local installations.

A smart, voice-controlled desktop assistant built with Python, Groq AI, Whisper speech recognition, and text-to-speech. JARVIS listens to your voice commands, opens Windows applications, launches websites, performs Google searches, answers questions using AI, and speaks its responses aloud.

Designed to bring hands-free desktop interaction and conversational AI together in a simple Windows application.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)
![AI](https://img.shields.io/badge/AI-Groq-orange)
![Speech](https://img.shields.io/badge/Speech-Whisper-purple)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [How It Works](#-how-it-works)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Run JARVIS](#-run-jarvis)
- [Web Dashboard](#-web-dashboard)
- [Voice Commands](#-voice-commands)
- [Testing](#-testing)
- [Run the Windows Executable](#-run-the-windows-executable)
- [Build from Source](#-build-from-source)
- [Troubleshooting](#-troubleshooting)
- [Security Best Practices](#-security-best-practices)
- [Future Improvements](#-future-improvements)
- [License](#-license)

---

## 🚀 Overview

NEXORA AI is a Python-based voice assistant that combines speech recognition,
local desktop automation, conversational AI, and speech synthesis.

Instead of manually opening applications or typing every query, users can interact with their computer through natural voice commands.

For example, say **"Open Notepad"** to launch an application, **"What time is it?"** to get the current time, or ask a general question to receive an AI-generated response.

The assistant prioritizes predefined local commands and uses the Groq API for conversational queries. It also supports Google Speech Recognition as a fallback when Groq Whisper transcription is unavailable.

### What makes JARVIS useful?

- Hands-free interaction with your Windows computer.
- Voice-based access to frequently used applications and websites.
- AI-powered conversational responses.
- Spoken feedback using text-to-speech.
- A standalone Windows executable option.
- A modular starting point for building more advanced desktop assistants.

## ✨ Features

### 🎙️ Voice Interaction
- Captures voice input through a microphone.
- Calibrates the microphone during startup.
- Converts speech into text using Groq Whisper.
- Falls back to Google Speech Recognition when appropriate.
- Provides spoken responses using `pyttsx3`.

### 🧠 AI-Powered Conversations
- Generates conversational answers through the Groq API.
- Maintains recent conversation history for contextual responses.
- Uses an available Groq chat model.
- Handles general questions that are not matched by local commands.

### 🖥️ Windows Desktop Automation

Launch commonly used Windows applications through voice commands.

| Application | Example command |
|---|---|
| Notepad | Open Notepad |
| Calculator | Open Calculator |
| Paint | Open Paint |
| Command Prompt | Open Command Prompt |
| File Explorer | Open File Explorer |

### 🌐 Website Automation

Open frequently used websites directly through voice commands.

| Website | Example command |
|---|---|
| Google | Open Google |
| YouTube | Open YouTube |
| Gmail | Open Gmail |
| GitHub | Open GitHub |

### 🔎 Google Search
- Performs Google searches from natural-language commands.
- Encodes search queries into URLs.
- Opens the resulting search page in the default browser.

Example:

`Search Google for Python tutorials`

### 🕒 Date and Time
- Retrieves the computer's local date.
- Retrieves the computer's local time.
- Responds to common greeting and assistant-status questions.

### 🔊 Speaker Test
- Includes a dedicated text-to-speech test mode.
- Verifies spoken output without requiring a microphone or API connection.

### 📦 Windows Executable
- Supports packaging through PyInstaller.
- Includes release and debug build specifications.
- Can run as a packaged Windows application without manually launching the Python script.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core application logic |
| Groq API | AI-powered conversational responses |
| Groq Whisper | Speech-to-text transcription |
| Google Speech Recognition | Alternative speech-recognition provider |
| SpeechRecognition | Microphone input and speech-recognition interface |
| PyAudio | Audio capture |
| pyttsx3 | Offline text-to-speech synthesis |
| python-dotenv | Environment variable and API key management |
| PyInstaller | Packaging the application as a Windows executable |

---

## ⚙️ How It Works

The following flow describes the main interaction cycle.

```mermaid
flowchart TD
    A([Start JARVIS]) --> B[Load environment variables]
    B --> C[Initialize available AI services]
    C --> D[Calibrate microphone]
    D --> E[Listen for voice command]
    E --> F[Convert speech to text]
    F --> G{Local command?}
    G -- Yes --> H[Execute allowed local action]
    G -- No --> I[Send query to Groq AI]
    H --> J[Prepare response]
    I --> J
    J --> K[Print response]
    K --> L[Speak response using pyttsx3]
    L --> M{Exit command?}
    M -- No --> E
    M -- Yes --> N([Stop JARVIS])
```

### Processing pipeline

1. **Initialization:** Load configuration from the `.env` file and initialize available services.
2. **Microphone setup:** Calibrate the microphone and prepare for voice input.
3. **Speech recognition:** Transcribe the captured audio using Groq Whisper, with Google recognition as a fallback.
4. **Command processing:** Match recognized text against predefined local commands.
5. **Action execution:** Launch an approved application, open a website, perform a Google search, or process a date/time request.
6. **AI response:** Send unmatched conversational questions to Groq, when available.
7. **Response delivery:** Print the response and read it aloud using `pyttsx3`.
8. **Continuous listening:** Repeat until the user gives an exit command.

---

## 📁 Project Structure

```text
Jarvis/
│
├── main.py                 # Main assistant and voice interaction loop
├── Jarvis.spec             # PyInstaller release configuration
├── JarvisDebug.spec        # PyInstaller debug configuration
├── .env                    # Local API configuration (not committed)
├── .gitignore              # Files excluded from version control
│
├── .venv/                  # Python virtual environment
│
├── build/                  # PyInstaller intermediate build files
│
└── dist/
    ├── Jarvis/
    │   ├── Jarvis.exe
    │   └── _internal/
    │
    └── JarvisDebug/
        ├── JarvisDebug.exe
        └── _internal/
```

**Note:** `.venv/`, `build/`, and `dist/` are local or generated directories. They do not necessarily need to be committed to the repository. The `.env` file should remain private.

---

## 📋 Prerequisites

Before installing JARVIS, ensure that you have:

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- A working microphone.
- Speakers or headphones.
- An active internet connection for Groq and Google speech-recognition services.
- A Groq API key for AI responses and Groq Whisper transcription.
- PowerShell or another compatible terminal.

Check your Python installation:

```powershell
py --version
```

Check whether pip is available:

```powershell
py -m pip --version
```

---

## 📥 Installation

### 1. Open the project directory

Open PowerShell and navigate to the directory containing JARVIS.

```powershell
cd "C:\Users\palla\OneDrive\Documents\Projects\Jarvis"
```

Replace the path with your actual project location if necessary.

### 2. Activate the existing virtual environment

If the repository already contains `.venv`, activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation succeeds, your terminal should show the environment name.

### 3. Create a virtual environment if required

If `.venv` does not exist, create a new environment:

```powershell
py -3 -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

Upgrade pip and install the required packages:

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
python -m playwright install chromium
```

**PyAudio installation note:** If installation fails, check that your Python version and architecture are compatible with the available Windows wheel. Install a compatible wheel from a trusted source, then retry the dependency installation.

The Playwright browser is used for reliable tab navigation, history, refresh, and
scroll commands. JARVIS keeps its managed browser profile in `.browser-profile`
and falls back to the Windows default browser for ordinary URL launches if
Playwright is unavailable.

### 5. Configure your API key

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_groq_api_key_here
```

Get your API key from the [Groq Console](https://console.groq.com/keys).

Replace the placeholder with your actual key. Do not include the key in screenshots, public commits, or issue reports.

---

## 🔐 Configuration

JARVIS uses environment variables to keep API credentials separate from application code.

### Required environment variable

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | API key used for Groq services |

### Configuration checklist

- [ ] The `.env` file exists in the project root.
- [ ] `GROQ_API_KEY` contains a valid API key.
- [ ] `.env` is excluded from Git commits.
- [ ] The selected Groq models are available to your account.
- [ ] The computer has an active internet connection.

The Python source and packaged executable use different locations for loading `.env`. For the packaged application, place the file beside the executable, as explained in the executable section.

---

## ▶️ Run JARVIS

### Start from source

With the virtual environment activated:

```powershell
python .\main.py
```

Alternatively, launch the script using the virtual environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

### Startup behavior

On startup, JARVIS initializes its available services, calibrates the microphone, and announces that it is online.

Wait for the `Listening...` message before speaking your command.

### Stop the assistant

Say any of the following:

- `Stop`
- `Exit`
- `Quit`
- `Goodbye`
- `Shutdown`

You can also stop the program by pressing `Ctrl+C` in the terminal.

## 🖥️ Web Dashboard

NEXORA AI uses two local services with separate responsibilities: the public API
serves authenticated Groq chat and MongoDB history, while the loopback-only
Windows API owns the physical microphone, local speech, and allowlisted desktop
actions. The existing SQLite store remains available to the desktop assistant;
cloud account history is stored in MongoDB.

### Run the local dashboard and Windows assistant

Start MongoDB first and configure `.env` with `MONGODB_URI`,
`MONGODB_DATABASE`, `JWT_SECRET_KEY`, and `GROQ_API_KEY`. Install dependencies if
needed. The optional `run_local.bat` opens the cloud API, Windows API, and Vite
frontend in separate terminals.

Start them manually from the project directory in three terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.public_server:app --host 127.0.0.1 --port 8002
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.server:app --host 127.0.0.1 --port 8765
```

```powershell
cd .\frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://localhost:5173`. Vite sends login, AI chat, and conversation history
to `/api` -> `http://127.0.0.1:8002`; the microphone, local speech, and computer
actions use `/local-api` -> `http://127.0.0.1:8765`. The Windows API binds only
to loopback. Cloud chat history remains authenticated and MongoDB-backed.

Vite proxy targets are configurable with `VITE_CLOUD_API_PROXY_TARGET` and
`VITE_LOCAL_API_PROXY_TARGET` in `frontend/.env.local`. If you change the local
API port, start `api.server:app` on that port and update the matching Vite
proxy target. Production builds use `VITE_API_BASE_URL` for the cloud API and
optionally `VITE_LOCAL_API_BASE_URL` for the local service on the user's PC. Do
not put database or Groq secrets in Vercel.

Verify the local service with
`Invoke-RestMethod http://127.0.0.1:8765/api/health`. To test the microphone,
sign in, open Chat or Voice Control, click the mic, grant microphone access,
speak a short question, and wait for the transcript and answer. Do not run the
terminal listener in `main.py` at the same time; both use the same microphone.
To test computer control, enter `Open YouTube` and confirm the browser opens.
For cloud AI, ask `What is machine learning?`; the answer should appear in the
conversation and persist in your account history.

If local controls are unavailable while typed AI chat works, start
`api.server:app` and check port 8765. If login or chat is unavailable, check the
public API on port 8002, MongoDB readiness at `/api/ready`, and Groq
configuration. Local action requests are allowlisted; arbitrary shell and
Python execution are not supported.

For deployed browser voice, open the system status panel and choose
**Enable spoken replies** after signing in. Ask a typed question to hear the
new response, or use the speaker button on an assistant message. The browser
must support `speechSynthesis`; autoplay restrictions are handled by requiring
this user action first. The microphone button uses `SpeechRecognition` or
`webkitSpeechRecognition` when available over HTTPS. Chrome and Edge are the
recommended browsers; microphone permission must be granted. If browser
recognition is unavailable, the button reports that limitation rather than
pretending the local Windows microphone is online.

Run the mock-safe regression checks from the repository root with
`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`, and run the
frontend routing checks with `cd frontend; npm test`. The frontend production
bundle can be checked with `npm run build` from `frontend`.

The existing `main.py --test-speaker` mode and PyInstaller executable remain
available. The web dashboard is a development/source workflow and is not
bundled into the existing executable specifications.

## ☁️ Public Demo Deployment

The public demo is deliberately text-only. Use `api.public_server:app` for a
cloud deployment; it does not import `main.py` and therefore does not load
PyAudio, Windows process controls, browser automation, local SQLite history, or
`pyttsx3`. It cannot execute operating-system commands or claim to speak
through a visitor's speakers. The dashboard uses browser Web Speech APIs for
optional microphone recognition and spoken cloud replies when the browser
supports them. These browser features are independent of the optional local
Windows assistant.

### Render backend

Render uses the cloud-only dependency file `requirements-render.txt`; the
local `requirements.txt` intentionally retains Windows microphone, speech,
TTS, and browser dependencies.

The Blueprint targets Render's free web-service plan. Free services sleep after
inactivity and have ephemeral local storage, so the public API must not use
`jarvis_history.sqlite3` for production data. Conversation history is stored in
MongoDB Atlas configured by `MONGODB_URI`.

Set these environment variables in Render:

```text
GROQ_API_KEY=your_server_side_key
GROQ_MODEL=openai/gpt-oss-20b
PUBLIC_FRONTEND_ORIGINS=https://nexora-ai-two-smoky.vercel.app
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=nexora
JWT_SECRET_KEY=your_long_random_secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
COOKIE_SECURE=true
COOKIE_SAMESITE=none
```

Start command:

```text
uvicorn api.public_server:app --host 0.0.0.0 --port $PORT
```

Health check: `/api/health`; database readiness check: `/api/ready`. Keep the
Groq key, MongoDB URI, and JWT secret server-side and never place them in Vercel
environment variables exposed to the browser. The public demo uses FastAPI
authentication and MongoDB Atlas, with every conversation and message scoped to
the authenticated user. The local desktop dashboard continues to use SQLite.

### Vercel frontend

Set `VITE_API_BASE_URL` to the deployed public API URL ending in `/api`
(without a trailing slash after `api`), for example
`https://nexora-ai-api.onrender.com/api`,
and do not add MongoDB or JWT secrets to Vercel. Authentication is handled by
the FastAPI backend using secure cookies.
Then build the `frontend` directory with:

```text
npm install
npm run build
```

Configure the Vercel project root as `frontend`. For local development,
`.env.example` documents the local API URL. Local mode should use
`api.server:app`; public demo mode should use `api.public_server:app`.

---

## 🗣️ Voice Commands

Here are examples of supported interactions.

### General conversation

| Say this | Expected behavior |
|---|---|
| Hello Jarvis | Responds to the greeting |
| Who are you? | Describes the assistant |
| How are you? | Responds conversationally |
| Can you hear me? | Responds to the status question |
| What time is it? | Returns the local time |
| What is the date? | Returns the local date |

### Open Windows applications

```text
Open Notepad
Open Calculator
Open Paint
Open Command Prompt
Open File Explorer
```

### Open websites

```text
Open Google
Open YouTube
Open Gmail
Open GitHub
Open ChatGPT
Open Wikipedia
Open Stack Overflow
Open the Python documentation
```

### Search Google

```text
Search Google for Python tutorials
Search Google for machine learning projects
Search Google for Java interview questions
Search the web for LangGraph tutorials
Google Python list comprehensions
```

### Browser actions

```text
Open Chrome
Open my browser
Open a new browser tab
Go to YouTube
Open YouTube and search for Python tutorials
Search YouTube for Java DSA
Find a video about recursion on YouTube
Go back
Go forward
Refresh the page
Scroll down
Scroll to the top
Close the current tab
Close the browser
Navigate to https://example.com
```

Google and YouTube searches URL-encode the spoken query before navigation.
YouTube requests open the search results page; JARVIS does not invent video
IDs or claim that a video is playing. Direct browser controls use the
JARVIS-managed Playwright browser. An already-open browser that was launched
outside JARVIS cannot always be attached to safely, so JARVIS reports that
limitation instead of pretending the action succeeded. Chrome-specific launch
commands also report when Chrome is not installed.

### Ask AI questions

```text
Explain Python decorators.
What is the difference between AI and machine learning?
Explain how a REST API works.
Give me tips for debugging Python applications.
```

Questions that are not handled by the predefined local command logic are sent to Groq for conversational processing when the service is available.

**Important:** The commands listed above describe the intended supported behavior. Actual recognition accuracy depends on the microphone, background noise, and speech-recognition service.

---

## 🧪 Testing

JARVIS currently supports manual validation rather than a dedicated automated unit-test suite.

### 1. Python syntax check

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile .\main.py
```

If the command completes without output, the file passed Python's syntax compilation check.

### 2. Speaker test

Run:

```powershell
.\.venv\Scripts\python.exe .\main.py --test-speaker
```

You should hear three messages:

1. Speaker test one.
2. Speaker test two.
3. Speaker test three. All responses can be spoken.

This test checks text-to-speech output without requiring microphone input or an API connection.

### 3. Full manual test

Start the assistant:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

Verify the following:

- [ ] Microphone calibration completes.
- [ ] JARVIS announces that it is online.
- [ ] A greeting produces a spoken response.
- [ ] Date and time commands return local values.
- [ ] Application commands launch the correct programs.
- [ ] Website commands open the expected websites.
- [ ] Google searches use the requested search terms.
- [ ] YouTube searches open encoded search results.
- [ ] Managed-browser tab, history, refresh, and scroll commands report success
      only after the browser action completes.
- [ ] A general question receives a Groq response.
- [ ] The assistant speaks its response.
- [ ] An exit command stops the assistant cleanly.

### 4. Test the packaged executable

Launch `Jarvis.exe` and repeat the relevant manual checks. Confirm that the packaged application can locate its configuration, access the microphone, and produce audio output.

---

## 📦 Run the Windows Executable

A packaged Windows build is available under `dist`, provided that the generated files have been included in your local project.

### Release build

```powershell
.\dist\Jarvis\Jarvis.exe
```

### Debug build

```powershell
.\dist\JarvisDebug\JarvisDebug.exe
```

### Required directory structure

Keep the packaged directory together. The executable depends on supporting files in `_internal`.

```text
dist/
└── Jarvis/
    ├── Jarvis.exe
    ├── .env
    └── _internal/
```

Place `.env` beside `Jarvis.exe`, not inside `_internal`.

For distribution, do not bundle your personal API key. Each user should configure their own credentials securely.

---

## 🏗️ Build from Source

JARVIS includes PyInstaller specifications for release and debug builds.

### 1. Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Install PyInstaller

```powershell
python -m pip install pyinstaller
```

### 3. Build the release version

```powershell
python -m PyInstaller .\Jarvis.spec
```

### 4. Build the debug version

```powershell
python -m PyInstaller .\JarvisDebug.spec
```

### 5. Run the generated application

Check the `dist` directory for the generated executable and its supporting files.

**Note:** The exact output location depends on the settings in the corresponding `.spec` file. Ensure that the packaged application can locate `.env` and all required runtime dependencies before distributing it.

---

## 🛠️ Troubleshooting

### `GROQ_API_KEY is missing`

Check that `.env` exists in the correct directory.

For source execution, it should be beside `main.py`. For packaged execution, it should be beside `Jarvis.exe`.

Example:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### Microphone errors

- Check Windows microphone permissions.
- Select the correct default recording device in Windows Sound settings.
- Verify that the microphone works in another application.
- Close other applications that might be using the microphone.
- Confirm that PyAudio is installed in the active virtual environment.

### No speech is heard

- Check system volume and application volume.
- Verify the selected output device.
- Connect your speakers or headphones.
- Run the speaker test:

```powershell
.\.venv\Scripts\python.exe .\main.py --test-speaker
```

### PyAudio installation fails

Check the Python version and architecture, then install a compatible Windows wheel if required. Avoid installing arbitrary binaries from untrusted sources.

### Groq requests fail

- Verify the API key.
- Check the internet connection.
- Confirm that your account can access the selected models.
- Check whether you have reached an API usage or rate limit.
- Review the diagnostic output in PowerShell.

### Browser controls fail

- Install the Python dependency and the Playwright browser:

  ```powershell
  python -m pip install -r .\requirements.txt
  python -m playwright install chromium
  ```

- Keep the generated `.browser-profile` directory writable.
- If you only need to open a URL, JARVIS can use the Windows default browser
  even when managed browser controls are unavailable.
- JARVIS does not silently attach to or control an unrelated browser session.

### Google Speech Recognition fails

Check your internet connection and microphone input. Google recognition is a fallback service and may also fail because of network issues or service availability.

### PowerShell blocks script activation

You can run JARVIS without activating the virtual environment:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

Alternatively, if appropriate for your environment, allow locally created scripts for the current Windows user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Review your organization's security policies before changing execution settings.

### Executable cannot find `.env`

Place `.env` in the directory containing `Jarvis.exe`. Restart the application after making the change.

---

## 🔒 Security Best Practices

- **Protect API credentials:** Never publish your Groq API key.
- **Exclude secrets from Git:** Keep `.env` in `.gitignore`.
- **Rotate exposed keys:** Revoke and replace a key immediately if it becomes public.
- **Restrict local execution:** Keep application launching limited to explicitly allowed commands.
- **Validate user input:** Treat recognized speech as untrusted input.
- **Avoid arbitrary command execution:** Do not pass unrestricted voice input directly to PowerShell, Command Prompt, or a shell.
- **Use trusted dependencies:** Install packages from trusted package indexes and sources.
- **Protect distributed builds:** Do not distribute an executable containing your personal API credentials.

JARVIS is designed around predefined local commands rather than unrestricted voice-driven shell execution. Preserve that restriction when adding new functionality.

---

## 🚀 Future Improvements

Potential enhancements for future versions include:

- [ ] Wake-word detection for hands-free activation.
- [ ] A graphical user interface with a listening indicator.
- [ ] Improved background-noise handling.
- [ ] Configurable voice, speech rate, and volume.
- [ ] More customizable application and website commands.
- [ ] A plugin-based command architecture.
- [ ] Better offline command handling.
- [ ] Automated unit and integration tests.
- [ ] Structured logging and improved error reporting.
- [ ] Configurable AI models and conversation settings.
- [ ] Additional accessibility features.
- [ ] Secure configuration management for distributed builds.

These are possible future enhancements, not features claimed to be implemented in the current version.

---

## 🤝 Contributing

Contributions and suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Implement and test your changes.
4. Keep API credentials and other secrets out of commits.
5. Submit a pull request describing the change.

When reporting an issue, include the relevant error message and reproduction steps. Never include API keys or other private credentials in logs or screenshots.

---

## 📄 License

No license file is currently included in this project.

Before distributing or accepting external contributions, consider adding an appropriate open-source license. Until a license is added, others should not assume that the repository is freely reusable.

---

## ⭐ Acknowledgements

JARVIS builds on the Python ecosystem and the services and libraries that make desktop voice interaction possible:

- [Python](https://www.python.org/)
- [Groq](https://groq.com/)
- [Groq Console](https://console.groq.com/)
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition/)
- [PyAudio](https://pypi.org/project/PyAudio/)
- [pyttsx3](https://pypi.org/project/pyttsx3/)
- [PyInstaller](https://pyinstaller.org/)
- [Playwright](https://playwright.dev/python/)

---
example how to run:
(.venv) PS C:\Users\palla\OneDrive\Documents\Projects\Jarvis> .\.venv\Scripts\python.exe .\main.py
                    or
(.venv) PS C:\Users\palla\OneDrive\Documents\Projects\Jarvis> python main.py


**NEXORA AI — Your voice, your commands, your intelligent companion.** ✦
