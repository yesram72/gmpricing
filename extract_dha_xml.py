import pandas as pd
import xml.etree.ElementTree as ET

def extract_dha_tables(xml_path):
    """
    Extracts DHA tables from the XML template.

    Returns a dict of pandas DataFrames keyed by:
    - 'population_census_beginning'
    - 'population_census_end'
    - 'claims_by_month'
    - 'claims_by_member'
    - 'report_date' (string)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 1. Get report date (from <Created> tag)
    report_date = None
    props = root.find(".//{urn:schemas-microsoft-com:office:office}DocumentProperties")
    if props is not None:
        created = props.find("{urn:schemas-microsoft-com:office:office}Created")
        if created is not None:
            report_date = created.text.split("T")[0]

    # Helper function to extract table rows given a header row name
    def extract_table(header_text, num_rows=None):
        data = []
        header_row = None
        for crn in root.findall(".//{urn:schemas-microsoft-com:office:excel}Crn"):
            texts = [t.text for t in crn.findall("{urn:schemas-microsoft-com:office:excel}Text")]
            if texts and header_text in texts[0]:
                header_row = crn
                break
        if header_row is None:
            return None
        headers = [t.text for t in header_row.findall("{urn:schemas-microsoft-com:office:excel}Text")]
        # Find subsequent rows
        crns = root.findall(".//{urn:schemas-microsoft-com:office:excel}Crn")
        start_idx = crns.index(header_row) + 1
        if num_rows is None:
            # Grab until next header or end
            table_rows = []
            for crn in crns[start_idx:]:
                texts = [t.text for t in crn.findall("{urn:schemas-microsoft-com:office:excel}Text")]
                if not texts or "Total claims Processed" in texts[0] or "Claims data by member type" in texts[0]:
                    break
                table_rows.append(texts)
            data = table_rows
        else:
            for crn in crns[start_idx:start_idx+num_rows]:
                data.append([t.text for t in crn.findall("{urn:schemas-microsoft-com:office:excel}Text")])
        # Sometimes the first column is a row label
        df = pd.DataFrame(data, columns=headers[1:])
        df.insert(0, headers[0], [row[0] for row in data])
        return df

    # 2. Population census (beginning)
    population_census_beginning = extract_table("Population census (at beginning of reporting period)", num_rows=4)

    # 3. Population census (end)
    population_census_end = extract_table("Population census (at end of reporting period)", num_rows=4)

    # 4. Claims data by member type
    claims_by_member = extract_table("Claims data by member type (value AED)", num_rows=4)

    # 5. Claims processed per service month (Section 17: dynamic rows)
    # Find header
    claims_header_crn = None
    for crn in root.findall(".//{urn:schemas-microsoft-com:office:excel}Crn"):
        texts = [t.text for t in crn.findall("{urn:schemas-microsoft-com:office:excel}Text")]
        if texts and "Total claims Processed per service month" in texts[0]:
            claims_header_crn = crn
            break
    if claims_header_crn is not None:
        headers = ["Year", "Month ending date", "Value"]
        crns = root.findall(".//{urn:schemas-microsoft-com:office:excel}Crn")
        start_idx = crns.index(claims_header_crn)
        data = []
        # Find rows until "Claims data by member type" or end
        for crn in crns[start_idx+1:]:
            texts = [t.text for t in crn.findall("{urn:schemas-microsoft-com:office:excel}Text")]
            if not texts or "Claims data by member type" in texts[0]:
                break
            # Only rows with proper format (year, month, value)
            if len(texts) == 3 and texts[0].isdigit():
                data.append(texts)
            elif len(texts) == 2 and texts[0].isalpha():
                # Possibly the TOTAL row
                data.append(["", texts[0], texts[1]])
        claims_by_month = pd.DataFrame(data, columns=headers)
    else:
        claims_by_month = None

    return {
        "population_census_beginning": population_census_beginning,
        "population_census_end": population_census_end,
        "claims_by_month": claims_by_month,
        "claims_by_member": claims_by_member,
        "report_date": report_date
    }

# Example usage:
# tables = extract_dha_tables("Extraction template for DHA.xml")
# for k, df in tables.items():
#     if k != "report_date": print(f"{k}:
", df)