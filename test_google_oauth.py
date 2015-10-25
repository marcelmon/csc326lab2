import os
from bottle import run, request, route, Bottle, template, redirect
import pickle
import redis

import httplib2

from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import flow_from_clientsecrets
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

import random


r = redis.StrictRedis(host='localhost', port=6379, db=0)

CLIENT_ID = '953955239294-0uadckabahokisa159f6eov9ovq28uer.apps.googleusercontent.com'


CLIENT_SECRET = 'hM88qttdva-L94053HHD79v1'


SCOPE = 'https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/userinfo.email'


REDIRECT_URI = 'http://localhost:8080/redirect'





class User_Object(object):
	"""docstring for User_Object"""
	global Query_Counter

	def __init__(self, credentials, user_document):
		super(User_Object, self).__init__()
		self.credentials = credentials

		self.Query_Counter = Query_Counter()

		self.credentials = credentials

		self.user_document = user_document

		self.signed_in = True

		self.client_cookie_value = random.randint(0, 100000)


def Sign_Out_User(user_object):
	"""This is called when the user clicks the sign out button, no revoke of credentials"""
	user_object.signed_in = False

	user_object.client_cookie_value = -1


def User_Sign_In(database, credentials, user_document):
	"""use the user_document['id'] to see if is a user already in database, otherwise create"""
	pickled_user = database.get(user_document['id'])

	if pickled_user == None:
		user_object = User_Object(credentials, user_document)

	else:	
		user_object = pickle.loads(pickled_user)
		user_object.credentials = credentials
		user_object.user_document = user_document
		self.signed_in = True




def Store_User_Object(database, user_object):
	"""Pickles and stores the user object in the database"""
	if user_object.user_document['id'] == None:
		return False

	database.set(user_object.user_document['id'], pickle.dumps(user_object))
	return True



def Load_User_Object(database, user_id):
	"""Load a user object or return False if not in database for user_id"""
	pickled_user = database.get(user_id)
	if pickled_user == None:
		return -1

	else:	
		user_object = pickle.loads(pickled_user)
		return user_object


class Query_Counter(object):
	"""Object to store the persistent table data including the top_20_queries list
	and the word_count dictionary, and provide interface functions to this data"""

	top_20 = []
	word_count = dict()


	def __init__(self):
		"""initialize data structs"""
		super(Query_Counter, self).__init__()
		self.top_20 = []
		self.word_count = dict()

	def Process_Query_String(self, query_string):
		"""Input query string and return a dictionary of occurence count for each 
		word in the query, process """
		words = query_string.split()
		the_results = self.Increment_The_Counter_Return_Results(words)
		if len(the_results) > 0:
			return the_results
		else:
			return -1

	def Increment_The_Counter_Return_Results(self, words):
		"""take in a list of words and increment """
		results = dict()

		for w in words:
			if w in self.word_count:
				self.word_count[w] += 1

			else:
				self.word_count[w] = 1

			if w in results:
				results[w] += 1

			else:
				results[w] = 1
		return results

	def Bubble_Up_Top_20(self, word):
		"""called on each word in the query occurence disctionary
		places each word in its proper place in the top 20 list, or not at all"""
		length = len(self.top_20)

		index = Get_List_Index(self.top_20, word)

		if index < 0:
			#not in the top 20 list yet
			if length < 20:
				#theres at least one open spot on the list
				self.top_20.append(word)
				index = length
			else:
				if self.word_count[ self.top_20[19] ] < self.word_count[word]:
					#last top 20 has smaller count that word, so insert word at end
					self.top_20[19] = word
					index = 19
				else:
					return


		while index > 0 and self.word_count[self.top_20[index -1]] < self.word_count[word]:
			#go from current word position until it is in 0 positin, swapping with any value with a smaller count 
			self.top_20[index -1], self.top_20[index] = self.top_20[index], self.top_20[index -1]

	def Get_Top_20_Tuples(self):
		"""return a tuple list of the current top_20 of form (word,count)"""
		return_list = []
		for word in self.top_20:
			count = self.word_count[word]
			return_list.append( (word, count) )

		return return_list


@route('/', 'GET')
def home():
	return 'sign in from <a href="/login">HERE'

@route('/login')
def login():
	flow = flow_from_clientsecrets("client_secrets.json", scope='https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/userinfo.email', redirect_uri="http://localhost:8080/redirect")
	uri = flow.step1_get_authorize_url()
	redirect(str(uri)) 


@route('/redirect')
def redirect_page():
	"""This page handles the oauth procedure, if successful, will have a return in http after credentials.authorize(http)
	Check this object after service executed to get name email and the like (email as primary key)
	Display the user info on page by calling the home() function from lab1, passing the user info and store the user object using redis"""

	code = request.query.get('code', '')
	flow = OAuth2WebServerFlow( client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scope=SCOPE, redirect_uri=REDIRECT_URI)
	credentials = flow.step2_exchange(code)
	token = credentials.id_token['sub']


	http = httplib2.Http()
	http = credentials.authorize(http)

	# Get user email
	users_service = build('oauth2', 'v2', http=http)
	user_document = users_service.userinfo().get().execute()


	if Test_Is_Current_User(user_document['id']) == False:
		#is not currently a user (first time), so create the user object and set the required, a query counter will be auto created
		user_object = User_Object(credentials, user_document)


	else:
		#this user has previously signed in so load the user object and make sure to change the credentials and document accordingly
		user_object = pickle.loads(r.get(user_document['id']))

		user_object.credentials = credentials
		user_object.user_document = user_document

	#store the user object back into the database
	r.set(user_document['id'], pickle.dumps(user_object))

	return '<form name="revoke_token" method ="post" action="/revoke_token"><input type="submit" name="sign_out_button" value="revoke_token"/><input type="text" name="user_id" value="%s"/></form>And the email:'%(user_document['id']) + user_document['email']


def Test_Is_Current_User(google_id):
	if r.get(google_id) != None:
		return True
	else:
		return False


def Load_User_Object(google_id):
	user_object = pickle.loads(r.get(google_id))
	return user_object




@route('/revoke_token', method="post")
def revoke_token():
	"""
	"""
	user_id = request.forms.get('user_id')
	
	user_object_string = r.get(user_id)

	user_object = pickle.loads(user_object_string)

	user_object.credentials.revoke(httplib2.Http())

	return 'Token Revoked, Return <a href="/">home</a>'




port = int(os.environ.get('PORT', 8080))
run(host='localhost', port=port, debug=True)



home_template = """
<html>
<style>
.my-icon {
    position: relative;
}
.my-icon > i {
    position: absolute;
    display: inline-block;
    width: 0;
    height: 0;
    line-height: 0;
    border: 1.5em solid #4a608c;
    border-bottom: 1.5em solid #4a608c;
    left: 0em;
    top: 0em;
}
.my-icon > i+i {
    position: absolute;
    display: inline-block;
    width: 0;
    height: 0;
    line-height: 0;
    border: 1.5em solid #1142AA;
    border-top: none;
    border-bottom-right-radius: 1.5em;
    border-bottom-left-radius: 1.5em;
    left: 0em;
    top: 0em;
}
.my-icon > i+i+i {
    position: absolute;
    display: inline-block;
    width: 0;
    height: 0;
    line-height: 0;
    border: 1.5em solid #d9e1f1;
    border-top: none;
    border-bottom-right-radius: 1.5em;
    border-bottom-left-radius: 1.5em;
    left: 0em;
    top: 0em;
}
</style>


	<header>

	</header>

	<body style="background-color:black;color:white">
	<div style=height:200px>
		%if logged_in == False:
		<div style="width:70%"></div>
		<div id="login_stuffs">
			sign in from <a href="/login">HERE</div>
		</div>
		%else:
		<div>user_id: {{user_id}}, user_email: {{user_email}}
		<div>sign out from <a href="/sign_out">HERE</div>
		<form name="revoke_token" method ="post" action="/revoke_token">
			<input type="submit" name="sign_out_button" value="revoke_token"/>
			<input type="text" name="user_id" value={{user_id}}></input>
		</form>
		%end
	</div>

	<div>
		<i class=my-icon style=margin-right:65%;float:right><i></i><i></i><i></i></i>

		<text style=font-size:50px;font-weight:bold;color:lightblue;margin-left:40%;float:left>
			The Bucket
		</text>
	</div>

	<div style=top:100%;position:relative;clear:both;>
		<div align=center>
			<form name="query_form" method="get" action="/">
				<input type="text" name="keywords"></input>
				<input type="submit" name="submit_button" value="Submit"></input>
			</form>
		</div>
	</div>
	<table align=center style=width:600px>

		<tr align=center style=overflow:auto;position:relative>


		%if results != None:

			<td style=vertical-align:top;>
				<text style=font-weight:bold align=center> Search for "{{query_string}}" </text>
				<div>
					<table id="results" name="results" style=width:100%;>
					%for word,count in results:
					<tr>
						<td align=center>
							{{word}}
						</td>
						<td align=center>
							{{count}}
						</td>
					</tr>
					%end
				</table>

				</div>
			</td>

		%end

		%if top_20 != None and len(top_20) > 0:
			
			<td style=vertical-align:top;>
				<text style=font-weight:bold; align=center> Top 20 Results </text>
				<div>
					<table id="history" style=width:100%; name="history">
					%for word,count in top_20:
					<tr>
						<td align=center>
							{{word}}
						</td>
						<td align=center>
							{{count}}
						</td>
					</tr>
					%end
				</table>

				</div>
			</td>
		%end



		</tr>

		
	</table>

	</body>

</html>
"""


#style=float:right;margin-right:45%;

#style=float:left;margin-left:55%;


def Get_List_Index(the_list, word):
	"""Helper function to return index of word in list, else -1 if not in list"""
	for index, list_word in enumerate(the_list):
		if list_word == word:
			#is in list
			return index
	return -1

class Query_Counter(object):
	"""Object to store the persistent table data including the top_20_queries list
	and the word_count dictionary, and provide interface functions to this data"""

	top_20 = []
	word_count = dict()


	def __init__(self):
		"""initialize data structs"""
		super(Query_Counter, self).__init__()
		self.top_20 = []
		self.word_count = dict()

	def Process_Query_String(self, query_string):
		"""Input query string and return a dictinoary of occurence count for each 
		word in the query, process """
		words = query_string.split()
		the_results = self.Increment_The_Counter_Return_Results(words)
		if len(the_results) > 0:
			return the_results
		else:
			return -1

	def Increment_The_Counter_Return_Results(self, words):
		"""take in a list of words and increment """
		results = dict()

		for w in words:
			if w in self.word_count:
				self.word_count[w] += 1

			else:
				self.word_count[w] = 1

			if w in results:
				results[w] += 1

			else:
				results[w] = 1
		return results

	def Bubble_Up_Top_20(self, word):
		"""called on each word in the query occurence disctionary
		places each word in its proper place in the top 20 list, or not at all"""
		length = len(self.top_20)

		index = Get_List_Index(self.top_20, word)

		if index < 0:
			#not in the top 20 list yet
			if length < 20:
				#theres at least one open spot on the list
				self.top_20.append(word)
				index = length
			else:
				if self.word_count[ self.top_20[19] ] < self.word_count[word]:
					#last top 20 has smaller count that word, so insert word at end
					self.top_20[19] = word
					index = 19
				else:
					return


		while index > 0 and self.word_count[self.top_20[index -1]] < self.word_count[word]:
			#go from current word position until it is in 0 positin, swapping with any value with a smaller count 
			self.top_20[index -1], self.top_20[index] = self.top_20[index], self.top_20[index -1]

	def Get_Top_20_Tuples(self):
		"""return a tuple list of the current top_20 of form (word,count)"""
		return_list = []
		for word in self.top_20:
			count = self.word_count[word]
			return_list.append( (word, count) )

		return return_list



@route('/', method='GET')
def home_process():
	"""Check if a query was input and display the front page,
	Required to display an top_20 list that exists"""
	global query_counter

	query = request.query.keywords

	the_submit = request.query.submit_button

	if the_submit != 'Submit':
		#no query string was input as the submit value was not receive
		#just display top_20 list usings template
		top_20_tuples = query_counter.Get_Top_20_Tuples()
		return template(home_template, results=None, top_20=top_20_tuples, query_string=None)

	else:
		#a query was submitted so process it 
		the_results = query_counter.Process_Query_String(query)
		if the_results == -1:

			top_20_tuples = query_counter.Get_Top_20_Tuples()
			return template(home_template, results=None, top_20=top_20_tuples, query_string=None)

		for word in the_results:
			query_counter.Bubble_Up_Top_20(word)
	
	good_results = list(the_results.items())
	top_20_tuples = query_counter.Get_Top_20_Tuples()

	return template(home_template, results=good_results, top_20= top_20_tuples, query_string=query)

#called on startup, create the emtpy data structures
query_counter = Query_Counter()

