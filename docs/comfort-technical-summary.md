# `/comfort` — Technical Summary

## Purpose

`/comfort` (Spanish: `/consolar`) lets a parishioner describe how they're feeling or what they're going through, and returns a Bible verse from a vetted, parish-curated list that speaks to that emotional or situational context — along with a brief framing written by an LLM. The feature is explicitly designed as a _bridge to human pastoral care_, not a substitute for it: built-in crisis detection and usage-frequency monitoring exist to route parishioners to a priest or spiritual counselor when the situation calls for human support rather than (or in addition to) a Scripture passage.

---

## 1. Verse curation and storage (offline, one-time + ongoing maintenance)

1. **Sourcing.** Parish staff gathers inspiring verses/promises into a CSV with columns `verse` (text) and `reference` (book, chapter, verse). This file is version-controlled and checked into the repo — not stored in Google Sheets — so that changes to theologically load-bearing content go through PR review rather than live external edits.

2. **Tagging.** An LLM extends the CSV with metadata per verse:
   - **Emotional tags** — from a fixed, curated vocabulary
   - **Situational tags** — from a fixed, curated vocabulary
   - **Example user phrasings** — sample free-text expressions a parishioner might use that this verse would match

3. **Embedding and storage.** For each verse, one Qdrant point is created:
   - **Vector**: computed from a _synthesized text blob_ — not the raw verse text — combining the verse's emotional tags, situational tags, and example user phrasings. This is what makes semantic retrieval work: a user writing "I don't know what I'm doing with my life" won't resemble "Rejoice in the Lord always" as raw text, but will resemble a synthesized description like "speaks to discouragement and uncertainty about purpose."
   - **Payload** (structured, not embedded): Bible reference, verse text, `emotional_tags` (list of tag strings), `situational_tags` (list of tag strings).

   Example payload:

   ```json
   {
     "reference": "Philippians 4:4",
     "verse_text": "Rejoice in the Lord always...",
     "emotional_tags": ["joy", "sadness"],
     "situational_tags": ["unemployment"]
   }
   ```

   Relation (whether a tag is being _amplified_ or _soothed_) is not stored per verse. It's derived at runtime from a static positive/negative classification of the tag itself (e.g., `joy` → amplify, `sadness` → soothe), held in a constants module alongside the tag vocabulary.

---

## 2. Runtime flow

### Step 0 — First-use introduction

On the parishioner's first use of `/comfort`, the bot sends a one-time introductory message before waiting for input:

> Welcome to /comfort.
>
> Share what's on your heart and the bot will find a Bible verse from our parish's curated list, along with a brief reflection. You can ask for another verse anytime.
>
> We care about your privacy — we don't store any personal or identifiable information, only a history of passages shared to avoid repeating them.
>
> If you are going through something difficult or seek frequent guidance, a priest or staff member may reach out to talk.
>
> Ready when you are.

Whether the introduction has been shown is tracked per parishioner. On subsequent invocations, the bot sends a brief prompt instead:

> Share what's on your heart.

Then proceeds to Step A.

### Step A — Parishioner submits text

The parishioner sends free-text describing how they feel or what they're experiencing.

### Step B — Combined classification (single LLM call)

One LLM call classifies the submitted text and returns:

- `is_crisis` (boolean) if self-harm, suicidal ideation, sexual abuse or physical violence are described by the user
- One or more emotional tags (inferred from the text)
- Zero or more situational tags

This is deliberately **one call, not two**. Crisis detection and emotional/situational classification are coupled in a single structured response so that no separate "classify the emotion" pathway can run independently of the safety check — there is one verdict, and the schema is designed so the safety determination gates everything else.

### Step C — Notification deduplication check

Before any notification-triggering logic runs, the bot checks whether a parish notification has already been sent for this parishioner within the past 24 hours (rolling window):

- **No recent notification** → proceed to Step D.
- **Notification already sent within 24 hours** → skip Steps D and E and proceed directly to Step F. No additional notification will be sent for this request.

### Step D — Crisis gate

If `is_crisis` is true:

- The bot does **not** retrieve or send a verse immediately.
- The parishioner is told the situation warrants support from a priest, in pastoral, non-alarming language.
- An urgent notification is sent to the parish for follow-up.
- A single **Continue** button is presented to the parishioner. If tapped, the flow proceeds to Step F using the classification output already obtained in Step B. If not tapped, no retrieval or framing occurs.

This gate is enforced in control flow, not by relying on empty classification fields — emotional and situational tags are populated regardless of `is_crisis`, for logging purposes (see Section 4), but the retrieval function is never invoked unless the parishioner explicitly continues.

### Step E — Offer pastoral outreach

Runs only if `is_crisis` is false and Step C passed (no notification sent within the dedup window). Otherwise this step is skipped entirely and the flow proceeds directly to Step F. Using the same classification output from Step B, the bot checks:

- How many passages have been sent to this parishioner in the past rolling **frequency window** (configurable, default 24 hours — a separate setting from Step C's dedup window)
- Whether **any** of the classified emotional tags are in a curated **high-risk emotional tag** subset (stored in a constants module) — a single high-risk tag is sufficient, not all tags need to match

**Escalation path** (passage count strictly greater than a configurable threshold, default 10, **and** at least one high-risk tag):

- The bot sends a message acknowledging the parishioner may be going through a difficult time and asks whether they'd like someone from the parish to reach out — this is an offer, not an unconditional escalation like Step D's crisis gate.
- Two buttons are presented: **Yes** and **No**.
- **Yes** → an urgent notification is sent to the parish (a similar, but distinct, notification from Step D's crisis alert) and `comfort_last_notification_sent_at` is updated to `now()`. The flow proceeds to Step F using the classification output already obtained in Step B.
- **No** → no notification is sent and the timestamp is not updated (so Step C won't suppress the next notification opportunity for this parishioner). The flow proceeds to Step F using the same classification output.
- In both cases, retrieval proceeds as soon as the button is tapped — this step never gates or delays Step F beyond waiting for that response.

**No escalation** (threshold not met, or the count exceeds it but no high-risk tag is present) → the flow proceeds to Step F directly, with no message or notification.

### Step F — Retrieval

1. The parishioner's raw text is embedded directly (no synthesis step needed on the query side).
2. Qdrant performs a **filtered vector search**: results are ranked by embedding similarity against the verse vectors; the classified emotional/situational tags influence ranking but do not exclude non-matching verses outright. The top 40 results are fetched in a single query, sorted by descending similarity. Fetching all 40 up front in one call — rather than an initially smaller batch retried with a growing limit — avoids redundant round-trips: Qdrant's query is stateless, so re-querying with a larger limit would just redo the same search and re-return the same leading results instead of resuming from where a smaller query left off.
3. An index `j` (0-based) tracks the next unchecked result. The passage at position `j` is checked against a similarity threshold (`COMFORT_SIMILARITY_THRESHOLD`, default `0.2` — calibrated empirically, see Open Items). Because results are similarity-sorted, checking only position `j` is sufficient — everything after it has equal or lower similarity, so if `j` fails the threshold, nothing later in the batch could pass either.
   - If the passage at `j` is **below** the threshold → no relevant new passage exists in this batch; go to Step G (fallback).
   - If **at or above** the threshold → check it against the parishioner's passage history (passages sent in the last 2 weeks).
     - If **not** recently sent → this is the selected passage; proceed to Step H.
     - If recently sent → increment `j` by 1 (move to the next candidate) and re-check against the threshold, repeating within the batch.
4. If all 40 results are exhausted without finding a valid new passage, go to Step G (fallback).
5. If a verse is retrieved that shares **no** emotional or situational tags with the parishioner's classified input but is above the threshold, this is logged as a warning (intended as a feedback signal for vocabulary/curation gaps to be addressed by the development team).

### Step G — Fallback

If no new relevant passage is found among the top 40 results — either every one of them was recently sent, or the candidate at position `j` fell below the similarity threshold — the bot does not force a match or re-send a previously-sent passage. Instead, it presents a random verse tagged with one of `faith`, `hope`, or `love`, alongside a hardcoded encouraging message (not an LLM framing).

This fallback verse is **not** filtered against the parishioner's 2-week sent-passage history — deliberately, to keep the fallback simple. Repeats are acceptable specifically on this path: reaching Step G already means no relevant match was found for what the parishioner expressed, so this is a signal of a gap in the verse bank's tag vocabulary/curation (see Open Items), not a normal retrieval outcome subject to the same repeat-avoidance guarantee as Step F.

By contrast, a passage retrieved via Step F always respects the 2-week recently-sent exclusion — no repeated passage is ever sent through the normal retrieval path within that window.

### Step H — Framing

An LLM writes a 1–2 sentence framing to accompany the selected passage. **Skipped entirely on the Step G fallback path** — there's no real semantic match to frame, so the hardcoded encouraging message is used instead.

### Step I — Reply

- If the passage was retrieved via Step F (a genuine relevant match): reply with the passage and its LLM framing.
- If the passage came from the Step G fallback (random `faith`/`hope`/`love` verse): reply with the passage and the hardcoded encouraging message — no LLM framing.

### Step J — "Another passage"

If the parishioner asks for another passage, the flow restarts at **Step C** (notification deduplication check), not Step A — there is no new text to classify or crisis-check; the original classified input is reused for retrieval.

### Step K — History expiry

Passages are removed from a parishioner's sent-history after 2 weeks, which is what allows a previously-sent passage to become eligible again.

---

## 3. Data model summary

**Qdrant point (per verse):**
| Field | Type | Embedded or Payload |
|---|---|---|
| Vector | embedding | Vector (synthesized from emotional tags, situational tags, and example user phrasings — not stored as payload) |
| `reference` | string | Payload |
| `verse_text` | string | Payload |
| `emotional_tags` | list of tag strings | Payload |
| `situational_tags` | list of tag strings | Payload |

**Classification output (per parishioner message):**
| Field | Type |
|---|---|
| `is_crisis` | boolean |
| `emotional_tags` | list of enum |
| `situational_tags` | list of enum |

**Parishioner sent-history (per parishioner):**

- List of `(passage_reference, timestamp)`, pruned after 2 weeks.
- Used for both the 2-week repeat-passage check and the rolling frequency-window check (Step E).
- `last_notification_sent_at` — timestamp of the most recent parish notification sent for this parishioner (from either Step D or Step E), used to enforce the notification deduplication window (Step C). Null if no notification has ever been sent.

---

## 4. Logging

Two structurally separate logging paths, kept decoupled so identifiable data never leaks into aggregate stats:

- **Crisis escalation (identifiable):** the parish notification on crisis detection necessarily includes the parishioner's identity, so a priest can follow up. This is a distinct code path from stats logging below — not a shared "log everything about this event" function.
- **Aggregate stats (anonymized):** every classified message — crisis or not — logs `(is_crisis, emotional_tags, situational_tags, timestamp_rounded_to_time_of_day)`, with `timestamp_rounded_to_time_of_day` bucketed as one of `dawn`, `morning`, `afternoon`, `evening`, `night`. No parishioner identifier is included. Tags are populated regardless of `is_crisis`, since the data has value for understanding what emotional language tends to co-occur with crisis flags — this is safe specifically because the crisis (Step D) is enforced in control flow, not by leaving tags empty.

---

## 5. Key safety properties (for test coverage)

1. **Crisis gate is structural, not data-dependent.** (Step D) A test must assert that when `is_crisis` is true and the parishioner does not tap Continue, the retrieval function is never called — regardless of what `emotional_tags`/`situational_tags` contain.
2. **Crisis classification produces usable data even when gating retrieval.** A separate test asserts that crisis-flagged messages still produce populated, sensible tags (for the aggregate log), distinct from the control-flow test above.
3. **Notification deduplication is enforced before crisis and frequency checks.** (Step C) A test must assert that when `last_notification_sent_at` falls within the dedup window, no notification is sent by Step D (crisis gate) or Step E (pastoral outreach offer) — regardless of `is_crisis` value or passage count.
4. **Aggregate logging contains no identifiers.** The stats log schema should be tested/reviewed to confirm no parishioner ID, chat ID, or other joinable identifier is ever written to it.

---

## 6. Open Items (TBD)

1. **Similarity threshold value** (Step F.3) — set to `0.2` (`COMFORT_SIMILARITY_THRESHOLD`), chosen empirically: real queries against the curated verse bank score genuine matches around 0.28–0.36 and a clearly unrelated query around 0.06, so `0.2` sits safely between them. Still configurable and worth revisiting once there's real usage data.
2. **Tag/Vocabulary Maintenance** (Step F.5)
3. **Tag/Vocabulary Extension** (Step G)
4. **Qdrant result-ordering assumption** — the `j`-pointer optimization (checking only one passage per position rather than the whole batch) assumes results are returned in non-increasing similarity order. Manually verified live against the real Qdrant instance (scores came back strictly descending across several sample queries), but not yet covered by an automated regression test in the suite.
