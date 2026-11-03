"""AI script writer: a topic + the client's brand voice -> a 30-60 s reel script with a 2-second hook.

Uses Claude (default model claude-opus-5-5) with structured output, so the result always has the
same fields. If Anthropic's safety system declines a request, `fallbacks: "default"` lets the API
retry it on another Claude model automatically.
"""
from pydantic import BaseModel, Field

from . import config

SYSTEM = """You write short-form vertical video scripts (Instagram Reels, YouTube Shorts) that are spoken
to camera by the creator's AI avatar in their own cloned voice.

Rules for every script:
- The first sentence is the hook. It must stop the scroll within 2 seconds: a bold claim, a surprising
  number, a direct question, or "you're doing X wrong". Maximum 12 words.
- Total spoken length 30-60 seconds: 80-150 words. Short sentences. One idea per reel.
- Write for the ear: plain words, contractions, no lists, no emojis, no hashtags, no stage directions,
  no URLs, no text in brackets. Numbers as people say them.
- End with the creator's call to action, said naturally.
- Never invent statistics, quotes or facts you are not confident about. No medical, legal or financial
  promises. If the topic needs a specific fact you don't know, keep the claim general.
- Match the creator's tone, audience, language and do/don't list exactly."""


class ReelScript(BaseModel):
    title: str = Field(description="internal working title, max 8 words")
    hook: str = Field(description="the first sentence of the script, max 12 words")
    script: str = Field(description="the full spoken script including the hook as its first sentence")
    on_screen_text: str = Field(description="big text overlay for the first 2 seconds, max 6 words, no emoji")
    caption: str = Field(description="post caption: 1-3 short lines that add value and end with a question or CTA")
    hashtags: list[str] = Field(description="5-10 relevant hashtags, each starting with #, mix of broad and niche")
    broll_keywords: list[str] = Field(
        description="3-6 concrete visual search terms for free stock footage that match moments in the script, "
                    "e.g. 'person typing laptop', 'city traffic night'. Nouns and actions only.")


class NeedsSetup(RuntimeError):
    """Something the user has to set up first; the row is left as it is."""


def brand_brief(brand):
    lines = [f"Creator: {brand.get('name')} {brand.get('handle', '')}".strip(),
             f"Language: {brand.get('language', 'English')}",
             f"Niche: {brand.get('niche') or 'general'}",
             f"Audience: {brand.get('audience') or 'general social media viewers'}",
             f"Tone: {brand.get('tone')}",
             f"Call to action: {brand.get('cta')}"]
    if brand.get("do"):
        lines.append("Always: " + "; ".join(brand["do"]))
    if brand.get("dont"):
        lines.append("Never: " + "; ".join(brand["dont"]))
    if brand.get("examples"):
        lines.append("Example scripts in the creator's voice:\n" + "\n---\n".join(brand["examples"]))
    return "\n".join(lines)


def write_script(topic, brand, notes=""):
    import anthropic

    if not config.env("ANTHROPIC_API_KEY"):
        raise NeedsSetup("ANTHROPIC_API_KEY is empty in .env, so the AI can't write scripts yet. "
                           "Paste your key into .env, or type the script into the sheet yourself.")
    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"))
    prompt = f"{brand_brief(brand)}\n\nTopic / hook idea for this reel:\n{topic}"
    if notes:
        prompt += f"\n\nFeedback on the previous version (apply it):\n{notes}"
    request = dict(model=config.env("CLAUDE_MODEL", "claude-opus-5-5"), max_tokens=16000, system=SYSTEM,
                   messages=[{"role": "user", "content": prompt}], output_config={"effort": "medium"},
                   output_format=ReelScript)
    try:
        resp = client.beta.messages.parse(**request, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e).lower():
            raise
        resp = client.beta.messages.parse(**request)  # model/account without server-side fallbacks
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this topic. Rephrase the topic and set the row back to Idea.")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise RuntimeError(f"Script writer returned no usable script (stop_reason={resp.stop_reason}).")
    out = resp.parsed_output
    out.hashtags = [h if h.startswith("#") else f"#{h}" for h in (t.strip().replace(" ", "") for t in out.hashtags) if h]
    return out


def word_count_seconds(script, words_per_second=2.6):
    return len(script.split()) / words_per_second
