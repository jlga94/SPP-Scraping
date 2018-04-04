def readFile(filename):
    with open(filename) as f:
        dnis = list(f.read().splitlines())
        return list(set(dnis))

def writeFile(filename,dnisPendientes):
    with open(filename,"w") as f:
        f.write("DNIS\n")
        for dni in sorted(dnisPendientes):
            f.write(dni + "\n")


dnisScrapeados = set(readFile("dnisScraping_3.txt"))
dnisTotal = set(readFile("data.txt"))

dnisPendientes = dnisTotal.difference(dnisScrapeados)
writeFile("dnisPendientes_15.txt",dnisPendientes)
