# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2011 CERN.
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

"""
Solr utilities.
"""


from invenio.config import CFG_SOLR_URL
from invenio.bibtask import write_message, task_get_option, task_update_progress
from invenio.dbquery import run_sql
from invenio.search_engine import get_fieldvalues, record_exists
from invenio.textutils import remove_control_characters
from invenio.bibdocfile import BibRecDocs
from invenio.bibrank_bridge_config import CFG_MARC_ABSTRACT, \
                                          CFG_MARC_AUTHOR_NAME, \
                                          CFG_MARC_ADDITIONAL_AUTHOR_NAME, \
                                          CFG_MARC_TITLE, \
                                          CFG_MARC_KEYWORD
from invenio.solrutils_bibindex_indexer import remove_invalid_solr_characters


if CFG_SOLR_URL:
    import solr
    SOLR_CONNECTION = solr.SolrConnection(CFG_SOLR_URL) # pylint: disable=E1101


def solr_add_all(lower_recid, upper_recid):
    range_length = upper_recid - lower_recid + 1
    sub_range_length = task_get_option("flush")

    processed_amount = 0
    i_low = lower_recid
    while i_low <= upper_recid:
        i_up = min(i_low + sub_range_length - 1, upper_recid)
        processed_amount += i_up - i_low + 1
        solr_add_range(i_low, i_up)
        status_msg = "......processed %s/%s records" % (processed_amount, range_length)
        write_message(status_msg)
        task_update_progress(status_msg)
        i_low += sub_range_length


def solr_add_range(lower_recid, upper_recid):
    """
    Adds the regarding field values of all records from the lower recid to the upper one to Solr.
    It preserves the fulltext information.
    """
    for recid in range(lower_recid, upper_recid + 1):
        if record_exists(recid):
            try:
                abstract = unicode(remove_control_characters(get_fieldvalues(recid, CFG_MARC_ABSTRACT)[0]), 'utf-8')
            except:
                abstract = ""
            try:
                first_author = remove_control_characters(get_fieldvalues(recid, CFG_MARC_AUTHOR_NAME)[0])
                additional_authors = remove_control_characters(reduce(lambda x, y: x + " " + y, get_fieldvalues(recid, CFG_MARC_ADDITIONAL_AUTHOR_NAME), ''))
                author = unicode(first_author + " " + additional_authors, 'utf-8')
            except:
                author = ""
            try:
                bibrecdocs = BibRecDocs(recid)
                fulltext = unicode(remove_control_characters(bibrecdocs.get_text()), 'utf-8')
            except:
                fulltext = ""
            try:
                keyword = unicode(remove_control_characters(reduce(lambda x, y: x + " " + y, get_fieldvalues(recid, CFG_MARC_KEYWORD), '')), 'utf-8')
            except:
                keyword = ""
            try:
                title = unicode(remove_control_characters(get_fieldvalues(recid, CFG_MARC_TITLE)[0]), 'utf-8')
            except:
                title = ""
            solr_add(recid, abstract, author, fulltext, keyword, title)

    SOLR_CONNECTION.commit()


def solr_add(recid, abstract, author, fulltext, keyword, title):
    """
    Helper function that adds word similarity ranking relevant indexes to Solr.
    """
    SOLR_CONNECTION.add(id=recid,
                        abstract=remove_invalid_solr_characters(abstract),
                        author=remove_invalid_solr_characters(author),
                        fulltext=remove_invalid_solr_characters(fulltext),
                        keyword=remove_invalid_solr_characters(keyword),
                        title=remove_invalid_solr_characters(title))



def word_similarity_solr(run):
    return word_index(run)


def word_index(run): # pylint: disable=W0613
    """
    Runs the indexing task.
    """
    id_option = task_get_option("id")
    if len(id_option):
        for id_elem in id_option:
            lower_recid= id_elem[0]
            upper_recid = id_elem[1]
            write_message("Solr ranking indexer called for %s-%s" % (lower_recid, upper_recid))
            solr_add_all(lower_recid, upper_recid)

    else:
        max_recid = 0
        res = run_sql("SELECT max(id) FROM bibrec")
        if res and res[0][0]:
            max_recid = int(res[0][0])

        write_message("Solr ranking indexer called for %s-%s" % (1, max_recid))
        solr_add_all(1, max_recid)

    write_message("Solr ranking indexer completed")
