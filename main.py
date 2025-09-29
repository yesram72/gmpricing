import streamlit as st
import pandas as pd
import io
from typing import List, Dict, Optional, Tuple
import re

# Try importing PDF extraction libraries
PDF_LIBS_AVAILABLE = {
    'pdfplumber': False,
    'camelot': False, 
    'tabula': False,
    'pytesseract': False
}

try:
    import pdfplumber
    PDF_LIBS_AVAILABLE['pdfplumber'] = True
except ImportError:
    pass

try:
    import camelot
    PDF_LIBS_AVAILABLE['camelot'] = True
except ImportError:
    pass

try:
    import tabula
    PDF_LIBS_AVAILABLE['tabula'] = True
except ImportError:
    pass

try:
    import pytesseract
    PDF_LIBS_AVAILABLE['pytesseract'] = True
except ImportError:
    pass

st.set_page_config(
    page_title="DHA Report Table Extractor",
    page_icon="📊",
    layout="wide",
)

class DHAReportExtractor:
    """Extracts tables from DHA reports using multiple engines with fallbacks."""
    
    def __init__(self):
        self.engines = ['pdfplumber', 'camelot-lattice', 'camelot-stream', 'tabula-lattice', 'tabula-stream']
        
    def extract_with_pdfplumber(self, file_bytes: bytes) -> List[pd.DataFrame]:
        """Extract tables using pdfplumber."""
        if not PDF_LIBS_AVAILABLE['pdfplumber']:
            return []
            
        tables = []
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    for table in page_tables:
                        if table and len(table) > 0:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            tables.append(df)
        except Exception as e:
            st.warning(f"pdfplumber extraction failed: {str(e)}")
        return tables
    
    def extract_with_camelot(self, file_bytes: bytes, flavor: str = 'lattice') -> List[pd.DataFrame]:
        """Extract tables using camelot."""
        if not PDF_LIBS_AVAILABLE['camelot']:
            return []
            
        tables = []
        try:
            # Save bytes to temporary file as camelot needs file path
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name
            
            camelot_tables = camelot.read_pdf(tmp_file_path, flavor=flavor)
            for table in camelot_tables:
                tables.append(table.df)
                
            # Clean up temp file
            import os
            os.unlink(tmp_file_path)
            
        except Exception as e:
            st.warning(f"camelot-{flavor} extraction failed: {str(e)}")
        return tables
    
    def extract_with_tabula(self, file_bytes: bytes, lattice: bool = True) -> List[pd.DataFrame]:
        """Extract tables using tabula."""
        if not PDF_LIBS_AVAILABLE['tabula']:
            return []
            
        tables = []
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name
            
            tabula_tables = tabula.read_pdf(tmp_file_path, pages='all', lattice=lattice, multiple_tables=True)
            for table in tabula_tables:
                if not table.empty:
                    tables.append(table)
                    
            # Clean up temp file  
            import os
            os.unlink(tmp_file_path)
            
        except Exception as e:
            st.warning(f"tabula-{'lattice' if lattice else 'stream'} extraction failed: {str(e)}")
        return tables

    def extract_all_tables(self, file_bytes: bytes) -> Dict[str, List[pd.DataFrame]]:
        """Extract tables using all available engines."""
        all_tables = {}
        
        # Try pdfplumber
        if PDF_LIBS_AVAILABLE['pdfplumber']:
            all_tables['pdfplumber'] = self.extract_with_pdfplumber(file_bytes)
            
        # Try camelot
        if PDF_LIBS_AVAILABLE['camelot']:
            all_tables['camelot-lattice'] = self.extract_with_camelot(file_bytes, 'lattice')
            all_tables['camelot-stream'] = self.extract_with_camelot(file_bytes, 'stream')
            
        # Try tabula
        if PDF_LIBS_AVAILABLE['tabula']:
            all_tables['tabula-lattice'] = self.extract_with_tabula(file_bytes, True)
            all_tables['tabula-stream'] = self.extract_with_tabula(file_bytes, False)
            
        return all_tables

class DHATableProcessor:
    """Processes extracted tables to match DHA report structure."""
    
    @staticmethod
    def process_population_census(tables: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Process Section 6 & 7 (Population census) with fixed age-band columns."""
        # Expected structure: rows 6a-6c, 7a-7c with columns: 0-15, 16-25, 26-35, 36-50, 51-65, Over 65
        age_bands = ['0-15', '16-25', '26-35', '36-50', '51-65', 'Over 65']
        row_labels = ['6a Male', '6b Single females', '6c Married females', 
                     '7a Male', '7b Single females', '7c Married females']
        
        for table in tables:
            # Look for table that might contain population data
            if len(table.columns) >= 6 and len(table) >= 6:
                # Try to match the structure
                processed_df = pd.DataFrame(columns=['Category'] + age_bands + ['Total'])
                
                # Add rows
                for i, label in enumerate(row_labels[:min(len(row_labels), len(table))]):
                    if i < len(table):
                        row_data = [label]
                        # Extract numeric values from the row
                        for col_idx in range(1, min(7, len(table.columns))):
                            try:
                                val = str(table.iloc[i, col_idx]) if i < len(table) else '0'
                                # Clean and convert to numeric
                                val = re.sub(r'[^\d.]', '', val) if val else '0'
                                row_data.append(val)
                            except:
                                row_data.append('0')
                        
                        # Calculate total if not provided
                        if len(row_data) == len(age_bands) + 1:  # No total column
                            try:
                                total = sum(float(x) if x.replace('.', '').isdigit() else 0 for x in row_data[1:])
                                row_data.append(str(int(total)))
                            except:
                                row_data.append('0')
                        
                        processed_df.loc[len(processed_df)] = row_data[:len(processed_df.columns)]
                
                return processed_df
                
        return None
    
    @staticmethod
    def process_claims_by_member_type(tables: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Process Section 8 (Claims by member type) with fixed service columns."""
        # Expected structure: rows 8a-8d with columns: IP, OP, Pharmacy, Dental, Optical, Totals
        service_types = ['IP', 'OP', 'Pharmacy', 'Dental', 'Optical']
        row_labels = ['8a Employee', '8b Spouse', '8c Dependents', '8d Totals']
        
        for table in tables:
            if len(table.columns) >= 5 and len(table) >= 4:
                processed_df = pd.DataFrame(columns=['Member Type'] + service_types + ['Totals'])
                
                for i, label in enumerate(row_labels[:min(len(row_labels), len(table))]):
                    if i < len(table):
                        row_data = [label]
                        # Extract values
                        for col_idx in range(1, min(6, len(table.columns))):
                            try:
                                val = str(table.iloc[i, col_idx]) if i < len(table) else '0'
                                val = re.sub(r'[^\d.]', '', val) if val else '0'
                                row_data.append(val)
                            except:
                                row_data.append('0')
                        
                        # Calculate total if not provided
                        if len(row_data) == len(service_types) + 1:
                            try:
                                total = sum(float(x) if x.replace('.', '').isdigit() else 0 for x in row_data[1:])
                                row_data.append(str(int(total)))
                            except:
                                row_data.append('0')
                        
                        processed_df.loc[len(processed_df)] = row_data[:len(processed_df.columns)]
                
                return processed_df
                
        return None
    
    @staticmethod
    def process_claims_per_service_month(tables: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Process Section 17 (Total claims per service month) with Month/Year/Value columns."""
        # Expected structure: codes 17a-17m with columns: Month ending date, Year, Value
        
        for table in tables:
            if len(table.columns) >= 3 and len(table) >= 12:  # At least 12 months
                processed_df = pd.DataFrame(columns=['Month ending date', 'Year', 'Value'])
                
                total_value = 0
                for i in range(min(13, len(table))):  # 12 months + potential total
                    if i < len(table):
                        row_data = []
                        # Extract month, year, value
                        for col_idx in range(min(3, len(table.columns))):
                            try:
                                val = str(table.iloc[i, col_idx]) if i < len(table) else ''
                                row_data.append(val)
                            except:
                                row_data.append('')
                        
                        if len(row_data) >= 3:
                            try:
                                # Try to extract numeric value from the last column
                                value_str = re.sub(r'[^\d.]', '', row_data[2]) if row_data[2] else '0'
                                value = float(value_str) if value_str else 0
                                total_value += value
                            except:
                                pass
                            
                        processed_df.loc[len(processed_df)] = row_data[:3]
                
                # Add TOTAL row
                processed_df.loc[len(processed_df)] = ['TOTAL', '', str(int(total_value))]
                
                return processed_df
                
        return None

def main():
    st.title("🏥 DHA Report Table Extractor")
    st.write("Extract DHA report tables using fixed, code-anchored layouts with consolidated output view.")
    
    # Display available PDF libraries
    st.sidebar.header("PDF Extraction Engines")
    available_engines = [name for name, available in PDF_LIBS_AVAILABLE.items() if available]
    if available_engines:
        st.sidebar.success(f"Available: {', '.join(available_engines)}")
    else:
        st.sidebar.warning("No PDF extraction libraries installed. Upload will work with fallback text extraction.")
    
    # File upload
    uploaded_file = st.file_uploader("Upload DHA PDF report", type=['pdf'])
    
    if uploaded_file is not None:
        st.success(f"Uploaded: {uploaded_file.name}")
        
        # Read file bytes
        file_bytes = uploaded_file.read()
        
        # Initialize processors
        extractor = DHAReportExtractor()
        processor = DHATableProcessor()
        
        # Extract tables using all available engines
        with st.spinner("Extracting tables from PDF..."):
            all_extracted_tables = extractor.extract_all_tables(file_bytes)
        
        # Show extraction results
        st.header("📊 Extracted Sections")
        
        # Process each section
        sections_data = {}
        
        # Try to find and process each section from the extracted tables
        for engine_name, tables in all_extracted_tables.items():
            if tables:  # If this engine found tables
                
                # Process Population Census (Sections 6 & 7)
                if 'population_census' not in sections_data:
                    pop_census = processor.process_population_census(tables)
                    if pop_census is not None and not pop_census.empty:
                        sections_data['population_census'] = pop_census
                        
                # Process Claims by Member Type (Section 8)  
                if 'claims_by_member' not in sections_data:
                    claims_member = processor.process_claims_by_member_type(tables)
                    if claims_member is not None and not claims_member.empty:
                        sections_data['claims_by_member'] = claims_member
                        
                # Process Claims per Service Month (Section 17)
                if 'claims_per_month' not in sections_data:
                    claims_month = processor.process_claims_per_service_month(tables)
                    if claims_month is not None and not claims_month.empty:
                        sections_data['claims_per_month'] = claims_month
        
        # Display processed sections
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Section 6 & 7: Population Census")
            if 'population_census' in sections_data:
                st.dataframe(sections_data['population_census'])
                csv_data = sections_data['population_census'].to_csv(index=False)
                st.download_button(
                    label="📥 Download Population Census CSV",
                    data=csv_data,
                    file_name="population_census.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Population census data not found or could not be processed")
        
        with col2:
            st.subheader("💰 Section 8: Claims by Member Type")
            if 'claims_by_member' in sections_data:
                st.dataframe(sections_data['claims_by_member'])
                csv_data = sections_data['claims_by_member'].to_csv(index=False)
                st.download_button(
                    label="📥 Download Claims by Member CSV",
                    data=csv_data,
                    file_name="claims_by_member_type.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Claims by member type data not found or could not be processed")
        
        st.subheader("📅 Section 17: Total Claims per Service Month")
        if 'claims_per_month' in sections_data:
            st.dataframe(sections_data['claims_per_month'])
            csv_data = sections_data['claims_per_month'].to_csv(index=False)
            st.download_button(
                label="📥 Download Claims per Month CSV",
                data=csv_data,
                file_name="claims_per_service_month.csv",
                mime="text/csv"
            )
        else:
            st.warning("Claims per service month data not found or could not be processed")
        
        # Debug section - show all extracted tables
        with st.expander("🔍 Show ALL extracted tables (diagnostics)"):
            for engine_name, tables in all_extracted_tables.items():
                if tables:
                    st.write(f"**{engine_name.upper()} Engine Results:**")
                    for i, table in enumerate(tables):
                        st.write(f"Table {i+1}:")
                        st.dataframe(table)
                else:
                    st.write(f"**{engine_name.upper()}:** No tables extracted")
    else:
        st.info("👆 Please upload a DHA PDF report to begin extraction")
        
        # Show example of expected output structure
        st.header("📋 Expected Output Structure")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Population Census Example")
            example_pop = pd.DataFrame({
                'Category': ['6a Male', '6b Single females', '6c Married females'],
                '0-15': ['120', '110', '105'],
                '16-25': ['80', '90', '95'],
                '26-35': ['70', '85', '100'],
                '36-50': ['60', '75', '90'],
                '51-65': ['40', '50', '60'],
                'Over 65': ['20', '25', '30'],
                'Total': ['390', '435', '480']
            })
            st.dataframe(example_pop)
            
        with col2:
            st.subheader("Claims by Member Type Example")
            example_claims = pd.DataFrame({
                'Member Type': ['8a Employee', '8b Spouse', '8c Dependents', '8d Totals'],
                'IP': ['50000', '30000', '20000', '100000'],
                'OP': ['25000', '15000', '10000', '50000'],
                'Pharmacy': ['15000', '10000', '5000', '30000'],
                'Dental': ['8000', '5000', '3000', '16000'],
                'Optical': ['2000', '1500', '1000', '4500'],
                'Totals': ['100000', '61500', '39000', '200500']
            })
            st.dataframe(example_claims)

if __name__ == "__main__":
    main()