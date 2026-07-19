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


CF_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")

PROVIDERS = [
    {
        "name": "google_gemini",
        
        "model": "gemini/gemini-3.5-flash",
        "api_key_env": "GOOGLE_API_KEY",
        
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
        "model": "cerebras/gpt-oss-120b",
        "api_key_env": "CEREBRAS_API_KEY",
        "litellm_key_env": "CEREBRAS_API_KEY",
    },
    {
        "name": "openrouter",
        
        
        "model": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "api_key_env": "OPENROUTER_API_KEY",
        "litellm_key_env": "OPENROUTER_API_KEY",
    },
    {
        "name": "nvidia_nim",
        
        "model": "openai/meta/llama-3.1-70b-instruct",
        "api_key_env": "NVIDIA_API_KEY",
        "litellm_key_env": None,  
        "api_base": "https://integrate.api.nvidia.com/v1",
    },
    {
        "name": "cloudflare",
        
        "model": "openai/@cf/openai/gpt-oss-120b",
        "api_key_env": "CLOUDFLARE_API_KEY",
        "litellm_key_env": None,
        "api_base": f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1",
    },
]
