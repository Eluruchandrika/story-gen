import streamlit as st
import requests
import re

API_URL = "http://127.0.0.1:8000/generate_story"

st.title("🧠✨ AI-Powered Creative Story Generator")
st.write("Generate unique stories using AI and listen to them!")

genre = st.selectbox("Select Genre", ["Fantasy", "Sci-Fi", "Mystery", "Adventure", "Horror", "Romance"])
theme = st.text_input("Enter Story Theme", "A lost Kingdom")
length = st.selectbox("Story Length", ["short", "medium", "long"])

if st.button("Generate Story"):
    with st.spinner("Generating your story..."):
        try:
            response = requests.post(API_URL, json={
                "genre": genre,
                "theme": theme,
                "length": length,
                "language": "english"
            })

            if response.status_code == 200:
                data = response.json()
                title = data.get("title", "Untitled")
                content = data.get("content", "No content generated.")
                audio_url = data.get("audio_url")
                image_url = data.get("image_url", "")

                st.subheader(f"📖 {title}")
                if image_url:
                    st.image(image_url, use_column_width=True)
                st.write(content)

                st.subheader("🔊 Listen to Your Story")
                if audio_url:
                    st.audio(audio_url)
                else:
                    st.info("Audio unavailable for this story.")

                safe_theme = re.sub(r'[^a-zA-Z0-9]+', '_', theme)
                story_file = f"story_{genre}_{safe_theme}.txt"

                st.download_button(
                    label="📥 Download Story as Text",
                    data=content,
                    file_name=story_file,
                    mime="text/plain"
                )

            else:
                st.error(f"❌ Error {response.status_code}: Unable to generate the story.")
        except Exception as e:
            st.error(f"⚠️ An error occurred: {e}")
