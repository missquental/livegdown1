import sys
import subprocess
import threading
import time
import os
import streamlit.components.v1 as components
import requests
import re
from urllib.parse import parse_qs, urlparse

# Install packages jika belum ada
packages = ["streamlit", "requests"]
for package in packages:
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import streamlit as st

def extract_folder_id_from_url(url):
    """Ekstrak folder ID dari URL Google Drive"""
    if '/folders/' in url:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        if 'folders' in path_parts:
            folder_index = path_parts.index('folders')
            if folder_index + 1 < len(path_parts):
                return path_parts[folder_index + 1]
    return None

def get_drive_files_basic(folder_url):
    """Metode dasar untuk mengambil file dari folder Google Drive"""
    try:
        folder_id = extract_folder_id_from_url(folder_url)
        if not folder_id:
            raise ValueError("URL Google Drive tidak valid")
        
        # Headers untuk mensimulasikan browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        
        # URL untuk mengakses folder
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        
        # Lakukan request
        response = requests.get(url, headers=headers, timeout=15)
        content = response.text
        
        files = []
        processed_ids = set()
        
        # Pattern untuk mencari file dengan nama dan ID
        patterns = [
            r'"([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"[^}]*?"id":"([^"]+)"',
            r'"id":"([^"]+)"[^}]*?"([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"',
            r'data-tooltip="([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"[^}]*?"id":"([^"]+)"',
            r'title="([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"[^}]*?"id":"([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                try:
                    if len(match) >= 3:
                        # Pattern dengan format (nama, ext, id) atau (id, nama, ext)
                        if '"id":"' in pattern:
                            filename = match[0] if '.' in match[0] else match[1]
                            file_id = match[2] if len(match) > 2 else match[0]
                        else:
                            filename = match[0]
                            file_id = match[2] if len(match) > 2 else ''
                    elif len(match) == 2:
                        # Pattern dengan format (nama_dengan_ext, id)
                        filename = match[0]
                        file_id = match[1]
                    else:
                        continue
                    
                    # Validasi
                    if file_id and len(file_id) > 20 and filename and '.' in filename:
                        if file_id not in processed_ids:
                            processed_ids.add(file_id)
                            files.append({
                                'title': filename,
                                'id': file_id,
                                'url': f"https://drive.google.com/file/d/{file_id}/view"
                            })
                except:
                    continue
        
        return files
        
    except Exception as e:
        st.error(f"Error basic scraping: {str(e)}")
        return []

def download_video_from_drive(file_id, filename):
    """Download video dari Google Drive"""
    try:
        # URL download
        url = f"https://drive.google.com/uc?id={file_id}&export=download"
        
        # Headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Lakukan download
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            # Coba metode alternatif
            url_alt = f"https://docs.google.com/uc?export=download&id={file_id}"
            response_alt = requests.get(url_alt, headers=headers, stream=True, timeout=30)
            if response_alt.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response_alt.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
        
        return False
        
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
    if 'drive_folder_url' not in st.session_state:
        st.session_state.drive_folder_url = "https://drive.google.com/drive/folders/1d7fpbrOI9q9Yl6w99-yZGNMB30XNyugf"
    if 'manual_videos' not in st.session_state:
        st.session_state.manual_videos = []

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
        
        # Input URL folder Google Drive
        drive_url = st.text_input("URL Folder Google Drive", 
                                 value=st.session_state.drive_folder_url,
                                 help="Format: https://drive.google.com/drive/folders/FOLDER_ID")
        
        if drive_url != st.session_state.drive_folder_url:
            st.session_state.drive_folder_url = drive_url
        
        # Section untuk auto-scraping
        st.markdown("---")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Auto Scan Folder"):
                if drive_url:
                    with st.spinner("Scanning folder..."):
                        try:
                            scraped_videos = get_drive_files_basic(drive_url)
                            st.session_state.drive_videos = scraped_videos
                            if scraped_videos:
                                st.success(f"Ditemukan {len(scraped_videos)} file!")
                            else:
                                st.warning("Tidak menemukan file. Gunakan metode manual di bawah.")
                        except Exception as e:
                            st.error(f"Error scanning: {str(e)}")
                else:
                    st.error("Masukkan URL folder dulu")
        
        # Section untuk input manual (metode utama yang lebih reliable)
        st.markdown("---")
        st.subheader("➕ Tambah Video Manual (Lebih Akurat)")
        
        col_add1, col_add2, col_add3 = st.columns(3)
        with col_add1:
            manual_name = st.text_input("Nama File Asli", placeholder="Part_1.mp4")
        with col_add2:
            manual_id = st.text_input("File ID", placeholder="ID dari URL Google Drive", help="Bagian setelah /d/ dalam URL")
        with col_add3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("➕ Tambah ke List"):
                if manual_name and manual_id:
                    new_video = {
                        'title': manual_name,
                        'id': manual_id,
                        'url': f"https://drive.google.com/file/d/{manual_id}/view"
                    }
                    st.session_state.manual_videos.append(new_video)
                    st.success(f"Added: {manual_name}")
                else:
                    st.error("Isi nama file dan ID!")
        
        # Tampilkan daftar video manual
        if st.session_state.manual_videos:
            st.subheader(f"📋 Daftar Video Manual ({len(st.session_state.manual_videos)})")
            for i, video in enumerate(st.session_state.manual_videos):
                col_name, col_id, col_action = st.columns([3, 2, 1])
                with col_name:
                    st.write(f"📄 {video['title']}")
                with col_id:
                    st.code(video['id'][:15] + "...")
                with col_action:
                    if st.button("❌", key=f"del_{i}"):
                        st.session_state.manual_videos.pop(i)
                        st.experimental_rerun()
        
        # Gabungkan semua video (scraped + manual)
        all_videos = st.session_state.manual_videos + st.session_state.drive_videos
        
        # Tampilkan dropdown untuk memilih video
        if all_videos:
            st.markdown("---")
            st.subheader("🎬 Pilih Video untuk Streaming")
            
            # Urutkan berdasarkan nama
            all_videos_sorted = sorted(all_videos, key=lambda x: x['title'])
            video_titles = [v['title'] for v in all_videos_sorted]
            
            selected_title = st.selectbox("Pilih video", video_titles, key="video_selector")
            
            # Cari info video yang dipilih
            selected_video_info = None
            for video in all_videos_sorted:
                if video['title'] == selected_title:
                    selected_video_info = video
                    break
            
            if selected_video_info:
                st.info(f"📁 Nama File: {selected_video_info['title']}")
                st.info(f"🆔 File ID: {selected_video_info['id']}")
                
                if st.button("📥 Download & Gunakan Video Ini"):
                    with st.spinner(f"Mendownload: {selected_video_info['title']}"):
                        # Gunakan nama file asli
                        filename = selected_video_info['title']
                        # Handle jika file sudah ada
                        counter = 1
                        original_filename = filename
                        while os.path.exists(filename):
                            name_part, ext = os.path.splitext(original_filename)
                            filename = f"{name_part}_{counter}{ext}"
                            counter += 1
                        
                        if download_video_from_drive(selected_video_info['id'], filename):
                            st.session_state.downloaded_video_path = filename
                            st.session_state.selected_drive_video = selected_video_info['title']
                            st.success(f"✅ Berhasil! File disimpan sebagai: {filename}")
                        else:
                            st.error("❌ Gagal download. Periksa ID file atau koneksi internet.")
        else:
            st.info("🔍 Belum ada video. Gunakan 'Auto Scan' atau tambah manual dengan ID file.")

    # Tab 3: Upload Video
    with tab3:
        st.subheader("Upload Video Baru")
        uploaded_file = st.file_uploader("Upload video (mp4/flv/mov/avi)", 
                                        type=['mp4', '.flv', '.mov', '.avi'])
        
        if uploaded_file:
            with open(uploaded_file.name, "wb") as f:
                f.write(uploaded_file.read())
            st.success("Video berhasil diupload!")
            st.session_state.selected_local_video = uploaded_file.name

    # Form konfigurasi streaming
    st.markdown("---")
    st.subheader("⚙️ Konfigurasi Streaming")
    
    # Tentukan video yang akan digunakan
    video_to_use = None
    if st.session_state.downloaded_video_path and os.path.exists(st.session_state.downloaded_video_path):
        video_to_use = st.session_state.downloaded_video_path
        st.info(f"🎥 Video aktif: {st.session_state.selected_drive_video}")
    elif st.session_state.selected_local_video and os.path.exists(st.session_state.selected_local_video):
        video_to_use = st.session_state.selected_local_video
        st.info(f"🎥 Video aktif: {st.session_state.selected_local_video}")
    else:
        st.warning("⚠️ Belum ada video yang dipilih")

    stream_key = st.text_input("🔑 Stream Key YouTube", type="password")
    is_shorts = st.checkbox("📱 Mode Shorts (720x1280)")

    # Kontrol streaming
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Mulai Streaming", disabled=not video_to_use or not stream_key):
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
                st.success("🚀 Streaming dimulai!")
    
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
            st.warning("🛑 Streaming dihentikan!")

    # Tampilkan logs
    if st.session_state.logs:
        st.subheader("📝 Log Streaming")
        log_text = "\n".join(st.session_state.logs[-30:])
        st.text_area("Logs", value=log_text, height=300, key="log_display")

    # Petunjuk cara mendapatkan File ID
    with st.expander("ℹ️ Cara Mendapatkan File ID Google Drive"):
        st.markdown("""
        **Langkah-langkah:**
        
        1. **Buka file di Google Drive**
        2. **Klik kanan → Bagikan → Dapatkan link**
        3. **Ubah permission ke "Siapa pun dengan link ini dapat melihat"**
        4. **Salin link yang muncul**
        
        **Contoh URL:**
        ```
        https://drive.google.com/file/d/1abc123XYZabcdefghijklmnopqrst/view?usp=sharing
        ```
        
        **File ID adalah bagian:** `1abc123XYZabcdefghijklmnopqrst`
        
        **Tips:**
        - File ID biasanya 28 karakter alfanumerik
        - Pastikan file dalam mode "publik"
        """)

if __name__ == '__main__':
    main()
