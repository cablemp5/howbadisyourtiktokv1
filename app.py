import json
import random
import re
import time
import zipfile
import pandas as pd
import streamlit as st
from concurrent.futures import as_completed
from io import StringIO, BytesIO
from google import genai
from requests_futures.sessions import FuturesSession

num_links_to_parse = 0
num_links_to_analyze = 0
num_items_to_show = 0

TAG_IGNORE = ["#fyp", "#viral", "#foryou", "fy", "#foryoupage", "#trending",
              "#fyp", "#fypシ゚viral", "#fypシ", "#blowthisup",
              "#fyppppppppppppppppppppppp", "#fy", "#fypage", "#viralvideo",
              "#xyzbca"]

def gemini_analysis(payload):

  client = genai.Client(api_key=st.secrets.key)
  prompt = st.secrets.prompt

  with (st.spinner('Loading AI analysis...')):
    try:
      response = client.models.generate_content(model="gemini-2.0-flash",
                                                contents=[
                                                  prompt + str(payload)])
      return response.text
    except Exception as e:
      return e

def parse_tiktok_links(zip_file, selection):
  with zipfile.ZipFile(zip_file, 'r') as z:
    with z.open('user_data_tiktok.json') as f:
      html_data = json.load(f)

  links = []
  liked_videos = [i["link"] for i in
                  html_data["Activity"]["Like List"]["ItemFavoriteList"]]
  saved_videos = [i["Link"] for i in
                  html_data["Activity"]["Favorite Videos"]["FavoriteVideoList"]]

  if "Liked" in selection and "Saved" in selection:
    while liked_videos or saved_videos:
      if liked_videos:
        links.append(liked_videos.pop(0))
      if saved_videos:
        links.append(saved_videos.pop(0))
  elif "Liked" in selection:
    links = liked_videos
  elif "Saved" in selection:
    links = saved_videos

  return list(set(links))

def sort_dict(dictionary):
  sorted_dict = (
    dict(sorted(dictionary.items(), key=lambda x: x[1], reverse=True)))

  for to_pop in TAG_IGNORE:
    sorted_dict.pop(to_pop, None)

  return sorted_dict

def scrape_tiktok(links, st_progress_bar):

  description_list = []
  hashtag_dict = {}
  username_dict = {}
  avatar_dict = {}

  num_to_scrape = min(num_links_to_parse, len(links))
  num_scraped = 0
  start_time = time.time()

  with FuturesSession() as session:
    futures = [session.get(links[i]) for i in range(min(num_links_to_parse, len(links)))]

    for future in as_completed(futures):
      response = future.result()
      response.raw.chunked = True
      response.encoding = 'utf-8'
      html = response.text

      num_scraped += 1
      elapsed_time = time.time() - start_time
      avg_time_per_video = elapsed_time / num_scraped
      remaining_time = (num_to_scrape - num_scraped) * avg_time_per_video

      eta_minutes = int(remaining_time // 60)
      eta_seconds = int(remaining_time % 60)

      st_progress_bar.progress(num_scraped / num_to_scrape,
                               text=f"**{num_scraped}/{num_to_scrape} videos scanned...  |   ⏳ Time Remaining - {eta_minutes:02d}:{eta_seconds:02d}**")

      description = re.search('\"desc\":\"([^\"]+)\"', html)
      if not description:
        description = ""
      else:
        description = description.group(1)
      description_list.append(description)

      username = re.search('\"uniqueId\":\"([^\"]+)\",\"nickname\":\"([^\"]+)\"', html)
      if not username:
        username = "Name Unavailable"
      else:
        username = "@" + username.group(1)
      username_dict.setdefault(username, 0)
      username_dict[username] += 1

      avatar = re.search('\"avatarMedium\":\"([^\"]+)\"', html)
      if not avatar:
        avatar = ""
      else:
        avatar = avatar.group(1).replace("\\u002F", "/")
      avatar_dict[username] = avatar

      hashtags = re.findall("#\S+", description)
      for tag in hashtags:
        hashtag_dict.setdefault(tag, 0)
        hashtag_dict[tag] += 1

  session.close()
  time.sleep(0.5)
  st_progress_bar.empty()

  return description_list, hashtag_dict, username_dict, avatar_dict

def on_upload(zip_file, selection, st_progress_bar):
  links = parse_tiktok_links(zip_file, selection)

  description_list, hashtag_dict, username_dict, avatar_dict = scrape_tiktok(
      links, st_progress_bar)

  sorted_hashtags = sort_dict(hashtag_dict)
  sorted_users = sort_dict(username_dict)

  if "Name Unavailable" in sorted_users:
    del sorted_users["Name Unavailable"]

  num_hashtags_to_show = min(num_items_to_show, len(sorted_hashtags))
  top_hashtags_to_show = dict(list(sorted_hashtags.items())[:num_hashtags_to_show])

  num_users_to_show = min(num_items_to_show, len(sorted_users))
  top_users = dict(list(sorted_users.items())[:num_users_to_show])

  num_hashtags_to_analyze = min(num_links_to_analyze, len(sorted_hashtags))
  top_hashtags_to_analyze = dict(list(sorted_hashtags.items())[:num_hashtags_to_analyze])

  description_str = str(description_list)
  prompt = str(top_hashtags_to_analyze) + description_str

  gemini_result = gemini_analysis(prompt)

  return top_users, top_hashtags_to_show, avatar_dict, gemini_result

def stream_data(text):
  for word in text.split(" "):
    yield word + " "
    time.sleep(random.random() * 0.1)


def update_checkbox():
  st.session_state.show_text_input = not st.session_state.checkbox_state
  st.rerun()

if "show_text_input" not in st.session_state:
  st.session_state.show_text_input = True
if "checkbox_state" not in st.session_state:
  st.session_state.checkbox_state = False

st.set_page_config(
    page_title="How bad is your TikTok?",
    page_icon="https://i.postimg.cc/BnLW2WLk/favicon.png",
)

st.image("https://i.postimg.cc/BnLW2WLk/favicon.png", width=100)
st.title("How Bad Is Your Tiktok?")
st.write(
    'Curious what **AI** really thinks of your TikTok feed? This self-proclaimed "content-connoisseur" will dive into your liked videos and provide a brutally honest—*and painfully accurate*—assessment of your digital footprint.')
st.info(
    "This project was heavily inspired by [**How Bad Is Your Streaming Music?**](https://pudding.cool/2021/10/judge-my-music/) by The Pudding!",
    icon="✨")
st.warning(
    "By using this website, you acknowledge that analyzing your TikTok activity requires uploading your TikTok data and, optionally, providing a Gemini API key. **All data remains private and is neither stored nor viewed by anyone other than you and Google's Gemini AI**. For your security, please avoid including any personally identifiable information in the data you upload. Additionally, if you choose to use a Gemini API key, we recommend generating a new key that is not linked to any other projects to ensure the integrity and security of your data.",
    icon='⚠️')
st.success(
    "If you are on mobile, turn on **Wide Mode** located in the settings in the top right (**⋮**) for the best user experience!",
    icon='👀')

with st.container(border=True):
  st.write("**📂  How To Download And Analyze Your TikTok Data:**")
  st.caption(
      "**1.** Follow the official [TikTok data request guide](https://support.tiktok.com/en/account-and-privacy/personalized-ads-and-data/requesting-your-data) to download your data  \n  **2.** When prompted, ensure you select the following settings using the reference images below for guidance:")
  st.image("https://i.postimg.cc/HL2D6k0R/darkinstructionsrounded.png",
           use_container_width=True)
  st.caption(
      '**3.** Upload the `TikTok_Data_XXXXXXXXXX.zip` file below and click **"🚀 Analyze Your Algorithm"** to start the analysis')

with st.expander("**Additional Help**", icon="💡"):
  st.caption(
      '🚨 :red[The website will use the testing/demo key by default. If you receive a `429 RESOURCE_EXHAUSTED` error, please create and use your own key! Otherwise, IGNORE THE BELOW INSTRUCTIONS and upload your file to the website to start your scan. To use your own key toggle the "Use the testing/demo Gemini API key" box and proceed with the below instructions]')
  st.write("**Generating a Gemini API key:**")
  st.caption(
      "1. Sign in with your Google account and create and your Gemini API key [here](https://aistudio.google.com/app/apikey)  \n  2. After signing in, select the option to use the Gemini API and accept the terms and conditions  \n  3. Generate your API key and copy it, using the reference images below for guidance")
  st.image("https://i.postimg.cc/d07NyQHG/inst1rounded.png",
           use_container_width=True)
  st.image("https://i.postimg.cc/cCcFSvCG/inst2rounded.png",
           use_container_width=True)
  st.caption(
      '4. Toggle **"Use the testing/demo Gemini API key"** to off and paste the copied API key into the text input field labeled **"Enter your Gemini API Key:"**')

st.divider()

with st.container(border=True):
  if "testKey" not in st.session_state:
    st.session_state.testKey = False
  if "key" not in st.session_state:
    st.session_state.key = ""
  if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

  st.session_state.testKey = st.toggle(
      label="**Use the testing/demo Gemini API key**",
      help="This key is for testing/demos and is enabled by default for ease of use. The key may not work! If you receive a 429 RESOURCE_EXHAUSTED error, please create and use your own key using the instructions in the Additional Help section.",
      value=True
  )

  if not st.session_state.testKey:
    st.session_state.key = st.text_input(
        label="**Enter your Gemini API Key:**",
        placeholder="e.g. AIsaSyDLyhv4ImdpQAqd8H_R54oj56VGdVFvnPK",
        help="Check the Help section to learn how to generate an API key"
    )

  selection = st.pills(
      "**Select the type of videos to scan**:",
      options=["Saved", "Liked"],
      default=["Saved"],
      selection_mode='multi',
      help="Most accurate with only **Saved** videos. Use **Liked** when there isn't a large amount of saved videos to scan"
  )

  st.session_state.uploaded_file = st.file_uploader(
      "**Upload the .zip file containing your TikTok Data:**", type=".zip",
      accept_multiple_files=False,
      help="Check the Help section to learn how to download the correct data",
  )

  col1, col2 = st.columns([0.65, 0.35], gap="small")
  with col2.popover("**Additional Settings**", icon="⚙️",
                    use_container_width=True):
    st.markdown(
        """
        <style>
        [data-testid="stSliderTickBarMin"] {
          font-family:Source Sans Pro, sans-serif;
        }
        [data-testid="stSliderThumbValue"] {
          font-family:Source Sans Pro, sans-serif;
        }
        [data-testid="stSliderTickBarMax"] {
          font-family:Source Sans Pro, sans-serif;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    to_parse = st.slider("**📺 Videos to scan**:", min_value=1,
                         max_value=10000, value=5000,
                         help="Default: 5000 videos")
    to_analyze = st.slider("**📝 Hashtags to scan:**", min_value=10,
                           max_value=500, value=500,
                           help="Default: all hashtags (up to 500)")
    to_show = st.slider("**👁️‍🗨️ Items to preview:**",
                        min_value=3, max_value=100, value=25,
                        help="Default: 25 hashtags/users (up to 100)")

  if col1.button(label="**🚀 Analyze your algorithm**", use_container_width=True,
                 type="secondary"):
    if not st.session_state.testKey and not st.session_state.key:
      st.error("**💥 You haven't added a Gemini API key!**")
    elif st.session_state.uploaded_file is None:
      st.error("**💥 You haven't uploaded a file!**")
    elif not selection:
      st.error("**💥 You must select at least 1 type of video to scan!**")
    else:
      zip_file = BytesIO(st.session_state.uploaded_file.getvalue())

      num_links_to_parse = to_parse
      num_links_to_analyze = to_analyze
      num_items_to_show = to_show

      st_progress_bar = st.progress(0)

      username_dict, hashtag_dict, pfp_dict, gemini_response = on_upload(
        zip_file,
        selection,
        st_progress_bar=st_progress_bar)

      st.divider()
      st.header("**💬 Your most frequent hashtags and users:**")

      hashtags_to_show = list(hashtag_dict.keys())[:num_items_to_show]
      hashtag_counts_to_show = [str(hashtag_dict[hashtag]) for hashtag in
                                hashtags_to_show]

      df1 = pd.DataFrame(
          list(zip(hashtags_to_show, hashtag_counts_to_show)),
          columns=["#", "Number of videos"]
      )

      users_to_show = list(username_dict.keys())[:num_items_to_show]
      avatars_to_show = [pfp_dict.get(user, "") for user in users_to_show]
      numvideos_to_show = [str(username_dict[user]) for user in users_to_show]
      links_to_show = ["https://www.tiktok.com/" + user for user in
                       users_to_show]

      df2 = pd.DataFrame(
          list(zip(avatars_to_show, users_to_show, numvideos_to_show,
                   links_to_show)),
          columns=["Avatar", "Username", "# of Videos", "Link"]
      )

      st.dataframe(df1, hide_index=True, use_container_width=True)
      st.dataframe(df2, hide_index=True,
                   column_config={"Link": st.column_config.LinkColumn("Link"),
                                  "Avatar": st.column_config.ImageColumn()},
                   use_container_width=True)

      if isinstance(gemini_response, Exception):
        st.error(
            f'**👾 There was an unexpected error generating your AI analysis. Check the "Additional Help" section for more info:**\n\n:red[`{str(gemini_response)}`]')
      else:
        st.header("**🖨️ Your AI analysis:**")
        st.write_stream(stream_data(gemini_response))