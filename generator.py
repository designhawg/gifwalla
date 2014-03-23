import os

from flask import Flask, render_template, url_for, abort
from werkzeug import cached_property
import markdown
import yaml

POSTS_FILE_EXTENSION = '.md'

class Blog(object):
	def __init__(self, app, root_dir='', file_ext=POSTS_FILE_EXTENSION):
		self.root_dir = root_dir
		self.file_ext = file_ext
		self.app = app
		self._cache = {}
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

	@property
	def url(self):
		return url_for('post', path=self.urlpath)

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


@app.template_filter('date')
def format_date(value, format='%B %d, %Y'):
	return value.strftime(format)

@app.route('/')
def index():
	return render_template('index.html', posts=blog.posts)

@app.route('/blog/<path:path>')
def post(path):
	post = blog.get_post_or_404(path)
	return render_template('post.html', post=post)

if __name__ == '__main__':
	app.run(port=8000, debug=True)