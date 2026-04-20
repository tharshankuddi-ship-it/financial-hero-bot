"""
src/scripter.py - Gemini AI Script Writer for The Financial Hero
"""
import os
import logging
import random

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write viral YouTube Shorts scripts for a personal finance channel called The Financial Hero.
Rules:
- Write exactly 130 to 150 words — this must be spoken aloud in 50 to 60 seconds.
- Structure: Hook (1 shocking sentence) → Problem (2 sentences) → Solution (2-3 sentences) → Call to action (1 sentence).
- Open with a shocking money hook that stops the scroll.
- End with a powerful truth or call to action that makes viewers want to save or share.
- Plain text only, no emojis, no hashtags, no stage directions, no bullet points.
- Write as if speaking directly to one person about their financial future.
- Every sentence must flow naturally when spoken aloud."""

FINANCE_TOPICS = [
    "why most people stay broke their entire life",
    "how compound interest makes you rich while you sleep",
    "the one money habit that separates the wealthy from everyone else",
    "why your salary will never make you rich",
    "the psychological trick banks use to keep you spending",
    "how the wealthy use debt to build wealth while others sink",
    "why saving money is not enough to retire early",
    "the truth about how millionaires actually make their money",
    "why 95 percent of people never invest and stay poor",
    "the simple money rule that could change your life forever",
    "how inflation silently destroys your savings every year",
    "why the rich get richer and the poor get poorer",
    "the investing mistake that costs most people their retirement",
    "how to make your money work for you instead of working for money",
]

FALLBACK_SCRIPTS = [
    "Ninety five percent of people will retire with almost nothing, and most of them never saw it coming. They spent their entire lives working hard, paying bills, and hoping things would work out. But hope is not a financial plan. The wealthy do not leave retirement to chance. They automate their investments, live below their means, and let compound interest do the heavy lifting over decades. The difference between retiring rich and retiring broke is not your salary. It is your habits. Start by investing just ten percent of every paycheck into a low cost index fund. Do it automatically so you never have to think about it. Ten years from now, you will thank yourself for starting today instead of waiting for the perfect moment that never comes.",
    "The bank makes billions of dollars every single year from people who do not understand how money works. Every time you carry a credit card balance, every time you take out a loan without reading the terms, the bank wins and you lose. But here is what they will never teach you in school. Compound interest works both ways. It can either destroy your finances through debt or build your wealth through investing. The wealthy use compound interest as a weapon. They invest early, they invest consistently, and they let time multiply their money while they sleep. You do not need to be rich to start. You need to start to become rich. Open an index fund today, invest whatever you can afford, and let the most powerful force in finance work for you.",
    "Most people spend forty hours a week making money for someone else and zero hours building wealth for themselves. They trade their time for a paycheck, spend almost all of it, and save whatever is left over. The problem is that nothing is ever left over. Wealthy people flip this system completely. They pay themselves first by automatically investing before they spend a single dollar. Then they build assets that generate income without requiring their time. A rental property, an index fund, a business. These things work while you sleep. Your goal should not be a higher salary. Your goal should be income that does not require your presence. Start small, start now, and focus every spare dollar on buying assets that grow. Your future self is depending on the decisions you make today.",
]

def pick_topic() -> str:
    import datetime
    now  = datetime.datetime.now(datetime.timezone.utc)
    slot = now.weekday() * 2 + (0 if now.hour < 12 else 1)
    return FINANCE_TOPICS[slot % len(FINANCE_TOPICS)]

def generate_script(topic: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        result = _gemini_script(topic, api_key)
        if result:
            return result
    return random.choice(FALLBACK_SCRIPTS)

def _gemini_script(topic: str, api_key: str) -> str:
    try:
        import requests
        prompt = f"{SYSTEM_PROMPT}\n\nWrite a YouTube Shorts script about: {topic}"
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Gemini failed ({e}), using fallback")
        return None
