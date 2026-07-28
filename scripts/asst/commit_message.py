#!/usr/bin/env python3
"""
Commit Message Generator supporting OpenAI-compatible LLM endpoints (Grok, GitHub Models, Azure OpenAI, Local vLLM/Ollama).

Usage:
    python commit_message.py -f diff_output.tmp
    python commit_message.py -p "Some diff content here"
    echo "diff content" | python commit_message.py

Environment Variables:
    AI_ENDPOINT - OpenAI-compatible ChatCompletions endpoint URL (default: https://api.x.ai/v1/chat/completions)
    AI_MODEL    - Model name (default: grok-build-0.1)
    AI_API_KEY  - API Key for LLM provider (or GITHUB_TOKEN / GH_TOKEN)
"""

import argparse
import os
import sys
import json
from urllib import request, error

# Default Configuration
DEFAULT_ENDPOINT = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-build-0.1"

# System prompt for commit message generation
SYSTEM_PROMPT = """You are a commit message generator. Given a git diff, produce a single-line commit message that:
1. Starts with a verb (Add, Update, Fix, Remove, Refactor, etc.)
2. Is max 72 characters
3. Describes WHAT changed, not HOW
4. Is specific but concise

Examples:
- "Add user authentication endpoint"
- "Fix null pointer in config parser"
- "Update API version to v2"
- "Remove deprecated logging calls"

Output ONLY the commit message, nothing else. No quotes, no explanation."""


def get_api_key(args_token: str = None) -> str:
    """Get API Key from CLI argument or environment variables."""
    key = args_token or os.environ.get("AI_API_KEY") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not key:
        raise EnvironmentError(
            "No API key found. Set AI_API_KEY, GITHUB_TOKEN, or GH_TOKEN environment variable, "
            "or pass via -t/--token argument."
        )
    return key


def generate_commit_message(diff_content: str, token: str, endpoint: str = DEFAULT_ENDPOINT, model: str = DEFAULT_MODEL) -> str:
    """
    Generate a commit message from a git diff using OpenAI-compatible ChatCompletions API.
    
    Args:
        diff_content: The git diff text
        token: API Key for authentication
        endpoint: ChatCompletions URL endpoint
        model: Model to use (default: grok-build-0.1)
    
    Returns:
        Generated commit message string
    """
    # Truncate diff if too long (keep first 12000 chars for context window)
    max_diff_chars = 12000
    if len(diff_content) > max_diff_chars:
        diff_content = diff_content[:max_diff_chars] + "\n... [truncated]"
    
    # Build request payload (OpenAI-compatible format)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate a commit message for this diff:\n\n{diff_content}"}
        ],
        "max_tokens": 100,
        "temperature": 0.3
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            message = result["choices"][0]["message"]["content"].strip()
            # Clean up: remove quotes if wrapped
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]
            return message
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"AI API error ({e.code}): {error_body}")
    except error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def read_file(filepath: str) -> str:
    """Read file contents."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate commit messages using OpenAI-compatible LLMs (Grok, GitHub Models, Azure, Local)"
    )
    parser.add_argument("-p", "--prompt", help="Diff content as string")
    parser.add_argument("-f", "--filepath", help="Path to diff file")
    parser.add_argument("-t", "--token", "--key", dest="token", help="API key (or use AI_API_KEY env)")
    parser.add_argument("-e", "--endpoint", default=os.environ.get("AI_ENDPOINT", DEFAULT_ENDPOINT),
                        help=f"LLM API Endpoint (default: {DEFAULT_ENDPOINT})")
    parser.add_argument("-m", "--model", default=os.environ.get("AI_MODEL", DEFAULT_MODEL), 
                        help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--fallback", default="Update repository",
                        help="Fallback message if AI fails")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Get diff content
    if args.prompt:
        content = args.prompt
    elif args.filepath:
        content = read_file(args.filepath)
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        print("Error: No diff content provided. Use -p, -f, or pipe input.", file=sys.stderr)
        sys.exit(1)
    
    # Skip if no actual content
    if not content.strip():
        print(args.fallback)
        sys.exit(0)
    
    # Get API key
    try:
        token = get_api_key(args.token)
    except EnvironmentError as e:
        print(f"Warning: {e}", file=sys.stderr)
        print(args.fallback)
        sys.exit(0)
    
    # Generate message
    try:
        message = generate_commit_message(content, token, endpoint=args.endpoint, model=args.model)
        print(message)
    except Exception as e:
        print(f"Warning: AI generation failed: {e}", file=sys.stderr)
        print(args.fallback)
        sys.exit(0)


if __name__ == "__main__":
    main()

