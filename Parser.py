__author__="Humza Ahmad"
"""
Parser to read Tresorit export logs
"""

from SharedLink import SharedLink
import re

class Parser:

    def parseSharedLinks(self, fileName):
        links = []
        try:
            #read all lines from csv file
            with open(fileName) as file:
                fileDataRows = file.readlines()
        
            """
            format for shared links is:
            "Active","Tresor","Creator","Creator Email","Link Target","Password Protected",
            "Open Count","Open Count Limit","Creation Date","Expiration Date","Detailed Access Logs","Email Verification",
            "Download Disabled","Watermark Type","Watermark Position","Email Allow List","Suspension Date",
            "Link ID"
            """

            assert len(fileDataRows) != 0 #there is data in file

            for row in fileDataRows:
                row = re.split(r',(?=")', row)
                assert len(row) == 18 #ensure all columns are present
                row = [i.replace('"', '') for i in row] # remove quote from each element
                if "Tresor" in row[1]:
                    #this is the first row with column names
                    continue
                links.append(SharedLink(*row))

        except AssertionError as e:
            print("file data not correct")
            print(e)
        except Exception as e:
            print("can not read data from file")
            print(e)
        
        return links



    



        