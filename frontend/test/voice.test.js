import test from "node:test";
import assert from "node:assert/strict";
import { speechChunks, speechRecognitionConstructor, speechSynthesisSupported } from "../src/voice.js";

test("splits long spoken responses into bounded chunks", () => {
  const chunks = speechChunks("First sentence. ".repeat(40), 80);
  assert.ok(chunks.length > 1);
  assert.ok(chunks.every((chunk) => chunk.length <= 80));
});

test("detects browser speech APIs without crashing outside a browser", () => {
  assert.equal(speechRecognitionConstructor(), null);
  assert.equal(speechSynthesisSupported(), false);
});
