RedditmagViewModel = function(subreddit){
	var self = this;
	self.subreddit = subreddit;
	self.after = "";
	self.afters = [];
	self.over_18 = ko.observable(false);
	self.data = ko.observableArray();
	self.size = ko.observable(260);
	self.load = function(){
		if($.inArray(self.after, self.afters) === -1){
			self.afters.push(self.after);
			$.ajax({
				url: "http://www.reddit.com/r/"+self.subreddit+"/.json",
				data: {after: self.after},
				dataType: "jsonp",
				jsonp : "jsonp",
				jsonpCallback: "rmvm.receive"
			});
        }
	}
	self.receive = function(data){
		for(var i in data.data.children){
			post = ko.mapping.fromJS(data.data.children[i].data);
			post.hover = ko.observable(false);
			post.hoverOn = function(){ this.hover(true) };
			post.hoverOff = function(){ this.hover(false) };
			self.data.push(post);
		}
		if(self.after == ""){
			self.after = data.data.after;
			self.load();
		} else self.after = data.data.after;
		self.resize();
	}
	self.resize = function(){
		var size = 260;
		var width = $("#posts").width();
		while(width % size >= 25) size--;
		self.size(size-2);
	},
	self.showImg = function(data, event){
		$(event.target).addClass("loaded");
	}
	$(window).scroll(function(){
		var documentHeight = $(document).height();
		var scrollPosition = $(window).height() + $(window).scrollTop();
		if(scrollPosition > 0 && documentHeight - 600 <= scrollPosition){
			self.load();
		}
	});
	$(window).resize(function() { self.resize(); });
	$("#top button").click(function(){ $("#subreddits").toggle() });
	self.load();
}
