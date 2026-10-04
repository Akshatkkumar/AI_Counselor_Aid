# calls take a sys prompt| format: {"role": "user"|"assistant", "content": str}
# calls can return plain text or a parsed dict depending on json_mode bool

import json
import os
import random
import re

GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini"]


class LLM:
    def __init__(self, provider, model, api_key):
        self.provider = provider
        self.model = model
        if provider == "Gemini":
            from google import genai  # install appropriate lib in func
            key = api_key or os.getenv("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("No Gemini API key. Add GEMINI_API_KEY to .env or the sidebar.")
            self._client = genai.Client(api_key=key)
        elif provider == "OpenAI":
            from openai import OpenAI
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("No OpenAI API key. Add OPENAI_API_KEY to .env or the sidebar.")
            self._client = OpenAI(api_key=key)
        elif provider == "Offline demo":
            self._client = None
        else:
            raise RuntimeError(f"Unknown provider: {provider}")

    # public

    def chat(self, system, messages, temperature = 0.9):
        return self._generate(system, messages, temperature, json_mode=False)

    def json(self, system, prompt, temperature = 0.4):
        text = self._generate(system, [{"role": "user", "content": prompt}], temperature, json_mode=True)
        return parse_json(text)

    # providers

    def _generate(self, system, messages, temperature, json_mode) -> str:
        try:
            if self.provider == "Gemini":
                return self._gemini(system, messages, temperature, json_mode)
            if self.provider == "OpenAI":
                return self._openai(system, messages, temperature, json_mode)
            return _offline(system, messages, json_mode)
        except Exception as e:  
            raise RuntimeError(f"{self.provider} request failed: {e}") from e

    def _gemini(self, system, messages, temperature, json_mode):
        from google.genai import types
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        resp = self._client.models.generate_content(model=self.model, contents=contents, config=config)
        if not resp.text:
            raise RuntimeError("Error in Gemini response")
        return resp.text.strip()

    def _openai(self, system, messages, temperature, json_mode) -> str:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=temperature,
            max_tokens=2048,
            **kwargs,
        )
        return (resp.choices[0].message.content or "").strip()


def parse_json(text):
    """Parse a JSON object"""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise RuntimeError("The model did not return valid JSON. Try again.")


# offline demo[for test without API key]

def _offline(system, messages, json_mode):
    if not json_mode:
        lines = [
            "I don't really know where to start... things have just been a lot lately.",
            "Yeah. I guess I haven't told anyone that before.",
            "Sometimes I think I'm overreacting, but it keeps coming back.",
            "My family wouldn't understand. They'd say I just need to try harder.",
            "That's... actually a fair point. I hadn't thought of it that way.",
        ]
        return random.choice(lines)
    prompt = messages[-1]["content"]
    if "PERSONA" in system:
        return json.dumps({
            "name": "Jordan Lee", "age": 20, "occupation": "Second-year university student",
            "background": "Lives in student housing; first in family to attend university.",
            "presenting_problem": "Falling grades and frequent arguments with parents over phone calls.",
            "personality": "Polite, guarded, self-critical.",
            "communication_style": "Short answers at first, opens up when feeling understood.",
            "emotional_state": "Anxious and tired.",
            "hidden_concerns": "Has been skipping classes and hasn't told anyone.",
            "cultural_context": "Feels pressure to make family proud.",
            "goals_for_counselling": "Wants to feel less overwhelmed.",
        })
    if "SUPERVISOR" in system:
        from prompts import FEEDBACK_DIMENSIONS
        return json.dumps({
            "scores": {k: {"score": random.randint(2, 5), "evidence": "\"How did that feel?\"",
                           "comment": "Offline demo comment."} for k in FEEDBACK_DIMENSIONS},
            "strengths": ["Warm opening", "Used open questions"],
            "improvements": [{"issue": "Moved to advice quickly", "original": "You should study more.",
                              "better": "It sounds like studying has been hard lately. What gets in the way?"}],
            "overall_comment": "Offline demo feedback. Connect an API key for real evaluation.",
        })
    return json.dumps({
        "one_line_summary": "Client discussed academic stress and family pressure.",
        "presenting_concerns": ["Academic performance", "Parent-child relationship"],
        "key_disclosures": ["Skipping some classes"], "important_people": ["Mother", "Father"],
        "emotional_state_start": "Anxious", "emotional_state_end": "Slightly calmer",
        "progress_made": "Client named the main stressors.", "agreed_next_steps": [],
        "risk_indicators": [], "unexplored_topics": ["Sleep"], "rapport": "Developing",
    })
