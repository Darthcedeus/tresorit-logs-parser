

from Parser import Parser

shared_links = Parser().parseSharedLinks("../../shared_links_2025.07.09.21.39.csv")

count = 0
for link in shared_links:
    if "Yes" in link.active:
        count = count + 1
        print(link) 
print("number of active links found:", count)