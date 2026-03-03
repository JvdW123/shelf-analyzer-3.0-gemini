import json
import base64
import mimetypes
from pathlib import Path
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL
from prompt import SYSTEM_PROMPT, build_user_prompt


def analyze_shelf(photo_paths: list[str], metadata: dict, model: str = None) -> list[dict]:
    """
    Send shelf photos to Gemini for analysis.
    Returns a list of SKU dictionaries.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    file_names = [Path(p).name for p in photo_paths]

    # Build content parts: user prompt text + all images
    parts = []
    parts.append(types.Part.from_text(text=build_user_prompt(metadata, file_names)))

    for photo_path in photo_paths:
        mime_type = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
        image_bytes = Path(photo_path).read_bytes()
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    response = client.models.generate_content(
        model=model or GEMINI_MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=65536,
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text.strip()

    # Parse JSON response
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code fences
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
        data = json.loads(raw_text)

    skus = data.get("skus", data if isinstance(data, list) else [])
    return skus
