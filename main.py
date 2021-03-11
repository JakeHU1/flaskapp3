from flask import Flask, render_template, request, make_response, session
from flask_pymongo import PyMongo
from authomatic.adapters import WerkzeugAdapter
from authomatic import Authomatic
import authomatic
import logging

from config import CONFIG

# Instantiate Authomatic.
authomatic = Authomatic(CONFIG, 'your secret string', report_errors=False)
app = Flask(__name__, template_folder='.')
app.secret_key = "very secret key"
app.config['MONGO_URI'] = "mongodb+srv://user3:ssANd6vkHlfYU4ze@cluster0.fshnt.mongodb.net/flaskapp?retryWrites=true&w=majority"
mongo = PyMongo(app)
@app.route('/')
def index():
    if session:
        return render_template('dns.html')
    return render_template('index.html', message="Please login")

@app.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    # We need response object for the WerkzeugAdapter.
    response = make_response()
    # Log the user in, pass it the adapter and the provider name.
    result = authomatic.login(WerkzeugAdapter(request, response), provider_name,
    session=session, session_saver=lambda: app.save_session(session, response)
    )
    # If there is no LoginResult object, the login procedure is still pending.
    if result:
        if result.user:
            # We need to update the user to get more info.
            result.user.update()
            session['email'] = result.user.email
            session['username'] = result.user.name
            session['token'] = result.user.id
        # The rest happens inside the template.
        if mongo.db.users.find_one({'email': session['email']}):
            result = mongo.db.users.find_one({'email': session['email']})
            return render_template("dns.html", user=session['username'], fqdns=result['fqdns'])
        else:
            mongo.db.users.insert_one({"username": session['username'], "email": session['email'], "token": session['token']})
            return render_template("dns.html", user=session['username'])

    # Don't forget to return the response.
    return response

@app.route('/logout')
def logout():
    if session:
        session.clear()
        return render_template("index.html", message="Logged out succesfully")
    else:   
        return render_template("index.html", message="You're not logged in")
    


# Run the app on port 5000 on all interfaces, accepting only HTTPS connections
if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc', host='0.0.0.0', port=5000)
