import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from datetime import datetime
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session['user_id']
    stocks = db.execute("SELECT * FROM stocks WHERE user_id = :user_id ORDER BY symbol ASC", user_id=id)
    user = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
    g_total = 0.0
    for i in range(len(stocks)):
        stock = lookup(stocks[i]['symbol'])
        stocks[i]['name'] = stock['name']
        stocks[i]["curr_price"] = "%.2f"%(stock["price"])
        stocks[i]["curr_total"] = "%.2f"%(float(stock["price"]) * float(stocks[i]["shares"]))
        stocks[i]["profit"] = "%.2f"%(float(stocks[i]["curr_total"]) - float(stocks[i]["total"]))
        g_total += (stocks[i]["total"])
        stocks[i]["total"] = "%.2f"%(stocks[i]["total"])

    g_total += float(user[0]["cash"])

    return render_template("index.html", stocks=stocks, cash=usd(user[0]["cash"]), grand_total=usd(g_total))



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'POST':
        if not request.form.get("symbol") or not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology("Invalid data supplied")
        id = session["user_id"]
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock = lookup(symbol)
        if not stock:
            return apology("Stock does not exist")
        totalPrice = stock["price"] * float(shares)
        user = db.execute("SELECT * FROM users WHERE id =:sess_id",sess_id = id)
        cash = float(user[0]["cash"])
        if cash < totalPrice:
            return apology("You do not have enough funds to purchase this stock")

        cashRemaining = cash - totalPrice
        stock_db = db.execute("SELECT * FROM stocks WHERE user_id = :user_id AND symbol = :symbol",user_id=id, symbol=symbol)
        if len(stock_db) == 1:
            new_shares = int(stock_db[0]["shares"]) + int(shares)
            new_total = float(stock_db[0]["total"]) + totalPrice
            new_price = "%.2f"%(new_total / float(new_shares))
            db.execute("UPDATE stocks SET shares = :shares, total = :total, price = :price WHERE user_id = :user_id AND symbol = :symbol",shares=new_shares, total=new_total, price=new_price, user_id=id, symbol=symbol)
        else:
            db.execute("INSERT INTO stocks (user_id, symbol, shares, total, price) VALUES (:user_id, :symbol, :shares, :total, :price)",user_id=id, symbol=symbol, shares=shares, total=totalPrice, price=stock["price"])

        db.execute("UPDATE users SET cash = :cash WHERE id = :sess_id", cash=cashRemaining, sess_id=id)
        db.execute("INSERT INTO history (user_id, action, symbol, shares, price,date) VALUES (:user_id, :action, :symbol, :shares, :price,:date)",user_id=id, action=1, symbol=symbol, shares=shares, price=stock["price"],date=datetime.now())
        flash("Bought!")
        return redirect("/")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    stocks = db.execute("SELECT * FROM history WHERE user_id = :user_id ORDER BY date DESC", user_id=session["user_id"])
    for i in range(len(stocks)):
        stocks[i]["total"] = "%.2f"%(float(stocks[i]["shares"]) * float(stocks[i]["price"]))
    return render_template("history.html", stocks=stocks)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("You are logged in!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    flash("Logged Out!")
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return render_template("quote.html")
        else:
            symbol = lookup(request.form.get("symbol"))
            return render_template("quoted.html",symbol = request.form.get("symbol"),price = usd(lookup(request.form.get("symbol"))["price"]), name = lookup(request.form.get("symbol"))["name"])
    elif request.method == "GET":
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        if not request.form.get('username'):
            return apology("must provide username", 403)
        elif request.form.get('password') != request.form.get('confirmation'):
            return apology("passwords must match",403)

        db.execute("INSERT INTO users(username,hash) VALUES(:username,:hash)",username = request.form.get('username'),hash= generate_password_hash(request.form.get('password')))

        return redirect("/")
    else:
        return render_template('register.html')



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks = db.execute("SELECT * FROM stocks WHERE user_id = :user_id", user_id=session["user_id"])
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology("Invalid data supplied")
        id = session["user_id"]
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stocks = db.execute("SELECT * FROM stocks WHERE user_id = :id AND symbol = :symbol",id=id, symbol=symbol)
        if stocks:
            stocks = stocks[0]
        else:
            return render_template("sell.html")
        user = db.execute("SELECT * FROM users WHERE id = :id", id=id)
        if int(shares) > stocks['shares']:
            return apology("You don't have that many stocks")

        stock = lookup(symbol)
        total_price = float(stock["price"]) * float(shares)

        if int(shares) == stocks['shares']:
            db.execute("DELETE FROM stocks WHERE user_id=:id AND symbol =:symbol",id=id,symbol=symbol)
        else:
            updatedShares = int(stocks['shares']) - int(shares)
            updatedTotal = float(updatedShares) * float(stocks["price"])
            db.execute("UPDATE stocks SET shares = :shares, total = :total WHERE user_id = :id AND symbol = :symbol",shares=updatedShares, total=updatedTotal, id=id, symbol=symbol)
        balance = float(user[0]["cash"]) + total_price
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=balance, id=id)
        db.execute("INSERT INTO history (user_id, action, symbol, shares, price,date) VALUES (:user_id, :action, :symbol, :shares, :price,:date)",user_id=id, action=0, symbol=symbol, shares=shares, price=stock["price"],date=datetime.now())
        flash("Sold " + shares +" shares" +" of" + " " + stock['name'])
        return redirect("/")
    else:
        return render_template("sell.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
