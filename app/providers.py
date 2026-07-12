"""
This file defines your 6 LLM providers and the ORDER in which the router
tries them. If provider #1 fails (rate limit, quota, timeout, etc.), the
router automatically moves to provider #2 with the SAME conversation
history, and so on.

Reorder this list any time you want to change priority.
Nothing here contains real keys — they're pulled from environment
variables (which come from your .env file) at request time.
"""

import os

# Cloudflare needs your account ID baked into the URL, so we read it once here.
CF_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")

PROVIDERS = [
    {
        "name": "google_gemini",
        # litellm's "gemini/" prefix talks to Google AI Studio directly
        "model": "gemini/gemini-3.5-flash",
        "api_key_env": "GOOGLE_API_KEY",
        # litellm looks for GEMINI_API_KEY specifically, so we alias it in router.py
        "litellm_key_env": "GEMINI_API_KEY",
    },
    {
        "name": "groq",
        "model": "groq/llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY",
        "litellm_key_env": "GROQ_API_KEY",
    },
    {
        "name": "cerebras",
        "model": "cerebras/llama3.1-70b",
        "api_key_env": "CEREBRAS_API_KEY",
        "litellm_key_env": "CEREBRAS_API_KEY",
    },
    {
        "name": "openrouter",
        # ":free" models cost nothing on OpenRouter. Swap the model name
        # any time from https://openrouter.ai/models?max_price=0
        "model": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "api_key_env": "OPENROUTER_API_KEY",
        "litellm_key_env": "OPENROUTER_API_KEY",
    },
    {
        "name": "nvidia_nim",
        # NVIDIA NIM exposes an OpenAI-compatible endpoint
        "model": "openai/meta/llama-3.1-70b-instruct",
        "api_key_env": "NVIDIA_API_KEY",
        "litellm_key_env": None,  # passed manually as api_key in router.py
        "api_base": "https://integrate.api.nvidia.com/v1",
    },
    {
        "name": "cloudflare",
        # Cloudflare Workers AI, also OpenAI-compatible
        "model": "openai/@cf/meta/llama-3.1-8b-instruct",
        "api_key_env": "CLOUDFLARE_API_KEY",
        "litellm_key_env": None,
        "api_base": f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1",
    },
]
