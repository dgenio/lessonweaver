# Voice Slot Repair

## Description
When a user corrects a misheard slot value, repair the specific slot and confirm
the change in one short sentence instead of restarting the booking.

## Use when
- A voice agent mishears a slot (time, date, location, name).
- The user issues a correction such as "No, I said Tuesday, not Thursday".

## Do not use when
- The user is starting a new request rather than correcting a value.
- The misunderstanding spans the whole intent, not a single slot.

## Instructions
- Identify which slot the user corrected and update only that slot.
- Read the corrected value back in one short confirmation sentence.
- Keep the confirmation under a sentence to stay within voice latency budget.

## Anti-patterns
- Re-asking every slot after a single-slot correction.
- Long spoken summaries that make the agent sound robotic.

## Evidence
- trace: trace-voice-slot-001
