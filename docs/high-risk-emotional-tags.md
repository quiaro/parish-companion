# `/comfort` — High-Risk Emotional Tag Subset

## Purpose

This is the curated subset of the negative emotional tag vocabulary that triggers the **pastoral outreach offer** (Step E of the runtime flow): when a parishioner's classified emotional tag falls within this set _and_ their passage-request frequency in the past rolling 24 hours exceeds a threshold, the bot asks — via Yes/No buttons — whether they'd like someone from the parish to reach out. It's an offer the parishioner can decline, not an unconditional escalation.

## Scope — what this is, and what it is not

**This subset is not a crisis-detection mechanism.** Crisis and real-threat detection (self-harm, suicidal ideation, sexual abuse, physical violence) is handled entirely by the dedicated classifier in Step B, which evaluates the actual content and context of each message and — independent of any emotional tag — triggers an immediate urgent notification. A single message tagged with any emotion in this subset — including just once — does **not** indicate crisis and should never be treated as one.

This subset exists solely to answer a narrower question: _which emotional states, when expressed repeatedly within a short window, warrant offering a human check-in even though no individual message crossed the crisis threshold?_ Frequency of an emotional tag is a weak, indirect signal on its own. It should never be used as a substitute for, or a proxy for, the Step B crisis classifier, and should not be extended to serve that purpose in the future without a separate, deliberate design decision.

## The subset

| Tag            | Why included                                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `despair`      | Closest in spirit to crisis-adjacent language without crossing the crisis threshold; deepest end of hopelessness.        |
| `hopelessness` | Among the most consistently research-correlated emotional states with self-harm risk.                                    |
| `loneliness`   | Social disconnection is a well-established risk correlate; repeated expression in a short window is a meaningful signal. |
| `helplessness` | Closely related to "entrapment" / no-way-out framing associated with elevated risk.                                      |
| `rage`         | Associated with interpersonal-conflict and violence-adjacent situations, particularly when sustained.                    |

## Explicitly excluded (for now)

Tags such as `grief`, `heartbreak`, `anxiety`, `dread`, `overwhelm`, and `exhaustion` were considered but left out of the initial set. Repeated use of these tags is plausibly _normal_ behavior for the feature (e.g., sustained grief in the days after a loss, or anxiety-driven repeated use during a hard week) rather than a signal of escalation. Starting narrower and widening this set later — based on real usage patterns or pastoral staff feedback — is preferred over starting broad and risking alert fatigue or a nudge that feels presumptuous rather than caring.

## Maintenance note

This list lives in a constants module (not hardcoded inline) so it can be revised without a code change to the classification or retrieval logic. Any future change to this set should be a deliberate decision, documented with reasoning, the same way the initial set is documented here — not an ad hoc addition during unrelated feature work.
