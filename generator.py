import os
import sys
import collections

import boto

from boto.s3.key import Key
from flask import Flask, render_template, url_for, abort, request
from flask.ext.frozen import Freezer
from werkzeug import cached_property
from werkzeug.contrib.atom import AtomFeed
import markdown
import yaml

DOMAIN = 'gifwalla.com'
AWS_ACCESS_KEY_ID = 'AKIAIOFCHO67G7A4A35A'
AWS_SECRET_ACCESS_KEY = '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'

POSTS_FILE_EXTENSION = '.md'

# inheriting off of the MutableMapping abstract base class here

class SortedDict(collections.MutableMapping):
	def __init__(self, items=None, key=None, reverse=False):
		self._items = {}
		self._keys = []
		if key:
			self._key_fn = lambda k: key(self._items[k])
		else:
			self._key_fn = lambda k: self._items[k]
		self._reverse = reverse

		if items is not None:
			self.update(items)


	def __getitem__(self, key):
		return self._items[key]

	def __setitem__(self, key, value):
		self._items[key] = value
		if key not in self._keys:
			self._keys.append(key)
			# this allows for the list of items to be compared and reordered
			self._keys.sort(key=self._key_fn, reverse=self._reverse)

	def __delitem__(self, key):
		self._items.pop(key)
		self._keys.remove(key)

	def __len__(self):
		return len(self._keys)

	def __iter__(self):
		for key in self._keys:
			yield key

	def __repr__(self):
		return '%s(%s)' % (self.__class__.__name__, self._items)

class Blog(object):
	def __init__(self, app, root_dir='', file_ext=POSTS_FILE_EXTENSION):
		self.root_dir = root_dir
		self.file_ext = file_ext
		self.app = app
		# this is where the blog class calls upon the SortedDict for comparison of dates
		# changing reverse to false will flip the order of posts shown
		self._cache = SortedDict(key = lambda p: p.date, reverse=True)
		self._initialize_cache()

	@property
	def posts(self):
		return self._cache.values()

	def get_post_or_404(self, path):
		# returns the Post object for a given path or raises an exception
		try:
			return self._cache[path]
		except KeyError:
			abort(404)

	def _initialize_cache(self):
		# Walks the root directory and adds all posts to cache
		# current root_dir + directory list of root_dir + files in root_dir
		for (root, dirpaths, filepaths) in os.walk(self.root_dir):
			for filepath in filepaths:
				filename, ext = os.path.splitext(filepath)
				if ext == self.file_ext:
					path = os.path.join(root, filepath).replace(self.root_dir, '')
					post = Post(path, root_dir = self.root_dir)
					self._cache[post.urlpath] = post

class Post(object):
	def __init__(self, path, root_dir=''):
		self.urlpath = os.path.splitext(path.strip('/'))[0]
		self.filepath = os.path.join(root_dir, path.strip('/'))
		self._initialize_metadata()

	@cached_property
	def html(self):
		with open(self.filepath, 'r') as fin:
			content = fin.read().split('\n\n', 1)[1].strip()
		return markdown.markdown(content)

	def url(self, _external=False):
		return url_for('post', path=self.urlpath, _external = _external)

	def _initialize_metadata(self):
		content = ''
		with open(self.filepath, 'r') as fin:
			for line in fin:
				if not line.strip():
					break
				content += line
		self.__dict__.update(yaml.load(content))

app = Flask(__name__)
blog = Blog(app, root_dir = 'posts')
freezer = Freezer(app)


@app.template_filter('date')
def format_date(value, format='%B %d, %Y'):
	return value.strftime(format)

@app.route('/')
def index():
	return render_template('index.html', posts=blog.posts)

@app.route('/series/<path:path>/')
def post(path):
	post = blog.get_post_or_404(path)
	return render_template('post.html', post=post)

@app.route('/feed.atom')
def feed():
	feed = AtomFeed('Recent Articles',
		#the feed url is the source that powers the website url, which is the literal address
		#request is imported from Flask, but this Global variable is considered a Context Local.
    	feed_url=request.url,
    	url=request.url_root)
	posts = blog.posts[:10]
    # this exists because there is no subtitle option within FeedEntry method
	title = lambda p: "%s: %s" % (p.title, p.subtitle) if hasattr(p, 'subtitle') else p.title

	for post in posts:
		feed.add(title(post),
		unicode(post.html),
			content_type='html',
			author='Chris Courtney',
			url=post.url(_external=True),
			updated=post.date,
			published=post.date)
	return feed.get_response()

def deploy(root_dir):
	conn = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
	bucket = conn.get_bucket(DOMAIN)
	for (root, dirpaths, filepaths) in os.walk(root_dir):
		for filepath in filepaths:
			filename = os.path.join(root, filepath)
			name = filename.replace(root_dir, '', 1)[1:]
			key = Key(bucket, name)
			key.set_contents_from_filename(filename)

	print 'Site is now up on %s' % bucket.get_website_endpoint()

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == 'build':
		freezer.freeze()
	elif len(sys.argv) > 1 and sys.argv[1] == 'deploy':
		freezer.freeze()
		deploy('build')
	else:
		post_files = [post.filepath for post in blog.posts]
		app.run(port=8000, debug=True, extra_files=post_files)

		#post_files was created to allow the creator to automatically update the app locally without having to respin up the local server to account for the new files
