import re


filename = "..\\WebScrapers\\instagram\\tags_for_embedding.txt" 
all_data = ""
with open(filename, 'r') as f:
    for line in f:
        all_data += line.split("\t")[0] + " "

re.sub(r"[.,\/!?$%\^&\*;:{}=\-_`~()]", "", all_data)
all_data = all_data.split(" ")