from tornado.escape import xhtml_escape


def html_escape(html):
    if html:
        return xhtml_escape(html)
    return None

def simple_escape(html):
    if html:
        html = html.replace('<', '&lt;').replace('>', '&gt;')
    else:
        html = ""
    return html

def br_escape(html):
    if html:
        html = html.replace('\n', '<br/>')
    else:
        html = ""
    return html