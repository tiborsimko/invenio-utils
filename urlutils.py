# -*- coding: utf-8 -*-
##
## This file is part of CDS Invenio.
## Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007, 2008 CERN.
##
## CDS Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## CDS Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with CDS Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
urlutils.py -- helper functions for URL related problems such as
argument washing, redirection, etc.
"""

__revision__ = "$Id$"

import re
from urllib import urlencode, quote_plus, quote
from urlparse import urlparse
from cgi import parse_qs, escape

try:
    from mod_python import apache, util
except ImportError:
    pass

from invenio.config import \
     CFG_SITE_LANG, \
     CFG_SITE_URL, \
     CFG_WEBSTYLE_EMAIL_ADDRESSES_OBFUSCATION_MODE

def wash_url_argument(var, new_type):
    """
    Wash argument into 'new_type', that can be 'list', 'str',
                                               'int', 'tuple' or 'dict'.
    If needed, the check 'type(var) is not None' should be done before
    calling this function.
    @param var: variable value
    @param new_type: variable type, 'list', 'str', 'int', 'tuple' or 'dict'
    @return as much as possible, value var as type new_type
            If var is a list, will change first element into new_type.
            If int check unsuccessful, returns 0
    """
    out = []
    if new_type == 'list':  # return lst
        if type(var) is list:
            out = var
        else:
            out = [var]
    elif new_type == 'str':  # return str
        if type(var) is list:
            try:
                out = "%s" % var[0]
            except:
                out = ""
        elif type(var) is str:
            out = var
        else:
            out = "%s" % var
    elif new_type == 'int': # return int
        if type(var) is list:
            try:
                out = int(var[0])
            except:
                out = 0
        elif type(var) is int:
            out = var
        elif type(var) is str:
            try:
                out = int(var)
            except:
                out = 0
        else:
            out = 0
    elif new_type == 'tuple': # return tuple
        if type(var) is tuple:
            out = var
        else:
            out = (var,)
    elif new_type == 'dict': # return dictionary
        if type(var) is dict:
            out = var
        else:
            out = {0:var}
    return out

def redirect_to_url(req, url, redirection_type=None):
    """
    Redirect current page to url.
    @param req: request as received from apache
    @param url: url to redirect to
    @param redirection_type: what kind of redirection is required:
    e.g.: apache.HTTP_MULTIPLE_CHOICES             = 300
          apache.HTTP_MOVED_PERMANENTLY            = 301
          apache.HTTP_MOVED_TEMPORARILY            = 302
          apache.HTTP_SEE_OTHER                    = 303
          apache.HTTP_NOT_MODIFIED                 = 304
          apache.HTTP_USE_PROXY                    = 305
          apache.HTTP_TEMPORARY_REDIRECT           = 307
    The default is apache.HTTP_TEMPORARY_REDIRECT
    Please see: http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.3
    """
    if redirection_type is None:
        redirection_type = apache.HTTP_MOVED_TEMPORARILY
    req.err_headers_out["Location"] = url

    del req.headers_out["Cache-Control"]
    req.err_headers_out["Cache-Control"] = "no-cache, private, no-store, must-revalidate, post-check=0, pre-check=0, max-age=0"
    req.err_headers_out["Pragma"] = "no-cache"

    if req.headers_out.has_key("Set-Cookie"):
        cookies = req.headers_out['Set-Cookie']
        if type(cookies) is list:
            for cookie in cookies:
                req.err_headers_out.add("Set-Cookie", cookie)
        else:
            req.err_headers_out.add("Set-Cookie", cookies)

    if req.sent_bodyct:
        raise IOError, "Cannot redirect after headers have already been sent."

    req.status = redirection_type
    req.write('<p>Please go to <a href="%s">here</a></p>\n' % url)

    raise apache.SERVER_RETURN, apache.DONE

def get_client_ip_address(req):
    """ Returns IP address as string from an apache request. """
    return str(req.get_remote_host(apache.REMOTE_NOLOOKUP))

def get_referer(req, replace_ampersands=False):
    """ Return the referring page of a request.
    Referer (wikipedia): Referer is a common misspelling of the word "referrer";
    so common, in fact, that it made it into the official specification of HTTP.
    When visiting a webpage, the referer or referring page is the URL of the
    previous webpage from which a link was followed.
    @param req: request
    @param replace_ampersands: if 1, replace & by &amp; in url
                               (correct HTML cannot contain & characters alone).
    """
    try:
        referer = req.headers_in['Referer']
        if replace_ampersands == 1:
            return referer.replace('&', '&amp;')
        return referer
    except KeyError:
        return ''

def drop_default_urlargd(urlargd, default_urlargd):
    lndefault = {}
    lndefault.update(default_urlargd)

    ## Commented out. An Invenio URL now should always specify the desired
    ## language, in order not to raise the automatic language discovery
    ## (client browser language can be used now in place of CFG_SITE_LANG)
    # lndefault['ln'] = (str, CFG_SITE_LANG)

    canonical = {}
    canonical.update(urlargd)

    for k, v in urlargd.items():
        try:
            d = lndefault[k]

            if d[1] == v:
                del canonical[k]

        except KeyError:
            pass

    return canonical

def make_canonical_urlargd(urlargd, default_urlargd):
    """ Build up the query part of an URL from the arguments passed in
    the 'urlargd' dictionary.  'default_urlargd' is a secondary dictionary which
    contains tuples of the form (type, default value) for the query
    arguments (this is the same dictionary as the one you can pass to
    webinterface_handler.wash_urlargd).

    When a query element has its default value, it is discarded, so
    that the simplest (canonical) url query is returned.

    The result contains the initial '?' if there are actual query
    items remaining.
    """

    canonical = drop_default_urlargd(urlargd, default_urlargd)

    if canonical:
        return '?' + urlencode(canonical, doseq=True).replace('&', '&amp;')

    return ''

def create_html_link(urlbase, urlargd, link_label, linkattrd={},
                     escape_urlargd=True, escape_linkattrd=True):
    """Creates a W3C compliant link.
    @param urlbase: base url (e.g. invenio.config.CFG_SITE_URL/search)
    @param urlargd: dictionary of parameters. (e.g. p={'recid':3, 'of'='hb'})
    @param link_label: text displayed in a browser (has to be already escaped)
    @param linkattrd: dictionary of attributes (e.g. a={'class': 'img'})
    @param escape_urlargd: boolean indicating if the function should escape
                           arguments (e.g. < becomes &lt; or " becomes &quot;)
    @param escape_linkattrd: boolean indicating if the function should escape
                           attributes (e.g. < becomes &lt; or " becomes &quot;)
    """
    attributes_separator = ' '
    output = '<a href="' + \
             create_url(urlbase, urlargd, escape_urlargd) + '"'
    if linkattrd:
        output += ' '
        if escape_linkattrd:
            attributes = [escape(str(key), quote=True) + '="' + \
                          escape(str(linkattrd[key]), quote=True) + '"'
                                for key in linkattrd.keys()]
        else:
            attributes = [str(key) + '="' + str(linkattrd[key]) + '"'
                                for key in linkattrd.keys()]
        output += attributes_separator.join(attributes)
    output += '>' + link_label + '</a>'
    return output

def create_html_mailto(email, subject=None, body=None, cc=None, bcc=None,
                       link_label="%(email)s", linkattrd=None,
                       escape_urlargd=True, escape_linkattrd=True,
                       email_obfuscation_mode=CFG_WEBSTYLE_EMAIL_ADDRESSES_OBFUSCATION_MODE):

    """Creates a W3C compliant 'mailto' link.

    Encode/encrypt given email to reduce undesired automated email
    harvesting when embedded in a web page.

    NOTE: there is no ultimate solution to protect against email
    harvesting. All have drawbacks and can more or less be
    circumvented. There are other techniques to protect email
    adresses. We implement the less annoying one for users.

    @param email: the recipient of the email
    @param subject: a default subject for the email (must not contain
                    line feeds)
    @param body: a default body for the email
    @param cc: the co-recipient(s) of the email
    @param bcc: the hidden co-recpient(s) of the email
    @param link_label: the label of this mailto link. String
                       replacement is performed on key %(email)s with
                       the email address if needed.
    @param linkattrd: dictionary of attributes (e.g. a={'class': 'img'})
    @param escape_urlargd: boolean indicating if the function should escape
                           arguments (e.g. < becomes &lt; or " becomes &quot;)
    @param escape_linkattrd: boolean indicating if the function should escape
                           attributes (e.g. < becomes &lt; or " becomes &quot;)
    @param email_obfuscation_mode: the protection mode. See below:

    You can choose among several modes to protect emails. It is
    advised to keep the default
    CFG_MISCUTIL_EMAIL_HARVESTING_PROTECTION value, so that it is
    possible for an admin to change the policy globally.

    Available modes ([t] means "transparent" for the user):

         -1: hide all emails, excepted CFG_SITE_ADMIN_EMAIL and
              CFG_SITE_SUPPORT_EMAIL.

      [t] 0 : no protection, email returned as is.
                foo@example.com => foo@example.com

          1 : basic email munging: replaces @ by [at] and . by [dot]
                foo@example.com => foo [at] example [dot] com

      [t] 2 : transparent name mangling: characters are replaced by
              equivalent HTML entities.
                foo@example.com => &#102;&#111;&#111;&#64;&#101;&#120;&#97;&#109;&#112;&#108;&#101;&#46;&#99;&#111;&#109;

      [t] 3 : javascript insertion. Requires Javascript enabled on client side.

          4 : replaces @ and . characters by gif equivalents.
                foo@example.com => foo<img src="at.gif" alt=" [at] ">example<img src="dot.gif" alt=" [dot] ">com
    """
    # TODO: implement other protection modes to encode/encript email:
    #
    ## [t] 5 : form submission. User is redirected to a form that he can
    ##         fills in to send the email (??Use webmessage??).
    ##         Depending on WebAccess, ask to answer a question.
    ##
    ## [t] 6 : if user can see (controlled by WebAccess), display. Else
    ##         ask to login to see email. If user cannot see, display
    ##         form submission.

    if linkattrd is None:
        linkattrd = {}

    parameters = {}
    if subject:
        parameters["subject"] = subject
    if body:
        parameters["body"] = body.replace('\r\n', '\n').replace('\n', '\r\n')
    if cc:
        parameters["cc"] = cc
    if bcc:
        parameters["bcc"] = bcc

    # Preprocessing values for some modes
    if email_obfuscation_mode == 1:
        # Basic Munging
        email = email.replace("@", " [at] ").replace(".", " [dot] ")
    elif email_obfuscation_mode == 2:
        # Transparent name mangling
        email = string_to_numeric_char_reference(email)

    if '%(email)s' in link_label:
        link_label = link_label % {'email': email}

    mailto_link = create_html_link('mailto:' + email, parameters,
                                   link_label, linkattrd,
                                   escape_urlargd, escape_linkattrd)

    if email_obfuscation_mode == 0:
        # Return "as is"
        return mailto_link
    elif email_obfuscation_mode == 1:
        # Basic Munging
        return mailto_link
    elif email_obfuscation_mode == 2:
        # Transparent name mangling
        return mailto_link
    elif email_obfuscation_mode == 3:
        # Javascript-based
        return '''<script language="JavaScript" type="text/javascript">document.write('%s'.split("").reverse().join(""))</script>''' % \
               mailto_link[::-1].replace("'", "\\'")
    elif email_obfuscation_mode == 4:
        # GIFs-based
        email = email.replace('.',
                              '<img src="%s/img/dot.gif" alt=" [dot] " style="vertical-align:bottom"  />' \
                              % CFG_SITE_URL)
        email = email.replace('@',
                              '<img src="%s/img/at.gif" alt=" [at] " style="vertical-align:baseline" />' % \
                              CFG_SITE_URL)
        return email

    # All other cases, including mode -1:
    return ""

def string_to_numeric_char_reference(string):
    """
    Encode a string to HTML-compatible numeric character reference.
    Eg: encode_html_entities("abc") == '&#97;&#98;&#99;'
    """
    out = ""
    for char in string:
        out += "&#" + str(ord(char)) + ";"
    return out

def create_url(urlbase, urlargd, escape_urlargd=True):
    """Creates a W3C compliant URL. Output will look like this:
    'urlbase?param1=value1&amp;param2=value2'
    @param urlbase: base url (e.g. invenio.config.CFG_SITE_URL/search)
    @param urlargd: dictionary of parameters. (e.g. p={'recid':3, 'of'='hb'}
    @param escape_urlargd: boolean indicating if the function should escape
                           arguments (e.g. < becomes &lt; or " becomes &quot;)
    """
    separator = '&amp;'
    output = urlbase
    if urlargd:
        output += '?'
        if escape_urlargd:
            arguments = [escape(quote(str(key)), quote=True) + '=' + \
                         escape(quote(str(urlargd[key])), quote=True)
                                for key in urlargd.keys()]
        else:
            arguments = [str(key) + '=' + str(urlargd[key])
                            for key in urlargd.keys()]
        output += separator.join(arguments)
    return output

def same_urls_p(a, b):
    """ Compare two URLs, ignoring reorganizing of query arguments """

    ua = list(urlparse(a))
    ub = list(urlparse(b))

    ua[4] = parse_qs(ua[4])
    ub[4] = parse_qs(ub[4])

    return ua == ub

def urlargs_replace_text_in_arg(urlargs, regexp_argname, text_old, text_new):
    """Analyze `urlargs' (URL CGI GET query arguments in string form)
       and for each occurrence of argument matching `regexp_argname'
       replace every substring `text_old' by `text_new'.  Return the
       resulting new URL.

       Used to be used for search engine's create_nearest_terms_box,
       now it is not used there anymore.  It is left here in case it
       will become possibly useful later.
    """
    out = ""
    # parse URL arguments into a dictionary:
    urlargsdict = parse_qs(urlargs)
    ## construct new URL arguments:
    urlargsdictnew = {}
    for key in urlargsdict.keys():
        if re.match(regexp_argname, key): # replace `arg' by new values
            urlargsdictnew[key] = []
            for parg in urlargsdict[key]:
                urlargsdictnew[key].append(parg.replace(text_old, text_new))
        else: # keep old values
            urlargsdictnew[key] = urlargsdict[key]
    # build new URL for this word:
    for key in urlargsdictnew.keys():
        for val in urlargsdictnew[key]:
            out += "&amp;" + key + "=" + quote_plus(val, '')
    if out.startswith("&amp;"):
        out = out[5:]
    return out

