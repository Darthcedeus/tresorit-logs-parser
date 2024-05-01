

from Parser import Parser

shared_links = Parser().parseSharedLinks("shared_links_2024.04.23.16.38.csv")

count = 0
for link in shared_links:
    if "Yes" in link.active:
        count = count + 1
        print(link) 
print("number of active links found:", count)