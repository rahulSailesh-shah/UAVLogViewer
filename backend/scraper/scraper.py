import requests
from bs4 import BeautifulSoup
import json

def scrape_ardupilot_logs(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')

    main_content = soup.find('div', attrs={'role': 'main'})
    if not main_content:
        print("Could not find the main content container. The page structure might have changed.")
        return []

    log_sections = main_content.find_all('section', id=True)

    scraped_data = []

    for section in log_sections:
        header = section.find('h2')
        if not header:
            continue
        message_name = header.get_text(strip=True).replace('¶', '')

        description_tag = header.find_next_sibling('p')
        description = description_tag.get_text(strip=True) if description_tag else "No description available."

        table = section.find('table')
        fields = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 3:
                    field_name = cells[0].get_text(strip=True)
                    units = cells[1].get_text(strip=True)
                    field_description = cells[2].get_text(strip=True)
                    fields.append({
                        "FieldName": field_name,
                        "Units": units,
                        "Description": field_description
                    })

        message_data = {
            "MessageName": message_name,
            "Description": description,
            "Fields": fields
        }
        scraped_data.append(message_data)

    return scraped_data

if __name__ == "__main__":
    target_url = "https://ardupilot.org/plane/docs/logmessages.html"

    print(f"Scraping log messages from: {target_url}\n")

    log_messages = scrape_ardupilot_logs(target_url)

    if log_messages:
        print(f"Successfully scraped {len(log_messages)} log messages.")
        formatted_json = json.dumps(log_messages, indent=4)
        output_filename = "schema.json"
        with open(output_filename, 'w') as f:
            f.write(formatted_json)

        print(f"\nScraped data has been saved to '{output_filename}'")
        print("\n--- First 3 Log Messages ---")
        print(json.dumps(log_messages[:3], indent=4))
        print("----------------------------")

    else:
        print("Scraping failed. No data was retrieved.")
