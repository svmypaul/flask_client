# importing required classes 
from PyPDF2 import PdfReader

# creating a pdf reader object 
reader = PdfReader("resume1.pdf") 

# printing number of pages in pdf file 
print(len(reader.pages)) 

# creating a page object 
page = reader.pages[0] 

# extracting text from page 
text = page.extract_text()

# # saving extracted text into a text file with UTF-8 encoding
# with open("extracted_text.txt", "w", encoding="utf-8") as text_file:
#     text_file.write(text)

# print("Text extracted and saved into 'extracted_text.txt' file.")


from openai import OpenAI
client = OpenAI()

def extract_text(text_input):
    message_content = text_input.choices[0].message.content

    # Replace '\n' with a space
    message_content_without_newlines = message_content.replace('\n', ' ')

    # Now you can print or use the modified content
    return(message_content_without_newlines)


question = f"{text} find name, skills, phone no and email id"
completion = client.chat.completions.create(
  model="gpt-3.5-turbo",
  messages=[
    {"role": "user", "content": f"{question}"}
  ]
)
extract_text(completion)