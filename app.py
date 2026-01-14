import sys
import subprocess
import threading
import time
import os
import streamlit.components.v1 as components
import requests
import re
from urllib.parse import parse_qs, urlparse
import json

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

def get_all_drive_files(folder_id):
    """Mengambil semua file dari folder Google Drive menggunakan API"""
    try:
        # Headers untuk mensimulasikan browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        # URL awal
        base_url = f"https://drive.google.com/drive/folders/{folder_id}"
        
        # Dapatkan konten pertama
        response = requests.get(base_url, headers=headers)
        content = response.text
        
        videos = []
        processed_ids = set()
        
        # Pattern untuk mencari file-file
        patterns = [
            # Pattern untuk nama file dan ID
            r'"([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"[^}]*?"id":"([^"]+)"',
            r'"id":"([^"]+)"[^}]*?"([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"',
            # Pattern alternatif
            r'data-tooltip="([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"[^}]*?"id":"([^"]+)"',
            # Pattern untuk title
            r'title="([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"[^}]*?"id":"([^"]+)"',
        ]
        
        # Cari file menggunakan semua pattern
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) >= 3:
                    # Format: (filename, extension, id) atau (id, filename, extension)
                    if 'id":"' in pattern or '"id":"' in pattern:
                        # ID biasanya di posisi terakhir atau pertama
                        filename = match[0] if '.' in match[0] else match[1]
                        file_id = match[2] if len(match) > 2 else match[0]
                    else:
                        filename = match[0]
                        file_id = match[2] if len(match) > 2 else ''
                elif len(match) == 2:
                    filename = match[0] if '.' in match[0] else ''
                    file_id = match[1] if len(match[1]) > 20 else ''
                else:
                    continue
                
                # Validasi ID dan filename
                if file_id and len(file_id) > 20 and filename and '.' in filename:
                    if file_id not in processed_ids:
                        processed_ids.add(file_id)
                        video_info = {
                            'title': filename,
                            'id': file_id,
                            'url': f"https://drive.google.com/file/d/{file_id}/view"
                        }
                        videos.append(video_info)
        
        # Jika masih kurang, coba metode alternatif - cari semua ID dan nama terpisah
        if len(videos) < 10:  # Jika hasil kurang dari 10, coba metode lain
            # Cari semua ID panjang
            id_pattern = r'"([a-zA-Z0-9_-]{25,})"'
            ids = re.findall(id_pattern, content)
            
            # Cari semua nama file
            name_pattern = r'"([^"]+\.(mp4|MP4|flv|FLV|mov|MOV|avi|AVI|mkv|MKV|wmv|WMV))"'
            names = re.findall(name_pattern, content)
            
            # Gabungkan dengan logika pairing
            for i, file_id in enumerate(ids):
                if file_id not in processed_ids and len(file_id) > 25:
                    processed_ids.add(file_id)
                    # Gunakan nama dari list names jika tersedia
                    if i < len(names):
                        if isinstance(names[i], tuple):
                            filename = names[i][0]
                        else:
                            filename = names[i]
                    else:
                        filename = f"video_{i+1}.mp4"  # Default naming
                    
                    video_info = {
                        'title': filename,
                        'id': file_id,
                        'url': f"https://drive.google.com/file/d/{file_id}/view"
                    }
                    videos.append(video_info)
        
        # Hapus duplikat berdasarkan ID
        unique_videos = []
        seen_ids = set()
        for video in videos:
            if video['id'] not in seen_ids:
                seen_ids.add(video['id'])
                unique_videos.append(video)
        
        return unique_videos
        
    except Exception as e:
        st.error(f"Error dalam get_all_drive_files: {str(e)}")
        return []

def get_drive_video_list(folder_url):
    """Mengambil daftar video dari folder Google Drive publik dengan nama asli"""
    try:
        folder_id = extract_folder_id_from_url(folder_url)
        if not folder_id:
            raise ValueError("URL Google Drive tidak valid")
        
        st.info("Mengambil daftar file dari folder...")
        videos = get_all_drive_files(folder_id)
        
        # Filter hanya file video
        video_extensions = ('.mp4', '.MP4', '.flv', '.FLV', '.mov', '.MOV', 
                           '.avi', '.AVI', '.mkv', '.MKV', '.wmv', '.WMV')
        video_files = [v for v in videos if v['title'].lower().endswith(video_extensions)]
        
        return video_files
        
    except Exception as e:
        st.error(f"Gagal mengambil daftar video dari Google Drive: {str(e)}")
        return []

def download_video_from_drive(file_id, filename):
    """Download video dari Google Drive"""
    try:
        # URL download
        url = f"https://drive.google.com/uc?id={file_id}&export=download"
        
        # Headers untuk menghindari masalah rate limit
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Lakukan download
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # Update progress setiap 1MB
                        if downloaded_size % (1024*1024) == 0:
                            st.spinner(f"Downloading... {downloaded_size/(1024*1024):.1f} MB")
            return True
        else:
            # Coba metode alternatif
            st.info("Mencoba metode download alternatif...")
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
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Ambil Daftar Video dari Folder"):
                if drive_url:
                    with st.spinner("Mengambil daftar video dari folder Google Drive..."):
                        try:
                            drive_videos = get_drive_video_list(drive_url)
                            st.session_state.drive_videos = drive_videos
                            if drive_videos:
                                st.success(f"Berhasil mengambil {len(drive_videos)} video dari folder!")
                                # Tampilkan sample beberapa file pertama
                                sample_files = [f"{v['title']} (ID: {v['id'][:10]}...)" for v in drive_videos[:10]]
                                if len(drive_videos) > 10:
                                    sample_files.append(f"... dan {len(drive_videos) - 10} file lainnya")
                                st.caption("Beberapa file: " + "; ".join(sample_files))
                            else:
                                st.warning("Tidak menemukan video dalam folder. Pastikan folder publik dan berisi file video.")
                        except Exception as e:
                            st.error(f"Error mengambil daftar video: {str(e)}")
                else:
                    st.error("Masukkan URL folder Google Drive terlebih dahulu")
        
        # Tampilkan daftar video Drive
        if st.session_state.drive_videos:
            st.subheader(f"Daftar Video ({len(st.session_state.drive_videos)} items)")
            
            # Filter hanya file video dan urutkan
            video_files = [v for v in st.session_state.drive_videos if v['title'].lower().endswith(('.mp4', '.flv', '.mov', '.avi', '.mkv', '.wmv'))]
            video_files.sort(key=lambda x: x['title'])  # Urutkan berdasarkan nama
            
            if video_files:
                video_titles = [v['title'] for v in video_files]
                selected_drive_title = st.selectbox("Pilih video dari Drive", video_titles, key="drive_select")
                
                # Cari info video yang dipilih
                selected_video_info = None
                for video in video_files:
                    if video['title'] == selected_drive_title:
                        selected_video_info = video
                        break
                
                if selected_video_info:
                    st.info(f"File ID: {selected_video_info['id']}")
                    st.info(f"Nama File Asli: {selected_video_info['title']}")
                    
                    if st.button("📥 Download dan Gunakan Video Ini"):
                        with st.spinner(f"Mendownload video: {selected_video_info['title']}"):
                            # Gunakan nama file asli untuk download
                            filename = selected_video_info['title']
                            # Pastikan nama file unik jika sudah ada
                            counter = 1
                            original_filename = filename
                            while os.path.exists(filename):
                                name_part, ext = os.path.splitext(original_filename)
                                filename = f"{name_part}_{counter}{ext}"
                                counter += 1
                            
                            if download_video_from_drive(selected_video_info['id'], filename):
                                st.session_state.downloaded_video_path = filename
                                st.session_state.selected_drive_video = selected_video_info['title']
                                st.success(f"Video '{selected_video_info['title']}' berhasil didownload sebagai '{filename}'!")
                            else:
                                st.error("Gagal mendownload video. Coba lagi.")
            else:
                st.info("Tidak ada file video ditemukan dalam folder")
        else:
            st.info("Belum ada daftar video dari Drive. Klik tombol '🔄 Ambil Daftar Video dari Folder' di atas.")

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
    st.subheader("Konfigurasi Streaming")
    
    # Tentukan video yang akan digunakan
    video_to_use = None
    if st.session_state.downloaded_video_path and os.path.exists(st.session_state.downloaded_video_path):
        video_to_use = st.session_state.downloaded_video_path
        st.info(f"Video yang akan digunakan: {st.session_state.selected_drive_video} (dari Drive)")
    elif st.session_state.selected_local_video and os.path.exists(st.session_state.selected_local_video):
        video_to_use = st.session_state.selected_local_video
        st.info(f"Video yang akan digunakan: {st.session_state.selected_local_video} (lokal/upload)")
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

    # Petunjuk cara menggunakan
    with st.expander("ℹ️ Cara Menggunakan"):
        st.markdown("""
        **Langkah-langkah penggunaan:**
        
        1. **Masuk ke Tab "Video Google Drive"**
        2. **Pastikan URL folder sudah benar** (default sudah terisi)
        3. **Klik tombol "🔄 Ambil Daftar Video dari Folder"**
        4. **Tunggu sampai proses selesai** (bisa memakan waktu beberapa detik)
        5. **Pilih video yang ingin digunakan dari dropdown**
        6. **Klik "📥 Download dan Gunakan Video Ini"**
        7. **Isi Stream Key YouTube**
        8. **Klik "▶️ Jalankan Streaming"**
        
        **Catatan:**
        - Folder harus dalam mode "publik" atau "siapa pun dengan link dapat melihat"
        - Semua file video dalam folder akan diambil (bukan hanya 20 pertama)
        - Video akan didownload dengan nama file asli (misal: Part_1.mp4)
        - File yang sama akan ditambahkan suffix angka jika sudah ada (_1, _2, dst)
        """)

if __name__ == '__main__':
    main()
