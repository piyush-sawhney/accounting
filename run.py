import webbrowser
import threading
import time
from app import app, db


def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    thread = threading.Thread(target=open_browser)
    thread.daemon = True
    thread.start()

    print("=" * 50)
    print("  GST Invoice Management System")
    print("  Starting at http://127.0.0.1:5000")
    print("=" * 50)

    app.run(debug=False, host="0.0.0.0", port=5000)
