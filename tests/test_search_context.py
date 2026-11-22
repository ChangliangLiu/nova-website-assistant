import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from search_context import select_search_context


def test_initial_context_limits_passages_and_matching_sources():
    result = {'passages': [{'citationId': str(i)} for i in range(5)],
              'sources': [{'citationId': str(i)} for i in range(5)]}
    context, sources = select_search_context(result)
    assert [p['citationId'] for p in context['passages']] == ['0', '1', '2']
    assert context['additional_available'] is True
    assert [s['citationId'] for s in sources] == ['0', '1', '2']
    context, sources = select_search_context(result, True)
    assert context['passages'] == result['passages']
    assert sources == result['sources']
    assert context['additional_available'] is False


def test_empty_search_has_no_expansion():
    context, sources = select_search_context({'passages': [], 'sources': []})
    assert context == {'passages': [], 'additional_available': False}
    assert sources == []
