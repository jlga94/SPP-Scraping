from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from contextlib import contextmanager
from selenium.webdriver.support.expected_conditions import staleness_of
import selenium

import cv2
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from time import sleep
import re, time, datetime
from bs4 import BeautifulSoup
import csv, string, sys
import numpy as np

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from os import cpu_count
import os
from pyvirtualdisplay import Display

from selenium.webdriver.common.proxy import *
from urllib.request import Request, urlopen
from fake_useragent import UserAgent
import random

import multiprocessing
from functools import partial

ua = UserAgent() # From here we generate a random user agent
proxies = [] # Will contain proxies [ip, port]

browser = None
url = "https://www.sbs.gob.pe/app/spp/Reporte_Sit_Prev/afil_existe.asp"
columnsData = ['DNI','Nombre','AfiliadoSPPDesde','AFP','AfiliadoAFPDesde','FechaNacimiento','IdentificacionSPP','SituacionActual','TipoComision','FechaDevengueUltimoAporte',
                   'AporteVoluntarioAFP','AporteVoluntarioSinFin','AporteVoluntarioConFin','DateTime','EsAfiliadoSPP']

alphabet = set(string.ascii_lowercase)
alphabet = alphabet.union(set(string.punctuation))


outputFileResults = 'ResultadosScraping_SBS_TOTAL.tsv'
outputFileDNIsToReSearch = 'DnisPendientes_SBS_TOTAL.txt'


with open(outputFileResults,'w') as f:
    file_writer = csv.writer(f, delimiter='\t', lineterminator='\n')
    file_writer.writerow(columnsData)


class BanException(Exception):
    def __init__(self):
        Exception.__init__(self,"IP baneada")


def getProxies():
    # Retrieve latest proxies
    proxies_req = Request('https://www.sslproxies.org/')
    proxies_req.add_header('User-Agent', ua.random)
    proxies_doc = urlopen(proxies_req).read().decode('utf8')


    soup = BeautifulSoup(proxies_doc, 'html.parser')
    proxies_table = soup.find(id='proxylisttable')

    # Save proxies in the array
    for row in proxies_table.tbody.find_all('tr'):
      proxies.append({
        'ip':   row.find_all('td')[0].string,
        'port': row.find_all('td')[1].string
      })


def random_proxy():
    return random.randint(0, len(proxies) - 1)


def wait_for_page_load(browser, timeout=30):
    old_page = browser.find_element_by_tag_name('html')
    yield
    WebDriverWait(browser, timeout).until(
        staleness_of(old_page)
    )

def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def cleanText(text):
    cleanr = re.compile('&.*?;')
    cleantext = re.sub(cleanr, ' ', text)
    return cleantext

def cleanNameText(text):
    text = " ".join(text.split())
    return ''.join(character for character in text if character.isalpha() or character == ' ')

def readFile(filename):
    with open(filename) as f:
        dnis = list(f.read().splitlines())
        #dnis.pop(0)
        return list(sorted(set(dnis)))

def getScreenShotName(dni):
    #Take a Screenshot in the Browser and saves it in a file
    
    filenameScreenShot = 'screenshot_' + dni + '.png'
    return filenameScreenShot

def getCaptchaImages(filenameScreenShot,dni):
    #Crop the Screenshot, to only have the Captcha area

    fileNameCaptcha = 'captcha_' + dni + '.jpg'
    img = cv2.imread(filenameScreenShot, 0)
    crop_img = img[144:144 + 21, 165:165 + 86]
    cv2.imwrite(fileNameCaptcha, crop_img)

    return fileNameCaptcha

def getCaptchaFileName(dni):
    fileNameCaptcha = 'captcha_' + dni + '.png'
    return fileNameCaptcha


def preprocessImage(fileNameCaptcha):
    #Process the Image to make it gray for a better application of Pytesseract

    image = cv2.imread(fileNameCaptcha)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    gray = cv2.bitwise_not(gray)
    
    kernel = np.ones((2, 1), np.uint8)

    img_erosion = cv2.erode(gray, kernel, iterations=1)
    img_dilation = cv2.dilate(img_erosion, kernel, iterations=1)

    cv2.imwrite(fileNameCaptcha, img_dilation)
    return fileNameCaptcha

def decodeNumberInImage(fileNameGrayCaptcha):
    #Detects the number in the image using Pytesseract

    im = Image.open(fileNameGrayCaptcha)
    #enhancer = ImageEnhance.Contrast(im)
    #im = enhancer.enhance(5)
    numberInCaptcha = pytesseract.image_to_string(im, config='--psm 10 --eom 3 -c tessedit_char_whitelist=0123456789')
    return numberInCaptcha.replace(" ", "")

def deleteImagesFiles(dni):
	filenameScreenShot = 'screenshot_' + dni + '.png'
	fileNameCaptcha = 'captcha_' + dni + '.png'
	os.remove(filenameScreenShot)
	os.remove(fileNameCaptcha)

def deleteImagesFiles_v2(dni):
	fileNameCaptcha = 'captcha_' + dni + '.png'
	os.remove(fileNameCaptcha)


def extractAportesVoluntarios(html_source):
    html_cutted = re.findall('Registra Aportes Voluntarios(.*?)I M P O R T A N T E</td>', html_source, flags=re.S)
    if len(html_cutted) > 0:
        html_cutted = html_cutted[0]
        html_table = re.findall('<table(.*?)</table>', html_cutted, flags=re.S)
        html_table = html_table[0]
        html_lines = re.findall('<td (.*?)</td>', html_table, flags=re.S)
        linesCleaned = []
        for line in html_lines:
            lineText = cleanhtml(line).strip()
            lineText = lineText.replace("&#39;", "'")
            lineText = cleanText(lineText).strip()
            lineText += '\n'
            lineText = re.findall('>(.*?)\n', lineText, flags=re.S)[0].strip()
            linesCleaned.append(lineText)

        return linesCleaned

    else:
        print("No hay Aportes Voluntarios")


def getResultsInPage(html_source,results):
    # Extract the Data in the HTML
    soup = BeautifulSoup(html_source, 'lxml')
    relevantData = soup.find_all("td", {"class": "APLI_txtActualizado_Rep"})

    #Puede que el orden de datos cambie, tener cuidado con esto
    for indexRelevantData in range(2,len(relevantData)):
        results[columnsData[indexRelevantData]] = relevantData[indexRelevantData].text.strip()

    name_element = soup.find("td", {"class": "APLI_txtActualizado"}).text.strip()
    results['Nombre'] = cleanNameText(name_element)

    if "Registra Aportes Voluntarios" in html_source:
        print("Hay Aportes Voluntarios")
        linesCleaned = extractAportesVoluntarios(html_source)
        results['AporteVoluntarioAFP'] = linesCleaned[0]
        results['AporteVoluntarioSinFin'] = linesCleaned[1]
        results['AporteVoluntarioConFin'] = linesCleaned[2]

    return results

def haveLettersInCaptcha(numberInCaptcha):
    for letter in numberInCaptcha:
        if letter.lower() in alphabet:
            return True
    return False


def isCaptchaOK(html_source):
    if "imagen no coincide".lower() in html_source.lower():
        return False
    else:
        return True

def isAffiliated(html_source):
    if "No hay resultado".lower() in html_source.lower() or "No se encuentra".lower() in html_source.lower():
        return False
    else:
        #print("Existe Tag y si esta afiliado - solo por si acaso")
        return True


def scrapingOneDocument(browser,dni):
    sleep(random.randint(3, 5))
    browser.get(url)
    delay = 25 #seconds

    try:
        myElem = WebDriverWait(browser, delay).until(EC.presence_of_element_located((By.NAME, 'cmdEnviar')))
    except TimeoutException:
        print("Se excedió el tiempo de espera")
        resultsScrappingTsvFile.close()

    captchaElement = browser.find_element_by_xpath("//img[@alt='This Is CAPTCHA Image']")

    fileNameCaptcha = getCaptchaFileName(dni)

    captchaElement.screenshot(fileNameCaptcha)

    fileNameGrayCaptcha = preprocessImage(fileNameCaptcha)

    numberInCaptcha = decodeNumberInImage(fileNameGrayCaptcha)
    print('DNI: ' + dni + ' - numberInCaptcha: ' + str(numberInCaptcha))

    deleteImagesFiles_v2(dni)

    isCaptchaNumberOk = True
    results = {}

    if numberInCaptcha == '':
        raise BanException()

    if haveLettersInCaptcha(numberInCaptcha):
        print("El Captcha tiene letras: " + str(numberInCaptcha))
        isCaptchaNumberOk = False
        return isCaptchaNumberOk, results
    elif len(numberInCaptcha) != 4:
        print("El Captcha tiene longitud diferente de 4: " + str(numberInCaptcha))
        isCaptchaNumberOk = False
        return isCaptchaNumberOk, results


    # 4. Getting form
    num_doc = browser.find_element_by_id("num_doc")
    strCAPTCHA = browser.find_element_by_id("strCAPTCHA")
    tip_Doc = browser.find_element_by_name("tip_doc")

    # 5. Filling form
    num_doc.send_keys(dni)
    strCAPTCHA.send_keys(numberInCaptcha)
    tip_Doc.send_keys("00")

    # 6. Sending form
    cmdEnviar = browser.find_element_by_name("cmdEnviar")
    cmdEnviar.click()
    #with wait_for_page_load(browser, timeout=15):

    #sleep(5)

    html_source = browser.page_source
    if isCaptchaOK(html_source):
        results['DNI'] = dni
        results['Nombre'] = '-'
        results['AfiliadoSPPDesde'] = '-'
        results['AFP'] = '-'
        results['AfiliadoAFPDesde'] = '-'
        results['FechaNacimiento'] = '-'
        results['IdentificacionSPP'] = '-'
        results['SituacionActual'] = '-'
        results['TipoComision'] = '-'
        results['FechaDevengueUltimoAporte'] = '-'
        results['AporteVoluntarioAFP'] = '-'
        results['AporteVoluntarioSinFin'] = '-'
        results['AporteVoluntarioConFin'] = '-'
        ts = time.time()
        results['DateTime'] = datetime.datetime.fromtimestamp(ts).strftime('%d-%m-%Y %H:%M:%S')

        if isAffiliated(html_source):
            results['EsAfiliadoSPP'] = 'True'
            results = getResultsInPage(html_source, results)
            #results = getResultsInPage(browser, html_source, results)
        else:
            results['EsAfiliadoSPP'] = 'False'

        print(results)

        if results['EsAfiliadoSPP'] == 'True' and results['Nombre'] == '-':
            print("Caso a observar")
            print(html_source)

        elif results['EsAfiliadoSPP'] == 'False' and results['Nombre'] != '-':
            print("Caso a observar")
            print(html_source)

        addRowTsvFile(results)

    else:
        print("No se realizó correctamente el Captcha: " + str(numberInCaptcha))
        isCaptchaNumberOk = False

    return isCaptchaNumberOk,results


def addRowTsvFile(result):
    row = []
    for column in columnsData:
        row.append(result[column])

    with open(outputFileResults, 'a') as f:
        file_writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        file_writer.writerow(row)


def writeTsvFile(resultScrapping,filename):
    with open(filename, 'w') as o:
        file_writer = csv.writer(o, delimiter='\t', lineterminator='\n')
        file_writer.writerow(columnsData)

        for register in resultScrapping:
            row = []
            for column in columnsData:
                row.append(register[column])

            file_writer.writerow(row)

def DNIsToResearch(dnisWithCaptchaError,filename):
    with open(filename, 'w') as f:
        for dni in dnisWithCaptchaError:
            f.write(dni + '\n')

def downloader(dni,proxy):
    print(dni)

    proxy = Proxy({
    'proxyType': ProxyType.MANUAL,
    'httpProxy': proxy['ip'] + ':' + proxy['port'],
    'ftpProxy': proxy['ip'] + ':' + proxy['port'],
    'sslProxy': proxy['ip'] + ':' + proxy['port'],
    'noProxy': '' # set this value as desired
    })

    options = Options()
    options.add_argument("--headless")

    profile = webdriver.FirefoxProfile()
    profile.set_preference("dom.disable_beforeunload", True)

    profile.set_preference("browser.tabs.remote.autostart", False)
    profile.set_preference("browser.tabs.remote.autostart.1", False)
    profile.set_preference("browser.tabs.remote.autostart.2", False)

    profile.set_preference("browser.tabs.remote.force-enable", False)

    try:
        browser = webdriver.Firefox(firefox_options=options,firefox_profile = profile,proxy=proxy)
        browser.set_page_load_timeout(60)

        numTries = 15
        for actualTry in range(numTries):
            print("DNI: " + dni + " - Intento: " + str(actualTry + 1))
            isCaptchaNumberOk, result = scrapingOneDocument(browser, dni)
            if isCaptchaNumberOk:
                browser.quit()
                return dni
            else:
                print("Fallo DNI: " + dni)

        browser.quit()
        with open(outputFileDNIsToReSearch, 'a') as f:
            f.write(dni + '\n')
            return None
    except BanException:
        browser.quit()
        raise BanException()
    except:
        browser.quit()


def processWork(dni):
    if len(proxies) == 0:
        getProxies()

    proxy_index = random_proxy()
    proxy = proxies[proxy_index]
    try:
        downloader(dni,proxy)
    except: # If error, delete this proxy and find another one
        del proxies[proxy_index]
        print('Proxy ' + proxy['ip'] + ':' + proxy['port'] + ' deleted.')
        return None

    return dni



def main():
    filename = 'TOTAL_DNIS_20.txt'
    dnis = readFile(filename)
    #print(dnis)

    #dnis = dnis[10]


    getProxies()

    t0 = time.time()

    #with ThreadPoolExecutor(max_workers=1) as executor:
    #    futures = [executor.submit(downloader, dni) for dni in dnis]


    iterationMultiprocessing = 1
    with multiprocessing.Pool(24) as p:

        print("iterationMultiprocessing: "+ str(iterationMultiprocessing))
        dnisToScrap = dnis[:200]

        dnisScraped = set(p.map(processWork,dnisToScrap))
        if None in dnisScraped:
            dnisScraped.remove(None)

        dnis = list(set(dnis).difference(dnisScraped))

        os.system('pkill firefox')
        os.system('pkill geckodriver')

        sleep((iterationMultiprocessing % 10) * 60)
        iterationMultiprocessing += 1


    t1 = time.time()
    total_time = int(t1 - t0)
    print("Tiempo total de ejecución: " + str(datetime.timedelta(seconds=total_time)))


try:
    display = Display(visible=0, size=(800, 600))
    display.start()
    main()
except:
    print("Unexpected error:", sys.exc_info()[0])
    raise
finally:
    display.stop()
