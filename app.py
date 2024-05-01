__author__="Humza Ahmad"
"""
Simple web app to display data from Tresorit export logs
"""

from flask import Flask, request, abort, render_template
from Parser import Parser
import os

app = Flask(__name__)

@app.get('/')
def index():
    return render_template('index.html')

@app.post('/process')
def process():
    try:
        file = request.files["file"]
        #temporarily save file for processing
        file.save(file.filename)

        shared_links = Parser().parseSharedLinks(file.filename)
        active_links = []
        inactive_links = []
        
        for link in shared_links:
            if "Yes" in link.active:
                link.remove_tuples()
                active_links.append(link)
            else:
                link.remove_tuples()
                inactive_links.append(link)
                
        #delete file
        os.remove(file.filename)

        return render_template('index.html', active_links=active_links, inactive_links=inactive_links)
    except Exception as e:
        abort(500, e)
