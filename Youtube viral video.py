import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import time
import configparser

# Configuration
config = configparser.ConfigParser()
config.read('config.ini')

# YouTube API Key 
API_KEY = config.get('YOUTUBE', 'API_KEY', fallback='AIzaSyBA-WdCo1FfkfQ1G5k5M3AFTV0x-kq9IlU')
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search" 
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos" 
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title 
st.set_page_config(page_title="YouTube Viral Topics Tool", layout="wide")
st.title("📈 YouTube Viral Topics Tool")

# Sidebar Settings
with st.sidebar:
    st.header("⚙ Settings")
    days = st.number_input("Days to Search (1-30):", min_value=1, max_value=30, value=5)
    min_subs = st.number_input("Maximum Subscribers", min_value=0, value=3000, 
                              help="Filter channels with subscribers below this count")
    max_results = st.number_input("Max Results per Keyword", min_value=1, max_value=50, value=5)
    sort_by = st.selectbox("Sort Results By", ["Views", "Subscribers", "Recent"])
    
    st.header("🔍 Keyword Options")
    # Keyword categories
    keyword_categories = {
        "Relationship": ["Affair Relationship Stories", "Reddit Relationship Advice", 
                        "Reddit Relationship", "Reddit Cheating", "AITA Update"],
        "Cheating": ["Open Marriage", "Open Relationship", "X BF Caught", "Stories Cheat",
                    "X GF Reddit", "AskReddit Surviving Infidelity", "GurlCan Reddit"],
        "Reddit": ["Reddit Update", "Cheating Story Actually Happened", "Cheating Story Real",
                  "True Cheating Story", "Reddit Cheating Story", "R/Surviving Infidelity"]
    }
    selected_categories = st.multiselect("Select Categories", options=list(keyword_categories.keys()))
    
    # Allow custom keywords input
    custom_keywords = st.text_area("Add Custom Keywords", 
                                 help="Enter additional keywords to search, separated by commas")
    
    st.header("📤 Export Options")
    export_format = st.selectbox("Export Format", ["None", "CSV", "JSON", "Excel"])

# Initialize keywords list
keywords = []
for category in selected_categories:
    keywords.extend(keyword_categories[category])

# Add custom keywords
if custom_keywords:
    keywords.extend([k.strip() for k in custom_keywords.split(",") if k.strip()])

# Default keywords if none selected
if not keywords:
    keywords = [
        "Affair Relationship Stories", "Reddit Update", "Reddit Relationship Advice",
        "Reddit Cheating", "AITA Update", "Open Marriage", "Open Relationship"
    ]

# Cached API calls
@st.cache_data(ttl=3600)
def fetch_youtube_data(url, params):
    return requests.get(url, params=params).json()

# Safe API call with retries
def safe_api_call(url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            if response.status_code == 403:  # Quota exceeded
                st.error("API quota exceeded. Please try again later.")
                break
            time.sleep(2 ** attempt)  # Exponential backoff
    return None

# Process each keyword
def process_keyword(keyword, start_date, max_results, min_subs):
    try:
        # Define search parameters
        search_params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": start_date,
            "maxResults": max_results,
            "key": API_KEY,
        }

        # Fetch video data
        data = safe_api_call(YOUTUBE_SEARCH_URL, search_params)
        if not data or "items" not in data or not data["items"]:
            return []

        videos = data["items"]
        video_ids = [video["id"]["videoId"] for video in videos if "id" in video and "videoId" in video["id"]]
        channel_ids = [video["snippet"]["channelId"] for video in videos if "snippet" in video and "channelId" in video["snippet"]]

        if not video_ids or not channel_ids:
            return []

        # Fetch video statistics
        stats_params = {"part": "statistics,contentDetails", "id": ",".join(video_ids), "key": API_KEY}
        stats_data = safe_api_call(YOUTUBE_VIDEO_URL, stats_params)
        if not stats_data or "items" not in stats_data:
            return []

        # Fetch channel statistics
        channel_params = {"part": "statistics", "id": ",".join(channel_ids), "key": API_KEY}
        channel_data = safe_api_call(YOUTUBE_CHANNEL_URL, channel_params)
        if not channel_data or "items" not in channel_data:
            return []

        stats = stats_data["items"]
        channels = channel_data["items"]

        # Collect results
        keyword_results = []
        for video, stat, channel in zip(videos, stats, channels):
            try:
                title = video["snippet"].get("title", "N/A")
                description = video["snippet"].get("description", "")[:200]
                video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
                views = int(stat["statistics"].get("viewCount", 0))
                subs = int(channel["statistics"].get("subscriberCount", 0))
                duration = stat["contentDetails"].get("duration", "PT0M")
                published_at = video["snippet"].get("publishedAt", "")
                
                if subs <= min_subs:
                    keyword_results.append({
                        "Keyword": keyword,
                        "Title": title,
                        "Description": description,
                        "URL": video_url,
                        "Views": views,
                        "Subscribers": subs,
                        "Duration": duration,
                        "Published At": published_at,
                        "Channel": video["snippet"].get("channelTitle", "N/A")
                    })
            except Exception as e:
                continue
                
        return keyword_results
    except Exception as e:
        return []

# Main App Logic
if st.button("🚀 Fetch Data"):
    if not API_KEY or API_KEY == "Enter your API Key here":
        st.error("Please enter a valid YouTube API Key")
        st.stop()
        
    with st.spinner("Fetching data from YouTube..."):
        try:
            # Calculate date range
            start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
            all_results = []

            # Process keywords in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(
                    lambda k: process_keyword(k, start_date, max_results, min_subs), 
                    keywords
                ))
                for keyword_result in results:
                    all_results.extend(keyword_result)

            # Sort results
            if sort_by == "Views":
                all_results.sort(key=lambda x: x["Views"], reverse=True)
            elif sort_by == "Subscribers":
                all_results.sort(key=lambda x: x["Subscribers"], reverse=True)
            else:  # Recent
                all_results.sort(key=lambda x: x["Published At"], reverse=True)

            # Display results
            if all_results:
                st.success(f"🎉 Found {len(all_results)} results across {len(keywords)} keywords!")
                
                # Analytics Section
                st.header("📊 Analytics")
                df = pd.DataFrame(all_results)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Views Distribution")
                    st.bar_chart(df["Views"])
                with col2:
                    st.subheader("Top Performing Keywords")
                    keyword_performance = df.groupby("Keyword")["Views"].sum().sort_values(ascending=False)
                    st.dataframe(keyword_performance)
                
                # Results Section
                st.header("📺 Results")
                
                # Pagination
                items_per_page = 10
                total_pages = (len(all_results) - 1) // items_per_page + 1
                page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
                
                start_idx = (page - 1) * items_per_page
                end_idx = min(start_idx + items_per_page, len(all_results))
                
                for result in all_results[start_idx:end_idx]:
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            video_id = result['URL'].split('=')[-1]
                            st.image(f"https://img.youtube.com/vi/{video_id}/0.jpg", 
                                    width=200, caption=result['Title'][:50] + "...")
                        with col2:
                            st.markdown(f"### [{result['Title']}]({result['URL']})")
                            st.markdown(f"*Channel:* {result['Channel']} | *Subscribers:* {result['Subscribers']:,}")
                            st.markdown(f"*Views:* {result['Views']:,} | *Published:* {result['Published At'][:10]}")
                            st.progress(min(result['Views']/100000, 1.0))
                            st.markdown(f"*Description:* {result['Description']}")
                        st.write("---")
                
                # Export functionality
                if export_format != "None":
                    st.header("💾 Export Results")
                    if st.button(f"Export as {export_format}"):
                        if export_format == "CSV":
                            csv = df.to_csv(index=False)
                            st.download_button("Download CSV", csv, "youtube_results.csv")
                        elif export_format == "JSON":
                            json = df.to_json(orient="records")
                            st.download_button("Download JSON", json, "youtube_results.json")
                        elif export_format == "Excel":
                            excel = df.to_excel("youtube_results.xlsx", index=False)
                            with open("youtube_results.xlsx", "rb") as f:
                                st.download_button("Download Excel", f, "youtube_results.xlsx")
            else:
                st.warning("No results found matching your criteria.")
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
