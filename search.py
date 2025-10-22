from libgen_api_enhanced import LibgenSearch, SearchTopic, SearchType

lib_search = LibgenSearch()
filter_params = {"extension": "epub"}
search_types = [SearchType.AUTHOR]
search_topics = [SearchTopic.LIBGEN]

# request = SearchRequest()

results = lib_search.search_title_filtered(
    query="Othello",
    filters=filter_params,
    exact_match=False,
    search_in=search_topics
)

if results:
    for book in results:
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
