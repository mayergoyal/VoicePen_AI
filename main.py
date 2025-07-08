# main.py - FastAPI Backend
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile,File
from fastapi.responses import HTMLResponse
import json
import speech_recognition as sr
import io
import wave
import openai
from docx import Document
import base64
from pydub import AudioSegment
import re
import os
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
app = FastAPI()
load_dotenv()
# Set your OpenAI API key
tokenizer = AutoTokenizer.from_pretrained("vennify/t5-base-grammar-correction")
model = AutoModelForSeq2SeqLM.from_pretrained("vennify/t5-base-grammar-correction")


# Serve static files
#app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

def transcribe_audio(audio_data):
    """Transcribe audio data using speech recognition"""
    try:
        r = sr.Recognizer()
        # Convert base64 to audio
        audio_data_clean = re.sub(r"^data:audio/\w+;base64,", "", audio_data)
        audio_bytes = base64.b64decode(audio_data_clean)
        
        print(f"Audio data size: {len(audio_bytes)} bytes")
        
        # Convert to wav format for better compatibility
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm") 
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)
        
        print(f"Converted WAV size: {len(wav_io.getvalue())} bytes")
        
        # Use the converted WAV data for transcription
        with sr.AudioFile(wav_io) as source:
            # Adjust for ambient noise
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.record(source)
        
        print("Attempting transcription...")
        text = r.recognize_google(audio)
        print(f"Transcribed text: {text}")
        return text
    except sr.UnknownValueError:
        print("Could not understand audio")
        return ""  # Return empty string instead of error message
    except sr.RequestError as e:
        print(f"Speech recognition service error: {e}")
        return f"Speech recognition service error: {e}"
    except Exception as e:
        print("Transcription error:", str(e))
        return f"Error: {str(e)}"

def correct_grammar(text):
    input_text = "fix: " + text
    inputs = tokenizer.encode(input_text, return_tensors="pt")
    outputs = model.generate(inputs, max_length=128, num_beams=4, early_stopping=True)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

def append_to_existing_file(file_name: str, text: str):
    """Appends text to a .docx or .txt file in the user_docs folder."""
    path = os.path.join("user_docs", file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{file_name} not found in user_docs folder")

    ext = os.path.splitext(file_name)[1].lower()

    if ext == ".docx":
        doc = Document(path)
        doc.add_paragraph(text)
        doc.save(path)
    elif ext == ".txt":
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n" + text)
    else:
        raise ValueError("Unsupported file type. Only .docx and .txt are allowed.")

    
        

@app.get("/")
async def get():
    try:
        with open("main.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(html_content)
    except FileNotFoundError:
        # Fallback if main.html is in templates folder
        try:
            with open("templates/main.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(html_content)
        except FileNotFoundError:
            return HTMLResponse("<h1>HTML file not found. Please ensure main.html exists.</h1>")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send a properly formatted JSON connected message
    await manager.send_personal_message(
        json.dumps({"type": "status", "text": "Connected to server"}),
        websocket
    )

    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received data from client: {data[:100]}...")  # Log first 100 chars

            try:
                message = json.loads(data)
                print(f"Parsed message type: {message.get('type')}")
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    json.dumps({"type": "error", "text": "Invalid JSON"}),
                    websocket
                )
                continue

            msg_type = message.get("type")

            if msg_type == "audio":
                print("Processing audio message...")
                audio_data = message.get("data")
                if not audio_data:
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "text": "No audio data received"}),
                        websocket
                    )
                    continue
                
                text = transcribe_audio(audio_data)
                
                # Only send transcription if we got text
                if text and not text.startswith("Error:"):
                    await manager.send_personal_message(
                        json.dumps({"type": "transcription", "text": text}),
                        websocket
                    )
                elif text.startswith("Error:"):
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "text": text}),
                        websocket
                    )

            elif msg_type == "grammar_check":
                input_text = message.get("text", "")
                print(f"Grammar check requested for: {input_text[:50]}...")
                corrected = correct_grammar(input_text)
                await manager.send_personal_message(
                    json.dumps({"type": "grammar_corrected", "text": corrected}),
                    websocket
                )
                
            elif msg_type=="append_to_doc":
                doc_name=message.get("doc_name","")
                text_to_append=message.get("text","")
                print(f"Appending to doc: {doc_name} -> {text_to_append[:50]}...")
                
                try:
                    append_to_existing_file(doc_name,text_to_append)
                    await manager.send_personal_message(
                        json.dumps({"type": "status", "text": f"Text appended to {doc_name}"}),
                        websocket
                    )
                except Exception as e:
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "text": str(e)}),
                        websocket
                    )
                
    except WebSocketDisconnect:
        print("Client disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join("user_docs", file.filename)

    # Only allow .docx or .txt files
    if not file.filename.endswith((".docx", ".txt")):
        return {"error": "Only .docx and .txt files are supported."}

    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {"message": "File uploaded successfully", "filename": file.filename}


from fastapi.responses import FileResponse

@app.get("/download-updated/{filename}")
async def download_updated_file(filename: str):
    file_path = f"user_docs/{filename}"
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
    return {"error": "File not found"}
  

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)