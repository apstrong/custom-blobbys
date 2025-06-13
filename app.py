import streamlit as st
from PIL import Image, ImageDraw, ImageFilter
import requests
from io import BytesIO
import base64
import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

st.title("Custom Blobby Logo Generator")
st.write("Enter a company logo URL to see it placed on Blobby's hat!")

def advanced_logo_overlay(logo_url):
    """Advanced logo overlay with perspective, blending, and natural integration"""
    try:
        # Load base image
        base_img = Image.open("og_blobby.png").convert("RGBA")
        
        # Download logo
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(logo_url, headers=headers, timeout=10)
        logo_img = Image.open(BytesIO(response.content)).convert("RGBA")
        
        # Hat positioning (fine-tuned for your Blobby)
        hat_center_x = 550
        hat_center_y = 235  # Much lower - on the front vertical panel of the hat
        logo_width = 100     # Smaller to fit the hat panel
        logo_height = 100    # Smaller to fit the hat panel
        
        # Resize logo
        logo_resized = logo_img.resize((logo_width, logo_height), Image.LANCZOS)
        
        # Calculate position
        logo_x = hat_center_x - (logo_width // 2)
        logo_y = hat_center_y - (logo_height // 2)
        
        # Create result image
        result_img = base_img.copy()
        
        # Paste logo directly with its original transparency
        result_img.paste(logo_resized, (logo_x, logo_y), logo_resized)
        
        return result_img
        
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

def upload_to_github(image, github_token, repo_owner, repo_name, file_path):
    """Upload image to GitHub repository and return the public URL"""
    try:
        # Convert image to base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # GitHub API URL
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        
        # Headers
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if file exists (to get SHA for update)
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()["sha"]
        
        # Prepare data
        data = {
            "message": f"Add generated Blobby image: {file_path}",
            "content": img_base64
        }
        
        if sha:
            data["sha"] = sha  # Required for updating existing file
        
        # Upload/update file
        response = requests.put(url, json=data, headers=headers)
        
        if response.status_code in [200, 201]:
            # Return the raw GitHub URL
            raw_url = f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/main/{file_path}"
            return raw_url
        else:
            st.error(f"GitHub upload failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Error uploading to GitHub: {e}")
        return None

# Streamlit UI
logo_url = st.text_input("Enter logo image URL:")

# GitHub upload settings (optional)
github_token = os.getenv("GITHUB_TOKEN")
repo_owner = os.getenv("GITHUB_REPO_OWNER")
repo_name = os.getenv("GITHUB_REPO_NAME")

if not (github_token and repo_owner and repo_name):
    with st.expander("🚀 Configure GitHub Auto-upload"):
        st.write("Set up automatic upload to GitHub and get public URLs")
        st.code("""
# Create a .env file with:
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO_OWNER=your_username
GITHUB_REPO_NAME=your_repo_name
        """)
        st.write("Or enter manually:")
        manual_token = st.text_input("GitHub Personal Access Token:", type="password", help="Create one at https://github.com/settings/tokens")
        manual_owner = st.text_input("Repository Owner:", placeholder="your-username")
        manual_name = st.text_input("Repository Name:", placeholder="your-repo-name")
        
        # Use manual inputs if provided
        if manual_token and manual_owner and manual_name:
            github_token = manual_token
            repo_owner = manual_owner
            repo_name = manual_name

if logo_url:
    if st.button("Generate custom Blobby"):
        with st.spinner("Adding logo to Blobby's hat..."):
            try:
                result_img = advanced_logo_overlay(logo_url)
                if result_img:
                    # Generate filename with timestamp
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"blobby_with_logo_{timestamp}.png"
                    
                    # Store result in session state for GitHub upload
                    st.session_state.result_img = result_img
                    st.session_state.filename = filename
                    st.session_state.has_generated_image = True

            except Exception as e:
                st.error(f"Error: {e}")

# Show generated image and options if available
if hasattr(st.session_state, 'has_generated_image') and st.session_state.has_generated_image:
    if hasattr(st.session_state, 'result_img') and st.session_state.result_img is not None:
        st.image(st.session_state.result_img, caption="", use_container_width=True)
        
        # Buttons side by side
        col1, col2 = st.columns(2)
        
        with col1:
            # Offer download
            buffered = BytesIO()
            st.session_state.result_img.save(buffered, format="PNG")
            st.download_button(
                label="📥 Download Image",
                data=buffered.getvalue(),
                file_name=st.session_state.filename,
                mime="image/png",
                use_container_width=True
            )
        
        with col2:
            # GitHub upload button if credentials provided
            if github_token and repo_owner and repo_name:
                if st.button("🚀 Upload to GitHub", type="secondary", use_container_width=True):
                    with st.spinner("Uploading to GitHub..."):
                        github_path = f"generated_images/{st.session_state.filename}"
                        public_url = upload_to_github(st.session_state.result_img, github_token, repo_owner, repo_name, github_path)
                        
                        if public_url:
                            st.success("🎉 Successfully uploaded to GitHub!")
                            st.code(public_url, language="text")
                            st.write("You can now use this URL to reference your image publicly!")
                            # Store success in session state
                            st.session_state.upload_success = True
                            st.session_state.public_url = public_url
                            st.rerun()
                        else:
                            st.error("❌ Upload failed. Please check your GitHub credentials and repository permissions.")
else:
    # Show original image
    base_img = Image.open("og_blobby.png")
    st.image(base_img, caption="", use_container_width=True)
    

# Show upload success if it exists in session state
if hasattr(st.session_state, 'upload_success') and st.session_state.upload_success:
    if hasattr(st.session_state, 'public_url'):
        st.success("🎉 Last upload was successful!")
        st.code(st.session_state.public_url, language="text")
