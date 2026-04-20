"""
src/scripter.py - Script Writer for The Financial Hero
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
    "why most people will never be able to retire",
    "the debt trap that keeps the middle class poor forever",
    "why financial freedom is closer than you think",
    "how to build wealth starting from zero",
    "the truth about passive income nobody tells you",
    "why the stock market is the greatest wealth builder in history",
]

FALLBACK_SCRIPTS = {
    "why most people stay broke their entire life": "Ninety five percent of people will retire with almost nothing, and most of them never saw it coming. They spent their entire lives working hard, paying bills, and hoping things would work out. But hope is not a financial plan. The wealthy do not leave retirement to chance. They automate their investments, live below their means, and let compound interest do the heavy lifting over decades. The difference between retiring rich and retiring broke is not your salary. It is your habits. Start by investing just ten percent of every paycheck into a low cost index fund. Do it automatically so you never have to think about it. Ten years from now, you will thank yourself for starting today instead of waiting for the perfect moment that never comes.",

    "how compound interest makes you rich while you sleep": "The bank makes billions of dollars every single year from people who do not understand how money works. Every time you carry a credit card balance, every time you take out a loan without reading the terms, the bank wins and you lose. But here is what they will never teach you in school. Compound interest works both ways. It can either destroy your finances through debt or build your wealth through investing. The wealthy use compound interest as a weapon. They invest early, they invest consistently, and they let time multiply their money while they sleep. You do not need to be rich to start. You need to start to become rich. Open an index fund today, invest whatever you can afford, and let the most powerful force in finance work for you.",

    "why your salary will never make you rich": "Most people spend forty hours a week making money for someone else and zero hours building wealth for themselves. They trade their time for a paycheck, spend almost all of it, and save whatever is left over. The problem is that nothing is ever left over. Wealthy people flip this system completely. They pay themselves first by automatically investing before they spend a single dollar. Then they build assets that generate income without requiring their time. A rental property, an index fund, a business. These things work while you sleep. Your goal should not be a higher salary. Your goal should be income that does not require your presence. Start small, start now, and focus every spare dollar on buying assets that grow. Your future self is depending on the decisions you make today.",

    "how inflation silently destroys your savings every year": "Inflation is the silent tax that nobody talks about, and it is stealing your future every single day. While your money sits in a bank account earning almost nothing, inflation eats away at its purchasing power year after year. One hundred thousand dollars today will only buy sixty thousand dollars worth of goods in twenty years. The wealthy know this, which is why they never let cash sit idle. They put their money into assets that grow faster than inflation. Stocks, real estate, index funds. These are the tools that protect and multiply wealth over time. You do not have to be rich to use them. You just have to start. Every month you delay is another month inflation wins. Put your money to work today and stop letting time work against you.",

    "the one money habit that separates the wealthy from everyone else": "There is one habit that separates people who build wealth from people who struggle their entire lives, and almost nobody practices it. The wealthy pay themselves first. Before they pay rent, before they buy groceries, before they spend a single dollar on anything, they invest a portion of every paycheck automatically. This one decision, made once and automated, changes everything. Your brain stops seeing that money as available to spend. Wealth begins to build quietly in the background while you live your normal life. Most people do the opposite. They spend first and save whatever is left, which is almost always nothing. Flip the order. Set up an automatic investment of even five percent of your income today. That single habit, practiced consistently for decades, is the true secret behind most wealthy people you will ever meet.",

    "why the rich get richer and the poor get poorer": "The gap between the rich and everyone else is not about luck or intelligence. It is about a system most people never learn. When wealthy people earn money, they buy assets. Assets that grow, produce income, and multiply over time. When most people earn money, they buy liabilities. Cars, gadgets, subscriptions that drain their income every month. Rich people own things that make them richer while they sleep. Most people own things that make someone else richer. The financial system is designed to reward asset owners and punish those who only trade time for money. But here is the truth. Anyone can start buying assets. An index fund is an asset. A rental property is an asset. Even a small business is an asset. Stop buying things that depreciate and start buying things that appreciate. That shift in thinking is where wealth begins.",
}

# Generic fallback for topics without a specific script
GENERIC_FALLBACKS = [
    "Most people will work for forty years and have almost nothing to show for it at the end. Not because they did not earn enough, but because nobody taught them how money actually works. The wealthy follow a simple formula. Earn, invest, repeat. They do not wait until they have more money. They start with whatever they have, no matter how small. A dollar invested today is worth far more than ten dollars invested ten years from now. That is the power of time and compound growth working together. The financial education system has failed most people, but that does not mean you have to stay stuck. Learn how money works. Start investing something, anything, today. The only mistake worse than investing too little is waiting too long to start at all. Your financial future is built one decision at a time.",
    "Seventy percent of Americans live paycheck to paycheck, and it is not because they are lazy or irresponsible. It is because they were never taught the rules of the financial game. The wealthy play by different rules. They understand that building wealth is not about earning more. It is about keeping more and making that money grow. Every dollar you invest has the potential to become two, then four, then eight over time. That is not magic. That is mathematics. The stock market has returned an average of ten percent annually for over a century. If you invested five hundred dollars a month starting today, you would have over a million dollars in thirty years. You do not need to be rich. You need to be consistent. Start today, stay consistent, and let time and compound interest do the rest.",
]

def pick_topic() -> str:
    """Pick a random topic each run for variety across videos."""
    return random.choice(FINANCE_TOPICS)

def generate_script(topic: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        result = _gemini_script(topic, api_key)
        if result:
            return result
    # Use topic-specific fallback if available, otherwise generic
    if topic in FALLBACK_SCRIPTS:
        return FALLBACK_SCRIPTS[topic]
    return random.choice(GENERIC_FALLBACKS)

def _gemini_script(topic: str, api_key: str) -> str:
    try:
        import requests
        prompt = f"{SYSTEM_PROMPT}\n\nWrite a YouTube Shorts script about: {topic}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Gemini failed ({e}), using fallback")
        return None
