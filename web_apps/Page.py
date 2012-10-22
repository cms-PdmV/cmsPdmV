from jinja2 import Environment, PackageLoader

class Page(object) :
	def __init__(self, title=None, result=None, signature=None, restful=False):
		if not title:
			self.title = ''
		else:
			self.title = title
		if not result:
			self.result = ''
		else:
			self.result = result
		if not signature:
			self.signature = ''
		else:
			self.signature = signature
		
		# indicate if a template is to be loaded
		self.restful = restful
		
		# load template
		self.environment = Environment(loader=PackageLoader(__name__, '../templates'))
	
	def header(self):
		header_tmpl = self.environment.get_template('header.tmpl')
		return header_tmpl.render({'title': self.title})
	
	def footer(self):
		return '<br><br><span class="footer">' + self.signature + '</span></html>'
	
	def render_template(self, template=''):
		if not template:
			return False
		try:	
			temp = self.environment.get_template(template)
			self.result = temp.render() 
		except Exception as ex:
			return False
		return True
		
	def index(self):
		if not self.restful:
			return self.header() + self.result + self.footer()
		return self.result	
	
	def default(self):
		return self.index()
		
	index.exposed = True
	default.exposed = True
