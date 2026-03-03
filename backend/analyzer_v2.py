"""
Four-pass shelf analyzer with image tiling.

Pass 1: Send overview photo(s) to get shelf structure
  - Total SKU count, shelf levels, brand list, approximate layout
Pass OCR: Dedicated text-reading pass on tile images
  - Reads ALL text on every label (brand, product name, flavor, size, claims)
  - Separates "reading" from "thinking" for better accuracy
Pass 2: Send tiled images + close-ups for detailed SKU extraction
  - Uses Pass 1 structure + OCR text as context
Pass 3: Verification pass
  - Cross-check Pass 2 results against Pass 1 structure
"""
import json
import mimetypes
from pathlib import Path
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL
from image_tiler import prepare_images


PASS1_PROMPT = """You are a shelf auditor. Analyze this overview photo of a retail shelf.

Your ONLY job is to describe the shelf structure. Do NOT extract detailed SKU data yet.

Count and identify:
1. Total number of DISTINCT products (unique SKUs) visible on the shelf
2. Number of shelf levels (horizontal rows)
3. All BRAND names visible — read the actual brand/company name from the logo or label.
   IMPORTANT: "Juice" is NOT a brand name. Read the full brand name (e.g., "The Juice Company", "Tropicana", "Innocent").
   Look for the company/brand logo, usually at the top of the label.
4. For each brand, list the approximate number of distinct products
5. Estimated total linear meters of the shelf

Return JSON:
{
  "shelf_levels": 4,
  "total_distinct_skus": 21,
  "est_linear_meters": 2.5,
  "brands": [
    {"name": "The Juice Company", "approx_sku_count": 12},
    {"name": "Specially Selected", "approx_sku_count": 5}
  ],
  "layout_description": "Brief description of shelf layout from left to right, top to bottom"
}

Return ONLY valid JSON."""


PASS_OCR_PROMPT = """You are an OCR specialist. Your ONLY job is to read ALL text visible on every product label in these photos.

For EACH distinct product you can see, transcribe ALL text on its label from top to bottom:
- Brand name / logo text (usually at the TOP of the label, often in a distinctive font or logo)
- Sub-brand or quality tier text (e.g., "Specially Selected", "Finest", "Premium")
- Product name (the LARGEST marketing text)
- Flavor / variety description (smaller text below product name)
- Volume / size (e.g., "1L", "750ml", "330ml")
- Any claims text (e.g., "Cold Pressed", "Not from concentrate", "No added sugar")
- Price tag text if visible (price, per-unit price)

CRITICAL RULES:
1. Read EVERY word, even small text. Small text often contains the real brand name.
2. Do NOT classify or analyze — just transcribe what you see.
3. Do NOT guess — if text is unreadable, write "[unreadable]".
4. Pay special attention to text ABOVE the product name — this is usually the brand.
5. If you see "The [Something] Company" or similar, that is the BRAND NAME — transcribe it fully.

Format your response as JSON:
{
  "products": [
    {
      "position": "shelf level and approximate left-to-right position",
      "all_text_top_to_bottom": ["Brand Logo Text", "Sub-brand", "Product Name", "Flavor description", "750ml", "Cold Pressed"],
      "brand_text": "the text that appears to be the brand/company name",
      "price_tag_text": "£2.49 / £3.32 per litre" or null
    }
  ]
}

Return ONLY valid JSON."""


PASS2_PROMPT = """You are a professional shelf auditor AI. Analyze these shelf photos and extract all SKU data.

SHELF STRUCTURE (from overview analysis — use this as your reference):
{structure_context}

OCR TEXT READINGS (from dedicated text-reading pass — use this to get accurate brand names and label text):
{ocr_text_context}

IMPORTANT RULES:
1. The overview analysis found {expected_sku_count} distinct SKUs. Your count should be close to this number. If you find significantly more, you are likely creating phantom SKUs.
2. USE THE OCR TEXT READINGS ABOVE to get accurate brand names. The OCR pass read the actual text on labels. Match each product to its OCR reading to get the correct brand, product name, and flavor.
3. The brands on this shelf are: {brand_list}. Do NOT use generic names like "Juice" as a brand. Every SKU must be assigned to one of these brands, or a brand you can clearly read from the label.
4. NEVER invent a product. Only include a SKU if you can see at least TWO of: (a) product label text, (b) price tag, (c) distinct bottle/package.
5. Each unique SKU appears only ONCE — deduplicate across all photos.
6. Count facings carefully: count bottle caps/tops in the front row only. Ignore depth. Same cap + same color = same SKU = count as another facing.

BRAND READING — CRITICAL:
- The brand is the COMPANY or BRAND name, NOT the product category
- "Juice" is NEVER a valid brand name
- Look for the brand logo, usually at the TOP of the label or on the cap
- Common brand patterns: "The [X] Company", "[Brand Name]" in distinctive font
- If a product says "Specially Selected" or similar quality tier branding, THAT is the brand (or sub-brand of the retailer)
- Private label products: use the retailer quality tier as the brand (e.g., "Specially Selected" for Aldi's premium line)

PRODUCT TYPE CLASSIFICATION:
- "Pure Juices" = any single-fruit or blended fruit juice (including vitamin/immune/functional juices that are still juice-based)
- "Smoothies" = thick blended drinks with fruit pulp, yogurt, or similar
- "Shots" = small format drinks (typically <100ml)
- "Other" = ONLY for products that are clearly NOT juice or smoothie (e.g., coconut water, energy drinks, coffee)
- When in doubt, classify as "Pure Juices" — NOT "Other"
- Products labeled "Multivitamin", "Immune Support", "Gut Health" etc. are still Pure Juices if they are juice-based

For every unique SKU, capture these fields:
1. country, 2. city, 3. retailer, 4. store_format, 5. store_name, 6. photo (exact file name),
7. shelf_location, 8. shelf_levels, 9. shelf_level (1st/2nd/3rd/4th from top),
10. product_type (Pure Juices/Smoothies/Shots/Other),
11. branded_private_label ("Branded" or "Private Label"),
12. brand (NEVER "Juice" — read the actual brand name),
13. sub_brand, 14. product_name (largest text on front of label),
15. flavor (ingredient composition in smaller text, or = product_name if none),
16. facings (front row count only),
17. price_local (from price tag, null if not visible),
18. currency, 19. price_eur, 20. packaging_size_ml (null if not visible),
21. price_per_liter_eur (always null — calculated by Excel),
22. need_state (Indulgence/Functional),
23. juice_extraction_method (Cold Pressed/Squeezed/From Concentrate/NA/Centrifugal),
24. processing_method (HPP/Pasteurised/Raw — default "Pasteurised"),
25. hpp_treatment (Yes/No/Unknown — default "Unknown"),
26. packaging_type (PET bottle/Glass bottle/Tetra Pak/Can/Pouch/Cup),
27. claims (comma-separated, empty string if none),
28. bonus_promotions (empty string if none),
29. stock_status (In Stock/Out of Stock),
30. est_linear_meters (same for every row),
31. fridge_number (empty string if only one),
32. confidence_score (100/80/60/40),
33. notes

PRODUCT NAME VS FLAVOR:
- product_name = LARGEST marketing text on front label
- flavor = fruit/ingredient composition in smaller text below
- If no separate description, flavor = product_name

DEFAULTS: juice_extraction_method → "NA/Centrifugal", processing_method → "Pasteurised", hpp_treatment → "Unknown", need_state → "Indulgence"

Return JSON: {{"skus": [...]}}
Return ONLY valid JSON."""


PASS3_PROMPT = """You are a quality checker for shelf audit data.

OVERVIEW STRUCTURE (ground truth reference):
{structure_context}

EXTRACTED SKU DATA:
{sku_data}

Check for these errors and fix them:

1. PHANTOM SKUS: Remove any SKU that doesn't match a real product visible in the overview. The overview found ~{expected_sku_count} SKUs. If the data has significantly more, identify and remove the extras.

2. BRAND ERRORS: The brands on this shelf are: {brand_list}. Fix any SKU that has "Juice" as a brand or uses a generic category name. Assign the correct brand from the list.

3. DUPLICATE SKUS: If two rows describe the same product (same brand + product name + flavor + ml), merge them — keep the one with higher confidence and sum the facings.

4. PRODUCT TYPE: Products labeled as "Other" should be rechecked. If they contain juice, reclassify as "Pure Juices". Only true non-juice products (coconut water, coffee, etc.) should be "Other".

5. FACINGS: Total facings across all SKUs should be approximately {expected_facings} (from overview count). If significantly different, adjust the most uncertain entries.

Return the corrected data as JSON: {{"skus": [...]}}
Make minimal changes — only fix clear errors. Keep all other data exactly as-is.
Return ONLY valid JSON."""


def _call_gemini(client, model: str, system_prompt: str, user_text: str,
                 image_paths: list[str] = None) -> str:
    """Make a Gemini API call with optional images."""
    parts = [types.Part.from_text(text=user_text)]

    if image_paths:
        for path in image_paths:
            mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
            image_bytes = Path(path).read_bytes()
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            max_output_tokens=65536,
            response_mime_type="application/json",
        ),
    )
    return response.text.strip()


def _parse_json(raw_text: str) -> dict:
    """Parse JSON from Gemini response, handling code fences."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
        return json.loads(raw_text)


def analyze_shelf_v2(photo_paths: list[str], metadata: dict,
                     session_dir: str, model: str = None) -> list[dict]:
    """
    Two-pass shelf analysis with image tiling.
    Returns a list of verified SKU dictionaries.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    use_model = model or GEMINI_MODEL

    # Prepare images: classify and tile
    prepared = prepare_images(photo_paths, session_dir)

    # === PASS 1: Shelf structure from overview(s) ===
    overview_text = (
        "Analyze this overview photo of a retail shelf. "
        f"Store: {metadata.get('retailer', 'Unknown')} in {metadata.get('city', 'Unknown')}, {metadata.get('country', 'Unknown')}."
    )

    pass1_result = _call_gemini(
        client, use_model, PASS1_PROMPT, overview_text,
        image_paths=prepared["overview_originals"]
    )
    structure = _parse_json(pass1_result)

    # Build context for Pass 2
    brand_list = ", ".join(b["name"] for b in structure.get("brands", []))
    expected_count = structure.get("total_distinct_skus", "unknown")

    structure_context = json.dumps(structure, indent=2)

    # === PASS OCR: Read all text from labels ===
    all_images = prepared["all_analysis_images"]

    ocr_text = "Analyze these shelf photos. Read ALL text on every product label."
    ocr_result = _call_gemini(
        client, use_model, PASS_OCR_PROMPT, ocr_text,
        image_paths=all_images
    )
    ocr_data = _parse_json(ocr_result)
    ocr_text_context = json.dumps(ocr_data, indent=2)

    # Also update brand list from OCR findings
    ocr_brands = set()
    for product in ocr_data.get("products", []):
        brand = product.get("brand_text", "")
        if brand and brand.lower() not in ("juice", "unknown", "", "[unreadable]"):
            ocr_brands.add(brand)
    if ocr_brands:
        # Merge OCR-detected brands with Pass 1 brands
        all_brands = set(b["name"] for b in structure.get("brands", []))
        all_brands.update(ocr_brands)
        brand_list = ", ".join(sorted(all_brands))

    # === PASS 2: Detailed extraction from tiles + close-ups ===
    file_names = [Path(p).name for p in all_images]

    # Build the user prompt with metadata
    user_parts = []
    user_parts.append("STORE METADATA:")
    user_parts.append(f"- Country: {metadata.get('country', 'Unknown')}")
    user_parts.append(f"- City: {metadata.get('city', 'Unknown')}")
    user_parts.append(f"- Retailer: {metadata.get('retailer', 'Unknown')}")
    user_parts.append(f"- Store Format: {metadata.get('store_format', 'Unknown')}")
    user_parts.append(f"- Store Name: {metadata.get('store_name', 'Unknown')}")
    user_parts.append(f"- Shelf Location: {metadata.get('shelf_location', 'Unknown')}")
    user_parts.append(f"\nPHOTO FILE NAMES:")
    for name in file_names:
        user_parts.append(f"- {name}")
    user_parts.append(f"\nTotal images: {len(file_names)}")
    user_parts.append("\nAnalyze all images and return JSON with all SKUs.")

    pass2_system = PASS2_PROMPT.format(
        structure_context=structure_context,
        expected_sku_count=expected_count,
        brand_list=brand_list or "Unknown — read brands from labels carefully",
        ocr_text_context=ocr_text_context,
    )

    pass2_result = _call_gemini(
        client, use_model, pass2_system, "\n".join(user_parts),
        image_paths=all_images
    )
    pass2_data = _parse_json(pass2_result)
    skus = pass2_data.get("skus", pass2_data if isinstance(pass2_data, list) else [])

    # === PASS 3: Verification ===
    # Estimate expected facings (rough: ~3 per SKU average)
    expected_facings = expected_count * 3 if isinstance(expected_count, int) else "unknown"

    pass3_system = PASS3_PROMPT.format(
        structure_context=structure_context,
        sku_data=json.dumps(skus, indent=2),
        expected_sku_count=expected_count,
        brand_list=brand_list,
        expected_facings=expected_facings,
    )

    pass3_result = _call_gemini(
        client, use_model, pass3_system,
        "Verify and correct the SKU data. Return corrected JSON.",
        image_paths=prepared["overview_originals"]  # Re-send overview for reference
    )
    pass3_data = _parse_json(pass3_result)
    verified_skus = pass3_data.get("skus", pass3_data if isinstance(pass3_data, list) else [])

    # Replace tile filenames with original photo filenames in the output
    tile_to_original = {}
    for tile in prepared["overview_tiles"]:
        tile_to_original[Path(tile["path"]).name] = tile["original"]

    for sku in verified_skus:
        photo_field = sku.get("photo", "")
        if photo_field in tile_to_original:
            sku["photo"] = tile_to_original[photo_field]

    return verified_skus
