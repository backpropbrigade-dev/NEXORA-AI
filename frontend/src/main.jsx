import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity, AppWindow, ArrowLeft, Bot, Calculator, ChevronDown, Clock3,
  FileText, FolderOpen, Globe2, Github, History, Home, Mail, Menu, MessageSquare,
  Mic, Moon, MoreHorizontal, Palette, Paintbrush, Plus, RefreshCw, Search,
  Send, Settings, Sparkles, Sun, Terminal, Trash2, Youtube, Zap, LockKeyhole,
  Eye, EyeOff, ArrowRight, ShieldCheck, Layers3, LogOut
} from "lucide-react";
import "./styles.css";
import { localActionRequest } from "./localActions.js";
import {
  cancelSpeech,
  createSpeechRecognition,
  speechRecognitionConstructor,
  speechSynthesisSupported,
  speakText,
} from "./voice.js";

// Use Vite's same-origin proxy during local development to keep auth cookies
// first-party and avoid browser CORS. Production builds use the configured API.
const withoutTrailingSlash = (value) => value.replace(/\/+$/, "");
const cloudApiBase = (value) => {
  const normalized = withoutTrailingSlash(value);
  return normalized === "/api" || normalized.endsWith("/api")
    ? normalized
    : `${normalized}/api`;
};
const API = import.meta.env.DEV
  ? "/api"
  : cloudApiBase(import.meta.env.VITE_API_BASE_URL || "/api");
const LOCAL_API = import.meta.env.DEV
  ? "/local-api"
  : withoutTrailingSlash(import.meta.env.VITE_LOCAL_API_BASE_URL || "http://127.0.0.1:8765/api");
const localHostnames = new Set(["localhost", "127.0.0.1", "[::1]"]);
const LOCAL_API_ENABLED = import.meta.env.DEV
  || (localHostnames.has(window.location.hostname)
    && import.meta.env.VITE_ENABLE_LOCAL_API === "true");
const navItems = [
  ["home", "Home", Home], ["chat", "Chat", MessageSquare],
  ["voice", "Voice Control", Mic], ["apps", "Applications", AppWindow],
  ["browser", "Browser", Globe2], ["history", "Chat History", History],
  ["settings", "Settings", Settings],
];
const shortcuts = [
  ["Google", "Open Google", Globe2, "website"], ["YouTube", "Open YouTube", Youtube, "website"],
  ["Gmail", "Open Gmail", Mail, "website"], ["GitHub", "Open GitHub", Github, "website"],
  ["Notepad", "Open Notepad", FileText, "app"], ["Calculator", "Open Calculator", Calculator, "app"],
  ["Paint", "Open Paint", Paintbrush, "app"], ["File Explorer", "Open File Explorer", FolderOpen, "app"],
];

function microphoneLabel(value) {
  return {
    not_checked: "Not checked",
    checking: "Checking",
    available: "Available",
    listening: "Listening",
    permission_denied: "Permission denied",
    permission_needed: "Permission needed",
    unavailable: "Unavailable",
    device_unavailable: "Device unavailable",
    error: "Error",
  }[value] || "Not checked";
}

function voiceInteractionState(status) {
  if (["disconnected", "unavailable"].includes(status.local_service)) return "disconnected";
  if (["connecting", "checking"].includes(status.local_service)) return "connecting";
  return ({ idle: "ready", ready: "ready", starting: "connecting", stopping: "connecting" })[status.status] || status.status;
}

function localServiceLabel(value) {
  if (["ready", "available"].includes(value)) return "Ready";
  if (["connecting", "checking"].includes(value)) return "Connecting";
  return "Unavailable";
}

async function request(path, options = {}, apiBase = API) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || 15000);
  delete options.timeout;
  const url = new URL(`${apiBase}${path}`, window.location.origin);
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      credentials: apiBase === API ? "include" : "omit",
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The server took too long to respond. Check that the API is running.");
    }
    throw new Error(`Cannot reach the API at ${url.pathname}. Check that the backend is running and the Vite proxy is active.`);
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    // A protected request can outlive its 30-minute access cookie. Notify the
    // app so it can return to sign-in instead of leaving a stale chat session
    // on screen. Login failures are handled by AuthScreen and are excluded.
    if (response.status === 401 && apiBase === API && !path.startsWith("/auth/")) {
      window.dispatchEvent(new Event("nexora:session-expired"));
    }
    let detail = `Backend request failed (${response.status})`;
    try {
      const body = await response.json();
      const responseDetail = body.detail;
      if (typeof responseDetail === "string") {
        detail = responseDetail;
      } else if (Array.isArray(responseDetail)) {
        detail = responseDetail.map((item) => item?.msg).filter(Boolean).join(" ") || detail;
      }
    } catch {
      // Keep the status-based message for HTML or empty server error responses.
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

const requestLocal = (path, options = {}) => request(path, options, LOCAL_API);

function App() {
  const [session, setSession] = useState(null);
  const [page, setPage] = useState("home");
  const [theme, setTheme] = useState(() => localStorage.getItem("nexora-theme") || (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  const [status, setStatus] = useState({ status: "idle", message: "Click to Start Listening.", groq: "unknown", microphone: "not_checked", speech_engine: "unknown", local_service: LOCAL_API_ENABLED ? "connecting" : "unavailable" });
  const [conversations, setConversations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [historySearch, setHistorySearch] = useState("");
  const [toast, setToast] = useState("");
  const [authNotice, setAuthNotice] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const sendMessageRef = useRef(null);
  const voiceChatInFlight = useRef(false);
  const validatedSessionRef = useRef(null);
  const browserRecognitionRef = useRef(null);

  useEffect(() => { localStorage.setItem("nexora-theme", theme); }, [theme]);

  useEffect(() => {
    const handleSessionExpired = () => {
      setSession(null);
      setPage("home");
      setSelected(null);
      setMessages([]);
      setAuthNotice("Your session expired. Please sign in again to continue.");
    };
    window.addEventListener("nexora:session-expired", handleSessionExpired);
    return () => window.removeEventListener("nexora:session-expired", handleSessionExpired);
  }, []);

  useEffect(() => {
    request("/auth/session")
      .then((result) => setSession(result.user))
      .catch((error) => {
        setSession(null);
        if (error.status !== 401) setToast(error.message);
      });
  }, []);

  const loadConversations = async (search = historySearch) => {
    try { setConversations(await request(`/conversations?search=${encodeURIComponent(search)}`)); }
    catch (error) { setToast(error.message); }
  };
  const selectConversation = async (id) => {
    try { const conversation = await request(`/conversations/${id}`); setSelected(id); setMessages(conversation.messages); setPage("chat"); }
    catch (error) { setToast(error.message); }
  };
  const newChat = async () => {
    try { const conversation = await request("/conversations", { method: "POST", body: JSON.stringify({}) }); setSelected(conversation.id); setMessages([]); setPage("chat"); loadConversations(); }
    catch (error) { setToast(error.message); }
  };
  const localUnavailableText = "Local computer control is unavailable. Start the NEXORA AI Windows assistant to use this feature.";
  const browserSpeechAvailable = speechSynthesisSupported();
  const browserRecognitionAvailable = Boolean(speechRecognitionConstructor());
  const updateSpeechState = (speechState) => {
    setStatus((current) => ({
      ...current,
      speech_engine: speechState === "speaking" ? "Speaking"
        : speechState === "error" ? "Error"
          : speechState === "unavailable" ? "Unavailable" : "Ready",
      status: speechState === "speaking" ? "speaking" : current.status,
    }));
  };
  const speak = useCallback((text) => {
    if (!browserSpeechAvailable) {
      setToast("Speech synthesis is unavailable in this browser.");
      updateSpeechState("unavailable");
      return false;
    }
    return speakText(text, updateSpeechState);
  }, [browserSpeechAvailable]);
  const toggleSpeech = () => {
    if (!browserSpeechAvailable) {
      setToast("Speech synthesis is unavailable in this browser.");
      updateSpeechState("unavailable");
      return;
    }
    if (speechEnabled) {
      cancelSpeech();
      setSpeechEnabled(false);
      updateSpeechState("ready");
      return;
    }
    setSpeechEnabled(true);
    updateSpeechState("ready");
    setToast("Spoken responses enabled.");
  };
  const runAction = async (command) => {
    if (!LOCAL_API_ENABLED) {
      setToast("Local computer control is disabled for this deployment.");
      return;
    }
    try {
      const result = await requestLocal("/actions/execute", { method: "POST", body: JSON.stringify({ command }), timeout: 20000 });
      if (!result.ok) throw new Error(result.message || "The local action did not complete.");
      setToast(result.message);
    } catch (error) {
      setToast(error.status === 422 ? error.message : localUnavailableText);
    }
  };
  const toggleVoice = useCallback(async () => {
    if (!LOCAL_API_ENABLED) {
      if (!browserRecognitionAvailable) {
        setToast("Browser microphone recognition is unavailable. Use Chrome or Edge over HTTPS.");
        setStatus((current) => ({ ...current, microphone: "unavailable", status: "error", message: "Microphone recognition unavailable." }));
        return;
      }
      if (status.status === "listening") {
        browserRecognitionRef.current?.stop();
        return;
      }
      setStatus((current) => ({ ...current, status: "starting", microphone: "permission_needed", message: "Requesting microphone permission..." }));
      const recognition = createSpeechRecognition(
        (transcript, isFinal) => {
          if (transcript) setStatus((current) => ({ ...current, last_transcript: transcript, microphone: isFinal ? "available" : "listening" }));
          if (isFinal && transcript) {
            browserRecognitionRef.current?.stop();
            setStatus((current) => ({ ...current, status: "processing", microphone: "available", message: "Sending your voice request..." }));
            Promise.resolve(sendMessageRef.current?.(transcript, "voice"))
              .catch((error) => setToast(error.message || "The voice request could not be completed."))
              .finally(() => setStatus((current) => ({ ...current, status: "idle", message: "Click to Start Listening." })));
          }
        },
        (error) => {
          const message = error === "not-allowed"
            ? "Microphone permission was denied. Allow microphone access in your browser settings."
            : `Browser microphone error: ${error}.`;
          setStatus((current) => ({ ...current, status: "error", microphone: error === "not-allowed" ? "permission_denied" : "error", message }));
          setToast(message);
        },
        () => {
          browserRecognitionRef.current = null;
          setStatus((current) => current.status === "listening" || current.status === "starting"
            ? { ...current, status: "idle", microphone: "available", message: "Click to Start Listening." } : current);
        },
      );
      if (!recognition) return;
      browserRecognitionRef.current = recognition;
      try {
        recognition.start();
        setStatus((current) => ({ ...current, status: "listening", microphone: "listening", message: "Listening... Speak now..." }));
      } catch {
        browserRecognitionRef.current = null;
        setStatus((current) => ({ ...current, status: "error", microphone: "error", message: "The browser microphone could not be started." }));
      }
      return;
    }
    const currentVoiceState = voiceInteractionState(status);
    if (currentVoiceState === "disconnected" || currentVoiceState === "connecting") {
      setToast("Connecting to the Windows assistant. Start it with run_local.bat and try again when Local control shows Ready.");
      return;
    }
    if (["processing", "speaking"].includes(currentVoiceState)) return;
    if (currentVoiceState === "listening") {
      setStatus((current) => ({ ...current, status: "stopping", message: "Stopping microphone..." }));
      try { await requestLocal("/voice/stop", { method: "POST", timeout: 5000 }); }
      catch { setToast(localUnavailableText); setStatus((current) => ({ ...current, status: "idle", microphone: "error" })); }
      return;
    }
    setStatus((current) => ({ ...current, status: "starting", message: "Starting microphone...", microphone: "checking" }));
    try {
      const result = await requestLocal("/voice/start", { method: "POST", body: JSON.stringify({}), timeout: 8000 });
      if (!result.ok) {
        const startError = new Error(result.message || "The microphone could not be started.");
        startError.microphone = result.microphone || "error";
        throw startError;
      }
    } catch (error) {
      const unavailable = error.message.startsWith("Cannot reach the API") || error.message.includes("too long");
      setToast(unavailable ? localUnavailableText : error.message);
      setStatus((current) => ({ ...current, status: "error", message: unavailable ? "Local assistant unavailable." : error.message, microphone: error.microphone || "error", local_service: unavailable ? "disconnected" : current.local_service }));
    }
  }, [status.status, status.local_service]);
  const sendMessage = async (message, inputType = "text") => {
    if (!message.trim()) return;
    let id = selected;
    if (!id) { const conversation = await request("/conversations", { method: "POST", body: JSON.stringify({}) }); id = conversation.id; setSelected(id); }
    const action = localActionRequest(message);
    let actionResult = null;
    if (action) {
      if (!LOCAL_API_ENABLED) {
        setToast("Local computer control is disabled for this deployment.");
        return;
      }
      try {
        const localResult = await requestLocal("/actions/execute", { method: "POST", body: JSON.stringify({ command: action.command }), timeout: 20000 });
        if (!localResult.ok) throw new Error(localResult.message || "The local action did not complete.");
        actionResult = localResult.message;
      } catch (error) {
        setToast(error.status === 422 ? error.message : localUnavailableText);
        return;
      }
    }
    setMessages((current) => [...current, { role: "user", content: message, created_at: new Date().toISOString() }]);
    try {
      const payload = { conversation_id: id, message, input_type: inputType };
      if (actionResult) {
        payload.action_result = actionResult;
        if (action.question) payload.follow_up_question = action.question;
      }
      const result = await request("/chat", { method: "POST", body: JSON.stringify(payload) });
      setMessages(result.conversation.messages); loadConversations();
      if (speechEnabled && result.response) {
        speak(result.response);
      }
    } catch (error) { setToast(error.message); }
  };
  sendMessageRef.current = sendMessage;
  useEffect(() => {
    if (!session) {
      validatedSessionRef.current = null;
      return undefined;
    }
    const sessionId = session.id;
    const loadAuthenticatedData = () => Promise.all([
      request("/status").then((cloudStatus) => setStatus((current) => ({ ...current, ...cloudStatus, local_service: current.local_service }))),
      loadConversations(historySearch),
    ]);
    if (validatedSessionRef.current === sessionId) {
      loadAuthenticatedData().catch((error) => setToast(error.message));
      return undefined;
    }
    request("/auth/session")
      .then((result) => {
        if (!result.user || result.user.id !== sessionId) {
          setSession(null);
          setAuthNotice("Your login session was not saved. Please sign in again.");
          return;
        }
        validatedSessionRef.current = sessionId;
        return loadAuthenticatedData();
      })
      .catch(() => setStatus((current) => ({ ...current, status: "error", message: "Cloud API unavailable" })));
    return undefined;
  }, [session, historySearch]);
  useEffect(() => () => {
    browserRecognitionRef.current?.stop();
    cancelSpeech();
  }, []);
  useEffect(() => {
    if (!session) return undefined;
    if (!LOCAL_API_ENABLED) {
      setStatus((current) => ({ ...current, local_service: "unavailable" }));
      return undefined;
    }
    let active = true;
    let socket;
    let retryTimer;
    let handshakeTimer;
    let retryDelay = 1000;
    let connectionNoticeShown = false;
    const socketUrl = new URL(`${LOCAL_API}/events`, window.location.origin);
    socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";
    const markUnavailable = () => {
      if (!active) return;
      setStatus((current) => ({ ...current, local_service: "disconnected" }));
      if (!connectionNoticeShown) {
        setToast("Windows assistant is unavailable. Run run_local.bat and keep its local API window running.");
        connectionNoticeShown = true;
      }
    };
    const scheduleReconnect = () => {
      if (!active || retryTimer) return;
      markUnavailable();
      retryTimer = setTimeout(() => {
        retryTimer = undefined;
        connectLocalService();
      }, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 10000);
    };
    const connectLocalService = async () => {
      setStatus((current) => ({ ...current, local_service: "connecting" }));
      try {
        await requestLocal("/health", { timeout: 4000 });
        const localStatus = await requestLocal("/status", { timeout: 4000 });
        if (!active) return;
        setStatus((current) => ({ ...current, ...localStatus, local_service: "connecting" }));
        socket = new WebSocket(socketUrl);
        handshakeTimer = setTimeout(() => socket?.close(), 5000);
        socket.onopen = () => {
          clearTimeout(handshakeTimer);
          retryDelay = 1000;
          connectionNoticeShown = false;
          setStatus((current) => ({ ...current, local_service: "ready" }));
        };
        socket.onmessage = (event) => {
          let data;
          try { data = JSON.parse(event.data); }
          catch { return; }
          if (["listening_finished", "response_received"].includes(data.type) && voiceChatInFlight.current) return;
          setStatus((current) => ({ ...current, ...data, local_service: "ready" }));
          if (data.type === "transcript_received" && data.transcript) {
            voiceChatInFlight.current = true;
            setPage("chat");
            setStatus((current) => ({ ...current, status: "processing", message: "Thinking about your request...", local_service: "ready" }));
            Promise.resolve(sendMessageRef.current?.(data.transcript, "voice"))
              .catch((error) => setToast(error.message || "The voice request could not be completed."))
              .finally(() => {
                voiceChatInFlight.current = false;
                setStatus((current) => ({ ...current, status: "idle", message: "Click to Start Listening." }));
              });
          }
        };
        socket.onerror = () => socket?.close();
        socket.onclose = () => {
          clearTimeout(handshakeTimer);
          if (active) scheduleReconnect();
        };
      } catch {
        scheduleReconnect();
      }
    };
    connectLocalService();
    return () => {
      active = false;
      clearTimeout(retryTimer);
      clearTimeout(handshakeTimer);
      socket?.close();
    };
  }, [session]);
  useEffect(() => {
    const handler = (event) => {
      const target = document.activeElement;
      const editing = target && (
        ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
        || target.isContentEditable
      );
      if (event.code === "Space" && !editing) {
        event.preventDefault();
        toggleVoice();
      }
      if (event.code === "Escape" && !editing && status.status === "listening") {
        event.preventDefault();
        toggleVoice();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [status.status, toggleVoice]);

  const nav = (target) => { setPage(target); setMobileOpen(false); };
  if (!session) return <AuthScreen theme={theme} setTheme={setTheme} notice={authNotice} onAuthenticated={(user) => { setAuthNotice(""); setSession(user); }} />;
  const logout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await request("/auth/logout", { method: "POST" });
      setPage("home");
      setSelected(null);
      setMessages([]);
      setConversations([]);
      setHistorySearch("");
      setAuthNotice("");
      setToast("");
      setSession(null);
    } catch {
      setToast("Could not sign out right now. Check your connection and try again.");
    } finally {
      setLoggingOut(false);
    }
  };
  return <div className={`app ${theme}`}><Sidebar theme={theme} page={page} nav={nav} conversations={conversations} search={historySearch} setSearch={setHistorySearch} selected={selected} select={selectConversation} newChat={newChat} mobileOpen={mobileOpen} status={status} onLogout={logout} loggingOut={loggingOut} speechEnabled={speechEnabled} toggleSpeech={toggleSpeech} />
    <main className="workspace">
      <header className="topbar"><button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={18} /></button><div className={`status-dot ${voiceInteractionState(status)}`} /><span>{status.local_service === "disconnected" ? "Windows assistant is offline. Run run_local.bat." : status.local_service === "connecting" ? "Connecting to local Windows assistant..." : status.message}</span><div className="top-actions"><button className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Toggle theme">{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button><span className="live-label">LOCAL / {voiceInteractionState(status).toUpperCase()}</span></div></header>
      <div className="content">{page === "home" && <HomePage status={status} activity={[]} runAction={runAction} toggleVoice={toggleVoice} nav={nav} />}
        {page === "chat" && <ChatPage messages={messages} send={sendMessage} status={status} toggleVoice={toggleVoice} speak={speak} />}
        {page === "voice" && <VoicePage status={status} toggleVoice={toggleVoice} />}
        {page === "apps" && <AppsPage runAction={runAction} />}
        {page === "browser" && <BrowserPage runAction={runAction} />}
        {page === "history" && <HistoryPage conversations={conversations} select={selectConversation} search={historySearch} setSearch={setHistorySearch} refresh={loadConversations} setToast={setToast} />}
        {page === "settings" && <SettingsPage theme={theme} setTheme={setTheme} status={status} setToast={setToast} logout={logout} />}
      </div>
    </main>
    {toast && <button className="toast" onClick={() => setToast("")}>{toast}</button>}
  </div>;
}

function AuthScreen({ onAuthenticated, theme, setTheme, notice = "" }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState("sign_in");
  const [message, setMessage] = useState(notice);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const submitInFlight = useRef(false);
  const submit = async (event) => {
    event.preventDefault();
    if (submitInFlight.current) return;
    submitInFlight.current = true;
    setMessage("");
    setLoading(true);
    try {
      const result = await request(mode === "sign_in" ? "/auth/login" : "/auth/register", {
        method: "POST",
        // Match the backend's normalized-email lookup and avoid whitespace
        // accidentally turning a valid account into a failed login.
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!result?.user) throw new Error("The server did not return an account. Please try again.");
      const session = await request("/auth/session");
      if (!session?.user || session.user.id !== result.user.id) {
        throw new Error("Your login session was not saved. Please sign in again.");
      }
      onAuthenticated(session.user);
    } catch (error) {
      setMessage(error.status === 401
        ? "Email or password is incorrect. Check your details or create an account."
        : error.message || "Unable to sign in right now. Please try again.");
    } finally {
      submitInFlight.current = false;
      setLoading(false);
    }
  };
  const toggleMode = () => { setMode((current) => current === "sign_in" ? "sign_up" : "sign_in"); setMessage(""); };
  return <main className={`auth-page ${theme}`}>
    <div className="auth-ambient" aria-hidden="true"><i className="auth-planet" /><i className="auth-ribbon ribbon-one" /><i className="auth-ribbon ribbon-two" /><i className="auth-stars" /></div>
    <header className="auth-nav">
      <a className="auth-brand" href="#welcome" aria-label="NEXORA AI home"><img className="auth-brand-image" src={theme === "light" ? "/f-logo.png" : "/d-logo.png"} alt="" /><span>NEXORA AI</span></a>
      <nav className="auth-links" aria-label="Product"><a href="#features">Features</a><a href="#solutions">Solutions</a><a href="#architecture">Architecture</a><a href="#voice-workflow">Voice Workflow</a><a href="#pricing">Pricing</a><a href="#about">About</a></nav>
      <button className="auth-theme-toggle" type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>{theme === "dark" ? <Moon size={19} /> : <Sun size={19} />}</button>
    </header>
    <section className="auth-main" id="welcome">
      <div className="auth-hero"><span className="auth-kicker">WELCOME TO</span><h1>NEXORA AI</h1><p>Your intelligent companion for deeper conversations.</p></div>
      <form className="auth-panel" onSubmit={submit} aria-busy={loading}>
        <span className="auth-mobile-brand">NEXORA AI</span>
        <h2>{mode === "sign_in" ? "Welcome back" : "Create your account"}</h2>
        <p className="auth-description">Your public conversations are private to your account.</p>
        <label className="auth-field"><Mail size={19} aria-hidden="true" /><span className="sr-only">Email address</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email address" autoComplete="email" required /></label>
        <label className="auth-field"><LockKeyhole size={19} aria-hidden="true" /><span className="sr-only">Password</span><input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" autoComplete={mode === "sign_in" ? "current-password" : "new-password"} minLength={8} required /><button className="password-toggle" type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={19} /> : <Eye size={19} />}</button></label>
        <button className="auth-submit" type="submit" disabled={loading}>{loading ? <><span className="auth-spinner" />{mode === "sign_in" ? "Signing in…" : "Creating account…"}</> : <>{mode === "sign_in" ? "Sign in" : "Create account"}<ArrowRight size={18} /></>}</button>
        {message && <p className="auth-message" role="alert">{message}</p>}
        <p className="auth-switch">{mode === "sign_in" ? "Need an account?" : "Already have an account?"}<button type="button" onClick={toggleMode}>{mode === "sign_in" ? "Create account" : "Sign in"}</button></p>
      </form>
    </section>
    <section className="auth-benefits" id="benefits" aria-label="NEXORA AI benefits">
      <article><span><ShieldCheck size={22} /></span><div><h3>Private &amp; Secure</h3><p>Your data stays yours</p></div></article>
      <article><span><Zap size={22} /></span><div><h3>AI Powered</h3><p>Smarter conversations</p></div></article>
      <article><span><Layers3 size={22} /></span><div><h3>Built for You</h3><p>Personalized experience</p></div></article>
    </section>
    <section className="auth-info-section" id="features">
      <span className="auth-kicker">CAPABILITIES</span><h2>One assistant, ready for your day.</h2>
      <div className="auth-info-grid">
        <article><ShieldCheck size={20} /><h3>Private conversations</h3><p>Sign in to keep your chat history associated with your account.</p></article>
        <article><Zap size={20} /><h3>AI chat</h3><p>Ask questions and get conversational responses from the configured AI service.</p></article>
        <article><Mic size={20} /><h3>Windows voice control</h3><p>Use the local companion for microphone input, spoken responses, and supported desktop actions.</p></article>
      </div>
    </section>
    <section className="auth-info-section" id="solutions">
      <span className="auth-kicker">HOW IT HELPS</span><h2>From a question to a useful action.</h2>
      <p className="auth-info-lede">Use NEXORA AI for cloud conversations, then switch to the Windows companion for voice interaction or an available local action.</p>
      <div className="auth-info-grid auth-info-grid-two">
        <article><MessageSquare size={20} /><h3>Think things through</h3><p>Explore ideas in text chat and return to saved conversations when you sign in.</p></article>
        <article><AppWindow size={20} /><h3>Control your PC</h3><p>Run supported app, website, and search shortcuts through the local Windows service.</p></article>
      </div>
    </section>
    <section className="auth-info-section auth-diagram-section" id="architecture" aria-labelledby="architecture-title">
      <span className="auth-kicker">PLATFORM OVERVIEW</span><h2 id="architecture-title">NEXORA AI System Architecture</h2>
      <p className="auth-info-lede">Explore how the NEXORA AI frontend, cloud backend, local Windows assistant, AI services, and MongoDB work together.</p>
      <figure className="auth-diagram-frame">
        <a className="auth-diagram-link" href="/architecture%20.png" target="_blank" rel="noopener noreferrer" aria-label="Open the complete NEXORA AI system architecture diagram at full size in a new tab">
          <img className="auth-diagram-image" src="/architecture%20.png" alt="System architecture diagram showing the NEXORA AI React and Vite frontend, local Windows assistant, FastAPI cloud backend, Groq AI service, and MongoDB collections and connections." loading="lazy" />
        </a>
        <figcaption className="auth-diagram-caption"><span>Full architecture diagram · select the image to open it at full size.</span><a href="/architecture%20.png" target="_blank" rel="noopener noreferrer">Open full size <ArrowRight size={14} /></a></figcaption>
      </figure>
    </section>
    <section className="auth-info-section auth-diagram-section" id="voice-workflow" aria-labelledby="voice-workflow-title">
      <span className="auth-kicker">VOICE EXPERIENCE</span><h2 id="voice-workflow-title">How the NEXORA AI Voice Assistant Works</h2>
      <p className="auth-info-lede">Follow the complete voice interaction flow, from microphone capture and speech recognition to AI responses, local actions, and speech output.</p>
      <figure className="auth-diagram-frame">
        <a className="auth-diagram-link" href="/micrphone.png" target="_blank" rel="noopener noreferrer" aria-label="Open the complete NEXORA AI microphone workflow diagram at full size in a new tab">
          <img className="auth-diagram-image" src="/micrphone.png" alt="Microphone workflow sequence showing the user, React frontend, local Python service, Windows microphone, speech recognition, Groq AI, and text-to-speech, including conversational and supported-command paths." loading="lazy" />
        </a>
        <figcaption className="auth-diagram-caption"><span>Microphone-to-response workflow · select the image to open it at full size.</span><a href="/micrphone.png" target="_blank" rel="noopener noreferrer">Open full size <ArrowRight size={14} /></a></figcaption>
      </figure>
    </section>
    <section className="auth-info-section auth-pricing" id="pricing">
      <span className="auth-kicker">PRICING</span><h2>Demo access</h2>
      <p className="auth-info-lede">The project does not define paid plans or checkout. Create an account to access the current public demo; availability depends on the configured services.</p>
      <a className="auth-inline-cta" href="#welcome">Continue to sign in <ArrowRight size={16} /></a>
    </section>
    <section className="auth-info-section auth-about" id="about">
      <div className="about-hero">
        <div><span className="auth-kicker">ABOUT NEXORA AI</span><h2>AI Conversations That Connect to Your World.</h2>
          <p className="about-intro">NEXORA AI is built to make useful AI feel close at hand: a clear place to ask questions, keep track of conversations, and connect supported assistant features to everyday work.</p>
          <p className="auth-info-lede">The public web experience provides account-based text chat. A companion service on Windows adds voice input, spoken responses, and a defined set of local desktop actions.</p>
        </div>
        <div className="about-orbit-card" aria-hidden="true"><div className="about-orbit-core"><Sparkles size={30} /></div><i className="about-orbit orbit-a" /><i className="about-orbit orbit-b" /><span>CONVERSATION<br />MEETS ACTION</span></div>
      </div>
      <div className="about-purpose">
        <div><span className="auth-kicker">WHAT IS NEXORA AI?</span><h3>A practical assistant across two connected experiences.</h3></div>
        <p>NEXORA AI pairs a browser-based chat and account history with an optional Windows companion for features that need access to the computer. Sign in to use the public chat; run the local service when you want supported voice or desktop workflows. Each part has a clear role, so the experience stays straightforward.</p>
      </div>
      <div className="about-principles">
        <div className="about-section-heading"><span className="auth-kicker">CORE PRINCIPLES</span><h3>Designed around the way you work.</h3></div>
        <div className="auth-info-grid about-card-grid">
          <article><MessageSquare size={20} /><h3>Natural conversations</h3><p>A focused chat interface makes it easy to ask a question and continue the conversation.</p></article>
          <article><ShieldCheck size={20} /><h3>Account-based access</h3><p>Sign-in keeps conversations and history associated with the user account.</p></article>
          <article><Mic size={20} /><h3>Voice when it helps</h3><p>The Windows companion supports microphone input and spoken responses where available.</p></article>
          <article><AppWindow size={20} /><h3>Local actions, by design</h3><p>Desktop control runs through the Windows service and supports an allowlisted set of actions.</p></article>
        </div>
      </div>
      <div className="about-how">
        <div className="about-section-heading"><span className="auth-kicker">HOW IT WORKS</span><h3>Three simple steps.</h3></div>
        <div className="about-steps">
          <article><span>01</span><div><h4>Connect</h4><p>Sign in or create an account to open the public chat experience.</p></div></article>
          <article><span>02</span><div><h4>Converse</h4><p>Chat with the configured AI service and return to your saved conversations.</p></div></article>
          <article><span>03</span><div><h4>Continue locally</h4><p>When needed, start the Windows companion for supported voice and desktop features.</p></div></article>
        </div>
      </div>
      <div className="about-why">
        <span className="auth-kicker">WHY NEXORA AI</span><h3>Useful capability, with a clear path through it.</h3>
        <p>We bring the assistant’s available features into one considered experience: a clean interface for conversation, account-based continuity, and a local companion for supported computer interactions. The aim is to make each capability easy to understand and comfortable to use.</p>
      </div>
      <div className="about-cta">
        <div><span className="auth-kicker">YOUR NEXT CONVERSATION</span><h3>Ready to start a conversation?</h3><p>Sign in or create an account to try the current NEXORA AI demo.</p></div>
        <a className="auth-inline-cta" href="#welcome">Go to sign in <ArrowRight size={16} /></a>
      </div>
    </section>
  </main>;
}

function Sidebar({ theme, page, nav, conversations, search, setSearch, selected, select, newChat, mobileOpen, status, onLogout, loggingOut, speechEnabled, toggleSpeech }) {
  const brandImage = theme === "light" ? "/lightmode.png" : "/darkmode.png";
  return <aside className={`sidebar ${mobileOpen ? "open" : ""}`}><div className="brand"><img src={brandImage} alt="NEXORA AI — Your Intelligent Companion" className="brand-art" /></div>
    <div className="nav">{navItems.map(([id, label, Icon]) => <button key={id} className={page === id ? "active" : ""} onClick={() => nav(id)}><Icon size={17} />{label}</button>)}</div>
    <div className="history-head"><span>CHAT HISTORY</span><button className="icon-button" onClick={newChat} title="New chat"><Plus size={16} /></button></div>
    <button className="new-chat" onClick={newChat}><Plus size={16} /> New Chat</button>
    <div className="history-search"><Search size={14} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search chats" /></div>
    <div className="history-list">{conversations.length ? conversations.slice(0, 8).map((conversation) => <button className={`history-item ${selected === conversation.id ? "selected" : ""}`} onClick={() => select(conversation.id)} key={conversation.id}><MessageSquare size={14} /><span>{conversation.title}</span></button>) : <p className="empty-history">Your conversations will appear here.</p>}</div>
    <div className="system-card"><div className="system-title"><span className={`status-dot ${voiceInteractionState(status)}`} /> System status</div><StatusRow label="NEXORA" value={status.status === "error" ? "Attention" : "Online"} /><StatusRow label="Local control" value={localServiceLabel(status.local_service)} /><StatusRow label="Microphone" value={microphoneLabel(status.microphone)} /><StatusRow label="Groq AI" value={status.groq || "Unknown"} /><StatusRow label="Speech engine" value={status.speech_engine || "Unknown"} /><button className="speech-toggle" type="button" onClick={toggleSpeech}>{speechEnabled ? "Disable spoken replies" : "Enable spoken replies"}</button></div>
    <button className="sidebar-logout" type="button" onClick={onLogout} disabled={loggingOut} aria-busy={loggingOut}><LogOut size={17} />{loggingOut ? "Signing out..." : "Logout"}</button>
  </aside>;
}
function StatusRow({ label, value }) { return <div className="status-row"><span>{label}</span><b>{value}</b></div>; }
function voiceCopy(status) {
  const currentState = voiceInteractionState(status);
  return {
    disconnected: ["Windows assistant is offline.", "Run run_local.bat to start the local microphone service."],
    connecting: ["Connecting to the local assistant...", "Please wait while the Windows service becomes ready."],
    ready: ["Click to Start Listening.", "Spacebar: Start / Stop Listening"],
    idle: ["Click to Start Listening.", "Spacebar: Start / Stop Listening"],
    starting: ["Starting microphone...", "Please wait..."],
    listening: ["Listening... Speak now...", "Click Stop Listening or press the spacebar"],
    processing: ["Processing your request...", "Thinking about your request..."],
    speaking: ["NEXORA AI is responding...", "NEXORA AI is speaking..."],
    stopping: ["Stopping listening...", "Releasing the microphone..."],
    error: [status.message || "Microphone unavailable", "Try again when the microphone is ready"],
  }[currentState] || ["Click to Start Listening.", "Spacebar: Start / Stop Listening"];
}
function Orb({ status = "ready", onClick }) { return <div className={`orb-wrap ${status}`}><div className="wave wave-left" /><button className="orb" onClick={onClick} aria-label={status === "listening" ? "Stop listening" : "Start listening"}><Mic size={42} /></button><div className="wave wave-right" /></div>; }
function HomePage({ status, activity, runAction, toggleVoice, nav }) { const state = voiceInteractionState(status); const active = state === "listening"; const [title, subtitle] = voiceCopy(status); return <><PageIntro eyebrow="COMMAND CENTER" title="Good to see you, Commander." description="Your intelligent desktop companion is ready for your next instruction." /><section className={`hero-panel voice-state-${state}`}><Orb status={state} onClick={toggleVoice} /><h2>{title}</h2><p>{subtitle}</p>{state === "processing" && <span className="loading-indicator" aria-label="Processing" />}{active && <button className="stop-button" onClick={toggleVoice}>Stop Listening</button>}</section><section className="section-heading"><div><span className="eyebrow">SHORTCUTS</span><h3>Quick Actions</h3></div><button className="text-button" onClick={() => nav("apps")}>View all <ArrowLeft size={14} className="flip" /></button></section><ShortcutGrid runAction={runAction} /><ActivityList activity={activity} /></>; }
function PageIntro({ eyebrow, title, description }) { return <div className="page-intro"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>; }
function ShortcutGrid({ runAction }) { return <div className="shortcut-grid">{shortcuts.map(([label, command, Icon]) => <button className="shortcut" key={label} onClick={() => runAction(command)}><span className="shortcut-icon"><Icon size={19} /></span><span>{label}</span><Zap size={13} className="shortcut-arrow" /></button>)}</div>; }
function ActivityList({ activity }) { return <section className="activity-panel"><div className="section-heading"><div><span className="eyebrow">LIVE FEED</span><h3>Recent Activity</h3></div><Activity size={18} /></div>{activity.length ? activity.slice(0, 5).map((item, index) => <div className="activity-row" key={`${item.timestamp}-${index}`}><span className="activity-icon"><Activity size={14} /></span><span>{item.message || item.type.replaceAll("_", " ")}</span><time>{new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>) : <p className="muted">Actions performed by NEXORA AI will appear here.</p>}</section>; }

const markdownComponents = {
  a: ({ href, children, ...props }) => <a {...props} href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
  table: ({ children, ...props }) => <div className="markdown-table-wrap"><table {...props}>{children}</table></div>,
  img: () => null,
};

function normalizeCompactMarkdown(content) {
  if (typeof content !== "string") return "";
  return content.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~)/g).map((segment, segmentIndex) => {
    if (segmentIndex % 2) return segment;
    return segment.split(/(`+[^`\n]*`+)/g).map((part, partIndex) => {
      if (partIndex % 2) return part;
      return part
        .replace(/([^\n])\s+(?=#{1,6}\s)/g, "$1\n\n")
        .replace(/([^\n])\s+(?=(?:[-+*]|\d+[.)])\s+\S)/g, "$1\n");
    }).join("");
  }).join("");
}

function ChatPage({ messages, send, status, toggleVoice, speak }) {
  const [input, setInput] = useState("");
  return <><PageIntro eyebrow="CONVERSATION" title="Chat with NEXORA AI" description="Questions use cloud AI and MongoDB history. Voice and computer actions run on this Windows PC." /><section className="chat-panel"><div className="messages">{messages.length ? messages.map((message, index) => <div className={`message ${message.role}`} key={message.id || index}><span className="message-avatar">{message.role === "user" ? "YOU" : "N"}</span><div className="message-content"><small>{message.role === "user" ? "You" : "NEXORA AI"}</small>{message.role === "user" ? <p className="message-text">{message.content}</p> : <><div className="message-body markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{normalizeCompactMarkdown(message.content)}</ReactMarkdown></div><button className="speak-message" type="button" onClick={() => speak(message.content)} title={speechEnabled ? "Play response" : "Enable speech in the system status panel first"} aria-label="Play response">Speaker</button></>}{message.created_at && <time className="message-time" dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>}</div></div>) : <div className="chat-empty"><Bot size={36} /><h3>Start a conversation</h3><p>Your conversations are saved to your private account.</p></div>}</div><form className="chat-input" onSubmit={(event) => { event.preventDefault(); const message = input.trim(); if (!message) return; send(message); setInput(""); }}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask NEXORA AI anything..." /><button className="icon-button" type="button" onClick={toggleVoice} title={status.status === "listening" ? "Stop microphone" : "Start microphone"} aria-label={status.status === "listening" ? "Stop microphone" : "Start microphone"}><Mic size={18} /></button><button className="primary-button" type="submit" aria-label="Send message"><Send size={16} /></button></form></section></>;
}
function VoicePage({ status, toggleVoice }) { const state = voiceInteractionState(status); const active = state === "listening"; const [title, subtitle] = voiceCopy(status); return <><PageIntro eyebrow="VOICE CONTROL" title="Speak naturally." description="The Python engine owns microphone capture, transcription, command execution, and speech synthesis." /><section className={`voice-panel voice-state-${state}`}><Orb status={state} onClick={toggleVoice} /><h2>{title}</h2><p className="muted">{subtitle}</p>{state === "processing" && <span className="loading-indicator" aria-label="Processing" />}{active && <button className="stop-button" onClick={toggleVoice}>Stop Listening</button>}<div className="transcript"><span>Latest transcript</span><strong>{status.last_transcript || "Waiting for a voice command..."}</strong></div></section></>; }
function AppsPage({ runAction }) { return <><PageIntro eyebrow="APPLICATIONS" title="Desktop control" description="Only allowlisted Windows applications can be launched." /><ShortcutGrid runAction={runAction} /></>; }
function BrowserPage({ runAction }) { const [query, setQuery] = useState(""); return <><PageIntro eyebrow="BROWSER CONTROL" title="Navigate the web." description="Search and navigation actions are routed through the safe Python browser layer." /><div className="browser-tools"><form onSubmit={(event) => { event.preventDefault(); runAction(`Search Google for ${query}`); }}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Google..." /><button className="primary-button">Search</button></form><form onSubmit={(event) => { event.preventDefault(); runAction(`Search YouTube for ${query}`); }}><Youtube size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search YouTube..." /><button className="primary-button">Search</button></form></div><ShortcutGrid runAction={runAction} /></>; }
function HistoryPage({ conversations, select, search, setSearch, refresh, setToast }) { const remove = async (id) => { if (!window.confirm("Delete this conversation?")) return; try { await request(`/conversations/${id}`, { method: "DELETE" }); refresh(); } catch (error) { setToast(error.message); } }; return <><PageIntro eyebrow="ARCHIVE" title="Chat History" description="Your conversations are stored locally and never sent to a remote history service." /><div className="history-page-toolbar"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search titles and messages" /></div><div className="history-cards">{conversations.map((conversation) => <article className="history-card" key={conversation.id}><MessageSquare size={18} /><div onClick={() => select(conversation.id)}><h3>{conversation.title}</h3><p>{new Date(conversation.updated_at).toLocaleString()}</p></div><button className="icon-button danger" onClick={() => remove(conversation.id)}><Trash2 size={16} /></button></article>)}</div></>; }
function SettingsPage({ theme, setTheme, status, setToast, logout }) { const clear = async () => { if (!window.confirm("Clear all conversations?")) return; try { await request("/conversations", { method: "DELETE" }); setToast("Conversation history cleared."); } catch (error) { setToast(error.message); } }; return <><PageIntro eyebrow="SYSTEM" title="Settings" description="Tune the dashboard without exposing credentials." /><div className="settings-grid"><article className="setting-card"><Palette size={20} /><h3>Appearance</h3><p>Choose the interface theme.</p><button className="setting-choice" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Moon size={16} /> : <Sun size={16} />} {theme === "dark" ? "Dark mode" : "Light mode"}</button></article><article className="setting-card"><Mic size={20} /><h3>Audio services</h3><StatusRow label="Microphone" value={status.microphone} /><StatusRow label="Speech engine" value={status.speech_engine} /><p className="muted">Voice capture remains owned by the Python assistant.</p></article><article className="setting-card"><History size={20} /><h3>Chat history</h3><p>Delete conversations and their messages.</p><button className="danger-button" onClick={clear}><Trash2 size={15} /> Clear all history</button><button className="text-button" onClick={logout}>Sign out</button></article></div></>; }

createRoot(document.getElementById("root")).render(<App />);
