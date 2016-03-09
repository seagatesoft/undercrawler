#!/usr/bin/env python3
from urllib.parse import urlsplit, urlunsplit

import jinja2
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import flask_admin
from flask_admin.contrib import sqla
from sqlalchemy import UniqueConstraint, sql
from sqlalchemy.exc import IntegrityError


app = Flask(__name__)

app.config['SECRET_KEY'] = '_@5z$#yogw-zoe4ev2oxv#7ta-80s*m!$^o)#-*6s+6vm1d9i'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keychain_db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


@app.route('/')
def index():
    return '<a href="/admin/keychainitem/">Login keychain admin</a>'


class KeychainItem(db.Model):
    __tablename__ = 'keychain_item'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Parts of the registration url
    scheme = db.Column(db.String(63), nullable=False)
    netloc = db.Column(db.String(255), nullable=False)
    path = db.Column(db.Text(), nullable=False, default='')
    query = db.Column(db.Text(), nullable=False, default='')
    fragment = db.Column(db.Text(), nullable=False, default='')
    # Login credentials (or marked as skipped)
    skip = db.Column(db.Boolean, default=False, nullable=False)
    login = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint('scheme', 'netloc', 'path', 'query', 'fragment',
                         name='_unique_url'),
    )

    @classmethod
    def add_task(cls, url, max_per_domain):
        parts = urlsplit(url)
        if (db.session.query(cls)
                .filter(cls.netloc == parts.netloc)
                .count()) >= max_per_domain:
            return None
        item = cls(
            scheme=parts.scheme,
            netloc=parts.netloc,
            path=parts.path,
            query=parts.query,
            fragment=parts.fragment,
            skip=False)
        db.session.add(item)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        else:
            return item

    @classmethod
    def solved_by_login_url(cls, url):
        ''' Return a list of (login, password) pairs for solved registration
        task. URLS are filter only by netloc.
        '''
        netloc = urlsplit(url).netloc
        return [(item.login, item.password) for item in db.session.query(cls)
            .filter(cls.netloc == netloc)
            .filter(cls.skip == False)
            .filter(cls.login != None)
            .filter(cls.password != None)]

    @classmethod
    def any_unsolved(cls):
        ''' Are there any unsolved tasks?
        '''
        return db.session.query(sql.exists().where(
            (cls.skip == False) &
            ((cls.login == None) | (cls.password == None))
            )).scalar()

    def __unicode__(self):
        return '%s: %s' % (self.url, self.login)

    @property
    def url(self):
        return urlunsplit(
            (self.scheme, self.netloc, self.path, self.query, self.fragment))

    @property
    def href(self):
        return jinja2.Markup(
            '<a href="{url}" target="_blank">{url}</a>'.format(url=self.url))


class KeychainItemAdmin(sqla.ModelView):
    column_list = ['href', 'skip', 'login', 'password']
    column_labels = {
        'href': 'URL',
        'skip': 'Skip?',
    }
    column_editable_list = ['skip', 'login', 'password']
    column_searchable_list = ['netloc', 'query']


admin = flask_admin.Admin(app, template_mode='bootstrap3')
admin.add_view(KeychainItemAdmin(KeychainItem, db.session))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default='5000')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    db.create_all()
    app.run(args.host, args.port, debug=args.debug)
