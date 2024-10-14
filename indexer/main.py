import os
import argparse
import re
from collections import defaultdict
import html
import concurrent.futures
from functools import partial
import webbrowser

def search_file(search_words, full_search_key, file_path, match_case):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    if not match_case:
        content = content.lower()
        search_words = [word.lower() for word in search_words]
        full_search_key = full_search_key.lower()
    
    # Score for individual words
    word_score = sum(1 for word in search_words if word in content)
    
    # Additional score for full phrase match
    full_phrase_score = 1 if re.search(r'\b' + re.escape(full_search_key) + r'\b', content) else 0
    
    # Additional score if any search word is in the folder name (always case-insensitive)
    folder_name = os.path.basename(os.path.dirname(file_path)).lower()
    folder_score = 1 if any(word.lower() in folder_name for word in search_words) else 0
    
    total_score = word_score + full_phrase_score + folder_score
    return file_path, total_score

def search_files(search_key, directory, num_workers, match_case):
    search_words = re.findall(r'\w+', search_key)
    
    all_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.txt'):
                all_files.append(os.path.join(root, file))
    
    file_count = len(all_files)
    
    scores = defaultdict(int)
    
    print(f"Searching {file_count} files...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        search_func = partial(search_file, search_words, search_key, match_case=match_case)
        results = list(executor.map(search_func, all_files))
    
    for file_path, score in results:
        if score >= 1:
            scores[file_path] = score
    
    print(f"\nCompleted search. Total files searched: {file_count}")
    
    sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_files

def create_html_report(search_key, results, project_directory):
    filename = f"{search_key}.html"
    filepath = os.path.join(project_directory, filename)
    
    html_content = f"""
    <html>
    <head>
        <title>Search Results for "{search_key}"</title>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .result {{ margin-bottom: 20px; }}
            img {{ max-width: 100%; height: auto; }}
        </style>
    </head>
    <body>
        <h1>Search Results for "{search_key}"</h1>
    """
    
    for file_path, score in results:
        html_content += f"""
        <div class="result">
            <h2>{html.escape(file_path)} (Score: {score})</h2>
            <p>Text file: <a href="file://{html.escape(file_path)}">{html.escape(file_path)}</a></p>
        """
        
        # Find corresponding PNG file
        png_path = file_path.rsplit('.', 1)[0] + '.png'
        if os.path.exists(png_path):
            html_content += f'<img src="file://{html.escape(png_path)}" alt="Related image">'
        else:
            html_content += '<p>No corresponding PNG file found.</p>'
        
        html_content += '</div>'
    
    html_content += """
    </body>
    </html>
    """
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML report generated: {filepath}")
    return filepath

def main():
    parser = argparse.ArgumentParser(description="Search OCR results in txt files.")
    parser.add_argument("--searchkey", type=str, required=True, help="Search key to look for in txt files")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads (default: 4)")
    parser.add_argument("--matchcase", action="store_true", help="Enable case-sensitive matching")
    args = parser.parse_args()

    directory = os.path.expanduser("~/Downloads/tm_daily_ingest")
    results = search_files(args.searchkey, directory, args.workers, args.matchcase)

    print("Search results (sorted by relevance, score >= 1):")
    for file_path, score in results:
        print(f"{file_path} (Score: {score})")

    project_directory = os.path.dirname(os.path.abspath(__file__))
    html_filepath = create_html_report(args.searchkey, results, project_directory)

    # Open the HTML file in the default web browser
    webbrowser.open('file://' + os.path.realpath(html_filepath))

if __name__ == "__main__":
    main()
