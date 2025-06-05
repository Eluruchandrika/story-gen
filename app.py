import streamlit as st
import requests

API_URL = "https://ai-story-backend-1h6m.onrender.com/generate_story"

st.title("AI-Powered Creative Story Generator")
st.write("Generate unique AI-Powered Stories and listion to them!")

genre = st.selectbox("Select Genre",["Fantasy", "Sci-Fi" , "Mystery","Adventure","Horror","Romance"])
theme = st.text_input("Enter Story Theme", "A lost Kingdom")
length = st.selectbox("Story Length" , ["short","medium","long"])

if st.button("Generate Story"):
    with st.spinner("Generating Your Story..."):
        response = requests.post(API_URL,json={"genre":genre,"theme":theme,"length":length})

        if response.status_code ==200:
            data = response.json()
            story_text=data["story"]
            audio_url=data["audio_url"]

            st.subheader(" your AI-Generated Story")
            st.write(story_text)

            st.subheader("Listion to Your Story")
            st.audio(audio_url)

            story_file = f"story_{genre}_{theme}.txt"
            with open(story_file,"w", encoding="utf-8") as f:
                f.write(story_text)
            
            st.download_button(label="Download Story as Text", data=story_text ,file_name=story_file, mime="text/plain")

        else:
            st.error("Error while generating the story. Please try again")
