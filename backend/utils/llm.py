import json
import logging
from typing import List, Dict, Any, Generator, Optional
import requests
from backend.config import settings

logger = logging.getLogger("apks.llm")

def get_gemini_client():
    """Dynamically imports and returns a Gemini client."""
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from google import genai
        return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to import/initialize new google-genai SDK client: {e}. Trying legacy google.generativeai...")
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=settings.GEMINI_API_KEY)
            return legacy_genai
        except Exception as ex:
            logger.error(f"Failed to initialize any Gemini client: {ex}")
            return None

def get_openai_client():
    """Dynamically imports and returns an OpenAI client."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None

def llm_generate(
    prompt: str,
    system_instruction: Optional[str] = None,
    json_mode: bool = False,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> str:
    """
    Generates a response from the selected LLM provider.
    Fallback logic: Gemini -> OpenAI -> Ollama.
    """
    prov = provider or settings.DEFAULT_LLM_PROVIDER
    model = model_name or settings.DEFAULT_LLM_MODEL
    
    # Clean up names for fallbacks
    if not settings.GEMINI_API_KEY and prov == "gemini":
        if settings.OPENAI_API_KEY:
            prov = "openai"
            model = "gpt-4o-mini"
        else:
            prov = "ollama"
            model = "llama3"
            
    logger.info(f"Generating LLM response using {prov} ({model}). JSON mode: {json_mode}")
    
    try:
        if prov == "gemini":
            client = get_gemini_client()
            if client:
                # Determine if it's the new SDK or legacy
                if hasattr(client, "models"):  # New genai SDK
                    config = {}
                    if system_instruction:
                        config["system_instruction"] = system_instruction
                    if json_mode:
                        config["response_mime_type"] = "application/json"
                    
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config
                    )
                    return response.text
                else:  # Legacy google.generativeai
                    model_to_use = client.GenerativeModel(
                        model_name=model,
                        generation_config={"response_mime_type": "application/json"} if json_mode else None,
                        system_instruction=system_instruction
                    )
                    response = model_to_use.generate_content(prompt)
                    return response.text
            else:
                raise ValueError("Gemini API client not initialized. Check API keys.")
                
        elif prov == "openai":
            client = get_openai_client()
            if client:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                response_format = {"type": "json_object"} if json_mode else None
                
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                )
                return response.choices[0].message.content
            else:
                raise ValueError("OpenAI API client not initialized. Check API keys.")
                
        elif prov == "ollama":
            url = "http://localhost:11434/api/chat"
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2}
            }
            if json_mode:
                payload["format"] = "json"
                
            res = requests.post(url, json=payload, timeout=60)
            res.raise_for_status()
            return res.json()["message"]["content"]
            
        else:
            raise ValueError(f"Unknown LLM provider: {prov}")
            
    except Exception as e:
        logger.error(f"Error generating LLM response with {prov}: {e}")
        # Final emergency fallback to Local Ollama if not already using it
        if prov != "ollama":
            logger.warning("Attempting emergency fallback to local Ollama (llama3)...")
            try:
                return llm_generate(prompt, system_instruction, json_mode, "ollama", "llama3")
            except Exception as fe:
                logger.error(f"Ollama fallback failed: {fe}")
        
        # If all else fails, return a mock structured or raw output based on json_mode
        if json_mode:
            return json.dumps({"error": "Failed to generate response", "confidence": 0.0, "issues": ["All LLM backends failed"]})
        return f"Error: All configured LLM providers failed. Detailed logs: {e}"

def llm_generate_stream(
    prompt: str,
    system_instruction: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Streams response tokens from the selected LLM provider.
    """
    prov = provider or settings.DEFAULT_LLM_PROVIDER
    model = model_name or settings.DEFAULT_LLM_MODEL
    
    if not settings.GEMINI_API_KEY and prov == "gemini":
        if settings.OPENAI_API_KEY:
            prov = "openai"
            model = "gpt-4o-mini"
        else:
            prov = "ollama"
            model = "llama3"
            
    logger.info(f"Streaming LLM response using {prov} ({model})")
    
    try:
        if prov == "gemini":
            client = get_gemini_client()
            if client:
                if hasattr(client, "models"):  # New genai SDK
                    config = {}
                    if system_instruction:
                        config["system_instruction"] = system_instruction
                    response = client.models.generate_content_stream(
                        model=model,
                        contents=prompt,
                        config=config
                    )
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
                else:  # Legacy google.generativeai
                    model_to_use = client.GenerativeModel(
                        model_name=model,
                        system_instruction=system_instruction
                    )
                    response = model_to_use.generate_content(prompt, stream=True)
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
            else:
                yield "Error: Gemini client not initialized."
                
        elif prov == "openai":
            client = get_openai_client()
            if client:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True
                )
                for chunk in response:
                    token = chunk.choices[0].delta.content
                    if token:
                        yield token
            else:
                yield "Error: OpenAI client not initialized."
                
        elif prov == "ollama":
            url = "http://localhost:11434/api/chat"
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            res = requests.post(url, json=payload, stream=True, timeout=60)
            res.raise_for_status()
            for line in res.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    data = json.loads(decoded)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
        else:
            yield f"Error: Unknown provider {prov}"
    except Exception as e:
        logger.error(f"Streaming error with {prov}: {e}")
        yield f"\n[Streaming Error: {e}]"
