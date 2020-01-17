/** Ajax interaction implemented with Prototype 1.6.
 * 
 * usage example:

	bacon.setNavigationFunction(function (query) {
		var loader = new bacon.Loader(query);
		// The HTML page contains elements whose id are 'plot', 'nav', 'table'
		loader.addImg('plot');
		loader.addHTML('nav');
		loader.addHTML('table');
		loader.loadAll();
	});
	bacon.fixBackButton();
	bacon.navigate();
	
 */

var bacon = function () {
	return {

_current_query: Object(),

fixBackButton: function () {
	setInterval(bacon.checkBackButton, 200);
},

getQuery: function (name) {
	var query = bacon._current_query[name];
	if (query != '__loading__') return query;
},

// Update the page if the user uses the browser history.
checkBackButton: function () {
	var prev = bacon._current_query;
	var query = window.location.hash.substring(1);
	if (query.indexOf('=') == -1) {
		// the query is a string without the 'name=' part
		// not used anymore, but let's try to not break urls
		query = "q=" + query;
	}
	var curr = query.toQueryParams();
	
	for (name in prev) {
		if (curr[name] === undefined) {
			curr[name] = '';
		}
	}
	for (name in curr) {
		if (curr[name] != prev[name] && prev[name] != '__loading__') {
			bacon.navigate(name, query);
		}
	}
},

/** Set the function to be invoked when navigation is required
 *
 * The function shouls have signature f(query)
 */
setNavigationFunction: function (f) {
	bacon._navigate = f;
},

/** Load the objects in the page.
 *
 * What to load with the objects is dictated by the function installed by
 * `setNavigationFunction()`.
 */
navigate: function (name, query) {
	if (undefined === bacon._navigate) {
		alert("no function installed: use setNavigationFunction()");
		return undefiend;
	}
	bacon._current_query[name] = '__loading__';
	if (undefined === query) {
		query = window.location.hash.substring(1);
	}
	if (query.indexOf('=') == -1) {
		// the query is a string without the 'name=' part
		// not used anymore, but let's try to not break urls
		query = "q=" + query;
	}
	return bacon._navigate(name, query);
},

/// Load a coordinated set of page snippets.
Loader: function (name, query) {
	this.name = name;
	this.query = query;
	this.reqs = [];
	this.observers = [];
	return this;
}

// end of module
	}
}();

bacon.Loader.prototype.addHTML = function (url, tgt) {
	if (undefined === tgt) { tgt = $(url); }
	this.reqs.push([url, tgt, this._elementLoaded.bind(this)]);
}

bacon.Loader.prototype.addImg = function (url, tgt) {
	if (undefined === tgt) { tgt = $(url); }
	this.reqs.push([url, tgt, this._imgLoaded.bind(this)]);
}

bacon.Loader.prototype.addObserver = function (url, cb) {
	this.observers.push([url, cb]);
}

bacon.Loader.prototype.loadAll = function () {
	this._hideError();
	this._showThrobber();
	this.loaded = [];

	for (var i = 0, ii = this.reqs.length; i < ii; ++i) {
		this._loadElement.apply(this, this.reqs[i]);
	}
}

/** Signal that one of the snippet has finished.
 *
 * When all the snippets have been loaded, record the current
 * query in the module: this is needed to make the back button
 * work. There is some race condition so if the new query is
 * stored before loading, it may be set before the location.hash
 * has updated, triggering a "back and forth" flash.
 */
bacon.Loader.prototype._urlLoaded = function (url) {
	this.loaded.push(url);
	if (this.loaded.length == this.reqs.length) {
		bacon._current_query[this.name] = this.query.toQueryParams()[this.name] || "";
		this._hideThrobber();
		if (this.failure_response) {
			this._showError(this.failure_response.statusText.toLowerCase());
		}
		else {
			this._hideError();
		}
	}
	
	// fire the user-defined callbacks
	var base_url = url.replace(/\?.*/, '');
	for (var i = 0, ii = this.observers.length; i < ii; ++i) {
		if (this.observers[i][0] == base_url) {
			this.observers[i][1](url);
		}
	}
}

/// Replace `tgt` content with the snippet returned from `url`.
bacon.Loader.prototype._elementLoaded = function  (response, tgt) {
	tgt.update(response.responseText.strip());
/* The navigation links are regular links only changing the location fragment.
 * The checkBackButton poller detects changes to the fragment and triggers a
 * page refresh. The 'nav' elements used to be active, with an event handler
 * intercepting the click and calling navigate(), but this triggered strange
 * reactions when ctrl+clicking to open a page in a new tab. */
}

/// Replace `tgt` content with the img tag returned from `url`.
bacon.Loader.prototype._imgLoaded = function  (response, tgt) {
	var prev_url = tgt.down('img');
	if (prev_url) { prev_url = prev_url.src; }
	
	var tmp = new Element('span');
	tmp.update(response.responseText);
	var new_url = tmp.down('img').src;
	
	if (new_url != prev_url) {
		tgt.update(response.responseText.strip());
	}
}

/// Replace `tgt` content with the snippet returned from `url`.
bacon.Loader.prototype._loadElement = function  (url, tgt, cb) {
	var self = this;
	url += '?' + this.query;
	new Ajax.Request(url, {
		method: 'get',
		onSuccess: function (response) { cb(response, tgt) },
		onFailure: function (response) {
			// Assume stuff failing fail for the same reason.
			self.failure_response = response;
			window.bacon_error_response = response;
		},
		onComplete: function () { self._urlLoaded(url); }
	});
}

bacon.Loader.prototype._showThrobber = function () {
	var e = $('bacon-throbber');
	if (e) { e.up().show(); }
	$$('body')[0].style.cursor = 'wait';
}

bacon.Loader.prototype._hideThrobber = function () {
	var e = $('bacon-throbber');
	if (e) { e.up().hide(); }
	$$('body')[0].style.cursor = '';
}

bacon.Loader.prototype._hideError = function () {
	var e = $('bacon-error');
	if (e) { e.up().hide(); }
}

bacon.Loader.prototype._showError = function (message) {
	var e = $('bacon-error');
	if (e) { e.update("Error: " + message).up().show(); }
}
