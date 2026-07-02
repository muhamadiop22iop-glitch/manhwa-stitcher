import io
import os
import re
import zipfile
import numpy as np
import streamlit as st
from PIL import Image

# ڕێکخستنی لاپەڕەی وێبەکە
st.set_page_config(page_title="Manhwa Stitcher - Kurdsubtitle", page_icon="📜", layout="centered")

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

def apply_watermark(base_img, watermark_img):
    """دانانی لۆگۆ لە گۆشەی خوارەوەی لای ڕاستی وێنەکە"""
    base_w, base_h = base_img.size
    wm_w = max(40, int(base_w * 0.12))
    wm_h = int(watermark_img.height * (wm_w / watermark_img.width))
    wm_resized = watermark_img.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
    
    paste_x = base_w - wm_w - 20
    paste_y = base_h - wm_h - 20
    
    img_copy = base_img.copy()
    if wm_resized.mode == 'RGBA':
        img_copy.paste(wm_resized, (paste_x, paste_y), wm_resized)
    else:
        img_copy.paste(wm_resized, (paste_x, paste_y))
    return img_copy

# --- بەشی چوارەم: پیشاندانی لۆگۆ ڕەشەکەی کوردسەب لە ڕووکاری سایتەکە ---
logo_black_found = False
if os.path.exists("logo_black.png"):
    col_empty, col_logo = st.columns([3, 1])
    with col_logo:
        st.image("logo_black.png", use_container_width=True)
    logo_black_found = True
else:
    st.info("💡 ڕێنمایی: فایلی logo_black.png لە GitHub ئەپڵۆد بکە تا لۆگۆی ڕەشی سایتەکە لێرە دەربکەوێت.")

# سەر دێڕی سایتەکە
st.title("📜 ئامرازی لکاندنی لاپەڕەکانی مانهوا (کوردسەب)")
st.write("تایبەت بە ڕێکخستن، لکاندن و بڕینی زیرەکی وێنەکانی مانهوا و مانگا.")

uploaded_files = st.file_uploader(
    "وێنەکانی مانهوا دەستنیشان بکە...", 
    type=["png", "jpg", "jpeg", "webp"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"تەواو! ({len(uploaded_files)}) وێنە لۆد کران.")
    
    col1, col2 = st.columns(2)
    with col1:
        output_format = st.selectbox("فۆرماتی وێنەکان:", ["JPEG", "JPG", "PNG"])
    with col2:
        max_split_height = st.number_input("بەرزی هەر لاپەڕەیەک (پێکسڵ):", min_value=1000, max_value=10000, value=3000)
        
    no_crop = st.checkbox("دەمجکردن بەبێ بڕینەوە (تەواوی وێنەکان پێکەوە ببنە یەک وێنە)")
    
    jpeg_quality = 90
    if output_format in ["JPEG", "JPG"]:
        jpeg_quality = st.slider("کوالیتی وێنەکان (Quality):", 70, 100, 90)

    # --- بەشی سێیەم: ڕێکخستنی واتەرمارکی دووانە (سپی و ڕەش) ---
    st.write("---")
    st.subheader("🛡️ ڕێکخستنی واتەرمارک (Watermark)")
    enable_watermark = st.checkbox("زیادکردنی لۆگۆی کوردسەب وەک واتەرمارک بۆ سەر لاپەڕەکان", value=False)
    
    watermark_image = None
    if enable_watermark:
        # هەڵبژاردنی ڕەنگی واتەرمارک
        wm_color = st.radio("ڕەنگی لۆگۆی واتەرمارکەکە هەڵبژێرە:", ["سپی (White)", "ڕەش (Black)"], horizontal=True)
        
        if wm_color == "سپی (White)":
            if os.path.exists("logo_white.png"):
                watermark_image = Image.open("logo_white.png")
            else:
                uploaded_white = st.file_uploader("فایلی لۆگۆ سپییەکە لێرە ئەپڵۆد بکە (PNG):", type=["png"])
                if uploaded_white:
                    watermark_image = Image.open(uploaded_white)
        else:
            if os.path.exists("logo_black.png"):
                watermark_image = Image.open("logo_black.png")
            else:
                uploaded_black = st.file_uploader("فایلی Lۆگۆ ڕەشەکە لێرە ئەپڵۆد بکە (PNG):", type=["png"])
                if uploaded_black:
                    watermark_image = Image.open(uploaded_black)

    # دوگمەی دەستپێکردن
    if st.button("دەستپێکردنی پڕۆسەکە"):
        if enable_watermark and watermark_image is None:
            st.error("تکایە سەرەتا فایلی لۆگۆی دیاریکراو دابنێ یان ئەپڵۆدی بکە.")
        else:
            uploaded_files = sorted(uploaded_files, key=lambda x: natural_sort_key(x.name))
            images = [Image.open(file) for file in uploaded_files]
            target_width = images[0].width
            
            resized_images = []
            total_height = 0
            
            progress_bar = st.progress(0.0)
            st.write("خەریکە قەبارەی وێنەکان یەکدەخرێت...")
            
            for idx, img in enumerate(images):
                if img.width != target_width:
                    aspect_ratio = img.height / img.width
                    new_height = int(target_width * aspect_ratio)
                    img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
                
                resized_images.append(img)
                total_height += img.height
                progress_bar.progress(0.1 + (idx / len(images)) * 0.2)
                
            mode = "RGB" if output_format in ["JPEG", "JPG"] else "RGBA"
            stitched_image = Image.new(mode, (target_width, total_height))
            
            current_y = 0
            for img in resized_images:
                stitched_image.paste(img, (0, current_y))
                current_y += img.height
                
            progress_bar.progress(0.4)
            st.write("خەریکە بڕینەوەی زیرەک جێبەجێ دەکرێت...")

            save_format = "JPEG" if output_format in ["JPEG", "JPG"] else "PNG"
            ext = "jpg" if output_format in ["JPEG", "JPG"] else "png"

            if no_crop:
                final_img = stitched_image
                if enable_watermark and watermark_image is not None:
                    final_img = apply_watermark(final_img, watermark_image)
                    
                img_byte_arr = io.BytesIO()
                if save_format == "JPEG":
                    final_img.convert("RGB").save(img_byte_arr, format=save_format, quality=jpeg_quality)
                else:
                    final_img.save(img_byte_arr, format=save_format)
                
                progress_bar.progress(1.0)
                st.download_button(label="📥 داگرتنی وێنە لکێنراوەکە", data=img_byte_arr.getvalue(), file_name=f"full_manga.{ext}", mime=f"image/{ext}")
                
            else:
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

                zip_buffer = io.BytesIO()
                total_steps = len(steps)
                
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for idx, (s_y, e_y) in enumerate(steps):
                        crop_box = (0, s_y, target_width, e_y)
                        cropped_part = stitched_image.crop(crop_box)
                        
                        if enable_watermark and watermark_image is not None:
                            cropped_part = apply_watermark(cropped_part, watermark_image)
                        
                        img_byte_arr = io.BytesIO()
                        if save_format == "JPEG":
                            cropped_part.convert("RGB").save(img_byte_arr, format=save_format, quality=jpeg_quality)
                            filename = f"page_{idx+1:02d}.jpg"
                        else:
                            cropped_part.save(img_byte_arr, format=save_format)
                            filename = f"page_{idx+1:02d}.png"
                            
                        zip_file.writestr(filename, img_byte_arr.getvalue())
                        progress_bar.progress(0.4 + ((idx + 1) / total_steps) * 0.6)
                
                st.success("کارەکە بە سەرکەوتوویی کۆتایی هات!")
                st.download_button(label="📥 داگرتنی هەموو لاپەڕەکان (ZIP)", data=zip_buffer.getvalue(), file_name="manga_pages.zip", mime="application/zip")
