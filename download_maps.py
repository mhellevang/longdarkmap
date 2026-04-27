#!/usr/bin/env python3
"""Download region maps (Pilgrim/Voyageur/Stalker + Interloper/Misery variants)
from the Steam Community guide.

Source: https://steamcommunity.com/sharedfiles/filedetails/?id=3255435617
        "Updated Region Maps [2025]" by HokuOwl
"""

import os
import urllib.request

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Each region maps to (pvs_url, loper_url).
# loper_url may be None for regions that only ship a single variant.
REGIONS: dict[str, tuple[str, str | None]] = {
    "Mystery Lake": (
        "https://images.steamusercontent.com/ugc/15476628118068146896/964E7DB3A8CF5601A727E12FAC153C8DEB0884AC/",
        "https://images.steamusercontent.com/ugc/12181171108607855328/BB9FA07418F10BAE5DA9748A27FD9CB8E1C9AE02/",
    ),
    "Coastal Highway": (
        "https://images.steamusercontent.com/ugc/9516403236853107764/7C78444F11075F0CA7801155D89B604BEA222670/",
        "https://images.steamusercontent.com/ugc/9475295296023591018/8FA0642300D3597E7E2EB050545003226E35316F/",
    ),
    "Pleasant Valley": (
        "https://images.steamusercontent.com/ugc/9495851414846658845/BF9179F621AD5200996B7A4EE8F3BD7309B37470/",
        "https://images.steamusercontent.com/ugc/17407195001097129457/5D4565517DAE352E7A400A381BD9FE14DF5E54C9/",
    ),
    "Desolation Point": (
        "https://images.steamusercontent.com/ugc/16057301526255972814/3A4FB4945D272F27EEBCEAFF483C452374C935CE/",
        "https://images.steamusercontent.com/ugc/17555198380887569827/EBDC7B329B52AF9B8F6F0A907F90EAAFFB8ED230/",
    ),
    "Timberwolf Mountain": (
        "https://images.steamusercontent.com/ugc/18019470743317950368/FE3E7A2C5308EDFB4C43A5B8BB8230426A9D19A1/",
        "https://images.steamusercontent.com/ugc/16015738267194102941/276C79D3CAE76AA15CBC3C55021299B5A7A13956/",
    ),
    "Forlorn Muskeg": (
        "https://images.steamusercontent.com/ugc/15190933220557313885/B5B3BC2BABBF9E90336E0AF50BC7379E197410A9/",
        "https://images.steamusercontent.com/ugc/13120278709304539605/D8F929B355A896EBCA2F5EA01775F6B56A395D5E/",
    ),
    "Broken Railroad": (
        "https://images.steamusercontent.com/ugc/37819645136703055/8674195A3C3098E9878C83512BF03B9CF9488AA9/",
        "https://images.steamusercontent.com/ugc/37819645136703248/C355359C5487B23BF2BBD00EFE4CEA054573F085/",
    ),
    "Mountain Town": (
        "https://images.steamusercontent.com/ugc/17330490373698343471/CDCE98E29CE9BD56C91A8C7A290564ECD6757783/",
        "https://images.steamusercontent.com/ugc/16875759404303424817/0F18A56018496256E69826BF10AFA67B4B80F838/",
    ),
    "Hushed River Valley": (
        "https://images.steamusercontent.com/ugc/11738172134438972729/9DB6EBD8279EB82FA9041ACF286CFF8F51C280D0/",
        "https://images.steamusercontent.com/ugc/11458033074726588907/497E67C51FD94E97E14086322E2DFDBC5E8BA64F/",
    ),
    "Bleak Inlet": (
        "https://images.steamusercontent.com/ugc/15963475340427975657/8F8932D34BDB1AEECBD81F0DF0D4FF0A8F9B895F/",
        "https://images.steamusercontent.com/ugc/12747202571525077315/F6C8FEC4B25C2DCD7FF82D5D8E0DC38C35D43C68/",
    ),
    "Ash Canyon": (
        "https://images.steamusercontent.com/ugc/12423718121825641694/1436C3EE25819AC99F2765E65FF87EB91FEE82C7/",
        "https://images.steamusercontent.com/ugc/11775972934425462577/06F5B6240C384475FA96DE6B3D656E9B51CB5D38/",
    ),
    "Blackrock": (
        "https://images.steamusercontent.com/ugc/13725529750150141786/377C02F990FA45DF8EBAC15FFFA435457554996A/",
        "https://images.steamusercontent.com/ugc/13819165643333898105/D35F9682041D607CC43CEF91ECBF28A57F5F2098/",
    ),
    "Transfer Pass": (
        "https://images.steamusercontent.com/ugc/37819645136731165/2F143B1F4452AE9F9688686307AEAFE77D64CD0C/",
        "https://images.steamusercontent.com/ugc/37819645136731499/1A9515074C6E2DFE5960A3886C0534BB20265B41/",
    ),
    "Forsaken Airfield": (
        "https://images.steamusercontent.com/ugc/16913663260970933264/FB109BD04EA8ED996F248F237F7DDD07BB98CF4B/",
        "https://images.steamusercontent.com/ugc/10851226945735149924/44743CB450B469D5596D322623AAC3DF36CAAC04/",
    ),
    "Zone of Contamination": (
        "https://images.steamusercontent.com/ugc/10376660445325975268/BCF107D90B0B9E2D6D301731D0DFC0975F8E7EDB/",
        "https://images.steamusercontent.com/ugc/10958718653805267230/55045BF44ACECE678A21417948002A17C0AC973A/",
    ),
    "Sundered Pass": (
        "https://images.steamusercontent.com/ugc/13234845787225905708/3CCD158148CAF4F6E5651269D63AA378F2C7B361/",
        "https://images.steamusercontent.com/ugc/16979676319684412643/EE2D7A9F25D9742C4F9256678705F0A0B8286A48/",
    ),
    "Ravine": (
        "https://images.steamusercontent.com/ugc/37819645136730001/C7DC749F7E776CAA177FC3B5A0E679D01CF8B63C/",
        "https://images.steamusercontent.com/ugc/37819645136730182/3961F5EF2C43A79B7F730CD52F7EE1B8554EB1C6/",
    ),
    "Winding River & Carter Hydro Dam": (
        "https://images.steamusercontent.com/ugc/37819645136732320/2F95CDD280AF1BD5D52072DD0B242519C099F433/",
        "https://images.steamusercontent.com/ugc/37819645136732699/CD74A44711B35D34DC967262E7E90ECAA227B999/",
    ),
    # Crumbling Highway only ships a single all-difficulty variant.
    "Crumbling Highway": (
        "https://images.steamusercontent.com/ugc/37819645136723139/6CF8012DCBEE7E4C21BAA1373D076B13C8D2E545/",
        None,
    ),
    "Keeper's Pass": (
        "https://images.steamusercontent.com/ugc/15159145128947408591/484B84DD777B5E0742837BB86857EAA524315342/",
        "https://images.steamusercontent.com/ugc/16055965560201475697/BF5677731E7CEA8A282819D01C96AB5486A6E478/",
    ),
    "Far Range Branch Line": (
        "https://images.steamusercontent.com/ugc/12967305776514005370/390463FA1E9F539BCB876BF25E3065276D75DED2/",
        "https://images.steamusercontent.com/ugc/10893453294679762817/2CC6706F93D63DD60EF48511CB98A2B27EF149A9/",
    ),
}

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
}


def region_to_filename(name: str) -> str:
    return name.lower().replace(" ", "_").replace("'", "").replace("&", "and")


def download(url: str, dest: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        ct = resp.headers.get_content_type()
        ext = CONTENT_TYPE_EXT.get(ct, ".jpg")
        path = dest + ext
        if os.path.exists(path):
            return path, True
        with open(path, "wb") as f:
            f.write(resp.read())
    return path, False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = sum(2 if loper else 1 for _, loper in REGIONS.values())
    print(f"Laster ned {total} kart ({len(REGIONS)} regioner, PVS + Loper) ...\n")

    downloaded = skipped = failed = 0
    step = 0

    for region, (pvs_url, loper_url) in REGIONS.items():
        base = os.path.join(OUTPUT_DIR, region_to_filename(region))
        jobs = [("PVS", pvs_url, base)]
        if loper_url:
            jobs.append(("Loper", loper_url, base + "_loper"))

        for variant, url, dest in jobs:
            step += 1
            print(f"[{step}/{total}] {region} ({variant})")
            try:
                path, existed = download(url, dest)
                size_kb = os.path.getsize(path) // 1024
                if existed:
                    print(f"  Hopper over (finnes): {os.path.basename(path)}")
                    skipped += 1
                else:
                    print(f"  OK -> {os.path.basename(path)} ({size_kb} KB)")
                    downloaded += 1
            except Exception as e:
                print(f"  Feil: {e}")
                failed += 1

    print(f"\nFerdig! Lastet ned: {downloaded}, Hoppet over: {skipped}, Feil: {failed}")
    print(f"Bilder lagret i: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
