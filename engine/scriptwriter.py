"""AI script writer: a topic + the client's brand voice -> a 30-60 s reel script with a 2-second hook.

Uses ChatGPT (OpenAI, OPENAI_MODEL) or Claude (Anthropic, CLAUDE_MODEL), whichever has a key in .env
(SCRIPT_WRITER=openai or claude picks one when both do). Both use structured output, so the result
always has the same fields. For Claude, `fallbacks: "default"` lets the API retry a declined request
on another Claude model automatically.
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


def writer():
    """Which AI writes scripts: "openai", "claude", or None when no key is set."""
    choice = config.env("SCRIPT_WRITER", "auto").lower()
    keys = {"openai": config.env("OPENAI_API_KEY"), "claude": config.env("ANTHROPIC_API_KEY")}
    if choice in keys:
        return choice if keys[choice] else None
    return next((name for name, key in keys.items() if key), None)


def write_script(topic, brand, notes=""):
    prompt = f"{brand_brief(brand)}\n\nTopic / hook idea for this reel:\n{topic}"
    if notes:
        prompt += f"\n\nFeedback on the previous version (apply it):\n{notes}"
    which = writer()
    if which == "openai":
        out = _write_openai(prompt)
    elif which == "claude":
        out = _write_claude(prompt)
    else:
        raise NeedsSetup("No AI key in .env, so the AI can't write scripts yet. Paste an OpenAI (ChatGPT) or "
                         "Anthropic (Claude) key into .env, or type the script into the sheet yourself.")
    out.hashtags = [h if h.startswith("#") else f"#{h}" for h in (t.strip().replace(" ", "") for t in out.hashtags) if h]
    return out


def _write_openai(prompt):
    import openai

    client = openai.OpenAI(api_key=config.env("OPENAI_API_KEY"))
    resp = client.responses.parse(model=config.env("OPENAI_MODEL", "gpt-5.5"), instructions=SYSTEM, input=prompt,
                                  text_format=ReelScript, max_output_tokens=16000)
    for item in resp.output:
        for part in getattr(item, "content", None) or []:
            if part.type == "refusal":
                raise RuntimeError("ChatGPT declined this topic. Rephrase the topic and set the row back to Idea.")
    if resp.output_parsed is None:
        raise RuntimeError(f"Script writer returned no usable script (status={resp.status}).")
    return resp.output_parsed


def _write_claude(prompt):
    import anthropic

    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"))
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
    return resp.parsed_output


def word_count_seconds(script, words_per_second=2.6):
    return len(script.split()) / words_per_second
