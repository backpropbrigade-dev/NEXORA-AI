import test from "node:test";
import assert from "node:assert/strict";
import { localActionRequest } from "../src/localActions.js";

test("routes direct website and application imperatives locally", () => {
  for (const message of ["Open YouTube", "Launch Google", "Go to YouTube", "Start Notepad"]) {
    assert.ok(localActionRequest(message), `${message} should be a local action`);
  }
});

test("keeps questions and how-to requests on cloud chat", () => {
  assert.equal(localActionRequest("How do I open YouTube?"), null);
  assert.equal(localActionRequest("What is machine learning?"), null);
});

test("extracts a question from a mixed local action request", () => {
  assert.deepEqual(localActionRequest("Open YouTube and tell me what YouTube is"), {
    command: "Open YouTube and tell me what YouTube is",
    question: "What is YouTube?",
  });
});

test("routes explicit searches locally but rejects unsupported applications", () => {
  assert.ok(localActionRequest("Search Google for cats"));
  assert.equal(localActionRequest("Open an unlisted application"), null);
});
