import cgi
import urllib
import hashlib.sha1

from google.appengine.api import users, urlfetch
from google.appengine.ext import ndb

import webapp2

Form_FOOTER_TEMPLATE = """\
    <form action="/register?%s" method="post">
      IP Address of the server:  <input type="text" name="ipaddr"><br>
      <div><input type="submit" value="Register for ArkC"></div>
    </form>
  </body>
</html>
"""

DEFAULT_DB_NAME = 'default_guestbook'

######
#CONFIG
######

# We set a parent key on the 'Greetings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent.  However, the write rate should be limited to
# ~1/second.


def guestbook_key(guestbook_name=DEFAULT_GUESTBOOK_NAME):
    """Constructs a Datastore key for a Guestbook entity.

    We use guestbook_name as the key.
    """
    return ndb.Key('DB', guestbook_name)


class User(ndb.Model):
    """A main model for representing an individual Guestbook entry."""
    identity = ndb.StringProperty(indexed=True)
    #password = ndb.StringProperty(indexed = False)
    number = ndb.StringProperty(indexed=False)
    content = ndb.StringProperty(indexed=False)
    domain = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)


class Form(webapp2.RequestHandler):

    def get(self):
        self.response.write('<html><body>')
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_DB_NAME)

        # Write the submission form and the footer of the page
        sign_query_params = urllib.urlencode({'guestbook_name':
                                              guestbook_name})
        self.response.write(Form_FOOTER_TEMPLATE % (sign_query_params))


class ShowResult(webapp2.RequestHandler):
    # TODO: edit for query

    def get(self):
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_DB_NAME)
        identity = self.request.get('identity', '')
        userrecord_query = User.query(ancestor=guestbook_key(guestbook_name))
        userrecords = userrecord_query.fetch(1)
        try:
            resp = '''<html><body>
        <form>
      DNS NS record linked to %s:  <input type="text" value="%s" readonly=True><br>
      Example JSON configuration file at client side: <br>
      <textarea rows="15" cols="40">
      %s 
      </textarea>
    </form>
  </body>
</html>''' % (userrecords[0].content, userrecords[0].domain, '''{
    "control_domain":"%s",
    ......
}''' % userrecords[0].domain)
        except Exception:
            resp = '''<html><body>
        Not Found
  </body>
</html>'''
        self.response.write(resp)


class Register(webapp2.RequestHandler):

    def post(self):
        # We set the same parent key on the 'Greeting' to ensure each
        # Greeting is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_GUESTBOOK_NAME)
        userrecord = Greeting(parent=guestbook_key(guestbook_name))

        userrecord.content = self.request.get('ipaddr')
        #userrecord.password = self.request.get('password')
        #userrecord.number = self.request.get('number')
        h = hashlib.sha1()
        h.update(self.request.get('ipaddr'))
        userrecord.identity = h.hexdigest()
        userrecord.domain = h.hexdigest()[:10] + '.' + SECONDARY_DOMAIN
        form_data = '''{"type":"NS","name":"%s", "content":"%s","ttl":3600}''' % (
            userrecord.domain, userrecord.content)
        result = urlfetch.fetch(url="https://api.cloudflare.com/client/v4/zones/" + ZONE_ID + "/dns_records",
                                payload=form_data,
                                method=urlfetch.POST,
                                headers={"X-Auth-Email": EMAIL,
                                         "X-Auth-Key": AUTH_KEY,
                                         "Content-Type": "application/json"})
        if result.status_code == 200:
            userrecord.put()
            query_params = {
                'guestbook_name': guestbook_name, "identity": userrecord.identity}
            self.redirect('/result?' + urllib.urlencode(query_params))
        else:
            pass

app = webapp2.WSGIApplication([
    ('/', Form),
    ('/result', ShowResult),
    ('/register', Register),
], debug=True)
