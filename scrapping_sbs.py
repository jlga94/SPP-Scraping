from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import cv2
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from time import sleep
import re, time, datetime
from bs4 import BeautifulSoup
import csv, string

browser = None
url = "https://www.sbs.gob.pe/app/spp/Reporte_Sit_Prev/afil_existe.asp"
columnsData = ['DNI','Nombre','AfiliadoSPPDesde','AFP','AfiliadoAFPDesde','FechaNacimiento','IdentificacionSPP','SituacionActual','TipoComision','FechaDevengueUltimoAporte',
                   'AporteVoluntarioAFP','AporteVoluntarioSinFin','AporteVoluntarioConFin','DateTime','EsAfiliadoSPP']

alphabet = set(string.ascii_lowercase)
alphabet = alphabet.union(set(string.punctuation))

def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def cleanText(text):
    cleanr = re.compile('&.*?;')
    cleantext = re.sub(cleanr, ' ', text)
    return cleantext

def readFile(filename):
    with open(filename) as f:
        dnis = list(f.read().splitlines())
        dnis.pop(0)
        return dnis

def getScreenShot(browser,dni):

    filenameScreenShot = 'screenshot_'+ dni+'.png'
    browser.save_screenshot(filenameScreenShot)
    return filenameScreenShot

def getCaptchaImages(filenameScreenShot,dni):
    fileNameCaptchaA = 'captchaA_' + dni + '.jpg'

    img = cv2.imread(filenameScreenShot, 0)

    crop_img = img[144:144 + 21, 165:165 + 86]

    cv2.imwrite(fileNameCaptchaA, crop_img)

    return fileNameCaptchaA

def preprocessImage(fileNameCaptcha):
    fileNameCaptchaSplitted = fileNameCaptcha.split('.')
    fileNameGrayCaptcha = fileNameCaptchaSplitted[0] + '_Gray.' + fileNameCaptchaSplitted[1]
    image = cv2.imread(fileNameCaptcha)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    cv2.imwrite(fileNameGrayCaptcha, gray)
    return fileNameGrayCaptcha

def decodeNumberInImage(fileNameGrayCaptcha):
    im = Image.open(fileNameGrayCaptcha)
    enhancer = ImageEnhance.Contrast(im)
    im = enhancer.enhance(50)
    numberInCaptcha = pytesseract.image_to_string(im, config='0123456789')
    return numberInCaptcha.replace(" ", "")

def extractAportesVoluntarios(html_source):
    html_cutted = re.findall('Registra Aportes Voluntarios(.*?)I M P O R T A N T E</td>', html_source, flags=re.S)
    if len(html_cutted) > 0:
        html_cutted = html_cutted[0]
        html_table = re.findall('<table(.*?)</table>', html_cutted, flags=re.S)
        html_table = html_table[0]
        html_lines = re.findall('<td width(.*?)</td>', html_table, flags=re.S)
        linesCleaned = []
        for line in html_lines:
            lineText = cleanhtml(line).strip()
            lineText = lineText.replace("&#39;", "'")
            lineText = cleanText(lineText).strip()
            linesCleaned.append(lineText)

        return linesCleaned


    else:
        print("No hay Aportes Voluntarios")


def getResultsInPage(browser,html_source,results):
    # 7. Getting result
    relevantData = browser.find_elements_by_class_name('APLI_txtActualizado_Rep')

    #Puede que el orden de datos cambie, tener cuidado con esto
    for indexRelevantData in range(2,len(relevantData)):
        results[columnsData[indexRelevantData]] = relevantData[indexRelevantData].text

    for x in browser.find_elements_by_class_name('APLI_txtActualizado'):
        results['Nombre'] = x.text.strip()

    if "Registra Aportes Voluntarios".lower() in html_source:
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

    '''
    captchaBlockTextList = re.findall('<td class="APLI_subtitulo2"(.*?)</td>', html_source, flags=re.S)

    if len(captchaBlockTextList) == 0:
        return True
    else:
        textInBlock = captchaBlockTextList[0]
        if "imagen no coincide".lower() in textInBlock.lower():
            return False
        else:
            return True
    '''

def isAffiliated(html_source):
    if "No hay resultado".lower() in html_source.lower() or "No se encuentra".lower() in html_source.lower():
        return False
    else:
        #print("Existe Tag y si esta afiliado - solo por si acaso")
        return True

    '''
    blockTextList = re.findall('<td class="APLI_subtitulo2"(.*?)</td>', html_source, flags=re.S)

    if len(blockTextList) == 0:
        return True
    else:
        textInBlock = blockTextList[0]
        if "No hay resultado".lower() in textInBlock.lower():
            return False
        else:
            print("Existe Tag y si esta afiliado - solo por si acaso")
            return True
    '''


def scrappingOneDocument(browser,dni):
    browser.get(url)
    sleep(5)
    filenameScreenShot = getScreenShot(browser, dni)
    fileNameCaptcha = getCaptchaImages(filenameScreenShot, dni)
    fileNameGrayCaptcha = preprocessImage(fileNameCaptcha)

    numberInCaptcha = decodeNumberInImage(fileNameGrayCaptcha)
    print('numberInCaptcha: ' + str(numberInCaptcha))

    isCaptchaNumberOk = True
    results = {}

    if haveLettersInCaptcha(numberInCaptcha):
        print("El Captcha tiene letras: " + str(numberInCaptcha))
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

    html_source = browser.page_source

    if isCaptchaOK(html_source):
        print(html_source)

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
            results = getResultsInPage(browser, html_source, results)
        else:
            results['EsAfiliadoSPP'] = 'False'

        print(results)

    else:
        print("No se realizó correctamente el Captcha: " + str(numberInCaptcha))
        isCaptchaNumberOk = False

    return isCaptchaNumberOk,results

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

def main():

    filename = 'dnis10k.txt'
    dnis = readFile(filename)
    print(dnis)
    dnis = ['00006480','00008959','00009780','00011129','00023986']

    options = Options()
    options.add_argument("--headless")

    '''
    t0 = time.time()
    browser = webdriver.Firefox(firefox_options=options)
    sleep(2.5)

    isCaptchaNumberOk, result = scrappingOneDocument(browser, dnis[4])
    browser.quit()

    t1 = time.time()
    total_time = int(t1 - t0)
    print("Tiempo total de ejecución: " + str(datetime.timedelta(seconds=total_time)))
    '''


    dnisWithCaptchaError = []
    resultScrapping = []
    t0 = time.time()
    for i in range(5):
        print("Iteracion: " + str(i))
        browser = webdriver.Firefox(firefox_options=options)
        #sleep(2.5)
        isCaptchaNumberOk,result = scrappingOneDocument(browser,dnis[i])
        browser.quit()
        if isCaptchaNumberOk:
            resultScrapping.append(result)
        else:
            dnisWithCaptchaError.append(dnis[i])

    t1 = time.time()
    total_time = int(t1 - t0)
    print("Tiempo total de ejecución: " + str(datetime.timedelta(seconds=total_time)))
    print(dnisWithCaptchaError)
    #writeTsvFile(resultScrapping, 'ResultadosScrapping.tsv')
    #DNIsToResearch(dnisWithCaptchaError, "DnisPendientes.txt")



main()
#print(decodeNumberInImage('captchaB_00000395_Gray.jpg'))