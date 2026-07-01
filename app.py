import io
import re
import zipfile
import numpy as np
import streamlit as st
from PIL import Image

# ڕێکخستنی لاپەڕەی وێبەکە
st.set_page_config(page_title="Manhwa Stitcher", page_icon="📜", layout="centered")

# ستایلێکی کوردی و مۆدێرن بۆ وێبسایتەکە
st.markdown("""
    <style>
    .stApp { background-color: #121212; color: white; }
    h1, h2, h3, p, label { text-align: right; direction: rtl; font-family: 'Arial'; }
    .stButton>button { background-color: #be5a27 !important; color: white !important; width: 100%; font-weight: bold; }
    .stButton>button:hover { background-color: #96431a !important; }
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

# سەر دێڕی سایتەکە
st.title("📜 ئامرازی لکاندنی لاپەڕەکانی مانهوا")
st.write("وێنەکان لێرە دابنێ تا بە شێوازێکی زیرەک پێکەوە بڵکێنرێن و ببڕدرێنەوە.")

# بەشی ئەپڵۆدکردنی وێنەکان
uploaded_files = st.file_uploader("وێنەکانی مانهوا دەستنیشان بکە...", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.success(f"تەواو! ({len(uploaded_files)}) وێنە لۆد کران.")
    
    # ڕێکخستنەکان لەلایەن بەکارهێنەرەوە
    col1, col2 = st.columns(2)
    
    with col1:
        output_format = st.selectbox("فۆرماتی وێنەکان:", ["JPEG", "PNG"])
    with col2:
        max_split_height = st.number_input("بەرزی هەر لاپەڕەیەک (پێکسڵ):", min_value=1000, max_value=10000, value=3000)
        
    no_crop = st.checkbox("دەمجکردن بەبێ بڕینەوە (تەواوی وێنەکان پێکەوە ببنە یەک وێنە)")
    
    jpeg_quality = 90
    if output_format == "JPEG":
        jpeg_quality = st.slider("کوالیتی وێنەکان:", 70, 100, 90)

    # دوگمەی دەستپێکردن
    if st.button("دەستپێکردنی پڕۆسەکە"):
        # ڕێکخستنی ناوەکان بە زنجیرە
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
            
        # دروستکردنی یەک وێنەی گەورە
        mode = "RGB" if output_format == "JPEG" else "RGBA"
        stitched_image = Image.new(mode, (target_width, total_height))
        
        current_y = 0
        for img in resized_images:
            stitched_image.paste(img, (0, current_y))
            current_y += img.height
            
        progress_bar.progress(0.4)
        st.write("خەریکە بڕینەوەی زیرەک جێبەجێ دەکرێت...")

        # ئەگەر تەنها یەک فایلی گەورەی بوو بەبێ بڕینەوە
        if no_crop:
            img_byte_arr = io.BytesIO()
            ext = output_format.lower()
            if output_format == "JPEG":
                stitched_image.save(img_byte_arr, format=output_format, quality=jpeg_quality)
            else:
                stitched_image.save(img_byte_arr, format=output_format)
            
            progress_bar.progress(1.0)
            st.download_button(label="📥 داگرتنی وێنە لکێنراوەکە", data=img_byte_arr.getvalue(), file_name=f"full_manga.{ext}", mime=f"image/{ext}")
            
        else:
            # پڕۆسەی بڕینەوەی زیرەک
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

            # دروستکردنی فایلی ZIP لە ناو میمۆریدا بۆ داگرتن
            zip_buffer = io.BytesIO()
            total_steps = len(steps)
            
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, (s_y, e_y) in enumerate(steps):
                    crop_box = (0, s_y, target_width, e_y)
                    cropped_part = stitched_image.crop(crop_box)
                    
                    img_byte_arr = io.BytesIO()
                    ext = output_format.lower()
                    if output_format == "JPEG":
                        cropped_part.save(img_byte_arr, format=output_format, quality=jpeg_quality)
                        filename = f"page_{idx+1:02d}.jpg"
                    else:
                        cropped_part.save(img_byte_arr, format=output_format)
                        filename = f"page_{idx+1:02d}.png"
                        
                    zip_file.writestr(filename, img_byte_arr.getvalue())
                    progress_bar.progress(0.4 + ((idx + 1) / total_steps) * 0.6)
            
            st.success("کارەکە بە سەرکەوتوویی کۆتایی هات!")
            st.download_button(label="📥 داگرتنی هەموو لاپەڕەکان (ZIP)", data=zip_buffer.getvalue(), file_name="manga_pages.zip", mime="application/zip")