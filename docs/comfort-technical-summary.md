# `/comfort` — Technical Summary

## Purpose

`/comfort` (Spanish: `/consolar`) lets a parishioner describe how they're feeling or what they're going through, and returns a Bible verse from a vetted, parish-curated list that speaks to that emotional or situational context along with a brief framing written by an LLM. The feature is explicitly designed as a _bridge to human pastoral care_, not a substitute for it: built-in crisis detection and usage-frequency monitoring exist to route parishioners to a priest or spiritual counselor when the situation calls for human support rather than (or in addition to) a Scripture passage.

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
     "verse_text_es": "Alégrense siempre en el Señor...",
     "emotional_tags": ["joy", "sadness"],
     "situational_tags": ["unemployment"]
   }
   ```

   Relation (whether a tag is being _amplified_ or _soothed_) is not stored per verse. It's derived at runtime from a static positive/negative classification of the tag itself (e.g., `joy` → amplify, `sadness` → soothe), held in a constants module alongside the tag vocabulary.

---

## 2. Runtime flow

### Step 0 — First-use introduction

On the parishioner's first use of `/comfort`, the bot sends a one-time introductory message before waiting for input (`comfort_intro`).

Whether the introduction has been shown is tracked per parishioner. On subsequent invocations, the bot sends a brief prompt instead (`comfort_brief_intro`):

Then proceeds to Step A.

### Step A — Parishioner submits text

The parishioner sends free-text describing how they feel or what they're experiencing.

### Step B — Combined classification (single LLM call)

The parishioner's message may be in any language (`/comfort` → English, `/consolar` → Spanish, per the router's language-forcing convention). One LLM call classifies the submitted text and returns:

- `is_crisis` (boolean) if self-harm, suicidal ideation, sexual abuse or physical violence are described by the user
- One or more emotional tags (inferred from the text)
- Zero or more situational tags

### Step C — Notification deduplication check

Before any notification-triggering logic runs, the bot checks whether a parish notification has already been sent for this parishioner within the past `COMFORT_NOTIFICATION_DEDUP_WINDOW_HOURS` hours (rolling window):

- **No recent notification** → proceed to Step D.
- **Notification already sent within 24 hours** → skip Steps D and E and proceed directly to Step F. No additional notification will be sent for this request.

### Step D — Crisis gate

If `is_crisis` is true:

- The bot does **not** retrieve or send a verse immediately.
- The parishioner is told the situation warrants support from a priest, in pastoral, non-alarming language.
- An urgent notification is sent to the parish for follow-up.
- A single **Continue** button is presented to the parishioner. The flow proceeds to Step F until the button is tapped, using the classification output already obtained in Step B.

Emotional and situational tags are populated regardless of `is_crisis`, for logging purposes (see Section 4), but the retrieval function is never invoked unless the parishioner explicitly continues.

### Step E — Offer pastoral outreach

Runs only if `is_crisis` is false and Step C passed (no notification sent within the dedup window). Using the same classification output from Step B, the bot checks:

- How many passages have been sent to this parishioner in the past rolling **frequency window** (`COMFORT_FREQUENCY_WINDOW_HOURS`)
- Whether **any** of the classified emotional tags are in a curated **high-risk emotional tag** subset (`HIGH_RISK_EMOTIONAL_TAGS`) — a single high-risk tag is sufficient, not all tags need to match

**Escalation path** (passage count strictly greater than `COMFORT_ESCALATION_PASSAGE_THRESHOLD`, **and** at least one high-risk tag):

- The bot sends a message asking the user whether they'd like someone from the parish to reach out (`comfort_escalation_message`) — this is an offer, not an unconditional escalation like Step D's crisis gate.
- Two buttons are presented: **Yes** and **No**.
- **Yes** → a notification is sent to the parish (a similar, but distinct, notification from Step D's crisis alert) and `comfort_last_notification_sent_at` is updated to `now()`. The flow proceeds to Step F using the classification output already obtained in Step B.
- **No** → no notification is sent and the timestamp is not updated (so Step C won't suppress the next notification opportunity for this parishioner). The flow proceeds to Step F using the same classification output.
- In both cases, retrieval proceeds as soon as the button is tapped — this step never gates or delays Step F beyond waiting for that response.

**No escalation** (threshold not met, or the count exceeds it but no high-risk tag is present) → the flow proceeds to Step F directly, with no message or notification.

### Step F — Retrieval

1. The parishioner's raw text is embedded directly (no synthesis step needed on the query side), except when the session language isn't English, in which case the raw text is first translated to English via one LLM call. The verse bank's synthesized descriptions are English-only, so retrieval stays in a single embedding space this way.
2. Qdrant performs a **filtered vector search**: results are ranked by embedding similarity against the verse vectors; the classified emotional/situational tags influence ranking but do not exclude non-matching verses outright. The top \_MAX_K results are fetched in a single query, sorted by descending similarity (covered by an automated regression test against an embedded, in-memory Qdrant instance — see `tests/commands/comfort/test_qdrant_ordering.py`).
3. An index `j` (0-based) tracks the next unchecked result. The passage at position `j` is checked against a similarity threshold (`COMFORT_SIMILARITY_THRESHOLD` — calibrated empirically, see Open Items). Because results are similarity-sorted, checking only position `j` is sufficient — everything after it has equal or lower similarity, so if `j` fails the threshold, nothing later in the batch could pass either.
   - If the passage at `j` is **below** the threshold → no relevant new passage exists in this batch; go to Step G (fallback).
   - If **at or above** the threshold → check it against the parishioner's passage history (passages sent in the last 2 weeks).
     - If **not** recently sent → this is the selected passage; proceed to Step H.
     - If recently sent → increment `j` by 1 (move to the next candidate) and re-check against the threshold, repeating within the batch.
4. If all \_MAX_K results are exhausted without finding a valid new passage, go to Step G (fallback).
5. If a verse is retrieved that shares **no** emotional or situational tags with the parishioner's classified input but is above the threshold, this is logged as a warning (intended as a feedback signal for vocabulary/curation gaps to be addressed by the development team).

### Step G — Fallback

If no new relevant passage is found among the top \_MAX_K results — either every one of them was recently sent, or the candidate at position `j` fell below the similarity threshold — the bot does not force a match or re-send a previously-sent passage. Instead, it presents a random verse tagged with one of `faith`, `hope`, or `love`, alongside a hardcoded encouraging message `comfort_fallback_message` (not an LLM framing).

This fallback verse is **not** filtered against the parishioner's 2-week sent-passage history — deliberately, to keep the fallback simple. Repeats are acceptable specifically on this path: reaching Step G already means no relevant match was found for what the parishioner expressed, so this is a signal of a gap in the verse bank's tag vocabulary/curation, not a normal retrieval outcome subject to the same repeat-avoidance guarantee as Step F.

### Step H — Framing

An LLM writes a reflection of no more than 3 sentences to accompany the selected passage — a constraint given explicitly in the LLM prompt, not left to the model's default behavior. This framing is **skipped entirely on the Step G fallback path**. There's no real semantic match to frame so the hardcoded message `comfort_fallback_message` is used instead.

### Step I — Reply

- If the passage was retrieved via Step F (a genuine relevant match): reply with the passage and its LLM framing.
- If the passage came from the Step G fallback (random `faith`/`hope`/`love` verse): reply with the passage and the hardcoded encouraging message.
- The reply carries two buttons: **View another passage** (Step J) and **Exit**, which ends the flow the same way typing the session's help command would (`/help` or `/ayuda`, matching the session's language). The selected passage is recorded in the parishioner's sent-history only once the reply is confirmed delivered, so a failed send never pollutes the sent history.
- For Spanish sessions, both the verse text (`verse_text_es`) and the reference's book name are localized before being shown or passed to the framing call — e.g. `"1 Thessalonians 4:13-14"` displays as `"1 Tesalonicenses 4:13-14"`. Only the book name is substituted (`commands/comfort/localization.py`) so there's no need to curate a full localized reference per verse.

### Step J — "Another passage"

If the parishioner taps **View another passage**, retrieval restarts directly at Step F: there is no new text to classify, and Steps C/D/E (notification dedup, crisis gate, escalation offer) are skipped entirely rather than re-evaluated. The parishioner already passed through gating once for their original input message. The original classified input and raw text (already held in flow state) are reused for retrieval.

### Step K — History expiry

Passages are removed from a parishioner's sent-history after 2 weeks, which is what allows a previously-sent passage to become eligible again.

---

## 3. Data model summary

**Qdrant point (per verse):**
| Field | Type | Embedded or Payload |
|---|---|---|
| Vector | embedding | Vector (synthesized from emotional tags, situational tags, and example user phrasings — not stored as payload) |
| `reference` | string | Payload (English; canonical key used for Qdrant point IDs and sent-history lookups) |
| `verse_text` | string | Payload (English) |
| `verse_text_es` | string | Payload (Spanish, curated) |
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

## 4. Logging (anonymized)

A. **Aggregate stats:** every classified message (crisis or not) is recorded to the `comfort_aggregate_stats` table as `(is_crisis, emotional_tags, situational_tags, time_bucket)`, with `time_bucket` being one of `dawn`, `morning`, `afternoon`, `evening`, `night` (per the parish's local time, `LOCAL_TIMEZONE`). No parishioner identifier or precise timestamp are included so a row can never be correlated back to a specific request via server/webhook access logs. Recording is best-effort and happens once per successful `classify()` call i.e. not repeated on "View another passage". The goal of this data is to: 1- understand what emotional language tends to co-occur with crisis flags, 2- identify emotional and situational vocabulary gaps and 3- recognize usage patterns for parish staffing purposes. No dedicated reporting tool exists yet (TODO); see `DEVELOPMENT.md`'s for an example `psql` query.

B. **Performance tracing:** The `/comfort` pipeline can optionally be traced via [Langfuse](https://langfuse.com/docs) for latency/bottleneck and cost analysis. Classification, translation, embedding, and framing calls go through Langfuse's official OpenAI SDK integration (`langfuse.openai.AsyncOpenAI`), which auto-captures model name, token usage, and cost. The Qdrant lookups and the overall retrieval outcome are traced manually via `commands/comfort/tracing.py`'s `traced()` helper. The parishioner's message text, the classification tags, `telegram_user_id`, and `session_id` are deliberately never traced so there's no path by which a Langfuse trace could reconstruct what a parishioner wrote or who they are.

---

## 5. Key safety properties (for test coverage)

1. **Crisis classification produces usable data even when gating retrieval.** A separate test asserts that crisis-flagged messages still produce populated, sensible tags (for the aggregate log), distinct from the control-flow test above.
2. **Aggregate logging contains no identifiers.** Enforced structurally, not just by convention. Tests assert on the actual table schema (exactly `id`, `is_crisis`, `emotional_tags`, `situational_tags`, `time_bucket` — no timestamp, no identifier), so a future column addition can't silently introduce a timestamp or identifier without the test catching it.

---

## 6. Open Items (TBD)

1. **Similarity threshold value** (Step F.3) — set to `0.2` (`COMFORT_SIMILARITY_THRESHOLD`), chosen empirically: real queries against the curated verse bank score genuine matches around 0.28–0.36 and a clearly unrelated query around 0.06, so `0.2` sits safely between them. Still configurable and worth revisiting once there's real usage data.
2. **Tag/Vocabulary Maintenance** (Step F.5)
3. **Tag/Vocabulary Extension** (Step G)
4. **Identifying gaps for emotions/situations experienced by users: an `other_tags` free-text field approach on the classifier's output** — considered as a more direct way to surface vocabulary/curation gaps than the Step F.5 tag-mismatch warning alone, but deliberately not built. The classifier's output is currently restricted to a fixed enum vocabulary as a safety boundary, not just a data-quality choice. `_parse_tags` silently drops anything outside it, so no untrusted, arbitrary LLM-generated text ever propagates downstream. A free-text field describing "what the parishioner is going through" carries a materially higher risk of capturing identifying or sensitive details verbatim than a closed-vocabulary tag ever could, which conflicts with `/comfort`'s own stated privacy promise in the intro message. If a stronger gap-finding signal is wanted later, it should start with defining an owner/review cadence for the existing Step F.5 warning log, and if that's still insufficient, prefer a closed-vocabulary "candidate tag" suggestion over open text — not something to build without a deliberate privacy decision.
