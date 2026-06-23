# Video Downloader (VD)

A modern full-stack web application for downloading videos seamlessly.

## Prerequisites
- **Python 3.9+**
- **Node.js 18+**
- **FFmpeg**: Required for merging high-resolution video and audio (e.g., 1080p). 
  - Windows: `winget install --id Gyan.FFmpeg -e`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

## 1. Backend Setup & Run (FastAPI)

1. Open a terminal and navigate to the root directory (`vd`).
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```
   *(The backend will now be running at http://127.0.0.1:8000)*

## 2. Frontend Setup & Run (React / Vite)

1. Open a **new** terminal and navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install the Node.js packages:
   ```bash
   npm install
   ```
3. Run the frontend development server:
   ```bash
   npm run dev
   ```
   *(The frontend will now be running at http://localhost:5173)*

## 3. Usage
1. Open your browser and go to `http://localhost:5173`.
2. Sign up or log in (the default admin account is usually username: `admin`).
3. Paste a video URL, click Search, and choose your preferred resolution to download.

---

**Note**: When downloading high-resolution formats, the server downloads both the video and audio streams temporarily, merges them using FFmpeg, and then sends the completed file to your browser. The temporary file on the server is immediately deleted after the download completes.
