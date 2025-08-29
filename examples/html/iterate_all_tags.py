from bs4 import BeautifulSoup
import sys

def iterate_text_tags(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # List of tags that usually contain text
    text_tags = [
        "p", "span", "div", "td", "th", "li", "a", "h1", "h2", "h3", "h4", "h5", "h6",
        "button", "label", "strong", "em", "b", "i", "u", "small", "big", "caption",
        "title", "option", "textarea"
    ]

    for tag_name in text_tags:
        for tag in soup.find_all(tag_name):
            # Only print if tag has non-empty text (ignoring whitespace)
            text = tag.get_text(strip=True)
            if text:
                print(f"<{tag_name}>: {text}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python iterate_all_tags.py <html_file>")
        sys.exit(1)
    html_file = sys.argv[1]
    iterate_text_tags(html_file)
