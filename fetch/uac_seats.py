"""Download UAC's post-return 分發入學 seat table."""

from concurrent.futures import ThreadPoolExecutor

from fetch.high_school import download


YEARS = tuple(str(year) for year in range(107, 116))


def source(year):
    return {
        "dir": "uac",
        "filename": f"{year}-count.xlsx",
        "url": f"https://www2.uac.edu.tw/uac{year}_note/count.xlsx",
    }


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda year: download(source(year), "uac"), YEARS))


if __name__ == "__main__":
    main()
