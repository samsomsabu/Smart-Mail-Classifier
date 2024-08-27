import streamlit as st
from dotenv import load_dotenv
import os
import imaplib
import email
from email.header import decode_header
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from datetime import datetime
from streamlit_option_menu import option_menu
import base64

# Load environment variables
load_dotenv()
api_key = os.getenv('groq_api_key')

# Initialize the Groq model
model = ChatGroq(api_key="groq_api_key", model_name='llama3-8b-8192')
parser = StrOutputParser()

# IMAP email retrieval
def fetch_latest_emails(username, password, num_emails=5):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(username, password)
    mail.select("inbox")
    status, messages = mail.search(None, "ALL")
    email_ids = messages[0].split()[-num_emails:]

    emails = []
    for email_id in email_ids:
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")
        from_ = msg.get("From")
        date_ = msg.get("Date")
        body = ""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                try:
                    body = part.get_payload(decode=True).decode()
                except:
                    pass
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    break
                elif "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(filename)
        else:
            content_type = msg.get_content_type()
            body = msg.get_payload(decode=True).decode()

        emails.append({
            "id": email_id.decode(),
            "subject": subject,
            "from": from_,
            "date": date_,
            "body": body,
            "attachments": attachments
        })
    mail.close()
    mail.logout()
    return emails

def classify_email(subject, from_, date_, body, attachments):
    template = """
As an expert in email analysis, classify the following email based on its content. Provide the results in a table format with the following structure:

| Category            | Classification  | Score   | Reason                                                                                             |
|---------------------|------------------|---------|----------------------------------------------------------------------------------------------------|
| Spam Classification | [Spam/Not Spam]  | [Spam Score]  | [Provide the reason for the classification]                                                        |
| Phishing Attempt    | [Phishing/Not Phishing] | [Phishing Score]  | [Provide the reason for the classification]                                                        |
| Sentiment Analysis  | [Positive/Negative/Neutral] | [N/A]  | [Provide the reason for the sentiment classification]                                               |

In addition to the table, provide a brief summary of the email content separately.

Here are the details of the email to classify:

- **Subject:** {subject}
- **From:** {from_}
- **Date:** {date_}
- **Body:** {body}
- **Attachments:** {attachments}
"""
    prompt = PromptTemplate.from_template(template=template)
    chain = prompt | model | parser

    email_content = {
        "subject": subject,
        "from_": from_,
        "date_": date_,
        "body": body,
        "attachments": ", ".join(attachments) if attachments else "None"
    }

    result = chain.invoke(email_content)
    return result

def format_email_result(result):
    # Check if the result indicates spam
    spam_classification = "Spam Classification" in result
    return "Spam" if spam_classification else "Not Spam"

# Streamlit
# Placeholder for session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_history" not in st.session_state:
    st.session_state.user_history = []
if "emails" not in st.session_state:
    st.session_state.emails = []

@st.cache_data
def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

login_img_base64 = get_img_as_base64("login.jpg")
background_img_base64 = get_img_as_base64("login.jpg")

page_bg_img = f"""
<style>
[data-testid="stAppViewContainer"] > .main {{
background-image: url("data:image/jpeg;base64,{background_img_base64}");
background-size: 100%;
background-repeat: no-repeat;
background-position: right;
}}

[data-testid="stSidebar"] > div:first-child {{
background-image: url("data:image/jpeg;base64,{login_img_base64}");
background-position: center; 
background-repeat: no-repeat;
background-attachment: fixed;
}}

[data-testid="stHeader"] {{
background: rgba(0,0,0,0);
}}

[data-testid="stToolbar"] {{
right: 2rem;
}}
</style>
"""

st.markdown(page_bg_img, unsafe_allow_html=True)

def login_page():
    st.title("Login")
    placeholder = st.empty()
    with placeholder.form(key="login_form"):
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        username = st.text_input("Email:")
        password = st.text_input("Email App Password:", type="password")
        st.markdown('<div class="center">', unsafe_allow_html=True)
        submit = st.form_submit_button("Submit")
        st.markdown('</div>', unsafe_allow_html=True)

    if submit:
        if username and password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            st.success("Logged in successfully!")
        else:
            st.error("Invalid username or password")

def homepage():
    st.title("SpamShield")
    
    if st.session_state.authenticated:
        num_emails_option = st.selectbox("Number of emails to fetch:", options=[5, 10, 50, 100, "All"])
        num_emails = None if num_emails_option == "All" else num_emails_option
        
        if st.button("Fetch Emails"):
            with st.spinner("Fetching the latest emails..."):
                try:
                    st.session_state.emails = fetch_latest_emails(st.session_state.username, st.session_state.password, num_emails)
                    st.success("Emails fetched successfully!")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        
        if st.session_state.emails:
            email_options = [f"{email['from']} ({email['id']})" for email in st.session_state.emails]
            selected_email_option = st.selectbox("Select an email to classify:", email_options)
            
            if selected_email_option:
                selected_email_id = selected_email_option.split(" (")[1][:-1]  # Extract the email ID from the option
                selected_email = next(email for email in st.session_state.emails if email["id"] == selected_email_id)
                
                subject = selected_email["subject"]
                from_ = selected_email["from"]
                date_ = selected_email["date"]
                body = selected_email["body"]
                attachments = selected_email["attachments"]
                
                classification_result = classify_email(subject, from_, date_, body, attachments)
                
                # Determine if the email is spam
                is_spam = format_email_result(classification_result)
                
                # Save to history
                st.session_state.user_history.append({
                    "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "subject": subject,
                    "from": from_,
                    "date": date_,
                    "body": body,
                    "result": classification_result
                })
                
                st.write(f"**Subject:** {subject}")
                st.write(f"**From:** {from_}")
                st.write(f"**Date:** {date_}")
                
                # Use expander to show email body
                with st.expander("More..."):
                    st.write(f"**Body:** {body}")
                st.write(f"**Attachments:** {', '.join(attachments) if attachments else 'None'}")
                
                # Highlight spam emails in red
                if is_spam == "Spam":
                    st.markdown('<div style="color: white;"><h3>Classification Result</h3></div>', unsafe_allow_html=True)
                else:
                    st.write("**Classification Result**")
                    
                st.write(classification_result)
    else:
        st.error("Please log in to fetch and classify emails.")

def user_profile_page():
    st.title("User Profile")
    if st.session_state.authenticated:
        st.write(f"Logged in as: {st.session_state.username}")
    else:
        st.error("Please log in to view your profile.")

def history_page():
    st.title("History")
    if st.session_state.authenticated:
        if st.session_state.user_history:
            for record in st.session_state.user_history:
                st.write(f"**Date and Time:** {record['datetime']}")
                st.write(f"**Subject:** {record['subject']}")
                st.write(f"**From:** {record['from']}")
                st.write(f"**Date:** {record['date']}")
                st.write(f"**Body:** {record['body']}")
                st.write(f"**Result:** {record['result']}")
                st.write("---")
        else:
            st.write("No history available.")
    else:
        st.error("Please log in to view your history.")

def about_us_page():
    st.title("SpamShield")
    st.write("""
# Welcome to SpamShield

Our innovative app is designed to enhance your email experience by keeping your inbox safe and organized. It seamlessly integrates with Gmail to classify your emails into categories such as **Spam**, **Phishing**, and provides **Sentiment Analysis**. Additionally, it offers a concise summary of each email, ensuring you stay informed and protected.

## Meet the Team
- **Aleena Varghese**
- **Samson Sabu**
- **Steffi Angel**

## Our Mission

We aim to provide a reliable tool that helps you manage your emails effortlessly, protect your personal information, and gain valuable insights into the nature of your communications. We are committed to leveraging cutting-edge technology to improve your digital experience.

Thank you for choosing our app. We hope it makes your email management simpler and more secure.

For any inquiries or feedback, feel free to reach out to us.
""")

def main():
    selected = option_menu(
        menu_title=None,  
        options=["Home", "Login", "Profile", "History", "About Us"],
        icons=['house', 'envelope', 'person', 'clock', 'info-circle'],
        menu_icon="cast", default_index=0,
        orientation="horizontal",
        styles={
         "container": {"padding": "0!important", "background-color": "black"},
        "icon": {"color": "white", "font-size": "16px"}, 
        "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "--hover-color": "red"},
        "nav-link-selected": {"background-color": "blue"},
        },
    )

    if selected == "Login":
        login_page()
    elif selected == "Profile":
        user_profile_page()
    elif selected == "History":
        history_page()
    elif selected == "About Us":
        about_us_page()
    else:
        homepage()

if __name__ == "__main__":
    main()
