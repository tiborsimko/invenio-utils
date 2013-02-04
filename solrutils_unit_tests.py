# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2008, 2009, 2010, 2011, 2013 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Unit tests for the solrutils library."""

import unittest
from invenio.config import CFG_SOLR_URL, CFG_SITE_NAME
from invenio import intbitset
from invenio.testutils import make_test_suite, run_test_suite
from invenio.solrutils_bibindex_indexer import replace_invalid_solr_characters
from invenio.solrutils_bibindex_searcher import solr_get_bitset
from invenio.solrutils_bibrank_searcher import get_collection_filter, solr_get_ranked, solr_get_similar_ranked
from invenio.search_engine import get_collection_reclist
from invenio.bibrank_bridge_utils import get_external_word_similarity_ranker


class TestReplaceInvalidCharacters(unittest.TestCase):
    """Test for removal of invalid Solr characters and control characters."""

    def test_no_replacement(self):
        """solrutils - no characters to replace"""
        utext_in = unicode('foo\nbar\tfab\n\r', 'utf-8')
        utext_out = unicode('foo\nbar\tfab\n\r', 'utf-8')
        self.assertEqual(utext_out, replace_invalid_solr_characters(utext_in))

    def test_replace_control_characters(self):
        """solrutils - replacement of control characters"""
        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u0000\nde'))
        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u0003\nde'))
        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u0008\nde'))

        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u000B\nde'))
        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u000C\nde'))

        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u000E\nde'))
        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u0012\nde'))
        self.assertEqual(u'abc \nde', replace_invalid_solr_characters(u'abc\u001F\nde'))

    def test_replace_invalid_chars(self):
        """solrutils - replacement of invalid characters"""
        self.assertEqual(u'abc\nde', replace_invalid_solr_characters(u'abc\uD800\nde'))
        self.assertEqual(u'abc\nde', replace_invalid_solr_characters(u'abc\uDF12\nde'))
        self.assertEqual(u'abc\nde', replace_invalid_solr_characters(u'abc\uDFFF\nde'))

        self.assertEqual(u'abc\nde', replace_invalid_solr_characters(u'abc\uFFFE\nde'))
        self.assertEqual(u'abc\nde', replace_invalid_solr_characters(u'abc\uFFFF\nde'))


class TestSolrRankingHelpers(unittest.TestCase):
    """Test for Solr ranking helper functions."""
    def test_get_collection_filter(self):
        """solrutils - creation of collection filter"""
        self.assertEqual('', get_collection_filter(intbitset.intbitset([]), 0))
        self.assertEqual('', get_collection_filter(intbitset.intbitset([]), 1))
        self.assertEqual('', get_collection_filter(intbitset.intbitset([1, 2, 3, 4, 5]), 0))
        self.assertEqual('id:(5)', get_collection_filter(intbitset.intbitset([1, 2, 3, 4, 5]), 1))
        self.assertEqual('id:(4 5)', get_collection_filter(intbitset.intbitset([1, 2, 3, 4, 5]), 2))
        self.assertEqual('id:(1 2 3 4 5)', get_collection_filter(intbitset.intbitset([1, 2, 3, 4, 5]), 5))
        self.assertEqual('id:(1 2 3 4 5)', get_collection_filter(intbitset.intbitset([1, 2, 3, 4, 5]), 6))


ROWS = 100


HITSETS = {
    'Willnotfind': intbitset.intbitset([]),
    'higgs': intbitset.intbitset([47, 48, 51, 52, 55, 56, 58, 68, 79, 85, 89, 96]),
    'of': intbitset.intbitset([8, 10, 11, 12, 15, 43, 44, 45, 46, 47, 48, 49, 50, 51,
                               52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 64, 68, 74,
                               77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90,
                               91, 92, 93, 94, 95, 96, 97]),
    '"higgs boson"': intbitset.intbitset([55, 56]),
}

def get_topN(n, data):
    res = dict()
    for key, value in data.iteritems():
        res[key] = value[-n:]
    return res


class TestSolrSearch(unittest.TestCase):
    """Test for Solr search. Requires:
    make install-solrutils
    CFG_SOLR_URL set
    fulltext index in idxINDEX containing 'SOLR' in indexer column
    AND EITHER
      Solr index built: ./bibindex -w fulltext for all records
     OR
      WRD method referring to Solr: <invenio installation>/etc/bibrank$ cp template_word_similarity_solr.cfg wrd.cfg
      and ./bibrank -w wrd for all records
    """

    def _get_result(self, query, index='fulltext'):
        return solr_get_bitset(index, query)

    def test_get_bitset(self):
        """solrutils - search results"""
        self.assertEqual(HITSETS['Willnotfind'], self._get_result('Willnotfind'))
        self.assertEqual(HITSETS['higgs'], self._get_result('higgs'))
        self.assertEqual(HITSETS['of'], self._get_result('of'))
        self.assertEqual(HITSETS['"higgs boson"'], self._get_result('"higgs boson"'))


class TestSolrRanking(unittest.TestCase):
    """Test for Solr ranking. Requires:
    make install-solrutils
    CFG_SOLR_URL set
    fulltext index in idxINDEX containing 'SOLR' in indexer column
    AND EITHER
      Solr index built: ./bibindex -w fulltext for all records
     OR
      WRD method referring to Solr: <invenio installation>/etc/bibrank$ cp template_word_similarity_solr.cfg wrd.cfg
      and ./bibrank -w wrd for all records
    """

    def _get_ranked_result_sequence(self, query, index='fulltext', rows=ROWS, hitset=None):
        if hitset is None:
            hitset=HITSETS[query]
        ranked_result = solr_get_ranked('%s:%s' % (index, query), hitset, self._get_ranking_params(), rows)
        return tuple([pair[0] for pair in ranked_result[0]])

    def _get_ranked_topN(self, n):
        return get_topN(n, self._RANKED)

    _RANKED = {
        'Willnotfind': tuple(),
        'higgs': (79, 51, 55, 47, 56, 96, 58, 68, 52, 48, 89, 85),
        'of': (50, 61, 60, 54, 56, 53, 10, 68, 44, 57, 83, 95, 92, 91, 74, 45, 48, 62, 82,
               49, 51, 89, 90, 96, 43, 8, 64, 97, 15, 85, 78, 46, 55, 79, 84, 88, 81, 52,
               58, 86, 11, 80, 93, 77, 12, 59, 87, 47, 94),
        '"higgs boson"': (55, 56),
    }

    def _get_ranking_params(self, cutoff_amount=10000, cutoff_time=2000):
        """
        Default values from template_word_similarity_solr.cfg
        """
        return {
            'cutoff_amount': cutoff_amount,
            'cutoff_time_ms': cutoff_time
        }

    def test_get_ranked(self):
        """solrutils - ranking results"""
        all_ranked = 0
        ranked_top = self._get_ranked_topN(all_ranked)
        self.assertEqual(ranked_top['Willnotfind'], self._get_ranked_result_sequence(query='Willnotfind'))
        self.assertEqual(ranked_top['higgs'], self._get_ranked_result_sequence(query='higgs'))
        self.assertEqual(ranked_top['of'], self._get_ranked_result_sequence(query='of'))
        self.assertEqual(ranked_top['"higgs boson"'], self._get_ranked_result_sequence(query='"higgs boson"'))

    def test_get_ranked_top(self):
        """solrutils - ranking top results"""
        top_n = 0
        self.assertEqual(tuple(), self._get_ranked_result_sequence(query='Willnotfind', rows=top_n))
        self.assertEqual(tuple(), self._get_ranked_result_sequence(query='higgs', rows=top_n))
        self.assertEqual(tuple(), self._get_ranked_result_sequence(query='of', rows=top_n))
        self.assertEqual(tuple(), self._get_ranked_result_sequence(query='"higgs boson"', rows=top_n))

        top_n = 2
        ranked_top = self._get_ranked_topN(top_n)
        self.assertEqual(ranked_top['Willnotfind'], self._get_ranked_result_sequence(query='Willnotfind', rows=top_n))
        self.assertEqual(ranked_top['higgs'], self._get_ranked_result_sequence(query='higgs', rows=top_n))
        self.assertEqual(ranked_top['of'], self._get_ranked_result_sequence(query='of', rows=top_n))
        self.assertEqual(ranked_top['"higgs boson"'], self._get_ranked_result_sequence(query='"higgs boson"', rows=top_n))

        top_n = 10
        ranked_top = self._get_ranked_topN(top_n)
        self.assertEqual(ranked_top['Willnotfind'], self._get_ranked_result_sequence(query='Willnotfind', rows=top_n))
        self.assertEqual(ranked_top['higgs'], self._get_ranked_result_sequence(query='higgs', rows=top_n))
        self.assertEqual(ranked_top['of'], self._get_ranked_result_sequence(query='of', rows=top_n))
        self.assertEqual(ranked_top['"higgs boson"'], self._get_ranked_result_sequence(query='"higgs boson"', rows=top_n))

    def test_get_ranked_smaller_hitset(self):
        """solrutils - ranking smaller hitset"""
        hitset = intbitset.intbitset([47, 56, 58, 68, 85, 89])
        self.assertEqual((47, 56, 58, 68, 89, 85), self._get_ranked_result_sequence(query='higgs', hitset=hitset))

        hitset = intbitset.intbitset([45, 50, 61, 74, 94])
        self.assertEqual((50, 61, 74, 45, 94), self._get_ranked_result_sequence(query='of', hitset=hitset))
        self.assertEqual((74, 45, 94), self._get_ranked_result_sequence(query='of', hitset=hitset, rows=3))

    def test_get_ranked_larger_hitset(self):
        """solrutils - ranking larger hitset"""
        hitset = intbitset.intbitset([47, 56, 58, 68, 85, 89])
        self.assertEqual(tuple(), self._get_ranked_result_sequence(query='Willnotfind', hitset=hitset))

        hitset = intbitset.intbitset([47, 56, 55, 56, 58, 68, 85, 89])
        self.assertEqual((55, 56), self._get_ranked_result_sequence(query='"higgs boson"', hitset=hitset))


class TestSolrSimilarToRecid(unittest.TestCase):
    """Test for Solr similar ranking. Requires:
    make install-solrutils
    CFG_SOLR_URL set
    fulltext index in idxINDEX containing 'SOLR' in indexer column
    WRD method referring to Solr: <invenio installation>/etc/bibrank$ cp template_word_similarity_solr.cfg wrd.cfg
    ./bibrank -w wrd for all records
    """

    def _get_similar_result_sequence(self, recid, rows=ROWS):
        similar_result = solr_get_similar_ranked(recid, self._all_records, self._get_similar_ranking_params(), rows)
        return tuple([pair[0] for pair in similar_result[0]])[-rows:]

    def _get_similar_topN(self, n):
        return get_topN(n, self._SIMILAR)

    _SIMILAR = {
        30: (12, 95, 85, 82, 44, 1, 89, 64, 58, 15, 96, 61, 50, 86, 78, 77, 65, 62, 60,
             47, 46, 100, 99, 102, 91, 80, 7, 92, 88, 74, 57, 55, 108, 84, 81, 79, 54,
             101, 11, 103, 94, 48, 83, 72, 63, 2, 68, 51, 5, 53, 97, 93, 70, 45, 52, 14,
             59, 6, 10, 32, 33, 29, 30),
        59: (17, 69, 3, 20, 109, 14, 22, 33, 24, 60, 6, 73, 113, 107, 78, 4, 13, 5, 45,
             8, 72, 46, 74, 63, 71, 44, 87, 70, 103, 57, 92, 49, 88, 7, 68, 77, 10, 62,
             93, 2, 65, 55, 96, 43, 94, 1, 11, 99, 91, 61, 51, 15, 89, 64, 97, 108, 80,
             101, 86, 90, 54, 95, 102, 47, 100, 79, 83, 48, 12, 81, 82, 58, 50, 56, 84,
             85, 53, 52, 59)
    }

    def _get_similar_ranking_params(self, cutoff_amount=10000, cutoff_time=2000):
        """
        Default values from template_word_similarity_solr.cfg
        """
        return {
            'cutoff_amount': cutoff_amount,
            'cutoff_time_ms': cutoff_time,
            'find_similar_to_recid': {
                'more_results_factor': 5,
                'mlt_fl': 'mlt',
                'mlt_mintf': 0,
                'mlt_mindf': 0,
                'mlt_minwl': 0,
                'mlt_maxwl': 0,
                'mlt_maxqt': 25,
                'mlt_maxntp': 1000,
                'mlt_boost': 'false'
                }
            }

    _all_records = get_collection_reclist(CFG_SITE_NAME)

    def test_get_similar_ranked(self):
        """solrutils - similar results"""
        all_ranked = 0
        similar_top = self._get_similar_topN(all_ranked)
        recid = 30
        self.assertEqual(similar_top[recid], self._get_similar_result_sequence(recid=recid))
        recid = 59
        self.assertEqual(similar_top[recid], self._get_similar_result_sequence(recid=recid))

    def test_get_similar_ranked_top(self):
        """solrutils - similar top results"""
        top_n = 5
        similar_top = self._get_similar_topN(top_n)
        recid = 30
        self.assertEqual(similar_top[recid], self._get_similar_result_sequence(recid=recid, rows=top_n))
        recid = 59
        self.assertEqual(similar_top[recid], self._get_similar_result_sequence(recid=recid, rows=top_n))


TESTS = [TestReplaceInvalidCharacters, TestSolrRankingHelpers]

if CFG_SOLR_URL:
    TESTS.append(TestSolrSearch)
    if get_external_word_similarity_ranker() == 'solr':
        TESTS.extend((TestSolrRanking, TestSolrSimilarToRecid))

TEST_SUITE = make_test_suite(*TESTS)

if __name__ == "__main__":
    run_test_suite(TEST_SUITE)
