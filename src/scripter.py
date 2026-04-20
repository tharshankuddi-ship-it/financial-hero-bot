"""
src/scripter.py - Gemini AI Script Writer for The Financial Hero
"""
import os
import logging
import random

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write viral YouTube Shorts scripts for a personal finance channel called The Financial Hero.
Rules:
- Exactly 3 sentences, max 60 words total.
- Open with a shocking money hook.
- End with a powerful truth that makes viewers want to save or share.
- Plain text only, no emojis, no hashtags, no stage directions.
- Write as if speaking directly to one person about their financial future."""

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
    "Most people work 40 years and retire broke, but it does not have to be you. The wealthy do not work for money, they make money work for them through investing. Start today, even with one dollar, because time in the market beats timing the market.",
    "The bank makes money every time you swipe your card, but almost nobody knows how to make the bank work for them. Compound interest is the most powerful force in finance, yet only 10 percent of people use it correctly. Open an index fund today and let time do the work.",
    "Ninety five percent of people will never become wealthy because they trade time for money their entire lives. The wealthy build assets that generate income while they sleep. Your goal is not a higher salary, your goal is income that does not require your time.",
    "Most people think being rich means earning more, but the truth is the wealthy simply spend less than they earn and invest the difference. A person earning 30000 a year who invests consistently will retire wealthier than someone earning 100000 who spends it all. Wealth is a habit, not an income level.",
    "Inflation is silently stealing 7 percent of your savings every single year. The money sitting in your bank account is losing value while you sleep. Move it into assets that grow faster than inflation, or watch your future slowly disappear.",
    "The number one reason people stay poor is they pay everyone else before paying themselves. Wealthy people automate their investments first and live on what is left. Pay yourself first, even if it is just 10 dollars, and your future self will thank you.",
    "Most people spend 40 hours a week making money for someone else and zero hours building wealth for themselves. The rich spend their evenings learning about investing, not watching television. One hour a day of financial education will change the trajectory of your entire life.",
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
