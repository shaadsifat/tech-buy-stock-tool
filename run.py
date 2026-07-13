from waitress import serve

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Tech Buy Stock Tool running at http://127.0.0.1:5000")
    serve(app, host="127.0.0.1", port=5000, threads=4)
