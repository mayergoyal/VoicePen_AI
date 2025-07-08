import streamlit as st
import speech_recognition as sr
from docx import Document
import os
import openai
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import av
import queue
import threading
import json
from vosk import Model, KaldiRecognizer

# 💡 Set your Vosk model path
vosk_model_path = r"C:\Users\Mayer\OneDrive\Desktop\writerai\vosk-model-small-en-us-0.15"

# 🔍 Check for Vosk model
if not os.path.exists(vosk_model_path):
    st.error("❌ Vosk model not found. Please download and extract it.")
    st.stop()

# Load Vosk model
model = Model(vosk_model_path)

# 🧠 Set your OpenAI API key here
openai.api_key = "YOUR_OPENAI_API_KEY"  # ← replace this with your actual key

st.set_page_config(page_title="VoicePen AI", layout="centered")
st.title("🎙️ VoicePen AI – Speak, Write, and Correct")
st.markdown("This tool helps writers speak ideas and improve grammar with AI.")
st.markdown("Start speaking and see your words appear live!")

# Session state for full text
if "full_text" not in st.session_state:
    st.session_state.full_text = ""

# 🔁 Queue for live transcription results
result_queue = queue.Queue()

# 🎙️ Audio Processor
class AudioProcessor:
    def __init__(self):
        self.rec = KaldiRecognizer(model, 16000)
        self.text = ""

    def recv(self, frame: av.AudioFrame):
        audio = frame.to_ndarray().flatten().tobytes()  # flatten to mono
        if self.rec.AcceptWaveform(audio):
            result = json.loads(self.rec.Result())
            print("✅ Final Result:", result)
            self.text += result.get("text", "") + " "
            result_queue.put(self.text.strip())
        else:
            partial = json.loads(self.rec.PartialResult())
            print("🟡 Partial:", partial)
        return av.AudioFrame.from_ndarray(frame.to_ndarray(), layout="mono")


audio_processor = AudioProcessor()

# 🎧 Streamlit WebRTC for real-time audio
webrtc_ctx = webrtc_streamer(
    key="voice-writer",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=16000,
    audio_frame_callback=audio_processor.recv,
    async_processing=True,
)
st.write("🎛 WebRTC State:", webrtc_ctx.state)

if webrtc_ctx.audio_receiver:
    st.success("✅ Audio receiver is active.")
else:
    st.error("❌ Audio receiver is not active. Mic permission issue?")

# 🖥️ Display live transcription
if webrtc_ctx.state.playing:
    st.write("✅ Microphone stream started!")

    st.info("🎤 Speak now! Your words will appear below.")
    if "live_transcript" not in st.session_state:
        st.session_state.live_transcript=""
    transcript_placeholder=st.empty()
    while True:
        try:
            
            new_text=result_queue.get(timeout=1.0)
            if new_text!=st.session_state.live_transcript:
                st.session_state.live_transcript=new_text
                transcript_placeholder.text_area(
                    " Live Transcription ",
                    value=st.session_state.live_transcript,
                    height=300
                )
        except queue.Empty:
            continue
        except Exception as e:
            st.error(f"ERROR : {e}")
            break

# ✍️ Manual Punctuation Buttons
st.subheader("➕ Add Punctuation Manually")
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button(","):
        st.session_state.full_text += ", "
    if st.button("."):
        st.session_state.full_text += ". "
with col2:
    if st.button("?"):
        st.session_state.full_text += "? "
    if st.button("!"):
        st.session_state.full_text += "! "
with col3:
    if st.button('"'):
        st.session_state.full_text += '"'
    if st.button("'"):
        st.session_state.full_text += "'"
with col4:
    if st.button(":"):
        st.session_state.full_text += ": "
    if st.button(";"):
        st.session_state.full_text += "; "

# 🧠 Grammar Correction with OpenAI
st.subheader("🔍 Improve with AI")
if st.button("🧠 Correct Grammar & Punctuation"):
    prompt = f"Correct the grammar and punctuation in the following text:\n\n{st.session_state.full_text}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        corrected = response["choices"][0]["message"]["content"]
        st.session_state.full_text = corrected
        st.success("✅ AI has corrected your text!")
    except Exception as e:
        st.error(f"OpenAI error: {e}")

# 📄 Export to DOCX
st.subheader("📤 Export Your Writing")
if st.button("📄 Download as DOCX"):
    doc = Document()
    doc.add_paragraph(st.session_state.full_text)
    file_path = "VoicePenAI_Output.docx"
    doc.save(file_path)
    with open(file_path, "rb") as f:
        st.download_button("📥 Click to Download", f, file_name="VoicePenAI_Output.docx")
    os.remove(file_path)
