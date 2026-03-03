import sys
import os
import tempfile
import shutil
from io import BytesIO

# Add backend directory to path so we can import backend modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import streamlit as st

st.set_page_config(
    page_title="Shelf Analyzer 3.0",
    page_icon="🛒",
    layout="wide",
)

from metadata_parser import parse_metadata_from_filenames
from analyzer_v2 import analyze_shelf_v2
from excel_generator import generate_excel

import pandas as pd
from PIL import Image

# Clockwise degrees stored → PIL transpose operation
_PIL_ROTATE = {
    90:  Image.Transpose.ROTATE_270,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


def _rotated_preview(uploaded_file, degrees: int) -> bytes:
    """Return JPEG bytes of the uploaded file rotated by `degrees` clockwise."""
    uploaded_file.seek(0)
    img = Image.open(uploaded_file).convert("RGB")
    if degrees != 0:
        img = img.transpose(_PIL_ROTATE[degrees])
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


# =============================================================================
# PASSWORD GATE
# =============================================================================
def _check_password() -> bool:
    """Returns True if the user has entered the correct password."""
    if st.session_state.get("authenticated"):
        return True

    st.subheader("Sign in")
    pwd = st.text_input("Password", type="password", key="pwd_input")
    if st.button("Enter", type="primary"):
        correct = st.secrets.get("APP_PASSWORD", "")
        if pwd == correct:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not _check_password():
    st.stop()


# --- Session state initialisation ---
def _init():
    defaults = {
        "step": "upload",
        "photos": [],
        "photo_rotations": {},
        "metadata": {
            "country": "",
            "city": "",
            "retailer": "",
            "store_format": "",
            "store_name": "",
            "shelf_location": "",
        },
        "results": None,
        "error": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init()

STEP_LABELS = ["Upload Photos", "Store Details", "Analyzing", "Results"]
STEP_ORDER = {"upload": 0, "metadata": 1, "processing": 2, "results": 3}

# ── Header ───────────────────────────────────────────────────────────────────
st.title("Shelf Analyzer 3.0")
st.caption("Upload shelf photos · Gemini AI extracts SKU data · Download Excel")

# ── Step indicator ────────────────────────────────────────────────────────────
current = STEP_ORDER.get(st.session_state.step, 0)
step_cols = st.columns(4)
for i, (col, label) in enumerate(zip(step_cols, STEP_LABELS)):
    with col:
        if i < current:
            st.success(f"✓ {label}")
        elif i == current:
            st.info(f"**{label}**")
        else:
            st.markdown(f"<p style='color:grey;margin:0'>{label}</p>", unsafe_allow_html=True)

st.divider()

# ── Error banner ──────────────────────────────────────────────────────────────
if st.session_state.error:
    st.error(st.session_state.error)
    if st.button("Dismiss error"):
        st.session_state.error = None
        st.rerun()

# =============================================================================
# STEP 1 — Upload Photos
# =============================================================================
if st.session_state.step == "upload":
    st.subheader("Step 1 — Upload & Rotate Photos")
    st.write("Upload one or more shelf photos. Use the rotation buttons to fix any sideways or upside-down images before analysis.")

    uploaded = st.file_uploader(
        "Choose photos",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if uploaded:
        # Reset rotations when the file selection changes
        current_names = [f.name for f in uploaded]
        prev_names = [f.name for f in st.session_state.get("photos", [])]
        if current_names != prev_names:
            st.session_state.photo_rotations = {i: 0 for i in range(len(uploaded))}

        st.write(f"**{len(uploaded)} photo(s) selected** — rotate any that are sideways or upside-down:")

        COLS_PER_ROW = 3
        for row_start in range(0, len(uploaded), COLS_PER_ROW):
            row_files = uploaded[row_start: row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for j, photo in enumerate(row_files):
                i = row_start + j
                rotation = st.session_state.photo_rotations.get(i, 0)
                with cols[j]:
                    preview = _rotated_preview(photo, rotation)
                    st.image(preview, caption=f"{photo.name}  ({rotation}°)", use_container_width=True)
                    b_left, b_right = st.columns(2)
                    with b_left:
                        if st.button("↺ Left", key=f"rot_l_{i}"):
                            st.session_state.photo_rotations[i] = (rotation - 90) % 360
                            st.rerun()
                    with b_right:
                        if st.button("↻ Right", key=f"rot_r_{i}"):
                            st.session_state.photo_rotations[i] = (rotation + 90) % 360
                            st.rerun()

        st.write("")
        if st.button("Continue →", type="primary"):
            st.session_state.photos = uploaded
            # Auto-parse metadata from filenames
            names = [f.name for f in uploaded]
            parsed = parse_metadata_from_filenames(names)
            for key, value in parsed.items():
                if value and key != "currency":
                    st.session_state.metadata[key] = value
            st.session_state.step = "metadata"
            st.rerun()

# =============================================================================
# STEP 2 — Metadata Form
# =============================================================================
elif st.session_state.step == "metadata":
    st.subheader("Step 2 — Store Details")
    st.write(f"**{len(st.session_state.photos)} photo(s) ready.** Confirm the store details below (auto-filled where detected from filenames).")

    meta = st.session_state.metadata
    FORMATS = ["", "Supermarket", "Hypermarket", "Convenience", "Express", "Discount"]

    col1, col2 = st.columns(2)
    with col1:
        country = st.text_input("Country *", value=meta.get("country", ""))
        retailer = st.text_input("Retailer *", value=meta.get("retailer", ""))
        store_name = st.text_input("Store Name", value=meta.get("store_name", ""))
    with col2:
        city = st.text_input("City *", value=meta.get("city", ""))
        saved_fmt = meta.get("store_format", "")
        fmt_idx = FORMATS.index(saved_fmt) if saved_fmt in FORMATS else 0
        store_format = st.selectbox("Store Format", FORMATS, index=fmt_idx)
        shelf_location = st.text_input(
            "Shelf Location",
            value=meta.get("shelf_location", ""),
            placeholder="e.g. Juice Aisle — Chilled",
        )

    back_col, analyze_col = st.columns([1, 5])
    with back_col:
        if st.button("← Back"):
            st.session_state.step = "upload"
            st.rerun()
    with analyze_col:
        if st.button("Analyze Shelf →", type="primary"):
            if not country.strip() or not city.strip() or not retailer.strip():
                st.error("Country, City, and Retailer are required.")
            else:
                st.session_state.metadata = {
                    "country": country.strip(),
                    "city": city.strip(),
                    "retailer": retailer.strip(),
                    "store_format": store_format,
                    "store_name": store_name.strip(),
                    "shelf_location": shelf_location.strip(),
                }
                st.session_state.step = "processing"
                st.rerun()

# =============================================================================
# STEP 3 — Processing
# =============================================================================
elif st.session_state.step == "processing":
    st.subheader("Analyzing shelf with Gemini AI…")
    st.write("This takes 1–3 minutes depending on the number of photos. Please keep this tab open.")

    session_dir = None
    with st.spinner("Running 4-pass analysis (structure → OCR → extraction → verification)…"):
        try:
            session_dir = tempfile.mkdtemp(prefix="shelf_")
            photo_paths = []

            rotations = st.session_state.get("photo_rotations", {})
            for i, uploaded_file in enumerate(st.session_state.photos):
                uploaded_file.seek(0)
                file_path = os.path.join(session_dir, uploaded_file.name)
                rotation = rotations.get(i, 0)
                if rotation != 0:
                    img = Image.open(uploaded_file).convert("RGB")
                    img = img.transpose(_PIL_ROTATE[rotation])
                    img.save(file_path, quality=95)
                else:
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.read())
                photo_paths.append(file_path)

            skus = analyze_shelf_v2(photo_paths, st.session_state.metadata.copy(), session_dir)

            st.session_state.results = {
                "skus": skus,
                "sku_count": len(skus),
            }
            st.session_state.step = "results"

        except Exception as e:
            st.session_state.error = str(e)
            st.session_state.step = "metadata"

        finally:
            if session_dir and os.path.exists(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)

    st.rerun()

# =============================================================================
# STEP 4 — Results
# =============================================================================
elif st.session_state.step == "results":
    results = st.session_state.results
    skus = results["skus"]
    sku_count = results["sku_count"]

    st.subheader("Analysis Complete")

    # Summary metrics
    brands = list({s.get("brand", "") for s in skus if s.get("brand")})
    total_facings = sum(s.get("facings", 0) or 0 for s in skus)
    oos_count = sum(1 for s in skus if s.get("stock_status") == "Out of Stock")
    avg_conf = (
        round(sum(s.get("confidence_score", 0) or 0 for s in skus) / len(skus))
        if skus else 0
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("SKUs Found", sku_count)
    m2.metric("Brands", len(brands))
    m3.metric("Total Facings", total_facings)
    m4.metric("Out of Stock", oos_count)
    m5.metric("Avg Confidence", f"{avg_conf}%")

    st.divider()

    # Action buttons
    btn_col, new_col = st.columns([2, 8])

    with btn_col:
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name
            generate_excel(skus, tmp_path)
            with open(tmp_path, "rb") as f:
                excel_bytes = f.read()
            os.unlink(tmp_path)

            st.download_button(
                label="⬇ Download Excel",
                data=excel_bytes,
                file_name="shelf_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except Exception as e:
            st.error(f"Excel generation failed: {e}")

    with new_col:
        if st.button("New Analysis"):
            for key in ["step", "photos", "results", "error"]:
                st.session_state.pop(key, None)
            st.session_state.metadata = {
                "country": "", "city": "", "retailer": "",
                "store_format": "", "store_name": "", "shelf_location": "",
            }
            st.rerun()

    # SKU preview table
    st.divider()
    st.subheader(f"SKU Preview ({sku_count} rows)")

    DISPLAY_COLS = [
        "photo", "shelf_level", "brand", "product_name", "flavor",
        "product_type", "facings", "price_local", "currency",
        "packaging_size_ml", "packaging_type", "stock_status", "confidence_score",
    ]

    df = pd.DataFrame(
        [{col: sku.get(col, "") for col in DISPLAY_COLS} for sku in skus],
        columns=DISPLAY_COLS,
    )
    df.index = df.index + 1

    def _conf_color(val):
        if isinstance(val, (int, float)):
            if val >= 75:
                return "background-color: #C6EFCE"
            if val >= 55:
                return "background-color: #FFEB9C"
            return "background-color: #FFC7CE"
        return ""

    def _stock_color(val):
        if val == "Out of Stock":
            return "background-color: #FFC7CE; color: red; font-weight: bold"
        return ""

    styled = (
        df.style
        .map(_conf_color, subset=["confidence_score"])
        .map(_stock_color, subset=["stock_status"])
    )

    st.dataframe(styled, use_container_width=True, height=500)
    st.caption("This preview shows key columns only. The Excel download contains all 33 columns with full formatting.")
