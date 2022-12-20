# Gunicorn configuration
import main

# Retrieve Flask app instance
debug = True
app, _, _ = main.set_app(debug=debug)

if __name__ == '__main__':
    app.run()
