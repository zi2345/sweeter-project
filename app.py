import os
from os.path import join, dirname
from dotenv import load_dotenv


from pymongo import MongoClient
import jwt
from datetime import datetime, timedelta
import hashlib
from flask import Flask, render_template, jsonify, request, url_for, redirect
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["UPLOAD_FOLDER"] = "./static/profile_pics"

SECRET_KEY = "SPARTA"

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

MONGODB_URl = os.environ.get("MONGODB_URl")
DB_NAME = os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URl)
db = client[DB_NAME]

TOKEN_KEY = "mytoken"


@app.route("/", methods=["GET"])
def home():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        user_info = db.user.find_one({"username": payload.get("id")})
        return render_template("index.html", user_info=user_info)
    except jwt.ExpiredSignatureError:
        msg = "Your token has expired"
        return redirect(url_for("login", msg=msg))
    except jwt.exceptions.DecodeError:
        msg = "There was a problem logging you in"
        return redirect(url_for("login", msg=msg))


@app.route("/login", methods=["GET"])
def login():
    msg = request.args.get("msg")
    return render_template("login.html", msg=msg)


@app.route("/user/<username>", methods=["GET"])
def user(username):
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        status = username == payload.get("id")
        user_info = db.user.find_one({"username": username}, {"_id": False})
        return render_template("user.html", user_info=user_info, status=status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/sign_in", methods=["POST"])
def sign_in():
    username_receive = request.form["username_give"]
    password_receive = request.form["password_give"]
    pw_hash = hashlib.sha256(password_receive.encode("utf-8")).hexdigest()
    result = db.user.find_one(
        {
            "username": username_receive,
            "password": pw_hash,
        }
    )
    if result:
        payload = {
            "id": username_receive,
            "exp": datetime.utcnow() + timedelta(seconds=60 * 60 * 24),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify(
            {
                "result": "success",
                "token": token,
            }
        )
    else:
        return jsonify(
            {
                "result": "fail",
                "msg": "We could not find a user with that id/password combination",
            }
        )


@app.route("/sign_up/save", methods=["POST"])
def sign_up():
    username_receive = request.form.get("username_give")
    password_receive = request.form.get("password_give")
    password_hash = hashlib.sha256(password_receive.encode("utf-8")).hexdigest()
    doc = {
        "username": username_receive,
        "password": password_hash,
        "profile_name": username_receive,
        "profile_pic": "",
        "profile_pic_real": "profile_pics/profile_placeholder.jpg",
        "profile_info": "",
    }
    db.user.insert_one(doc)
    return jsonify({"result": "success"})


@app.route("/sign_up/check_dup", methods=["POST"])
def check_dup():
    username_receive = request.form["username_give"]
    exists = bool(db.user.find_one({"username": username_receive}))
    return jsonify({"result": "success", "exists": exists})


@app.route("/update_profile", methods=["POST"])
def update_profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])

        username = payload.get("id")

        name_receive = request.form.get("name_give")
        about_receive = request.form.get("about_give")

        new_doc = {"profile_name": name_receive, "profile_info": about_receive}

        if "file_give" in request.files:
            file = request.files.get("file_give")
            filename = secure_filename(file.filename)
            extension = filename.split(".")[-1]
            file_path = f"profile_pics/{username}.{extension}"
            file.save("./static/" + file_path)
            new_doc["profile_pic"] = filename
            new_doc["profile_pic_real"] = file_path

        db.user.update_one({"username": username}, {"$set": new_doc})

        return jsonify({"result": "success", "msg": "Your profile has been updated"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/posting", methods=["POST"])
def posting():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        user_info = db.user.find_one({"username": payload.get("id")})
        comment_receive = request.form.get("comment_give")
        date_receive = request.form.get("date_give")
        doc = {
            "username": user_info.get("username"),
            "profile_name": user_info.get("profile_name"),
            "profile_pic_real": user_info.get("profile_pic_real"),
            "comment": comment_receive,
            "date": date_receive,
        }
        db.posts.insert_one(doc)
        return jsonify({"result": "success", "msg": "Posting successfull!"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/get_posts", methods=["GET"])
def get_posts():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        username_receive = request.args.get("username_give")
        if username_receive == "":
            posts = list(db.posts.find({}).sort("date", -1).limit(20))
        else:
            posts = list(
                db.posts.find({"username": username_receive}).sort("date", -1).limit(20)
            )

        for post in posts:
            post["_id"] = str(post["_id"])
            post["count_heart"] = db.likes.count_documents(
                {
                    "post_id": post["_id"],
                    "type": "heart",
                }
            )
            post["count_star"] = db.likes.count_documents(
                {
                    "post_id": post["_id"],
                    "type": "heart",
                }
            )
            post["count_thumbs"] = db.likes.count_documents(
                {
                    "post_id": post["_id"],
                    "type": "heart",
                }
            )
            #
            post["heart_by_me"] = bool(
                db.likes.find_one(
                    {
                        "post_id": post["_id"],
                        "type": "heart",
                        "username": payload.get("id"),
                    }
                )
            )
            post["star_by_me"] = bool(
                db.likes.find_one(
                    {
                        "post_id": post["_id"],
                        "type": "star",
                        "username": payload.get("id"),
                    }
                )
            )
            post["thumbsup_by_me"] = bool(
                db.likes.find_one(
                    {
                        "post_id": post["_id"],
                        "type": "thumbsup",
                        "username": payload.get("id"),
                    }
                )
            )
        return jsonify(
            {
                "result": "success",
                "msg": "Successfully fetched all posts",
                "posts": posts,
            }
        )
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/update_like", methods=["POST"])
def update_like():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        user_info = db.user.find_one({"username": payload.get("id")})
        post_id_receive = request.form.get("post_id_give")
        type_receive = request.form.get("type_give")
        action_receive = request.form.get("action_give")
        doc = {
            "post_id": post_id_receive,
            "username": user_info.get("username"),
            "type": type_receive,
        }

        if action_receive == "like":
            db.likes.insert_one(doc)
        else:
            db.likes.delete_one(doc)

        count = db.likes.count_documents(
            {"post_id": post_id_receive, "type": type_receive}
        )

        return jsonify({"result": "success", "msg": "Update!", "count": count})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


@app.route("/secret", methods=["GET"])
def secret():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        user_info = db.user.find_one({"username": payload.get("id")})
        return render_template("secret.html", user_info=user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


if __name__ == "__main__":
    app.run("0.0.0.0", debug=True, port=5000)
