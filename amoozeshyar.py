from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
import requests, base64, time, os, ntpath, glob, shutil
from fastapi import FastAPI
import multiprocessing
import sqlite3
from fastapi.responses import FileResponse
from retry import retry
from webdriver_manager.chrome import ChromeDriverManager

db = sqlite3.connect('amoozeshyar.db')
cursor = db.cursor()
config = db.execute("SELECT * from config").fetchone()
db.commit()
db.close()

PATH =  os.path.join(os.getcwd(), 'files')

if not os.path.exists("files"):
    os.makedirs("files")

def solve(f):
	with open(f, "rb") as image_file:
		encoded_string = base64.b64encode(image_file.read()).decode('ascii')
		url = 'https://api.apitruecaptcha.org/one/gettext'

		data = { 
            'userid': config[5],
			'apikey': config[6],
			'data':encoded_string
		}
		response = requests.post(url = url, json = data)
		data = response.json()
		return data

def cleanDir(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

def checkIsCsv(filename):
    if filename.endswith(".csv"):
        return True
    else:
        return False

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    db = sqlite3.connect('amoozeshyar.db')
    cursor = db.cursor()
    cursor.execute("UPDATE process_status SET fetchStatus = 'False' WHERE id = 1")
    db.commit()
    db.close()

    cleanDir("files")

@app.get("/fetch")
def fetch():
    db = sqlite3.connect('amoozeshyar.db')
    processStatus = db.execute("SELECT * from process_status").fetchone()

    if processStatus[1] == 'False':
        cursor = db.cursor()
        cursor.execute("UPDATE process_status SET fetchStatus = 'fetching' WHERE id = 1")
        db.commit()
        db.close()

        cleanDir("files")

        process = multiprocessing.Process(target=runFetch)
        process.start()

        result = {
            'status': 'fetchStarted'
        }
    else:
        result = {
            'status': 'fetching'
        }

    return result

@retry(Exception, tries=3, delay=3)
def runFetch():
    chrome_options = Options()
    prefs = {
        "download.default_directory" : PATH,
        #"download.open_pdf_in_system_reader": False,
        #"download.prompt_for_download": True,
        #"download_restrictions": 3,
        #"plugins.always_open_pdf_externally": False,
        #"plugins.plugins_disabled" : ["Chrome PDF Viewer"]
    }
    chrome_options.add_argument('--headless=chrome')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.page_load_strategy = 'eager'
    chrome_options.add_experimental_option("prefs", prefs)
    browser = webdriver.Chrome(ChromeDriverManager(version=config[7]).install(), chrome_options=chrome_options)
    actions = ActionChains(browser)

    browser.get(config[1])
    assert 'ورود به سيستم' in browser.title

    try:
        elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.NAME, "B1")))
        print("Login Page is ready!")
    except TimeoutException:
        print("Loading took too much time!")

    username = browser.find_element(By.NAME, 'j_username')
    username.send_keys(config[2])

    captchaImage = browser.find_element(By.ID, 'captchaimg')

    password = browser.find_element(By.NAME, 'temp_j_password')
    password.send_keys(config[3])

    with open('captcha.png', 'wb') as file:
        file.write(captchaImage.screenshot_as_png)

    captchaText = solve('captcha.png')['result']

    captchaFiled = browser.find_element(By.NAME, 'jcaptcha')
    captchaFiled.send_keys(captchaText)

    loginButton = browser.find_element(By.NAME, 'B1')
    actions.click(loginButton).perform()

    try:
        elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "logintime")))
        print("After Login Page is ready!")
    except TimeoutException:
        print("Loading took too much time!")

    browser.switch_to.frame(browser.find_elements(By.TAG_NAME, "iframe")[0])

    try:
        elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "l1")))
        print("Main Menu is ready!")
    except TimeoutException:
        print("Loading took too much time!")

    barnameRiziMenu = browser.find_element(By.XPATH, "//*[contains(text(), 'برنامه ريزي آموزشي نيمسال تحصيلي')]")
    actions.click(barnameRiziMenu).perform()

    time.sleep(1)

    for i in range(1, 5):
        if os.path.exists(os.path.join(PATH, str(i) + '.csv')):
            continue

        klasseDarsHa = browser.find_element(By.XPATH, "//*[contains(text(), 'كلاس درسها')]")
        actions.click(klasseDarsHa).perform()

        window_after = browser.window_handles[1]
        browser.switch_to.window(window_after)

        try:
            elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "reporttitle")))
            print("Report Page is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        groupSearch = browser.find_element(By.XPATH, "//*[@id='requestForm']/center[1]/fieldset[1]/table/tbody/tr[2]/td[2]/input[1]")
        actions.click(groupSearch).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.XPATH, "//button[@id='submitBtn']")))
            print("Select Groups Popup is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        groupSearchFindBtn = browser.find_element(By.XPATH, "//button[@id='submitBtn']")
        actions.click(groupSearchFindBtn).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "datagrid")))
            print("Select Groups List is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        for x in range(1, i):
            try:
                elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.XPATH, '//button[contains(@class, "next")]')))
                print("Select Groups List Next Page Button is ready!")
            except TimeoutException:
                print("Loading took too much time!")
            
            groupSearchSelectManager = browser.find_element(By.ID, "nextPage")
            actions.click(groupSearchSelectManager).perform()

            time.sleep(3)

            '''try:
                elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "datagrid")))
                print("Select Groups List is ready!")
            except TimeoutException:
                print("Loading took too much time!")'''

            '''try:
                elemReady = WebDriverWait(browser, 30).until(EC.text_to_be_present_in_element_value((By.NAME, "pageNumber"), str(i)))
                print("Select Groups List Next Page is ready!")
            except TimeoutException:
                print("Loading took too much time!")'''

        try:
            elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.NAME, "selectManager")))
            print("Select Groups List Next Page Button is ready!")
        except TimeoutException:
            print("Loading took too much time!")
        
        time.sleep(1)
        
        groupSearchSelectManager = browser.find_element(By.NAME, "selectManager")
        actions.click(groupSearchSelectManager).perform()

        groupSearchSelectForward = browser.find_element(By.XPATH, "//*[@id='formCommands']/tbody/tr/td/span/span")
        actions.click(groupSearchSelectForward).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.XPATH, '//*[@id="group"]/option')))
            print("Select Groups Send Result is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        browser.execute_script("window.scrollTo(0,document.body.scrollHeight)")
        groupSearchSubmitButton = browser.find_element(By.XPATH, "//span[contains(@class, 'gradiantButton')]")
        actions.click(groupSearchSubmitButton).perform()

        print("Start Of Report Generation!")

        try:
            myElem = WebDriverWait(browser, 600).until(EC.presence_of_element_located((By.ID, 'excelBtn')))
            print("Excel is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        time.sleep(3)

        #browser.get_screenshot_as_file(PATH + '/' + 'test.png')

        excelBtn = browser.find_element(By.ID, "excelBtn")
        actions.click(excelBtn).perform()

        excelFilePathElem = browser.find_element(By.NAME, "hd")
        excelFilePath = excelFilePathElem.get_attribute("value")
        excelFileName = '_' + os.path.splitext(ntpath.basename(excelFilePath))[0] + '.csv'

        while not os.path.exists(os.path.join(PATH, excelFileName)):
            time.sleep(3)

        # get list of files that matches pattern
        pattern = os.path.join(PATH, '*.csv')
        files = list(filter(checkIsCsv, glob.glob(pattern)))

        # sort by modified time
        files.sort(key=lambda x: os.path.getmtime(x))

        # get last item in list
        lastfile = files[-1]

        shutil.move(lastfile, os.path.join(PATH, str(i) + ".csv"))

        #obtain parent window handle
        p = browser.window_handles[0]
        #obtain browser tab window
        c = browser.window_handles[1]
        #switch to tab browser
        browser.switch_to.window(c)
        #close browser tab window
        browser.close()
        #switch to parent window
        browser.switch_to.window(p)

        browser.switch_to.frame(browser.find_elements(By.TAG_NAME, "iframe")[0])

    db = sqlite3.connect('amoozeshyar.db')
    cursor = db.cursor()
    cursor.execute("UPDATE process_status SET fetchStatus = 'False' WHERE id = 1")
    db.commit()
    db.close()
    browser.quit()

@app.get("/result")
def main(name = None):
    db = sqlite3.connect('amoozeshyar.db')
    processStatus = db.execute("SELECT * from process_status").fetchone()
    db.close()

    if processStatus[1] == 'False':
        # get list of files that matches pattern
        pattern = os.path.join(PATH, '*.csv')
        files = list(filter(checkIsCsv, glob.glob(pattern)))

        if len(files) == 4:
            result = {
                'status': 'ok',
                'links': []
            }

            for filename in files:
                    result['links'].append(config[4] + '/dl/?name=' + os.path.basename(filename))
        else:
            result = {
                'status': 'nok'
            }

        return result
    else:
        result = {
            'status': 'fetching'
        }

        return result
@app.get("/dl/")
async def read_item(name):
    return FileResponse(path='files/'+name, filename=name, media_type='text/csv')

@app.get("/clean-files")
def cleanFiles():
    cleanDir("files")
    
    db = sqlite3.connect('amoozeshyar.db')
    cursor = db.cursor()
    cursor.execute("UPDATE process_status SET fetchStatus = 'False' WHERE id = 1")
    db.commit()
    db.close()

    result = {
        'status': 'ok'
    }

    return result