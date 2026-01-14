import sys
import subprocess
import threading
import time
import os
import streamlit.components.v1 as components
import requests
import re
from urllib.parse import urlparse
from queue import Queue, Empty

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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        response = requests.get(url, headers=headers, timeout=15)
        content = response.text
        
        # Cari file Part_*.mp4
        file_patterns = [
            r'"(Part_[0-9]+\.mp4)"',
            r'"(part_[0-9]+\.mp4)"',
            r'"([Pp]art\s*[0-9]+\.mp4)"',
        ]
        
        files_found = []
        processed_names = set()
        
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                filename = match if isinstance(match, str) else match[0]
                if filename and filename not in processed_names:
                    processed_names.add(filename)
                    number_match = re.search(r'[0-9]+', filename)
                    number = int(number_match.group()) if number_match else 0
                    
                    files_found.append({
                        'title': filename,
                        'number': number,
                        'raw': filename
                    })
        
        # Jika tidak ketemu, cari pattern umum
        if not files_found:
            general_pattern = r'"([^"]+\.(mp4|flv|mov|avi))"'
            general_matches = re.findall(general_pattern, content)
            for match in general_matches:
                filename = match[0] if isinstance(match, tuple) else match
                if filename and filename not in processed_names:
                    processed_names.add(filename)
                    number_match = re.search(r'[0-9]+', filename)
                    number = int(number_match.group()) if number_match else 0
                    
                    files_found.append({
                        'title': filename,
                        'number': number,
                        'raw': filename
                    })
        
        files_found.sort(key=lambda x: x['number'])
        
        # Buat ID dummy untuk demo
        final_files = []
        for i, file_info in enumerate(files_found):
            file_id = f"dummy_id_{i:03d}"
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
    """Metode untuk mendapatkan ID file secara manual"""
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
        
        escaped_filename = re.escape(filename)
        pattern = f'"{escaped_filename}"[^{{}}]*?"id":"([^"]+)"'
        match = re.search(pattern, content)
        
        if match:
            return match.group(1)
        else:
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

def run_ffmpeg(video_path, stream_key, is_shorts, log_queue):
    """Fungsi FFmpeg yang kompatibel dengan threading"""
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
    
    # Log command yang dijalankan
    log_queue.put(f"🎬 Menjalankan: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            log_queue.put(line.strip())
        process.wait()
        log_queue.put("✅ Streaming selesai atau dihentikan.")
    except Exception as e:
        log_queue.put(f"❌ Error FFmpeg: {e}")

def main():
    # Page configuration
    st.set_page_config(
        page_title="Streaming YT by didinchy",
        page_icon="📈",
        layout="wide"
    )
    st.title("Live Streaming Loss Doll")
    
    # Inisialisasi session state
    session_keys = {
        'drive_videos': [],
        'selected_local_video': None,
        'selected_drive_video': None,
        'downloaded_video_path': None,
        'logs': [],  # Inisialisasi logs
        'streaming': False,
        'ffmpeg_thread': None,
        'log_queue': None,  # Queue untuk logging dari thread
        'drive_folder_url': "https://drive.google.com/drive/folders/1d7fpbrOI9q9Yl6w99-yZGNMB30XNyugf"
    }
    
    for key, default_value in session_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

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
                                preview_list = [f"{v['title']} (#{v['number']})" for v in drive_videos[:10]]
                                if len(drive_videos) > 10:
                                    preview_list.append("...")
                                st.caption("Preview: " + ", ".join(preview_list))
                            else:
                                st.warning("Tidak menemukan file Part_*. Silakan cek manual.")
                        except Exception as e:
                            st.error(f"Error scanning: {str(e)}")
                else:
                    st.error("Masukkan URL folder dulu")
        
        # Tampilkan daftar video
        if st.session_state.drive_videos:
            st.subheader("📋 Daftar File (Urut)")
            
            sorted_videos = sorted(st.session_state.drive_videos, key=lambda x: x['number'])
            
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
                            st.warning("ID tidak ditemukan")
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
            st.info("🔍 Gunakan tombol 'Scan Folder' untuk mencari file")

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

    # Kontrol streaming dengan sistem queue logging
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Mulai Streaming", disabled=not video_to_use or not stream_key):
            if not video_to_use or not stream_key:
                st.error("Video dan stream key harus diisi!")
            else:
                st.session_state.streaming = True
                st.session_state.logs = []  # Reset logs
                st.session_state.log_queue = Queue()  # Buat queue baru untuk logging
                
                # Start FFmpeg thread
                st.session_state.ffmpeg_thread = threading.Thread(
                    target=run_ffmpeg, 
                    args=(video_to_use, stream_key, is_shorts, st.session_state.log_queue), 
                    daemon=True
                )
                st.session_state.ffmpeg_thread.start()
                st.success("🚀 Streaming dimulai!")
    
    with col2:
        if st.button("⏹️ Stop Streaming"):
            st.session_state.streaming = False
            os.system("pkill ffmpeg 2>/dev/null")
            if st.session_state.downloaded_video_path and os.path.exists(st.session_state.downloaded_video_path):
                try:
                    os.remove(st.session_state.downloaded_video_path)
                    st.session_state.downloaded_video_path = None
                except:
                    pass
            st.warning("🛑 Streaming dihentikan!")

    # Tampilkan logs secara real-time
    st.subheader("📝 Log Streaming")
    
    # Baca log dari queue jika ada
    if 'log_queue' in st.session_state and st.session_state.log_queue:
        try:
            while True:
                try:
                    log_msg = st.session_state.log_queue.get_nowait()
                    st.session_state.logs.append(log_msg)
                except Empty:
                    break
        except:
            pass
    
    # Tampilkan logs (max 50 baris terakhir)
    if st.session_state.logs:
        log_text = "\n".join(st.session_state.logs[-50:])
        st.text_area("Logs", value=log_text, height=300, key="log_display")

if __name__ == '__main__':
    main()
