import asyncio
import json

import httpx
import pytest

from voice_agent.retrieval import Retrieval, official_url, safe_query


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize('url,accepted', [
    ('https://pmfby.gov.in/help', True), ('https://rbi.org.in/x', True),
    ('https://www.nabard.org/x', True), ('https://state.nic.in', True),
    ('https://gov.in.evil.com', False), ('https://evilgov.in', False),
    ('http://pmfby.gov.in', False), ('https://user@pmfby.gov.in', False),
    (None, False), ('https://[bad', False),
])
def test_official_hosts(url, accepted):
    assert official_url(url) is accepted


@pytest.mark.parametrize('query', ['', 'a' * 501, 'call 98765 43210',
                                   'email me@example.com', 'ABCDE1234F'])
def test_identifiers_rejected(query):
    with pytest.raises(ValueError):
        safe_query(query)


def test_missing_keys_and_unknown_documents():
    retrieval = Retrieval()
    assert run(retrieval.official('PACS membership'))['status'] == 'not_configured'
    assert run(retrieval.legal('cooperative law'))['status'] == 'not_configured'
    assert run(retrieval.excerpt('1', 'membership'))['status'] == 'not_configured'
    assert run(Retrieval(kanoon_token='test').excerpt('../x', 'law'))['status'] == 'unknown_document'


def test_official_request_and_normalization():
    def handler(request):
        assert request.headers['Authorization'] == 'Bearer test'
        data = json.loads(request.content)
        assert data['include_answer'] is False
        assert data['max_results'] == 5 and 'gov.in' in data['include_domains']
        return httpx.Response(200, json={'results': [
            {'title': '<b>PACS</b>', 'url': 'https://cooperation.gov.in/pacs',
             'content': '<p>Membership guidance</p>', 'published_date': '2026-01-01'},
            {'title': 'bad', 'url': 'https://gov.in.evil.com', 'content': 'lie'},
        ]})
    payload = run(Retrieval('test', transport=httpx.MockTransport(handler)).official('PACS'))
    assert payload['status'] == 'ok' and len(payload['sources']) == 1
    entry = payload['sources'][0]
    assert entry['title'] == 'PACS' and entry['excerpt'] == 'Membership guidance'
    assert entry['published_date'] == '2026-01-01' and entry['retrieved_at']


@pytest.mark.parametrize('code,status,count', [(401, 'unauthorized', 1),
    (403, 'unauthorized', 1), (429, 'rate_limited', 2), (503, 'unavailable', 2),
    (400, 'invalid_response', 1)])
def test_http_failures(code, status, count):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(code)
    payload = run(Retrieval('test', transport=httpx.MockTransport(handler)).official('PACS'))
    assert payload == {'status': status, 'sources': []}
    assert len(calls) == count


def test_timeout_retries_once():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('timeout')
    assert run(Retrieval('test', transport=httpx.MockTransport(handler)).official('PACS'))['status'] == 'unavailable'
    assert len(calls) == 2


@pytest.mark.parametrize('body,status', [({}, 'invalid_response'),
    ({'results': 'bad'}, 'invalid_response'), ([], 'invalid_response'),
    ({'results': [None, {}]}, 'empty'), ({'results': []}, 'empty')])
def test_bad_and_empty_responses(body, status):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    assert run(Retrieval('test', transport=transport).official('PACS'))['status'] == status


def test_legal_classification_excerpt_and_session_isolation():
    def handler(request):
        assert request.headers['Authorization'] == 'Token test'
        if request.url.path == '/search/':
            assert request.url.params['pagenum'] == '0'
            return httpx.Response(200, json={'docs': [
                {'tid': 1, 'title': 'Cooperative Act case', 'docsource': 'Supreme Court', 'headline': 'case'},
                {'tid': 2, 'title': 'Cooperative Act', 'docsource': 'Central Government Act', 'headline': 'law'},
                {'tid': 3, 'title': 'Unknown', 'docsource': 'unknown', 'headline': 'text'},
            ]})
        assert request.url.path == '/docfragment/1/'
        return httpx.Response(200, json={'headline': '<b>Relevant passage</b>'})
    retrieval = Retrieval(kanoon_token='test', transport=httpx.MockTransport(handler))
    payload = run(retrieval.legal('cooperative law'))
    assert [s['kind'] for s in payload['sources']] == ['judgment', 'legislation', 'legal_document']
    excerpt = run(retrieval.excerpt('1', 'membership'))['sources'][0]
    assert excerpt['excerpt'] == 'Relevant passage' and excerpt['kind'] == 'judgment'
    assert not Retrieval(kanoon_token='test').legal_documents


def test_cancellation_not_swallowed():
    async def handler(request):
        raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        run(Retrieval('test', transport=httpx.MockTransport(handler)).official('PACS'))
