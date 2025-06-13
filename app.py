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

# Logo URL input
logo_url = st.text_input("Enter logo image URL:")

# Set conservative defaults to preserve original logo quality
bg_removal_tolerance = 25  # Gentle background removal
contrast_boost = 1.0       # No contrast enhancement - preserve original
enable_smart_crop = True   # Keep smart cropping for better framing
enable_edge_smoothing = False  # No edge smoothing to prevent blur
preserve_quality = True    # Always use quality preservation

# Logo positioning and sizing options
with st.expander("📍 Logo Position & Size Controls"):
    st.write("**Adjust where and how big the logo appears on Blobby's hat:**")
    
    pos_col1, pos_col2 = st.columns(2)
    with pos_col1:
        st.write("**Position Controls:**")
        hat_center_x = st.slider("Horizontal Position", 400, 700, 550, 5,
                                help="Move logo left/right on Blobby's hat")
        hat_center_y = st.slider("Vertical Position", 100, 300, 175, 5,
                                help="Move logo up/down on Blobby's hat")
    
    with pos_col2:
        st.write("**Size Control:**")
        logo_size = st.slider("Logo Size", 50, 200, 100, 5,
                             help="Adjust logo size in pixels (square)")
        # Set both width and height to the same value since logos are square
        logo_width = logo_size
        logo_height = logo_size

# Preview option
show_preview = st.checkbox("🔍 Show processing preview", help="Display original vs processed logo comparison. This tool automatically removes backgrounds from the logo and squares the dimensions")


def remove_background_smart(image, tolerance=30):
    """Smart background removal using multiple techniques with anti-aliasing"""
    img = image.convert("RGBA")
    data = img.getdata()
    
    # Get corner pixels to identify potential background colors
    width, height = img.size
    corners = [
        img.getpixel((0, 0)),
        img.getpixel((width-1, 0)),
        img.getpixel((0, height-1)),
        img.getpixel((width-1, height-1))
    ]
    
    # Find most common corner color (likely background)
    from collections import Counter
    corner_colors = [c[:3] for c in corners if len(c) >= 3]  # RGB only
    if corner_colors:
        most_common_bg = Counter(corner_colors).most_common(1)[0][0]
        
        # Remove background with gradual transparency for smoother edges
        new_data = []
        
        for item in data:
            r, g, b = item[:3]
            bg_r, bg_g, bg_b = most_common_bg
            
            # Calculate color distance
            color_distance = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
            
            if color_distance < tolerance:
                # Fully transparent for close matches
                new_data.append((r, g, b, 0))
            elif color_distance < tolerance * 1.5:
                # Partial transparency for edge smoothing
                alpha = int(255 * (color_distance - tolerance) / (tolerance * 0.5))
                new_data.append((r, g, b, min(255, alpha)))
            else:
                # Keep original pixel
                new_data.append(item if len(item) == 4 else (r, g, b, 255))
        
        img.putdata(new_data)
    
    return img

def smart_crop_logo(image):
    """Intelligently crop to focus on the main logo content"""
    img = image.convert("RGBA")
    
    # Find bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        # Add small padding around the content
        x1, y1, x2, y2 = bbox
        width, height = img.size
        padding = min(width, height) // 20  # 5% padding
        
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(width, x2 + padding)
        y2 = min(height, y2 + padding)
        
        return img.crop((x1, y1, x2, y2))
    
    return img

def smooth_edges(image):
    """Apply edge smoothing for cleaner appearance"""
    img = image.convert("RGBA")
    
    # Apply very subtle gaussian blur to alpha channel only for anti-aliasing
    r, g, b, a = img.split()
    a_smoothed = a.filter(ImageFilter.GaussianBlur(radius=0.3))
    
    return Image.merge("RGBA", (r, g, b, a_smoothed))

def make_square_with_padding(image, target_size=300):
    """Convert any image to square with transparent padding using high-quality resampling"""
    img = image.convert("RGBA")
    width, height = img.size
    
    # Create square canvas with transparent background
    square_img = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    
    # Calculate scaling to fit image within square while preserving aspect ratio
    scale = min(target_size / width, target_size / height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # Use high-quality resampling for better results
    # LANCZOS for downscaling, BICUBIC for upscaling
    resample_method = Image.LANCZOS if scale < 1 else Image.BICUBIC
    resized_img = img.resize((new_width, new_height), resample_method)
    
    # Center the image on the square canvas
    x_offset = (target_size - new_width) // 2
    y_offset = (target_size - new_height) // 2
    
    square_img.paste(resized_img, (x_offset, y_offset), resized_img)
    
    return square_img

def enhance_logo_contrast(image, factor=1.2):
    """Enhance logo contrast and remove noise"""
    img = image.convert("RGBA")
    
    # Split channels
    r, g, b, a = img.split()
    
    # Enhance contrast on RGB channels
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Contrast(Image.merge("RGB", (r, g, b)))
    enhanced_rgb = enhancer.enhance(factor)
    
    # Merge back with alpha
    r_enh, g_enh, b_enh = enhanced_rgb.split()
    enhanced_img = Image.merge("RGBA", (r_enh, g_enh, b_enh, a))
    
    return enhanced_img

def process_logo_only(logo_url, bg_tolerance=30, contrast_factor=1.2, 
                     smart_crop=True, edge_smooth=True):
    """Process logo without overlaying on Blobby - for preview purposes"""
    try:
        # Download logo
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(logo_url, headers=headers, timeout=10)
        original_logo = Image.open(BytesIO(response.content)).convert("RGBA")
        
        # Apply same processing pipeline
        logo_processed = remove_background_smart(original_logo, bg_tolerance)
        
        if smart_crop:
            logo_processed = smart_crop_logo(logo_processed)
        
        logo_processed = make_square_with_padding(logo_processed, 300)
        logo_processed = enhance_logo_contrast(logo_processed, contrast_factor)
        
        if edge_smooth:
            logo_processed = smooth_edges(logo_processed)
        
        return original_logo, logo_processed
    except:
        return None, None

def advanced_logo_overlay(logo_url, bg_tolerance=30, contrast_factor=1.2, 
                         smart_crop=True, edge_smooth=True, preserve_quality=True,
                         hat_center_x=550, hat_center_y=175, logo_width=100, logo_height=100):
    """Advanced logo overlay with smart preprocessing and natural integration"""
    try:
        # Load base image
        base_img = Image.open("og_blobby.png").convert("RGBA")
        
        # Download logo
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(logo_url, headers=headers, timeout=10)
        original_logo = Image.open(BytesIO(response.content)).convert("RGBA")
        
        # LOGO PREPROCESSING PIPELINE
        processing_steps = []
        
        # Step 1: Gentle background removal to preserve original colors
        logo_processed = remove_background_smart(original_logo, bg_tolerance)
        processing_steps.append("Gentle background removal")
        
        # Step 2: Smart cropping (optional)
        if smart_crop:
            logo_processed = smart_crop_logo(logo_processed)
            processing_steps.append("Smart cropping")
        
        # Step 3: Make square with proper padding (use larger intermediate size for quality)
        intermediate_size = 600 if preserve_quality else 300
        logo_processed = make_square_with_padding(logo_processed, intermediate_size)
        processing_steps.append("Square padding")
        
        # Step 4: Preserve original contrast and colors
        if contrast_factor != 1.0:
            logo_processed = enhance_logo_contrast(logo_processed, contrast_factor)
            processing_steps.append("Minimal contrast adjustment")
        else:
            processing_steps.append("Original contrast preserved")
        
        # Step 5: Skip edge smoothing to maintain original sharpness
        if edge_smooth:
            logo_processed = smooth_edges(logo_processed)
            processing_steps.append("Edge smoothing")
        else:
            processing_steps.append("Original sharpness preserved")
        
        # Step 6: Final resize for hat placement
        # Use user-specified positioning and sizing parameters
        
        logo_final = logo_processed.resize((logo_width, logo_height), Image.LANCZOS)
        
        # Calculate position
        logo_x = hat_center_x - (logo_width // 2)
        logo_y = hat_center_y - (logo_height // 2)
        
        # Create result image
        result_img = base_img.copy()
        
        # Paste logo with enhanced alpha blending
        result_img.paste(logo_final, (logo_x, logo_y), logo_final)
        
        return result_img, {
            'original_size': original_logo.size,
            'had_transparency': original_logo.mode == 'RGBA',
            'processing_steps': processing_steps,
            'processed_logo': logo_processed,  # Include processed logo for preview
            'settings_used': {
                'bg_tolerance': bg_tolerance,
                'contrast_factor': contrast_factor,
                'smart_crop': smart_crop,
                'edge_smooth': edge_smooth,
                'preserve_quality': preserve_quality,
                'hat_center_x': hat_center_x,
                'hat_center_y': hat_center_y,
                'logo_width': logo_width,
                'logo_height': logo_height
            }
        }
        
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None, None

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

if st.button("Generate custom Blobby"):
    if not logo_url:
        st.warning("⚠️ Please enter a logo URL first!")
    else:
        with st.spinner("Processing logo and adding to Blobby's hat..."):
            try:
                result_img, processing_info = advanced_logo_overlay(
                    logo_url, 
                    bg_tolerance=bg_removal_tolerance,
                    contrast_factor=contrast_boost,
                    smart_crop=enable_smart_crop,
                    edge_smooth=enable_edge_smoothing,
                    preserve_quality=preserve_quality,
                    hat_center_x=hat_center_x,
                    hat_center_y=hat_center_y,
                    logo_width=logo_width,
                    logo_height=logo_height
                )
                if result_img:
                    # Generate filename with timestamp
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"blobby_with_logo_{timestamp}.png"
                    
                    # Store result in session state for GitHub upload
                    st.session_state.result_img = result_img
                    st.session_state.filename = filename
                    st.session_state.processing_info = processing_info
                    st.session_state.has_generated_image = True
                    
                    # Show preview comparison if requested
                    if show_preview and processing_info:
                        st.write("### 🔍 Processing Preview")
                        prev_col1, prev_col2 = st.columns(2)
                        
                        with prev_col1:
                            st.write("**Original Logo**")
                            # Download and show original
                            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                            response = requests.get(logo_url, headers=headers, timeout=10)
                            original_for_preview = Image.open(BytesIO(response.content))
                            st.image(original_for_preview, use_container_width=True)
                        
                        with prev_col2:
                            st.write("**Processed Logo**")
                            # Show processed version from processing info
                            if 'processed_logo' in processing_info:
                                st.image(processing_info['processed_logo'], use_container_width=True)
                            else:
                                st.write("Processed version not available for preview")
                    


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
                if st.button("🚀 Upload to GitHub to Get URL", type="secondary", use_container_width=True):
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
        st.success("🎉 Upload was successful!")
        st.code(st.session_state.public_url, language="text")
