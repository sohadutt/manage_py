from libgen_api_enhanced import LibgenSearch, SearchTopic
import os
import json

lib_search = LibgenSearch()
filter_params = {"extension": "epub"}
search_topics = [SearchTopic.LIBGEN]

# Perform search
results = lib_search.search_title_filtered(
    query="Othello",
    filters=filter_params,
    exact_match=False,
    search_in=search_topics
)

if results:
    for book in results:
        # Resolve direct download link for each book
        book.resolve_direct_download_link()
        print(book.title)
        print(book.author)
        print(book.language)
        print(book.year)
        print(book.extension)
        print(book.pages)
        print(book.resolved_download_link)
        print("-" * 50)
else:
    print("No results found.")


# Convert results to JSON
def JSONify_search_results(results):
    results_list = []
    for book in results:
        book_dict = {
            "title": book.title,
            "author": book.author,
            "language": book.language,
            "year": book.year,
            "extension": book.extension,
            "pages": book.pages,
            "resolved_download_link": book.resolved_download_link,
        }
        results_list.append(book_dict)
    return json.dumps(results_list, indent=4, ensure_ascii=False)


# Save to file
if results:
    result_json = JSONify_search_results(results)
    output_path = os.path.join(os.getcwd(), "search_results.json")
    with open(output_path, "w", encoding="utf-8") as json_file:
        json_file.write(result_json)
    print(f"\n✅ Search results saved to {output_path}")
