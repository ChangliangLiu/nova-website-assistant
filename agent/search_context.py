"""Return a small first set of passages, with an explicit expansion path."""

INITIAL_PASSAGES = 3


def select_search_context(result, include_more_results=False):
    passages = result['passages']
    selected = passages if include_more_results else passages[:INITIAL_PASSAGES]
    selected_ids = {passage['citationId'] for passage in selected}
    sources = [source for source in result['sources'] if source.get('citationId') in selected_ids]
    return {'passages': selected, 'additional_available': len(selected) < len(passages)}, sources
