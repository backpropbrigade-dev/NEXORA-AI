const targets = "youtube|you tube|google chrome|chrome|notepad|calculator|paint|file explorer|command prompt|google|gmail|github|chatgpt|wikipedia|stack overflow|geeksforgeeks|python documentation|(?:https?:\\/\\/)?[a-z0-9.-]+\\.[a-z]{2,}(?:\\/\\S*)?";
const openPattern = new RegExp(
  `^(?:please\\s+)?(?:open|launch|start|go\\s+to|navigate\\s+to)\\s+(?:the\\s+)?(${targets})(?:\\s+for\\s+me)?(?:\\s+and\\s+(?:(?:tell\\s+me|explain)\\s+)?(?:(?:what\\s+is|what's)\\s+(.+)|what\\s+(.+?)\\s+is))?$`,
  "i",
);

export function localActionRequest(text) {
  const value = text.trim().replace(/[.!?]+$/, "");
  if (/^(?:what time is it|tell me the time|time)$/i.test(value)) return { command: value, question: null };
  if (/^(?:what is the date|tell me today's date|date)$/i.test(value)) return { command: value, question: null };
  const open = value.match(openPattern);
  if (open) {
    const subject = open[2] || open[3];
    return { command: value, question: subject ? `What is ${subject.trim()}?` : null };
  }
  if (/^(?:please\s+)?search\s+(?:google|youtube)(?:\s+for)?\s+.+$/i.test(value)) {
    return { command: value, question: null };
  }
  return null;
}
