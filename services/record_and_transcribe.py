import sounddevice as sd
import soundfile as sf
import numpy as np
import queue
from faster_whisper import WhisperModel
import os
from datetime import datetime

# Create a queue to hold audio data as it comes in from the microphone
audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    """This function is called continuously by sounddevice for each audio chunk."""
    if status:
        print(status)
    # Put a copy of the audio chunk into our queue
    audio_queue.put(indata.copy())

def record_until_enter(filename: str = "temp_dictation.wav", samplerate: int = 16000):
    """Starts recording immediately and stops when the user presses Enter."""
    
    # Clear out any old audio left in the queue just to be safe
    while not audio_queue.empty():
        audio_queue.get()

    print("\n🔴 RECORDING NOW... (Speak your dictation, then press ENTER to STOP)")
    
    # Open the microphone stream and start recording right away
    with sd.InputStream(samplerate=samplerate, channels=1, callback=audio_callback):
        input()  # The script pauses here, recording in the background, until you press Enter
    
    print("⏹️ Recording stopped. Saving file...")
    
    # Extract all the audio chunks from the queue
    recorded_chunks = []
    while not audio_queue.empty():
        recorded_chunks.append(audio_queue.get())
    
    # Safety check
    if not recorded_chunks:
        print("\n⚠️ ERROR: No audio was captured!")
        print("Make sure your microphone is connected and you didn't press Enter immediately.")
        return None
        
    # Combine the chunks into a single array and save as a .wav file
    audio_data = np.concatenate(recorded_chunks, axis=0)
    sf.write(filename, audio_data, samplerate)
    print(f"✅ Audio saved temporarily as '{filename}'")
    
    return filename

def transcribe_audio(audio_file_path: str, model: WhisperModel):
    """Transcribes the given audio file using the provided Whisper model."""
    print("\n🧠 Transcribing...")
    
    # beam_size=5 helps the model look at multiple possible word paths to improve accuracy
    segments, info = model.transcribe(audio_file_path, beam_size=5)
    
    full_transcript = ""
    for segment in segments:
        full_transcript += segment.text + " "
        
    return full_transcript.strip()


def save_transcript_to_file(transcript: str, folder_path: str = "data/raw_dictations"):
    """Saves the transcribed text to a unique text file using a timestamp."""
    
    # 1. Create the data folder if it doesn't exist yet
    os.makedirs(folder_path, exist_ok=True)
    
    # 2. Generate a unique filename using the current date and time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dictation_{timestamp}.txt"
    file_path = os.path.join(folder_path, filename)
    
    # 3. Save the transcript as a completely new file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(transcript)

    print(f"💾 Transcript saved as a new test case: {file_path}")



# --- Main Execution ---
if __name__ == "__main__":
    # 1. Load the model FIRST so we don't have to wait after recording
    print("Loading Whisper model into memory...")
    # Using "base.en" for fast, English testing.
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
    
    # 2. Record the audio
    temp_audio_file = record_until_enter()
    
    # 3. Transcribe the audio
    transcription = transcribe_audio(temp_audio_file, whisper_model)
    
    # 4. Display the result
    print("\n" + "="*40)
    print("📝 FINAL TRANSCRIPT:")
    print("="*40)
    print(transcription)
    print("="*40 + "\n")

    save_transcript_to_file(transcription)