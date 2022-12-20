# Gunicorn configuration
from main import set_app

# Retrieve Flask app instance
debug = True
app, _, _ = set_app(debug=debug)

if __name__ == '__main__':
    app.run()
