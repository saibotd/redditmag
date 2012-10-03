#!/usr/bin/python

from urllib2 import urlopen, Request, unquote
from urlparse import urljoin
import socket
from lxml import etree
from PIL import Image, ImageOps
import cStringIO
import traceback
import redis
import web
import sys
import json
import resource

rsrc = resource.RLIMIT_STACK
soft, hard = resource.getrlimit(rsrc)
print 'Soft limit starts as  :', soft

resource.setrlimit(rsrc, (32768, hard))

soft, hard = resource.getrlimit(rsrc)
print 'Soft limit changed to :', soft

web.config.debug = False

socket.setdefaulttimeout(25)
r = redis.StrictRedis(host='localhost', port=6379, db=3)
parser = etree.HTMLParser()
thumb_size = 260, 260

urls = (
	'/', 'index',
	'/r/(.*)', 'index',
	'/i/(.*)', 'go',
	'/j/(.*)/(.*)', 'json'
)

app = web.application(urls, globals())
render = web.template.render('templates/')

def get_header(response_info):
	_header = dict(response_info)
	header = {}
	for k in _header:
		header[k.lower()] = _header[k]
	return header

def gen_thumb(base_url, image_url, size):
	request = Request(image_url, headers={'User-Agent' : "Mozilla/5.0"})
	try:
		f = urlopen(request)
		input = cStringIO.StringIO(f.read())
		im = Image.open(input)
		w, h = im.size
		if w < size[0] * 0.65 or h < size[1] * 0.65:
			return False 
		im = ImageOps.fit(im, size, Image.ANTIALIAS)
		output = cStringIO.StringIO()
		im.convert('RGB').save(output, "JPEG", quality=68)
		r.set(base_url, output.getvalue())
		r.expire(base_url, 86400)
		input.close()
		output.close()
		return True
	except Exception, e:
		print image_url
		print traceback.format_exc()
	return False

def scrape(url):
	try:
		request = Request(url, headers={'User-Agent' : "Mozilla/5.0"})
		response = urlopen(request, timeout=8)
	except Exception, e:
		print url
		print traceback.format_exc()
		return False
	header = get_header(response.info())
	if('content-type' not in header) : return False
	if header['content-type'].startswith("image"):
		if gen_thumb(url, url, thumb_size): return True
		else: return False
	elif header['content-type'].startswith("text/html"):
		try:
			tree = etree.parse(cStringIO.StringIO(response.read()), parser)
		except Exception, e:
			print url
			print traceback.format_exc()
			return False
		for img in tree.xpath('.//meta[@property="og:image"]'):
			uri = img.get("content")
			if gen_thumb(url, uri, thumb_size) is True : return True
			
		for img in tree.xpath('.//link[@rel="image_src"]'):
			uri = img.get("href")
			if gen_thumb(url, uri, thumb_size) is True : return True
			if uri.find("imgur") >= 0 and gen_thumb(url, uri + ".jpg", thumb_size) is True : return True
			
		for img in tree.xpath('.//img[@id="img"]'):
			uri = urljoin(response.url, img.get("src"))
			if gen_thumb(url, uri, thumb_size) is True : return True
		
		images = {}
			
		for img in tree.xpath('.//img'):
			if img.get("data-src") is not None:
				uri = urljoin(response.url, img.get("data-src"))
			else:
				uri = urljoin(response.url, img.get("src"))
			if uri not in images:
				try:
					request = Request(uri, headers={'User-Agent' : "Mozilla/5.0"})
					response = urlopen(request, timeout=8)
					header = get_header(response.info())
					if 'content-type' in header and header['content-type'].startswith("image") and 'content-length' in header:
						images[uri] = int(header['content-length'])
				except Exception, e:
					print uri
					print traceback.format_exc()
				
		image_urls = images.items()
		image_urls.sort( key=lambda images:(-images[1],images[0]) )

		for image_url in image_urls:
			if gen_thumb(url, image_url[0], thumb_size): return True
			
		return False
			
	else: return False

class go:
	def GET(self, url):
		web.header('Server', "redditmag.py")
		web.header('ETag', url)
		web.header('Last-Modified', 'Mon, 14 Nov 2011 00:48:45 GMT')
		url = unquote(url)
		if r.exists(url):
			s = r.get(url)
			if s == "none":
				raise web.seeother('/static/noimage.png')
			else:
				r.expire(url, 86400)
				web.header('Content-Length', len(s))
				web.header('Content-Type', 'image/jpeg')
				return s
		else:
			if(url.startswith("http://www.reddit.com/r/")):
				r.set(url, "none")
				r.expire(url, 86400)
				raise web.seeother('/static/noimage.png')
			res = scrape(url)
			if res is True:
				web.header('Content-Type', 'image/jpeg')
				return r.get(url)
			else:
				r.set(url, "none")
				r.expire(url, 3600)
				raise web.seeother('/static/noimage.png')

class index:
	def GET(self, subreddit=None):
		if subreddit == None: raise web.seeother('/r/pics')
		return render.index(subreddit)

class json:
	def GET(self, subreddit, after):
		key = after
		if(after == "") : key = subreddit
		if r.exists(key):
			content = r.get(key)
		else:
			try:
				request = Request("http://www.reddit.com/r/"+subreddit+"/.json?after="+after)
				response = urlopen(request)
			except Exception, e:
				print traceback.format_exc()
				r.set(key, "30 second limit hit (from cache)")
	                        r.expire(key, 30)
				return "30 second limit hit (fresh request)"
			content = response.read()
			r.set(key, content)
			r.expire(key, 120)
		web.header('Content-Length', len(content))
		web.header('Content-Type', 'application/json')
		return content

if __name__ == '__main__' :
	app.run()
