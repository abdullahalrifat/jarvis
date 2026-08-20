# Local operations

## Session records

Every local run creates a SQLite record under
`${XDG_STATE_HOME:-~/.local/state}/jarvis/sessions.sqlite3`. Override the path
with `JARVIS_SESSION_DB`.

```bash
jarvis sessions
jarvis session-show SESSION_ID
```

Records contain workspace, task, status, model, result, and trace path. They are
inspectable run records; they do not yet resume the complete transcript into a
new local agent turn.

## Redacted traces

Local runs write JSONL events under the Jarvis state directory. Secret-shaped
fields such as tokens, passwords, cookies, and authorization values are
redacted.

```bash
jarvis trace PATH
```

Redaction is defense in depth. Do not place secrets in prompts, filenames, or
ordinary values and assume every possible secret pattern will be recognized.

## Repository map and attachments

`jarvis repo-map` stores a compact symbol/hash map for context selection.
`jarvis local --file PATH TASK` adds an explicit bounded text attachment.
Attachment content is untrusted. Image, PDF, directory, and glob attachments
are not yet supported by the standalone CLI.

## Undo

`jarvis undo` reverses the last patch recorded by the local Git-backed patch
transaction. Review the diff first. It is not yet a general multi-run undo
ledger and does not reverse arbitrary commands or external effects.

## Evaluations

Evaluation files are JSON arrays, or an object with a `cases` array:

```json
{
  "cases": [
    {
      "name": "cites-source",
      "task": "answer with a source URL",
      "expected_contains": ["https://"],
      "forbidden_contains": ["I cannot"]
    }
  ]
}
```

Run `jarvis eval evals/smoke.json`. The current scorer checks required and
forbidden text. It is useful for deterministic smoke tests, but it is not yet a
full model judge, coding benchmark, latency/cost harness, or A/B optimizer.
