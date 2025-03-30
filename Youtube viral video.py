import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
import os
import time

# YouTube API Configuration (use Streamlit secrets for security)
API_KEY = st.secrets["AIzaSyBA-WdCo1FfkfQ1G5k5M3AFTV0x-kq9IlU"]  # Ensure the API key is in the secrets file
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title with Advanced Options
st.title("🚀 AI-Powered YouTube Viral Topics Analyzer")

# Sidebar for Advanced Filters
with st.sidebar:
    st.header("🔍 Filters")
    days = st.slider("Days to Search:", 1, 30, 5)
    min_views = st.number_input("Minimum Views:", min_value=0, value=1000)
    max_views = st.number_input("Maximum Views:", min_value=0, value=1000000)
    max_subs = st.number_input("Max Subscribers:", min_value=0, value=3000)
    language = st.selectbox("Language:", ["en", "hi", "es", "fr"])  # English, Hindi, Spanish, French

# Dynamic Keyword Management
st.subheader("🎯 Keywords")
uploaded_file = st.file_uploader("Upload CSV with Keywords (or use defaults)", type=["csv"])

# Handling CSV upload
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()  # Strip extra spaces from column names
        if "Keyword" in df.columns:
            keywords = df["Keyword"].tolist()
        else:
            st.warning("CSV file doesn't contain a 'Keyword' column. Using default keywords.")
            keywords = [
                "Affair Relationship Stories", "Reddit Update", "Reddit Relationship Advice",
                "Cheating Story Real", "True Cheating Story", "Surviving Infidelity"
            ]
    except Exception as e:
        st.error(f"Error reading CSV file: {str(e)}")
        keywords = [
            "Affair Relationship Stories", "Reddit Update", "Reddit Relationship Advice",
            "Cheating Story Real", "True Cheating Story", "Surviving Infidelity"
        ]
else:
    keywords = [
        "Affair Relationship Stories", "Reddit Update", "Reddit Relationship Advice",
        "Cheating Story Real", "True Cheating Story", "Surviving Infidelity"
    ]

# AI-Powered Keyword Expansion (TF-IDF based)
if st.checkbox("🔍 Use AI to Expand Keywords"):
    vectorizer = TfidfVectorizer(max_features=20)
    tfidf_matrix = vectorizer.fit_transform(keywords)
    additional_keywords = vectorizer.get_feature_names_out()
    keywords.extend(additional_keywords)
    st.success(f"Added AI-suggested keywords: {', '.join(additional_keywords)}")

# Fetch Data Button
if st.button("🚀 Fetch & Analyze Data"):
    try:
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat("T") + "Z"
        all_results = []

        for keyword in keywords:
            # YouTube API Request
            search_params = {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "publishedAfter": start_date,
                "relevanceLanguage": language,
                "maxResults": 10,
                "key": API_KEY,
            }
            response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
            if response.status_code != 200:
                st.error(f"Failed to fetch data for keyword '{keyword}': {response.status_code}")
                continue
            data = response.json()

            if "items" not in data:
                continue

            # Process Videos
            for video in data["items"]:
                video_id = video["id"]["videoId"]
                channel_id = video["snippet"]["channelId"]

                # Fetch Video Stats
                stats_response = requests.get(YOUTUBE_VIDEO_URL, params={
                    "part": "statistics,contentDetails",
                    "id": video_id,
                    "key": API_KEY
                })
                if stats_response.status_code != 200:
                    st.error(f"Failed to fetch video stats for {video_id}: {stats_response.status_code}")
                    continue
                stats_data = stats_response.json().get("items", [{}])[0]

                # Fetch Channel Stats
                channel_response = requests.get(YOUTUBE_CHANNEL_URL, params={
                    "part": "statistics",
                    "id": channel_id,
                    "key": API_KEY
                })
                if channel_response.status_code != 200:
                    st.error(f"Failed to fetch channel stats for {channel_id}: {channel_response.status_code}")
                    continue
                channel_data = channel_response.json().get("items", [{}])[0]

                # Extract Data
                views = int(stats_data.get("statistics", {}).get("viewCount", 0))
                subs = int(channel_data.get("statistics", {}).get("subscriberCount", 0))
                duration = stats_data.get("contentDetails", {}).get("duration", "PT0M")

                # Apply Filters
                if (min_views <= views <= max_views) and (subs <= max_subs):
                    # Sentiment Analysis (AI)
                    title = video["snippet"]["title"]
                    sentiment = TextBlob(title).sentiment.polarity
                    sentiment_label = "😊 Positive" if sentiment > 0 else "😠 Negative" if sentiment < 0 else "😐 Neutral"

                    all_results.append({
                        "Keyword": keyword,
                        "Title": title,
                        "URL": f"https://youtu.be/{video_id}",
                        "Views": views,
                        "Subscribers": subs,
                        "Duration": duration,
                        "Sentiment": sentiment_label,
                        "Channel": video["snippet"]["channelTitle"]
                    })

            # Add a small delay to prevent hitting API rate limits
            time.sleep(1)

        # Display Results
        if all_results:
            df = pd.DataFrame(all_results)
            st.success(f"📊 Found {len(df)} videos!")

            # AI-Powered Insights
            st.subheader("🤖 AI Insights")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Avg. Views", f"{df['Views'].mean():,.0f}")
                st.metric("Top Keyword", df["Keyword"].mode()[0])
            with col2:
                st.metric("Avg. Subscribers", f"{df['Subscribers'].mean():,.0f}")
                st.metric("Dominant Sentiment", df["Sentiment"].mode()[0])

            # Visualizations
            st.subheader("📈 Trends")
            fig, ax = plt.subplots()
            df["Keyword"].value_counts().plot(kind="bar", ax=ax)
            st.pyplot(fig)

            # Video Previews
            st.subheader("🎥 Top Videos")
            for _, row in df.head(3).iterrows():
                st.video(row["URL"])
                st.write(f"{row['Title']} | Views: {row['Views']} | Sentiment: {row['Sentiment']}")

            # Export Data
            st.download_button(
                "💾 Download CSV",
                df.to_csv(index=False),
                file_name="youtube_trends.csv"
            )
        else:
            st.warning("No videos found matching your criteria.")

    except Exception as e:
        st.error(f"Error: {str(e)}")

# Dark Mode Toggle (UI Enhancement)
st.sidebar.markdown("---")
dark_mode = st.sidebar.checkbox("🌙 Dark Mode")
if dark_mode:
    st.markdown("""
        <style>
            .stApp { background-color: #1e1e1e; color: white; }
            .sidebar .sidebar-content { background-color: #1e1e1e; }
        </style>
    """, unsafe_allow_html=True)
