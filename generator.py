import os

from flask import Flask, render_template, url_for
from werkzeug import cached_property
import markdown
import yaml

POSTS_FILE_EXTENSION = '.md'

app = Flask(__name__)

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

@app.template_filter('date')
def format_date(value, format='%B %d, %Y'):
	return value.strftime(format)

@app.route('/')
def index():
	posts = [Post('hello.md', root_dir='posts')]
	return render_template('index.html', posts=posts)

@app.route('/blog/<path:path>')
def post(path):
	post = Post(path + POSTS_FILE_EXTENSION, root_dir='posts')
	return render_template('post.html', post=post)

if __name__ == '__main__':
	app.run(port=8000, debug=True)