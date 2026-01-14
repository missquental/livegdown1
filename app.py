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

def get_drive_video_list(folder_url):
    """Mengambil daftar video dari folder Google Drive publik dengan nama asli"""
    try:
        folder_id = extract_folder_id_from_url(folder_url)
        if not folder_id:
            raise ValueError("URL Google Drive tidak valid")
        
        # Headers untuk mensimulasikan browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # URL untuk mengakses folder
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        
        # Lakukan request untuk mendapatkan konten
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Gagal mengakses folder. Status code: {response.status_code}")
        
        content = response.text
        videos = []
        processed_ids = set()
        
        # Pattern untuk mencari file dengan nama asli
        patterns = [
            r'"([^"]+)"\s*:\s*"application\/x-extension-(mp4|flv|mov|avi|mkv|wmv)"',
            r'"([^"]+\.(mp4|flv|mov|avi|mkv|wmv))"',  # Nama file dengan ekstensi
            r'data-tooltip="([^"]+\.(mp4|flv|mov|avi|mkv|wmv))"',  # Tooltip dengan nama file
            r'title="([^"]+\.(mp4|flv|mov|avi|mkv|wmv))"',  # Title dengan nama file
        ]
        
        found_matches = False
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) >= 2 and match[0] and match[1]:
                        # Format: (filename_with_ext, extension)
                        filename = match[0]
                        ext = match[1].lower()
                    elif len(match) >= 1 and match[0]:
                        # Format: (filename_with_ext,)
                        filename = match[0]
                        ext = filename.split('.')[-1].lower() if '.' in filename else 'mp4'
                    else:
                        continue
                else:
                    # Format: filename_with_ext
                    filename = match
                    ext = filename.split('.')[-1].lower() if '.' in filename else 'mp4'
                
                # Ekstrak ID dari filename atau cari ID terpisah
                file_id = None
                
                # Cari ID menggunakan regex tambahan
                id_search_pattern = rf'"{re.escape(filename)}"[^{{}}]*?"id":"([^"]+)"'
                id_match = re.search(id_search_pattern, content)
                if id_match:
                    file_id = id_match.group(1)
                
                # Jika tidak ketemu, coba pattern umum
                if not file_id:
                    general_id_pattern = r'"([^"]{20,})"'
                    general_ids = re.findall(general_id_pattern, content)
                    if general_ids:
                        file_id = general_ids[0]  # Gunakan ID pertama sebagai fallback
                
                if file_id and file_id not in processed_ids and len(file_id) > 20:
                    processed_ids.add(file_id)
                    video_info = {
                        'title': filename,
                        'id': file_id,
                        'url': f"https://drive.google.com/file/d/{file_id}/view"
                    }
                    videos.append(video_info)
                    found_matches = True
        
        # Jika metode di atas tidak berhasil, gunakan pendekatan alternatif
        if not found_matches:
            # Cari semua ID panjang yang kemungkinan adalah file ID
            id_pattern = r'"([a-zA-Z0-9_-]{20,})"'
            ids = re.findall(id_pattern, content)
            
            # Cari nama file secara terpisah
            name_pattern = r'"([^"]+\.(mp4|flv|mov|avi|mkv|wmv))"'
            names = re.findall(name_pattern, content)
            
            # Gabungkan informasi
            for i, file_id in enumerate(ids[:len(names)] if names else ids[:10]):  # Batasi 10 file
                if file_id not in processed_ids and len(file_id) > 20:
                    processed_ids.add(file_id)
                    # Gunakan nama dari list names jika tersedia, atau buat nama default
                    if i < len(names):
                        if isinstance(names[i], tuple):
                            filename = names[i][0]
                        else:
                            filename = names[i]
                    else:
                        filename = f"Part_{i+1}.mp4"  # Default naming
                    
                    video_info = {
                        'title': filename,
                        'id': file_id,
                        'url': f"https://drive.google.com/file/d/{file_id}/view"
                    }
                    videos.append(video_info)
        
        # Hapus duplikat berdasarkan title
        unique_videos = []
        seen_titles = set()
        for video in videos:
            if video['title'] not in seen_titles:
                seen_titles.add(video['title'])
                unique_videos.append(video)
        
        return unique_videos
        
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Lakukan download
        response = requests.get(url, headers=headers, stream=True)
        
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            # Coba metode alternatif
            url_alt = f"https://docs.google.com/uc?export=download&id={file_id}"
            response_alt = requests.get(url_alt, headers=headers, stream=True)
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
                                # Debug info
                                debug_info = [f"{v['title']} (ID: {v['id']})" for v in drive_videos[:5]]
                                st.caption("Beberapa file pertama: " + ", ".join(debug_info))
                            else:
                                st.warning("Tidak menemukan video dalam folder. Pastikan folder publik dan berisi file video.")
                        except Exception as e:
                            st.error(f"Error mengambil daftar video: {str(e)}")
                else:
                    st.error("Masukkan URL folder Google Drive terlebih dahulu")
        
        # Tampilkan daftar video Drive
        if st.session_state.drive_videos:
            st.subheader(f"Daftar Video ({len(st.session_state.drive_videos)} items)")
            
            # Filter hanya file video
            video_files = [v for v in st.session_state.drive_videos if v['title'].lower().endswith(('.mp4', '.flv', '.mov', '.avi', '.mkv'))]
            
            if video_files:
                # Urutkan berdasarkan nama file
                video_files.sort(key=lambda x: x['title'])
                
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
                                st.error("Gagal mendownload video. Coba lagi atau gunakan metode manual.")
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
        4. **Tunggu sampai daftar video muncul dengan nama asli**
        5. **Pilih video yang ingin digunakan**
        6. **Klik "📥 Download dan Gunakan Video Ini"**
        7. **Isi Stream Key YouTube**
        8. **Klik "▶️ Jalankan Streaming"**
        
        **Catatan:**
        - Folder harus dalam mode "publik" atau "siapa pun dengan link dapat melihat"
        - Video akan didownload dengan nama file asli (misal: Part_1.mp4)
        - File yang sama akan ditambahkan suffix angka jika sudah ada
        """)

if __name__ == '__main__':
    main()
