import sys
import subprocess
import threading
import time
import os
import streamlit.components.v1 as components
import json
import requests
import gdown

# Install packages jika belum ada
packages = ["streamlit", "gdown"]
for package in packages:
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import streamlit as st

# Konfigurasi folder Google Drive
DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1d7fpbrOI9q9Yl6w99-yZGNMB30XNyugf"
DRIVE_FOLDER_ID = "1d7fpbrOI9q9Yl6w99-yZGNMB30XNyugf"

def get_drive_video_list():
    """Mengambil daftar video dari folder Google Drive menggunakan gdown"""
    try:
        # Gunakan gdown untuk mengambil info file dari folder
        file_infos = gdown.download_folder(url=DRIVE_FOLDER_URL, quiet=True, remain=False)
        
        videos = []
        if file_infos:
            for file_info in file_infos:
                if file_info.get('name', '').lower().endswith(('.mp4', '.flv', '.mov', '.avi')):
                    video_info = {
                        'title': file_info['name'],
                        'id': file_info['id']
                    }
                    videos.append(video_info)
        return videos
    except Exception as e:
        st.error(f"Gagal mengambil daftar video dari Google Drive: {str(e)}")
        return []

def download_video_from_drive(file_id, filename):
    """Download video dari Google Drive"""
    try:
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, filename, quiet=False)
        return True
    except Exception as e:
        st.error(f"Gagal mendownload video: {str(e)}")
        return False

def run_ffmpeg(video_path, stream_key, is_shorts, log_callback):
    output_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
    cmd = [
        "ffmpeg", "-re", "-stream_loop", "-1", "-i", video_path,
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "2500k",
        "-maxrate", "2500k", "-bufsize", "5000k",
        "-g", "60", "-keyint_min", "60",
        "-c:a", "aac", "-b:a", "128k",
        "-f", "flv"
    ]
    
    if is_shorts:
        cmd.extend(["-vf", "scale=720:1280"])
    
    cmd.append(output_url)
    log_callback(f"Menjalankan: {' '.join(cmd)}")
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            log_callback(line.strip())
        process.wait()
    except Exception as e:
        log_callback(f"Error: {e}")
    finally:
        log_callback("Streaming selesai atau dihentikan.")

def main():
    # Page configuration
    st.set_page_config(
        page_title="Streaming YT by didinchy",
        page_icon="📈",
        layout="wide"
    )
    st.title("Live Streaming Loss Doll")
    
    # Inisialisasi session state
    if 'drive_videos' not in st.session_state:
        st.session_state.drive_videos = []
    if 'selected_local_video' not in st.session_state:
        st.session_state.selected_local_video = None
    if 'selected_drive_video' not in st.session_state:
        st.session_state.selected_drive_video = None
    if 'downloaded_video_path' not in st.session_state:
        st.session_state.downloaded_video_path = None
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    if 'streaming' not in st.session_state:
        st.session_state.streaming = False
    if 'ffmpeg_thread' not in st.session_state:
        st.session_state.ffmpeg_thread = None

    # Bagian iklan baru
    show_ads = st.checkbox("Tampilkan Iklan", value=True)
    if show_ads:
        st.subheader("Iklan Sponsor")
        components.html(
            """
            <div style="background:#f0f2f6;padding:20px;border-radius:10px;text-align:center">
                <script type='text/javascript' 
                        src='//pl26562103.profitableratecpm.com/28/f9/95/28f9954a1d5bbf4924abe123c76a68d2.js'>
                </script>
                <p style="color:#888">Iklan akan muncul di sini</p>
            </div>
            """,
            height=300
        )

    # Tab untuk pemilihan video
    tab1, tab2, tab3 = st.tabs(["Video Lokal", "Video Google Drive", "Upload Video"])

    # Tab 1: Video Lokal
    with tab1:
        st.subheader("Video yang tersedia di lokal:")
        video_files = [f for f in os.listdir('.') if f.endswith(('.mp4', '.flv', '.mov', '.avi'))]
        if video_files:
            selected_local = st.selectbox("Pilih video lokal", video_files, key="local_select")
            if selected_local:
                st.session_state.selected_local_video = selected_local
        else:
            st.info("Tidak ada video lokal ditemukan")

    # Tab 2: Video Google Drive
    with tab2:
        st.subheader("Video dari Google Drive")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Ambil Daftar Video dari Drive"):
                with st.spinner("Mengambil daftar video dari Google Drive..."):
                    drive_videos = get_drive_video_list()
                    st.session_state.drive_videos = drive_videos
                    st.success(f"Ditemukan {len(drive_videos)} video")
        
        if st.session_state.drive_videos:
            video_titles = [v['title'] for v in st.session_state.drive_videos]
            selected_drive_title = st.selectbox("Pilih video dari Drive", video_titles, key="drive_select")
            
            # Cari info video yang dipilih
            selected_video_info = None
            for video in st.session_state.drive_videos:
                if video['title'] == selected_drive_title:
                    selected_video_info = video
                    break
            
            if selected_video_info:
                st.info(f"ID File: {selected_video_info['id']}")
                
                if st.button("📥 Download dan Gunakan Video Ini"):
                    with st.spinner("Mendownload video..."):
                        filename = f"downloaded_{selected_video_info['title']}"
                        if download_video_from_drive(selected_video_info['id'], filename):
                            st.session_state.downloaded_video_path = filename
                            st.session_state.selected_drive_video = selected_video_info['title']
                            st.success(f"Video '{selected_video_info['title']}' berhasil didownload!")
                        else:
                            st.error("Gagal mendownload video")

    # Tab 3: Upload Video
    with tab3:
        st.subheader("Upload Video Baru")
        uploaded_file = st.file_uploader("Upload video (mp4/flv/mov/avi - codec H264/AAC)", 
                                        type=['mp4', 'flv', 'mov', 'avi'])
        
        if uploaded_file:
            with open(uploaded_file.name, "wb") as f:
                f.write(uploaded_file.read())
            st.success("Video berhasil diupload!")
            st.session_state.selected_local_video = uploaded_file.name

    # Form konfigurasi streaming
    st.markdown("---")
    st.subheader("Konfigurasi Streaming")
    
    # Tentukan video yang akan digunakan
    video_to_use = None
    if st.session_state.downloaded_video_path and os.path.exists(st.session_state.downloaded_video_path):
        video_to_use = st.session_state.downloaded_video_path
        st.info(f"Video yang akan digunakan: {st.session_state.selected_drive_video} (dari Drive)")
    elif st.session_state.selected_local_video and os.path.exists(st.session_state.selected_local_video):
        video_to_use = st.session_state.selected_local_video
        st.info(f"Video yang akan digunakan: {st.session_state.selected_local_video} (lokal)")
    else:
        st.warning("Belum ada video yang dipilih")

    stream_key = st.text_input("Stream Key YouTube", type="password")
    date = st.date_input("Tanggal Tayang")
    time_val = st.time_input("Jam Tayang")
    is_shorts = st.checkbox("Mode Shorts (720x1280)")

    # Kontrol streaming
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Jalankan Streaming", disabled=not video_to_use or not stream_key):
            if not video_to_use or not stream_key:
                st.error("Video dan stream key harus diisi!")
            else:
                st.session_state.streaming = True
                st.session_state.logs = []
                
                def log_callback(msg):
                    st.session_state.logs.append(msg)
                
                st.session_state.ffmpeg_thread = threading.Thread(
                    target=run_ffmpeg, 
                    args=(video_to_use, stream_key, is_shorts, log_callback), 
                    daemon=True
                )
                st.session_state.ffmpeg_thread.start()
                st.success("Streaming dimulai!")
    
    with col2:
        if st.button("⏹️ Stop Streaming"):
            st.session_state.streaming = False
            os.system("pkill ffmpeg")
            if st.session_state.downloaded_video_path and os.path.exists(st.session_state.downloaded_video_path):
                try:
                    os.remove(st.session_state.downloaded_video_path)
                    st.session_state.downloaded_video_path = None
                except:
                    pass
            st.warning("Streaming dihentikan!")

    # Tampilkan logs
    if st.session_state.logs:
        st.subheader("Log Streaming")
        log_text = "\n".join(st.session_state.logs[-30:])  # Tampilkan 30 baris terakhir
        st.text_area("Logs", value=log_text, height=300, key="log_display")

if __name__ == '__main__':
    main()
