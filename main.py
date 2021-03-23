from flask import Flask, render_template, request, make_response, session, url_for
from flask_pymongo import PyMongo
from authomatic.adapters import WerkzeugAdapter
from authomatic import Authomatic
import authomatic
import logging
import os
import json
import authomatic
import dbus
import dns.rdataset
import dns.rdtypes.IN.A
import dns.zone
from authomatic import Authomatic
from authomatic.adapters import WerkzeugAdapter
from flask import Flask, make_response, render_template, request, session, url_for, flash, redirect
from flask_pymongo import PyMongo

sysbus = dbus.SystemBus()


# Instantiate Authomatic.
authomatic = Authomatic(CONFIG, 'your secret string', report_errors=False)
app = Flask(__name__, template_folder='./templates')
app.secret_key = "very secret key"
app.config[
    'MONGO_URI'] = "mongodb+srv://user3:ssANd6vkHlfYU4ze@cluster0.fshnt.mongodb.net/flaskapp?retryWrites=true&w=majority"
mongo = PyMongo(app)


@app.route('/')
def index():
    if session:
        result = mongo.db.users.find({'username': session['username']}, {
            '_id': 0, 'fqdns': 1})
        return render_template("dns.html", user=session["username"], message="Welcome back, {}".format(session["username"]), fqdns=[document["fqdns"] for document in result][0], UUID=session['token'])
    return render_template('index.html', message="Please login")


# login / logout routes
@app.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    # We need response object for the WerkzeugAdapter.
    response = make_response()
    # Log the user in, pass it the adapter and the provider name.
    result = authomatic.login(WerkzeugAdapter(request, response), provider_name,
                              session=session, session_saver=lambda: app.save_session(
                                  session, response)
                              )
    # If there is no LoginResult object, the login procedure is still pending.
    if result:
        if result.user:
            if provider_name == "google":
                # We need to update the user to get more info.
                result.user.update()
                session['email'] = result.user.email
                session['username'] = result.user.name
                session['token'] = result.user.id
            elif provider_name == "reddit":
                result.user.update()
                session['username'] = result.user.username
                session['token'] = result.user.id
                session['email'] = result.user.id + "@temp.com"
        # The rest happens inside the template.
        if mongo.db.users.find_one({'email': session['email']}):
            result = mongo.db.users.find_one({'email': session['email']})
            return render_template("dns.html", user=session['username'], message="Welcome back, {}".format(session["username"]), fqdns=result['fqdns'], UUID=session['token'])
        else:
            mongo.db.users.insert_one(
                {"username": session['username'], "email": session['email'], "token": session['token']})
            return render_template("dns.html", message="Welcome back, {}".format(session["username"]), user=session['username'], UUID=session['token'])

    # Don't forget to return the response.
    return response


@app.route('/logout')
def logout():
    if session:
        session.clear()
        return render_template("index.html", message="Logged out succesfully")
    else:
        return render_template("index.html", message="You're not logged in")


# new record, delete record and edit record routes
@app.route('/new_record', methods=['POST'])
def new_record():
    hostname = request.form['new_record']
    ip_adres = request.form['ip_new_record']
    try:
        append(ip_adres, hostname, session['token'])
        flash("new record {} added".format(hostname), "success")
    except:
        flash("ip address and/or hostname wrong!", "danger")
    result = mongo.db.users.find(
        {'username': session['username']}, {'_id': 0, 'fqdns': 1})
    return render_template("dns.html", user=session["username"], fqdns=[document["fqdns"] for document in result][0], UUID=session['token'])


@app.route('/delete_record', methods=['POST'])
def delete_record():
    hostname = request.form['delete_record']
    if mongo.db.users.count_documents(
            {'fqdns': hostname, 'username': session['username']}):
        delete(hostname, session['token'])
        flash("record {} deleted".format(hostname), "danger")
        result = mongo.db.users.find(
            {'username': session['username']}, {'_id': 0, 'fqdns': 1})
        return render_template("dns.html", user=session["username"], fqdns=[document["fqdns"] for document in result][0], UUID=session['token'])
    flash("No record found with hostname {}".format(hostname), "warning")
    result = mongo.db.users.find(
        {'username': session['username']}, {'_id': 0, 'fqdns': 1})
    return render_template("dns.html", user=session["username"], fqdns=[document["fqdns"] for document in result][0], UUID=session['token'])


@ app.route('/edit_record', methods=['POST'])
def edit_record():
    old_hostname = request.form['old_hostname']
    if not mongo.db.users.count_documents(
            {'fqdns': old_hostname, 'username': session['username']}):
        flash("No record found with hostname {}, aborting edit.".format(
            old_hostname), "danger")
        result = mongo.db.users.find(
            {'username': session['username']}, {'_id': 0, 'fqdns': 1})
        return render_template("dns.html", user=session["username"], fqdns=[document["fqdns"] for document in result][0], UUID=session['token'])
    new_hostname = request.form['new_hostname']
    new_ip = request.form['new_ip']
    try:
        append(new_ip, new_hostname, session['token'])
        flash("record {} changed to {} with ip {}".format(
            old_hostname, new_hostname, new_ip), "success")
    except:
        flash("ip address and/or hostname malformed, aborting edit.", "danger")
    delete(old_hostname, session['token'])
    result = mongo.db.users.find(
        {'username': session['username']}, {'_id': 0, 'fqdns': 1})
    return render_template("dns.html", user=session["username"], fqdns=[document["fqdns"] for document in result][0], UUID=session['token'])


# CRUD routes
@ app.route('/dns/append/<ip_adres>/<hostname>/<UUID>')
def append(ip_adres=None, hostname=None, UUID=None):
    if mongo.db.users.find_one({'token': UUID}):
        systemd1 = sysbus.get_object(
            'org.freedesktop.systemd1', '/org/freedesktop/systemd1')
        manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
        zonefile = '/etc/bind/db.example.com'
        zone = dns.zone.from_file(zonefile, os.path.basename(zonefile))
        rdataset = zone.find_rdataset(hostname, dns.rdatatype.A, create=True)
        rdata = dns.rdtypes.IN.A.A(
            dns.rdataclass.IN, dns.rdatatype.A, ip_adres)
        rdataset.add(rdata, 86400)
        zone.to_file(zonefile)
        manager.RestartUnit('bind9.service', 'fail')
        filter = {'username': session['username']}
        update = {"$push": {"fqdns": hostname}}
        mongo.db.users.update_one(filter, update)
        return {"message": "new A-record with ip {} and hostname {} inserted".format(ip_adres, hostname)}
    else:
        return {"message": "not authorized"}


@ app.route('/dns/delete/<hostname>/<UUID>')
def delete(hostname=None, UUID=None):
    if mongo.db.users.find_one({'token': UUID}):
        systemd1 = sysbus.get_object(
            'org.freedesktop.systemd1', '/org/freedesktop/systemd1')
        manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
        zonefile = '/etc/bind/db.example.com'
        zone = dns.zone.from_file(zonefile, os.path.basename(zonefile))
        zone.delete_rdataset(hostname, dns.rdatatype.A)
        # restart bind for changes to take effect
        manager.RestartUnit('bind9.service', 'fail')
        zone.to_file(zonefile)
        mongo.db.users.update({'username': session['username']}, {
            '$pull': {'fqdns': hostname}})
        return {"message": "A-record removed hostname {}".format(hostname)}
    else:
        return {"message": "not authorized"}


# Run the app on port 5000 on all interfaces, accepting only HTTPS connections
if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc', host='0.0.0.0', port=5000)