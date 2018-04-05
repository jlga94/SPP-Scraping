def readFile(filename):
    with open(filename) as f:
        dnis = list(f.read().splitlines())
        return list(set(dnis))

def writeFile(filename,dnisPendientes):
    with open(filename,"w") as f:
        #f.write("DNIS\n")
        for dni in sorted(dnisPendientes):
            f.write(dni + "\n")


dnisScrapeados = set(readFile("dnisScraping_MUESTREO_2.txt"))
dnisTotal = set(readFile("Muestreo_DNIS_05_04_18.txt"))

dnisPendientes = dnisTotal.difference(dnisScrapeados)
writeFile("Muestreo_DNIS_05_04_18_v3.txt",dnisPendientes)
