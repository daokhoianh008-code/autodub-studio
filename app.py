import asyncio
import json
import os
import subprocess
import tempfile
import edge_tts
from google import genai
from google.genai import types
import streamlit as st

# ================= CẤU HÌNH THƯƠNG HIỆU CỦA BẠN =================
APP_TITLE = "AUTO DUB STUDIO"
SUB_TITLE = "Tự động dịch phụ đề, lồng tiếng AI & xuất video hoàn chỉnh"
AUTHOR_INFO = "Phát triển bởi Đào Khởi Anh • Miễn phí 100%"
# ===============================================================

icon_path = "logo.png" if os.path.exists("logo.png") else "🎬"
st.set_page_config(page_title=APP_TITLE, page_icon=icon_path, layout="centered")

if os.path.exists("logo.png"):
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image("logo.png", width=110)

st.markdown(
    f"<h2 style='text-align: center; margin-bottom: 0;'>{APP_TITLE}</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='text-align: center; color: #A0A0A0; font-size: 15px;'>{SUB_TITLE}</p>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='text-align: center; color: #4DA8DA; font-size: 13px;'>{AUTHOR_INFO}</p>",
    unsafe_allow_html=True,
)
st.divider()

# Khu vực nhập API Key kèm hướng dẫn cho người dùng phổ thông
api_key = st.text_input(
    "🔑 Dán Gemini API Key của bạn:",
    type="password",
    placeholder="Mã bắt đầu bằng AIzaSy...",
)
with st.expander("❓ Chưa có API Key? Bấm vào đây để lấy miễn phí trong 30 giây"):
    st.markdown("""
    1. Truy cập **[Google AI Studio](https://aistudio.google.com/app/apikey)** và đăng nhập bằng Gmail.
    2. Bấm nút **Create API key** (Tạo khóa API).
    3. Copy đoạn mã hiện ra và dán vào ô phía trên (Hoàn toàn miễn phí, hệ thống không lưu lại mã của bạn).
    """)

uploaded_file = st.file_uploader(
    "🎬 Tải lên video hoặc file âm thanh gốc (MP4, MOV, MP3):",
    type=["mp4", "mov", "mkv", "mp3", "wav"],
)

col_v1, col_v2 = st.columns(2)
with col_v1:
    voice_map = {
        "Nam Minh (Giọng Nam trầm kể chuyện)": "vi-VN-NamMinhNeural",
        "Hoài My (Giọng Nữ truyền cảm)": "vi-VN-HoaiMyNeural",
    }
    selected_voice = st.selectbox("🗣️ Chọn giọng đọc AI:", list(voice_map.keys()))
    voice_code = voice_map[selected_voice]

with col_v2:
    style_option = st.selectbox(
        "✍️ Phong cách dịch thuật:",
        [
            "Kể chuyện kịch tính, lôi cuốn, cô đọng",
            "Tự nhiên, đời thường, dễ hiểu",
            "Hài hước, trẻ trung kiểu TikTok/Shorts",
        ],
    )

burn_sub = st.checkbox(
    "🔥 Tự động ghép thành Video hoàn chỉnh (tắt tiếng gốc + lồng tiếng + gắn phụ đề)",
    value=True,
)


def get_duration(file_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def format_srt_time(seconds):
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def generate_tts(text, voice, out_path):
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(out_path)


if st.button("🚀 BẮT ĐẦU TẠO LỒNG TIẾNG", use_container_width=True, type="primary"):
    if not api_key:
        st.warning("⚠️ Bạn hãy dán Gemini API Key vào ô phía trên trước nhé!")
    elif not uploaded_file:
        st.warning("⚠️ Bạn chưa chọn file video hoặc âm thanh nào!")
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            status = st.status("Đang xử lý tự động...", expanded=True)
            try:
                is_video = uploaded_file.name.lower().endswith((".mp4", ".mov", ".mkv"))
                input_ext = os.path.splitext(uploaded_file.name)[1].lower()
                input_path = os.path.join(tmpdir, f"input_source{input_ext}")

                with open(input_path, "wb") as f:
                    f.write(uploaded_file.read())

                status.write("1/5 Đang tách âm thanh từ file gốc...")
                raw_audio = os.path.join(tmpdir, "extracted.mp3")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        input_path,
                        "-vn",
                        "-acodec",
                        "libmp3lame",
                        "-q:a",
                        "4",
                        raw_audio,
                    ],
                    check=True,
                    capture_output=True,
                )

                status.write("2/5 AI đang nghe hiểu và dịch lời thoại sang tiếng Việt...")
                client = genai.Client(api_key=api_key.strip())
                gemini_file = client.files.upload(file=raw_audio)

                prompt = f"""Nghe file âm thanh này, tách từng câu thoại kèm mốc thời gian chính xác (tính bằng giây) và dịch sang tiếng Việt theo phong cách: {style_option}.
Yêu cầu: Câu dịch tiếng Việt phải tự nhiên, cô đọng để đọc vừa khít khoảng thời gian của câu gốc.
Trả về duy nhất một mảng JSON đúng định dạng sau, không thêm giải thích:
[
  {{"start": 0.5, "end": 3.2, "text": "Câu dịch tiếng Việt thứ nhất"}},
  {{"start": 3.5, "end": 6.0, "text": "Câu dịch tiếng Việt thứ hai"}}
]"""

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[gemini_file, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
                try:
                    client.files.delete(name=gemini_file.name)
                except Exception:
                    pass

                segments = json.loads(response.text)
                if not segments:
                    raise ValueError("Không phát hiện lời thoại trong file này.")
                segments.sort(key=lambda x: float(x["start"]))

                status.write("3/5 Đang tạo giọng đọc AI và căn chỉnh khớp thời gian...")
                concat_lines = []
                srt_lines = []
                current_time = 0.0

                for idx, seg in enumerate(segments, start=1):
                    start = float(seg["start"])
                    end = float(seg["end"])
                    text = seg["text"].strip()
                    if not text:
                        continue

                    if start > current_time + 0.05:
                        gap_dur = start - current_time
                        gap_file = os.path.join(tmpdir, f"gap_{idx}.mp3")
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-f",
                                "lavfi",
                                "-i",
                                "anullsrc=r=24000:cl=mono",
                                "-t",
                                f"{gap_dur:.3f}",
                                "-q:a",
                                "9",
                                gap_file,
                            ],
                            check=True,
                            capture_output=True,
                        )
                        concat_lines.append(f"file '{gap_file}'")
                        current_time = start

                    seg_raw = os.path.join(tmpdir, f"seg_raw_{idx}.mp3")
                    seg_final = os.path.join(tmpdir, f"seg_final_{idx}.mp3")
                    asyncio.run(generate_tts(text, voice_code, seg_raw))

                    seg_dur = get_duration(seg_raw)
                    allowed_dur = max(end - start, 0.4)

                    if seg_dur > allowed_dur:
                        speed = min(seg_dur / allowed_dur, 1.45)
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-i",
                                seg_raw,
                                "-filter:a",
                                f"atempo={speed:.2f}",
                                seg_final,
                            ],
                            check=True,
                            capture_output=True,
                        )
                    else:
                        seg_final = seg_raw

                    actual_dur = get_duration(seg_final)
                    concat_lines.append(f"file '{seg_final}'")

                    srt_end = max(end, current_time + actual_dur)
                    srt_lines.append(
                        f"{idx}\n{format_srt_time(current_time)} --> {format_srt_time(srt_end)}\n{text}\n"
                    )
                    current_time += actual_dur

                status.write("4/5 Đang xuất file âm thanh lồng tiếng & phụ đề SRT...")
                list_txt = os.path.join(tmpdir, "concat.txt")
                with open(list_txt, "w", encoding="utf-8") as f:
                    f.write("\n".join(concat_lines))

                final_mp3 = os.path.join(tmpdir, "long_tieng_viet.mp3")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        list_txt,
                        "-acodec",
                        "libmp3lame",
                        "-b:a",
                        "128k",
                        final_mp3,
                    ],
                    check=True,
                    capture_output=True,
                )

                srt_content = "\n".join(srt_lines)
                srt_path = os.path.join(tmpdir, "phu_de_viet.srt")
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)

                video_bytes = None
                if is_video and burn_sub:
                    status.write("5/5 Đang ghép tiếng Việt và gắn cứng phụ đề vào Video...")
                    final_mp4 = os.path.join(tmpdir, "video_hoan_chinh.mp4")
                    sub_style = (
                        "FontName=Noto Sans,FontSize=18,PrimaryColour=&H00FFFFFF,"
                        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=25"
                    )
                    vf_filter = f"scale=trunc(iw/2)*2:trunc(ih/2)*2,subtitles=phu_de_viet.srt:force_style='{sub_style}'"
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            f"input_source{input_ext}",
                            "-i",
                            "long_tieng_viet.mp3",
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0",
                            "-vf",
                            vf_filter,
                            "-c:v",
                            "libx264",
                            "-preset",
                            "fast",
                            "-crf",
                            "23",
                            "-c:a",
                            "aac",
                            "-b:a",
                            "128k",
                            "video_hoan_chinh.mp4",
                        ],
                        cwd=tmpdir,
                        check=True,
                        capture_output=True,
                    )
                    with open(final_mp4, "rb") as f:
                        video_bytes = f.read()
                else:
                    status.write("5/5 Hoàn tất đóng gói dữ liệu...")

                with open(final_mp3, "rb") as f:
                    mp3_bytes = f.read()

                status.update(
                    label="✅ Hoàn tất! Xem thử và tải thành phẩm bên dưới.",
                    state="complete",
                )

                if video_bytes:
                    st.video(video_bytes)
                    st.download_button(
                        "🎬 TẢI VIDEO HOÀN CHỈNH (.mp4)",
                        data=video_bytes,
                        file_name="video_long_tieng.mp4",
                        mime="video/mp4",
                        use_container_width=True,
                        type="primary",
                    )

                st.audio(mp3_bytes, format="audio/mpeg")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        "⬇️ Tải Giọng Đọc (.mp3)",
                        data=mp3_bytes,
                        file_name="long_tieng_viet.mp3",
                        mime="audio/mpeg",
                        use_container_width=True,
                    )
                with col_d2:
                    st.download_button(
                        "⬇️ Tải Phụ Đề (.srt)",
                        data=srt_content.encode("utf-8"),
                        file_name="phu_de_viet.srt",
                        mime="text/plain",
                        use_container_width=True,
                    )

            except Exception as e:
                status.update(label="❌ Có lỗi xảy ra", state="error")
                st.error(
                    f"Không thể xử lý file này. Hãy kiểm tra lại API Key hoặc thử video ngắn hơn. (Chi tiết: {e})"
                )
