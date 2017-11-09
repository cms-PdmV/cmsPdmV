from flask import Flask, send_from_directory
app = Flask(__name__)

@app.route('/')
def campaigns_html():
    return send_from_directory('HTML', 'maintenance.html')

app.run(host='0.0.0.0', port=443, threaded=True, ssl_context=('/etc/pki/tls/certs/localhost.crt','/etc/pki/tls/private/localhost.key'))