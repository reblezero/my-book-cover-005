import streamlit as st
import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import urllib.parse
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# --- 설정값 (JPG 품질 및 레이아웃) ---
TARGET_HEIGHT_PX = 400  # 이미지 개별 높이
GAP_PX = 10             # 이미지 사이 간격
CANVAS_WIDTH_PX = 1200  # 결과물 전체 가로 폭

# --- 핵심 기능: 알라딘에서 고화질 표지 수집 ---
def get_high_res_cover(book_title):
    try:
        encoded_title = urllib.parse.quote(book_title)
        url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=All&SearchWord={encoded_title}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.aladin.co.kr/"}
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        boxes = soup.select("div.ss_book_box")
        img_src = None
        for box in boxes:
            box_text = box.get_text()
            if any(x in box_text for x in ["[알라딘 굿즈]", "[음반]", "머그", "[블루레이]"]):
                continue 
            img_tag = box.select_one("img.i_cover") or box.select_one("img.front_cover")
            if img_tag and img_tag.has_attr('src'):
                img_src = img_tag['src']
                break
        if not img_src: return None
        high_res_src = img_src.replace('coversum', 'cover500').replace('cover200', 'cover500').replace('cover150', 'cover500')
        img_res = requests.get(high_res_src, headers=headers, verify=False, timeout=10)
        img = Image.open(BytesIO(img_res.content))
        
        # 높이 기준 리사이즈
        width_ratio = TARGET_HEIGHT_PX / img.height
        target_width_px = int(img.width * width_ratio)
        return img.resize((target_width_px, TARGET_HEIGHT_PX), Image.Resampling.LANCZOS)
    except Exception:
        return None

# --- 웹 화면(UI) 구성 ---
st.set_page_config(page_title="알라딘 JPG 메이커", page_icon="🖼️")
st.title("📚 알라딘 책 표지 JPG 수집기")
st.markdown("책 제목들을 입력하면 하나의 **JPG 이미지**로 합쳐서 내려받을 수 있습니다!")

titles_input = st.text_area("책 제목을 한 줄에 하나씩 입력하세요:", height=150, placeholder="구름 사람들\n파친코\n불편한 편의점")

if st.button("🚀 JPG 이미지 생성 시작!"):
    titles = [t.strip() for t in titles_input.split('\n') if t.strip()]
    if not titles:
        st.warning("제목을 입력해주세요!")
    else:
        images = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i, t in enumerate(titles):
            status_text.text(f"'{t}' 찾는 중... ({i+1}/{len(titles)})")
            img = get_high_res_cover(t)
            if img: images.append(img)
            else: st.toast(f"'{t}' 찾기 실패 ❌")
            progress_bar.progress((i + 1) / len(titles))
            
        if images:
            status_text.text("이미지 합성 중...")
            
            # 가로 폭에 맞춰 줄바꿈 계산
            rows = []
            current_row = []
            current_row_width = 0
            for img in images:
                if current_row_width + img.width + GAP_PX > CANVAS_WIDTH_PX:
                    rows.append(current_row)
                    current_row = [img]
                    current_row_width = img.width
                else:
                    current_row.append(img)
                    current_row_width += img.width + GAP_PX
            rows.append(current_row)
            
            # 캔버스 생성 (흰색 배경)
            final_height = len(rows) * (TARGET_HEIGHT_PX + GAP_PX) + GAP_PX
            canvas = Image.new('RGB', (CANVAS_WIDTH_PX, final_height), (255, 255, 255))
            
            # 이미지 붙여넣기
            curr_y = GAP_PX
            for row in rows:
                curr_x = GAP_PX
                for img in row:
                    canvas.paste(img, (curr_x, curr_y))
                    curr_x += img.width + GAP_PX
                curr_y += TARGET_HEIGHT_PX + GAP_PX
            
            # JPG 데이터로 변환
            buf = BytesIO()
            canvas.save(buf, format="JPEG", quality=95)
            byte_im = buf.getvalue()
            
            st.image(canvas, caption="생성된 이미지 미리보기", use_container_width=True)
            st.success("✅ 모든 이미지가 합쳐졌습니다!")
            
            st.download_button(
                label="📥 합성된 JPG 다운로드",
                data=byte_im,
                file_name=f"covers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                mime="image/jpeg"
            )
        else:
            st.error("이미지를 한 장도 찾지 못했습니다.")