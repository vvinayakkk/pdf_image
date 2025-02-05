import streamlit as st
import fitz  # PyMuPDF
import io
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Gemini model
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')

class SequentialDrawingAnalyzer:
    def __init__(self):
        self.drawings_list = []  # Store all extracted images info
        self.analyzed_drawings = []  # Store analyzed results
        
    def extract_drawings_list(self, pdf_bytes):
        """First pass: Extract all drawings from PDF and create a list"""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_idx, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        self.drawings_list.append({
                            'page': page_num + 1,
                            'drawing_number': img_idx + 1,
                            'xref': xref,
                            'image_bytes': image_bytes
                        })
                        
                    except Exception as img_error:
                        st.warning(f"Could not extract drawing {img_idx + 1} on page {page_num + 1}: {str(img_error)}")
            
            doc.close()
            return len(self.drawings_list)
            
        except Exception as e:
            st.error(f"Error extracting drawings: {str(e)}")
            return 0

    def analyze_drawing(self, drawing_info):
        """Analyze a single drawing"""
        try:
            image = Image.open(io.BytesIO(drawing_info['image_bytes']))
            
            engineering_prompt = """
            Analyze this engineering drawing in detail. Please provide:
            1. Drawing Type and Purpose
            - Identify the type of drawing (assembly, detail, section view, etc.)
            - Main purpose and function of the depicted component/system
            
            2. Dimensional Analysis
            - Key dimensions and measurements
            - Scale and proportions
            - Tolerances if specified
            
            3. Component Details
            - List all visible components and parts
            - Materials specifications if indicated
            - Surface finish markings
            
            4. Technical Specifications
            - Any technical notes or special instructions
            - Welding symbols or special instructions
            - Reference standards mentioned
            
            5. Critical Features
            - Important geometric features
            - Key interfaces or connections
            - Safety-critical aspects
            """
            
            response = gemini_model.generate_content([
                engineering_prompt,
                image
            ])
            
            return {
                'page': drawing_info['page'],
                'drawing_number': drawing_info['drawing_number'],
                'image': image,
                'analysis': response.text
            }
            
        except Exception as e:
            st.error(f"Error analyzing drawing {drawing_info['drawing_number']}: {str(e)}")
            return None

# Streamlit UI
st.title("Sequential Engineering Drawing Analyzer")

# Initialize session state
if "processed" not in st.session_state:
    st.session_state.processed = False
if "analyzer" not in st.session_state:
    st.session_state.analyzer = SequentialDrawingAnalyzer()
if "current_analysis_index" not in st.session_state:
    st.session_state.current_analysis_index = 0
if "analyzed_drawings" not in st.session_state:
    st.session_state.analyzed_drawings = []

# File upload
pdf_file = st.file_uploader("Upload PDF containing engineering drawings", type="pdf")

if pdf_file is not None:
    # First pass: Extract all drawings if not already processed
    if not st.session_state.processed:
        try:
            with st.spinner("Extracting drawings from PDF..."):
                pdf_bytes = pdf_file.getvalue()
                total_drawings = st.session_state.analyzer.extract_drawings_list(pdf_bytes)
                st.session_state.processed = True
                
                st.success(f"Found {total_drawings} drawings in the PDF!")
                
                # Display list of all drawings
                st.subheader("List of Extracted Drawings:")
                for drawing in st.session_state.analyzer.drawings_list:
                    st.write(f"Drawing {drawing['drawing_number']} on Page {drawing['page']}")
                
                st.markdown("---")
                
        except Exception as e:
            st.error(f"Failed to process PDF: {str(e)}")
            st.session_state.processed = False

    # Process drawings sequentially
    if st.session_state.processed:
        remaining_drawings = min(5, len(st.session_state.analyzer.drawings_list)) - st.session_state.current_analysis_index
        
        if remaining_drawings > 0:
            st.subheader(f"Analyzing Drawing {st.session_state.current_analysis_index + 1} of {min(5, len(st.session_state.analyzer.drawings_list))}")
            
            # Analyze current drawing
            current_drawing = st.session_state.analyzer.drawings_list[st.session_state.current_analysis_index]
            
            with st.spinner(f"Analyzing drawing {current_drawing['drawing_number']} from page {current_drawing['page']}..."):
                analysis_result = st.session_state.analyzer.analyze_drawing(current_drawing)
                
                if analysis_result:
                    # Store analysis result
                    st.session_state.analyzed_drawings.append(analysis_result)
                    
                    # Increment counter
                    st.session_state.current_analysis_index += 1
                    
                    # Auto-rerun to process next drawing
                    if remaining_drawings > 1:
                        st.rerun()
                    else:
                        st.success("Completed analysis of first 5 drawings!")
            
        elif len(st.session_state.analyzer.drawings_list) > 5:
            st.info("First 5 drawings have been analyzed. Reload the page to analyze a different set of drawings.")

    # Display all analyzed drawings
    if st.session_state.analyzed_drawings:
        st.subheader("Analyzed Drawings:")
        for analysis in st.session_state.analyzed_drawings:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.image(analysis['image'], 
                         use_column_width=True, 
                         caption=f"Drawing {analysis['drawing_number']} (Page {analysis['page']})")
            
            with col2:
                st.markdown("### Analysis Results")
                st.markdown(analysis['analysis'])
            
            st.markdown("---")
else:
    st.info("Please upload a PDF file containing engineering drawings to begin analysis.")