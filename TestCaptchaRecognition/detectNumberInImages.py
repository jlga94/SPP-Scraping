import cv2
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import numpy as np
import os
import csv

def writeFilenamesInDirectory(initialPath):
    imagesInPath = sorted(list(set(os.listdir(initialPath))))
    print(len(imagesInPath))
    outputFile = 'outputFile.txt'
    with open(outputFile, 'w') as f:
        for file in imagesInPath:
            f.write(file + '\n')


def preprocessImage(fileNameCaptcha):
    #Process the Image to make it gray for a better application of Pytesseract
    fileNameCaptchaSplitted = fileNameCaptcha.split('.')
    fileNameGrayCaptcha = fileNameCaptchaSplitted[0] + '_Dilatation.' + fileNameCaptchaSplitted[1]
    image = cv2.imread(fileNameCaptcha)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    gray = cv2.bitwise_not(gray)

    kernel = np.ones((2, 1), np.uint8)
    #kernel = cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))

    img_erosion = cv2.erode(gray, kernel, iterations=1)
    img_dilation = cv2.dilate(img_erosion, kernel, iterations=1)

    cv2.imwrite(fileNameGrayCaptcha, img_dilation)
    return fileNameGrayCaptcha

def decodeNumberInImage(fileNameGrayCaptcha):
    #Detects the number in the image using Pytesseract

    im = Image.open(fileNameGrayCaptcha)
    enhancer = ImageEnhance.Contrast(im)
    im = enhancer.enhance(5)
    numberInCaptcha = pytesseract.image_to_string(im, config='--psm 10 --eom 3 -c tessedit_char_whitelist=0123456789')
    return numberInCaptcha.replace(" ", "")


def readTestImagesFiles(filename):
    dictFileImages = {}
    with open(filename,'r') as f:
        csvReader = csv.reader(f)
        for row in csvReader:
            #print(row)
            dictFileImages[row[0]] = row[1]
    return dictFileImages


def testImages(testFilesDict,initialPath):

    numCorrectNumber = 0
    iteration = 1
    for file in sorted(testFilesDict.keys()):
        fileNameCaptcha = preprocessImage(initialPath + '/' + file)
        number = decodeNumberInImage(fileNameCaptcha)
        print("Iteration: " + str(iteration) + " - Filename: " + file + " - Expected: " + testFilesDict[file] + ' - Number: '+ number)
        if testFilesDict[file] == number:
            numCorrectNumber += 1
        iteration += 1

    print("De: " + str(len(testFilesDict.keys())) + " fueron correctos: " + str(numCorrectNumber))



#writeFilenamesInDirectory('Catpchas')

testFilesDict = readTestImagesFiles('captchas.csv')
testImages(testFilesDict,'Captchas')