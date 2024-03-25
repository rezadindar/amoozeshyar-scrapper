from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException
import requests
import base64
import time
import os
import signal
import ntpath
import glob
import shutil
from fastapi import FastAPI, Query
from multiprocessing import Pipe
from multiprocessing import Process
import sqlite3
from fastapi.responses import FileResponse
from retry import retry
from selenium.webdriver.chrome.service import Service as Service
#from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import sys
from typing import Union
from typing_extensions import Annotated

db = sqlite3.connect('amoozeshyar.db')
cursor = db.cursor()
config = db.execute("SELECT * from config").fetchone()
db.commit()
db.close()

PATH = os.path.join(os.getcwd(), 'files')
DEBUG = False

if not os.path.exists("files"):
    os.makedirs("files")

def signal_handler(self, sig, frame):
    print("Exiting the program...")
    sys.exit(0)

def solveCaptcha(f):
    with open(f, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('ascii')
        url = 'https://api.apitruecaptcha.org/one/gettext'

        data = {
            'userid': config[5],
            'apikey': config[6],
            'data': encoded_string
        }
        response = requests.post(url=url, json=data)
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


def registerFetchError(status=True):
    db = sqlite3.connect('amoozeshyar.db')
    cursor = db.cursor()
    cursor.execute(
        "UPDATE process_status SET fetchStatus = 'False', fetchError = '%s' WHERE id = 1" % status)
    db.commit()
    db.close()


def runFetchResult(conn1):
    try:
        msg = conn1.recv()
        if msg == 'error':
            print('Ended With Error!')
            registerFetchError()
    except Exception as e:
        print(e)
        registerFetchError()
        print('Ended With Unknown Error!')


app = FastAPI()


@app.on_event("startup")
async def startup_event():
    registerFetchError(False)

    cleanDir("files")


@app.get("/fetch")
def fetch(term: Annotated[Union[str, None], Query(min_length=4, max_length=4, pattern="\d{4}")] = None):
    db = sqlite3.connect('amoozeshyar.db')
    processStatus = db.execute("SELECT * from process_status").fetchone()

    if processStatus[1] == 'False':
        cursor = db.cursor()
        cursor.execute(
            "UPDATE process_status SET fetchError = 'False', fetchStatus = 'fetching' WHERE id = 1")
        db.commit()
        db.close()

        cleanDir("files")

        # create the pipe
        conn1, conn2 = Pipe()
        # create a child process process
        fetchProcess = Process(target=runFetch, args=(conn2, term))
        fetchProcess.start()
        resultProcess = Process(target=runFetchResult, args=(conn1,))
        resultProcess.start()

        result = {
            'status': 'fetchStarted'
        }
    else:
        result = {
            'status': 'fetching'
        }

    return result

@retry(Exception, tries=3, delay=5)
def runFetch(connection, term):
    print('Enter runFetch')
    chrome_options = Options()
    prefs = {
        "download.default_directory": PATH,
        "plugins.plugins_disabled" : ["Chrome PDF Viewer"]
    }
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    #chrome_options.add_argument("--start-maximized")
    #chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.page_load_strategy = 'normal'
    chrome_options.add_experimental_option("prefs", prefs)
    #chrome_options.set_capability("cloud:options", {"name": "test_1"})

    try:
        browser = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(e)
        print('Problem With Browser Start!')
        connection.send('error')
        return False
    
    print('After browser start')

    actions = ActionChains(browser)

    print(browser.title)

    browser.get(config[1])
    assert 'ورود به سيستم' in browser.title

    try:
        elemReady = WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.NAME, "B1")))
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

    try:
        sovleCaptcha = solveCaptcha('captcha.png')
    except:
        print('Captcha Not Solved!')
        connection.send('error')
        return False

    try:
        if DEBUG == False:
            captchaText = sovleCaptcha['result']
        else:
            captchaText = 1234
    except:
        if sovleCaptcha['error_type'] == 'QueryException':
            print('Captcha Credit Is Over!')
            connection.send('error')
            return False

    captchaFiled = browser.find_element(By.NAME, 'jcaptcha')
    captchaFiled.send_keys(captchaText)

    loginButton = browser.find_element(By.NAME, 'B1')
    actions.click(loginButton).perform()

    try:
        print("Testing Login Status!")
        myElem = WebDriverWait(browser, 30, 3).until(EC.any_of(EC.presence_of_element_located((By.CLASS_NAME, "logintime")), EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'خطا')]"))))
    except TimeoutException:
        print("Loading took too much time!")

    if myElem.get_attribute("class") == 'logintime':
        print("After Login Page is ready!")
    elif myElem.get_attribute("class") == 'dijitDialogTitle':
        print('Login Failed!')
        registerFetchError()
        connection.send('error')
        return False

    '''try:
        elemReady = WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "logintime")))
        print("After Login Page is ready!")
    except TimeoutException:
        print("Loading took too much time!")'''

    if term is not None:
        entekhabMenu = browser.find_element(
            By.XPATH, "//*[contains(text(), 'انتخاب')]")

        actions.click(entekhabMenu).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.ID, "saveWorkspace")))
            print("Entekhab Menu is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        termSelect = Select(browser.find_element(By.NAME, "parameter(wsTermRef)"))
        termSelect.select_by_visible_text(term)

        saveWorkspace = browser.find_element(By.ID, 'saveWorkspace')
        actions.click(saveWorkspace).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "logintime")))
            print("After saveWorkspace Page is ready!")
        except TimeoutException:
            print("Loading took too much time!")

    browser.switch_to.frame(browser.find_elements(By.TAG_NAME, "iframe")[0])

    try:
        elemReady = WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "l1")))
        print("Main Menu is ready!")
    except TimeoutException:
        print("Loading took too much time!")

    barnameRiziMenu = browser.find_element(
        By.XPATH, "//*[contains(text(), 'برنامه ريزي آموزشي نيمسال تحصيلي')]")
    actions.click(barnameRiziMenu).perform()

    time.sleep(1)

    for i in range(1, 5):
        if os.path.exists(os.path.join(PATH, str(i) + '.csv')):
            continue

        klasseDarsHa = browser.find_element(
            By.XPATH, "//*[contains(text(), 'كلاس درسها')]")
        actions.click(klasseDarsHa).perform()

        window_after = browser.window_handles[1]
        browser.switch_to.window(window_after)

        try:
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "reporttitle")))
            print("Report Page is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        groupSearch = browser.find_element(
            By.XPATH, "//*[@id='requestForm']/center[1]/fieldset[1]/table/tbody/tr[2]/td[2]/input[1]")
        actions.click(groupSearch).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.XPATH, "//button[@id='submitBtn']")))
            print("Select Groups Popup is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        groupSearchFindBtn = browser.find_element(
            By.XPATH, "//button[@id='submitBtn']")
        actions.click(groupSearchFindBtn).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "datagrid")))
            print("Select Groups List is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        for x in range(1, i):
            try:
                elemReady = WebDriverWait(browser, 30).until(EC.presence_of_element_located(
                    (By.XPATH, '//button[contains(@class, "next")]')))
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
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.NAME, "selectManager")))
            print("Select Groups List Next Page Button is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        time.sleep(1)

        groupSearchSelectManager = browser.find_element(
            By.NAME, "selectManager")
        actions.click(groupSearchSelectManager).perform()

        groupSearchSelectForward = browser.find_element(
            By.XPATH, "//*[@id='formCommands']/tbody/tr/td/span/span")
        actions.click(groupSearchSelectForward).perform()

        try:
            elemReady = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="group"]/option')))
            print("Select Groups Send Result is ready!")
        except TimeoutException:
            print("Loading took too much time!")

        browser.execute_script("window.scrollTo(0,document.body.scrollHeight)")

        reportTypeSelect = Select(browser.find_element(By.ID, "rptName"))
        reportTypeSelect.select_by_value('orgcrsbyclnandplc')  

        reportGenerationSubmitButton = browser.find_element(
            By.XPATH, "//span[contains(@class, 'gradiantButton')]")
        actions.click(reportGenerationSubmitButton).perform()

        print("Start Of Report Generation!")

        try:
            print("Testing Excel Report Creation!")
            myElem = WebDriverWait(browser, 600, 3).until(EC.any_of(EC.presence_of_element_located((By.ID, 'excelBtn')), EC.presence_of_element_located((By.ID, "lblTitle"))))
        except TimeoutException:
            print("Loading took too much time!")

        if myElem.get_attribute("id") == 'excelBtn':
            print("Excel is ready!")
        elif myElem.get_attribute("id") == 'lblTitle':
            print('Report is unavailable')
            registerFetchError()
            connection.send('error')
            return False

        time.sleep(3)

        # browser.get_screenshot_as_file(PATH + '/' + 'test.png')

        excelBtn = browser.find_element(By.ID, "excelBtn")
        actions.click(excelBtn).perform()

        excelFilePathElem = browser.find_element(By.NAME, "hd")
        excelFilePath = excelFilePathElem.get_attribute("value")
        excelFileName = '_' + \
            os.path.splitext(ntpath.basename(excelFilePath))[0] + '.csv'

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

        # obtain parent window handle
        p = browser.window_handles[0]
        # obtain browser tab window
        c = browser.window_handles[1]
        # switch to tab browser
        browser.switch_to.window(c)
        # close browser tab window
        browser.close()
        # switch to parent window
        browser.switch_to.window(p)

        browser.switch_to.frame(
            browser.find_elements(By.TAG_NAME, "iframe")[0])

    browser.close()
    browser.quit()
    registerFetchError(False)

    connection.send('success')
    return True


@app.get("/result")
def main(name=None):
    db = sqlite3.connect('amoozeshyar.db')
    processStatus = db.execute("SELECT * from process_status").fetchone()
    db.close()

    if processStatus[2] == 'False':
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
                    result['links'].append(
                        config[4] + '/dl/?name=' + os.path.basename(filename))
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
    else:
        result = {
            'status': 'error'
        }

        return result


@app.get("/dl/")
async def read_item(name):
    return FileResponse(path='files/'+name, filename=name, media_type='text/csv')


@app.get("/clean-files")
def cleanFiles():
    cleanDir("files")

    registerFetchError(False)

    result = {
        'status': 'ok'
    }

    return result
