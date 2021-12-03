from selenium import webdriver # Opens own webdriver to navigate to the schedule
from webdriver_manager.chrome import ChromeDriverManager # This will install the right chromedriver for each system (I think)
# import chromedriver_binary  # Adds chromedriver binary to path
#! For selenium to work you need to install chrome-beta and replace chrome with it (i.e. change the path of chrome beta to where original chrome was). 
# Other selenium things
from selenium.webdriver.chrome.service import Service # This is used to not use the depricated argument "executable_path"
from selenium.webdriver.chrome.options import Options # I don't even know what this does
from selenium.webdriver.common.by import By # By and EC is needed to not use depricated locating methods
from selenium.webdriver.support import expected_conditions as EC # ^
from selenium.webdriver.support.ui import WebDriverWait # Don't really need, but it's good to have

from bs4 import BeautifulSoup # BS4 is used to read the raw HTML content and find the right buttons/tables
import json # Here only used to output the complete schedule indended
import datetime # date and time would be really usefull to know when working with schedules
from dotenv import load_dotenv # This is used to safely take the username and password from a .env file
from os import getenv # to read the .env file
from sys import exit as Exit

#*========================== DATA EXTRACTION ========================
def extract_cell_data(cell, i): # Gets the data from the cell
    if not cell.get("nowrap") == "nowrap": # if it doesn't have nowrap it is not a significant cell
        return
    data = {
        "row_id": i,    # used later to calculate the overlaps
        "rowspan": 0,   # How much vertical space does the cell take?
        "colspan": 0,   # How much horisontal space does the cell take? #! MAX is 4!
        "info": []      # Will be empty if it is a break, otherwise it will get info like lesson name, teacher, times and room
    }
    if cell.find("span"):
        data["info"] = cell.find("span").encode_contents().decode('UTF-8').replace("\n","").split("<br/>")
    if cell.get("colspan"):
        data["colspan"] = int(cell.get("colspan"))
    if cell.get("rowspan"):
        data["rowspan"] = int(cell.get("rowspan"))
    return data

def return_cells(row, i): # returns only cells which are significant to the schedule
    cells = row.find_all("td", {"class": "schedulecell"}) # Find significant cells in the row (i.e. ignore the time and day cells)
    row_data = []
    if len(cells) >= 1: # If cell has content
        for cell in cells:
            cell_data = extract_cell_data(cell, i) # Extract the data from the cell
            if cell_data: # If there is any data at all, add it to the row
                row_data.append(cell_data)
    return row_data

def getRawData(): # uses selenium to download all the data we need
    chrome_options = Options()
    chrome_options.add_argument("--headless") # this will run the chromedriver invisible

    #* Some variables stored in a .env file

    load_dotenv()
    username = getenv("username")
    password = getenv("password")
    if username == None or password == None:
        print("Write your password and email address in the environment file.")
        with open(".env", "w") as f:
            f.write("username=\npassword=")
        input("exiting...")

        Exit()
    else:
        print("Found username and password in the environment file.")
    url = "https://sms.schoolsoft.se/nti/sso"

    #* open the Driver with the correct page
    # driver = webdriver.Chrome(options=chrome_options)
    print("Starting Selenium...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options) # this finds the right driver for your system
    driver.get(url)

    #* Click through and fill in the form

    username_input = '//*[@id="username"]'
    password_input = '//*[@id="password"]'
    login_button = '/html/body/article/form/div[3]/button'

    print("Logging in...")
    #inputs the username and password
    driver.find_element(By.XPATH, username_input).send_keys(username)
    driver.find_element(By.XPATH, password_input).send_keys(password)
    #presses the login button
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, login_button))).click()

    print("Logged in!")
    print("Searching the schedule...")
    #*: Go to the scedule page and store the schedule in a variable
    schedule_button = '/html/body/div[1]/div/div[2]/div/div/div/a[6]/div'
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, schedule_button))).click()
    # driver.find_element(By.XPATH, schedule_button).click()
    print("Schedule found!")
    soup = BeautifulSoup(driver.page_source, "html.parser") # BS4 object
    print("Exiting selenium.")
    driver.quit()
    raw_rows = soup.find_all("tr",{"class": "schedulerow"}) # The raw data of the schedule (it is the only table on the page)

    schedule_rows = {} #* RAW DATA (doesn't have to be in dict, but it works now so I'm not changing it)
    for i in range(len(raw_rows)):
        row_data = return_cells(raw_rows[i], i)
        schedule_rows[i] = row_data # this is used to index each row {1: row, 2: row, etc...}

    with open("rawdata.json", "w") as f:
        f.write(json.dumps(schedule_rows))
    print("Raw data downloaded.")

    return schedule_rows

#*========================= DECODING ==========================
def get_rowspan_ranges(c1,c2): # c1 and c2 are the cells we are checking rn
    s1 = c1["row_id"] # this is why we needed row_id
    s2 = c2["row_id"]
    e1 = s1 + c1["rowspan"]
    e2 = s2 + c2["rowspan"]
    # s and e stand for when a Cell Starts and when does it End
    return s1, s2, e1, e2

def check_overlap(c1, c2):
    s1, s2, e1, e2 = get_rowspan_ranges(c1,c2)
    return max(e1, e2) - min(s1, s2) < (e1 - s1) + (e2 - s2) 
    # https://stackoverflow.com/a/25369187/12132452

def get_rowspan_remainder(c1, c2): # If the lessons overlap we need to add up the remainder of the rowspan, if exists
    #! c1 MUST be the cell which is already added to the data, c2 is the new one we are checking
    s1, s2, e1, e2 = get_rowspan_ranges(c1,c2)
    if e2 > e1: # if the cell we are checking ends after the cell which is already added...
        return e2 - e1 # add the reminder of these lessons
    else:
        return 0
    # IMPORTATNT TO KNOW, we don't need to check for which cell starts earlier, because the cell which has lower row_id will always be added first.

def add_to_schedule(cell, day, schedule, final_schedule): # Idk, I just added this to not rewrite the if statemenet over and over again.
    if cell["info"]: # don't add the cell to the schedule if it is just a break
        schedule[day].append(cell)

        data = {
            "class": cell["info"][0].replace("\u00e4", "a"),
            "room": cell["info"][2],
            "start": [int(cell["info"][1].split("-")[0].split(":")[0]),int(cell["info"][1].split("-")[0].split(":")[1])],
            "end": [int(cell["info"][1].split("-")[1].split(":")[0]),int(cell["info"][1].split("-")[1].split(":")[1])]
        }
        final_schedule[day].append(data)
    return [schedule, final_schedule]

def convertRawData(schedule_rows = False): # converts the data to a dictionary

    if not schedule_rows:
        with open("rawdata.json", "r") as f:
            schedule_rows = json.load(f)

    schedule = { # this is needed to keep track of recorded days rowspan and colspan
        "Mon": [],
        "Tue": [],
        "Wed": [],
        "Thu": [],
        "Fri": []
    }

    final_schedule = { #* This is the final sorted output
        "Mon": [],
        "Tue": [],
        "Wed": [],
        "Thu": [],
        "Fri": []
    }

    rowspan_sum = { # this is needed to keep track of which day the next lesson/break belongs to
    "Mon": 0,
    "Tue": 0,
    "Wed": 0,
    "Thu": 0,
    "Fri": 0
    }

    for i,row_data in schedule_rows.items(): # Iterating through the RAW data dict
        for cell in row_data: # for each cell in the row...
            #* The day with the least rowspan in rowspan_sum is the one who will get the following lesson
            min_day = min(rowspan_sum, key=rowspan_sum.get) #finds the day with the least rospawn value
            if cell["colspan"] == 4: # If the cell takes up the full width of the day
                r = add_to_schedule(cell, min_day, schedule, final_schedule)
                schedule = r[0] # add this cell to the scedule
                final_schedule = r[1] 
                rowspan_sum[min_day] += cell["rowspan"] # adding that rowspan value to the current min_day
                #* This would have been it, if the school didn't have any overlapping lessons
            else: #! The following code took 2 weeks to develop!
                
                overlap_exists = False # if this remains False, it means it is the first lesson we found that doesn't take up the whole width of the column, thus we should treat it normally
                day = "" # We can't use the current min_day, because the overlaping lessons don't add up the rowspan the same way the normal ones do.
                #So we have got to find the previos lesson which could be overlapp
                for d,row_data in schedule.items(): # We gotta check each cell we have added to the schedule yet.
                    if overlap_exists: # gotta do this cause break only stops one loop
                        break
                    for c in row_data: # c is the cell (which is already in the database) we are comparing to the new cell we just got
                        #! This if statement doesn't work in some cases, but it fits my purposes. (doesn't work with more than 2 overlapping cells)
                        if check_overlap(cell, c) and cell["colspan"] + c["colspan"] == 4: # the sum of colspans have to sum up to 4 and they have to overlap
                            day = d # ok, this is the day we gotta add the new cell to,
                            overlap_exists = True        
                            break
                if overlap_exists: # we have which day to add the cell to from above
                    r = add_to_schedule(cell, day, schedule, final_schedule)
                    schedule = r[0] # add this cell to the scedule
                    final_schedule = r[1] 
                    rowspan_sum[day] += get_rowspan_remainder(c, cell) # we have to add the reminder because otherwise the rowspan will get over the max value. which breaks the whole system
                else: # again, if it doesn't overlap with anything YET, add it as a normal cell
                    r = add_to_schedule(cell, min_day, schedule, final_schedule)
                    schedule = r[0] # add this cell to the scedule
                    final_schedule = r[1] 
                    rowspan_sum[min_day] += cell["rowspan"] # adding that rowspan value to the current min_day
    print("Saved the schedule.")
    return final_schedule

#*=========================== DATA MANIPULATION ========================
def saveData(schedule, use_indent=False): # just saves the completed schedule in a json file
    with open("schedule.json", "w") as f:
        if use_indent:
            f.write(json.dumps(schedule, indent=2))
        else:
            f.write(json.dumps(schedule))

def getSavedData(): # get the raw data from schedule.json (used for debugging)
    with open("schedule.json", "r") as f:
        schedule = json.load(f)
    return schedule

def getTodaysSchedule(schedule):
    weekday = datetime.datetime.now().strftime("%A")
    if not(weekday == "Saturday" or weekday == "Sunday"): #Output nothing if its a weekend
        return schedule[weekday[0:3]]
    return False

def myprint(txt, out): # speciall print function, only allows to print if explicitly said so
    if out: print(txt)
    # I added this because getNextEvent calls the getCurrentEvent, and I don't want getCurrentEvent to print stuff if called inside other functions

def getCurrentEvent(schedule, out=False): # Tells you what is happening on your schedule right now
    now = datetime.datetime.now()
    todaysSchedule = getTodaysSchedule(schedule) # this is a list of all the lessons today

    if not todaysSchedule:
        myprint("It is weekend right now", out)
        return None

    hasALesson = False
    currentLesson = {}
    for lesson in todaysSchedule:
        lessonTimeStart = now.replace(hour=lesson["start"][0], minute=lesson["start"][1], second=0, microsecond=0)
        lessonTimeEnd = now.replace(hour=lesson["end"][0], minute=lesson["end"][1], second=0, microsecond=0)
        if lessonTimeStart <= now and now <= lessonTimeEnd: #https://stackoverflow.com/a/1831453/12132452
            hasALesson = True
            currentLesson = lesson
            break

    if hasALesson:
        myprint(f'You have a {currentLesson["class"]} class in {currentLesson["room"]}, which started at {currentLesson["start"][0]}:{currentLesson["start"][1]} and ends at {currentLesson["end"][0]}:{currentLesson["end"][1]}.', out)
        return currentLesson
    myprint("You have a break right now.", out)
    return None

def getNextEvent(schedule, out=False): # Tells you what is next on your schedule
    now = datetime.datetime.now()
    todaysSchedule = getTodaysSchedule(schedule)

    if not todaysSchedule:
        todaysSchedule = schedule["Mon"]
        now = now.replace(weekday="Monday", hour=0, minute=0, second=0, microsecond=0)

    currentLesson = getCurrentEvent(schedule)
    nextLesson = False
    for lesson in todaysSchedule:
        lessonTimeStart = now.replace(hour=lesson["start"][0], minute=lesson["start"][1], second=0, microsecond=0)
        lessonTimeEnd = now.replace(hour=lesson["end"][0], minute=lesson["end"][1], second=0, microsecond=0)
        if now < lessonTimeStart:
            nextLesson = lesson
            break
    
    if nextLesson:
        myprint(f'You will have a {nextLesson["class"]} class in {nextLesson["room"]}, which starts at {nextLesson["start"][0]}:{nextLesson["start"][1]} and ends at {nextLesson["end"][0]}:{nextLesson["end"][1]}.', out)
        return nextLesson
    myprint("There is nothing else on your schedule.", out)
    return None

def main():
    # getRawData() #*Just download the raw data from Schoolsoft using selenium and save it to rawdata.json
    # saveData(convertRawData(getRawData()), True) #* Download the data like above AND save the sorted schedule in schedule.json
    # saveData(convertRawData(), True) #* Save the sorted schedule in schedule.json from raw data in rawdata.json

    #* this is just showcase function, showing what could you do with this application
    getCurrentEvent(getSavedData(), True)
    getNextEvent(getSavedData(), True)
    pass

main()
input("Press Enter to exit")