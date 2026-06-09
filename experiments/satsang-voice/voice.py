#!/usr/bin/env python3
"""voice.py — the agent's voice arm: compose a grounded offering, speak it. WHEN is turn-taking's call.

turn-taking.fk (the body) decides WHETHER the agent speaks (named / button / a confident learned moment);
THIS carrier is only the WHAT and the sound: a local LLM (Ollama) composes one short question or insight
grounded in the recent transcript, and `say` (AVSpeechSynthesizer) speaks it as audio — beside the text.
The agent speaks ONLY when invited; on day one that is almost never (turn-taking keeps it silent).

PRIVACY: the offering is composed LOCALLY from the conversation (no cloud model — your dialog never leaves
the machine), and is never written into a committed artifact. When the agent speaks, it is heard in the
room by invitation; that is the whole point of being invited.

Carriers (Mac): ollama (local LLM), say (TTS). Model: COH_LLM_MODEL (default a small fast local model).
"""
import os
import subprocess
import sys

MODEL = os.environ.get("COH_LLM_MODEL", "llama3.2:3b")
VOICE = os.environ.get("COH_TTS_VOICE", "")  # e.g. "Samantha"; empty = system default


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def compose(transcript_tail, model=MODEL):
    """A local LLM composes ONE short question or insight grounded in the recent words. Local only."""
    prompt = (
        "You are a quiet, attentive presence in a group conversation — you speak rarely and only to add "
        "value. Given the recent words below, offer ONE short, genuine question or insight, a single "
        "sentence, no preamble, no quotes.\n\nRecent words:\n"
        + transcript_tail.strip()[-1200:]
        + "\n\nYour one-sentence offering:"
    )
    out = sh(["ollama", "run", model, prompt])
    text = (out.stdout or "").strip()
    # strip any <think> reasoning (reasoning models) and keep the last non-empty line as the offering.
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else ""


def speak(text, out=None):
    """Speak the offering. out=<path> writes audio to a file (verification, doesn't disturb the room);
    out=None speaks through the Mac's voice."""
    if not text:
        return False
    cmd = ["say"]
    if VOICE:
        cmd += ["-v", VOICE]
    if out:
        cmd += ["-o", out]
    cmd.append(text)
    return sh(cmd).returncode == 0


def offer(transcript_tail, out=None, model=MODEL):
    """Compose + speak — the agent's whole voice move, once turn-taking has said it is its turn."""
    text = compose(transcript_tail, model)
    spoke = speak(text, out)
    return text, spoke


if __name__ == "__main__":
    # Verification (does NOT speak into the room — writes the audio to a file). A sample context stands in
    # for a real transcript tail so no private dialog is needed to prove the arm works.
    sample = sys.argv[1] if len(sys.argv) > 1 else (
        "we were saying the engineering AIs will improve themselves, and produce better versions, "
        "and someone wondered where that ends for us"
    )
    print(f"composing with {MODEL} (local) ...")
    text, ok = offer(sample, out="/tmp/coh-voice.aiff")
    print("offering:", repr(text))
    print("spoke to /tmp/coh-voice.aiff:", ok, "(" + (sh(["ls", "-la", "/tmp/coh-voice.aiff"]).stdout.split()[4] if ok else "0") + " bytes)")
