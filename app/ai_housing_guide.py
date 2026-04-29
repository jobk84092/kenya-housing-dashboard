from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


SYSTEM_PROMPT = """
You are Mtaa Housing Guide, an assistant focused on Kenya affordable housing guidance.
Your role:
- Explain housing choices in simple Kenyan context language.
- Help users understand affordable housing programs, eligibility style checks, and practical next steps.
- Use cautious wording when policies may change and recommend official verification channels.
- Be concise, beginner-friendly, and structured.

Safety and quality rules:
- Do not invent allocation guarantees, pricing guarantees, or legal certainty.
- Clearly label uncertainty.
- Do not ask for sensitive personal data (ID numbers, passwords, full bank details).
- Remind users to confirm latest policy and application rules on official portals and notices.
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
    api_key = _get_secret("OPENAI_API_KEY")
    base_url = _get_secret("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model = _get_secret("OPENAI_MODEL", "openai/gpt-4o-mini")

    if not api_key:
        return (
            "AI guide is not configured yet. Add `OPENAI_API_KEY` in Streamlit secrets. "
            "Optional: `OPENAI_BASE_URL` and `OPENAI_MODEL` if you use a free-tier provider."
        )

    context_text = (
        f"Dashboard context: listing_count={context.get('listing_count')}, "
        f"median_price_kes={context.get('median_price_kes')}, "
        f"affordable_share_pct={context.get('affordable_share_pct')}."
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context_text}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

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

    with st.expander("Setup (free-tier friendly)", expanded=False):
        st.markdown(
            """
            Add these in Streamlit secrets:
            - `OPENAI_API_KEY`
            - `OPENAI_BASE_URL` (optional, default: `https://openrouter.ai/api/v1`)
            - `OPENAI_MODEL` (optional, default: `openai/gpt-4o-mini`)

            You can point to an API-compatible low/no-cost provider by changing base URL + model.
            """
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
