from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


SYSTEM_PROMPT = """
You are a Kenya Affordable Housing Programme (AHP) and BomaYangu FAQ assistant.
Your role:
- Only answer questions about Kenya's Affordable Housing Programme (AHP), BomaYangu, verified housing news, and buying affordable housing units in Kenya.
- Use simple, clear Kenyan context language.
- If you don't know something, say so clearly—do NOT invent information.
- Direct users to official channels for verification: BomaYangu portal (https://boma-yangu.go.ke), State Department for Housing, or county AHP offices.
- Focus on verified information only—no speculation.
- Be concise, structured, and beginner-friendly.

Strict rules:
- No made-up allocation guarantees, pricing guarantees, or legal certainty.
- No sensitive personal data requests (ID numbers, passwords, bank details).
- Always remind users to confirm latest details on official portals.
- If a question is off-topic (not about Kenyan AHP/BomaYangu/affordable housing), politely say you only help with Kenyan affordable housing topics.
""".strip()


def _get_secret(name: str, default: str = "") -> str:
    value = st.secrets.get(name, default) if hasattr(st, "secrets") else default
    if value:
        return str(value)
    return os.getenv(name, default)


def _chat_completion(
    user_message: str,
    context: dict[str, Any],
    history: list[dict[str, str]],
) -> str:
    # Try Groq first, then fall back to OpenAI/OpenRouter
    groq_api_key = _get_secret("GROQ_API_KEY")
    openai_api_key = _get_secret("OPENAI_API_KEY")
    
    if not groq_api_key and not openai_api_key:
        return (
            "AI guide is not configured yet. Add either `GROQ_API_KEY` (recommended, free) or `OPENAI_API_KEY` in Streamlit secrets. "
            "Get a free Groq key here: https://console.groq.com/keys"
        )

    context_text = (
        f"Dashboard context: listing_count={context.get('listing_count')}, "
        f"median_price_kes={context.get('median_price_kes')}, "
        f"affordable_share_pct={context.get('affordable_share_pct')}."
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context_text}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

    if groq_api_key:
        # Use Groq
        base_url = "https://api.groq.com/openai/v1"
        model = _get_secret("GROQ_MODEL", "llama-3.3-70b-versatile")
        api_key = groq_api_key
    else:
        # Use OpenAI/OpenRouter
        base_url = _get_secret("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        model = _get_secret("OPENAI_MODEL", "openai/gpt-4o-mini")
        api_key = openai_api_key

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.3}

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=45)
        if response.status_code >= 400:
            return (
                f"AI request failed ({response.status_code}). "
                "Check your API key/base URL/model in Streamlit secrets."
            )
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"AI request failed: {exc}"


def render_ai_housing_guide(context: dict[str, Any]) -> None:
    st.header("AI Housing Guide")
    st.caption(
        "Ask simple questions about Kenya affordable housing programs, budgeting, and first-home decisions."
    )

    if "ai_housing_chat" not in st.session_state:
        st.session_state.ai_housing_chat = []

    for msg in st.session_state.ai_housing_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_prompt = st.chat_input("Example: I earn KES 80k/month, how do I start planning for affordable housing?")
    if user_prompt:
        st.session_state.ai_housing_chat.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = _chat_completion(user_prompt, context, st.session_state.ai_housing_chat)
                st.markdown(reply)
        st.session_state.ai_housing_chat.append({"role": "assistant", "content": reply})
