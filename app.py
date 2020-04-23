#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 22 17:06:38 2020

@author: murali
"""
from flask import Flask, request, make_response
import json
import requests
import os
from flask_cors import cross_origin
import pandas as pd
import seaborn as sns
import requests 
from bs4 import BeautifulSoup 
import pymongo
from pymongo import MongoClient
import smtplib 
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders


app = Flask(__name__)

# geting and sending response to dialogflow
@app.route('/webhook', methods=['POST'])
@cross_origin()

def webhook():

    req = request.get_json(silent=True, force=True)
    
    res = processRequest(req)

    res = json.dumps(res, indent=4)
    #print(res)
    r = make_response(res)
    
    r.headers['Content-Type'] = 'application/json'
    return r


# processing the request from dialogflow
def processRequest(req):
    
    sessionID=req.get('responseId')
    result = req.get("queryResult")
    user_says=result.get("queryText")  
    parameters = result.get("parameters")
    
    intent = result.get("intent").get('displayName')
    
    if (intent=='cust_details'):
        result = req.get("queryResult")
        user_says=result.get("queryText")
        
        parameters = result.get("parameters")
        cust_name=parameters.get("name")
        
        cust_contact = parameters.get("phone")
        cust_email=parameters.get("email")
	#===============================================WEB-SCRAPPING================================================

        # offical ministry of health website
        url = 'https://www.mohfw.gov.in/' 
        
        # make a GET request to fetch the raw HTML content
        web_content = requests.get(url).content
        
        # parse the html content
        soup = BeautifulSoup(web_content, "html.parser")
        
        # remove any newlines and extra spaces from left and right
        extract_contents = lambda row: [x.text.replace('\n', '') for x in row] 
        
        stats = [] # initialize stats
        all_rows = soup.find_all('tr') # find all table rows 
        
        for row in all_rows: 
            stat = extract_contents(row.find_all('td')) # find all data cells  
            # notice that the data that we require is now a list of length 5
            if len(stat) == 5: 
                stats.append(stat)
        
        # convert the data into a pandas dataframe and then to list for further processing
        new_cols = ["Sr.No", "States/UT","Confirmed","Recovered","Deceased"]
        state_data = pd.DataFrame(data = stats, columns = new_cols)
        state_data1=state_data.drop(['Sr.No'], axis=1)
        state_dic=state_data1.to_dict ("records")
        
        #Converting to list
        state=[state_data.columns.values.tolist()] + state_data.values.tolist()
	
	#=================================================INTERACTION WITH MONGO DB==============================
        
       # Pushing data to database
        from pymongo import MongoClient
        client=MongoClient('mongodb+srv://test:test@cluster0-buydi.mongodb.net/test?retryWrites=true&w=majority')
        mydb=client['covid']
        information=mydb.collection
        information.delete_many({})
        information.insert_many(state_dic)
        users_dic=[{"cust_name":cust_name}, {"cust_email":cust_email},{"cust_contact":cust_contact}]
        mydb=client['users']
        information=mydb.collection
        information.insert_many(users_dic)

	#================================================REPORT GENERATION USING REPORT LAB======================
       
        # Report generation
        fileName = 'report.pdf'
        
        from reportlab.platypus import SimpleDocTemplate
        from reportlab.lib.pagesizes import letter
        
        pdf = SimpleDocTemplate(
            fileName,
            pagesize=letter
        )
        
        
        from reportlab.platypus import Table
        table = Table(state)
        
        # add style
        from reportlab.platypus import TableStyle
        from reportlab.lib import colors
        
        style = TableStyle([
            ('BACKGROUND', (0,0), (4,0), colors.green),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN',(2,0),(-1,-1),'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND',(0,1),(-1,-1),colors.beige),
        ])
        table.setStyle(style)
        
        # 2) Alternate backgroud color
        rowNumb = len(state)
        for i in range(1, rowNumb):
            if i % 2 == 0:
                bc = colors.burlywood
            else:
                bc = colors.beige
            
            ts = TableStyle(
                [('BACKGROUND', (0,i),(-1,i), bc)]
            )
            table.setStyle(ts)
        
        # 3) Add borders
        ts = TableStyle(
            [
            ('BOX',(0,0),(-1,-1),2,colors.black),
            ('LINEBEFORE',(2,1),(2,-1),2,colors.red),
            ('LINEABOVE',(0,2),(-1,2),2,colors.green),
            ('GRID',(0,1),(-1,-1),2,colors.black),
            ]
        )
        table.setStyle(ts)
        # adding date
        from datetime import datetime
        now = datetime.now()
        # dd/mm/YY H:M:S
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        preventive="To prevent the spread of COVID-19:<br /> Clean your hands often. Use soap and water, or an alcohol-based hand rub.<br /> Maintain a safe distance from anyone who is coughing or sneezing.<br /> Don’t touch your eyes, nose or mouth.<br /> Cover your nose and mouth with your bent elbow or a tissue when you cough or sneeze.<br /> Stay home if you feel unwell.<br /> If you have a fever, a cough, and difficulty breathing, seek medical attention. Call in advance.<br /> Follow the directions of your local health authority. "
        from reportlab.lib.styles import getSampleStyleSheet
        sample_style_sheet = getSampleStyleSheet()
        items = []
        from reportlab.platypus import Paragraph
        paragraph_1 = Paragraph("Latest updates on COVID-19 cases in India", sample_style_sheet['Heading2'])
        paragraph_2 = Paragraph("Retrived at: "+ dt_string,sample_style_sheet['BodyText'])
        paragraph_3 = Paragraph(preventive,sample_style_sheet['BodyText'])
        items.append(paragraph_1)
        items.append(paragraph_2)
        items.append(table)
        items.append(paragraph_3)
        pdf.build(items)

	#================================================================SENDING EMAIL=================================================

        #sending email
        
        fromaddr = "pytestchatbot@gmail.com"
        toaddr = cust_email
        
        # instance of MIMEMultipart 
        msg = MIMEMultipart() 
        
        # storing the senders email address 
        msg['From'] = fromaddr 
        
        # storing the receivers email address 
        msg['To'] = toaddr 
        
        # storing the subject 
        msg['Subject'] = "COVID19 Chatbot report"
        
        # string to store the body of the mail 
        body = "Thanks for using COVID19 chat bot. Please find attached latest update on COVID19 cases in India. "
        
        # attach the body with the msg instance 
        msg.attach(MIMEText(body, 'plain')) 
        
        # open the file to be sent 
        filename = "report.pdf"
        attachment = open("report.pdf", "rb") 
        
        # instance of MIMEBase and named as p 
        p = MIMEBase('application', 'octet-stream') 
        
        # To change the payload into encoded form 
        p.set_payload((attachment).read()) 
        
        # encode into base64 
        encoders.encode_base64(p) 
        
        p.add_header('Content-Disposition', "attachment; filename= %s" % filename) 
        
        # attach the instance 'p' to instance 'msg' 
        msg.attach(p) 
        
        # creates SMTP session 
        s = smtplib.SMTP('smtp.gmail.com', 587) 
        
        # start TLS for security 
        s.starttls() 
        
        # Authentication 
        s.login(fromaddr, "<password>") 
        
        # Converts the Multipart msg into a string 
        text = msg.as_string() 
        
        # sending the mail 
        s.sendmail(fromaddr, toaddr, text) 
        
        # terminating the session 
        s.quit() 
        # terminating the session 
        fulfillmentText="Thanks for sharing details, a report has been sent to your email id"
        
        return {
            "fulfillmentText": fulfillmentText
        }
	#=============================================INTENT FOR STAT QUERY============================================
    elif(intent=='stat'):

        state_ut=parameters.get("geo-state")
        
        from pymongo import MongoClient
        from bson.json_util import dumps 
       
        client=MongoClient('mongodb+srv://<name>:<password>@cluster0-buydi.mongodb.net/test?retryWrites=true&w=majority')
        mydb=client['covid']
        information=mydb.collection
        statistics=dumps(information.find({"States/UT":state_ut}).limit(1))
        print(statistics)
        string=statistics[47:]
        string=string.replace('"','')
        string=string.replace(']','')
        string=string.replace('}','')

        return {
            "fulfillmentText": string
        }     
    
if __name__ == '__main__':
    app.run(debug=False)
    
