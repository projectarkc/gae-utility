import cgi
import urllib
import hashlib

from google.appengine.api import users, urlfetch
from google.appengine.ext import ndb

import webapp2

Form_FOOTER_TEMPLATE = """\
    <form action="/nsregister?%s" method="post">
      This form creates an NS DNS record for you, so that you can use it as control_domain without owning a domain.<br>
      <br>
      IP Address of the server:  <input type="text" name="ipaddr"><br>
      Please provide your email address in case we need to modify DNS settings:  <input type="text" name="email"><br>
      <div><input type="submit" value="Register for ArkC"></div>
    </form>
    <hr>
    <a href="/fillconfig">Create server side JSON by filling a form.</a>
  </body>
</html>
"""

DEFAULT_DB_NAME = 'default_guestbook'

######
# CONFIG
NAME_SERVICE_PROVIDER = "Cloudflare.com"
######

# We set a parent key on the 'Greetings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent.  However, the write rate should be limited to
# ~1/second.


def validate_ip(s):
    a = s.split('.')
    if len(a) != 4:
        return False
    for x in a:
        if not x.isdigit():
            return False
        i = int(x)
        if i < 0 or i > 255:
            return False
    return True


def guestbook_key(guestbook_name=DEFAULT_DB_NAME):
    """Constructs a Datastore key for a Guestbook entity.

    We use guestbook_name as the key.
    """
    return ndb.Key('DB', guestbook_name)


class User(ndb.Model):
    """A main model for representing an individual Guestbook entry."""
    identity = ndb.StringProperty(indexed=True)
    #password = ndb.StringProperty(indexed = False)
    #number = ndb.StringProperty(indexed=False)
    content = ndb.StringProperty(indexed=False)
    NS_record = ndb.StringProperty(indexed=False)
    A_record = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)


class NSForm(webapp2.RequestHandler):

    def get(self):
        self.response.write('<html><body>')
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_DB_NAME)

        # Write the submission form and the footer of the page
        sign_query_params = urllib.urlencode({'guestbook_name':
                                              guestbook_name})
        self.response.write(Form_FOOTER_TEMPLATE % (sign_query_params))


class cfgForm(webapp2.RequestHandler):

    def get(self):
        resp = """<html><body>
    <form action="/showjsonconfig" method="post">
      Fill this form and we will generate the JSON config file at server side for you. <br>
      We recommmend you to use arkcserver-mailcheck to rececive register requests from clients. Set the location for the database to experience the conveniencei.<br>
      If not using database, in this page you can only create a config with ONE client in the config. However, you may add more later by yourself with the same format.<br>
      Leave it blank if you have no idea about some boxes.<br>
      <br>
      Path of your server's private key: (The path specified after "Private key written to" when generating it, often ends with "...pri.asc".)<br>
      <input type="text" name="localcert" size=60><br>
      <hr>
      Path of client information database: (Used with arkcserver-mailcheck) <br>
      <input type="text" name="clientdb" size=60><br>
      <hr>
      Path of client public key: (Often copied to server) <br>
      <input type="text" name="clientpub" size=60><br>
      SHA1 value of the client private key: (Prompted when generating key pair at client side): <br>
      <hr>
      <input type="text" name="clientsha1" size=60><br>
      Using MEEK or not? If you intend to integrate with GAE (and CDN in the future), choose yes. <br>
      <input type="radio" name="meek" value="3"> Yes<br>
      <input type="radio" name="meek" value="0" checked=True> No<br>
      MEEK executable path: (meek-client at server side.)<br>
      <input type="text" name="meekexec" size=60><br>
      <br>
      <div><input type="submit" value="See the generated file."></div>
    </form>
  </body>
</html>
"""
        self.response.write(resp)


class ShowResult(webapp2.RequestHandler):

    def get(self):
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_DB_NAME)
        identity = self.request.get('identity', '')
        userrecord_query = User.query(
            ancestor=guestbook_key(guestbook_name)).filter(User.identity == identity)
        userrecords = userrecord_query.fetch(1)
        try:
            resp = '''<html><body>
        <form>
      NS record is linked to your server:<br>
      DNS NS record linked to %s via A record %s:  <input type="text" value="%s" readonly=True><br>
      You can now enjoy the service. To add client keys to your server, send emails to anyname@%s with subject including "Confenrence Registration". Make the first line in the email the prompted SHA1 digest of the client's private key, and attach the public key file in the email!<br>
      Enjoy!<br>
      <hr>
      Example JSON configuration file at client side: <br>
      <textarea rows="15" cols="40">%s</textarea>
    </form>
  </body>
</html>''' % (userrecords[0].content, userrecords[0].A_record, userrecords[0].NS_record, userrecords[0].NS_record,
              '''{
    "control_domain":"%s",
    ......
}''' % userrecords[0].NS_record)
        except Exception:
            resp = '''<html><body>
        Not Found
  </body>
</html>'''
        self.response.write(resp)


class ShowJSON(webapp2.RequestHandler):

    def post(self):

        jsontext = '''{
    "local_cert_path":"%s",
    "clients_db":"%s"
    "clients": [["%s", "%s"]],
    "obfs_level":%s,
    "pt_exec":"%s"
}''' % (self.request.get('localcert', ''),
            self.request.get('clientpub', ''),
            self.request.get('clientdb', ''),
            self.request.get('clientsha1', ''),
            self.request.get('meek', '0'),
            self.request.get('meekexec', '')
        )
        resp = '''<html><body>
        <form>
      Example JSON configuration file at server side: <br>
      <textarea rows="15" cols="40">%s</textarea>
    </form>
  </body>
</html>''' % jsontext
        self.response.write(resp)


class NSRegister(webapp2.RequestHandler):

    def post(self):
        # We set the same parent key on the 'Greeting' to ensure each
        # Greeting is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_DB_NAME)
        userrecord = User(parent=guestbook_key(guestbook_name))
        userrecord.content = self.request.get('ipaddr').strip()
        if validate_ip(userrecord.content):
            #userrecord.password = self.request.get('password')
            h = hashlib.sha1()
            h.update(self.request.get('ipaddr'))
            userrecord_query = User.query(
                ancestor=guestbook_key(guestbook_name)).filter(User.identity == h.hexdigest())
            userrecords = userrecord_query.fetch(1)
            if len(userrecords) == 0:
                userrecord.identity = h.hexdigest()
                userrecord.NS_record = h.hexdigest()[
                    :10] + '.' + SECONDARY_DOMAIN
                userrecord.A_record = h.hexdigest()[
                    :10] + '.a.' + SECONDARY_DOMAIN
                form_data1 = '''{"type":"NS","name":"%s", "content":"%s","ttl":3600}''' % (
                    userrecord.NS_record, userrecord.A_record)
                result1 = urlfetch.fetch(url="https://api.cloudflare.com/client/v4/zones/" + ZONE_ID + "/dns_records",
                                         payload=form_data1,
                                         method=urlfetch.POST,
                                         headers={"X-Auth-Email": EMAIL,
                                                  "X-Auth-Key": AUTH_KEY,
                                                  "Content-Type": "application/json"})
                form_data2 = '''{"type":"A","name":"%s", "content":"%s","ttl":1800}''' % (
                    userrecord.A_record, userrecord.content)
                result2 = urlfetch.fetch(url="https://api.cloudflare.com/client/v4/zones/" + ZONE_ID + "/dns_records",
                                         payload=form_data2,
                                         method=urlfetch.POST,
                                         headers={"X-Auth-Email": EMAIL,
                                                  "X-Auth-Key": AUTH_KEY,
                                                  "Content-Type": "application/json"})
                if result1.status_code == 200 and result2.status_code == 200:
                    userrecord.email = self.request.get('email')
                    userrecord.put()
                    query_params = {
                        'guestbook_name': guestbook_name, "identity": userrecord.identity}
                    self.redirect('/result?' + urllib.urlencode(query_params))
                else:
                    pass
            else:
                query_params = {
                    'guestbook_name': guestbook_name, "identity": h.hexdigest()}
                self.redirect('/result?' + urllib.urlencode(query_params))
        else:
            pass

app = webapp2.WSGIApplication([
    ('/', NSForm),
    ('/result', ShowResult),
    ('/nsregister', NSRegister),
    ('/fillconfig', cfgForm),
    ('/showjsonconfig', ShowJSON)
])
