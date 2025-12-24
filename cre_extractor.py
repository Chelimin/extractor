import pandas as pd
import re
import json
from openai import OpenAI
import sys

# Initialize the OpenAI client. It will automatically use the pre-configured environment variables.
client = OpenAI()

# Define the structured output schema for the LLM
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "Date": {"type": "string", "description": "The date the transaction was announced or published (e.g., 'Dec 05, 2025')."},
        "Asset": {"type": "string", "description": "The name of the commercial property (e.g., 'The Clementi Mall')."},
        "Address": {"type": "string", "description": "The physical address of the property. Extract only if explicitly mentioned."},
        "Price": {"type": "string", "description": "The transaction price, including currency and magnitude (e.g., '$809 million')."},
        "Yield": {"type": "string", "description": "The net yield percentage (e.g., '4.1 per cent')."},
        "Type of Area (Site/NLA/GFA)": {"type": "string", "description": "The type of area mentioned, must be one of 'Site', 'NLA' (Net Lettable Area), or 'GFA' (Gross Floor Area)."},
        "Area (in sq ft)": {"type": "string", "description": "The area size in square feet (e.g., '195,772 sq ft')."},
        "Price/Unit Area ($/psf)": {"type": "string", "description": "The price per unit area (e.g., '$4,100 per square foot')."},
        "Buyer": {"type": "string", "description": "The name of the buyer entity."},
        "Seller": {"type": "string", "description": "The name of the seller entity."},
        "Comments": {"type": "string", "description": "Any other relevant details like lease tenure, deal context, or brokers involved."}
    },
    "required": ["Date", "Asset", "Price", "Buyer", "Seller"]
}

def clean_and_format_data(data):
    """Cleans and formats the extracted data to match the Excel column requirements."""
    
    # Helper function to convert text price to a number
    def convert_price_to_number(price_str):
        if not price_str:
            return None
        price_str = price_str.lower().replace('$', '').replace(',', '').strip()
        
        multiplier = 1
        if 'million' in price_str:
            multiplier = 1_000_000
            price_str = price_str.replace('million', '').strip()
        elif 'billion' in price_str:
            multiplier = 1_000_000_000
            price_str = price_str.replace('billion', '').strip()
        
        try:
            return float(price_str) * multiplier
        except ValueError:
            return price_str # Return original string if conversion fails

    # Helper function to clean yield
    def clean_yield(yield_str):
        if not yield_str:
            return None
        # Remove 'about', 'per cent', '%', and convert to float
        cleaned = re.sub(r'[^0-9\.]', '', yield_str.replace('about', '').replace('per cent', '').replace('%', '').strip())
        try:
            return float(cleaned)
        except ValueError:
            return yield_str

    # Helper function to clean area
    def clean_area(area_str):
        if not area_str:
            return None
        # Remove 'sq ft', ',', and convert to integer
        cleaned = re.sub(r'[^0-9]', '', area_str.lower().replace('sq ft', '').replace(',', '').strip())
        try:
            return int(cleaned)
        except ValueError:
            return area_str

    # Helper function to clean price/unit area
    def clean_price_psf(price_psf_str):
        if not price_psf_str:
            return None
        # Remove '$', 'per square foot', 'psf', ',', and convert to float
        cleaned = re.sub(r'[^0-9\.]', '', price_psf_str.lower().replace('$', '').replace('per square foot', '').replace('psf', '').strip())
        try:
            return float(cleaned)
        except ValueError:
            return price_psf_str

    # Apply cleaning and formatting
    data['Price'] = convert_price_to_number(data.get('Price'))
    data['Yield'] = clean_yield(data.get('Yield'))
    data['Area (in sq ft)'] = clean_area(data.get('Area (in sq ft)'))
    data['Price/Unit Area ($/psf)'] = clean_price_psf(data.get('Price/Unit Area ($/psf)'))
    
    # Rename keys to match the exact Excel headers for the DataFrame
    formatted_data = {
        "Date": data.get("Date"),
        "Asset": data.get("Asset"),
        "Address": data.get("Address"),
        "Price": data.get("Price"),
        "Yield ": data.get("Yield"),
        "Type of Area (Site/NLA/GFA)": data.get("Type of Area (Site/NLA/GFA)"),
        "Area (in sq ft)": data.get("Area (in sq ft)"),
        "Price/Unit Area ($/psf)": data.get("Price/Unit Area ($/psf)"),
        "Buyer": data.get("Buyer"),
        "Seller": data.get("Seller"),
        "Comments": data.get("Comments")
    }
    
    return formatted_data

def extract_and_update_db(article_text, db_path):
    """Extracts data from article text and updates the Excel database."""
    
    # 1. LLM Extraction
    try:
        print("Sending request to LLM for data extraction...")
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a commercial real estate analyst. Your task is to extract structured transaction data from a news article. Be precise and only use information explicitly stated in the text. If a field is not found, use an empty string. The output MUST be a JSON object that strictly conforms to the following JSON schema:\n" + json.dumps(EXTRACTION_SCHEMA, indent=2)},
                {"role": "user", "content": f"Extract the commercial real estate transaction details from the following news article text:\n\n---\n{article_text}\n---"}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON string from the response content
        extracted_data = json.loads(response.choices[0].message.content)
        print("Extraction successful.")
        
    except Exception as e:
        print(f"LLM Extraction Error: {e}", file=sys.stderr)
        return False

    # 2. Data Cleaning and Formatting
    try:
        formatted_data = clean_and_format_data(extracted_data)
        print("Data cleaning and formatting successful.")
    except Exception as e:
        print(f"Data Formatting Error: {e}", file=sys.stderr)
        return False

    # 3. Update Excel Database
    try:
        # Read existing data (or create a new DataFrame if the file is empty/new)
        try:
            df_existing = pd.read_excel(db_path)
        except FileNotFoundError:
            print(f"Database file not found at {db_path}. Creating new file.")
            df_existing = pd.DataFrame(columns=list(formatted_data.keys()))
        except Exception as e:
            print(f"Error reading existing Excel file: {e}. Attempting to create new DataFrame.", file=sys.stderr)
            df_existing = pd.DataFrame(columns=list(formatted_data.keys()))

        # Create a new DataFrame for the new entry
        df_new_entry = pd.DataFrame([formatted_data])

        # Concatenate and save
        df_updated = pd.concat([df_existing, df_new_entry], ignore_index=True)
        df_updated.to_excel(db_path, index=False)
        print(f"Successfully updated database at {db_path} with new entry.")
        return True

    except Exception as e:
        print(f"Excel Update Error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cre_extractor.py <article_text_file> <db_path>", file=sys.stderr)
        sys.exit(1)
    
    article_text_file = sys.argv[1]
    db_path = sys.argv[2]
    
    try:
        with open(article_text_file, 'r') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Article text file not found: {article_text_file}", file=sys.stderr)
        sys.exit(1)

    if extract_and_update_db(text, db_path):
        print("\nAgent run complete. Database updated.")
    else:
        print("\nAgent run failed.")
        sys.exit(1)
