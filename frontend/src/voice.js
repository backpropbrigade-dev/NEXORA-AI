export function speechRecognitionConstructor() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function speechSynthesisSupported() {
  return typeof window !== "undefined"
    && "speechSynthesis" in window
    && typeof window.SpeechSynthesisUtterance === "function";
}

export function speechChunks(text, maxLength = 220) {
  if (typeof text !== "string") return [];
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return [];
  const sentences = normalized.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [normalized];
  const chunks = [];
  let current = "";
  for (const sentence of sentences) {
    const candidate = current ? `${current} ${sentence.trim()}` : sentence.trim();
    if (candidate.length <= maxLength) {
      current = candidate;
      continue;
    }
    if (current) chunks.push(current);
    if (sentence.length <= maxLength) {
      current = sentence.trim();
      continue;
    }
    for (let index = 0; index < sentence.length; index += maxLength) {
      chunks.push(sentence.slice(index, index + maxLength).trim());
    }
    current = "";
  }
  if (current) chunks.push(current);
  return chunks.filter(Boolean);
}

export function cancelSpeech() {
  if (speechSynthesisSupported()) window.speechSynthesis.cancel();
}

export function speakText(text, onState = () => {}) {
  if (!speechSynthesisSupported()) {
    onState("unavailable");
    return false;
  }
  const chunks = speechChunks(text);
  if (!chunks.length) {
    onState("error");
    return false;
  }
  cancelSpeech();
  let index = 0;
  const speakNext = () => {
    if (index >= chunks.length) {
      onState("ready");
      return;
    }
    const utterance = new window.SpeechSynthesisUtterance(chunks[index++]);
    utterance.onstart = () => onState("speaking");
    utterance.onend = speakNext;
    utterance.onerror = () => onState("error");
    window.speechSynthesis.speak(utterance);
  };
  speakNext();
  return true;
}

export function createSpeechRecognition(onResult, onError, onEnd) {
  const Recognition = speechRecognitionConstructor();
  if (!Recognition) return null;
  const recognition = new Recognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = "en-US";
  recognition.onresult = (event) => {
    let transcript = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      transcript += event.results[index][0].transcript;
    }
    onResult(transcript.trim(), Boolean(event.results[event.results.length - 1].isFinal));
  };
  recognition.onerror = (event) => onError(event.error || "unknown");
  recognition.onend = onEnd;
  return recognition;
}
