"""Precise mode: confirmed sign labels -> English sentence.

GLOSS_TRANSLATOR=literal  joins the labels ("Stomach hurt.")
GLOSS_TRANSLATOR=llm      asks Claude to rephrase them; any failure falls back to literal.
Natural-signing output is never passed through here."""
import logging
import os

import anthropic

log = logging.getLogger(__name__)

SYSTEM = ("You convert a sequence of American Sign Language sign labels, signed by a patient in an "
          "emergency room, into one short first-person English sentence. Use only the meaning of the "
          "given labels: add no symptoms, body parts, times, quantities or other details. Keep the "
          "patient's meaning even if the grammar is simple. If the labels do not form a clear "
          "sentence, return them joined with spaces. Reply with the sentence only.")


def literal(labels):
    words = [label.split(" / ")[0] for label in labels]
    return " ".join(words).capitalize() + ".", "precise-literal"


class LlmTranslator:
    def __init__(self, client=None, model=None, timeout=3.0):
        self.client = (client or anthropic.Anthropic()).with_options(timeout=timeout, max_retries=0)
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

    def __call__(self, labels):
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=60, system=SYSTEM,
                messages=[{"role": "user", "content": "Sign labels: " + " ".join(labels)}],
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            log.warning("Claude credentials rejected, using literal text: %s", e)
            return literal(labels)
        except anthropic.APIStatusError as e:
            log.warning("Claude API error %s, using literal text", e.status_code)
            return literal(labels)
        except anthropic.APIConnectionError as e:
            log.warning("Claude unreachable (%s), using literal text", type(e).__name__)
            return literal(labels)
        except TypeError as e:  # raised when no credentials can be resolved at all
            log.warning("No Claude credentials (%s), using literal text", e)
            return literal(labels)
        text = " ".join(b.text for b in resp.content if b.type == "text").strip().splitlines()
        return (text[0].strip(), "precise-llm") if text and text[0].strip() else literal(labels)


def make_translator(client=None):
    if os.environ.get("GLOSS_TRANSLATOR", "literal").lower() == "llm":
        return LlmTranslator(client=client)
    return literal
