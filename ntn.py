from ntntools import ntncurl, ntndns, ntnsubnet, ntnping, ntntraceroute, ntnpubip, ntnoui, ntnmodels, ntnwhois, ntnrphash
from ntntools.ntndb import db_session

from datetime import datetime
from flask import Flask, request, render_template, redirect, send_from_directory
from urllib.parse import urlsplit

from ntntools.config import DNS_RECORD_TYPES, DNS_RESOLVER_LIST, DATABASE, DATABASE_KEY

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['FLATPAGES_EXTENSION'] = '.md'
app.config['FLATPAGES_MARKDOWN_EXTENSIONS'] = ['codehilite', 'fenced_code', 'footnotes', 'toc', 'tables']
app.secret_key = DATABASE_KEY

# chrome likes to add trailing slashes to links for some reason
app.url_map.strict_slashes = False


# end database sessions when the application is ended
@app.teardown_appcontext
def shutdown_session(exception = None):
    db_session.remove()


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow(),
            'public_ip': request.environ.get('HTTP_X_REAL_IP', request.remote_addr)}

@app.route('/', methods=['GET', 'POST'])
def tools():
    return render_template('tools/tools.html')

@app.route('/whois', methods=['GET', 'POST'])
def whois():

    if request.method == 'POST':
        
        hostname = request.form['hostname']

        render_buffer = get_whois_results(hostname)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":

            return render_buffer
        
        else:

            return render_template('tools/whois.html',
                                    results = render_buffer,
                                    hostname = hostname)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return render_template('tools/whois_app.html')

    else:

        # handle query strings
        hostname = request.args.get('hostname') or ''

        if hostname != '':

            try:

                render_buffer = get_whois_results(hostname)

            except ValueError:

                render_buffer = ''
        
        else:

            render_buffer = ''

        return render_template('tools/whois.html',
                                results = render_buffer,
                                hostname = hostname)

def get_whois_results(hostname):

    return render_template('tools/whois_results.html',
                            results = ntnwhois.ntnwhois(hostname),
                            hostname = hostname)

@app.route('/dns', methods=['GET', 'POST'])
def dns_check():

    if request.method == 'POST':

        user_url = request.form['url']
        user_resolver = request.form['user_resolver']
        record_type = request.form['record_type']

        render_buffer = get_dns_results(user_url, record_type, user_resolver)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":

            return render_buffer

        else:

            return render_template('tools/dns.html', results = render_buffer, dns_record_types = DNS_RECORD_TYPES,
                                    dns_resolver_list = DNS_RESOLVER_LIST, url = user_url)


    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return render_template('tools/dns_app.html', dns_record_types = DNS_RECORD_TYPES, dns_resolver_list = DNS_RESOLVER_LIST)

    else:

        # handle query strings
        user_url = request.args.get('url') or ''
        record_type = request.args.get('record_type') or 'A'
        user_resolver = request.args.get('user_resolver') or 'All'

        if user_url != '':

            try:

                render_buffer = get_dns_results(user_url, record_type, user_resolver)

            except ValueError:

                render_buffer = ''
        
        else:

            render_buffer = ''

        return render_template('tools/dns.html', dns_record_types = DNS_RECORD_TYPES, dns_resolver_list = DNS_RESOLVER_LIST,
                                url = user_url, record_type = record_type, user_resolver = user_resolver, results = render_buffer)

def get_dns_results(user_url, record_type, user_resolver):

    # input validation is handled by ntndns.py
    return render_template('tools/dns_results.html',
                        dns_results = ntndns.dnslookup(user_url, user_resolver, record_type),
                        url = user_url, record_type = record_type)


@app.route('/curl', methods=['GET', 'POST'])
def curl():

    if request.method == 'POST':

        render_buffer = get_curl_results(request.form['url'], request.form.get('follow_redirects'))

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_buffer
        else:
            return render_template('tools/curl.html', results = render_buffer, url = request.form['url'])

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return render_template('tools/curl_app.html')

    else:

        # handle query strings
        user_url = request.args.get('url') or ''
        follow_redirects = request.args.get('follow_redirects') or 'false'

        if user_url != '':

            render_buffer = get_curl_results(user_url, follow_redirects)

        else:

            render_buffer = ''

        return render_template('tools/curl.html', results = render_buffer, url = user_url)

def get_curl_results(user_url, follow_redirects):

    headers, status_code, elapsed_time = ntncurl.curl(user_url)

    render_buffer = render_template('tools/curl_results.html', headers = headers, status_code = status_code, elapsed_time = elapsed_time, url = user_url)
    
    # follow_redirects may be on or true/false depending on whether the request comes from ajax or directly
    if follow_redirects == 'on' or follow_redirects == 'true':

        counter = 1        

        while status_code == 301 or status_code == 302 or status_code == 303 or status_code == 307 or status_code == 308:
            new_url = headers['location']
            headers, status_code, elapsed_time = ntncurl.curl(headers['location'])
            render_buffer += render_template('tools/curl_results.html', headers = headers, status_code = status_code, elapsed_time = elapsed_time, url = new_url)
            render_buffer += ' Redirect Count {}\n'.format(counter)
            counter += 1

            if counter == 30:

                render_buffer += 'MAX REDIRECTS EXCEEDED'

    return render_buffer

@app.route('/subnet', methods=['GET', 'POST'])
def subnet():

    if request.method == 'POST':

        ip_address = request.form['ip_address']
        subnet_mask = request.form['subnet_mask']
        
        render_buffer = get_subnet_results(ip_address, subnet_mask)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_buffer
        else:
            return render_template('tools/subnet.html', results = render_buffer, ip_address = ip_address, subnet_mask = subnet_mask)
        
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template('tools/subnet_app.html')
    else:

        # handle query strings
        ip_address = request.args.get('ip_address') or ''
        subnet_mask = request.args.get('subnet_mask') or ''

        if ip_address != '':

            render_buffer = get_subnet_results(ip_address, subnet_mask)

        else:

            render_buffer = ''

        return render_template('tools/subnet.html', results = render_buffer, ip_address = ip_address, subnet_mask = subnet_mask)


def get_subnet_results(ip_address, subnet_mask):

    return render_template('tools/subnet_results.html', results = ntnsubnet.subnet(ip_address, subnet_mask),
                                        ip_address = ip_address, subnet_mask = subnet_mask)


@app.route('/oui', methods=['GET', 'POST'])
def oui():

    if request.method == 'POST':

        mac_address = request.form['mac_address']

        render_buffer = get_oui_results(mac_address)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_buffer
        else:
            return render_template('tools/oui.html', results = render_buffer, mac_address = mac_address) 

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template('tools/oui_app.html')
    else:

        # handle query strings
        mac_address = request.args.get('mac_address') or ''
        
        if mac_address != '':

            render_buffer = get_oui_results(mac_address)

        else:

            render_buffer = ''

        return render_template('tools/oui.html', results = render_buffer, mac_address = mac_address)

def get_oui_results(mac_address):

    try:
        render_buffer = render_template('tools/oui_results.html', results = ntnoui.ouilookup(mac_address), mac_address = mac_address)
    except ValueError as e:
        render_buffer = render_template('tools/oui_results.html', error=e)

    return render_buffer


@app.route('/ping', methods=['GET', 'POST'])
def ping():

    if request.method == 'POST':

        hostname = request.form['hostname']

        render_buffer = get_ping_results(hostname)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":

            return render_buffer
        else:
            return render_template('tools/ping.html', results = render_buffer, hostname = hostname)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template('tools/ping_app.html')

    else:

        # handle query strings
        hostname = request.args.get('hostname') or ''
        
        if hostname != '':

            render_buffer = get_ping_results(hostname)

        else:

            render_buffer = ''

        return render_template('tools/ping.html', results = render_buffer, hostname = hostname)


def get_ping_results(hostname):

    return render_template('tools/ping_results.html', results=ntnping.ping(hostname), hostname=hostname)


@app.route('/traceroute', methods=['GET', 'POST'])
def traceroute():
    if request.method == 'POST':

        hostname = request.form['hostname']

        render_buffer = get_traceroute_results(hostname)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_buffer
        else:
            return render_template('tools/traceroute.html', results = render_buffer, hostname = hostname)
            
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template('tools/traceroute_app.html')
    else:

        # handle query strings
        hostname = request.args.get('hostname') or ''
        
        if hostname != '':

            render_buffer = get_traceroute_results(hostname)

        else:

            render_buffer = ''

        return render_template('tools/traceroute.html', results = render_buffer, hostname = hostname)

def get_traceroute_results(hostname):

    return render_template('tools/traceroute_results.html', results=ntntraceroute.traceroute(hostname), hostname=hostname)


@app.route('/rphash', methods=['GET', 'POST'])
def rphash():

    if request.method == 'POST':

        rp_address = request.form['rp_address']
        group = request.form['group']
        mask = request.form['mask']
        
        render_buffer = get_rphash_results(rp_address, group, mask)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_buffer
        else:
            return render_template('tools/rphash.html', results = render_buffer, rp_address = rp_address, group = group, mask = mask)
        
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template('tools/rphash_app.html')
    else:

        # handle query strings
        rp_address = request.args.get('rp_address') or ''
        group = request.args.get('group') or ''
        mask = request.args.get('mask') or ''

        if rp_address != '':

            render_buffer = get_rphash_results(rp_address, group, mask)

        else:

            render_buffer = ''

        return render_template('tools/rphash.html', results = render_buffer, rp_address = rp_address, group = group, mask = mask)


def get_rphash_results(rp_address, group, mask):

    return render_template('tools/rphash_results.html', results = ntnrphash.ntnrphash(rp_address, group, mask),
                                        rp_address = rp_address, group = group, mask = mask)

@app.route('/sitemap.xml')
def sitemap():

    articles = (p for p in pages if 'published' in p.meta)

    sorted_articles = sorted(articles, reverse=True,
                    key=lambda p: p.meta['published'])

    return render_template('sitemap.xml', pages = sorted_articles)

@app.route('/robots.txt')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

@app.errorhandler(404)
def page_not_found(e):

    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host='0.0.0.0')
