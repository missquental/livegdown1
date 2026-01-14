import sys
import subprocess
import threading
import time
import os
import streamlit.components.v1 as components
import requests
import re
from urllib.parse import urlparse

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

def get_drive_files_simple(folder_url):
    """Metode sederhana untuk mengambil file dari folder Google Drive"""
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
        
        # Cari semua nama file yang mengandung "Part" atau "part"
        file_patterns = [
            r'"(Part_[0-9]+\.mp4)"',
            r'"(part_[0-9]+\.mp4)"',
            r'"(Part[0-9]+\.mp4)"',
            r'"([Pp]art\s*[0-9]+\.mp4)"',
            r'"([Pp]art[0-9]+\.[a-zA-Z0-9]+)"',
            r'"([0-9]+\.mp4)"',  # Hanya angka
        ]
        
        files_found = []
        processed_names = set()
        
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                filename = match if isinstance(match, str) else match[0] if match else ""
                if filename and filename not in processed_names:
                    processed_names.add(filename)
                    # Extract number from filename
                    number_match = re.search(r'[0-9]+', filename)
                    number = int(number_match.group()) if number_match else 0
                    
                    files_found.append({
                        'title': filename,
                        'number': number,
                        'raw': filename
                    })
        
        # Jika tidak ketemu dengan pattern Part_, coba pattern umum
        if not files_found:
            # Cari semua file dengan ekstensi video
            general_pattern = r'"([^"]+\.(mp4|flv|mov|avi))"'
            general_matches = re.findall(general_pattern, content)
            for match in general_matches:
                filename = match[0] if isinstance(match, tuple) else match
                if filename and filename not in processed_names:
                    processed_names.add(filename)
                    # Extract number if exists
                    number_match = re.search(r'[0-9]+', filename)
                    number = int(number_match.group()) if number_match else 0
                    
                    files_found.append({
                        'title': filename,
                        'number': number,
                        'raw': filename
                    })
        
        # Urutkan berdasarkan nomor
        files_found.sort(key=lambda x: x['number'])
        
        # Tambahkan ID untuk setiap file (metode sederhana)
        final_files = []
        for i, file_info in enumerate(files_found):
            # Generate ID dummy untuk demo (sebenarnya perlu cara lain untuk dapat ID asli)
            file_id = f"dummy_id_{i:03d}"  # Ini hanya untuk demo
            final_files.append({
                'title': file_info['title'],
                'id': file_id,
                'number': file_info['number'],
                'url': f"https://drive.google.com/file/d/{file_id}/view"
            })
        
        return final_files
        
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

def get_file_id_manual(folder_url, filename):
    """Metode untuk mendapatkan ID file secara manual dengan pencarian lebih intensif"""
    try:
        folder_id = extract_folder_id_from_url(folder_url)
        if not folder_id:
            return None
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        response = requests.get(url, headers=headers, timeout=15)
        content = response.text
        
        # Cari ID berdasarkan nama file
        escaped_filename = re.escape(filename)
        pattern = f'"{escaped_filename}"[^{{}}]*?"id":"([^"]+)"'
        match = re.search(pattern, content)
        
        if match:
            return match.group(1)
        else:
            # Coba pattern alternatif
            pattern2 = f'"id":"([^"]+)"[^{{}}]*?"{escaped_filename}"'
            match2 = re.search(pattern2, content)
            if match2:
                return match2.group(1)
        
        return None
    except:
        return None

def download_video_from_drive(file_id, filename):
    """Download video dari Google Drive"""
    try:
        # Coba metode pertama
        url = f"https://drive.google.com/uc?id={file_id}&export=download"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            # Coba metode kedua
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
        st.error(f"Download error: {str(e)}")
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
            if st.button("🔄 Scan Folder"):
                if drive_url:
                    with st.spinner("Scanning folder untuk file Part_*.mp4..."):
                        try:
                            drive_videos = get_drive_files_simple(drive_url)
                            st.session_state.drive_videos = drive_videos
                            if drive_videos:
                                st.success(f"Ditemukan {len(drive_videos)} file!")
                                # Tampilkan preview
                                preview_list = [f"{v['title']} (#{v['number']})" for v in drive_videos[:10]]
                                if len(drive_videos) > 10:
                                    preview_list.append("...")
                                st.caption("Preview: " + ", ".join(preview_list))
                            else:
                                st.warning("Tidak menemukan file Part_*. Silakan cek manual di Google Drive dan tambahkan di bawah.")
                        except Exception as e:
                            st.error(f"Error scanning: {str(e)}")
                else:
                    st.error("Masukkan URL folder dulu")
        
        # Tampilkan daftar video yang ditemukan
        if st.session_state.drive_videos:
            st.subheader("📋 Daftar File yang Ditemukan (Urut)")
            
            # Urutkan berdasarkan nomor part
            sorted_videos = sorted(st.session_state.drive_videos, key=lambda x: x['number'])
            
            # Tampilkan dalam format tabel
            for i, video in enumerate(sorted_videos):
                col1, col2, col3, col4 = st.columns([3, 1, 2, 1])
                with col1:
                    st.write(f"📄 {video['title']}")
                with col2:
                    st.write(f"#{video['number']}")
                with col3:
                    if st.button("🔍 Get ID", key=f"getid_{i}"):
                        actual_id = get_file_id_manual(drive_url, video['title'])
                        if actual_id:
                            video['id'] = actual_id
                            video['url'] = f"https://drive.google.com/file/d/{actual_id}/view"
                            st.success(f"ID ditemukan: {actual_id[:15]}...")
                        else:
                            st.warning("ID tidak ditemukan, gunakan manual")
                with col4:
                    if st.button("📥 Download", key=f"dl_{i}"):
                        if video['id'] and not video['id'].startswith('dummy'):
                            with st.spinner(f"Downloading {video['title']}..."):
                                filename = video['title']
                                counter = 1
                                original_filename = filename
                                while os.path.exists(filename):
                                    name_part, ext = os.path.splitext(original_filename)
                                    filename = f"{name_part}_{counter}{ext}"
                                    counter += 1
                                
                                if download_video_from_drive(video['id'], filename):
                                    st.session_state.downloaded_video_path = filename
                                    st.session_state.selected_drive_video = video['title']
                                    st.success(f"✅ Downloaded as: {filename}")
                                else:
                                    st.error("❌ Download failed")
                        else:
                            st.error("❌ Dapatkan ID dulu!")
            
            st.markdown("---")
            
        else:
            st.info("🔍 Gunakan tombol 'Scan Folder' untuk mencari file Part_*.mp4")

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

    # Petunjuk cara manual
    with st.expander("ℹ️ Jika Scan Tidak Bekerja"):
        st.markdown("""
        **Cara Manual:**
        
        1. **Buka folder Google Drive Anda**
        2. **Urutkan file berdasarkan nama**
        3. **Catat nama file dan urutannya**
        4. **Untuk setiap file:**
           - Klik kanan file → Bagikan → Dapatkan link
           - Copy File ID dari URL
           - Gunakan tombol "📥 Download" dengan ID tersebut
        """)

if __name__ == '__main__':
    main()
