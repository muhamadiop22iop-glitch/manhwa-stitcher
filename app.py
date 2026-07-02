import io
import os
import re
import random
import zipfile
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

# ڕێکخستنی لاپەڕەی وێبەکە
st.set_page_config(page_title="Kurdsubtitle Manga & Manhwa Toolkit", page_icon="📜", layout="centered")

# ستایلێکی کوردی و مۆدێرن بۆ وێبسایتەکە
st.markdown("""
    <style>
    .stApp { background-color: #121212; color: white; }
    h1, h2, h3, p, label { text-align: right; direction: rtl; font-family: 'Arial'; }
    .stButton>button { background-color: #be5a27 !important; color: white !important; width: 100%; font-weight: bold; }
    .stButton>button:hover { background-color: #96431a !important; }
    div[data-testid="stCheckbox"] label p { color: #be5a27; font-weight: bold; }
    div[data-testid="stRadio"] label p { color: white; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def find_smart_split_row(img_np, target_y, search_range=300):
    height, width, _ = img_np.shape
    start_y = max(0, target_y - search_range)
    end_y = min(height - 1, target_y + search_range)
    
    best_row = target_y
    min_variance = float('inf')
    
    for y in range(start_y, end_y):
        row = img_np[y, :, :3]
        mean_color = np.mean(row, axis=0)
        
        if np.all(mean_color > 240) or np.all(mean_color < 15):
            return y
            
        variance = np.var(row)
        if variance < min_variance:
            min_variance = variance
            best_row = y
            
    return best_row

def apply_watermark(base_img, watermark_img, count=1):
    base_w, base_h = base_img.size
    wm_w = max(40, int(base_w * 0.12))
    wm_h = int(watermark_img.height * (wm_w / watermark_img.width))
    wm_resized = watermark_img.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
    
    img_copy = base_img.copy()
    
    if count == 1:
        paste_x = base_w - wm_w - 20
        paste_y = base_h - wm_h - 20
        if wm_resized.mode == 'RGBA':
            img_copy.paste(wm_resized, (paste_x, paste_y), wm_resized)
        else:
            img_copy.paste(wm_resized, (paste_x, paste_y))
    else:
        for i in range(count):
            if count > 1:
                paste_y = int(20 + (base_h - wm_h - 40) * (i / (count - 1)))
            else:
                paste_y = (base_h - wm_h) // 2
                
            if i % 3 == 0:
                paste_x = 20
            elif i % 3 == 1:
                paste_x = (base_w - wm_w) // 2
            else:
                paste_x = base_w - wm_w - 20
                
            if wm_resized.mode == 'RGBA':
                img_copy.paste(wm_resized, (paste_x, paste_y), wm_resized)
            else:
                img_copy.paste(wm_resized, (paste_x, paste_y))
                
    return img_copy

def process_single_chapter(images, max_split_height, output_format, jpeg_quality, no_crop, enable_watermark, watermark_image, watermark_count, mode_2in1, credit_image, is_manga_mode, watermark_distribution):
    """پڕۆسێس کردنی یەک لیست لە وێنەکان (بۆ مانهوا یان مانگا)"""
    num_pages = len(images)
    
    # --- بەشی نوێ: ئەگەر مۆدی مانگا هەڵبژێردرابوو (بێ دەمج و بڕین، تەنها لۆگۆ) ---
    if is_manga_mode:
        # دیاریکردنی ئەو لاپەڕانەی کە لۆگۆیان لێدەدرێت بەپێی ویستی بەکارهێنەر
        if enable_watermark and watermark_image:
            if watermark_distribution == "لەسەر ١٠ لاپەڕە بە هەڕەمەکی":
                wm_indices = set(random.sample(range(num_pages), min(10, num_pages)))
            elif watermark_distribution == "لەسەر ٢٠ لاپەڕە بە هەڕەمەکی":
                wm_indices = set(random.sample(range(num_pages), min(20, num_pages)))
            else:  # لەسەر هەموو لاپەڕەکان
                wm_indices = set(range(num_pages))
        else:
            wm_indices = set()

        output_parts = []
        for idx, img in enumerate(images):
            img_copy = img.copy()
            # لۆگۆ لێدان ئەگەر ئەپڵۆد کرابوو و ناوی لە لیستی لاپەڕە هەڵبژێردراوەکاندا بوو
            if idx in wm_indices:
                img_copy = apply_watermark(img_copy, watermark_image, watermark_count)
            output_parts.append(img_copy)
            
        # زیادکردنی لاپەڕەی کرێدیت لە کۆتایی ئەگەر هەبێت
        if credit_image:
            output_parts.append(credit_image.copy())
            
        return output_parts, []

    # --- مۆدەکانی مانهوا (لکاندنی گشتی و ڕێکخستنی قەبارە) ---
    if credit_image:
        images.append(credit_image.copy())
        
    target_width = images[0].width
    resized_images = []
    
    for img in images:
        if img.width != target_width:
            aspect_ratio = img.height / img.width
            new_height = int(target_width * aspect_ratio)
            img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
        resized_images.append(img)

    # مۆدی دوو لەیەک (2-in-1)
    if mode_2in1:
        paired_outputs = []
        for i in range(0, len(resized_images), 2):
            pair = resized_images[i:i+2]
            pair_w = target_width
            pair_h = sum(img.height for img in pair)
            
            img_mode = "RGB" if output_format in ["JPEG", "JPG"] else "RGBA"
            combined_pair = Image.new(img_mode, (pair_w, pair_h))
            
            curr_y = 0
            for img in pair:
                combined_pair.paste(img, (0, curr_y))
                curr_y += img.height
                
            combined_pair = combined_pair.resize((pair_w, max_split_height), Image.Resampling.LANCZOS)
            
            if enable_watermark and watermark_image:
                combined_pair = apply_watermark(combined_pair, watermark_image, watermark_count)
                
            paired_outputs.append(combined_pair)
        return paired_outputs, []

    # پڕۆسەی ئاسایی مانهوا
    total_height = sum(img.height for img in resized_images)
    img_mode = "RGB" if output_format in ["JPEG", "JPG"] else "RGBA"
    stitched_image = Image.new(img_mode, (target_width, total_height))
    
    current_y = 0
    for img in resized_images:
        stitched_image.paste(img, (0, current_y))
        current_y += img.height
        
    if no_crop:
        final_img = stitched_image
        if enable_watermark and watermark_image:
            final_img = apply_watermark(final_img, watermark_image, watermark_count)
        return [final_img], []

    # بڕینی زیرەک بۆ مانهوا
    img_np = np.array(stitched_image)
    start_y = 0
    steps = []
    
    while start_y < total_height:
        if start_y + max_split_height >= total_height:
            end_y = total_height
        else:
            estimated_end_y = start_y + max_split_height
            end_y = find_smart_split_row(img_np, estimated_end_y)
            if total_height - end_y < 500:
                end_y = total_height
                
        steps.append((start_y, end_y))
        start_y = end_y

    output_parts = []
    for s_y, e_y in steps:
        crop_box = (0, s_y, target_width, e_y)
        cropped_part = stitched_image.crop(crop_box)
        
        if enable_watermark and watermark_image:
            cropped_part = apply_watermark(cropped_part, watermark_image, watermark_count)
            
        output_parts.append(cropped_part)
        
    return output_parts, steps

# نمایشکردنی لۆگۆ لە ڕووکاری سایتەکە
if os.path.exists("logo_black.png"):
    col_empty, col_logo = st.columns([3, 1])
    with col_logo:
        st.image("logo_black.png", use_container_width=True)

st.title("📜 ئامرازی لکاندن و لۆگۆ لێدانی مانهوا و مانگا Pro")
st.write("وەشانی نوێ: پشتگیری مۆدی مانگا (پاراستنی لاپەڕەکان + لۆگۆی هەڕەمەکی) بۆ یەک بەش یان بە کۆمەڵ (Batch).")

# جۆری داخڵکردن
input_mode = st.radio("شێوازی داخڵکردنی فایلەکان هەڵبژێرە:", ["وێنە بە جیا (تەنها یەک بەش)", "فایلی ZIP پێکەوە (چەندین بەش پێکەوە - Batch)"], horizontal=True)

uploaded_files = None
uploaded_zip = None

if input_mode == "وێنە بە جیا (تەنها یەک بەش)":
    uploaded_files = st.file_uploader("وێنەکان دەستنیشان بکە...", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
else:
    uploaded_zip = st.file_uploader("فایلی ZIPی سەرەکی ئەپڵۆد بکە (کە فۆڵدەری بەشەکانی تێدایە)...", type=["zip"])

st.write("---")
st.subheader("⚙️ ڕێکخستنەکانی جۆری پڕۆژە")

# لێرەدا بژاردەی مانگا زیادکراوە
mode_selection = st.selectbox("شێوازی کارکردن (مۆدی پڕۆژە):", [
    "بڕینی زیرەک (Smart Split) - بۆ مانهوا", 
    "دوو لاپەڕە لە یەک لاپەڕەدا (2-in-1) - بۆ مانهوا", 
    "دەمجکردن بەبێ بڕینەوە (تەواوی بەشەکە یەک وێنە)",
    "مانگا (پاراستنی لاپەڕە جیاوازەکان وەک خۆی + لۆگۆ لێدان)"
])

no_crop = (mode_selection == "دەمجکردن بەبێ بڕینەوە (تەواوی بەشەکە یەک وێنە)")
mode_2in1 = (mode_selection == "دوو لاپەڕە لە یەک لاپەڕەدا (2-in-1) - بۆ مانهوا")
is_manga_mode = (mode_selection == "مانگا (پاراستنی لاپەڕە جیاوازەکان وەک خۆی + لۆگۆ لێدان)")

col1, col2 = st.columns(2)
with col1:
    output_format = st.selectbox("فۆرماتی وێنە دەرچووەکان:", ["JPEG", "JPG", "PNG"])
with col2:
    # بەرزی تەنها بۆ مۆدەکانی مانهوا گرنگە، بۆ مانگا ناچالاک دەبێت
    max_split_height = st.number_input("بەرزی لاپەڕەکانی مانهوا (پێکسڵ):", min_value=1000, max_value=10000, value=3000, disabled=is_manga_mode)

jpeg_quality = 90
if output_format in ["JPEG", "JPG"]:
    jpeg_quality = st.slider("کوالیتی وێنەکان (Quality):", 70, 100, 90)

file_prefix = st.text_input("پێشگری ناوی فایلەکان:", value="page")

# --- بەشی واتەرمارک لەگەڵ نوێکارییەکەی مانگا ---
st.write("---")
st.subheader("🛡️ ڕێکخستنی واتەرمارک (Watermark)")
enable_watermark = st.checkbox("زیادکردنی لۆگۆی کوردسەب وەک واتەرمارک بۆ سەر لاپەڕەکان", value=False)

watermark_image = None
watermark_count = 1
watermark_distribution = "لەسەر هەموو لاپەڕەکان"

if enable_watermark:
    col_wm1, col_wm2 = st.columns(2)
    with col_wm1:
        wm_color = st.radio("ڕەنگی لۆگۆی واتەرمارکەکە:", ["سپی (White)", "ڕەش (Black)"], horizontal=True)
    with col_wm2:
        watermark_count = st.slider("ژمارەی دووبارەبوونەوەی لۆگۆ لەسەر *هەر یەک* لاپەڕە:", 1, 10, 1)
        
    # ئەگەر مۆدی مانگا بوو، ئۆپشنی دابەشکردنی لۆگۆ بە هەڕەمەکی پیشان بدە
    if is_manga_mode:
        watermark_distribution = st.radio(
            "شێوازی بڵاوبوونەوەی لۆگۆ لەناو بەشەکەدا (تایبەت بە مانگا):",
            ["لەسەر هەموو لاپەڕەکان", "لەسەر ١٠ لاپەڕە بە هەڕەمەکی", "لەسەر ٢٠ لاپەڕە بە هەڕەمەکی"],
            horizontal=True
        )
        
    if wm_color == "سپی (White)" and os.path.exists("logo_white.png"):
        watermark_image = Image.open("logo_white.png")
    elif wm_color == "ڕەش (Black)" and os.path.exists("logo_black.png"):
        watermark_image = Image.open("logo_black.png")
    else:
        uploaded_wm = st.file_uploader("فایلی لۆگۆکە ئەپڵۆد بکە (PNG):", type=["png"])
        if uploaded_wm:
            watermark_image = Image.open(uploaded_wm)

# خوێندنەوەی لاپەڕەی کرێدیت
credit_image = None
if os.path.exists("credit_page.png"):
    credit_image = Image.open("credit_page.png")

# --- جێبەجێکردنی کارەکە ---
if st.button("🚀 دەستپێکردنی پڕۆسە"):
    save_format = "JPEG" if output_format in ["JPEG", "JPG"] else "PNG"
    ext = "jpg" if output_format in ["JPEG", "JPG"] else "png"
    final_zip_buffer = io.BytesIO()
    
    # ١. مۆدی یەک بەش (وێنەی جیاواز)
    if input_mode == "وێنە بە جیا (تەنها یەک بەش)" and uploaded_files:
        sorted_files = sorted(uploaded_files, key=lambda x: natural_sort_key(x.name))
        chapter_images = [Image.open(f) for f in sorted_files]
        
        with st.spinner("خەریکە پڕۆسێس دەکرێت..."):
            output_parts, steps = process_single_chapter(
                chapter_images, max_split_height, output_format, jpeg_quality, 
                no_crop, enable_watermark, watermark_image, watermark_count, mode_2in1, credit_image,
                is_manga_mode, watermark_distribution
            )
            
            with zipfile.ZipFile(final_zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, part in enumerate(output_parts):
                    img_byte_arr = io.BytesIO()
                    if save_format == "JPEG":
                        part.convert("RGB").save(img_byte_arr, format=save_format, quality=jpeg_quality)
                    else:
                        part.save(img_byte_arr, format=save_format)
                    zip_file.writestr(f"{file_prefix}_{idx+1:02d}.{ext}", img_byte_arr.getvalue())
            
            # پێشبینی هێڵەکان (تەنها بۆ مانهوا و بڕینی زیرەک)
            if steps and len(chapter_images) > 0 and not is_manga_mode:
                st.write("---")
                st.subheader("📊 پێشبینی هێڵەکانی بڕین:")
                total_h = sum(img.height for img in chapter_images)
                preview_w = 150
                preview_h = min(2000, int(total_h * (preview_w / chapter_images[0].width)))
                preview_img = Image.new("RGB", (preview_w, preview_h), "#222222")
                draw = ImageDraw.Draw(preview_img)
                for _, e_y in steps[:-1]:
                    scaled_y = int(e_y * (preview_h / total_h))
                    draw.line([(0, scaled_y), (preview_w, scaled_y)], fill="red", width=2)
                st.image(preview_img, caption="شوێنی بڕینەکان")

        st.success("تەواو! بەشەکە بە سەرکەوتوویی ئامادەکرا.")
        st.download_button(label="📥 داگرتنی بەشەکە (ZIP)", data=final_zip_buffer.getvalue(), file_name="manga_chapter.zip", mime="application/zip")

   # ٢. مۆدی بە کۆمەڵ (Batch Processing) - بۆ مانهوا یان مانگا پێکەوە
    elif input_mode == "فایلی ZIP پێکەوە (چەندین بەش پێکەوە - Batch)" and uploaded_zip:
        with zipfile.ZipFile(uploaded_zip, "r") as in_zip:
            chapters_dict = {}
            for file_path in in_zip.namelist():
                # فلتەرکردنی فۆڵدەرەکان و فایلە شاردراوەکانی سیستەم
                if file_path.endswith('/') or '__MACOSX' in file_path or file_path.startswith('.'):
                    continue
                
                # 🛑 چارەسەری سەرەکی: دڵنیابوونەوە لەوەی فایلەکە بە ڕاستی وێنەیە
                if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                
                parts = file_path.split('/')
                ch_name = parts[-2] if len(parts) > 1 else "General_Pages"
                if ch_name not in chapters_dict:
                    chapters_dict[ch_name] = []
                chapters_dict[ch_name].append(file_path)
            
            if chapters_dict:
                progress_bar = st.progress(0.0)
                ch_keys = list(chapters_dict.keys())
                
                with zipfile.ZipFile(final_zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as out_zip:
                    for ch_idx, ch_name in enumerate(ch_keys):
                        st.write(f"خەریکە بەشی: `{ch_name}` پڕۆسێس دەکرێت...")
                        sorted_paths = sorted(chapters_dict[ch_name], key=natural_sort_key)
                        
                        images = []
                        for path in sorted_paths:
                            with in_zip.open(path) as f:
                                # خوێندنەوەی بێ کێشەی وێنەکە بۆ ناو میمۆری
                                img_data = io.BytesIO(f.read())
                                img = Image.open(img_data)
                                img.load()  
                                images.append(img)
                        
                        output_parts, _ = process_single_chapter(
                            images, max_split_height, output_format, jpeg_quality, 
                            no_crop, enable_watermark, watermark_image, watermark_count, mode_2in1, credit_image,
                            is_manga_mode, watermark_distribution
                        )
                        
                        for idx, part in enumerate(output_parts):
                            img_byte_arr = io.BytesIO()
                            if save_format == "JPEG":
                                part.convert("RGB").save(img_byte_arr, format=save_format, quality=jpeg_quality)
                            else:
                                part.save(img_byte_arr, format=save_format)
                            out_zip.writestr(f"{ch_name}/{file_prefix}_{idx+1:02d}.{ext}", img_byte_arr.getvalue())
                            
                        progress_bar.progress((ch_idx + 1) / len(ch_keys))
                
                st.success("هەموو بەشەکان بە سەرکەوتوویی ڕێکخران!")
                st.download_button(label="📥 داگرتنی هەموو بەشەکان (Batch ZIP)", data=final_zip_buffer.getvalue(), file_name="kurdsubtitle_manga_batch.zip", mime="application/zip")
            else:
                st.error("هیچ فۆڵدەر یان وێنەیەکی دروست لەناو فایلی زپەکەدا نەدۆزرایەوە.")
