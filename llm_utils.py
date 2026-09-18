# LLM helpers — supports Gemini, OpenAI, Anthropic (native + Bedrock), and Ollama.

import os
import json
import time
import tiktoken
from openai import OpenAI, OpenAIError
import google
from google import genai
from google.genai.types import GenerateContentConfig
import ollama
from ollama import chat
from ollama import ChatResponse
import anthropic

ANTHROPIC_MAX_TOKENS = 32768
# Anthropic SDK ≥1.0 refuses non-streaming calls whose max_tokens could exceed
# the default 10-minute timeout. Extend the per-call timeout to opt out.
ANTHROPIC_TIMEOUT_SECONDS = 1800.0

def query_llm_with_retries(client, prompt, value, response_format, model_name, max_retries=5, model_family='gemini'):
    """
    Query the configured LLM with retries and error handling. Returns parsed JSON or text.
    model_family: 'gemini', 'gpt', 'anthropic', 'anthropic_bedrock', or 'ollama'
    """
    for attempt in range(max_retries):
        try:
            if model_family == 'ollama':
                formattedPromptContents = [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': value},
                ]
                kwargs = {
                    'model': model_name,
                    'messages': formattedPromptContents,
                    'options': {'temperature': 0.2}
                }
                if response_format:
                    kwargs['format'] = response_format.model_json_schema() if hasattr(response_format, 'model_json_schema') else response_format

                response = client(**kwargs)
                
                if response_format:
                    parsed_response_content = json.loads(response.message.content)
                    return parsed_response_content
                else:
                    return response.message.content

            elif model_family == 'gemini':
                config_args = {
                    'system_instruction': prompt,
                }
                if response_format:
                    config_args['response_mime_type'] = 'application/json'
                    config_args['response_schema'] = response_format
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=value,
                    config=GenerateContentConfig(**config_args),
                )
                
                if response_format:
                    return json.loads(response.text)
                else:
                    return response.text

            elif model_family == 'gpt':
                messages = [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': value},
                ]

                if response_format:
                    response = client.beta.chat.completions.parse(
                        model=model_name,
                        messages=messages,
                        response_format=response_format
                    )
                    return response.choices[0].message.parsed.model_dump()
                else:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=messages
                    )
                    return response.choices[0].message.content

            elif model_family in ('anthropic', 'anthropic_bedrock'):
                # Both native (Anthropic) and Bedrock (AnthropicBedrock) clients share
                # the messages.create API. Structured output uses a forced tool call.
                kwargs = {
                    'model': model_name,
                    'max_tokens': ANTHROPIC_MAX_TOKENS,
                    'system': prompt,
                    'messages': [{'role': 'user', 'content': value}],
                }
                if response_format:
                    json_schema = response_format.model_json_schema()
                    kwargs['tools'] = [{
                        'name': 'emit_response',
                        'description': 'Emit the response in the required structure.',
                        'input_schema': json_schema,
                    }]
                    kwargs['tool_choice'] = {'type': 'tool', 'name': 'emit_response'}

                resp = client.with_options(timeout=ANTHROPIC_TIMEOUT_SECONDS).messages.create(**kwargs)

                if response_format:
                    for block in resp.content:
                        if getattr(block, 'type', None) == 'tool_use' and block.name == 'emit_response':
                            return dict(block.input or {})
                    return None
                else:
                    return "".join(
                        b.text for b in resp.content
                        if getattr(b, 'type', None) == 'text'
                    )

            else:
                raise ValueError(f"Unknown model_family: {model_family}")
        except (google.genai.errors.ServerError, OpenAIError, anthropic.APIError) as e:
            print(f"Connection error: {e}")
            if attempt < max_retries - 1:
                sleep_duration = (2 ** attempt) * 1
                print(f"Retrying in {sleep_duration} seconds...")
                time.sleep(sleep_duration)
            else:
                print("Max retries reached. Returning None.")
                return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            if attempt < max_retries - 1:
                sleep_duration = (2 ** attempt) * 1
                print(f"Retrying in {sleep_duration} seconds...")
                time.sleep(sleep_duration)
            else:
                print("Max retries reached. Returning None.")
                return None
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < max_retries - 1:
                    sleep_duration = (2 ** attempt) * 10
                    print(f"Rate limited (429). Retrying in {sleep_duration} seconds...")
                    time.sleep(sleep_duration)
                else:
                    print("Max retries reached after rate limiting. Returning None.")
                    return None
                continue
            # For Ollama or any other unexpected error
            print(f"Unexpected error: {e}")
            if attempt < max_retries - 1:
                sleep_duration = (2 ** attempt) * 1
                print(f"Retrying in {sleep_duration} seconds...")
                time.sleep(sleep_duration)
            else:
                print("Max retries reached. Returning None.")
                return None
    return None
